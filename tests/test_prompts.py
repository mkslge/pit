from __future__ import annotations

import json
from pathlib import Path

from pit.prompts import FixturePromptSource, prompt_source_from_config


def test_fixture_prompt_source_reads_jsonl_prompts(tmp_path: Path) -> None:
    prompt_file = tmp_path / "prompts.jsonl"
    prompt_file.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "id": "prompt-1",
                        "timestamp": "2026-05-03T10:00:00Z",
                        "text": "First prompt",
                    }
                ),
                "",
                json.dumps(
                    {
                        "id": "prompt-2",
                        "timestamp": "2026-05-03T10:01:00Z",
                        "text": "Second prompt",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    prompts = FixturePromptSource(prompt_file).read_prompts()

    assert [prompt.id for prompt in prompts] == ["prompt-1", "prompt-2"]
    assert [prompt.text for prompt in prompts] == ["First prompt", "Second prompt"]


def test_prompt_source_from_config_resolves_fixture_path_relative_to_repo(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    prompt_file = repo_root / "testdata" / "prompts.jsonl"
    prompt_file.parent.mkdir()
    prompt_file.write_text(
        json.dumps(
            {
                "id": "prompt-1",
                "timestamp": "2026-05-03T10:00:00Z",
                "text": "Prompt from repo fixture",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    source = prompt_source_from_config(
        {"prompt_source": {"type": "fixture", "path": "testdata/prompts.jsonl"}},
        repo_root,
    )

    assert source.read_prompts()[0].text == "Prompt from repo fixture"
