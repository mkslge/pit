"""Prompt source adapters."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Protocol


class PromptSourceError(Exception):
    """Raised when a prompt source cannot be read."""


@dataclass(frozen=True)
class Prompt:
    id: str
    timestamp: str
    text: str

    def to_json(self) -> dict[str, str]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "text": self.text,
        }


class PromptSource(Protocol):
    def read_prompts(self) -> list[Prompt]:
        """Read prompts from the source."""


@dataclass(frozen=True)
class FixturePromptSource:
    path: Path

    def read_prompts(self) -> list[Prompt]:
        if not self.path.exists():
            raise PromptSourceError(f"fixture prompt source not found: {self.path}")

        prompts: list[Prompt] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    raw_prompt = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise PromptSourceError(
                        f"invalid JSONL at {self.path}:{line_number}: {exc}"
                    ) from exc
                prompts.append(parse_prompt(raw_prompt, self.path, line_number))
        return prompts


@dataclass(frozen=True)
class CodexPromptSource:
    sessions_root: Path
    repo_root: Path

    def read_prompts(self) -> list[Prompt]:
        if not self.sessions_root.exists():
            raise PromptSourceError(f"Codex sessions path not found: {self.sessions_root}")
        if not self.sessions_root.is_dir():
            raise PromptSourceError(
                f"Codex sessions path is not a directory: {self.sessions_root}"
            )

        prompts: list[Prompt] = []
        for transcript_path in sorted(self.sessions_root.glob("**/*.jsonl")):
            prompts.extend(read_codex_transcript(transcript_path, self.repo_root))
        return sorted(prompts, key=lambda prompt: prompt.timestamp)


def prompt_source_from_config(config: dict, repo_root: Path) -> PromptSource:
    prompt_source = config.get("prompt_source")
    if not isinstance(prompt_source, dict):
        raise PromptSourceError("config prompt_source must be a JSON object")

    source_type = prompt_source.get("type")
    if source_type == "fixture":
        raw_path = prompt_source.get("path")
        if not isinstance(raw_path, str) or not raw_path:
            raise PromptSourceError(
                "fixture prompt_source.path must be a non-empty string"
            )
        return FixturePromptSource(resolve_source_path(raw_path, repo_root))
    if source_type == "codex":
        raw_path = prompt_source.get("path")
        if not isinstance(raw_path, str) or not raw_path:
            raise PromptSourceError("codex prompt_source.path must be a non-empty string")
        return CodexPromptSource(
            sessions_root=resolve_source_path(raw_path, repo_root),
            repo_root=repo_root,
        )

    raise PromptSourceError(f"unsupported prompt source type: {source_type or 'missing'}")


def resolve_source_path(raw_path: str, repo_root: Path) -> Path:
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return path
    return repo_root / path


def parse_prompt(raw_prompt: object, path: Path, line_number: int) -> Prompt:
    if not isinstance(raw_prompt, dict):
        raise PromptSourceError(
            f"invalid prompt at {path}:{line_number}: expected object"
        )

    prompt_id = raw_prompt.get("id")
    timestamp = raw_prompt.get("timestamp")
    text = raw_prompt.get("text")
    if not isinstance(prompt_id, str) or not prompt_id:
        raise PromptSourceError(f"invalid prompt id at {path}:{line_number}")
    if not isinstance(timestamp, str) or not timestamp:
        raise PromptSourceError(f"invalid prompt timestamp at {path}:{line_number}")
    if not isinstance(text, str):
        raise PromptSourceError(f"invalid prompt text at {path}:{line_number}")

    return Prompt(id=prompt_id, timestamp=timestamp, text=text)


def read_codex_transcript(path: Path, repo_root: Path) -> list[Prompt]:
    session_id: str | None = None
    session_cwd: Path | None = None
    prompt_events: list[tuple[int, dict, str]] = []

    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise PromptSourceError(
                    f"invalid Codex JSONL at {path}:{line_number}: {exc}"
                ) from exc
            if not isinstance(event, dict):
                raise PromptSourceError(
                    f"invalid Codex event at {path}:{line_number}: expected object"
                )

            payload = event.get("payload")
            if not isinstance(payload, dict):
                continue

            if event.get("type") == "session_meta":
                raw_session_id = payload.get("id")
                if isinstance(raw_session_id, str) and raw_session_id:
                    session_id = raw_session_id
                raw_cwd = payload.get("cwd")
                if isinstance(raw_cwd, str) and raw_cwd:
                    session_cwd = Path(raw_cwd).expanduser().resolve()
                continue

            if payload.get("type") != "user_message":
                continue
            timestamp = event.get("timestamp")
            if not isinstance(timestamp, str) or not timestamp:
                timestamp = payload.get("timestamp")
            if not isinstance(timestamp, str) or not timestamp:
                raise PromptSourceError(
                    f"Codex user prompt missing timestamp at {path}:{line_number}"
                )
            prompt_events.append((line_number, payload, timestamp))

    if session_cwd is None or session_cwd != repo_root.resolve():
        return []

    if session_id is None:
        session_id = path.stem

    prompts = []
    for line_number, payload, timestamp in prompt_events:
        text = codex_user_message_text(payload)
        if not text:
            continue
        prompt_id = derived_codex_prompt_id(
            session_id=session_id,
            timestamp=timestamp,
            text=text,
            line_number=line_number,
        )
        prompts.append(Prompt(id=prompt_id, timestamp=timestamp, text=text))
    return prompts


def codex_user_message_text(payload: dict) -> str:
    message = payload.get("message")
    if isinstance(message, str):
        return message

    text_elements = payload.get("text_elements")
    if isinstance(text_elements, list):
        texts = [element for element in text_elements if isinstance(element, str)]
        return "\n".join(texts)
    return ""


def derived_codex_prompt_id(
    session_id: str,
    timestamp: str,
    text: str,
    line_number: int,
) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    return f"codex:{session_id}:{timestamp}:{digest}:{line_number}"
