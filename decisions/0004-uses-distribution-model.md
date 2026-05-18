# ADR 0004: The `uses:` distribution model

- Status: Accepted
- Date: 2026-05-17

## Context

The suite is distributed onto a consumer repository by `scripts/quick-setup.sh`.
Three documents described that distribution incompatibly:

1. `quick-setup.sh` and `workflows/README.md` copied each compiled
   `.lock.yml` into the consumer's `.github/workflows/`, and the wrapper
   called it with a local `uses: ./.github/workflows/<agent>.lock.yml`.
2. ADR 0002 §4 said a consumer pulls shared fragments through pinned-ref
   `imports:`, which implies the consumer compiles its own workflows.
3. Neither is the GitHub-native model: a consumer references a hosted
   reusable workflow with a cross-repo `uses: owner/repo/.github/workflows/
   <agent>.lock.yml@<ref>`.

The copy model is also broken in practice. The compiled locks resolved their
prompt through gh-aw `{{#runtime-import}}` directives — the agent's own `.md`
source and the vendored `.github/aw/imports/` fragments — and `quick-setup.sh`
copied neither. An installed consumer rendered an empty prompt.

A naive fix to the copy model (also copy the `.md` and the imports tree) is
possible but distributes ~700 KB of generated locks plus a vendored import
cache to every consumer, and updating the suite means re-running the installer
on every consumer. The cross-repo `uses:` model distributes one small wrapper
per agent and updates with a ref bump.

Two gh-aw facts gate the `uses:` model:

- A lock that uses `{{#runtime-import}}` fails when called cross-repo: the
  import paths and the lock-file hash check resolve against the *caller* repo
  (gh-aw issues #24918, #24949). `inlined-imports: true` embeds every import
  into the lock at compile time, so the lock is self-contained.
- gh-aw compiles in strict mode by default. Strict mode emits a "Check
  workflow lock file" step that re-verifies the lock against its `.md` source
  at run time; called cross-repo it looks for the source in the caller repo,
  404s, and fails the job fatally. `strict: false` omits that step. This is
  the configuration `elastic/ai-github-actions` ships for its own
  `uses:`-distributed agentic workflows.

## Decision

1. **The suite is distributed by cross-repo `uses:`.** A consumer installs
   only the thin wrappers. Each wrapper calls a reusable workflow hosted in
   the spectacles repository:
   `uses: norrietaylor/spectacles/.github/workflows/<agent>.lock.yml@<ref>`.
   No `.lock.yml`, no agent `.md` source, and no `.github/aw/imports/` tree is
   placed on the consumer.

2. **Every agent lock compiles self-contained.** Each `sdd-*.md` and
   `distillery-sync.md` source sets `inlined-imports: true` and
   `strict: false`. The resulting lock embeds all imported content and carries
   no run-time lock-file check, so it is safe to invoke cross-repo.

3. **`distillery-sync` is a wrapped agent like the rest.** Its source becomes
   `on: workflow_call`; a new `wrappers/distillery-sync.yml` owns the daily
   `schedule` and `workflow_dispatch` triggers and calls the hosted reusable
   workflow. The distribution model is now uniform: every agent — scheduled or
   event-driven — is a hosted reusable workflow fronted by a thin wrapper.

4. **The installer pins a ref.** `quick-setup.sh` installs only the eight
   wrappers and rewrites the `@main` ref in each to the value of a new `--ref`
   option (default `main`). Pre-release the ref is `main`; it moves to release
   tags once releases are cut, the same progression ADR 0002 set for imports.

5. **The vendored import tree is not committed.** With `inlined-imports` the
   `.github/aw/imports/` tree is a compile cache with no run-time role.
   `gh aw compile` regenerates it; it is git-ignored.

## Reasoning

- The `uses:` model is the GitHub-native way to distribute reusable
  workflows. A consumer carries one auditable wrapper per agent, not a
  generated lock it cannot read.
- A suite update is a ref bump, not a re-install on every consumer.
- `inlined-imports` plus `strict: false` is the only compile configuration
  under which a gh-aw lock is correct when called cross-repo, and it is the
  configuration a real adopter (`elastic/ai-github-actions`) ships.
- spectacles is a public repository, so a consumer in any org can resolve the
  hosted reusable workflows without a cross-org token. Isolation between
  consumers stays enforced by `DISTILLERY_PROJECT` scoping and the consumer's
  own App identity.
- `strict: false` drops a compile-time validation set and the run-time
  lock-file check. The run-time check is incompatible with cross-repo `uses:`
  by construction. The compile-time validations are recovered by a `gh aw
  compile` drift gate in the spectacles `lint` workflow (see Verification),
  which is the correct place for them: in the suite's CI, not at every
  consumer's run time.

## Verification

- `gh aw compile` produces, for all seven `sdd-*` agents and
  `distillery-sync`, a `.lock.yml` with zero `{{#runtime-import}}` directives
  and no "Check workflow lock file" step.
- Each `wrappers/<agent>.yml` ends in a job with
  `uses: norrietaylor/spectacles/.github/workflows/<agent>.lock.yml@main`.
- `bash scripts/quick-setup.sh --target-repo <owner>/<name> --suite sdd
  --dry-run` lists only the eight wrappers, the issue templates, and the
  labels — no `.lock.yml` and no imports.
- `scripts/quick-setup.sh --ref <tag>` writes wrappers whose `uses:` lines
  pin `@<tag>`.
- The `lint` workflow runs `gh aw compile` and fails if any committed
  `.lock.yml` or `.md` is out of date.
- The fixture acceptance run (`docs/sdd/install.md`) completes with the
  consumer carrying only wrappers.

## Consequences

- This decision supersedes the copy-based distribution in `workflows/
  README.md` and the local `uses: ./` wrapper form. ADR 0002 §4 (a consumer
  pulls fragments via pinned-ref `imports:`) is superseded: a consumer pulls
  nothing and compiles nothing; it calls hosted, self-contained locks. ADR
  0002 §1–§3 (source layout, repo-root `shared/`, pinned-ref imports *within*
  spectacles) stand.
- Spec 01 requirement R9.1 and its `workflows/README.md` reference are
  updated to the `uses:` model; a correction note in the spec points here.
- The `.lock.yml` files roughly double in size from inlining. They are
  generated artifacts; size is not a consumer concern, since consumers no
  longer carry them.
- Editing a `shared/` fragment now requires a recompile for the change to
  reach the inlined locks. The `lint` compile-drift gate enforces this.
- A consumer pinned to a ref does not move until the operator re-runs the
  installer with a new `--ref`, or the ref itself moves. Pinning to a release
  tag is therefore stable; pinning to `main` tracks the suite.
