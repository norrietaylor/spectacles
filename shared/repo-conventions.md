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
  PRs, `sdd/<task-id>-<slug>` for implementation PRs. The branch prefix carries
  the pipeline routing signal; it is independent of the commit subject.
- Commit subjects: imperative mood, present tense, 72 characters or fewer.
  Use a conventional-commit type from the standard enum (`feat`, `fix`, `docs`,
  `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`); a
  target repo may lint commit subjects and reject anything else. The pipeline
  phase is **not** the commit type — encode it in the scope instead:
  `docs(spec-<slug>)`, `docs(arch-<slug>)`, and `<type>(<scope>)` mapped from
  the task's `kind:*` for implementation PRs (`kind:feature` → `feat`,
  `kind:bug` → `fix`, `kind:chore` → `chore`, `kind:spike` → `docs` — a
  spike's deliverable is its written finding, not a code change).
- A fix PR closes its issue with `Closes #N` in the description.
- Never force-push a branch that has an open PR.

## No private or hardcoded identities

No employer name, private org slug, internal repository name, internal URL,
cost figure, or contributor personal data belongs in any committed file,
issue, PR, or comment. The GitHub App identity, MCP endpoints, and org slug
are configuration, never literals in a workflow or fragment.
