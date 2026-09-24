#!/usr/bin/env python3
"""Report whether the handbook submission guard is installed for this user. Never installs.

States: `enabled` (Claude: hook and handler current), `configured` (Codex: hook and handler
current, trust not inferred -- the operator grants it in `/hooks`), `missing`, `stale`,
`broken`.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from session_logging import (  # noqa: E402
    SessionLoggingError,
    codex_policy_problem,
    read_json_object,
    read_toml_object,
    require_regular_or_absent,
)

_spec = importlib.util.spec_from_file_location(
    "install_submission_guard", Path(__file__).resolve().parent / "install-submission-guard.py"
)
_ISG = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ISG)


def inspect(frontend: str, user_root: Path, root: Path) -> dict[str, str]:
    def result(status: str, message: str) -> dict[str, str]:
        return {"frontend": frontend, "status": status, "message": message}

    try:
        source = _ISG.source_hook(root, frontend)
        installed = _ISG.installed_hook(user_root, frontend)
        require_regular_or_absent(installed)
    except SessionLoggingError as exc:
        return result("broken", str(exc))
    if not installed.is_file():
        return result("missing", "the submission guard hook is not installed")
    if installed.read_bytes() != source.read_bytes():
        return result("stale", "the installed guard hook differs from this handbook")

    configs = []
    try:
        if frontend == "claude":
            settings = user_root / ".claude" / "settings.json"
            if not settings.is_file():
                return result("broken", "the Claude settings file is missing")
            configs.append(read_json_object(settings))
        else:
            hooks_json = user_root / ".codex" / "hooks.json"
            config_toml = user_root / ".codex" / "config.toml"
            if hooks_json.is_file():
                configs.append(read_json_object(hooks_json))
            if config_toml.is_file():
                toml_config = read_toml_object(config_toml)
                problem = codex_policy_problem(toml_config)
                if problem:
                    return result("broken", problem)
                configs.append(toml_config)
        handlers = [h for config in configs for h in _ISG.guard_handlers(config, frontend)]
    except SessionLoggingError as exc:
        return result("broken", str(exc))
    if not handlers:
        return result("missing", "no PreToolUse handler invokes the guard hook")
    if len(handlers) > 1:
        return result("broken", "more than one PreToolUse handler invokes the guard hook")
    if not _ISG.handler_is_current(handlers[0], frontend):
        return result("stale", "the PreToolUse handler differs from the handbook's")
    if frontend == "codex":
        return result("configured", "hook and handler are current; trust is granted in /hooks and "
                                    "is not inferred from configuration files")
    return result("enabled", "hook and PreToolUse handler are current")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frontend", choices=("claude", "codex"), required=True)
    ap.add_argument("--user-root", type=Path, default=Path.home())
    ap.add_argument("--handbook-root", type=Path)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    root = args.handbook_root.resolve() if args.handbook_root else Path(__file__).resolve().parents[1]
    outcome = inspect(args.frontend, args.user_root.resolve(), root)
    if args.json:
        print(json.dumps(outcome))
    else:
        print(f"submission guard: {outcome['status']} — {outcome['message']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
