#!/usr/bin/env python3
"""Install one handbook session logger into the current user's global config."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import stat
import sys
from typing import Any

from session_logging import (
    SessionLoggingError,
    codex_policy_problem,
    command_handlers,
    expected_handler,
    handler_is_current,
    install_logger,
    installed_logger,
    merge_json_handler,
    read_json_object,
    read_toml_object,
    require_regular_or_absent,
    source_logger,
    stop_groups,
    targets_frontend,
    toml_module,
    write_with_backup,
)


def json_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2) + "\n").encode()


def load_json_or_empty(path: Path) -> dict[str, Any]:
    return read_json_object(path) if path.is_file() else {}


def append_toml_handler(path: Path, handler: dict[str, Any]) -> bytes:
    text = path.read_text()
    if text and not text.endswith("\n"):
        text += "\n"
    text += (
        "\n[[hooks.Stop]]\n"
        "\n[[hooks.Stop.hooks]]\n"
        'type = "command"\n'
        f"command = {handler['command']!r}\n"
        f"timeout = {handler['timeout']}\n"
        f"statusMessage = {handler['statusMessage']!r}\n"
    )
    module = toml_module()
    if module is None:
        raise SessionLoggingError(
            "Python 3.11+ or tomli is required to merge inline Codex hooks"
        )
    try:
        module.loads(text)
    except ValueError as exc:
        raise SessionLoggingError(f"proposed Codex TOML is invalid: {exc}") from exc
    return text.encode()


def current_mode(path: Path, default: int = 0o600) -> int:
    return stat.S_IMODE(path.stat().st_mode) if path.exists() else default


def install_claude(
    user_root: Path, source: Path
) -> tuple[bool, list[tuple[Path, Path | None]]]:
    if shutil.which("jq") is None:
        raise SessionLoggingError("jq is required before installing Claude logging")
    settings = user_root / ".claude/settings.json"
    destination = installed_logger(user_root, "claude")
    require_regular_or_absent(settings)
    require_regular_or_absent(destination)
    config = load_json_or_empty(settings)
    handler = expected_handler("claude")
    config_changed = merge_json_handler(config, "claude", handler)

    script_changed = (
        not destination.exists()
        or destination.read_bytes() != source.read_bytes()
        or current_mode(destination, 0o700) != 0o700
    )
    changes: list[tuple[Path, Path | None]] = []
    if script_changed:
        changes.append((destination, install_logger(source, destination)))
    if config_changed or not settings.exists():
        saved = write_with_backup(settings, json_bytes(config))
        changes.append((settings, saved))
    return bool(changes), changes


def install_codex(
    user_root: Path, source: Path
) -> tuple[bool, list[tuple[Path, Path | None]]]:
    python_path = sys.executable
    if not python_path or not os.path.isabs(python_path):
        raise SessionLoggingError("an absolute Python executable is required")
    handler = expected_handler("codex", python_path)
    hooks_json = user_root / ".codex/hooks.json"
    config_toml = user_root / ".codex/config.toml"
    destination = installed_logger(user_root, "codex")
    require_regular_or_absent(hooks_json)
    require_regular_or_absent(config_toml)
    require_regular_or_absent(destination)
    json_config = load_json_or_empty(hooks_json)
    toml_config: dict[str, Any] = {}
    if config_toml.is_file():
        toml_config = read_toml_object(config_toml)
        problem = codex_policy_problem(toml_config)
        if problem:
            raise SessionLoggingError(problem)

    json_targets = [
        item
        for item in command_handlers(json_config)
        if targets_frontend(item, "codex")
    ]
    toml_targets = [
        item
        for item in command_handlers(toml_config)
        if targets_frontend(item, "codex")
    ]
    toml_imported_claude = [
        item
        for item in command_handlers(toml_config)
        if targets_frontend(item, "claude")
    ]
    if len(json_targets) + len(toml_targets) > 1:
        raise SessionLoggingError(
            "duplicate Codex session-log handlers exist; review them manually"
        )

    config_write: tuple[Path, bytes] | None = None
    if toml_imported_claude:
        raise SessionLoggingError(
            "config.toml contains a Claude session logger; replace that inline handler "
            "manually before installing the Codex adapter"
        )
    if toml_targets:
        if not handler_is_current(toml_targets[0], "codex"):
            raise SessionLoggingError(
                "the inline Codex session-log handler differs from the handbook; "
                "review config.toml manually"
            )
    elif json_targets or hooks_json.is_file() or not stop_groups(toml_config):
        changed = merge_json_handler(json_config, "codex", handler)
        if changed or not hooks_json.exists():
            config_write = (hooks_json, json_bytes(json_config))
    else:
        config_write = (config_toml, append_toml_handler(config_toml, handler))

    script_changed = (
        not destination.exists()
        or destination.read_bytes() != source.read_bytes()
        or current_mode(destination, 0o700) != 0o700
    )
    changes: list[tuple[Path, Path | None]] = []
    if script_changed:
        changes.append((destination, install_logger(source, destination)))
    if config_write is not None:
        path, data = config_write
        changes.append((path, write_with_backup(path, data)))
    return bool(changes), changes


def display_path(path: Path, user_root: Path) -> str:
    try:
        return f"~/{path.relative_to(user_root)}"
    except ValueError:
        return str(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frontend", choices=("claude", "codex"), required=True)
    parser.add_argument("--user-root", type=Path, default=Path.home())
    parser.add_argument("--handbook-root", type=Path)
    args = parser.parse_args()
    user_root = args.user_root.resolve()
    if user_root == Path(user_root.anchor):
        print(
            "session logging was not installed: user root cannot be filesystem root",
            file=sys.stderr,
        )
        return 2
    handbook_root = (
        args.handbook_root.resolve()
        if args.handbook_root
        else Path(__file__).resolve().parents[1]
    )
    try:
        source = source_logger(handbook_root, args.frontend)
        if args.frontend == "claude":
            changed, changes = install_claude(user_root, source)
        else:
            changed, changes = install_codex(user_root, source)
    except (OSError, SessionLoggingError) as exc:
        print(f"session logging was not installed: {exc}", file=sys.stderr)
        return 2

    if not changed:
        print(f"{args.frontend} session logging is already current")
    else:
        for path, saved in changes:
            message = f"updated {display_path(path, user_root)}"
            if saved is not None:
                message += f" (backup: {display_path(saved, user_root)})"
            print(message)
    if args.frontend == "claude":
        print("Reload hooks with /hooks or restart Claude Code, then complete one turn.")
    else:
        print(
            "Open /hooks, review and trust the Codex Stop logger, then complete one turn."
        )
        print("Do not edit trusted_hash or bypass hook trust.")
    print("Session logs contain verbatim conversation text and are not secret-scrubbed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
