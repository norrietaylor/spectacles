# Repository conventions

Every spectacles agent imports this fragment so it can apply repository
conventions without restating them in each workflow prompt.

## Canonical doc surface

If the repository has a `CLAUDE.md` at its root, treat it as the authoritative
guide for build and test commands, code style, PR conventions, and
domain-specific constraints. Read it before any analysis or change. If
`CLAUDE.md` and the code disagree, flag the discrepancy rather than silently
preferring one. If there is no `CLAUDE.md`, fall back to `README.md`.

## Branch and commit conventions

Unless `CLAUDE.md` says otherwise:

- Branch names: `spec/<slug>` for spec PRs, `arch/<slug>` for architecture
  PRs, `sdd/<task-id>-<slug>` for implementation PRs.
- Commit subjects: imperative mood, present tense, 72 characters or fewer.
- A fix PR closes its issue with `Closes #N` in the description.
- Never force-push a branch that has an open PR.

## No private or hardcoded identities

No employer name, private org slug, internal repository name, internal URL,
cost figure, or contributor personal data belongs in any committed file,
issue, PR, or comment. The GitHub App identity, MCP endpoints, and org slug
are configuration, never literals in a workflow or fragment.
