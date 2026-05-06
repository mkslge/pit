MVP: pit, a Git-native prompt history layer

Implementation planning note

Future agents should read `PLAN.md` before making code changes. This file defines the product behavior and MVP boundaries; `PLAN.md` contains the detailed implementation phases, code structure, testing plan, and open questions.

Goal: automatically store the prompts/context used with an AI coding agent alongside the code changes they produced.

Core idea

A developer runs `pit init` once in a Git repo. After that, they keep using their normal AI coding tool and their normal Git workflow. When they create a commit, pit automatically attaches the prompts made since the previous commit.

Example:

```sh
pit init

# User works normally in their AI coding agent.
# User makes prompts normally.
# User edits code normally.

git add .
git commit -m "Fix buffer pool eviction"
```

The resulting commit contains both the code changes and a `.pit/sessions/<session-id>.json` file with the prompt history for that commit.

Important product point

Git hooks can detect commits, but they cannot magically see prompts typed into an AI coding agent. For this MVP to work with no per-prompt user action, pit must read prompts from a supported source.

For the first MVP, support one prompt source only.

Recommended MVP source:

- Codex local transcript/history files, if available and readable.

Alternative MVP sources:

- Cursor local conversation export/history, if available.
- A `pit` wrapper around an agent command, for example `pit run codex`, but this is less aligned with the desired "only run `pit init`" flow.
- A background watcher started by `pit init`, but this is more operationally complex.

The cleanest MVP is not "pit records every possible AI tool." The cleanest MVP is "pit automatically records prompts from one explicitly supported AI tool."

User flow

```sh
pit init
git add .
git commit -m "..."
pit show HEAD
```

No `pit start`.

No `pit prompt`.

No `pit commit`.

File structure

```text
.pit/
  config.json
  state.json
  sessions/
    2026-05-01_abc123.json
```

`.pit/config.json` is committed. It describes how pit is configured for the repo.

Example:

```json
{
  "version": 1,
  "prompt_source": {
    "type": "codex",
    "path": "~/.codex/sessions"
  }
}
```

`.pit/state.json` is local working state and should not be committed.

Example:

```json
{
  "last_captured_at": "2026-05-01T20:15:00Z",
  "last_seen_prompt_id": "prompt_abc123"
}
```

Session files are committed.

Example:

```json
{
  "session_id": "2026-05-01_abc123",
  "captured_at": "2026-05-01T21:03:00Z",
  "commit": null,
  "tool": "codex",
  "source": {
    "type": "codex",
    "path": "~/.codex/sessions"
  },
  "prompts": [
    {
      "id": "prompt_abc123",
      "timestamp": "2026-05-01T20:16:00Z",
      "text": "Fix the LRU eviction bug in BufferPoolManager"
    },
    {
      "id": "prompt_def456",
      "timestamp": "2026-05-01T20:24:00Z",
      "text": "Add tests for dirty page eviction"
    }
  ],
  "summary": ""
}
```

Use session IDs for filenames. Do not name files by commit SHA in the MVP. This avoids the SHA/amend problem because the session file must be created before the commit exists.

Commands

`pit init`

Initializes pit in the current Git repo.

Creates:

```text
.pit/
  config.json
  state.json
  sessions/
```

Installs local Git hooks:

- `pre-commit`
- `post-commit`

Ensures `.pit/state.json` is ignored by Git.

During MVP development, `pit init` may require the user to choose or confirm the prompt source once. After that, prompt capture should be automatic.

`pit status`

Shows whether pit is initialized, which prompt source is configured, and how many uncaptured prompts are currently available.

Example:

```text
pit initialized
Prompt source: codex
Uncaptured prompts: 2
Will attach prompts automatically on the next git commit.
```

`pit capture`

Manually performs the same capture work that the `pre-commit` hook performs.

This is useful for debugging, but should not be part of the normal user flow.

`pit show <commit>`

Shows the prompt history attached to a commit.

Example:

```sh
pit show HEAD
```

Output:

```text
Commit: a13f9c2 Fix buffer pool eviction

Prompts:
1. Fix the LRU eviction bug in BufferPoolManager
2. Add tests for dirty page eviction
```

Git hook behavior

`pre-commit`

Runs:

```sh
pit hook pre-commit
```

Behavior:

1. Read `.pit/config.json`.
2. Read `.pit/state.json`.
3. Read prompts from the configured prompt source.
4. Select prompts newer than the last captured prompt.
5. If there are no new prompts, do nothing and allow the commit.
6. If there are new prompts, write `.pit/sessions/<session-id>.json`.
7. Stage that session file with `git add .pit/sessions/<session-id>.json`.
8. Update `.pit/state.json` with the newest captured prompt marker.

`post-commit`

Runs:

```sh
pit hook post-commit
```

Behavior:

1. If the previous `pre-commit` created a session file, optionally record the resulting commit SHA in local state.
2. Do not amend the commit just to write the SHA into the session JSON.

Implementation strategy

For `pit show`, detect session files added or modified in the selected commit, then read them with:

```sh
git show <commit>:.pit/sessions/<session-file>
```

Prompt inspection should go through `pit show <commit>`.

For hook installation:

- Write directly to `.git/hooks/pre-commit` and `.git/hooks/post-commit`.
- If a hook already exists, do not overwrite it silently. Either append a clearly marked pit block or fail with instructions.
- Hook scripts should call the installed `pit` executable.

MVP constraints

Do not build:

- cloud sync
- replay mode
- prompt-to-line attribution
- support for every AI coding agent
- secret or background Git commits
- commit-SHA-named session files

Build only:

- CLI
- local Git repo support
- JSON prompt sessions
- Git hook installation
- automatic prompt capture from one supported source
- automatic prompt attachment to normal Git commits
- status/capture/show/log commands

Best first implementation language

Use Python or Go.

Python is fastest for MVP:

```sh
pit init
pit status
git add .
git commit -m "..."
pit show HEAD
```

One-sentence pitch

pit is a Git-native CLI that automatically attaches AI prompt history to ordinary Git commits, so every commit can explain not just what changed, but what the developer asked the agent to do.
