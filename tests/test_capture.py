from __future__ import annotations

import json
from pathlib import Path

from helpers import run, run_pit, write_json


def test_capture_writes_valid_session_and_stages_it(git_repo: Path) -> None:
    run_pit(git_repo, "init")
    prompts_path = git_repo / "testdata" / "prompts.jsonl"
    prompts_path.parent.mkdir()
    prompts_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "id": "prompt-1",
                        "timestamp": "2026-05-03T10:00:00Z",
                        "text": "Build the feature",
                    }
                ),
                json.dumps(
                    {
                        "id": "prompt-2",
                        "timestamp": "2026-05-03T10:05:00Z",
                        "text": "Add a focused test",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    write_json(
        git_repo / ".pit" / "config.json",
        {
            "version": 1,
            "prompt_source": {
                "type": "fixture",
                "path": "testdata/prompts.jsonl",
            },
        },
    )

    result = run_pit(git_repo, "capture")

    assert "pit capture: captured 2 prompt(s)" in result.stdout

    session_files = sorted((git_repo / ".pit" / "sessions").glob("*.json"))
    assert len(session_files) == 1

    session = json.loads(session_files[0].read_text(encoding="utf-8"))
    assert session["commit"] is None
    assert session["tool"] == "fixture"
    assert session["source"]["path"] == "testdata/prompts.jsonl"
    assert [prompt["text"] for prompt in session["prompts"]] == [
        "Build the feature",
        "Add a focused test",
    ]

    state = json.loads((git_repo / ".pit" / "state.json").read_text(encoding="utf-8"))
    assert state["last_seen_prompt_id"] is None
    assert state["pending_last_seen_prompt_id"] == "prompt-2"
    assert state["pending_session_file"] == str(session_files[0].relative_to(git_repo))

    staged = run(["git", "diff", "--cached", "--name-only"], cwd=git_repo).stdout
    assert state["pending_session_file"] in staged.splitlines()
