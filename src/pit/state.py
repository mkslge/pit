"""State file loading and saving."""

from __future__ import annotations

import json
from pathlib import Path


DEFAULT_STATE = {
    "last_captured_at": None,
    "last_seen_prompt_id": None,
    "pending_session_file": None,
    "pending_captured_at": None,
    "pending_last_seen_prompt_id": None,
}


class StateError(Exception):
    """Raised when pit state is invalid."""


def load_state(path: Path) -> dict:
    if not path.exists():
        return dict(DEFAULT_STATE)

    with path.open("r", encoding="utf-8") as handle:
        state = json.load(handle)
    if not isinstance(state, dict):
        raise StateError("invalid .pit/state.json: expected a JSON object")

    merged = dict(DEFAULT_STATE)
    merged.update(state)
    return merged


def save_state(path: Path, state: dict) -> None:
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
