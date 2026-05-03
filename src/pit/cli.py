"""Command-line interface for pit."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from . import __version__
from .git import GitError
from .paths import PitPaths, discover_paths


DEFAULT_CONFIG = {
    "version": 1,
    "prompt_source": {
        "type": "codex",
        "path": "~/.codex/history",
    },
}

DEFAULT_STATE = {
    "last_captured_at": None,
    "last_seen_prompt_id": None,
    "pending_session_file": None,
}


class PitError(Exception):
    """User-facing pit error."""


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return args.func(args)
    except (GitError, PitError, OSError, json.JSONDecodeError) as exc:
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

    return parser


def cmd_init(_args: argparse.Namespace) -> int:
    paths = discover_paths()

    paths.pit_dir.mkdir(exist_ok=True)
    paths.sessions_dir.mkdir(exist_ok=True)
    write_json_if_missing(paths.config_file, DEFAULT_CONFIG)
    write_json_if_missing(paths.state_file, DEFAULT_STATE)
    ensure_state_ignored(paths)

    print(f"pit initialized in {paths.repo_root}")
    print("hook installation: pending Phase 2")
    return 0


def cmd_status(_args: argparse.Namespace) -> int:
    paths = discover_paths()

    if not paths.pit_dir.exists():
        raise PitError("not initialized; run `pit init`")

    config = read_json(paths.config_file, ".pit/config.json")
    state = read_json(paths.state_file, ".pit/state.json")
    prompt_source = config.get("prompt_source", {})
    source_type = prompt_source.get("type", "unknown")

    print("pit initialized")
    print(f"Repo: {paths.repo_root}")
    print(f"Prompt source: {source_type}")
    print(f"Sessions directory: {paths.sessions_dir}")
    print(f"Last captured prompt: {state.get('last_seen_prompt_id') or 'none'}")
    print("Hook installation: pending Phase 2")
    return 0


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
