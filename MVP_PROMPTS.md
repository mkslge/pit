# Prompt Sequence for Making pit Installable

Use these prompts one at a time. Each prompt should be small enough for an agent to implement, test, and explain without broadening scope.

Before each prompt, make sure the agent reads:

- `AGENTS.md`
- `PLAN.md`
- `README.md`
- the current code tree

The MVP core loop already exists:

```sh
pit init
git add .
git commit -m "..."
pit show HEAD
```

The next goal is to make pit installable, testable, and practical to use outside this development checkout.

## Prompt 1: Python Packaging

```text
Read AGENTS.md, PLAN.md, README.md, and the current implementation. Implement packaging only.

Goal: make pit installable as a Python CLI with a real `pit` console command.

Requirements:
- add pyproject.toml using a standard backend such as hatchling or setuptools
- package the existing src/pit layout
- expose a console script named pit that calls pit.cli:main
- include README.md as project readme metadata
- declare a supported Python version
- do not add runtime dependencies unless truly needed
- keep the repo-root ./pit development entrypoint working
- do not change pit behavior beyond packaging

After coding, test in a temporary virtual environment:
- python -m pip install -e .
- pit --help
- pit --version
- pit init inside a temporary Git repo
- verify installed Git hooks call an installed pit command or otherwise work outside this repo checkout

Explain the packaging choice and how users should install pit locally.
```

## Prompt 2: Test Suite Foundation

```text
Read AGENTS.md, PLAN.md, README.md, and the current implementation. Add an automated test suite foundation only.

Goal: make core behavior testable with one command.

Requirements:
- choose pytest unless there is a strong reason not to
- add test dependencies under a development/test extra in pyproject.toml
- add tests/ with helpers for creating temporary Git repos
- tests should invoke the installed CLI or python module in a realistic way
- cover path discovery, JSON state loading, fixture prompt source parsing, and session writing
- keep tests isolated from the user's real ~/.codex by using fixtures
- do not hit network

After coding, run:
- python -m pytest
- python -m pip install -e .[test] in a fresh venv if feasible

Explain the test layout and how future tests should be added.
```

## Prompt 3: Hook Integration Tests

```text
Read AGENTS.md, PLAN.md, README.md, and the current implementation. Add focused hook integration tests.

Goal: lock down Git hook behavior before changing install paths further.

Requirements:
- test pit init creates pre-commit and post-commit hooks
- test repeated pit init does not duplicate managed blocks
- test existing hook content is preserved
- test hook files are executable
- test normal git commit attaches a session file using sanitized Codex fixtures
- test failed commit leaves last_seen_prompt_id unchanged and pending state set
- test retry after failed commit reuses one pending session and then promotes state
- use temporary Git repos and sanitized fixtures only

After coding, run:
- python -m pytest

Explain any platform assumptions about Git hooks and executable permissions.
```

## Prompt 4: Codex Source Tests and Edge Cases

```text
Read AGENTS.md, PLAN.md, README.md, and the current implementation. Strengthen Codex source parsing tests only.

Goal: make the Codex transcript adapter safe against real-world transcript variation.

Requirements:
- test repo cwd filtering includes matching transcripts
- test unrelated cwd transcripts are skipped
- test transcripts missing cwd are skipped
- test payload.type == "user_message" is captured
- test response_item payload.role == "user" is not captured
- test assistant messages and tool events are not captured
- test payload.message is preferred when present
- test payload.text_elements fallback works
- test deterministic prompt IDs remain stable across reads
- test invalid JSONL gives a useful error with file and line number
- do not use private local Codex transcripts in tests

After coding, run:
- python -m pytest

Explain the privacy boundary the adapter enforces.
```

## Prompt 5: Install-Aware Hook Command Strategy

```text
Read AGENTS.md, PLAN.md, README.md, and the current implementation. Improve hook command installation for installed use.

Goal: hooks should work when pit is installed globally, installed in a venv, or run from a development checkout.

Requirements:
- inspect the current hook command strategy
- prefer the active pit executable path when safe, for example sys.argv[0] or shutil.which("pit"), but preserve development checkout support
- avoid writing brittle commands that only work in the current shell session
- quote paths safely for POSIX shell hooks
- keep existing hook content and managed block update behavior
- document the assumptions in README.md

After coding, test:
- editable install in a venv, run pit init, then git commit succeeds from a temp repo
- development checkout ./pit init still writes working hooks
- repeated pit init updates existing pit block without duplication

Explain exactly what command the hook writes and why.
```

## Prompt 6: User-Facing Config Commands

```text
Read AGENTS.md, PLAN.md, README.md, and the current implementation. Add small config UX commands.

Goal: users should not need to hand-edit .pit/config.json for common setup checks.

Requirements:
- add `pit config show` to print current config safely
- add `pit config set-source codex [--path PATH]`
- add `pit config set-source fixture --path PATH` for tests/development
- validate source paths where practical
- never print prompt contents
- preserve unrelated config keys
- keep .pit/config.json committed project config
- keep .pit/state.json local ignored state

After coding, test in temporary repos:
- config show before init errors clearly
- set-source codex writes ~/.codex/sessions by default
- set-source fixture requires --path
- capture still works after setting fixture source

Explain why config is committed while state is ignored.
```

## Prompt 7: Safer Status and Doctor Checks

```text
Read AGENTS.md, PLAN.md, README.md, and the current implementation. Add diagnostic checks without changing capture behavior.

Goal: help users understand whether pit is ready before committing.

Requirements:
- improve pit status to show hook installation health
- add pit doctor or equivalent diagnostic command
- check Git repo detection
- check .pit/config.json existence and parseability
- check .pit/state.json ignore status
- check prompt source path validity
- check legacy ~/.codex/history config and explain the fix
- check whether pre-commit and post-commit hooks contain the pit managed block
- do not read or print prompt contents

After coding, test:
- healthy repo reports OK
- missing hooks report actionable fix
- legacy Codex path reports actionable fix
- fixture source remains supported

Explain the difference between status and doctor.
```

## Prompt 8: README and Install Documentation

```text
Read AGENTS.md, PLAN.md, README.md, and the current implementation. Improve documentation only.

Goal: a new user should be able to install, initialize, commit, and inspect prompt history without reading the source.

Requirements:
- document install from local checkout
- document editable install for development
- document normal flow: pit init, git add, git commit, pit show HEAD
- document what files are committed and ignored
- document Codex source assumptions and ~/.codex/sessions
- document hook behavior and how to troubleshoot hooks
- document privacy boundaries: what is captured and what is not
- document known limitations
- keep README concise but complete

After editing, verify commands in docs match actual CLI help.

Do not change runtime code.
```

## Prompt 9: Release Hygiene

```text
Read AGENTS.md, PLAN.md, README.md, and the current implementation. Add release hygiene without publishing anything.

Goal: prepare the repo for a local or future package release.

Requirements:
- add or update LICENSE if the project owner has chosen one; otherwise add a clear TODO section, not a fake license
- add CHANGELOG.md with an Unreleased section
- ensure version lives in one obvious place or document current version source
- ensure package metadata has author/project URLs only if known
- add MANIFEST or package-data config only if needed
- ensure testdata needed by tests is included appropriately
- do not publish to PyPI

After coding, test:
- python -m build if build tooling is available, or explain if not installed
- pip install from the built artifact if feasible

Explain what remains before an actual public release.
```

## Prompt 10: End-to-End Install Smoke Test

```text
Read AGENTS.md, PLAN.md, README.md, and the current implementation. Run and document a full install smoke test. Make code changes only for bugs found during the smoke test.

Goal: prove pit works as an installed CLI in a clean temporary repo.

Required smoke test:
- create a temporary virtual environment
- install pit from this checkout
- create a separate temporary Git repo
- configure sanitized Codex fixture source
- run pit init
- run pit status
- make a normal git commit
- verify .pit/sessions/*.json is committed
- run pit show HEAD
- run a second commit with no new prompts
- verify no extra session is created
- simulate a failed commit and verify pending state is not promoted

If bugs are found, fix them narrowly and rerun the failed part.

Return:
- exact commands run
- pass/fail summary
- any bugs fixed
- remaining limitations
- whether pit is usable to install locally
```

## Ongoing Prompt Template

Use this shape for any additional task:

```text
Read AGENTS.md, PLAN.md, README.md, and the current implementation. Work only on <specific installability or usability issue>.

Preserve the core flow:
pit init
git add .
git commit -m "..."
pit show HEAD

Implement the smallest complete change, run focused tests, and explain what changed, what was verified, and what remains.
```

## Not Yet

Avoid these until installability and local reliability are solid:

- cloud sync
- daemon/background watcher
- support for every AI coding tool
- IDE plugins
- prompt-to-line attribution
- replay mode
- rewriting Git history or amending commits to insert commit SHAs
