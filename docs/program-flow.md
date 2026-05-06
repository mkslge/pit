# Program Flow Deep Dive

This document explains how pit works as a whole program. The function reference
files describe individual pieces; this guide explains how those pieces cooperate
during real user flows.

The core product loop is:

```sh
./pit init
git add .
git commit -m "..."
./pit show HEAD
```

The important idea is that pit does not replace Git. It uses normal Git hooks to
add one extra committed file, `.pit/sessions/<session-id>.json`, to an ordinary
commit.

## Mental Model

pit has three kinds of state:

1. **Repo configuration** in `.pit/config.json`
2. **Local capture state** in `.pit/state.json`
3. **Committed prompt sessions** in `.pit/sessions/*.json`

These files have different lifetimes.

`.pit/config.json` is project configuration. It is meant to be committed so the
repository records that pit is enabled and which prompt source type is expected.

`.pit/state.json` is local working state. It remembers what this machine has
already captured and whether a capture is pending between `pre-commit` and
`post-commit`. It is ignored because another developer's local capture marker is
not meaningful on your machine.

`.pit/sessions/*.json` files are the product output. They are committed with the
code changes, so future readers can inspect which prompts were attached to the
commit.

## High-Level Architecture

The modules divide responsibility like this:

- `pit` is the checkout script that makes `src/` importable and calls
  `pit.cli.main()`.
- `src/pit/cli.py` is the orchestrator. It parses commands, coordinates capture,
  installs hooks, and prints command output.
- `src/pit/git.py` is the Git boundary. It runs Git commands and raises
  `GitError` when Git fails.
- `src/pit/paths.py` discovers the repo root, Git directory, and `.pit` paths.
- `src/pit/prompts.py` reads prompts from supported sources.
- `src/pit/session.py` writes session JSON files.
- `src/pit/state.py` loads and saves local state.

When reading code, start in `cli.py`. Most product behavior enters there and then
fans out to the smaller modules.

## CLI Startup

Every command starts the same way:

```text
repo-root ./pit
  -> add <repo>/src to sys.path
  -> import pit.cli.main
  -> main()
```

`main()` in `src/pit/cli.py` does three things:

1. Calls `build_parser()` to create the command parser.
2. Parses argv.
3. Calls the selected handler through `args.func(args)`.

For example:

- `./pit init` dispatches to `cmd_init()`.
- `./pit hook pre-commit` dispatches to `cmd_hook_pre_commit()`.
- `./pit show HEAD` dispatches to `cmd_show()`.

`main()` also defines the user-facing error boundary. Expected operational
failures such as bad Git commands, bad JSON, invalid state, and unreadable prompt
sources are caught and printed as:

```text
pit: <error message>
```

That is why helpers raise typed exceptions instead of printing directly.

## Path Discovery

Most commands begin by calling `discover_paths()` from `src/pit/paths.py`.

That function asks Git two questions:

```sh
git rev-parse --show-toplevel
git rev-parse --git-dir
```

From those answers it builds a `PitPaths` object:

```text
repo_root     /path/to/repo
git_dir       /path/to/repo/.git
pit_dir       /path/to/repo/.pit
config_file   /path/to/repo/.pit/config.json
state_file    /path/to/repo/.pit/state.json
sessions_dir  /path/to/repo/.pit/sessions
```

This is a useful pattern: commands do not repeatedly compute paths by hand. They
receive one object that names all filesystem locations involved in pit.

If the current directory is not inside a Git repository, Git fails and
`discover_paths()` ultimately raises `GitError`.

## `pit init`

`pit init` prepares a repository for automatic prompt attachment.

Call flow:

```text
main()
  -> cmd_init()
     -> discover_paths()
     -> create .pit/
     -> create .pit/sessions/
     -> write_json_if_missing(.pit/config.json, DEFAULT_CONFIG)
     -> write_json_if_missing(.pit/state.json, DEFAULT_STATE)
     -> ensure_state_ignored()
     -> install_hooks()
     -> warn_if_legacy_codex_config()
```

The default config is:

```json
{
  "version": 1,
  "prompt_source": {
    "type": "codex",
    "path": "~/.codex/sessions"
  }
}
```

The default state is:

```json
{
  "last_captured_at": null,
  "last_seen_prompt_id": null,
  "pending_session_file": null,
  "pending_captured_at": null,
  "pending_last_seen_prompt_id": null
}
```

The most important part of init is hook installation.

`install_hooks()` installs two hook files:

```text
.git/hooks/pre-commit
.git/hooks/post-commit
```

Each hook gets a managed block:

```sh
# BEGIN pit managed block
<pit executable> hook pre-commit
# END pit managed block
```

The post-commit hook is the same shape but calls `hook post-commit`.

The managed block matters because a repository might already have hook content.
`upsert_managed_block()` replaces only pit's block when it already exists, or
appends pit's block when it does not. This avoids overwriting unrelated hook
logic.

## Choosing The Hook Command

`pit_hook_command()` builds the command written into each hook. It asks
`find_pit_executable()` for the most stable executable path.

Search order:

1. The active executable from `sys.argv[0]`, if it is a real executable path.
2. A `pit` command found on `PATH`.
3. A repo-root `pit` script in the repository being initialized.
4. Fallback to `pit hook <hook-name>`.

Paths are quoted with `shell_quote()` so hook commands survive spaces or quotes
in filenames.

For the current checkout-oriented workflow, running:

```sh
./pit init
```

usually writes an absolute path to the repo-root `pit` script into the hook.
That makes the hook less dependent on your interactive shell's `PATH`.

## Normal Commit Flow

After init, the user commits normally:

```sh
git add .
git commit -m "..."
```

Git runs hooks automatically around the commit:

```text
git commit
  -> .git/hooks/pre-commit
     -> pit hook pre-commit
        -> cmd_hook_pre_commit()
           -> capture_pending_prompts()
  -> Git creates commit if pre-commit succeeds
  -> .git/hooks/post-commit
     -> pit hook post-commit
        -> cmd_hook_post_commit()
           -> promote_pending_capture()
```

This split is the core reliability mechanism.

The pre-commit hook creates and stages the session file before the commit exists.
The post-commit hook updates local state only after Git successfully creates the
commit.

## Pre-Commit Capture

`cmd_hook_pre_commit()` is intentionally small:

```text
cmd_hook_pre_commit()
  -> discover_paths()
  -> if .pit/ missing: return 0
  -> capture_pending_prompts(paths)
```

The real work is in `capture_pending_prompts()`.

Call flow:

```text
capture_pending_prompts()
  -> read .pit/config.json
  -> load .pit/state.json
  -> if pending_session_file exists:
       stage it again
       return "pending"
  -> prompt_source_from_config()
  -> source.read_prompts()
  -> filter_uncaptured_prompts()
  -> if no new prompts:
       return "empty"
  -> write_session()
  -> git add .pit/sessions/<session-id>.json
  -> write pending fields to .pit/state.json
  -> return (session_id, prompt_count)
```

There are three outcomes.

### Outcome 1: Existing Pending Session

If `.pit/state.json` contains `pending_session_file` and that file still exists,
pit does not create a second session file. It stages the existing pending file
again and returns `"pending"`.

This handles a failed commit retry. If the first commit attempt failed after
pre-commit, the prompts should be reused, not duplicated.

### Outcome 2: No New Prompts

If the prompt source has no prompts after `last_seen_prompt_id`, pit returns
`"empty"` and does not stage a session file.

The commit proceeds as a normal Git commit with no pit session attached.

### Outcome 3: New Prompts

If new prompts exist, pit writes a session file like:

```json
{
  "session_id": "2026-05-06_ab12cd34",
  "captured_at": "2026-05-06T20:15:00Z",
  "commit": null,
  "tool": "codex",
  "source": {
    "type": "codex",
    "path": "~/.codex/sessions"
  },
  "prompts": [
    {
      "id": "prompt-id",
      "timestamp": "2026-05-06T20:10:00Z",
      "text": "Prompt text"
    }
  ],
  "summary": ""
}
```

Then pit stages it:

```sh
git add .pit/sessions/<session-id>.json
```

Finally, it writes pending state:

```json
{
  "pending_session_file": ".pit/sessions/2026-05-06_ab12cd34.json",
  "pending_captured_at": "2026-05-06T20:15:00Z",
  "pending_last_seen_prompt_id": "prompt-id"
}
```

It does not yet update `last_seen_prompt_id`.

## Why Pending State Exists

This is the key subtlety.

Pre-commit happens before Git creates a commit. Many things can still fail after
pit writes the session file:

- another hook can fail
- Git can reject an empty commit
- the user can abort commit message editing

If pit updated `last_seen_prompt_id` during pre-commit, a failed commit could
make prompts look captured even though no commit contains their session file.

So pit uses a two-phase approach:

1. Pre-commit writes a session file and marks it pending.
2. Post-commit promotes the pending marker only after Git succeeds.

That is why `.pit/state.json` has both `last_*` and `pending_*` fields.

## Prompt Source Selection

`capture_pending_prompts()` does not know the details of Codex or fixture files.
It calls:

```text
prompt_source_from_config(config, repo_root)
```

That function reads `config["prompt_source"]["type"]`.

For `"fixture"` it returns `FixturePromptSource`.

For `"codex"` it returns `CodexPromptSource`.

Unsupported types raise `PromptSourceError`.

This is a small adapter pattern. The capture flow only needs an object with:

```python
read_prompts() -> list[Prompt]
```

Everything source-specific lives behind that method.

## Fixture Prompt Flow

Fixture sources are simple JSONL files. Each line looks like:

```json
{"id":"prompt-1","timestamp":"2026-05-06T10:00:00Z","text":"Fix the bug"}
```

`FixturePromptSource.read_prompts()`:

1. Opens the configured file.
2. Skips blank lines.
3. Parses each line as JSON.
4. Validates required fields with `parse_prompt()`.
5. Returns `Prompt` objects.

Fixture sources are mostly for development because they are deterministic and do
not touch real local Codex transcripts.

## Codex Prompt Flow

Codex sources read transcript JSONL files under `~/.codex/sessions`.

`CodexPromptSource.read_prompts()`:

1. Verifies the sessions root exists and is a directory.
2. Recursively scans for `*.jsonl`.
3. Calls `read_codex_transcript()` on each file.
4. Sorts all prompts by timestamp.

`read_codex_transcript()` has the privacy boundary.

It only captures from transcripts whose `session_meta` event says the transcript
working directory equals the current repository root:

```text
session_meta.payload.cwd == repo_root.resolve()
```

If the transcript has no cwd, or cwd points to another project, pit returns no
prompts from that transcript.

For matching transcripts, it captures only events where:

```text
payload.type == "user_message"
```

It ignores assistant messages, tool calls, and other event shapes.

Prompt text extraction prefers:

1. `payload.message`
2. `payload.text_elements` joined by newlines

Then pit derives a prompt ID:

```text
codex:<session-id>:<timestamp>:<text-hash>:<line-number>
```

The derived ID lets pit remember the last captured prompt even though Codex
events may not provide a simple stable prompt ID field.

## Filtering New Prompts

Once the prompt source returns a sorted list, pit calls:

```text
filter_uncaptured_prompts(prompts, state)
```

If `state["last_seen_prompt_id"]` is empty, every prompt is new.

If the marker appears in the prompt list, pit returns everything after it.

If the marker does not appear, pit returns the full list. This is conservative:
it avoids losing prompts if source history changed, but it can duplicate prompts
if the old marker disappeared from the source.

## Session File Creation

`write_session()` in `src/pit/session.py` writes the actual committed JSON file.

It chooses `captured_at`, builds a session ID, serializes prompts through
`Prompt.to_json()`, and writes:

```text
.pit/sessions/<session-id>.json
```

Session IDs look like:

```text
YYYY-MM-DD_ab12cd34
```

The date comes from the capture timestamp. The suffix comes from UUID4.

The file is not named after the commit SHA because the commit SHA does not exist
yet during pre-commit. The `"commit"` field also stays `null` because the MVP
does not amend commits just to write the SHA back into JSON.

## Post-Commit Promotion

After Git creates the commit, it runs the post-commit hook:

```text
cmd_hook_post_commit()
  -> discover_paths()
  -> if .pit/ missing: return 0
  -> promote_pending_capture(paths)
```

`promote_pending_capture()`:

1. Loads `.pit/state.json`.
2. If no `pending_last_seen_prompt_id` exists, returns.
3. Copies `pending_captured_at` to `last_captured_at`.
4. Copies `pending_last_seen_prompt_id` to `last_seen_prompt_id`.
5. Clears pending fields.
6. Saves state.

After promotion, the next commit will only capture prompts after that prompt ID.

## Manual Capture

`pit capture` calls the same `capture_pending_prompts()` function as the
pre-commit hook.

That means manual capture has the same semantics:

- it can reuse a pending session
- it can report no new prompts
- it can write and stage a new session file
- it writes pending state, not final captured state

The important difference is that `pit capture` is not followed by post-commit
unless the user then makes a successful commit. It is a debugging tool, not the
normal workflow.

## Status And Doctor

`pit status` is a concise operational summary.

It:

- confirms `.pit/` exists
- reads config and state
- counts uncaptured prompts when possible
- reports hook health as `OK` or `needs attention`

It is meant for quick checks.

`pit doctor` is deeper and read-only.

It runs `run_diagnostics()`, which checks:

- current directory is inside a Git repository
- `.pit/config.json` exists and is valid JSON
- `.pit/state.json` is ignored
- prompt source path is valid
- legacy Codex history path is not configured
- both hooks exist
- both hooks contain the pit managed block
- both hooks are executable

`doctor` returns exit code `1` if any diagnostic fails. That makes it useful for
scripts or preflight checks.

Neither command prints prompt contents.

## Inspecting Prompt History

pit has two inspection shapes:

```sh
./pit show <commit>
./pit log [commit]
```

`pit show <commit>` shows prompt text attached to one commit.

`pit log` without a commit walks history and summarizes commits that include pit
session files:

```text
a13f9c2 Fix buffer pool eviction
  pit session: 2026-05-06_ab12cd34
  prompts: 2
```

`pit log <commit>` is commit-scoped and uses the same rendering as
`pit show <commit>`.

The shared helper is:

```text
print_commit_prompts(paths, commit)
```

That helper calls:

```text
read_sessions_from_commit(paths, commit)
```

The commit-scoping primitive is:

```text
session_paths_changed_in_commit(paths, commit)
```

It runs:

```sh
git diff-tree --root --no-commit-id --name-status -r <commit>
```

Then it keeps only added or modified paths matching:

```text
.pit/sessions/*.json
```

This matters because it does not search all previous history. It looks only at
session files changed by the selected commit. That is why `pit log HEAD` shows
only prompts attached to HEAD, not prompts from earlier commits.

After it finds session paths, `read_session_from_commit()` reads each file from
the commit object with:

```sh
git show <commit>:.pit/sessions/<session-id>.json
```

This is important because pit reads the file as it existed in that commit, not
whatever happens to be in the working tree today.

## Failure Handling

The error strategy is layered.

Low-level Git failures become `GitError`.

Prompt source failures become `PromptSourceError`.

Invalid local state becomes `StateError`.

CLI-specific user errors become `PitError`.

`main()` catches these expected exceptions and converts them to clean stderr
messages and exit code `1`.

Unexpected programming errors are not caught. During MVP development, that is
useful because it keeps real bugs visible.

## Why Hooks Cannot See Prompts By Themselves

Git hooks know Git events: a commit is about to happen, a commit just happened,
and so on. They do not know what the user typed into Codex.

That is why the MVP needs a prompt source. For now the supported real source is
Codex local transcript files. The hook is only the trigger; the prompt adapter is
what actually reads prompt history.

This separation is the core design:

```text
Git hook = when to capture
Prompt source = what to capture
Session file = how to attach it to Git history
State file = how to avoid duplicates and survive failed commits
```

## Full End-To-End Example

Imagine this sequence:

```sh
./pit init
# user asks Codex: "Fix cache eviction"
git add .
git commit -m "Fix eviction"
./pit show HEAD
```

The internal flow is:

```text
./pit init
  -> creates .pit/config.json
  -> creates .pit/state.json
  -> creates .pit/sessions/
  -> ignores .pit/state.json
  -> installs pre-commit and post-commit hooks

git commit
  -> pre-commit hook runs
     -> reads .pit/config.json
     -> reads .pit/state.json
     -> reads Codex transcripts for this repo
     -> selects prompts after last_seen_prompt_id
     -> writes .pit/sessions/2026-05-06_ab12cd34.json
     -> git add .pit/sessions/2026-05-06_ab12cd34.json
     -> records pending state
  -> Git creates the commit
  -> post-commit hook runs
     -> promotes pending_last_seen_prompt_id to last_seen_prompt_id
     -> clears pending state

./pit show HEAD
  -> finds .pit/sessions/*.json added by HEAD
  -> reads that JSON from HEAD with git show
  -> prints the prompt text
```

At the end, the commit contains both code changes and the pit session JSON file.
The local state file knows which prompt ID was last captured, so the next commit
starts from the correct point.

## How To Read The Code

If you are learning the codebase, use this path:

1. Read `pit`, the repo-root script. It shows how the development entrypoint
   reaches `pit.cli.main()`.
2. Read `main()` and `build_parser()` in `src/pit/cli.py`.
3. Read `cmd_init()` to understand repository setup.
4. Read `capture_pending_prompts()` carefully. It is the central capture
   function.
5. Read `promote_pending_capture()` to understand why state is two-phase.
6. Read `prompt_source_from_config()` and `CodexPromptSource.read_prompts()` to
   understand where prompts come from.
7. Read `write_session()` to understand what gets committed.
8. Read `print_commit_prompts()` and `session_paths_changed_in_commit()` to
   understand inspection.

Once those functions make sense, the rest of the project is mostly supporting
infrastructure.
