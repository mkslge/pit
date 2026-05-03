from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path

from helpers import run, run_pit_with_env, write_json
from pit.cli import HOOK_BEGIN, HOOK_END


def test_init_creates_executable_hooks_without_duplicate_blocks(
    git_repo: Path,
    pit_command_env: dict[str, str],
) -> None:
    run_pit_with_env(git_repo, pit_command_env, "init")
    run_pit_with_env(git_repo, pit_command_env, "init")

    for hook_name in ("pre-commit", "post-commit"):
        hook = git_repo / ".git" / "hooks" / hook_name
        hook_text = hook.read_text(encoding="utf-8")

        assert hook.exists()
        assert hook_text.count(HOOK_BEGIN) == 1
        assert hook_text.count(HOOK_END) == 1
        assert os.access(hook, os.X_OK)
        assert hook.stat().st_mode & stat.S_IXUSR


def test_init_preserves_existing_hook_content(
    git_repo: Path,
    pit_command_env: dict[str, str],
) -> None:
    hooks_dir = git_repo / ".git" / "hooks"
    hooks_dir.mkdir(exist_ok=True)
    pre_commit = hooks_dir / "pre-commit"
    pre_commit.write_text(
        "#!/bin/sh\n"
        "echo existing pre-commit hook\n",
        encoding="utf-8",
    )

    run_pit_with_env(git_repo, pit_command_env, "init")

    hook_text = pre_commit.read_text(encoding="utf-8")
    assert "echo existing pre-commit hook" in hook_text
    assert hook_text.count(HOOK_BEGIN) == 1
    assert " hook pre-commit" in hook_text


def test_git_commit_attaches_session_file_from_codex_fixture(
    git_repo: Path,
    pit_command_env: dict[str, str],
) -> None:
    run_pit_with_env(git_repo, pit_command_env, "init")
    write_codex_config(git_repo)
    write_codex_transcript(
        git_repo,
        [
            ("2026-05-03T10:00:01Z", "Implement hook capture"),
            ("2026-05-03T10:00:02Z", "Add hook tests"),
        ],
    )
    (git_repo / "app.txt").write_text("hello\n", encoding="utf-8")

    run(["git", "add", "."], cwd=git_repo)
    run(["git", "commit", "-m", "capture prompts"], cwd=git_repo, env=pit_command_env)

    session_files = sorted((git_repo / ".pit" / "sessions").glob("*.json"))
    assert len(session_files) == 1

    session = json.loads(session_files[0].read_text(encoding="utf-8"))
    assert session["tool"] == "codex"
    assert [prompt["text"] for prompt in session["prompts"]] == [
        "Implement hook capture",
        "Add hook tests",
    ]

    committed_files = run(
        ["git", "show", "--name-only", "--format=", "HEAD"],
        cwd=git_repo,
    ).stdout.splitlines()
    assert str(session_files[0].relative_to(git_repo)) in committed_files

    state = read_state(git_repo)
    assert state["last_seen_prompt_id"] == session["prompts"][-1]["id"]
    assert state["pending_session_file"] is None


def test_failed_commit_keeps_prompt_marker_pending(
    git_repo: Path,
    pit_command_env: dict[str, str],
) -> None:
    run_pit_with_env(git_repo, pit_command_env, "init")
    write_codex_config(git_repo)
    write_codex_transcript(git_repo, [("2026-05-03T10:00:01Z", "Prompt before failure")])
    install_failing_hook_after_pit_block(git_repo)
    (git_repo / "app.txt").write_text("hello\n", encoding="utf-8")

    run(["git", "add", "."], cwd=git_repo)
    result = subprocess.run(
        ["git", "commit", "-m", "should fail"],
        cwd=git_repo,
        env=pit_command_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode != 0

    state = read_state(git_repo)
    session_files = sorted((git_repo / ".pit" / "sessions").glob("*.json"))
    assert len(session_files) == 1
    assert state["last_seen_prompt_id"] is None
    assert state["pending_session_file"] == str(session_files[0].relative_to(git_repo))
    assert state["pending_last_seen_prompt_id"] is not None


def test_retry_after_failed_commit_reuses_pending_session_and_promotes_state(
    git_repo: Path,
    pit_command_env: dict[str, str],
) -> None:
    run_pit_with_env(git_repo, pit_command_env, "init")
    write_codex_config(git_repo)
    write_codex_transcript(git_repo, [("2026-05-03T10:00:01Z", "Retry this prompt")])
    install_failing_hook_after_pit_block(git_repo)
    (git_repo / "app.txt").write_text("hello\n", encoding="utf-8")

    run(["git", "add", "."], cwd=git_repo)
    first_result = subprocess.run(
        ["git", "commit", "-m", "first attempt"],
        cwd=git_repo,
        env=pit_command_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert first_result.returncode != 0

    pending_state = read_state(git_repo)
    pending_session_file = pending_state["pending_session_file"]
    assert pending_session_file is not None

    remove_failing_hook_line(git_repo)
    run(["git", "commit", "-m", "retry succeeds"], cwd=git_repo, env=pit_command_env)

    session_files = sorted((git_repo / ".pit" / "sessions").glob("*.json"))
    assert [str(path.relative_to(git_repo)) for path in session_files] == [
        pending_session_file
    ]

    state = read_state(git_repo)
    assert state["last_seen_prompt_id"] == pending_state["pending_last_seen_prompt_id"]
    assert state["pending_session_file"] is None
    assert state["pending_last_seen_prompt_id"] is None


def write_codex_config(repo: Path) -> None:
    write_json(
        repo / ".pit" / "config.json",
        {
            "version": 1,
            "prompt_source": {
                "type": "codex",
                "path": "codex_sessions",
            },
        },
    )


def write_codex_transcript(repo: Path, prompts: list[tuple[str, str]]) -> None:
    transcript = repo / "codex_sessions" / "2026" / "05" / "03" / "rollout-test.jsonl"
    transcript.parent.mkdir(parents=True, exist_ok=True)
    events = [
        {
            "timestamp": "2026-05-03T10:00:00Z",
            "type": "session_meta",
            "payload": {
                "id": "test-session",
                "timestamp": "2026-05-03T10:00:00Z",
                "cwd": str(repo.resolve()),
                "source": "test",
                "model_provider": "openai",
                "cli_version": "0.0.0",
            },
        },
        {
            "timestamp": "2026-05-03T10:00:00.500Z",
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "Do not capture this."}],
            },
        },
        {
            "timestamp": "2026-05-03T10:00:00.750Z",
            "type": "response_item",
            "payload": {
                "type": "function_call",
                "name": "shell",
                "arguments": "{}",
                "call_id": "call-test",
            },
        },
    ]
    for timestamp, message in prompts:
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
    transcript.write_text(
        "".join(json.dumps(event) + "\n" for event in events),
        encoding="utf-8",
    )


def install_failing_hook_after_pit_block(repo: Path) -> None:
    pre_commit = repo / ".git" / "hooks" / "pre-commit"
    pre_commit.write_text(
        pre_commit.read_text(encoding="utf-8")
        + "echo forced failure >&2\n"
        + "exit 1\n",
        encoding="utf-8",
    )


def remove_failing_hook_line(repo: Path) -> None:
    pre_commit = repo / ".git" / "hooks" / "pre-commit"
    lines = pre_commit.read_text(encoding="utf-8").splitlines()
    cleaned = [
        line
        for line in lines
        if line not in {"echo forced failure >&2", "exit 1"}
    ]
    pre_commit.write_text("\n".join(cleaned) + "\n", encoding="utf-8")


def read_state(repo: Path) -> dict:
    return json.loads((repo / ".pit" / "state.json").read_text(encoding="utf-8"))
