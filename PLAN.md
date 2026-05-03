# pit MVP Implementation Plan

This plan implements the current MVP described in `AGENTS.md`: after `pit init`, prompt history is captured automatically from one supported AI prompt source and attached to ordinary Git commits.

For copy-pasteable implementation prompts, see `MVP_PROMPTS.md`.

The core engineering constraint is worth repeating: Git hooks can detect commits, but they cannot see prompts by themselves. Automatic capture requires a readable prompt source. The MVP should support exactly one source first, then generalize later.

## 1. Implementation Decision

The repository currently contains a CMake/C++ skeleton:

```text
CMakeLists.txt
main.cpp
```

Default implementation path for this repo:

- Implement `pit` as a Python CLI.
- Keep dependencies minimal and prefer the Python standard library.
- Use `argparse` for command dispatch.
- Use `pathlib` for filesystem work.
- Use `json` for config, state, and session files.
- Use `subprocess.run` for Git commands.

Reasoning for an intern:

- Python is the fastest path for this MVP because most of the work is filesystem, JSON, subprocess, and Git-hook orchestration.
- The existing CMake/C++ files are just a skeleton and should not drive the architecture.
- Avoid adding a packaging framework too early. A simple executable Python entrypoint is enough until the behavior is proven.

If the project owner decides to return to C++ later, preserve the behavior and tests from this plan.

## 2. MVP User Flow

The intended flow is:

```sh
pit init
git add .
git commit -m "..."
pit show HEAD
```

There should be no required:

- `pit start`
- `pit prompt`
- `pit commit`

The user controls commits with normal Git. pit only attaches prompt history automatically.

## 3. Data Model

After initialization:

```text
.pit/
  config.json
  state.json
  sessions/
```

Committed files:

- `.pit/config.json`
- `.pit/sessions/*.json`

Ignored local state:

- `.pit/state.json`

### `.pit/config.json`

Example:

```json
{
  "version": 1,
  "prompt_source": {
    "type": "codex",
    "path": "~/.codex/history"
  }
}
```

Responsibilities:

- Describes the repo-level pit configuration.
- Should be stable across machines where possible.
- May need path expansion for `~`.

### `.pit/state.json`

Example:

```json
{
  "last_captured_at": "2026-05-01T20:15:00Z",
  "last_seen_prompt_id": "prompt_abc123",
  "pending_session_file": null
}
```

Responsibilities:

- Tracks local capture progress.
- Prevents attaching the same prompt repeatedly.
- May track a pending session between `pre-commit` and `post-commit`.

Important implementation detail:

- Do not update `state.json` too early in a way that loses prompts if the commit fails.
- Safer approach: during `pre-commit`, write pending state separately or mark prompts as pending; during `post-commit`, promote pending markers to committed markers.

### Session Files

Example:

```json
{
  "session_id": "2026-05-01_abc123",
  "captured_at": "2026-05-01T21:03:00Z",
  "commit": null,
  "tool": "codex",
  "source": {
    "type": "codex",
    "path": "~/.codex/history"
  },
  "prompts": [
    {
      "id": "prompt_abc123",
      "timestamp": "2026-05-01T20:16:00Z",
      "text": "Fix the LRU eviction bug in BufferPoolManager"
    }
  ],
  "summary": ""
}
```

Rules:

- Name files by session ID, not commit SHA.
- Generate session IDs before the commit exists.
- Leave `"commit": null` for MVP. Do not amend commits just to write the SHA.
- Prefer ISO-8601 UTC timestamps.

## 4. Commands

### `pit init`

Responsibilities:

1. Verify the current directory is inside a Git worktree.
2. Find the repo root with `git rev-parse --show-toplevel`.
3. Create `.pit/`.
4. Create `.pit/sessions/`.
5. Create `.pit/config.json` if missing.
6. Create `.pit/state.json` if missing.
7. Ensure `.pit/state.json` is ignored by Git.
8. Install or update local Git hooks.
9. Print a concise success message.

Hook installation policy:

- Write to `.git/hooks/pre-commit` and `.git/hooks/post-commit`.
- If a hook does not exist, create it.
- If a hook exists and already contains the pit managed block, update that block.
- If a hook exists without a pit block, append a clearly marked pit block rather than overwriting it.
- Make hook files executable.

Pit hook block shape:

```sh
# BEGIN pit managed block
pit hook pre-commit
# END pit managed block
```

For `post-commit`, use:

```sh
# BEGIN pit managed block
pit hook post-commit
# END pit managed block
```

Intern note:

- Appending is friendlier than replacing because many repos already use hooks.
- A future improvement would support `core.hooksPath`, but direct `.git/hooks` is acceptable for MVP.

### `pit status`

Responsibilities:

1. Verify `.pit/config.json` exists.
2. Load config and state.
3. Probe the prompt source.
4. Count uncaptured prompts.
5. Print a human-readable status.

Example:

```text
pit initialized
Prompt source: codex
Uncaptured prompts: 2
Will attach prompts automatically on the next git commit.
```

Failure cases:

- Not in Git repo.
- `.pit/` missing.
- Prompt source path missing.
- Prompt source exists but cannot be parsed.

### `pit capture`

Manual debug command that performs the same capture as `pit hook pre-commit`.

Responsibilities:

1. Read config and state.
2. Read source prompts.
3. Select prompts not yet captured.
4. If none exist, print that nothing was captured.
5. If prompts exist, write a session file.
6. Stage the session file unless a `--no-stage` flag is later added.

Normal users should not need this command. It exists so developers can debug capture behavior without making commits.

### `pit hook pre-commit`

Responsibilities:

1. Be quiet on success.
2. If pit is not initialized, do nothing and allow commit.
3. Read config and state.
4. Read new prompts from the configured source.
5. If no new prompts exist, allow commit.
6. Write `.pit/sessions/<session-id>.json`.
7. Stage it with `git add .pit/sessions/<session-id>.json`.
8. Record pending capture metadata in `.pit/state.json`.

Important edge case:

- If session writing fails, fail the hook and block the commit. A commit that claims to be captured but silently missed prompts is worse than a visible failure.

### `pit hook post-commit`

Responsibilities:

1. Be quiet on success.
2. If no pending capture exists, do nothing.
3. Read the new commit SHA with `git rev-parse HEAD`.
4. Promote pending capture metadata to the latest captured marker.
5. Clear pending state.

Important edge case:

- If `pre-commit` captured prompts but the commit failed, `post-commit` will not run. The next capture should either reuse the pending session file or safely replace it without losing prompts.

### `pit log`

Responsibilities:

1. Walk Git history for commits touching `.pit/sessions/*.json`.
2. For each matching commit, read the session file from that commit.
3. Print short commit SHA, subject, session ID, and prompt count.

Likely Git commands:

```sh
git log --name-only --pretty=format:%H%x09%s -- .pit/sessions
git show <commit>:.pit/sessions/<file>
```

### `pit show <commit>`

Responsibilities:

1. Resolve the commit.
2. Detect `.pit/sessions/*.json` files added or modified by that commit.
3. Read each session file using `git show`.
4. Print prompts in chronological order.

Likely Git commands:

```sh
git diff-tree --no-commit-id --name-only -r <commit>
git show <commit>:.pit/sessions/<file>
```

## 5. Prompt Source Adapter

Create a small internal interface for prompt sources.

Conceptual shape:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Prompt:
    id: str
    timestamp: str
    text: str

class PromptSource:
    def read_prompts(self) -> list[Prompt]:
        raise NotImplementedError
```

MVP source:

- `codex`

Required investigation:

- Locate the actual Codex local transcript/history format on disk.
- Confirm whether it includes user prompts, timestamps, and stable IDs.
- Confirm whether the format is JSON, JSONL, SQLite, or another structure.

Do not guess the final parser before checking the real source format.

Development fallback:

- Add a fixture/file prompt source for tests, for example:

```json
{
  "version": 1,
  "prompt_source": {
    "type": "fixture",
    "path": "testdata/prompts.jsonl"
  }
}
```

This lets the core Git/session behavior be implemented and tested while Codex transcript parsing is being confirmed.

## 6. Suggested Code Structure

Implement the MVP in Python with a small package-style layout:

```text
pit
src/
  pit/
    __init__.py
    __main__.py
    cli.py
    git.py
    hooks.py
    paths.py
    session.py
    state.py
    prompt_source.py
    sources/
      __init__.py
      fixture.py
      codex.py
tests/
  test_init.py
  test_hooks.py
  test_capture.py
  test_show_log.py
testdata/
  prompts.jsonl
pyproject.toml
  ...
```

Entrypoint options:

- For the earliest phase, a repo-root executable script named `pit` can call `src.pit.cli.main`.
- Once packaging is added, expose a console script named `pit` from `pyproject.toml`.

Keep responsibilities separated:

- CLI parsing should dispatch commands only.
- Git helpers should wrap subprocess calls.
- Prompt source code should only read prompts.
- Session code should only build and write session JSON.
- Hook code should orchestrate capture.

Intern note:

- This separation keeps the risky parts testable. Git operations, JSON serialization, and prompt parsing each fail in different ways, so mixing them all into one script makes debugging much harder.

## 7. Testing Plan

Use a temporary Git repo for integration tests.

Core tests:

1. `pit init` creates `.pit/config.json`, `.pit/state.json`, `.pit/sessions/`.
2. `pit init` installs executable `pre-commit` and `post-commit` hooks.
3. `pit init` does not erase an existing hook.
4. `.pit/state.json` is ignored by Git.
5. `pit status` reports configured source and uncaptured count.
6. `pit hook pre-commit` with no prompts creates no session file.
7. `pit hook pre-commit` with prompts creates and stages a session file.
8. A normal `git commit` includes `.pit/sessions/<session-id>.json`.
9. Failed commit does not permanently advance captured state.
10. `pit show HEAD` prints prompts attached to the commit.
11. `pit log` lists commits containing session files.

Manual smoke test:

```sh
PYTHONPATH=/path/to/pit/src python3 -m pit --help
tmpdir=$(mktemp -d)
cd "$tmpdir"
git init
git config user.email "test@example.com"
git config user.name "Test User"
PYTHONPATH=/path/to/pit/src python3 -m pit init
echo "hello" > hello.txt
git add .
git commit -m "initial"
PYTHONPATH=/path/to/pit/src python3 -m pit show HEAD
```

Adjust the smoke test once the real prompt source is implemented.

## 8. Error Handling Rules

Prefer clear, boring failures.

Examples:

- Not in Git repo: `pit: not inside a Git repository`
- Missing prompt source: `pit: prompt source not found: <path>`
- Invalid config: `pit: invalid .pit/config.json: <reason>`
- Existing malformed state: `pit: invalid .pit/state.json: <reason>`
- Hook install issue: `pit: could not update .git/hooks/pre-commit: <reason>`

Hook-specific behavior:

- Success should be quiet.
- Expected no-op should be quiet.
- Capture failure should print to stderr and return nonzero.

## 9. Implementation Phases

### Phase 1: CLI and Repo Plumbing

Deliver:

- Create the Python package layout under `src/pit/`.
- Add a repo-root executable script named `pit` or document using `PYTHONPATH=src python3 -m pit` during development.
- Implement `src/pit/__main__.py` so `python3 -m pit ...` works.
- Implement `src/pit/cli.py` with an `argparse` command parser.
- Implement `src/pit/git.py` with small helpers around `git rev-parse --show-toplevel`, `git rev-parse --git-dir`, and later `git add`.
- Implement `src/pit/paths.py` for resolving the repo root, `.pit/`, `.pit/config.json`, `.pit/state.json`, and `.pit/sessions/`.
- Implement `pit init`.
- Implement basic `pit status`.
- Leave the existing CMake/C++ skeleton alone unless the project owner asks to remove it.

Done when:

- Running `pit init` in a Git repo creates the expected files.
- Running `pit init` outside a Git repo fails clearly.
- Running `python3 -m pit --help` shows the available commands.
- Running `pit status` after initialization reports that pit is initialized.

### Phase 2: Hook Installation

Deliver:

- `pre-commit` hook install/update.
- `post-commit` hook install/update.
- Preserve existing hook contents.
- Make hooks executable.

Done when:

- Existing hooks remain intact.
- pit managed blocks are added once, not duplicated.

### Phase 3: Fixture Prompt Source

Deliver:

- Prompt source interface.
- Fixture JSONL source.
- Prompt filtering using state markers.
- Session file creation.

Done when:

- `pit capture` can read fixture prompts and write a valid session file.

### Phase 4: Commit Integration

Deliver:

- `pit hook pre-commit`.
- `pit hook post-commit`.
- Safe pending state handling.
- Automatic `git add` for generated session files.

Done when:

- A normal `git commit` includes the generated session file.
- Failed commits do not lose prompts.

### Phase 5: Show and Log

Deliver:

- `pit show <commit>`.
- `pit log`.
- Session file discovery from Git history.

Done when:

- `pit show HEAD` prints prompts from the latest commit.
- `pit log` lists commits with prompt sessions.

### Phase 6: Real Codex Source

Deliver:

- Locate and document Codex prompt history format.
- Implement `codex` source adapter.
- Add tests with sanitized fixtures matching the real format.

Done when:

- `pit status` can count uncaptured Codex prompts.
- Normal commits attach real Codex prompts without `pit prompt`.

## 10. Open Questions

These should be answered before claiming the automatic MVP is complete:

1. Where exactly does Codex store local user prompt transcripts on this machine and on other supported machines?
2. Are prompt IDs stable, or do we need to derive IDs from timestamp plus content hash?
3. Does the source distinguish user prompts from assistant responses and tool output?
4. How do we avoid capturing prompts from a different repo or unrelated coding session?
5. Should `.pit/config.json` store absolute prompt-source paths, or should user-specific paths stay in ignored local state?
6. What should happen when a commit is created with `--no-verify`, bypassing hooks?

## 11. Non-Goals for MVP

Do not implement yet:

- Background daemon.
- Cloud sync.
- IDE plugin.
- Support for every AI coding tool.
- Prompt-to-line attribution.
- Replay mode.
- Secret/background Git commits.
- Commit-SHA-named session files.

These are tempting, but each one increases the product surface before the core loop is proven.
