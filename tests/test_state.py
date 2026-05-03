from __future__ import annotations

from pathlib import Path

import pytest

from pit.state import DEFAULT_STATE, StateError, load_state, save_state


def test_load_state_uses_defaults_when_file_is_missing(tmp_path: Path) -> None:
    assert load_state(tmp_path / "state.json") == DEFAULT_STATE


def test_load_state_merges_saved_partial_state(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    save_state(state_path, {"last_seen_prompt_id": "prompt-1"})

    state = load_state(state_path)

    assert state["last_seen_prompt_id"] == "prompt-1"
    assert state["pending_session_file"] is None


def test_load_state_rejects_non_object_json(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    state_path.write_text("[]\n", encoding="utf-8")

    with pytest.raises(StateError, match="expected a JSON object"):
        load_state(state_path)
