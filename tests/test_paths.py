from __future__ import annotations

from pathlib import Path

from pit.paths import discover_paths


def test_discover_paths_from_nested_directory(git_repo: Path) -> None:
    nested = git_repo / "src" / "package"
    nested.mkdir(parents=True)

    paths = discover_paths(nested)

    assert paths.repo_root == git_repo.resolve()
    assert paths.git_dir == (git_repo / ".git").resolve()
    assert paths.pit_dir == git_repo / ".pit"
    assert paths.config_file == git_repo / ".pit" / "config.json"
    assert paths.state_file == git_repo / ".pit" / "state.json"
    assert paths.sessions_dir == git_repo / ".pit" / "sessions"
