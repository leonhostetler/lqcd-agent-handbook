#!/usr/bin/env python3
"""Install the handbook submission guard into the current user's frontend configuration.

Offer-only, like the session-logging installer: nothing here runs at startup, and the
startup checker (`check-submission-guard.py`) only reports. The guard is a `PreToolUse`
hook on the frontend's shell tool; the installed shim carries no handbook path and acts
only in a session launched through the handbook (see tools/submission-guard-hook.sh).

Both frontends implement the same command-hook protocol -- a `PreToolUse` event, JSON on
stdin carrying `tool_input.command` and `cwd`, and exit status 2 with the reason on stderr
to block -- so the same shim serves both. They differ in where the handler lives and in
trust: Claude Code loads `~/.claude/settings.json`; Codex reads `~/.codex/hooks.json` or
inline `hooks` tables in `~/.codex/config.toml`, and runs a non-managed command hook only
after the operator reviews and trusts that exact definition through `/hooks`. This tool
never writes trust state; a guard the operator did not trust is not enforcing, and the
checker says so.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import stat
import sys
from typing import Any

import yaml

from session_logging import (
    SessionLoggingError,
    codex_policy_problem,
    read_json_object,
    read_toml_object,
    require_regular_or_absent,
    toml_module,
    write_with_backup,
)

INSTALLED = {
    "claude": Path(".claude/submission_guard.sh"),
    "codex": Path(".codex/submission_guard.sh"),
}
MARKERS = {
    "claude": ".claude/submission_guard.sh",
    "codex": ".codex/submission_guard.sh",
}
STATUS_MESSAGE = "Checking batch-script submission readiness"
MATCHER = "Bash"


def guard_manifest(root: Path) -> dict[str, Any]:
    config = yaml.safe_load((root / "handbook.yaml").read_text())
    guard = config.get("submission_guard") if isinstance(config, dict) else None
    if not isinstance(guard, dict):
        raise SessionLoggingError("handbook.yaml lacks a submission_guard block")
    return guard


def source_hook(root: Path, frontend: str) -> Path:
    frontends = guard_manifest(root).get("frontends") or {}
    spec = frontends.get(frontend) if isinstance(frontends, dict) else None
    if not isinstance(spec, dict) or not spec.get("hook"):
        raise SessionLoggingError(f"no submission-guard hook is recorded for {frontend}")
    path = root / str(spec["hook"])
    if not path.is_file():
        raise SessionLoggingError(f"submission-guard hook is missing: {spec['hook']}")
    return path


def installed_hook(user_root: Path, frontend: str) -> Path:
    return user_root / INSTALLED[frontend]


def expected_handler(frontend: str) -> dict[str, Any]:
    return {
        "type": "command",
        "command": f'bash "$HOME/{MARKERS[frontend]}"',
        "timeout": 120,
        "statusMessage": STATUS_MESSAGE,
    }


def pre_tool_groups(config: dict[str, Any]) -> list[dict[str, Any]]:
    hooks = config.get("hooks")
    if hooks is None:
        return []
    if not isinstance(hooks, dict):
        raise SessionLoggingError("hooks must be a mapping")
    groups = hooks.get("PreToolUse", [])
    if not isinstance(groups, list) or not all(isinstance(g, dict) for g in groups):
        raise SessionLoggingError("hooks.PreToolUse must be a list of mappings")
    return groups


def guard_handlers(config: dict[str, Any], frontend: str) -> list[dict[str, Any]]:
    found = []
    for group in pre_tool_groups(config):
        handlers = group.get("hooks", []) or []
        if not isinstance(handlers, list):
            raise SessionLoggingError("hooks.PreToolUse[].hooks must be a list")
        for handler in handlers:
            if isinstance(handler, dict) and MARKERS[frontend] in str(handler.get("command", "")):
                found.append(handler)
    return found


def handler_is_current(handler: dict[str, Any], frontend: str) -> bool:
    return handler == expected_handler(frontend)


def merge_handler(config: dict[str, Any], frontend: str) -> bool:
    """Ensure exactly one current guard handler in a PreToolUse group matching the shell tool."""
    current = guard_handlers(config, frontend)
    if len(current) == 1 and handler_is_current(current[0], frontend):
        return False
    hooks = config.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise SessionLoggingError("hooks must be a mapping")
    groups = hooks.setdefault("PreToolUse", [])
    if not isinstance(groups, list):
        raise SessionLoggingError("hooks.PreToolUse must be a list")
    marker = MARKERS[frontend]
    target = None
    for group in groups:
        handlers = group.setdefault("hooks", [])
        kept = [h for h in handlers if not (isinstance(h, dict) and marker in str(h.get("command", "")))]
        if len(kept) != len(handlers):
            group["hooks"] = kept
    for group in groups:
        if group.get("matcher") == MATCHER:
            target = group
            break
    if target is None:
        target = {"matcher": MATCHER, "hooks": []}
        groups.append(target)
    target.setdefault("hooks", []).append(expected_handler(frontend))
    return True


def append_toml_handler(path: Path, handler: dict[str, Any]) -> bytes:
    text = path.read_text()
    if text and not text.endswith("\n"):
        text += "\n"
    text += (
        "\n[[hooks.PreToolUse]]\n"
        f'matcher = "{MATCHER}"\n'
        "\n[[hooks.PreToolUse.hooks]]\n"
        'type = "command"\n'
        f"command = {handler['command']!r}\n"
        f"timeout = {handler['timeout']}\n"
        f"statusMessage = {handler['statusMessage']!r}\n"
    )
    module = toml_module()
    if module is None:
        raise SessionLoggingError("Python 3.11+ or tomli is required to merge inline Codex hooks")
    try:
        module.loads(text)
    except ValueError as exc:
        raise SessionLoggingError(f"proposed Codex TOML is invalid: {exc}") from exc
    return text.encode()


def install_shim(source: Path, destination: Path, changes: list) -> None:
    if (not destination.exists() or destination.read_bytes() != source.read_bytes()
            or stat.S_IMODE(destination.stat().st_mode) != 0o700):
        saved = write_with_backup(destination, source.read_bytes(), default_mode=0o700)
        destination.chmod(0o700)
        changes.append((destination, saved))


def install_claude(user_root: Path, source: Path) -> list[tuple[Path, Path | None]]:
    settings = user_root / ".claude" / "settings.json"
    destination = installed_hook(user_root, "claude")
    require_regular_or_absent(settings)
    require_regular_or_absent(destination)
    config = read_json_object(settings) if settings.is_file() else {}
    changes: list[tuple[Path, Path | None]] = []
    install_shim(source, destination, changes)
    if merge_handler(config, "claude") or not settings.exists():
        data = (json.dumps(config, indent=2) + "\n").encode()
        changes.append((settings, write_with_backup(settings, data)))
    return changes


def install_codex(user_root: Path, source: Path) -> list[tuple[Path, Path | None]]:
    hooks_json = user_root / ".codex" / "hooks.json"
    config_toml = user_root / ".codex" / "config.toml"
    destination = installed_hook(user_root, "codex")
    require_regular_or_absent(hooks_json)
    require_regular_or_absent(config_toml)
    require_regular_or_absent(destination)
    json_config = read_json_object(hooks_json) if hooks_json.is_file() else {}
    toml_config: dict[str, Any] = {}
    if config_toml.is_file():
        toml_config = read_toml_object(config_toml)
        problem = codex_policy_problem(toml_config)
        if problem:
            raise SessionLoggingError(problem)
    json_targets = guard_handlers(json_config, "codex")
    toml_targets = guard_handlers(toml_config, "codex")
    if len(json_targets) + len(toml_targets) > 1:
        raise SessionLoggingError("duplicate Codex submission-guard handlers exist; review them manually")

    changes: list[tuple[Path, Path | None]] = []
    install_shim(source, destination, changes)
    handler = expected_handler("codex")
    if toml_targets:
        if not handler_is_current(toml_targets[0], "codex"):
            raise SessionLoggingError(
                "the inline Codex submission-guard handler differs from the handbook; "
                "review config.toml manually"
            )
    elif json_targets or hooks_json.is_file() or not toml_config.get("hooks"):
        # hooks.json is the home unless the operator already keeps command hooks inline
        # in config.toml -- for any event, since one hooks file per frontend is the rule.
        if merge_handler(json_config, "codex") or not hooks_json.exists():
            data = (json.dumps(json_config, indent=2) + "\n").encode()
            changes.append((hooks_json, write_with_backup(hooks_json, data)))
    else:
        changes.append((config_toml, write_with_backup(config_toml, append_toml_handler(config_toml, handler))))
    return changes


def display(path: Path, user_root: Path) -> str:
    try:
        return f"~/{path.relative_to(user_root)}"
    except ValueError:
        return str(path)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frontend", choices=("claude", "codex"), required=True)
    ap.add_argument("--user-root", type=Path, default=Path.home())
    ap.add_argument("--handbook-root", type=Path)
    args = ap.parse_args()
    user_root = args.user_root.resolve()
    if user_root == Path(user_root.anchor):
        print("submission guard was not installed: user root cannot be filesystem root", file=sys.stderr)
        return 2
    root = args.handbook_root.resolve() if args.handbook_root else Path(__file__).resolve().parents[1]
    try:
        source = source_hook(root, args.frontend)
        if args.frontend == "claude":
            changes = install_claude(user_root, source)
        else:
            changes = install_codex(user_root, source)
    except (OSError, SessionLoggingError) as exc:
        print(f"submission guard was not installed: {exc}", file=sys.stderr)
        return 2
    if not changes:
        print(f"{args.frontend} submission guard is already current")
    else:
        for path, saved in changes:
            line = f"updated {display(path, user_root)}"
            if saved is not None:
                line += f" (backup: {display(saved, user_root)})"
            print(line)
    if args.frontend == "claude":
        print("Reload hooks with /hooks or restart Claude Code.")
    else:
        print("Open /hooks, review and trust the PreToolUse submission guard, then it enforces.")
        print("Do not edit trusted_hash or bypass hook trust; an untrusted guard is not enforcing.")
    print("The guard acts only in sessions launched through the handbook (LQCD_HANDBOOK set) and "
          "refuses a submit command whose script has not passed the checker and the dry-run harness.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
