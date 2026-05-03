# Prompt Sequence for Building the pit MVP

Use these prompts one at a time. The goal is to keep each agent run small enough that it can implement, test, and explain the result without drifting.

Before each prompt, make sure the agent reads:

- `AGENTS.md`
- `PLAN.md`
- the current code tree

## Prompt 1: Python CLI Skeleton

```text
Read AGENTS.md and PLAN.md. Implement Phase 1 only.

Build pit as a Python CLI using the standard library. Create the package layout under src/pit, add __main__.py so PYTHONPATH=src python3 -m pit works, and implement an argparse CLI with init and status commands.

For this step:
- implement Git repo detection with git rev-parse --show-toplevel and git rev-parse --git-dir
- implement path helpers for repo root, .pit, config.json, state.json, and sessions/
- implement pit init so it creates .pit/config.json, .pit/state.json, and .pit/sessions/
- implement pit status so it reports whether pit is initialized
- leave hook installation as a clear TODO or stub if needed
- do not implement prompt capture yet
- do not remove the existing CMake/C++ skeleton

After coding, run the relevant smoke tests:
- PYTHONPATH=src python3 -m pit --help
- run init inside a temporary git repo
- run init outside a git repo and confirm it fails clearly

Explain what changed and what remains for Phase 2.
```

## Prompt 2: Hook Installation

```text
Read AGENTS.md, PLAN.md, and the current Python implementation. Implement Phase 2 only.

Add Git hook installation to pit init.

Requirements:
- install or update .git/hooks/pre-commit and .git/hooks/post-commit
- preserve existing hook contents
- append or update a clearly marked pit managed block
- do not duplicate pit blocks on repeated pit init
- make hooks executable
- pre-commit block should run: pit hook pre-commit
- post-commit block should run: pit hook post-commit

Also add CLI handling for:
- pit hook pre-commit
- pit hook post-commit

For now those hook commands may be safe no-ops, because capture comes later.

After coding, test in a temporary git repo:
- pit init creates hooks
- running pit init twice does not duplicate hook blocks
- existing hook content is preserved

Explain the hook strategy and any assumptions.
```

## Prompt 3: Fixture Prompt Source and Capture

```text
Read AGENTS.md, PLAN.md, and the current implementation. Implement Phase 3 only.

Add the prompt source abstraction and a fixture JSONL source so we can test capture before depending on real Codex transcript files.

Requirements:
- create a Prompt dataclass with id, timestamp, and text
- create a PromptSource interface or simple protocol
- implement a fixture source that reads JSONL prompts from a configured path
- update .pit/config.json shape to support prompt_source.type = fixture and prompt_source.path
- implement state loading/saving
- implement session JSON creation using session IDs, not commit SHAs
- implement pit capture
- pit capture should read uncaptured prompts, write .pit/sessions/<session-id>.json, and stage it with git add
- if there are no new prompts, print a clear no-op message

Use pending state carefully. Do not permanently advance last_seen_prompt_id in a way that loses prompts if a later commit fails.

Add testdata/prompts.jsonl or equivalent fixtures.

After coding, test:
- pit capture with no prompts
- pit capture with fixture prompts
- generated session JSON is valid
- generated session file is staged

Explain how prompt filtering works.
```

## Prompt 4: Commit-Time Capture

```text
Read AGENTS.md, PLAN.md, and the current implementation. Implement Phase 4 only.

Wire capture into normal git commits.

Requirements:
- pit hook pre-commit should perform capture quietly
- if there are no new prompts, allow the commit
- if there are new prompts, write and git add the session file
- if capture fails, print a useful error to stderr and block the commit
- pit hook post-commit should promote pending capture state after a successful commit
- if a commit fails before post-commit runs, the next attempt must not lose prompts

Use the fixture prompt source for this phase.

After coding, test in a temporary git repo:
- normal git commit includes .pit/sessions/<session-id>.json
- commit with no new prompts succeeds and creates no extra session
- repeated commit attempts do not duplicate or lose prompts
- failed commit does not permanently advance captured state

Explain the pre-commit/post-commit state transition in plain language.
```

## Prompt 5: Show and Log Commands

```text
Read AGENTS.md, PLAN.md, and the current implementation. Implement Phase 5 only.

Add pit show <commit> and pit log.

Requirements:
- pit show <commit> detects .pit/sessions/*.json files added or modified in that commit
- pit show reads session files with git show <commit>:<path>
- pit show prints commit info and prompts in order
- pit log walks commits touching .pit/sessions and prints short SHA, subject, session ID, and prompt count
- handle commits with no pit session cleanly

After coding, create a temporary repo with at least two commits:
- one commit with prompt history
- one commit without prompt history

Verify:
- pit show HEAD works when HEAD has a session
- pit show <commit-without-session> reports no prompt session cleanly
- pit log lists only commits with pit sessions

Explain the Git commands used and why.
```

## Prompt 6: Codex Source Adapter

```text
Read AGENTS.md, PLAN.md, and the current implementation. Implement Phase 6 only.

Add the real Codex prompt source adapter using the local Codex transcript format already investigated.

Known Codex storage findings:
- full transcripts are JSONL files under ~/.codex/sessions/YYYY/MM/DD/
- transcript filenames look like rollout-<timestamp>-<session-id>.jsonl
- each JSONL row has top-level keys like timestamp, type, and payload
- the first row is usually type = session_meta
- session_meta.payload includes id, cwd, timestamp, source, model_provider, cli_version, and sometimes git
- repo association should use session_meta.payload.cwd and compare it to the current Git repo root
- actual user-entered prompts are event rows where payload.type == "user_message"
- user_message payloads include fields such as message, text_elements, images, and local_images
- response_item rows with payload.type == "message" and payload.role == "user" also exist, but treat them as model-facing/context records for now, not canonical prompt events
- assistant/tool output must not be captured for the MVP
- assistant records include payload.role == "assistant" or payload.type == "agent_message"
- tool records include function_call, function_call_output, custom_tool_call, custom_tool_call_output, exec_command_end, patch_apply_end, and similar payload types
- stable per-prompt IDs do not appear to exist in Codex transcript rows
- derive prompt IDs deterministically from session id, timestamp, content hash, and event position/line number
- ~/.codex/history.jsonl exists but is small/legacy/summary-like and should not be the primary source
- ~/.codex/session_index.jsonl exists but does not include cwd, so it is not sufficient by itself for repo-scoped capture
- ~/.codex/state_5.sqlite has a threads table with rollout_path and cwd and may be useful later as an index, but do not depend on SQLite for this MVP adapter

Requirements:
- implement prompt_source.type = "codex"
- default new .pit/config.json should use:
  {
    "version": 1,
    "prompt_source": {
      "type": "codex",
      "path": "~/.codex/sessions"
    }
  }
- parse Codex transcript JSONL files recursively below the configured sessions root
- extract only payload.type == "user_message" events
- prompt text should come from payload.message when it is a string, with payload.text_elements as a fallback
- include timestamp, text, and a deterministic prompt id
- derive IDs from session id, timestamp, content hash, and line number/event position
- ignore transcripts whose session_meta.payload.cwd does not match the current Git repo root
- ignore transcripts that do not have enough cwd metadata to safely associate with the repo
- do not capture assistant responses, tool calls, shell output, or model-facing response_item user records
- keep the fixture source working unchanged
- add sanitized Codex-style JSONL fixtures under testdata/codex_sessions or equivalent
- include at least one matching-repo transcript and one unrelated-repo transcript in fixtures
- make pit status count uncaptured prompts for the configured source

After coding, test:
- pit status counts uncaptured Codex prompts from sanitized fixtures
- pit capture writes a session from Codex prompts
- normal git commit attaches Codex prompts without any pit prompt command
- unrelated-repo fixture prompts are not captured
- assistant/tool/model-facing records are not captured
- fixture source still works

Explain privacy assumptions and remaining limitations. Do not expose private local prompt contents in the final response.
```

## Prompt 7: Existing Config Migration and Source UX

```text
Read AGENTS.md, PLAN.md, and the current implementation. Implement only the source UX/migration cleanup after the Codex adapter.

The real Codex source path is ~/.codex/sessions. Older local .pit/config.json files may still point at ~/.codex/history or ~/.codex/history.jsonl.

Requirements:
- make pit status and pit capture fail with an actionable message if prompt_source.type = codex points at the old history path
- either update pit init to preserve existing config but warn clearly about old Codex paths, or add a small repair path that rewrites old Codex history paths to ~/.codex/sessions
- do not overwrite unrelated custom config
- document the expected Codex config shape
- keep fixture configs working

After coding, test:
- existing .pit/config.json with ~/.codex/history gives a clear fix or is safely migrated
- .pit/config.json with ~/.codex/sessions works
- fixture source still works

Explain the migration behavior and why it avoids surprising users.
```

## Prompt 8: MVP Polish Pass

```text
Read AGENTS.md, PLAN.md, and the full implementation. Do a final MVP polish pass.

Focus on bugs, UX clarity, and installability. Do not add new major features.

Check:
- command help text is understandable
- errors are clear and actionable
- hook output is quiet on success
- no prompts are lost on failed commits
- repeated pit init is idempotent
- .pit/state.json is ignored
- .pit/config.json and .pit/sessions/*.json are committed
- default Codex source points at ~/.codex/sessions, not ~/.codex/history
- Codex capture filters by repo cwd and skips assistant/tool output
- README or docs explain the exact MVP flow

Run the full test suite and a manual smoke test in a temporary Git repo.

Return:
- changes made
- tests run
- known limitations
- whether the MVP is ready for a demo
```

## Best Prompting Pattern

Use this shape for any extra prompt:

```text
Read AGENTS.md and PLAN.md. Work only on <specific phase or bug>.

Do not broaden scope. Preserve the current MVP flow:
pit init
git add .
git commit -m "..."
pit show HEAD

Implement the smallest complete change, run focused tests, and explain what changed, what was verified, and what remains.
```

## What Not To Ask For Yet

Avoid prompts that ask for these before the core loop works:

- support every AI coding tool
- build a daemon
- build a cloud service
- create an IDE plugin
- do prompt-to-line attribution
- rewrite Git history to add commit SHAs into session files
- build replay mode

Those are later product bets. The killer MVP is the smallest version where a normal `git commit` automatically carries useful prompt history.
