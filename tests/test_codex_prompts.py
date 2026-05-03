from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from pit.prompts import CodexPromptSource, PromptSourceError, read_codex_transcript


MISSING = object()


def test_codex_source_filters_transcripts_by_matching_repo_cwd(tmp_path: Path) -> None:
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    sessions_root = tmp_path / "codex_sessions"
    write_codex_transcript(
        sessions_root / "2026" / "05" / "03" / "matching.jsonl",
        cwd=str(repo_root),
        prompts=[("2026-05-03T10:00:01Z", "Capture this repo prompt")],
    )
    write_codex_transcript(
        sessions_root / "2026" / "05" / "03" / "unrelated.jsonl",
        cwd=str((tmp_path / "other-repo").resolve()),
        prompts=[("2026-05-03T10:00:02Z", "Do not capture unrelated repo")],
    )
    write_codex_transcript(
        sessions_root / "2026" / "05" / "03" / "missing-cwd.jsonl",
        cwd=MISSING,
        prompts=[("2026-05-03T10:00:03Z", "Do not capture missing cwd")],
    )

    prompts = CodexPromptSource(sessions_root, repo_root).read_prompts()

    assert [prompt.text for prompt in prompts] == ["Capture this repo prompt"]


def test_codex_transcript_captures_only_user_message_payloads(tmp_path: Path) -> None:
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    transcript = tmp_path / "transcript.jsonl"
    write_codex_transcript(
        transcript,
        cwd=str(repo_root),
        extra_events=[
            {
                "timestamp": "2026-05-03T10:00:01Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "model-facing user"}],
                },
            },
            {
                "timestamp": "2026-05-03T10:00:02Z",
                "type": "event_msg",
                "payload": {
                    "type": "agent_message",
                    "message": "assistant event",
                },
            },
            {
                "timestamp": "2026-05-03T10:00:03Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "assistant"}],
                },
            },
            {
                "timestamp": "2026-05-03T10:00:04Z",
                "type": "response_item",
                "payload": {
                    "type": "function_call",
                    "name": "shell",
                    "arguments": "{}",
                    "call_id": "call-1",
                },
            },
            {
                "timestamp": "2026-05-03T10:00:05Z",
                "type": "event_msg",
                "payload": {
                    "type": "exec_command_end",
                    "exit_code": 0,
                },
            },
        ],
        prompts=[("2026-05-03T10:00:06Z", "Only canonical user prompt")],
    )

    prompts = read_codex_transcript(transcript, repo_root)

    assert [prompt.text for prompt in prompts] == ["Only canonical user prompt"]


def test_codex_user_message_prefers_message_over_text_elements(
    tmp_path: Path,
) -> None:
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    transcript = tmp_path / "transcript.jsonl"
    write_codex_transcript(
        transcript,
        cwd=str(repo_root),
        user_message_payloads=[
            {
                "message": "preferred message",
                "text_elements": ["fallback text"],
            }
        ],
    )

    prompts = read_codex_transcript(transcript, repo_root)

    assert [prompt.text for prompt in prompts] == ["preferred message"]


def test_codex_user_message_uses_text_elements_fallback(tmp_path: Path) -> None:
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    transcript = tmp_path / "transcript.jsonl"
    write_codex_transcript(
        transcript,
        cwd=str(repo_root),
        user_message_payloads=[
            {
                "text_elements": [
                    "first fallback line",
                    {"type": "image"},
                    "second fallback line",
                ],
            }
        ],
    )

    prompts = read_codex_transcript(transcript, repo_root)

    assert [prompt.text for prompt in prompts] == [
        "first fallback line\nsecond fallback line"
    ]


def test_codex_prompt_ids_are_deterministic_across_reads(tmp_path: Path) -> None:
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    transcript = tmp_path / "transcript.jsonl"
    write_codex_transcript(
        transcript,
        cwd=str(repo_root),
        prompts=[
            ("2026-05-03T10:00:01Z", "Stable id prompt one"),
            ("2026-05-03T10:00:02Z", "Stable id prompt two"),
        ],
    )

    first_read = read_codex_transcript(transcript, repo_root)
    second_read = read_codex_transcript(transcript, repo_root)

    assert [prompt.id for prompt in first_read] == [
        prompt.id for prompt in second_read
    ]


def test_invalid_codex_jsonl_reports_file_and_line_number(tmp_path: Path) -> None:
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(
        json.dumps(
            {
                "timestamp": "2026-05-03T10:00:00Z",
                "type": "session_meta",
                "payload": {
                    "id": "session-1",
                    "cwd": str(repo_root),
                },
            }
        )
        + "\n"
        + "{not-json}\n",
        encoding="utf-8",
    )

    with pytest.raises(
        PromptSourceError,
        match=rf"invalid Codex JSONL at {re.escape(str(transcript))}:2:",
    ):
        read_codex_transcript(transcript, repo_root)


def write_codex_transcript(
    path: Path,
    *,
    cwd: str | object,
    prompts: list[tuple[str, str]] | None = None,
    extra_events: list[dict[str, Any]] | None = None,
    user_message_payloads: list[dict[str, Any]] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    meta_payload: dict[str, Any] = {
        "id": "session-1",
        "timestamp": "2026-05-03T10:00:00Z",
        "source": "test",
        "model_provider": "openai",
        "cli_version": "0.0.0",
    }
    if cwd is not MISSING:
        meta_payload["cwd"] = cwd

    events: list[dict[str, Any]] = [
        {
            "timestamp": "2026-05-03T10:00:00Z",
            "type": "session_meta",
            "payload": meta_payload,
        }
    ]
    events.extend(extra_events or [])

    for timestamp, message in prompts or []:
        events.append(
            {
                "timestamp": timestamp,
                "type": "event_msg",
                "payload": {
                    "type": "user_message",
                    "message": message,
                    "text_elements": [message],
                    "images": [],
                    "local_images": [],
                },
            }
        )

    for index, payload in enumerate(user_message_payloads or [], start=1):
        event_payload = dict(payload)
        event_payload["type"] = "user_message"
        events.append(
            {
                "timestamp": f"2026-05-03T10:01:0{index}Z",
                "type": "event_msg",
                "payload": event_payload,
            }
        )

    path.write_text(
        "".join(json.dumps(event) + "\n" for event in events),
        encoding="utf-8",
    )
