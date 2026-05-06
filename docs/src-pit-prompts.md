# `src/pit/prompts.py`

`prompts.py` owns prompt source adapters. The MVP supports fixture JSONL files
for tests/development and Codex local transcript JSONL files for real capture.

The module's privacy boundary is important: Codex parsing captures user prompts
from transcripts whose recorded working directory exactly matches the current
repository. Assistant messages, tool events, and unrelated repository
transcripts are ignored.

## Constants

### `CODEX_SESSIONS_PATH`

Canonical MVP Codex transcript root: `~/.codex/sessions`.

### `LEGACY_CODEX_HISTORY_PATHS`

Paths for older Codex history storage that this MVP intentionally rejects:

- `~/.codex/history`
- `~/.codex/history.jsonl`

## Exceptions And Protocols

### `PromptSourceError`

Raised when a prompt source cannot be read, parsed, or validated.

### `PromptSource`

Protocol for prompt source adapters.

Required method:

- `read_prompts() -> list[Prompt]`

Any source implementation that provides this method can be consumed by the
capture flow.

## Data Classes

### `Prompt`

Immutable representation of one user prompt.

Fields:

- `id`: stable prompt identifier.
- `timestamp`: timestamp string from the source.
- `text`: prompt text.

#### `Prompt.to_json(self) -> dict[str, str]`

Converts a `Prompt` into the session-file JSON shape.

Returns:

- `{"id": id, "timestamp": timestamp, "text": text}`.

Side effects:

- None.

### `FixturePromptSource`

Prompt source for newline-delimited JSON fixture files. This is useful for
development and tests because it avoids reading the user's real Codex data.

Field:

- `path`: JSONL fixture file.

#### `FixturePromptSource.read_prompts(self) -> list[Prompt]`

Reads all prompts from a fixture JSONL file.

Behavior:

- Requires the file to exist.
- Skips blank lines.
- Parses each non-blank line as JSON.
- Validates each object with `parse_prompt()`.
- Preserves file order.

Returns:

- List of `Prompt` objects.

Raises:

- `PromptSourceError` when the file is missing, a line is invalid JSON, or a
  prompt object is malformed.

### `CodexPromptSource`

Prompt source for local Codex transcript files.

Fields:

- `sessions_root`: root directory containing Codex session JSONL files.
- `repo_root`: repository root used for transcript working-directory filtering.

#### `CodexPromptSource.read_prompts(self) -> list[Prompt]`

Reads matching user prompts from Codex transcripts.

Behavior:

- Requires `sessions_root` to exist and be a directory.
- Recursively scans `**/*.jsonl`.
- Reads each transcript with `read_codex_transcript()`.
- Sorts all collected prompts by timestamp.

Returns:

- Timestamp-sorted `Prompt` objects from matching transcripts.

Raises:

- `PromptSourceError` if the sessions path is missing, is not a directory, or a
  transcript has invalid required data.

Privacy boundary:

- Transcripts whose recorded `cwd` does not equal the current repo root are
  skipped entirely.

## Source Selection

### `prompt_source_from_config(config: dict, repo_root: Path) -> PromptSource`

Builds the configured prompt source adapter.

Inputs:

- `config`: parsed `.pit/config.json`.
- `repo_root`: current Git repository root.

Supported source types:

- `fixture`: requires a non-empty `path` string.
- `codex`: requires a non-empty `path` string and rejects legacy history paths.

Returns:

- `FixturePromptSource` or `CodexPromptSource`.

Raises:

- `PromptSourceError` for missing/invalid `prompt_source`, missing path, legacy
  Codex paths, or unsupported source types.

### `resolve_source_path(raw_path: str, repo_root: Path) -> Path`

Resolves prompt source paths consistently.

Behavior:

- Expands `~`.
- Returns absolute paths unchanged.
- Resolves relative paths relative to the repository root.

Returns:

- A `Path` object. The path is not required to exist here.

### `is_legacy_codex_config(config: dict) -> bool`

Checks whether a config object points Codex at a legacy history path.

Returns:

- `True` only when `prompt_source.type == "codex"` and its path is a legacy
  Codex history path.
- `False` for malformed configs, other source types, or modern Codex paths.

### `is_legacy_codex_history_path(raw_path: str) -> bool`

Checks one path string against known legacy Codex history paths.

Behavior:

- Ignores a trailing slash.
- Also compares expanded `~` paths.

Returns:

- `True` for `~/.codex/history`, `~/.codex/history.jsonl`, or expanded
  equivalents.
- `False` otherwise.

### `legacy_codex_history_message(raw_path: str) -> str`

Builds the actionable error/warning text for legacy Codex path configs.

Returns:

- A message explaining that the MVP reads from `~/.codex/sessions` and showing
  the config replacement shape.

## Fixture Prompt Parsing

### `parse_prompt(raw_prompt: object, path: Path, line_number: int) -> Prompt`

Validates and converts a fixture prompt object.

Inputs:

- `raw_prompt`: parsed JSON value.
- `path`: source file path, used in errors.
- `line_number`: source line number, used in errors.

Required fields:

- `id`: non-empty string.
- `timestamp`: non-empty string.
- `text`: string. Empty text is allowed.

Returns:

- `Prompt`.

Raises:

- `PromptSourceError` when the JSON value is not an object or required fields
  are malformed.

## Codex Transcript Parsing

### `read_codex_transcript(path: Path, repo_root: Path) -> list[Prompt]`

Reads one Codex transcript JSONL file.

Inputs:

- `path`: transcript JSONL file.
- `repo_root`: current Git repository root.

Behavior:

1. Reads the transcript line by line.
2. Skips blank lines.
3. Parses each line as JSON.
4. Reads `session_meta` events to discover session ID and transcript `cwd`.
5. Collects payloads whose `payload.type == "user_message"`.
6. Rejects user prompt events without a timestamp.
7. Skips the whole transcript if the recorded `cwd` is missing or does not
   equal `repo_root.resolve()`.
8. Derives stable prompt IDs from session ID, timestamp, prompt text, and line
   number.

Returns:

- List of `Prompt` objects from that transcript.

Ignored events:

- assistant responses
- tool calls
- events without dict payloads
- user-looking `response_item` shapes that do not use `payload.type ==
  "user_message"`

Raises:

- `PromptSourceError` for invalid JSON lines, non-object events, or user prompt
  events missing timestamps.

### `codex_user_message_text(payload: dict) -> str`

Extracts text from a Codex user-message payload.

Priority:

1. `payload["message"]` when it is a string.
2. `payload["text_elements"]` when it is a list; only string elements are joined
   with newlines.
3. Empty string when neither shape provides text.

Returns:

- Extracted prompt text.

### `derived_codex_prompt_id(session_id: str, timestamp: str, text: str, line_number: int) -> str`

Builds a deterministic ID for a Codex prompt event.

Inputs:

- `session_id`: Codex session ID or transcript filename stem fallback.
- `timestamp`: prompt timestamp.
- `text`: prompt text.
- `line_number`: line number in the transcript.

Behavior:

- Hashes prompt text with SHA-256.
- Uses the first 16 hex characters of that hash.
- Combines session ID, timestamp, digest, and line number.

Returns:

- String shaped like `codex:<session-id>:<timestamp>:<digest>:<line-number>`.

Why line number is included: it helps distinguish repeated identical prompts in
the same session at the same timestamp.
