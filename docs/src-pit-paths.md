# `src/pit/paths.py`

`paths.py` defines the canonical repository paths used throughout pit. Keeping
these in one data object avoids recomputing `.pit` and hook paths in each
command.

## Data Classes

### `PitPaths`

Frozen dataclass containing important repository paths.

Fields:

- `repo_root`: root of the Git worktree.
- `git_dir`: Git metadata directory, usually `<repo>/.git`.
- `pit_dir`: `<repo>/.pit`.
- `config_file`: `<repo>/.pit/config.json`.
- `state_file`: `<repo>/.pit/state.json`.
- `sessions_dir`: `<repo>/.pit/sessions`.

Because the dataclass is frozen, callers treat it as immutable configuration
instead of mutable state.

## Functions

### `discover_paths(cwd: Path | None = None) -> PitPaths`

Discovers all paths pit needs for a repository.

Inputs:

- `cwd`: optional directory to use for Git discovery. When omitted, Git uses the
  current process working directory.

Behavior:

1. Calls `git.repo_root(cwd)` to find the worktree root.
2. Calls `git.git_dir(root)` to find the Git metadata directory.
3. Constructs `.pit`, config, state, and sessions paths relative to the root.

Returns:

- `PitPaths`.

Raises:

- `GitError` when the directory is not inside a Git worktree.

Side effects:

- None. This function discovers paths only; it does not create files or
  directories.
