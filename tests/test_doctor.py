from __future__ import annotations

from pathlib import Path

from helpers import run_pit_raw, run_pit_with_env, write_json


def test_doctor_reports_healthy_fixture_repo(
    git_repo: Path,
    pit_command_env: dict[str, str],
) -> None:
    run_pit_with_env(git_repo, pit_command_env, "init")
    write_fixture_source(git_repo)

    result = run_pit_raw(git_repo, pit_command_env, "doctor")

    assert result.returncode == 0
    assert "OK: Git repository" in result.stdout
    assert "OK: Prompt source path" in result.stdout
    assert "OK: pre-commit hook" in result.stdout
    assert "OK: post-commit hook" in result.stdout


def test_status_reports_hook_health(
    git_repo: Path,
    pit_command_env: dict[str, str],
) -> None:
    run_pit_with_env(git_repo, pit_command_env, "init")
    write_fixture_source(git_repo)

    healthy = run_pit_raw(git_repo, pit_command_env, "status")
    assert healthy.returncode == 0
    assert "Hooks: OK" in healthy.stdout

    (git_repo / ".git" / "hooks" / "pre-commit").unlink()

    missing_hook = run_pit_raw(git_repo, pit_command_env, "status")
    assert missing_hook.returncode == 0
    assert "Hooks: needs attention; run `pit init`" in missing_hook.stdout


def test_doctor_reports_missing_hooks_with_fix(
    git_repo: Path,
    pit_command_env: dict[str, str],
) -> None:
    run_pit_with_env(git_repo, pit_command_env, "init")
    write_fixture_source(git_repo)
    (git_repo / ".git" / "hooks" / "post-commit").unlink()

    result = run_pit_raw(git_repo, pit_command_env, "doctor")

    assert result.returncode == 1
    assert "FAIL: post-commit hook" in result.stdout
    assert "Run `pit init` to repair hooks." in result.stdout


def test_doctor_reports_legacy_codex_path_with_fix(
    git_repo: Path,
    pit_command_env: dict[str, str],
) -> None:
    run_pit_with_env(git_repo, pit_command_env, "init")
    write_json(
        git_repo / ".pit" / "config.json",
        {
            "version": 1,
            "prompt_source": {
                "type": "codex",
                "path": "~/.codex/history",
            },
        },
    )

    result = run_pit_raw(git_repo, pit_command_env, "doctor")

    assert result.returncode == 1
    assert "FAIL: Prompt source path" in result.stdout
    assert "old history file" in result.stdout
    assert '"path": "~/.codex/sessions"' in result.stdout


def write_fixture_source(repo: Path) -> None:
    prompt_file = repo / "testdata" / "prompts.jsonl"
    prompt_file.parent.mkdir()
    prompt_file.write_text(
        '{"id":"prompt-1","timestamp":"2026-05-03T10:00:00Z","text":"sanitized"}\n',
        encoding="utf-8",
    )
    write_json(
        repo / ".pit" / "config.json",
        {
            "version": 1,
            "prompt_source": {
                "type": "fixture",
                "path": "testdata/prompts.jsonl",
            },
        },
    )
