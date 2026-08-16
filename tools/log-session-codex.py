#!/usr/bin/env python3
"""Regenerate a user/assistant-only Codex session log after each turn."""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from typing import Any


TEXT_BLOCK_TYPES = {"text", "input_text", "output_text"}
INJECTED_USER_BLOCK = re.compile(
    r"^\s*<environment_context>.*</environment_context>\s*$", re.DOTALL
)


def wait_until_stable(path: Path) -> None:
    """Wait for three unchanged samples, capped at roughly five seconds."""
    previous = -1
    stable = 0
    for _ in range(20):
        try:
            size = path.stat().st_size
        except OSError:
            return
        if size == previous:
            stable += 1
            if stable >= 3:
                return
        else:
            stable = 0
        previous = size
        time.sleep(0.25)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                # A concurrently flushed trailing record may still be partial.
                continue
            if isinstance(value, dict):
                records.append(value)
    return records


def message_from_record(record: dict[str, Any]) -> tuple[str, str] | None:
    """Extract a visible user/assistant message from known transcript shapes."""
    if record.get("isMeta") is True:
        return None

    payload = record.get("payload")
    if not isinstance(payload, dict):
        payload = record
    if payload.get("isMeta") is True:
        return None
    if record.get("type") == "response_item" and payload.get("type") != "message":
        return None

    role = payload.get("role") or record.get("role") or record.get("type")
    if role not in {"user", "assistant"}:
        return None

    content = payload.get("content")
    if content is None and isinstance(payload.get("message"), dict):
        content = payload["message"].get("content")

    texts: list[str] = []
    if isinstance(content, str):
        texts.append(content)
    elif isinstance(content, list):
        if role == "user" and any(
            isinstance(block, dict) and block.get("type") == "tool_result"
            for block in content
        ):
            return None
        for block in content:
            if (
                isinstance(block, dict)
                and block.get("type") in TEXT_BLOCK_TYPES
                and isinstance(block.get("text"), str)
            ):
                texts.append(block["text"])

    text = "\n\n".join(texts)
    if not text.strip():
        return None
    if role == "user" and INJECTED_USER_BLOCK.fullmatch(text):
        return None
    return role, text


def launch_directory(records: list[dict[str, Any]], hook: dict[str, Any]) -> Path:
    for record in records:
        if record.get("type") != "session_meta":
            continue
        payload = record.get("payload")
        if isinstance(payload, dict) and isinstance(payload.get("cwd"), str):
            return Path(payload["cwd"]).expanduser()
    cwd = hook.get("cwd")
    return Path(cwd if isinstance(cwd, str) and cwd else os.getcwd()).expanduser()


def canonical_transcripts(session_id: Any, primary: Path) -> list[Path]:
    """Find Codex's persisted rollout when a hook provides a shadow transcript."""
    if not isinstance(session_id, str) or not session_id:
        return []
    safe_id = re.sub(r"[^A-Za-z0-9._-]", "_", session_id)
    codex_home_value = os.environ.get("CODEX_HOME")
    codex_home = (
        Path(codex_home_value).expanduser()
        if codex_home_value
        else Path.home() / ".codex"
    )
    sessions = codex_home / "sessions"
    if not sessions.is_dir():
        return []
    try:
        primary_resolved = primary.resolve()
    except OSError:
        primary_resolved = primary
    candidates: list[Path] = []
    for candidate in sessions.rglob(f"*{safe_id}*.jsonl"):
        try:
            if candidate.resolve() != primary_resolved:
                candidates.append(candidate)
        except OSError:
            continue
    return sorted(candidates, key=lambda item: item.stat().st_mtime, reverse=True)


def render(records: list[dict[str, Any]], last_assistant: Any) -> str:
    turns: list[tuple[str, str]] = []
    assistant_messages: set[str] = set()
    for record in records:
        message = message_from_record(record)
        if message is None:
            continue
        role, text = message
        if role == "assistant":
            assistant_messages.add(text)
        if turns and turns[-1][0] == role:
            turns[-1] = (role, turns[-1][1] + "\n\n" + text)
        else:
            turns.append((role, text))

    if (
        isinstance(last_assistant, str)
        and last_assistant.strip()
        and last_assistant not in assistant_messages
    ):
        if turns and turns[-1][0] == "assistant":
            turns[-1] = ("assistant", turns[-1][1] + "\n\n" + last_assistant)
        else:
            turns.append(("assistant", last_assistant))

    labels = {"user": "User", "assistant": "Assistant"}
    return "\n\n".join(
        f"## {labels[role]}\n\n{text}" for role, text in turns
    ) + "\n"


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(text)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def main() -> int:
    hook = json.load(sys.stdin)
    transcript_value = hook.get("transcript_path")
    if not isinstance(transcript_value, str) or not transcript_value:
        return 0
    transcript = Path(transcript_value).expanduser()
    if not transcript.is_file():
        return 0

    wait_until_stable(transcript)
    records = read_jsonl(transcript)
    rendered = render(records, hook.get("last_assistant_message"))

    for candidate in canonical_transcripts(hook.get("session_id"), transcript):
        wait_until_stable(candidate)
        candidate_records = read_jsonl(candidate)
        candidate_rendered = render(
            candidate_records, hook.get("last_assistant_message")
        )
        if len(candidate_rendered) > len(rendered):
            records = candidate_records
            rendered = candidate_rendered

    directory = launch_directory(records, hook)
    session_id = hook.get("session_id")
    safe_id = ""
    if isinstance(session_id, str):
        safe_id = re.sub(r"[^A-Za-z0-9._-]", "_", session_id)
    name = f"session_{dt.datetime.now().astimezone():%Y-%m-%d}"
    if safe_id:
        name += f"_{safe_id}"
    atomic_write(directory / f"{name}.log", rendered)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Codex session logger failed: {error}", file=sys.stderr)
        raise SystemExit(1)
