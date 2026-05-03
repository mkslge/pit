"""Small wrappers around Git commands."""

from __future__ import annotations

from pathlib import Path
import subprocess


class GitError(Exception):
    """Raised when a Git command needed by pit fails."""


def run_git(args: list[str], cwd: Path | None = None) -> str:
    command = ["git", *args]
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        if not message:
            message = f"git {' '.join(args)} failed"
        raise GitError(message)
    return result.stdout.strip()


def repo_root(cwd: Path | None = None) -> Path:
    return Path(run_git(["rev-parse", "--show-toplevel"], cwd=cwd)).resolve()


def git_dir(cwd: Path | None = None) -> Path:
    root = repo_root(cwd)
    raw_git_dir = Path(run_git(["rev-parse", "--git-dir"], cwd=root))
    if raw_git_dir.is_absolute():
        return raw_git_dir.resolve()
    return (root / raw_git_dir).resolve()
