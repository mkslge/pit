# `src/pit/cli.py`

`cli.py` owns the user-facing CLI, Git hook entrypoints, capture orchestration,
diagnostics, and hook installation. It is the coordination layer: most functions
either parse command-line intent, call helpers from other modules, or perform
small filesystem/Git side effects.

## Constants

### `DEFAULT_CONFIG`

Default repository config written by `pit init` when `.pit/config.json` does not
exist. It configures the MVP prompt source as Codex transcripts under
`~/.codex/sessions`.

### `HOOK_BEGIN` and `HOOK_END`

Marker comments used to identify the pit-managed block inside Git hook files.
They allow `pit init` to update its own hook command without overwriting unrelated
hook content.

### `STATE_IGNORE_PATH`

The repo-relative path `.pit/state.json`. This is local state and should be
ignored by Git.

## Exceptions And Data Classes

### `PitError`

User-facing exception for CLI-level errors that are not more specific Git,
prompt-source, or state errors. `main()` catches it and prints `pit: <message>`
to stderr.

### `DiagnosticCheck`

Frozen dataclass used by `pit doctor`.

Fields:

- `name`: human-readable check name.
- `status`: status string, currently `OK` or `FAIL`.
- `detail`: optional explanatory text or repair guidance.

## CLI Entrypoints

### `main(argv: Sequence[str] | None = None) -> int`

Builds the argument parser, dispatches to the selected command handler, and
normalizes user-facing errors into exit code `1`.

Inputs:

- `argv`: optional argument list. When `None`, `argparse` reads `sys.argv`.

Returns:

- `0` when the selected command succeeds.
- `1` when a known user-facing exception is raised.

Catches:

- `GitError`
- `PitError`
- `PromptSourceError`
- `StateError`
- `OSError`
- `json.JSONDecodeError`

Important detail: command handlers are expected to return integer exit codes.
Unexpected exceptions are intentionally not swallowed, which keeps programming
errors visible during development.

### `build_parser() -> argparse.ArgumentParser`

Creates the complete `argparse` parser for the CLI.

Commands registered:

- `init`
- `status`
- `doctor`
- `capture`
- `show <commit>`
- `hook pre-commit`
- `hook post-commit`

Return value:

- A configured `ArgumentParser` whose parsed args include a `func` attribute
  pointing at the handler to run.

Side effects:

- None. This only constructs parser objects.

## User Command Handlers

### `cmd_init(_args: argparse.Namespace) -> int`

Initializes pit in the current Git repository.

Behavior:

1. Discovers the repository paths with `discover_paths()`.
2. Creates `.pit/` and `.pit/sessions/`.
3. Writes `.pit/config.json` with `DEFAULT_CONFIG` if missing.
4. Writes `.pit/state.json` with `DEFAULT_STATE` if missing.
5. Ensures `.pit/state.json` is in `.gitignore`.
6. Installs or updates `pre-commit` and `post-commit` hooks.
7. Warns if the existing Codex config points to legacy history paths.

Returns:

- `0` on success.

Side effects:

- Creates directories and JSON files.
- Edits `.gitignore` if needed.
- Creates or edits files in `.git/hooks/`.
- Prints a short success message.

### `cmd_status(_args: argparse.Namespace) -> int`

Prints a concise status summary for an initialized repository.

Behavior:

- Requires `.pit/` to exist.
- Reads `.pit/config.json`.
- Loads `.pit/state.json`.
- Counts uncaptured prompts if the prompt source is readable.
- Prints hook health based on installed hook files.

Returns:

- `0` on success.

Failure modes:

- Raises `PitError` if `.pit/` is missing.
- Propagates JSON, Git, and state errors through `main()`.

Privacy detail: it counts prompts but does not print prompt text.

### `cmd_doctor(_args: argparse.Namespace) -> int`

Runs read-only diagnostics and prints each check.

Returns:

- `0` when no diagnostic has status `FAIL`.
- `1` when any check has status `FAIL`.

Side effects:

- Prints diagnostics.
- Does not modify files.
- Does not print prompt contents.

### `cmd_capture(_args: argparse.Namespace) -> int`

Manually performs the same capture work as the `pre-commit` hook.

Behavior:

- Calls `capture_pending_prompts()`.
- Prints one of:
  - an existing capture is already pending
  - no new prompts exist
  - a new session was captured with its session ID

Returns:

- `0` on success.

Side effects:

- May write `.pit/sessions/<session-id>.json`.
- May stage that session file with `git add`.
- May update `.pit/state.json` pending fields.

### `cmd_show(args: argparse.Namespace) -> int`

Shows prompt history attached to one commit.

Behavior:

- Discovers repository paths.
- Delegates rendering to `print_commit_prompts()`.

Returns:

- Whatever `print_commit_prompts()` returns, currently `0`.

`pit show <commit>` is the single command for inspecting prompt text attached
to one commit.

### `print_commit_prompts(paths: PitPaths, commit: str) -> int`

Renders the prompt sessions attached to a single commit.

Inputs:

- `paths`: discovered repository paths.
- `commit`: any Git revision accepted by `git show`, such as `HEAD`, a branch
  name, or a SHA.

Behavior:

1. Reads the commit subject with `git show -s --format=%h %s`.
2. Reads pit session files added or modified by that exact commit.
3. Prints `Commit: <short-sha> <subject>`.
4. If no pit sessions exist, prints a no-session message.
5. Otherwise prints each prompt under a visible `--- Prompt N ---` header.

Returns:

- `0`.

Side effects:

- Prints to stdout only.

Commit scoping: this function relies on `read_sessions_from_commit()`, which
uses `git diff-tree` for the selected commit rather than walking history.

## Git Hook Command Handlers

### `cmd_hook_pre_commit(_args: argparse.Namespace) -> int`

Internal handler installed into `.git/hooks/pre-commit`.

Behavior:

- Discovers repository paths.
- If `.pit/` does not exist, does nothing and allows the commit.
- Otherwise calls `capture_pending_prompts(paths)`.

Returns:

- `0` when the hook should allow the commit.

Side effects:

- May write and stage a session file.
- May update pending state.

### `cmd_hook_post_commit(_args: argparse.Namespace) -> int`

Internal handler installed into `.git/hooks/post-commit`.

Behavior:

- Discovers repository paths.
- If `.pit/` does not exist, does nothing.
- Otherwise calls `promote_pending_capture(paths)`.

Returns:

- `0`.

Side effects:

- May update `.pit/state.json` by promoting pending capture markers.

## Capture State Flow

### `capture_pending_prompts(paths: PitPaths | None = None) -> tuple[str, int] | str`

Captures new prompts into a session file and stages it.

Inputs:

- `paths`: optional pre-discovered paths. If omitted, the function requires an
  initialized repo via `discover_initialized_paths()`.

Returns:

- `"pending"` if state already points at an existing pending session file, after
  re-staging that file.
- `"empty"` if no new prompts are available.
- `(session_id, prompt_count)` when a new session is written.

Behavior:

1. Reads config and state.
2. Reuses an existing pending session file if one exists.
3. Builds a prompt source from config.
4. Reads all prompts from the source.
5. Filters out prompts already captured.
6. Writes a new session JSON file if new prompts exist.
7. Stages the session file.
8. Records pending state fields.

Why pending state matters: the pre-commit hook runs before Git creates the
commit. If the commit later fails, the state is not promoted, so prompts are not
lost or silently marked captured.

### `promote_pending_capture(paths: PitPaths) -> None`

Promotes pending capture markers after a successful commit.

Inputs:

- `paths`: discovered repository paths.

Behavior:

- Loads `.pit/state.json`.
- If no `pending_last_seen_prompt_id` exists, returns immediately.
- Copies pending capture data into `last_captured_at` and `last_seen_prompt_id`.
- Clears pending fields.
- Saves state.

Side effects:

- Writes `.pit/state.json` when pending state exists.

### `discover_initialized_paths() -> PitPaths`

Discovers repository paths and verifies pit has been initialized.

Returns:

- `PitPaths` for the current repository.

Raises:

- `PitError` if `.pit/` does not exist.
- `GitError` if the current directory is not inside a Git worktree.

### `filter_uncaptured_prompts(prompts: list[Prompt], state: dict) -> list[Prompt]`

Selects prompts that appear after the last captured prompt marker.

Inputs:

- `prompts`: ordered prompt list.
- `state`: loaded state dictionary.

Returns:

- All prompts when `last_seen_prompt_id` is empty.
- Prompts after the matching `last_seen_prompt_id` when found.
- All prompts when the state marker is not found in the current source list.

Implementation note: returning all prompts when the marker is missing is
conservative, but it can duplicate prompts if the prompt source loses history.

### `count_uncaptured_prompts(config: dict, state: dict, paths: PitPaths) -> int`

Counts prompts that would be captured on the next commit.

Inputs:

- `config`: repository config dictionary.
- `state`: loaded state dictionary.
- `paths`: discovered repository paths.

Returns:

- Number of prompts after `filter_uncaptured_prompts()`.

Side effects:

- Reads from the configured prompt source.
- Does not print or write prompt contents.

### `stage_file(paths: PitPaths, path: Path) -> None`

Stages one file with Git.

Inputs:

- `paths`: repository paths.
- `path`: absolute or repository-root-based path to stage.

Behavior:

- Converts `path` to a repo-relative path.
- Runs `git add <relative-path>`.

Raises:

- `ValueError` if `path` is not under the repository root.
- `GitError` if `git add` fails.

## Commit Session Reading

### `split_commit_log_line(line: str) -> tuple[str, str]`

Splits a line emitted by `git log --format=%H%x09%s`.

Inputs:

- `line`: one formatted Git log line.

Returns:

- `(commit, subject)` when a tab is present.
- `(line, "")` when no tab is present.

### `read_sessions_from_commit(paths: PitPaths, commit: str) -> list[tuple[Path, dict]]`

Reads pit session JSON objects added or modified by one commit.

Inputs:

- `paths`: repository paths.
- `commit`: Git revision to inspect.

Returns:

- A list of `(session_path, session_dict)` tuples.

Behavior:

- Calls `session_paths_changed_in_commit()` to find candidate files.
- Calls `read_session_from_commit()` for each candidate.

### `session_paths_changed_in_commit(paths: PitPaths, commit: str) -> list[Path]`

Finds pit session files added or modified by a specific commit.

Behavior:

- Runs `git diff-tree --root --no-commit-id --name-status -r <commit>`.
- Keeps only paths whose status starts with `A` or `M`.
- Keeps only paths matching `.pit/sessions/*.json`.

Returns:

- Repo-relative `Path` objects for matching session files.

Why this matters: it is the core commit-scoping primitive used by
`pit show <commit>`.

### `is_session_path(path: str) -> bool`

Checks whether a path is an MVP pit session file.

Returns:

- `True` when the path starts with `.pit/sessions/` and ends with `.json`.
- `False` otherwise.

### `read_session_from_commit(paths: PitPaths, commit: str, session_path: Path) -> dict`

Reads and parses one session file from a commit object.

Inputs:

- `paths`: repository paths.
- `commit`: Git revision.
- `session_path`: repo-relative session path.

Returns:

- Parsed JSON object as a dictionary.

Raises:

- `GitError` if `git show <commit>:<path>` fails.
- `json.JSONDecodeError` if the file is not valid JSON.
- `PitError` if the parsed JSON is not an object.

## JSON Helpers

### `write_json_if_missing(path, data: dict) -> None`

Writes JSON only if the target file does not already exist.

Inputs:

- `path`: file path to create.
- `data`: dictionary to serialize.

Side effects:

- May write indented UTF-8 JSON with a trailing newline.
- Does not modify existing files.

### `read_json(path, label: str) -> dict`

Reads a JSON object from disk.

Inputs:

- `path`: file to read.
- `label`: user-facing label used in error messages.

Returns:

- Parsed JSON dictionary.

Raises:

- `PitError` if the file is missing or does not contain a JSON object.
- `json.JSONDecodeError` for invalid JSON syntax.
- `OSError` for filesystem failures.

## Diagnostics

### `run_diagnostics() -> list[DiagnosticCheck]`

Builds the complete `pit doctor` check list.

Checks:

- current directory is inside a Git repository
- `.pit/config.json` exists and is parseable
- `.pit/state.json` is ignored by Git
- prompt source path is valid
- `pre-commit` hook exists, contains the pit block, and is executable
- `post-commit` hook exists, contains the pit block, and is executable

Returns:

- A list of `DiagnosticCheck` values.

Side effects:

- Runs Git commands and reads files.
- Does not write files or print prompt contents.

### `prompt_source_path_check(config: dict, paths: PitPaths) -> DiagnosticCheck`

Validates the configured prompt source path for diagnostics.

Inputs:

- `config`: parsed `.pit/config.json`.
- `paths`: repository paths.

Returns:

- `DiagnosticCheck` with `OK` or `FAIL`.

Validation rules:

- `prompt_source` must be an object.
- `prompt_source.path` must be a non-empty string.
- legacy Codex history paths fail with an actionable fix.
- supported source types are `codex` and `fixture`.
- Codex paths must exist and be directories.
- Fixture paths must exist and be files.

### `state_ignore_is_healthy(paths: PitPaths) -> bool`

Checks whether `.pit/state.json` is ignored by Git.

Returns:

- `True` when `git check-ignore .pit/state.json` succeeds.
- `False` when Git reports the path is not ignored.

### `hook_health_issues(paths: PitPaths) -> list[str]`

Collects health issues for both pit-managed hooks.

Returns:

- A list of strings prefixed with the hook name, such as
  `pre-commit: missing`.

### `single_hook_issues(paths: PitPaths, hook_name: str) -> list[str]`

Checks one Git hook file.

Inputs:

- `paths`: repository paths.
- `hook_name`: hook filename, such as `pre-commit`.

Returns:

- `[]` when the hook is healthy.
- Issue strings for missing, unreadable, missing managed block, or not
  executable.

### `warn_if_legacy_codex_config(paths: PitPaths) -> None`

Prints a warning if `.pit/config.json` uses old Codex history paths.

Behavior:

- Reads config when it exists.
- Checks `is_legacy_codex_config()`.
- Prints a warning to stderr when needed.

Side effects:

- stderr output only.

## Init And Hook Installation Helpers

### `ensure_state_ignored(paths: PitPaths) -> None`

Ensures `.pit/state.json` appears in the repository `.gitignore`.

Behavior:

- Reads existing `.gitignore` lines when the file exists.
- Returns unchanged if the ignore entry already exists exactly.
- Appends `.pit/state.json` otherwise.

Side effects:

- May create or rewrite `.gitignore`.

### `install_hooks(paths: PitPaths) -> None`

Installs or updates pit blocks in local Git hooks.

Behavior:

- Builds commands for `pre-commit` and `post-commit`.
- Calls `install_hook()` for each hook file under `.git/hooks/`.

Side effects:

- Writes hook files and marks them executable.

### `pit_hook_command(paths: PitPaths, hook_name: str) -> str`

Builds the shell command stored in a Git hook.

Inputs:

- `paths`: repository paths.
- `hook_name`: `pre-commit` or `post-commit`.

Returns:

- A POSIX-shell-quoted absolute executable command when pit can find one.
- Fallback `pit hook <hook_name>` when no executable path can be found.

### `find_pit_executable(paths: PitPaths) -> Path | None`

Finds the most stable executable path for hook installation.

Search order:

1. Active `sys.argv[0]` when it resolves to an executable file.
2. `pit` found on `PATH`.
3. Repo-root `pit` script in the target repository.

Returns:

- Resolved executable path, or `None`.

### `executable_from_argv0() -> Path | None`

Resolves `sys.argv[0]` into an executable file path when possible.

Behavior:

- Handles absolute paths.
- Handles relative paths containing a path separator by resolving them against
  the current working directory.
- Ignores bare command names because those are better handled by `PATH`.

Returns:

- Resolved executable path, or `None`.

### `executable_from_path() -> Path | None`

Finds `pit` on `PATH`.

Returns:

- Resolved path from `shutil.which("pit")` when executable.
- `None` when not found or not executable.

### `is_executable_file(path: Path) -> bool`

Checks whether a path is a regular executable file.

Returns:

- `True` when `path.is_file()` and `os.access(path, os.X_OK)` are both true.
- `False` otherwise.

### `shell_quote(value: str) -> str`

Quotes a string for POSIX shell single-quoted contexts.

Behavior:

- Wraps the value in single quotes.
- Escapes embedded single quotes using the standard `'"'"'` sequence.

Used for hook commands so paths with spaces or quotes still run correctly.

### `install_hook(path, command: str) -> None`

Creates or updates one Git hook file.

Inputs:

- `path`: hook file path.
- `command`: pit hook command to place inside the managed block.

Behavior:

- Ensures the hooks directory exists.
- Creates a default `#!/bin/sh` hook when missing.
- Inserts or updates the managed pit block.
- Marks the hook executable for user, group, and others.

Side effects:

- Writes a hook file.
- Changes file mode.

### `managed_hook_block(command: str) -> str`

Formats the pit-managed hook block.

Returns:

- A string containing `HOOK_BEGIN`, the command, and `HOOK_END`, each on its own
  line, ending with a newline.

### `upsert_managed_block(existing_text: str, block: str) -> str`

Inserts or replaces the pit-managed block inside hook text.

Behavior:

- If a valid existing pit block is found, replaces only that block.
- Preserves text before and after the block.
- If no valid block is found, appends the new block.
- Handles missing trailing newlines cleanly.

Returns:

- New hook text.
