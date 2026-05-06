# `src/pit/git.py`

`git.py` is a thin wrapper around Git subprocess calls. It centralizes error
handling so higher-level modules can deal with `GitError` instead of inspecting
subprocess results directly.

## Exceptions

### `GitError`

Raised when a Git command required by pit exits with a non-zero status.

The message comes from stderr when available, then stdout, then a generic
fallback.

## Functions

### `run_git(args: list[str], cwd: Path | None = None) -> str`

Runs one Git command and returns stdout.

Inputs:

- `args`: Git arguments without the leading `git`. Example:
  `["rev-parse", "--show-toplevel"]`.
- `cwd`: optional working directory for the subprocess.

Behavior:

- Builds `["git", *args]`.
- Captures stdout and stderr as text.
- Does not use `shell=True`, which avoids shell quoting issues.
- Strips surrounding whitespace from stdout before returning.

Returns:

- `stdout.strip()` when Git exits successfully.

Raises:

- `GitError` when Git returns a non-zero exit code.

Side effects:

- Whatever side effects the Git command itself performs. For example, callers
  use this function for read-only commands and for `git add`.

### `repo_root(cwd: Path | None = None) -> Path`

Finds the root directory of the current Git worktree.

Inputs:

- `cwd`: optional directory from which to run Git discovery.

Behavior:

- Runs `git rev-parse --show-toplevel`.
- Resolves the returned path.

Returns:

- Absolute resolved `Path` for the repository root.

Raises:

- `GitError` when `cwd` is not inside a Git worktree.

### `git_dir(cwd: Path | None = None) -> Path`

Finds the repository's `.git` directory.

Inputs:

- `cwd`: optional directory for repository discovery.

Behavior:

1. Calls `repo_root(cwd)`.
2. Runs `git rev-parse --git-dir` from that root.
3. Resolves absolute Git dirs directly.
4. Resolves relative Git dirs against the repository root.

Returns:

- Absolute resolved `Path` for the Git directory.

Why relative handling matters: `git rev-parse --git-dir` commonly returns
`.git`, but linked worktrees and some setups may return different paths.
