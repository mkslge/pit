# pit

pit is an experimental Git-native prompt history layer for AI coding sessions.

This repository is not prepared for a user-facing package release yet. For now,
work from the development checkout and use the repo-root `./pit` entrypoint.

## Prototype Flow

```sh
./pit init
git add .
git commit -m "..."
./pit show HEAD
```

The MVP stores local pit metadata under `.pit/` and uses Git hooks to attach
captured prompt sessions to ordinary commits.

## Commands

Run commands from inside a Git repository. Because this is still a checkout-only
prototype, examples use the repo-root `./pit` script.

### Initialize Pit

```sh
./pit init
```

Creates `.pit/config.json`, `.pit/state.json`, `.pit/sessions/`, ensures
`.pit/state.json` is ignored, and installs local `pre-commit` and `post-commit`
hooks.

### Check Status

```sh
./pit status
```

Shows the repo path, configured prompt source, uncaptured prompt count, sessions
directory, last captured prompt marker, and hook health.

### Run Diagnostics

```sh
./pit doctor
```

Runs read-only checks for Git discovery, pit config, state ignore rules, prompt
source path validity, legacy Codex config, and installed hooks.

### Capture Manually

```sh
./pit capture
```

Runs the same capture work as the pre-commit hook. This is mainly for debugging;
normal use is to let `git commit` trigger capture automatically.

### Inspect A Commit

```sh
./pit show HEAD
./pit show <commit-sha>
```

Shows only the pit session files attached to that commit and prints each prompt
with a visible prompt separator.

### Hook Internals

```sh
./pit hook pre-commit
./pit hook post-commit
```

These are internal commands installed into Git hooks by `./pit init`. You
normally should not run them directly unless you are debugging hook behavior.

## Normal Commit Example

```sh
./pit init

# Work normally in Codex and edit files.

git add .
git commit -m "Fix buffer pool eviction"
./pit show HEAD
```

If new prompts are available from the configured source, the commit includes a
new `.pit/sessions/<session-id>.json` file.

For implementation scope and open questions, read `AGENTS.md` and `PLAN.md`.
