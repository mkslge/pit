# pit

pit is a Git-native prompt history layer for AI coding sessions.

The MVP records prompts from local Codex transcript files and attaches them to ordinary Git commits as JSON session files.

## Flow

```sh
pit init
git add .
git commit -m "..."
pit show HEAD
```

There is no `pit start`, `pit prompt`, or `pit commit`. Keep using normal Git commands.

## Install Locally

From this checkout, install pit into your active Python environment:

```sh
python -m pip install -e .
```

That exposes a real `pit` console command. The repo-root `./pit` script remains available for development.

## What `pit init` Creates

```text
.pit/
  config.json
  state.json
  sessions/
```

Committed:

- `.pit/config.json`
- `.pit/sessions/*.json`

Ignored local state:

- `.pit/state.json`

`pit init` also installs local Git hooks:

```text
.git/hooks/pre-commit
.git/hooks/post-commit
```

The hook files contain a clearly marked pit block and preserve any existing hook content outside that block.

## Codex Source

The default MVP source is Codex local transcript JSONL files:

```json
{
  "version": 1,
  "prompt_source": {
    "type": "codex",
    "path": "~/.codex/sessions"
  }
}
```

pit scans `~/.codex/sessions/YYYY/MM/DD/*.jsonl`, keeps transcripts whose `session_meta.payload.cwd` matches the current Git repo root, and captures only user prompt events where `payload.type == "user_message"`.

pit does not capture assistant responses, tool calls, shell output, or transcripts from unrelated repos.

Older configs that point Codex at `~/.codex/history` or `~/.codex/history.jsonl` are not valid for this MVP source. Update `.pit/config.json` to use `~/.codex/sessions`.

## Commands

```sh
pit status
```

Shows initialization state, prompt source, uncaptured prompt count, and local paths.

```sh
pit capture
```

Manually performs the same capture work as the pre-commit hook. This is mainly for debugging.

```sh
pit log
```

Lists commits that include pit session files.

```sh
pit show HEAD
```

Shows the prompts attached to a commit.

## Hook Behavior

Before a commit, `pre-commit` reads new prompts, writes `.pit/sessions/<session-id>.json`, stages that file, and records pending state.

After a successful commit, `post-commit` promotes pending state to `last_seen_prompt_id`.

This split prevents prompt loss: if a commit fails after pre-commit, the prompts are still pending and will be reused on the next attempt.

## Development

From this repo, run the development entrypoint:

```sh
./pit --help
```

If using hooks before pit is installed globally, run `./pit init`; the hook installer will use this repo's `pit` executable by absolute path.
