"""Command-line interface for pit."""

from __future__ import annotations

import argparse
import json
import stat
import sys
from pathlib import Path
from typing import Sequence

from . import __version__
from .git import GitError, run_git
from .paths import PitPaths, discover_paths
from .prompts import Prompt, PromptSourceError, prompt_source_from_config
from .session import write_session
from .state import DEFAULT_STATE, StateError, load_state, save_state


DEFAULT_CONFIG = {
    "version": 1,
    "prompt_source": {
        "type": "codex",
        "path": "~/.codex/sessions",
    },
}

HOOK_BEGIN = "# BEGIN pit managed block"
HOOK_END = "# END pit managed block"


class PitError(Exception):
    """User-facing pit error."""


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return args.func(args)
    except (
        GitError,
        PitError,
        PromptSourceError,
        StateError,
        OSError,
        json.JSONDecodeError,
    ) as exc:
        print(f"pit: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pit",
        description="Git-native prompt history for AI coding sessions.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"pit {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser(
        "init",
        help="initialize pit in the current Git repository",
    )
    init_parser.set_defaults(func=cmd_init)

    status_parser = subparsers.add_parser(
        "status",
        help="show pit initialization status",
    )
    status_parser.set_defaults(func=cmd_status)

    capture_parser = subparsers.add_parser(
        "capture",
        help="capture new prompts into a staged pit session file",
    )
    capture_parser.set_defaults(func=cmd_capture)

    log_parser = subparsers.add_parser(
        "log",
        help="show commits that include pit prompt sessions",
    )
    log_parser.set_defaults(func=cmd_log)

    show_parser = subparsers.add_parser(
        "show",
        help="show prompt history attached to a commit",
    )
    show_parser.add_argument("commit", help="commit to inspect")
    show_parser.set_defaults(func=cmd_show)

    hook_parser = subparsers.add_parser(
        "hook",
        help="run pit Git hook integration commands",
    )
    hook_subparsers = hook_parser.add_subparsers(dest="hook_name", required=True)

    pre_commit_parser = hook_subparsers.add_parser(
        "pre-commit",
        help="run the pit pre-commit hook",
    )
    pre_commit_parser.set_defaults(func=cmd_hook_pre_commit)

    post_commit_parser = hook_subparsers.add_parser(
        "post-commit",
        help="run the pit post-commit hook",
    )
    post_commit_parser.set_defaults(func=cmd_hook_post_commit)

    return parser


def cmd_init(_args: argparse.Namespace) -> int:
    paths = discover_paths()

    paths.pit_dir.mkdir(exist_ok=True)
    paths.sessions_dir.mkdir(exist_ok=True)
    write_json_if_missing(paths.config_file, DEFAULT_CONFIG)
    write_json_if_missing(paths.state_file, DEFAULT_STATE)
    ensure_state_ignored(paths)
    install_hooks(paths)

    print(f"pit initialized in {paths.repo_root}")
    print("hooks installed")
    return 0


def cmd_status(_args: argparse.Namespace) -> int:
    paths = discover_paths()

    if not paths.pit_dir.exists():
        raise PitError("not initialized; run `pit init`")

    config = read_json(paths.config_file, ".pit/config.json")
    state = load_state(paths.state_file)
    prompt_source = config.get("prompt_source", {})
    source_type = prompt_source.get("type", "unknown")
    uncaptured_count = count_uncaptured_prompts(config, state, paths)

    print("pit initialized")
    print(f"Repo: {paths.repo_root}")
    print(f"Prompt source: {source_type}")
    print(f"Uncaptured prompts: {uncaptured_count}")
    print(f"Sessions directory: {paths.sessions_dir}")
    print(f"Last captured prompt: {state.get('last_seen_prompt_id') or 'none'}")
    print("Hooks: installed by `pit init`")
    return 0


def cmd_capture(_args: argparse.Namespace) -> int:
    result = capture_pending_prompts()

    if result == "pending":
        print("pit capture already pending")
    elif result == "empty":
        print("pit capture: no new prompts")
    else:
        session_id, prompt_count = result
        print(f"pit capture: captured {prompt_count} prompt(s)")
        print(f"pit session: {session_id}")
    return 0


def cmd_log(_args: argparse.Namespace) -> int:
    paths = discover_paths()
    output = run_git(
        ["log", "--format=%H%x09%s", "--", ".pit/sessions"],
        cwd=paths.repo_root,
    )
    if not output:
        print("No pit sessions found.")
        return 0

    printed = False
    for line in output.splitlines():
        commit, subject = split_commit_log_line(line)
        sessions = read_sessions_from_commit(paths, commit)
        for _session_path, session in sessions:
            session_id = session.get("session_id", "unknown")
            prompt_count = len(session.get("prompts", []))
            print(f"{commit[:7]} {subject}")
            print(f"  pit session: {session_id}")
            print(f"  prompts: {prompt_count}")
            printed = True

    if not printed:
        print("No pit sessions found.")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    paths = discover_paths()
    commit = args.commit
    commit_info = run_git(["show", "-s", "--format=%h %s", commit], cwd=paths.repo_root)
    sessions = read_sessions_from_commit(paths, commit)

    print(f"Commit: {commit_info}")
    if not sessions:
        print("\nNo pit prompt session found for this commit.")
        return 0

    for index, (session_path, session) in enumerate(sessions):
        if len(sessions) > 1:
            if index > 0:
                print()
            print(f"Session: {session.get('session_id', session_path.stem)}")
        print("\nPrompts:")
        prompts = session.get("prompts", [])
        if not isinstance(prompts, list) or not prompts:
            print("none")
            continue
        for prompt_index, prompt in enumerate(prompts, start=1):
            if isinstance(prompt, dict):
                text = prompt.get("text", "")
            else:
                text = ""
            print(f"{prompt_index}. {text}")
    return 0


def cmd_hook_pre_commit(_args: argparse.Namespace) -> int:
    paths = discover_paths()
    if not paths.pit_dir.exists():
        return 0
    capture_pending_prompts(paths)
    return 0


def cmd_hook_post_commit(_args: argparse.Namespace) -> int:
    paths = discover_paths()
    if not paths.pit_dir.exists():
        return 0
    promote_pending_capture(paths)
    return 0


def capture_pending_prompts(
    paths: PitPaths | None = None,
) -> tuple[str, int] | str:
    paths = paths or discover_initialized_paths()
    config = read_json(paths.config_file, ".pit/config.json")
    state = load_state(paths.state_file)

    pending_session = state.get("pending_session_file")
    if pending_session:
        pending_path = paths.repo_root / pending_session
        if pending_path.exists():
            stage_file(paths, pending_path)
            return "pending"

    source = prompt_source_from_config(config, paths.repo_root)
    prompts = source.read_prompts()
    new_prompts = filter_uncaptured_prompts(prompts, state)

    if not new_prompts:
        return "empty"

    source_config = config["prompt_source"]
    session_id, session_path, captured_at = write_session(
        paths.sessions_dir,
        source_config,
        new_prompts,
    )
    stage_file(paths, session_path)

    newest_prompt = new_prompts[-1]
    state["pending_session_file"] = str(session_path.relative_to(paths.repo_root))
    state["pending_captured_at"] = captured_at
    state["pending_last_seen_prompt_id"] = newest_prompt.id
    save_state(paths.state_file, state)

    return session_id, len(new_prompts)


def promote_pending_capture(paths: PitPaths) -> None:
    state = load_state(paths.state_file)
    pending_last_seen_prompt_id = state.get("pending_last_seen_prompt_id")
    if not pending_last_seen_prompt_id:
        return

    state["last_captured_at"] = state.get("pending_captured_at")
    state["last_seen_prompt_id"] = pending_last_seen_prompt_id
    state["pending_session_file"] = None
    state["pending_captured_at"] = None
    state["pending_last_seen_prompt_id"] = None
    save_state(paths.state_file, state)


def discover_initialized_paths() -> PitPaths:
    paths = discover_paths()
    if not paths.pit_dir.exists():
        raise PitError("not initialized; run `pit init`")
    return paths


def filter_uncaptured_prompts(prompts: list[Prompt], state: dict) -> list[Prompt]:
    last_seen_prompt_id = state.get("last_seen_prompt_id")
    if not last_seen_prompt_id:
        return prompts

    for index, prompt in enumerate(prompts):
        if prompt.id == last_seen_prompt_id:
            return prompts[index + 1:]
    return prompts


def count_uncaptured_prompts(config: dict, state: dict, paths: PitPaths) -> int:
    source = prompt_source_from_config(config, paths.repo_root)
    prompts = source.read_prompts()
    return len(filter_uncaptured_prompts(prompts, state))


def stage_file(paths: PitPaths, path: Path) -> None:
    run_git(["add", str(path.relative_to(paths.repo_root))], cwd=paths.repo_root)


def split_commit_log_line(line: str) -> tuple[str, str]:
    if "\t" not in line:
        return line, ""
    commit, subject = line.split("\t", 1)
    return commit, subject


def read_sessions_from_commit(paths: PitPaths, commit: str) -> list[tuple[Path, dict]]:
    sessions = []
    for session_path in session_paths_changed_in_commit(paths, commit):
        session = read_session_from_commit(paths, commit, session_path)
        sessions.append((session_path, session))
    return sessions


def session_paths_changed_in_commit(paths: PitPaths, commit: str) -> list[Path]:
    output = run_git(
        ["diff-tree", "--root", "--no-commit-id", "--name-status", "-r", commit],
        cwd=paths.repo_root,
    )
    session_paths = []
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status = parts[0]
        path = parts[-1]
        if not status.startswith(("A", "M")):
            continue
        if is_session_path(path):
            session_paths.append(Path(path))
    return session_paths


def is_session_path(path: str) -> bool:
    return path.startswith(".pit/sessions/") and path.endswith(".json")


def read_session_from_commit(paths: PitPaths, commit: str, session_path: Path) -> dict:
    raw_session = run_git(["show", f"{commit}:{session_path}"], cwd=paths.repo_root)
    session = json.loads(raw_session)
    if not isinstance(session, dict):
        raise PitError(f"invalid session file in commit: {session_path}")
    return session


def write_json_if_missing(path, data: dict) -> None:
    if path.exists():
        return
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def read_json(path, label: str) -> dict:
    if not path.exists():
        raise PitError(f"missing {label}; run `pit init`")
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise PitError(f"invalid {label}: expected a JSON object")
    return data


def ensure_state_ignored(paths: PitPaths) -> None:
    gitignore = paths.repo_root / ".gitignore"
    ignore_entry = ".pit/state.json"

    if gitignore.exists():
        lines = gitignore.read_text(encoding="utf-8").splitlines()
    else:
        lines = []

    if ignore_entry in lines:
        return

    new_text = "\n".join(lines)
    if new_text:
        new_text += "\n"
    new_text += f"{ignore_entry}\n"
    gitignore.write_text(new_text, encoding="utf-8")


def install_hooks(paths: PitPaths) -> None:
    hooks = {
        "pre-commit": pit_hook_command(paths, "pre-commit"),
        "post-commit": pit_hook_command(paths, "post-commit"),
    }
    for hook_name, command in hooks.items():
        install_hook(paths.git_dir / "hooks" / hook_name, command)


def pit_hook_command(paths: PitPaths, hook_name: str) -> str:
    repo_pit = paths.repo_root / "pit"
    if repo_pit.exists():
        return f"{shell_quote(str(repo_pit))} hook {hook_name}"
    return f"pit hook {hook_name}"


def shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def install_hook(path, command: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    block = managed_hook_block(command)

    if path.exists():
        existing_text = path.read_text(encoding="utf-8")
    else:
        existing_text = "#!/bin/sh\n"

    new_text = upsert_managed_block(existing_text, block)
    path.write_text(new_text, encoding="utf-8")

    current_mode = path.stat().st_mode
    path.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def managed_hook_block(command: str) -> str:
    return f"{HOOK_BEGIN}\n{command}\n{HOOK_END}\n"


def upsert_managed_block(existing_text: str, block: str) -> str:
    begin_index = existing_text.find(HOOK_BEGIN)
    end_index = existing_text.find(HOOK_END)

    if begin_index != -1 and end_index != -1 and begin_index < end_index:
        end_index += len(HOOK_END)
        trailing_newline = "\n" if existing_text[end_index : end_index + 1] == "\n" else ""
        return (
            existing_text[:begin_index]
            + block
            + existing_text[end_index + len(trailing_newline) :]
        )

    if not existing_text:
        return block

    separator = "" if existing_text.endswith("\n") else "\n"
    return f"{existing_text}{separator}{block}"
