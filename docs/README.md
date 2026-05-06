# pit Internal Documentation

This directory documents the current implementation of pit at the function level.
It is organized by Python file so a reader can move from source to docs without
having to infer where behavior lives.

The docs focus on:

- what each module owns
- what every function or method does
- inputs and return values
- side effects, such as filesystem writes or Git commands
- important exceptions and edge cases

## File Map

- [`program-flow.md`](program-flow.md): end-to-end explanation of how the program works across init, hooks, capture, state promotion, and inspection.
- [`src/pit/cli.py`](src-pit-cli.md): command-line parsing, command handlers, capture flow, diagnostics, and hook installation.
- [`src/pit/prompts.py`](src-pit-prompts.md): prompt source adapters for fixture files and Codex transcript files.
- [`src/pit/git.py`](src-pit-git.md): small Git command wrappers.
- [`src/pit/paths.py`](src-pit-paths.md): repository path discovery.
- [`src/pit/session.py`](src-pit-session.md): committed session JSON creation.
- [`src/pit/state.py`](src-pit-state.md): local state file loading and saving.
- [`src/pit/__init__.py`, `src/pit/__main__.py`, and `pit`](entrypoints.md): package metadata and entrypoints.

## Reading Order

For the main product flow, read in this order:

1. `program-flow.md` for the full system narrative.
2. `src-pit-cli.md`, starting with `cmd_init`, `capture_pending_prompts`, and `cmd_hook_post_commit`.
3. `src-pit-prompts.md`, especially `prompt_source_from_config` and `CodexPromptSource.read_prompts`.
4. `src-pit-session.md` for the JSON session shape written into `.pit/sessions/`.
5. `src-pit-git.md` and `src-pit-paths.md` for the Git repository assumptions.

## Design Boundary

pit deliberately keeps prompt capture local and Git-native. The core invariant is
that normal Git commits remain the unit of history: hooks create and stage a pit
session file before the commit, then local state is promoted after the commit
succeeds.
