# `src/pit/session.py`

`session.py` creates committed pit session JSON files. A session file is written
before the Git commit exists, so its filename is based on a generated session ID
rather than a commit SHA.

## Functions

### `utc_now() -> str`

Returns the current UTC time in the timestamp format used by pit.

Behavior:

- Uses timezone-aware UTC.
- Drops microseconds.
- Replaces the `+00:00` suffix with `Z`.

Returns:

- ISO-like UTC timestamp string such as `2026-05-06T14:23:00Z`.

Side effects:

- None.

### `make_session_id(captured_at: str | None = None) -> str`

Creates a session ID suitable for a filename.

Inputs:

- `captured_at`: optional timestamp. When omitted, `utc_now()` is used.

Behavior:

- Takes the first 10 characters of the timestamp as the date.
- Appends an underscore and the first 8 hex characters of a UUID4.

Returns:

- String shaped like `YYYY-MM-DD_ab12cd34`.

Why UUID is used: the session must be named before Git creates the commit, and
multiple captures can happen on the same day.

### `write_session(sessions_dir: Path, source_config: dict, prompts: list[Prompt], captured_at: str | None = None) -> tuple[str, Path, str]`

Writes a pit session JSON file.

Inputs:

- `sessions_dir`: `.pit/sessions` directory.
- `source_config`: prompt source config copied into the session.
- `prompts`: prompts to serialize.
- `captured_at`: optional capture timestamp for deterministic tests or callers.

Behavior:

1. Uses `captured_at` or `utc_now()`.
2. Generates a session ID.
3. Builds a session JSON object with:
   - `session_id`
   - `captured_at`
   - `commit: null`
   - `tool`
   - `source`
   - `prompts`
   - `summary`
4. Ensures `sessions_dir` exists.
5. Writes indented UTF-8 JSON with a trailing newline.

Returns:

- `(session_id, session_path, captured_at)`.

Side effects:

- Creates `sessions_dir` if needed.
- Writes `.pit/sessions/<session-id>.json`.

MVP constraint: the `commit` field is left as `null`; pit does not amend commits
to write the final commit SHA into the session file.
