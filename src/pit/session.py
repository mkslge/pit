"""Session file creation."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from uuid import uuid4

from .prompts import Prompt


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def make_session_id(captured_at: str | None = None) -> str:
    timestamp = captured_at or utc_now()
    date_part = timestamp[:10]
    return f"{date_part}_{uuid4().hex[:8]}"


def write_session(
    sessions_dir: Path,
    source_config: dict,
    prompts: list[Prompt],
    captured_at: str | None = None,
) -> tuple[str, Path, str]:
    captured_at = captured_at or utc_now()
    session_id = make_session_id(captured_at)
    session_path = sessions_dir / f"{session_id}.json"
    session = {
        "session_id": session_id,
        "captured_at": captured_at,
        "commit": None,
        "tool": source_config.get("type", "unknown"),
        "source": source_config,
        "prompts": [prompt.to_json() for prompt in prompts],
        "summary": "",
    }

    sessions_dir.mkdir(exist_ok=True)
    session_path.write_text(json.dumps(session, indent=2) + "\n", encoding="utf-8")
    return session_id, session_path, captured_at
