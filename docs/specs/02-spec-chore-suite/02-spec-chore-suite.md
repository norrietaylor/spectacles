# 02-spec-chore-suite

> The repository is public. This file, and everything committed to the repo,
> carries no employer name, no private org slug, no internal repository name,
> no internal URL, no cost figure, and no contributor personal data. Patterns
> reused from prior private work are described generically and never
> attributed by name.

## Context

The issue-native SDD suite (`docs/specs/01-spec-issue-native-sdd/`) moves a
feature from a plain GitHub issue through a disciplined spec, triage, execute,
validate, and review pipeline. That pipeline is deliberate: it always designs
an architecture, always persists a record, always decomposes into a task
graph. That is correct for a feature. It is heavy for a chore.

Most maintenance work is not a feature. A doc has drifted from the code. A
public API gained a function that no changelog mentions. A module has no
tests. A dependency bumped a patch version. Two bots opened the same PR. None
of these needs a spec, an architecture record, or a task DAG. Each needs a
small, mechanical, well-evidenced fix. Routing them through `sdd-spec` and
`sdd-triage` adds latency and review surface for no design benefit, and it
crowds the SDD lifecycle queue with work that has no design content.

This spec stands up a **chore-bot suite**: a standalone fast-track that runs
alongside the SDD pipeline rather than inside it. A set of detector bots audit
whatever repository the suite is installed on and file labelled chore issues.
A `chore-fix` worker selects an open chore issue, drafts a fix, and opens a
pull request directly, bypassing `sdd-spec` and `sdd-triage` entirely. Two
PR-maintenance bots keep the resulting flow of bot pull requests tidy.

The suite is generic and repo-agnostic. Each bot audits and fixes the
repository it runs on, with no assumption about that repository's stack,
domain, or layout. The detectors read the target repo's `CLAUDE.md` (fallback
`README.md`) for conventions and toolchain exactly as the SDD agents do; they
hardcode nothing.

The chore suite is not a new foundation. It reuses spec 01's foundation
directly:

- **gh-aw** as the agentic-workflow engine, with the workflow layout and
  import model fixed by ADR 0002: sources at `.github/workflows/*.md` compiled
  to an adjacent `.lock.yml`, thin `wrappers/` for consumer distribution, and
  shared fragments at the repo-root `shared/` consumed via pinned-ref imports
  of the form `owner/repo/path@ref`.
- **The `needs-human` contract** from ADR 0001: the single, uniform
  agent-to-human hand-off marker. The chore bots inherit it unchanged. A bot
  that cannot proceed applies `needs-human`, posts one comment, and stops; a
  human clears the label to resume the bot.
- **The evidence-rigor standard** in `shared/rigor.md`: reproduce the finding,
  rule out false positives, cite a `file:line` or command output, bound the
  scope, one finding per issue, an 80% confidence floor. This standard governs
  what a detector is allowed to file. A detector that cannot meet it does not
  file.
- **The CI gates** from spec 01 Unit 1: lint, docs strict build, actionlint,
  shellcheck, and the secret-denylist `leak-scan`. Every chore-suite source
  and fragment runs against them.

The constraint that shaped spec 01 shapes this suite too: agentic workflows
run unattended in CI with no interactive prompt. Every point where a desktop
tool would ask a question becomes an asynchronous exchange through GitHub
issue and PR comments, with `needs-human` as the escalation lever.

One scoping point carries through from spec 01: the suite must work on
existing codebases. The detectors audit consumer repositories that already
carry substantial code and history, so the same code-intelligence dependency
applies. Where a detector benefits from symbol-level retrieval it uses the
Serena MCP fragment from spec 01 Unit 3; where it benefits from prior-finding
recall it uses the Distillery MCP fragment, scoped to the running repo's own
project so a shared store cannot leak unrelated content.

## Introduction/Overview

This spec stands up the **chore-bot suite**: eight agentic workflows that run
as a standalone fast-track alongside the SDD pipeline. Four are detectors that
audit the running repository and file labelled chore issues (`doc-drift`,
`api-surface-drift`, `test-coverage`, `trivial-dep-bump`). A fifth bot,
`dependency-review`, audits dependency-bumping pull requests but files no
chore issue: it posts an advisory risk comment on the pull request, so it is a
PR-advisory bot rather than an issue-filing detector. One is the `chore-fix`
worker that turns an open chore-labelled issue into a fix pull request
directly, bypassing spec and triage. Two are PR-maintenance bots that keep the
bot pull-request flow tidy (`pr-conflict-resolver`, `dedupe-prs`).

The fast-track is the design center. A detector files a chore issue carrying
an `agent:*` label. The `chore-fix` worker selects an `agent:*`-labelled issue
and opens a fix pull request that closes it. There is no spec file, no
architecture record, and no task graph for chore work. A chore that turns out
to need a design is handed to a human via `needs-human`, who may reopen it as
a feature or bug issue for the SDD pipeline; the chore suite never escalates a
chore into the SDD pipeline itself.

State lives in GitHub primitives only: chore issues carry an `agent:*` label
identifying their detector source, fixes arrive as pull requests, and every
human decision point is `needs-human` plus a comment. There is no external
queue and no separate UI. The suite dogfoods in its own repo and installs on
consumer repos through the same thin-wrapper distribution model as the SDD
suite.

## Goals

1. A maintenance finding reaches a fix pull request without a human authoring
   the finding or the fix by hand: a detector files an evidenced chore issue,
   the `chore-fix` worker drafts the fix, a human reviews and merges.
2. The chore fast-track is genuinely standalone: a chore issue never enters
   `sdd-spec` or `sdd-triage`, and the chore suite reuses but does not modify
   the SDD pipeline.
3. Every detector files only what `shared/rigor.md` permits: reproduced, false
   positives ruled out, evidence cited, scope bounded, one finding per issue,
   at or above 80% confidence. A detector that cannot meet the standard files
   nothing.
4. The `agent:*` label taxonomy is the chore-suite task board: a detector
   stamps its source label on every issue it files, and the `chore-fix` worker
   selects on it. `needs-human` remains the single hand-off marker.
5. The bots are generic and portable: each audits and fixes whatever repo it
   runs on, reads stack and convention from that repo's `CLAUDE.md` (fallback
   `README.md`), and carries no org-specific or private literal. One installer
   run adds the suite to another repo with no source edits.
6. The bot pull-request flow stays tidy without a human babysitting it:
   trivially conflicting bot PRs are resolved mechanically, non-trivial
   conflicts are handed off, and duplicate bot PRs are closed.
7. The chore suite reuses spec 01's foundation unchanged: the gh-aw layout and
   import model (ADR 0002), the `needs-human` contract (ADR 0001), the CI
   gates, and the evidence standard. It adds no second foundation.

## User Stories

- As a maintainer, I want a bot to notice that a user-facing doc no longer
  matches the code and file an evidenced issue, so drift is caught before a
  reader hits it.
- As a library author, I want a bot to flag a public-API change that no
  changelog records, so consumers are never surprised by an undocumented
  surface change.
- As whoever owns test health, I want a bot to file coverage-gap issues for
  untested code, so the gaps are tracked rather than forgotten.
- As a reviewer of a dependency-bumping pull request, I want a bot to post a
  risk read on the dependency change, so I review with the diff's blast radius
  already summarized.
- As a maintainer, I want safe, trivial dependency updates to arrive as ready
  pull requests I can merge, so routine bumps do not need my time to open.
- As a maintainer, I want a chore-labelled issue to turn into a fix pull
  request directly, without a spec or a triage round, so small work ships
  fast.
- As whoever is on triage this week, I want one `label:needs-human` filter
  that lists every chore issue or bot PR a bot handed back, the same filter
  the SDD suite uses, so I have one escalation queue, not two.
- As a maintainer, I want trivially conflicting bot pull requests rebased
  automatically and duplicate bot pull requests closed, so the bot PR list
  stays readable.

## Interaction Model

The chore suite is operated through the same four GitHub primitives as the SDD
suite: issues, comments, labels, and pull requests. This section is the
contract that the units below implement; it reuses ADR 0001 and adds only the
`agent:*` label taxonomy.

### The `agent:*` label taxonomy

Every chore issue a detector files carries exactly one `agent:*` label naming
the detector that filed it. The label is the chore-suite task board and the
selector the `chore-fix` worker reads.

| Label | Filed by | Marks |
|---|---|---|
| `agent:doc-drift` | `doc-drift` detector | a doc that diverged from the implementation |
| `agent:api-drift` | `api-surface-drift` detector | a public-API change missing from docs or changelog |
| `agent:coverage` | `test-coverage` detector | code lacking test coverage |
| `agent:dep-bump` | `trivial-dep-bump` detector | a safe, trivial dependency update |

`agent:dependency-review` is not a filing label: `dependency-review` posts a
review comment on an existing pull request rather than filing an issue, so it
needs no chore-issue label. The taxonomy is open: a future detector adds its
own `agent:*` label rather than reusing another bot's.

The `agent:*` label is a source marker, orthogonal to `kind:chore` (the
content category) and to `needs-human` (the hand-off state). A chore issue
carries `kind:chore` and one `agent:*` label; it gains `needs-human` only when
a bot hands it off.

### The fast-track lifecycle

A chore issue has a deliberately flat lifecycle, in contrast to the SDD
`sdd:*` label state machine:

1. A detector files an issue with `kind:chore` and one `agent:*` label.
2. The `chore-fix` worker selects an `agent:*`-labelled issue with no
   `needs-human` label and opens a fix pull request that closes it.
3. A human reviews and merges the pull request, which closes the issue.

There are no intermediate lifecycle labels. The chore suite does not use the
`sdd:*` labels and does not advance any SDD lifecycle state. A chore issue is
either open (and selectable), handed off (`needs-human`, skipped), or closed.

### The `needs-human` contract

The chore bots inherit the `needs-human` contract from ADR 0001 unchanged: a
bot applies `needs-human` via the `add-labels` safe-output at the terminal
step where it cannot safely proceed and posts exactly one comment; every bot
skips `needs-human`-labelled items in candidate selection; no bot ever clears
the label; clearing it fires an `unlabeled` event that re-triggers the bot
that applied it.

The chore-suite trigger table below extends ADR 0001's table; it does not
replace it.

| Bot | Applies `needs-human` when | Comment must include |
|---|---|---|
| any detector | a candidate finding cannot meet the `shared/rigor.md` standard but is judged genuinely risky; a finding's fix is not mechanical | the finding with `file:line` and why it is not auto-filable |
| `chore-fix` | the chore needs a design decision, touches a protected path, or cannot be implemented at or above 80% confidence; a proof artifact will not pass | what blocked it, with evidence, and whether the chore should become a feature or bug issue |
| `pr-conflict-resolver` | a merge conflict is not mechanically trivial to resolve | the conflicting files and why the resolution is not mechanical |
| `dedupe-prs` | duplicate detection is ambiguous (the pull requests overlap but are not clearly the same change) | the candidate pull requests and the overlap |

A `chore-fix` hand-off never silently promotes a chore into the SDD pipeline.
It hands the chore to a human, who decides whether to reopen it as a feature
or bug issue.

## Demoable Units of Work

> Requirement IDs use the format **R{unit}.{seq}**. The planner references
> these directly; do not renumber after approval.

### Unit 1: Chore label taxonomy and shared chore fragment

**Purpose:** Add the `agent:*` label taxonomy and a single importable chore
fragment on top of spec 01's foundation, so every chore bot states the
fast-track contract once instead of restating it per workflow. Demoable: the
labels sync onto a repo and the fragment passes the leak-scan.
**Depends on:** spec 01 Units 1 and 2
**Affected areas:** `templates/.github/labels.yml`,
`shared/chore-interaction.md` (new), `docs/sdd/index.md`

**Functional Requirements:**

- **R1.1**: `templates/.github/labels.yml` shall gain the `agent:*` taxonomy
  labels `agent:doc-drift`, `agent:api-drift`, `agent:coverage`, and
  `agent:dep-bump`, each with a hex color and a one-line description. The
  labels reuse a single shared hue so the taxonomy reads as one family.
- **R1.2**: `shared/chore-interaction.md` shall be a new importable gh-aw
  fragment, consumed via the pinned-ref `owner/repo/path@ref` import form per
  ADR 0002. It shall state the chore fast-track contract: the `agent:*`
  taxonomy and what each label marks, the flat chore lifecycle, the rule that
  a chore issue never enters `sdd-spec` or `sdd-triage`, and the chore-suite
  `needs-human` trigger table from this spec.
- **R1.3**: `shared/chore-interaction.md` shall reference, not restate, the
  `needs-human` contract: it shall cite `decisions/0001-needs-human.md` for
  the four clauses and add only the chore-specific trigger rows.
- **R1.4**: `shared/chore-interaction.md` shall state that a detector files
  only what `shared/rigor.md` permits and shall import or reference that
  fragment, so the evidence standard is the single gate on filing.
- **R1.5**: The fragment shall carry no employer name, no org slug, no bot
  name, no hostname, and no absolute path. The detector identity and any
  endpoint are configuration supplied at install.
- **R1.6**: `docs/sdd/index.md` shall gain a short section describing the
  chore fast-track as a standalone track parallel to the SDD pipeline, so a
  reader of the suite docs sees both tracks.

**Proof Artifacts:**

- File: `templates/.github/labels.yml` contains all four `agent:*` labels,
  each with a hex color and a description.
- File: `shared/chore-interaction.md` exists, references
  `decisions/0001-needs-human.md` and `shared/rigor.md`, and passes the
  `leak-scan` check.
- Test: running the existing `quick-setup.sh` label sync against a test repo
  creates the four `agent:*` labels, after which a test issue can be opened
  and labelled `agent:doc-drift`. This uses the spec 01 Unit 1 label-sync
  mechanism as is; it does not depend on the `--suite chore` flag added later.

### Unit 2: `doc-drift` and `api-surface-drift` detectors

**Purpose:** Stand up the two documentation-focused detectors. `doc-drift`
finds divergence between user-facing or agent-facing docs and the
implementation; `api-surface-drift` finds public-API-surface changes missing
from docs or a changelog. Demoable: each detector files one evidenced chore
issue against a seeded drift.
**Depends on:** Unit 1; spec 01 Unit 3 (Serena MCP fragment)
**Affected areas:** `.github/workflows/doc-drift.md` (new),
`.github/workflows/doc-drift.lock.yml` (generated),
`.github/workflows/api-surface-drift.md` (new),
`.github/workflows/api-surface-drift.lock.yml` (generated),
`wrappers/doc-drift.yml` (new), `wrappers/api-surface-drift.yml` (new)

**Functional Requirements:**

- **R2.1**: `.github/workflows/doc-drift.md` shall be a gh-aw source compiled
  to an adjacent `.lock.yml` per ADR 0002. It shall trigger on a `schedule`
  cron and on `workflow_dispatch`, and shall import `chore-interaction.md`,
  `repo-conventions.md`, `runtime-setup.md`, and `rigor.md` via the pinned-ref
  import form.
- **R2.2**: `doc-drift` shall scan the target repository for divergence
  between user-facing or agent-facing documentation (such as `README.md`,
  docs pages, and `CLAUDE.md`) and the implementation those docs describe,
  using Serena symbol-level retrieval (`sdd-mcp-serena.md`) where available
  and degrading to text-level reading where no language server exists.
- **R2.3**: For each confirmed drift `doc-drift` shall file exactly one chore
  issue via the `create-issue` safe-output, carrying `kind:chore` and
  `agent:doc-drift`, with a body that cites the doc location and the code
  location it diverged from per `shared/rigor.md`. One finding per issue; it
  shall not bundle unrelated drifts.
- **R2.4**: Before filing, `doc-drift` shall check open `agent:doc-drift`
  issues and skip a drift already filed, updating the existing issue instead
  of opening a duplicate, per the false-positive clause of `shared/rigor.md`.
- **R2.5**: `.github/workflows/api-surface-drift.md` shall be a gh-aw source
  compiled to an adjacent `.lock.yml`, triggering on `pull_request`
  (`opened`, `synchronize`) and on a `schedule` cron, importing the same four
  fragments as R2.1.
- **R2.6**: `api-surface-drift` shall detect changes to the repository's
  public API surface (exported symbols, public signatures, public
  entry points, as resolved for the target repo's stack) that are not
  reflected in the repository's documentation or a changelog. It shall not
  assume a language; it resolves the public surface from the target repo's
  conventions per `repo-conventions.md`.
- **R2.7**: On a `pull_request` run `api-surface-drift` shall post its finding
  as a single advisory comment on that pull request; on a `schedule` run it
  shall file a chore issue with `kind:chore` and `agent:api-drift`. Either way
  the finding cites the changed surface and the missing doc or changelog
  entry.
- **R2.8**: Either detector shall apply `needs-human` and post one comment,
  rather than filing, when a candidate finding cannot meet the
  `shared/rigor.md` standard but is judged genuinely risky.

**Proof Artifacts:**

- File: `.github/workflows/doc-drift.md` contains the `schedule` trigger and
  the four pinned-ref `imports:` lines; `api-surface-drift.md` contains the
  `pull_request` and `schedule` triggers.
- CLI: `gh aw compile` succeeds on `doc-drift.md` and `api-surface-drift.md`,
  producing the adjacent `.lock.yml` files.
- Test: on a fixture repo seeded with a doc that contradicts the code,
  `doc-drift` files exactly one issue carrying `kind:chore` and
  `agent:doc-drift` whose body cites both the doc and the code location.

### Unit 3: `test-coverage` detector

**Purpose:** Stand up the coverage detector: it finds code lacking test
coverage and files coverage-gap chore issues. Demoable: the detector files an
evidenced coverage-gap issue against an untested module.
**Depends on:** Unit 1; spec 01 Unit 3 (Serena MCP fragment)
**Affected areas:** `.github/workflows/test-coverage.md` (new),
`.github/workflows/test-coverage.lock.yml` (generated),
`wrappers/test-coverage.yml` (new)

**Functional Requirements:**

- **R3.1**: `.github/workflows/test-coverage.md` shall be a gh-aw source
  compiled to an adjacent `.lock.yml`, triggering on a `schedule` cron and on
  `workflow_dispatch`, and importing `chore-interaction.md`,
  `repo-conventions.md`, `runtime-setup.md`, and `rigor.md` via pinned-ref
  imports.
- **R3.2**: `test-coverage` shall identify code in the target repository that
  lacks test coverage. It shall read the target repo's `CLAUDE.md` (fallback
  `README.md`) for the test command and coverage tooling and shall not
  hardcode a toolchain. When the repository exposes a coverage report the
  detector reads it; when it does not, the detector reasons about test
  presence at the symbol level via Serena and degrades to text-level reading
  where no language server exists.
- **R3.3**: For each confirmed coverage gap `test-coverage` shall file exactly
  one chore issue via `create-issue`, carrying `kind:chore` and
  `agent:coverage`, with a body that cites the uncovered `file:line` range and
  states what behavior is untested, per `shared/rigor.md`.
- **R3.4**: `test-coverage` shall bound each finding: a coverage-gap issue
  names a specific uncovered unit, not a broad "coverage is low" claim. It
  shall not file a finding it cannot reproduce against the current default
  branch.
- **R3.5**: Before filing, `test-coverage` shall check open `agent:coverage`
  issues and skip a gap already filed, updating the existing issue rather than
  opening a duplicate.
- **R3.6**: When the target repository has no discoverable test command or
  coverage tooling at all, `test-coverage` shall emit `noop` and exit 0 rather
  than file speculative findings; it shall record the reason in the run log.

**Proof Artifacts:**

- File: `.github/workflows/test-coverage.md` contains the `schedule` trigger,
  the four pinned-ref `imports:` lines, and no hardcoded test command.
- Test: on a fixture repo with an untested module, `test-coverage` files
  exactly one issue carrying `kind:chore` and `agent:coverage` whose body
  cites the uncovered `file:line` range.
- Test: on a fixture repo with no discoverable test tooling, `test-coverage`
  emits `noop`, files no issue, and exits 0.

### Unit 4: `dependency-review` and `trivial-dep-bump` bots

**Purpose:** Stand up the two dependency bots. `dependency-review` posts a
risk read on dependency changes in a pull request; `trivial-dep-bump` opens
pull requests for safe, trivial dependency updates. Demoable: a risk comment
appears on a dependency PR, and a trivial bump arrives as a PR.
**Depends on:** Unit 1
**Affected areas:** `.github/workflows/dependency-review.md` (new),
`.github/workflows/dependency-review.lock.yml` (generated),
`.github/workflows/trivial-dep-bump.md` (new),
`.github/workflows/trivial-dep-bump.lock.yml` (generated),
`wrappers/dependency-review.yml` (new), `wrappers/trivial-dep-bump.yml` (new)

**Functional Requirements:**

- **R4.1**: `.github/workflows/dependency-review.md` shall be a gh-aw source
  compiled to an adjacent `.lock.yml`, triggering on `pull_request` (`opened`,
  `synchronize`) and importing `chore-interaction.md`, `repo-conventions.md`,
  `runtime-setup.md`, and `rigor.md` via pinned-ref imports.
- **R4.2**: `dependency-review` shall run only on pull requests that change
  the target repository's dependency manifest or lockfile, as resolved from
  the target repo's stack; on a pull request that changes no dependency it
  shall emit `noop` and exit 0.
- **R4.3**: For a pull request that does change dependencies,
  `dependency-review` shall post a single advisory comment summarizing the
  risk of each changed dependency: the version delta, whether the change
  crosses a major version, and any security-relevant signal it can cite. The
  comment cites each dependency by name and version. It updates that one
  comment on re-runs rather than posting a new one each run.
- **R4.4**: `dependency-review` shall not block the pull request and shall not
  be a required status check; it is advisory by design, consistent with the
  SDD suite's advisory-validation stance.
- **R4.5**: `.github/workflows/trivial-dep-bump.md` shall be a gh-aw source
  compiled to an adjacent `.lock.yml`, triggering on a `schedule` cron and on
  `workflow_dispatch`, and importing the same four fragments as R4.1.
- **R4.6**: `trivial-dep-bump` shall identify safe, trivial dependency updates
  in the target repository (a bump that does not cross a major version and has
  no other signal of risk) and shall open one `create-pull-request` per
  trivial bump that updates the manifest and lockfile and runs the target
  repo's verification commands. A non-trivial update is out of scope for this
  bot: it is left for a human or escalated by `dependency-review`.
- **R4.7**: `trivial-dep-bump` shall apply `needs-human` rather than open a
  pull request when an update it judged trivial turns out to fail the target
  repo's verification commands, with a comment stating the failure.
- **R4.8**: A `trivial-dep-bump` pull request shall close no chore issue: it
  is opened from a detected update, not from a filed `agent:dep-bump` issue.
  The `agent:dep-bump` label exists for the case where a human or a future
  detector files a dependency-bump chore for the `chore-fix` worker; it is not
  applied by `trivial-dep-bump` itself.

**Proof Artifacts:**

- File: `.github/workflows/dependency-review.md` contains the `pull_request`
  trigger and shows no `required` status-check declaration;
  `trivial-dep-bump.md` contains the `schedule` trigger.
- Test: a pull request that changes a dependency manifest receives a single
  advisory comment from `dependency-review` naming each changed dependency and
  its version delta; a pull request that changes no dependency yields a
  `noop`.
- Test: on a fixture repo whose manifest pins a dependency one safe
  patch-level release behind its latest, `trivial-dep-bump` opens one pull
  request that updates the manifest and lockfile to that release.

### Unit 5: `chore-fix` worker

**Purpose:** Stand up the standalone fast-track worker: it selects an open
chore-labelled issue, drafts a fix, and opens a pull request directly,
bypassing `sdd-spec` and `sdd-triage`. Demoable: an `agent:*`-labelled issue
produces a fix pull request that closes it.
**Depends on:** Units 1, 2, 3; spec 01 Unit 3 (Serena MCP fragment)
**Affected areas:** `.github/workflows/chore-fix.md` (new),
`.github/workflows/chore-fix.lock.yml` (generated),
`wrappers/chore-fix.yml` (new)

**Functional Requirements:**

- **R5.1**: `.github/workflows/chore-fix.md` shall be a gh-aw source compiled
  to an adjacent `.lock.yml`, triggering on a `schedule` cron, on
  `workflow_dispatch`, on `issue_comment` filtered to a `/chore-fix` command
  from write-access authors, and on `issues` (`unlabeled`, matching
  `needs-human`). It shall import `chore-interaction.md`, `repo-conventions.md`,
  `runtime-setup.md`, `rigor.md`, and `sdd-mcp-serena.md` via pinned-ref
  imports.
- **R5.2**: On a scheduled run `chore-fix` shall select one open issue
  carrying `kind:chore` and any `agent:*` label, with no `needs-human` label
  and no open linked pull request, choosing highest `priority:*` then oldest
  `updated_at`. When no eligible issue exists it shall emit `noop` and exit 0.
- **R5.3**: `chore-fix` shall implement the selected chore using Serena
  symbol-level retrieval and editing, run the target repo's verification
  commands read from `CLAUDE.md` (fallback `README.md`), and open exactly one
  `create-pull-request` titled `chore(<scope>): <issue title>` with
  `Closes #<issue>` in the body and the captured verification output included.
- **R5.4**: `chore-fix` shall bypass `sdd-spec` and `sdd-triage` entirely: it
  shall author no spec file, no architecture record, and no task sub-issues,
  and it shall apply no `sdd:*` lifecycle label. The fix pull request is the
  only artifact it produces.
- **R5.5**: `chore-fix` shall never edit protected paths (`.github/`,
  `decisions/`, `templates/.github/`, secrets). A chore requiring such an edit
  triggers `needs-human` instead of a pull request.
- **R5.6**: When the selected chore needs a design decision, cannot be
  implemented at or above 80% confidence, or has a proof artifact that will
  not pass, `chore-fix` shall apply `needs-human` and post one comment stating
  what blocked it, with evidence, and whether the chore should be reopened as
  a feature or bug issue for the SDD pipeline. It shall not promote the chore
  into the SDD pipeline itself.
- **R5.7**: `chore-fix` shall skip any chore issue carrying `needs-human` in
  candidate selection, per ADR 0001 clause 2, so its hand-off comment posts
  once. On `needs-human` removal it re-reads the issue thread, including the
  human's new comment, and resumes.

**Proof Artifacts:**

- File: `.github/workflows/chore-fix.md` contains the four trigger types from
  R5.1, the five pinned-ref `imports:` lines, a protected-paths list, and no
  `sdd:*` label write.
- Test: an open issue carrying `kind:chore` and `agent:coverage` produces,
  within one run, a pull request titled `chore(...)` with `Closes #<issue>`
  and a verification-output block in the body, and no spec file or task
  sub-issue is created.
- Test: an open issue carrying `kind:chore` whose body asks for a design
  decision yields no pull request, a `needs-human` label, and one comment
  proposing the chore be reopened as a feature issue.

### Unit 6: PR-maintenance bots (`pr-conflict-resolver`, `dedupe-prs`)

**Purpose:** Keep the bot pull-request flow tidy. `pr-conflict-resolver`
resolves mechanically-trivial merge conflicts on bot pull requests and hands
off non-trivial ones; `dedupe-prs` detects and closes duplicate pull requests.
Demoable: a trivially conflicting bot PR is rebased clean, and a duplicate bot
PR is closed.
**Depends on:** Units 2, 3, 4, 5
**Affected areas:** `.github/workflows/pr-conflict-resolver.md` (new),
`.github/workflows/pr-conflict-resolver.lock.yml` (generated),
`.github/workflows/dedupe-prs.md` (new),
`.github/workflows/dedupe-prs.lock.yml` (generated),
`wrappers/pr-conflict-resolver.yml` (new), `wrappers/dedupe-prs.yml` (new)

**Functional Requirements:**

- **R6.1**: `.github/workflows/pr-conflict-resolver.md` shall be a gh-aw
  source compiled to an adjacent `.lock.yml`, triggering on a `schedule` cron
  and on `workflow_dispatch`, and importing `chore-interaction.md`,
  `repo-conventions.md`, and `runtime-setup.md` via pinned-ref imports.
- **R6.2**: `pr-conflict-resolver` shall act only on bot-authored pull
  requests that are in a conflicting state, identified by their authoring
  GitHub App identity, not by a hardcoded bot name. It shall not touch a
  human-authored pull request.
- **R6.3**: For a bot pull request whose conflict is mechanically trivial (for
  example a lockfile regeneration or a non-overlapping import-list change),
  `pr-conflict-resolver` shall resolve the conflict by rebasing or
  regenerating, push the result to the same branch, and post one comment
  recording what it resolved. It shall not force-push a branch with an open
  pull request in a way that loses review history beyond the rebase.
- **R6.4**: When a conflict is not mechanically trivial, `pr-conflict-resolver`
  shall apply `needs-human` to the pull request and post one comment naming
  the conflicting files and why the resolution is not mechanical. It shall not
  guess at a semantic merge.
- **R6.5**: `.github/workflows/dedupe-prs.md` shall be a gh-aw source compiled
  to an adjacent `.lock.yml`, triggering on a `schedule` cron, on
  `workflow_dispatch`, and on `pull_request` (`opened`), and importing the
  same three fragments as R6.1.
- **R6.6**: `dedupe-prs` shall detect when two or more open pull requests make
  the same change (for example two bots opening the same trivial dependency
  bump, or a fix re-filed). When a duplicate is unambiguous it shall close the
  newer pull request with a comment linking the one it kept, keeping the
  oldest or the further-along pull request.
- **R6.7**: When duplicate detection is ambiguous (the pull requests overlap
  but are not clearly the same change), `dedupe-prs` shall apply `needs-human`
  to the newer pull request and post one comment naming the candidates and the
  overlap, rather than close a pull request on a guess.
- **R6.8**: Both bots shall skip any pull request carrying `needs-human` in
  candidate selection, per ADR 0001 clause 2, and shall never clear the label.

**Proof Artifacts:**

- File: `.github/workflows/pr-conflict-resolver.md` and `dedupe-prs.md` each
  contain their trigger sets and the three pinned-ref `imports:` lines; no
  bot name appears as a literal in either source.
- Test: a bot pull request with a trivial lockfile conflict is rebased clean
  by `pr-conflict-resolver`, which pushes the result and posts one resolution
  comment.
- Test: two open bot pull requests making the identical change result in
  `dedupe-prs` closing the newer one with a comment linking the kept pull
  request.

### Unit 7: Consumer packaging and chore-suite install

**Purpose:** Make the chore suite installable on another repository with one
command, alongside or independent of the SDD suite. Demoable: the installer
adds the chore suite to a fixture repo and a seeded drift runs end to end on
it.
**Depends on:** Units 1 to 6
**Affected areas:** `scripts/quick-setup.sh`, `wrappers/README.md`,
`docs/sdd/install.md`

**Functional Requirements:**

- **R7.1**: Each chore-suite workflow shall be authored as a reusable workflow
  (`on: workflow_call`) with a thin `wrappers/<bot>.yml` caller, per the
  thin-wrapper distribution model from spec 01 Unit 1 and the layout fixed by
  ADR 0002.
- **R7.2**: `scripts/quick-setup.sh` shall gain a `--suite chore` option that
  installs the eight chore-suite wrappers, the `agent:*` labels, and the
  `chore` issue template on the target repo. The option shall be independent
  of `--suite sdd`: a repo may install either suite, both, or neither.
- **R7.3**: Install shall configure, not hardcode: the GitHub App identity and
  any MCP endpoint and credential are resolved at install time from
  operator-supplied values. No chore-suite source or `shared/chore-*` fragment
  shall carry an org-specific or private literal; the `leak-scan` CI check
  shall pass on the full tree at this unit's commit.
- **R7.4**: `docs/sdd/install.md` shall document the `--suite chore` install,
  the required configuration, how the chore fast-track relates to the SDD
  pipeline, and a post-install smoke test, in a chore-suite section ending
  with a `## Verification` block of copy-pasteable `gh` commands. `install.md`
  is planned by spec 01 Unit 9; if spec 01 Unit 9 has not yet delivered the
  file when this unit lands, Unit 7 creates `docs/sdd/install.md` with the
  chore-suite section, and a later spec 01 Unit 9 edit appends the SDD
  section. Either way the edit is additive.
- **R7.5**: `wrappers/README.md` shall list every chore-suite wrapper and
  state which trigger fires each bot, so an operator sees the full chore suite
  in one place. `wrappers/README.md` is planned by spec 01 Unit 9; if it does
  not yet exist when this unit lands, Unit 7 creates it; otherwise Unit 7
  appends the chore-suite wrappers to it.

**Proof Artifacts:**

- File: `wrappers/` contains a wrapper for each of the eight chore-suite bots;
  `wrappers/README.md` lists all eight.
- CLI: `bash scripts/quick-setup.sh --target-repo <owner>/test-fixture
  --suite chore --dry-run` lists the eight chore-suite wrappers, the `agent:*`
  labels, and the `chore` template in its planned-writes output.
- Test: on a fixture repo seeded with a doc that diverged from the code,
  installing with `--suite chore` and running `doc-drift` then `chore-fix`
  produces a chore issue and then a fix pull request that closes it, with no
  edits to the installed wrappers.

## Non-Goals (Out of Scope)

- **Modifying the SDD pipeline.** The chore suite reuses spec 01's foundation
  and fragments but changes no `sdd-*` workflow source or fragment. The two
  suites run in parallel; the chore suite never alters the SDD pipeline. It
  does make additive-only edits to shared foundation assets (`labels.yml`
  gains the `agent:*` labels, suite-level docs gain a chore-fast-track
  section); these append to shared assets and modify no `sdd-*` workflow.
- **Escalating a chore into the SDD pipeline automatically.** A `chore-fix`
  hand-off proposes, via a `needs-human` comment, that a human reopen the
  chore as a feature or bug issue. No bot files an `sdd:spec` issue or
  triggers `sdd-spec` itself.
- **Auto-merge.** No chore bot merges a pull request. Humans merge; consumer
  CI gates. This matches the SDD suite's stance.
- **Non-trivial dependency updates.** `trivial-dep-bump` opens pull requests
  only for safe, trivial bumps. A major-version bump or any update with a risk
  signal is left for a human; `dependency-review` summarizes its risk but does
  not open a pull request for it.
- **Semantic merge-conflict resolution.** `pr-conflict-resolver` resolves only
  mechanically-trivial conflicts. A conflict that needs a judgment call is
  handed off via `needs-human`, never guessed.
- **Hosting MCP infrastructure.** The chore suite consumes Serena and
  Distillery as the configured MCP servers from spec 01 Unit 3; standing them
  up is operator infra.
- **Depending on or modifying any prior private system.** The chore bots are
  described generically and attributed to no private source system.

## Design Considerations

No UI work. The chore suite's surface is GitHub issues, comments, labels, and
pull requests with GitHub defaults. The `agent:*` label set is the chore-suite
task board; the `label:needs-human` filter is the shared escalation queue, the
same one the SDD suite uses. The chore fast-track is deliberately flat: no
intermediate lifecycle labels, no spec, no architecture record, no task graph.
That flatness is the point of a fast-track and the visible contrast with the
SDD `sdd:*` state machine.

## Repository Standards

- The repository is public. No employer or company name, private org slug,
  private or internal repository name, internal URL, cost or budget figure, or
  contributor personal data appears in any committed file, issue, pull
  request, or comment. The `leak-scan` CI check enforces this on the tree
  against a secret denylist; for issues, pull requests, and comments it is an
  authoring discipline. The chore bots are described generically and are
  attributed to no private source system.
- No em dashes in any prose, code comment, or workflow string.
- Markdown uses ATX headings and fenced code blocks with language tags.
- Workflow files are authored in `gh aw compile` source format at
  `.github/workflows/*.md`; the adjacent `.lock.yml` is generated by the
  toolchain and never hand-edited. Shared fragments live at the repo-root
  `shared/` and are imported via the pinned-ref `owner/repo/path@ref` form.
  Both points are fixed by ADR 0002.
- No org slug, bot name, hostname, or absolute path is a literal in any
  chore-suite workflow or `shared/chore-*` fragment. The GitHub App and MCP
  endpoints are configuration supplied at install.
- Bots read stack and convention from the target repo's `CLAUDE.md` (fallback
  `README.md`); no toolchain is hardcoded into a source.
- Branch names: `chore/<issue-id>-<slug>` for `chore-fix` pull requests;
  `chore/dep-bump-<slug>` for `trivial-dep-bump` pull requests.
- Every new runbook or doc ends with a `## Verification` section.

## Verification

**Project maturity:** The chore suite is built on the foundation spec 01
Unit 1 already established. It introduces no new CI gate; it runs against the
existing lint, docs strict build, actionlint, shellcheck, leak-scan, and
gh-aw compilation checks.

**Available commands:**

| Check | Command |
|-------|---------|
| Lint  | `npx markdownlint-cli2 docs/**/*.md` + `shellcheck` + `actionlint` |
| Build | `mkdocs build --strict` |
| Test  | `gh aw compile .github/workflows/*.md` (frontmatter and schema validation) |
| Leak  | `leak-scan` CI job against the secret denylist |

The `markdownlint-cli2` glob covers `docs/` only; it is inherited from spec
01 and not changed here. Chore-suite sources at `.github/workflows/*.md` and
fragments under `shared/` are covered by the `gh aw compile` check and the
`leak-scan` job, which run on those paths regardless of the lint glob.

**Bootstrapping:** The chore suite is built conventionally, consistent with
ADR 0003: each of the seven units (eight bots across seven units) is delivered
as an ordinary pull request, not built through the SDD pipeline. There is no
bootstrapping unit; Unit 1 consumes the foundation that spec 01 Unit 1 already
provides.

## Technical Considerations

- The chore suite is a fast-track, not a pipeline. A detector files a chore
  issue and the `chore-fix` worker turns it into a fix pull request directly.
  There is no spec, no architecture record, and no task graph, because chore
  work has no design content. The flat lifecycle is the deliberate contrast
  with the SDD `sdd:*` state machine.
- The `agent:*` label is both a source marker and the `chore-fix` selector.
  A detector stamps its label on every issue it files; `chore-fix` selects on
  the `agent:*` family. The taxonomy is open: a future detector adds its own
  `agent:*` label rather than overloading an existing one.
- The evidence-rigor standard is the gate on filing. A detector reproduces a
  finding against the current default branch, rules out an existing issue or a
  known suppression, cites a `file:line` or command output, bounds the scope,
  and files one finding per issue, at or above 80% confidence. A candidate
  that fails the standard is not filed; if it is judged genuinely risky it is
  handed off via `needs-human` rather than filed as a low-confidence issue.
- Two of the bots post advisory comments on existing pull requests rather than
  file issues: `dependency-review` and the `pull_request` mode of
  `api-surface-drift`. They never block a pull request and are never required
  status checks, consistent with the SDD suite's advisory-validation stance.
- The bots reuse spec 01 Unit 3's MCP fragments where they help. `doc-drift`,
  `test-coverage`, and `chore-fix` use Serena for symbol-level retrieval and
  editing and degrade to text-level reading where no language server exists.
  A detector that needs prior-finding recall uses Distillery scoped to the
  running repo's own project so a shared store cannot leak unrelated content.
- gh-aw layout and imports follow ADR 0002 exactly: sources at
  `.github/workflows/*.md` compiled to an adjacent `.lock.yml`, both
  committed; shared fragments at the repo-root `shared/`; imports in the
  pinned-ref `owner/repo/path@ref` form, `@main` before the first release and
  a release tag after.
- `chore-fix` is the standalone fast-track. It bypasses `sdd-spec` and
  `sdd-triage`, writes no `sdd:*` label, and creates no task sub-issue. When
  a chore turns out to need a design it is handed to a human via `needs-human`
  with a comment; the human, not a bot, decides whether to reopen it as a
  feature or bug issue for the SDD pipeline.
- The PR-maintenance bots act only on bot-authored pull requests, identified
  by the authoring GitHub App identity, not by a hardcoded bot name.
  `pr-conflict-resolver` resolves only mechanically-trivial conflicts;
  `dedupe-prs` closes only unambiguous duplicates. Anything that needs a
  judgment call is handed off.
- gh-aw safe-outputs used: `create-issue`, `create-pull-request`,
  `add-comment`, `add-labels`, `noop`. All writes go through safe-outputs with
  threat detection; `permissions:` stays read-only.

## Security Considerations

- The repository is public. The `leak-scan` CI check from spec 01 Unit 1 fails
  any pull request that introduces a denylisted private term; the denylist
  lives in a secret, never in the tree. No chore-suite source or
  `shared/chore-*` fragment carries a private literal, and the bots are
  attributed to no private source system.
- The chore bots write via the configurable GitHub App identity from spec 01,
  minted per run and scoped to the running repository, not a broad PAT and not
  a hardcoded bot. The PR-maintenance bots identify bot-authored pull requests
  by that App identity, so they never act on a human-authored pull request by
  mistake.
- `chore-fix` and `trivial-dep-bump` never edit `.github/`, `decisions/`,
  `templates/.github/`, or secrets; a chore that requires such an edit
  escalates via `needs-human`.
- MCP outputs are untrusted input. Serena code reads and Distillery search
  results are tool data, not instructions; agent prompts wrap them as
  untrusted and threat detection on safe-outputs still applies. Distillery
  queries are scoped to the running repo's own project so a shared knowledge
  store cannot leak unrelated content into a public chore issue or comment.
- Comment commands are gated to write-access authors via the gh-aw `command:`
  trigger; a non-write user commenting `/chore-fix` is a no-op.
- No chore bot has merge or approve authority: bots draft, humans and consumer
  CI gate.
- `needs-human` is never cleared by a bot (ADR 0001 clause 3), so a bot cannot
  release its own hand-off. A detector that files a low-confidence finding as
  a `needs-human` hand-off rather than as an issue keeps the chore-issue
  stream at or above the 80% evidence-rigor threshold.

## Success Metrics

- All seven demoable units land with proof artifacts passing.
- Each chore-suite source compiles clean under `gh aw compile`, producing the
  committed adjacent `.lock.yml`.
- The `leak-scan` CI check passes on every commit; no private term and no
  private source-system attribution ever reaches the public tree.
- The fast-track works end to end: a seeded drift produces a `doc-drift` chore
  issue, and `chore-fix` turns that issue into a fix pull request that closes
  it, with no spec file, no architecture record, and no task sub-issue created
  at any point.
- Every detector files only rigor-compliant issues: a deliberately
  low-confidence candidate produces a `needs-human` hand-off, not an issue.
- The bot pull-request flow stays tidy: a trivially conflicting bot pull
  request is rebased clean, a non-trivial conflict is handed off, and a
  duplicate bot pull request is closed.
- Install proof: `--suite chore` installs the eight bots on a fixture repo
  independent of `--suite sdd`, and the seeded-drift run completes with no
  edits to the installed wrappers.
- The `label:needs-human` queue is the only place a blocked chore item
  appears, and it is the same queue the SDD suite uses: no bot exits silently,
  no bot posts a hand-off comment twice.

## Open Questions

No open questions at this time.
