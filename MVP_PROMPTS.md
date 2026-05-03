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

## Prompt 6: Real Codex Source Investigation

```text
Read AGENTS.md, PLAN.md, and the current implementation. Do not implement the parser yet.

Investigate the local Codex prompt/transcript storage format on this machine.

Goals:
- locate likely Codex transcript/history files
- determine whether the format is JSON, JSONL, SQLite, or something else
- determine whether user prompts are distinguishable from assistant responses and tool output
- determine whether stable prompt IDs exist
- determine whether transcripts can be associated with the current repo

Do not expose private prompt contents in the final response. Summarize file locations, schemas, and fields safely.

Update PLAN.md if the real findings change the Codex source design.
```

## Prompt 7: Codex Source Adapter

```text
Read AGENTS.md, PLAN.md, and the Codex source investigation notes. Implement Phase 6 only.

Add the real Codex prompt source adapter.

Requirements:
- parse the real Codex transcript/history format
- extract only user prompts
- include timestamp, text, and a stable prompt id if available
- if no stable id exists, derive one deterministically from timestamp plus content hash
- avoid capturing prompts from unrelated repos if the source format gives enough context
- keep fixture source tests working
- add sanitized test fixtures matching the real Codex format

After coding, test:
- pit status counts uncaptured Codex prompts
- pit capture writes a session from Codex prompts
- normal git commit attaches Codex prompts without pit prompt

Explain privacy assumptions and any remaining limitations.
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
