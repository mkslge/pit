"""Path discovery for pit repositories."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import git


@dataclass(frozen=True)
class PitPaths:
    repo_root: Path
    git_dir: Path
    pit_dir: Path
    config_file: Path
    state_file: Path
    sessions_dir: Path


def discover_paths(cwd: Path | None = None) -> PitPaths:
    root = git.repo_root(cwd)
    git_dir = git.git_dir(root)
    pit_dir = root / ".pit"
    return PitPaths(
        repo_root=root,
        git_dir=git_dir,
        pit_dir=pit_dir,
        config_file=pit_dir / "config.json",
        state_file=pit_dir / "state.json",
        sessions_dir=pit_dir / "sessions",
    )
