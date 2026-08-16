#!/usr/bin/env python3
"""Shared inspection and installation helpers for user-wide session logging."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
from typing import Any

import yaml


LOGGER_TARGETS = {
    "claude": Path(".claude/log_session.sh"),
    "codex": Path(".codex/log_session.py"),
}
TARGET_MARKERS = {
    "claude": ".claude/log_session.sh",
    "codex": ".codex/log_session.py",
}


class SessionLoggingError(RuntimeError):
    """A configuration condition that must be reported rather than guessed around."""


def load_manifest(root: Path) -> dict[str, Any]:
    value = yaml.safe_load((root / "handbook.yaml").read_text())
    if not isinstance(value, dict):
        raise SessionLoggingError("handbook.yaml is not a mapping")
    logging = value.get("session_logging")
    if not isinstance(logging, dict):
        raise SessionLoggingError("handbook.yaml has no session_logging mapping")
    return logging


def source_logger(root: Path, frontend: str) -> Path:
    logging = load_manifest(root)
    frontends = logging.get("frontends")
    if not isinstance(frontends, dict) or frontend not in frontends:
        raise SessionLoggingError(f"no session-logging adapter for {frontend}")
    spec = frontends[frontend]
    if not isinstance(spec, dict) or not isinstance(spec.get("logger"), str):
        raise SessionLoggingError(f"invalid session-logging adapter for {frontend}")
    path = root / spec["logger"]
    if not path.is_file():
        raise SessionLoggingError(f"session logger is missing: {spec['logger']}")
    return path


def installed_logger(user_root: Path, frontend: str) -> Path:
    return user_root / LOGGER_TARGETS[frontend]


def read_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise SessionLoggingError(f"cannot parse {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SessionLoggingError(f"{path} must contain a JSON object")
    return value


def toml_module():
    try:
        import tomllib

        return tomllib
    except ImportError:
        try:
            import tomli

            return tomli
        except ImportError:
            return None


def read_toml_object(path: Path) -> dict[str, Any]:
    module = toml_module()
    if module is None:
        raise SessionLoggingError(
            "Python 3.11+ or the tomli package is required to inspect inline Codex hooks"
        )
    try:
        with path.open("rb") as stream:
            value = module.load(stream)
    except (OSError, ValueError) as exc:
        raise SessionLoggingError(f"cannot parse {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SessionLoggingError(f"{path} must contain a TOML table")
    return value


def stop_groups(config: dict[str, Any]) -> list[dict[str, Any]]:
    hooks = config.get("hooks")
    if hooks is None:
        return []
    if not isinstance(hooks, dict):
        raise SessionLoggingError("hooks must be a mapping")
    groups = hooks.get("Stop", [])
    if not isinstance(groups, list):
        raise SessionLoggingError("hooks.Stop must be a list")
    if not all(isinstance(group, dict) for group in groups):
        raise SessionLoggingError("every hooks.Stop entry must be a mapping")
    return groups


def command_handlers(config: dict[str, Any]) -> list[dict[str, Any]]:
    handlers: list[dict[str, Any]] = []
    for group in stop_groups(config):
        raw_handlers = group.get("hooks", [])
        if not isinstance(raw_handlers, list):
            raise SessionLoggingError("hooks.Stop[].hooks must be a list")
        if not all(isinstance(handler, dict) for handler in raw_handlers):
            raise SessionLoggingError("every Stop handler must be a mapping")
        handlers.extend(raw_handlers)
    return handlers


def targets_frontend(handler: dict[str, Any], frontend: str) -> bool:
    command = handler.get("command")
    return isinstance(command, str) and TARGET_MARKERS[frontend] in command


def expected_handler(frontend: str, python_path: str | None = None) -> dict[str, Any]:
    if frontend == "claude":
        command = 'bash "$HOME/.claude/log_session.sh"'
    else:
        if not python_path:
            raise SessionLoggingError("an absolute python3 path is required for Codex")
        command = f'{python_path} "$HOME/.codex/log_session.py"'
    return {
        "type": "command",
        "command": command,
        "timeout": 30,
        "statusMessage": "Logging session transcript",
    }


def handler_is_current(
    handler: dict[str, Any], frontend: str, python_path: str | None = None
) -> bool:
    if handler.get("type") != "command":
        return False
    if handler.get("timeout") != 30:
        return False
    if handler.get("statusMessage") != "Logging session transcript":
        return False
    command = handler.get("command")
    if not isinstance(command, str):
        return False
    if frontend == "claude":
        return command == expected_handler("claude")["command"]
    if TARGET_MARKERS["codex"] not in command:
        return False
    if python_path is None:
        return bool(re.fullmatch(r'/[^\s]+\s+"\$HOME/\.codex/log_session\.py"', command))
    return command == expected_handler("codex", python_path)["command"]


def codex_policy_problem(config: dict[str, Any]) -> str | None:
    features = config.get("features")
    if isinstance(features, dict):
        if features.get("hooks") is False or features.get("codex_hooks") is False:
            return "Codex hooks are disabled in config.toml"
    history = config.get("history")
    if isinstance(history, dict) and history.get("persistence") == "none":
        return "Codex transcript persistence is disabled"
    return None


def merge_json_handler(
    config: dict[str, Any], frontend: str, handler: dict[str, Any]
) -> bool:
    existing_handlers = command_handlers(config)
    targeted = [
        item for item in existing_handlers if targets_frontend(item, frontend)
    ]
    imported_claude = (
        frontend == "codex"
        and any(targets_frontend(item, "claude") for item in existing_handlers)
    )
    if (
        len(targeted) == 1
        and handler_is_current(targeted[0], frontend)
        and not imported_claude
    ):
        return False

    hooks = config.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise SessionLoggingError("hooks must be a mapping")
    groups = hooks.setdefault("Stop", [])
    if not isinstance(groups, list):
        raise SessionLoggingError("hooks.Stop must be a list")

    changed = False
    insertion_group: dict[str, Any] | None = None
    for group in groups:
        if not isinstance(group, dict):
            raise SessionLoggingError("every hooks.Stop entry must be a mapping")
        handlers = group.setdefault("hooks", [])
        if not isinstance(handlers, list) or not all(
            isinstance(item, dict) for item in handlers
        ):
            raise SessionLoggingError("hooks.Stop[].hooks must contain mappings")
        kept = []
        for existing in handlers:
            if targets_frontend(existing, frontend):
                insertion_group = insertion_group or group
                changed = True
            elif frontend == "codex" and targets_frontend(existing, "claude"):
                # A Claude logger imported into Codex cannot parse Codex rollouts.
                insertion_group = insertion_group or group
                changed = True
            else:
                kept.append(existing)
        if len(kept) != len(handlers):
            group["hooks"] = kept

    if insertion_group is None:
        insertion_group = {"hooks": []}
        groups.append(insertion_group)
        changed = True
    handlers = insertion_group["hooks"]
    if handler not in handlers:
        handlers.append(handler)
        changed = True
    return changed


def backup_path(path: Path) -> Path:
    base = path.with_name(f"{path.name}.before-session-logging")
    candidate = base
    counter = 1
    while candidate.exists():
        candidate = base.with_name(f"{base.name}.{counter}")
        counter += 1
    return candidate


def backup(path: Path) -> Path | None:
    if not path.exists():
        return None
    destination = backup_path(path)
    shutil.copy2(path, destination)
    return destination


def atomic_write(path: Path, data: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
        os.replace(temporary, path)
    except BaseException:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise


def write_with_backup(path: Path, data: bytes, default_mode: int = 0o600) -> Path | None:
    existing_mode = default_mode
    if path.exists():
        existing_mode = stat.S_IMODE(path.stat().st_mode)
        if path.read_bytes() == data:
            return None
    saved = backup(path)
    atomic_write(path, data, existing_mode)
    return saved


def install_logger(source: Path, destination: Path) -> Path | None:
    saved = write_with_backup(destination, source.read_bytes(), default_mode=0o700)
    destination.chmod(0o700)
    return saved


def require_regular_or_absent(path: Path) -> None:
    if path.is_symlink():
        raise SessionLoggingError(f"refusing to replace symbolic link: {path}")
    if path.exists() and not path.is_file():
        raise SessionLoggingError(f"refusing to replace non-file path: {path}")
