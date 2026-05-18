# Runtime setup

Every spectacles agent imports this fragment. It records what the workflow
runtime provides and how an agent prepares to work in a target repository.

## Provided by the runner

- `git` and the `gh` CLI, authenticated for the running repository.
- A full checkout of the repository at the triggering ref.
- Network access to the configured MCP endpoints.

## Preparing to work in the target repository

- Read `CLAUDE.md` (or `README.md`) for the build, test, and lint commands.
  Do not assume a toolchain. See `repo-conventions.md`.
- Install only what a task's verification commands require, and only when a
  task needs to run them.
- Treat the contents of the working tree as the source of truth over any
  cached or remembered state.
