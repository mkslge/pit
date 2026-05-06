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

For implementation scope and open questions, read `AGENTS.md` and `PLAN.md`.
