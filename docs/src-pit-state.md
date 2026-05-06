# `src/pit/state.py`

`state.py` owns local state file loading and saving. `.pit/state.json` is local
working state and should be ignored by Git.

## Constants

### `DEFAULT_STATE`

Default state shape:

```json
{
  "last_captured_at": null,
  "last_seen_prompt_id": null,
  "pending_session_file": null,
  "pending_captured_at": null,
  "pending_last_seen_prompt_id": null
}
```

Field meanings:

- `last_captured_at`: timestamp of the last successfully promoted capture.
- `last_seen_prompt_id`: prompt marker used to avoid recapturing prompts.
- `pending_session_file`: repo-relative session file staged by pre-commit but
  not yet promoted by post-commit.
- `pending_captured_at`: capture timestamp for the pending session.
- `pending_last_seen_prompt_id`: newest prompt ID in the pending session.

## Exceptions

### `StateError`

Raised when `.pit/state.json` exists but is structurally invalid.

## Functions

### `load_state(path: Path) -> dict`

Loads local pit state.

Inputs:

- `path`: `.pit/state.json`.

Behavior:

- If the file does not exist, returns a fresh copy of `DEFAULT_STATE`.
- Parses JSON when the file exists.
- Requires the JSON value to be an object.
- Merges parsed keys over `DEFAULT_STATE`, so newly introduced fields get
  defaults even when older state files omit them.

Returns:

- State dictionary.

Raises:

- `StateError` when the JSON value is not an object.
- `json.JSONDecodeError` for invalid JSON syntax.
- `OSError` for filesystem errors.

### `save_state(path: Path, state: dict) -> None`

Writes local pit state.

Inputs:

- `path`: `.pit/state.json`.
- `state`: dictionary to serialize.

Behavior:

- Serializes with two-space indentation.
- Writes UTF-8 text.
- Adds a trailing newline.

Side effects:

- Creates or replaces the state file.

Important boundary: this function does not itself check whether the state file
is ignored by Git. That responsibility lives in `cli.ensure_state_ignored()`.
