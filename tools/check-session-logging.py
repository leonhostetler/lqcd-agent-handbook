#!/usr/bin/env python3
"""Report whether handbook-managed user-wide session logging is configured."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys

from session_logging import (
    SessionLoggingError,
    codex_policy_problem,
    command_handlers,
    handler_is_current,
    installed_logger,
    read_json_object,
    read_toml_object,
    require_regular_or_absent,
    source_logger,
    targets_frontend,
)


def result(status: str, message: str, frontend: str) -> dict[str, str]:
    return {"frontend": frontend, "status": status, "message": message}


def inspect(frontend: str, user_root: Path, handbook_root: Path) -> dict[str, str]:
    source = source_logger(handbook_root, frontend)
    installed = installed_logger(user_root, frontend)
    try:
        require_regular_or_absent(installed)
    except SessionLoggingError as exc:
        return result("broken", str(exc), frontend)
    if not installed.is_file():
        return result("missing", "the handbook-managed logger is not installed", frontend)
    if installed.read_bytes() != source.read_bytes():
        return result("stale", "the installed logger differs from this handbook", frontend)

    configs: list[tuple[str, dict]] = []
    if frontend == "claude":
        if shutil.which("jq") is None:
            return result("broken", "jq is required by the Claude logger", frontend)
        settings = user_root / ".claude/settings.json"
        if not settings.is_file():
            return result("broken", "the Claude settings file is missing", frontend)
        configs.append((str(settings), read_json_object(settings)))
    else:
        hooks_json = user_root / ".codex/hooks.json"
        config_toml = user_root / ".codex/config.toml"
        if hooks_json.is_file():
            configs.append((str(hooks_json), read_json_object(hooks_json)))
        if config_toml.is_file():
            toml_config = read_toml_object(config_toml)
            policy_problem = codex_policy_problem(toml_config)
            if policy_problem:
                return result("broken", policy_problem, frontend)
            configs.append((str(config_toml), toml_config))

    targeted: list[dict] = []
    for _, config in configs:
        targeted.extend(
            handler
            for handler in command_handlers(config)
            if targets_frontend(handler, frontend)
        )
    if not targeted:
        return result("broken", "the global Stop handler is not configured", frontend)
    if len(targeted) > 1:
        return result("broken", "duplicate global session-log handlers are configured", frontend)
    if not handler_is_current(targeted[0], frontend):
        return result("stale", "the global Stop handler differs from the handbook", frontend)

    if frontend == "codex":
        return result(
            "configured",
            "configuration is current; Codex hook trust must be checked in /hooks",
            frontend,
        )
    return result("enabled", "configuration and logger are current", frontend)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frontend", choices=("claude", "codex"), required=True)
    parser.add_argument("--user-root", type=Path, default=Path.home())
    parser.add_argument("--handbook-root", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    handbook_root = (
        args.handbook_root.resolve()
        if args.handbook_root
        else Path(__file__).resolve().parents[1]
    )
    try:
        state = inspect(args.frontend, args.user_root.resolve(), handbook_root)
    except (OSError, SessionLoggingError) as exc:
        state = result("broken", str(exc), args.frontend)
    if args.json:
        print(json.dumps(state, sort_keys=True))
    else:
        print(f"session logging: {state['status']} — {state['message']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
