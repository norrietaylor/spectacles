# 01-spec-issue-native-sdd

> The repository is public. This file, and everything committed to the repo,
> carries no employer name, no private org slug, no internal repository name,
> no internal URL, no cost figure, and no contributor personal data. Patterns
> reused from prior private work are described generically and never
> attributed by name.

**Correction (2026-05-16):** ADR 0002 supersedes this spec's `workflows/`
source location and its local-import assumption. gh-aw workflow sources live
at `.github/workflows/`; shared fragments stay at `shared/` and are consumed
via pinned-ref imports (`owner/repo/path@ref`). See
`decisions/0002-workflow-layout-and-imports.md`.

## Context

This spec stands up a public, standalone repository hosting a spec-driven
development (SDD) agent suite built as agentic GitHub Actions workflows
(gh-aw). The suite moves a feature from a plain GitHub issue to a merged
implementation through a disciplined spec then triage then execute then
validate then review pipeline.

The design lifts patterns proven in a prior private agentic-workflow system: a
gh-aw reusable-workflow plus thin-wrapper distribution model, an ADR
convention, a shared-fragment pattern, an evidence-rigor standard, and an
installer script. That prior system is private; it is not named, referenced,
or linked anywhere in this public repository. This repo is independent: it
inherits no legacy code, no prior workflows, and no coexistence constraints.
Because it is public from day one, thin-wrapper `workflow_call` distribution
works as designed, without the private-to-private constraint that affects
private hosts.

The design also draws on a comparison of two open-source SDD frameworks
(`sighup/claude-workflow`, `atelier-fashion/adlc-toolkit`). Four features from
that comparison are adopted as the agreed feature set:

1. **A retrieval and citation memory layer** so each spec is informed by prior
   specs, ADRs, and issues, with load-bearing matches cited.
2. **A real architecture phase with persisted ADRs**: the first phase of
   `sdd-triage` always designs the approach and persists an architecture
   record, and a genuine cross-cutting decision is promoted to a numbered ADR.
3. **Validation at every phase boundary**: spec, architecture, triage, and
   implementation are each checked.
4. **Cross-repo task routing**: the task schema and dependency graph support
   tasks that target sibling repos; this spec builds that seam.

Also adopted: typed proof artifacts with the "empty PR" test, demoable units,
native task metadata, two-phase decomposition, model-tier-by-complexity, and
shipping with an open-source license (both surveyed frameworks shipped
unlicensed; this repo does not repeat that). What is rejected: hardcoded stack
assumptions, hardcoded org or bot identities, and uncompiled skill edits.

Two scoping points carry through:

- **The suite must work on existing codebases.** The suite's own repo is
  greenfield, but it will be installed on consumer repos that already carry
  substantial code and history. Code-intelligence tooling is a first-class
  dependency for that reason.
- **Automatic routing is a future extension.** Deciding a task's target repo
  from signals is planned for later and is built on the cross-repo seam this
  spec lays down in `sdd-triage`.

The constraint that shapes everything: agentic workflows run unattended in CI.
They have no interactive prompt. Every point where a desktop SDD framework
would call `AskUserQuestion` becomes an asynchronous exchange through GitHub
issue and PR comments, with the `needs-human` label as the escalation lever.

Two MCP servers were investigated and are adopted as complementary
infrastructure, not alternatives:

- **Distillery**, a semantic knowledge-store MCP server with a `gh-sync`
  capability for ingesting issues and PRs. It is the retrieval and memory
  layer of feature 1.
- **Serena** (`oraios/serena`), an LSP-backed symbol-level code retrieval and
  editing MCP server. It is the code-intelligence layer: it lets an agent
  understand and edit an existing codebase by symbols and relations without
  reading whole files, which is what makes installing onto a non-greenfield
  consumer viable.

## Introduction/Overview

This spec stands up the **issue-native SDD suite**: five agentic workflows
(`sdd-spec`, `sdd-triage`, `sdd-execute`, `sdd-validate`, `sdd-review`), a
repository foundation, a human-interaction contract, and shared MCP tooling
(Distillery for retrieval, Serena for code intelligence). `sdd-triage` runs
three phases under one workflow: architecture design, parent-task creation,
and sub-task decomposition. State lives in GitHub primitives only: the spec
and the architecture record are committed files authored via PR, tasks are
linked sub-issues, lifecycle is expressed as labels, and every human decision
point is an issue or PR comment. There is no external task board and no
separate UI. The suite dogfoods in its own repo and installs on consumer
repos, including ones with an existing codebase, through a thin-wrapper
distribution model.

## Goals

1. A feature issue reaches a structured spec, a persisted architecture record,
   a task graph, an implementation PR, and validation passes, without a human
   authoring any of those artifacts by hand: humans steer, agents draft.
2. Every human interaction is a GitHub-native action already in the team's
   habit: creating an issue, applying a label, writing a comment, reviewing
   and merging a PR. No new tool, no slash-command app required.
3. `needs-human` is the single, uniform agent-to-human hand-off marker for the
   whole suite, with a defined trigger table so an agent never silently gives
   up and never spams.
4. Validation runs at all four phase boundaries (spec, architecture, triage,
   implementation) but never blocks a merge: validation is advisory by design;
   human review plus consumer CI is the only merge gate.
5. The suite operates on existing codebases, not only greenfield ones: agents
   use Serena code intelligence to understand a repo that already has
   substantial code and history.
6. The task schema supports cross-repo routing: every task carries a `repo:`
   field and the task graph may span repos. Single-repo is the exercised
   default; cross-repo execution is the documented next extension.
7. The suite is portable and carries no org-specific or private literal: the
   GitHub App identity, MCP endpoints, and org slug are configuration. One
   `quick-setup.sh` run installs it on another repo with no source edits.

## User Stories

- As a team member with an idea, I want to open a feature issue and have a
  drafted spec PR appear, so I review a concrete proposal instead of writing
  one from scratch.
- As a reviewer, I want the spec, the architecture record, the triage plan,
  and each implementation to arrive as PRs and linked sub-issues I can read
  and comment on, so review happens on my normal GitHub surface.
- As whoever is on triage this week, I want one `label:needs-human` filter
  that lists every issue or PR an agent handed back, so I know exactly what is
  blocked and why.
- As a team member, I want to answer an agent's clarifying question in a
  comment and clear `needs-human`, and have the agent resume, so the exchange
  feels like a conversation, not a restart.
- As a maintainer installing this on an existing service repo, I want the
  agents to map the real code (not guess), so the spec, the architecture, and
  the tasks reflect what is actually there.
- As an operator, I want validation findings posted as advisory PR comments
  rather than as a failed required check, so a draft is never wedged by the
  agent's own opinion.

## Human Interaction Model

The pipeline is operated entirely through four GitHub primitives. This section
is the contract; Units 1 and 2 implement it.

### Surfaces

1. **Issues.** A human opens an issue from the `feature` or `bug` template.
   That issue is the **tracking issue** for the whole feature. Task issues
   created later by `sdd-triage` are linked as its sub-issues.
2. **Comments.** Agents post structured output (spec links, architecture and
   triage summaries, clarifying questions, validation findings) as issue or PR
   comments. Humans answer agents, request changes, and approve, in comments.
3. **Labels.** Lifecycle state is a label on the tracking issue. The label set
   is the GitHub-native task board.
4. **PRs.** The spec, the per-feature architecture record, each numbered ADR,
   and each implementation arrive as PRs. Merging a PR is the approval signal
   that advances the pipeline.

### Lifecycle labels (on the tracking issue)

`sdd:spec` -> `sdd:triage` -> `sdd:ready` -> `sdd:in-progress` ->
`sdd:review` -> `sdd:done`. Exactly one is present at a time; the agent that
completes a phase moves the label. `sdd:triage` covers all three `sdd-triage`
phases. `kind:*`, `priority:*`, and the `model:{haiku,sonnet,opus}` labels are
orthogonal metadata.

### Comment commands

A small command vocabulary, gated to comment authors with write access (the
`command:` trigger in gh-aw):

| Command | Where | Effect |
|---|---|---|
| `/spec` | tracking issue | trigger `sdd-spec` (also auto-applied by the `feature`/`bug` template label) |
| `/triage` | tracking issue, after spec PR merged | trigger `sdd-triage` phase A (architecture) |
| `/approve` | tracking issue | confirm the parent-task list; `sdd-triage` proceeds to sub-tasks |
| `/revise <note>` | spec PR, architecture PR, triage comment, or impl PR | re-run the owning agent with the note as added instruction |
| `/execute` | a task sub-issue | trigger `sdd-execute` for that task ahead of the cron |

Merging the spec PR advances to the architecture phase; merging the
architecture PR advances to the parent-task phase. `/approve` is the one
non-PR decision point: it confirms the parent-task list before sub-task
decomposition.

### The `needs-human` contract

`needs-human` is the uniform agent-to-human hand-off marker, defined by
ADR 0001 (Unit 1). Contract:

1. An agent applies `needs-human` (via `add-labels`) at the terminal step
   where it decides it cannot safely proceed, and posts **exactly one**
   comment stating the blocker and what it needs.
2. Every agent **skips** `needs-human`-labelled items in candidate selection.
   This is the idempotency guarantee: the hand-off comment posts once.
3. No agent ever removes `needs-human`. A human clears it to take the item
   back or, having answered, to hand it on.
4. Clearing `needs-human` fires `issues.unlabeled` / `pull_request.unlabeled`
   and re-triggers the agent that applied it, which re-reads the thread
   (including the human's new comment) and resumes.

#### When each agent applies `needs-human`

| Agent | Applies `needs-human` when | Comment must include |
|---|---|---|
| `sdd-spec` | clarifying questions are still open after one comment round; the source issue is too vague to spec at >=80% confidence; scope is too large or too small and no split is obvious | the open questions, or the scope assessment with proposed splits |
| `sdd-triage` | the architecture has a genuine fork (more than one defensible approach with material tradeoffs); a spec requirement maps to no task; a dependency cycle is not mechanically resolvable | the decision framed as options, or the gap |
| `sdd-execute` | a proof artifact cannot be made to pass; the task needs edits to protected paths (`.github/`, `decisions/`, secrets); the task is underspecified to implement at >=80% confidence | what blocked it and what it attempted, with evidence |
| `sdd-validate` | a blocking gate fails and the remediation is not mechanical | the failed gate and the citing evidence |
| `sdd-review` | a CRITICAL or HIGH finding needs a human call; spec-compliance is genuinely ambiguous | the finding with `file:line` |
| any agent | a merge conflict it will not resolve; retries exhausted; self-rated confidence below the 80% `shared/rigor.md` threshold | the reason |

Beyond the blocker cases above, `sdd-execute` also applies `needs-human` to a
tracking issue when every task sub-issue is closed: this hands the final
review and close to a human (R6.7). A tracking issue is never closed by an
agent. `needs-human` is a hand-off state, distinct from any `kind:*` content
label.

## Demoable Units of Work

> Requirement IDs use the format **R{unit}.{seq}**. The planner references
> these directly; do not renumber after approval.

### Unit 1: Repository foundation

**Purpose:** Stand up the new public repo's baseline so the SDD agents have
the ADR, labels, shared fragments, CI (including a leak-scan), and
distribution model they import and assume. Demoable: CI is green, `gh aw
compile` succeeds on a sample workflow, the leak-scan passes, and the docs
site builds.
**Depends on:** None
**Affected areas:** `LICENSE` (new), `README.md` (new),
`.github/workflows/{lint,docs,leak-scan}.yml` (new), `mkdocs.yml` (new),
`decisions/0001-needs-human.md` (new), `templates/.github/labels.yml` (new),
`shared/{repo-conventions,rigor,runtime-setup}.md` (new),
`scripts/quick-setup.sh` (new), `docs/index.md` (new)

**Functional Requirements:**

- **R1.1**: The repository shall be public and shall carry a permissive
  OSI-approved `LICENSE` (MIT or Apache-2.0) and a `README.md` stating purpose,
  the pipeline, and install.
- **R1.2**: CI shall wire a `lint` workflow (markdownlint, actionlint,
  shellcheck) and a `docs` workflow (`mkdocs build --strict`). gh-aw shall be
  enabled and a sample workflow shall compile under `gh aw compile`.
- **R1.3**: A `leak-scan` CI workflow shall fail the build when any term from
  a denylist appears in the committed tree. The denylist (employer name,
  private org slugs, internal repository names, internal URLs, contributor
  personal data) shall be supplied as a repo or org **secret**, never
  committed, so the private terms are not themselves present in the public
  repo. The scan runs on every PR.
- **R1.4**: `decisions/0001-needs-human.md` shall define the `needs-human`
  contract for the whole SDD pipeline (the four clauses and the per-agent
  trigger table from this spec).
- **R1.5**: `templates/.github/labels.yml` shall define the base labels
  `needs-human`, `kind:{bug,feature,chore}`, and
  `priority:{must-have,should-have,nice-to-have}`, each with a hex color and a
  one-line description. SDD lifecycle and model-tier labels are added in
  Unit 2.
- **R1.6**: `shared/repo-conventions.md`, `shared/rigor.md`, and
  `shared/runtime-setup.md` shall be created as importable gh-aw fragments,
  carrying no org-specific or private literal. `rigor.md` shall state the
  evidence standard (reproduce, rule out false positives, cite a file:line or
  command output, bound scope, one finding per issue, 80% confidence floor).
- **R1.7**: The reusable-workflow (`on: workflow_call`) plus thin-wrapper
  distribution model shall be documented, and `scripts/quick-setup.sh` shall
  be created as the installer skeleton that fetches wrappers and syncs labels
  onto a consumer repo. Because the repo is public, thin-wrapper distribution
  works without a private-repo workaround.
- **R1.8**: The agent write identity shall be a configurable GitHub App (App
  ID and private key as repo or org variables and secrets); the foundation
  docs shall record the required variable and secret names. No bot identity is
  hardcoded.

**Proof Artifacts:**

- CLI: the `lint`, `docs`, and `leak-scan` workflows all pass on the
  foundation commit.
- CLI: `gh aw compile` succeeds on a sample workflow.
- File: `LICENSE` is an OSI-approved license; `decisions/0001-needs-human.md`
  exists and contains the four-clause contract and the trigger table.
- Test: a PR that adds a denylisted term to a file fails the `leak-scan` job.

### Unit 2: Human-interaction contract

**Purpose:** Add the SDD lifecycle labels, issue templates, command
vocabulary, and interaction fragment on top of the foundation. Demoable: open
an issue from the new template and see the lifecycle label and command hint.
**Depends on:** Unit 1
**Affected areas:** `templates/.github/labels.yml`,
`templates/.github/ISSUE_TEMPLATE/{feature,bug,chore}.md` (new),
`shared/sdd-interaction.md` (new), `docs/sdd/index.md` (new), `mkdocs.yml`

**Functional Requirements:**

- **R2.1**: `templates/.github/labels.yml` shall gain the lifecycle labels
  `sdd:spec`, `sdd:triage`, `sdd:ready`, `sdd:in-progress`, `sdd:review`,
  `sdd:done`, and the tier labels `model:haiku`, `model:sonnet`,
  `model:opus`, each with a hex color and one-line description.
- **R2.2**: The `feature`, `bug`, and `chore` issue templates shall be
  created. `feature` and `bug` shall apply `sdd:spec` on creation and shall
  carry a footer documenting the `/spec`, `/triage`, `/approve`, `/revise`,
  `/execute` command vocabulary.
- **R2.3**: `shared/sdd-interaction.md` shall be a new importable fragment
  stating the lifecycle-label state machine, the command table, and the
  `needs-human` contract clauses (referencing ADR 0001). Every `sdd-*`
  workflow imports it so the contract is defined once.
- **R2.4**: `docs/sdd/index.md` shall document the end-to-end flow for a team
  member and shall be added to `mkdocs.yml` nav.

**Proof Artifacts:**

- File: `templates/.github/labels.yml` contains all six `sdd:*` labels and all
  three `model:*` labels.
- File: `shared/sdd-interaction.md` references `decisions/0001-needs-human.md`.
- Test: opening a test issue from the `feature` template results in an issue
  carrying both `feature` and `sdd:spec` labels.

### Unit 3: Shared agent infrastructure (Distillery and Serena MCP)

**Purpose:** Make two MCP servers available to the SDD agents, configured not
hardcoded: Distillery for retrieval and memory, Serena for code intelligence.
Demoable: a smoke run resolves both servers and returns a result from each.
**Depends on:** Unit 1
**Affected areas:** `shared/sdd-mcp-distillery.md` (new),
`shared/sdd-mcp-serena.md` (new), `workflows/distillery-sync.md` (new),
`docs/sdd/mcp-tools.md` (new)

**Functional Requirements:**

- **R3.1**: `shared/sdd-mcp-distillery.md` shall be an importable fragment that
  declares the Distillery MCP server over HTTP transport, authenticated via
  OAuth, and documents the tools SDD agents may call (`search`, `find_similar`,
  `relations`, `recall`). The endpoint and OAuth credentials shall be read
  from repo or org variables and secrets; no endpoint or org slug is a literal.
- **R3.2**: Distillery queries from `sdd-*` agents shall be scoped (via the
  `project` filter) to this repository's own ingested content, so retrieval
  cannot surface unrelated or private knowledge from a shared store into
  public specs, issues, or PRs.
- **R3.3**: `workflows/distillery-sync.md` shall be a scheduled agentic
  workflow that keeps the store current by ingesting this repo's
  `docs/specs/`, `decisions/`, and issues and PRs via Distillery `gh-sync`.
  Daily cron.
- **R3.4**: `shared/sdd-mcp-serena.md` shall be an importable fragment that
  declares the Serena MCP server (`oraios/serena`) over the checked-out
  working tree and documents the symbol-level retrieval and editing tools
  agents may call. The fragment shall pin no language: Serena's language-server
  set is resolved at install time. When no language server exists for a repo's
  stack, the agents shall degrade gracefully to text-level file reading rather
  than fail.
- **R3.5**: Neither fragment shall contain a literal hostname, org slug, bot
  name, or absolute path. All such values are configuration.
- **R3.6**: A `workflow_dispatch` smoke workflow (or a documented dispatch
  procedure in `docs/sdd/mcp-tools.md`) shall resolve both servers and return
  one non-empty result from each, for install verification.

**Proof Artifacts:**

- File: `shared/sdd-mcp-distillery.md` and `shared/sdd-mcp-serena.md` exist and
  pass the `leak-scan` check.
- CLI: `gh aw compile` succeeds with both MCP server declarations present.
- Test: the smoke dispatch logs a non-empty `distillery.search` result
  (scoped to this repo's project) and a non-empty Serena symbol-query result.

### Unit 4: `sdd-spec` agent

**Purpose:** Turn a `sdd:spec`-labelled tracking issue into a structured spec
delivered as a PR, grounded in the target codebase. Demoable: label an issue,
get a spec PR.
**Depends on:** Units 2, 3
**Affected areas:** `workflows/sdd-spec.md` (new),
`shared/sdd-proof-artifacts.md` (new), `wrappers/sdd-spec.yml` (new)

**Functional Requirements:**

- **R4.1**: `workflows/sdd-spec.md` shall declare `engine: copilot`, trigger on
  `issues` (`labeled`, matching `sdd:spec`), `issue_comment` filtered to
  `/spec` and `/revise` from write-access authors, and `issues` (`unlabeled`,
  matching `needs-human`). It shall import `sdd-interaction.md`,
  `sdd-proof-artifacts.md`, `sdd-mcp-distillery.md`, `sdd-mcp-serena.md`,
  `repo-conventions.md`.
- **R4.2**: Before authoring, the agent shall perform a context assessment of
  the target repo using Serena: map the modules, conventions, and code areas
  the feature touches, so the spec reflects the real codebase.
- **R4.3**: The agent shall query Distillery (`search`, `find_similar`, scoped
  per R3.2) for prior specs, ADRs, and issues, and cite load-bearing matches
  inline as `(informed by #N)` or `(informed by ADR-0001)`.
- **R4.4**: The agent shall produce a spec file at
  `docs/specs/NN-spec-<slug>/NN-spec-<slug>.md` following the section
  structure of this spec, and open it as a `create-pull-request` (max 1,
  `draft: ${{ false }}`) titled `spec(<slug>): <issue title>`.
- **R4.5**: `shared/sdd-proof-artifacts.md` shall define the five
  proof-artifact types (Test, CLI, URL, Browser, File) and the "empty PR" rule
  verbatim: a proof that would pass against an empty PR is a health check, not
  a proof, and must be dropped. The agent shall emit 1 to 3 proof artifacts per
  demoable unit, each demonstrating behavior that exists only after that unit.
- **R4.6**: When the source issue is too vague to spec at >=80% confidence, or
  has unresolved scope, the agent shall post one comment with numbered
  clarifying questions, apply `needs-human`, and exit `noop`. It shall not
  guess. On `needs-human` removal it re-reads the thread and resumes.
- **R4.7**: On a merged spec PR (a trigger on `pull_request: closed, merged`),
  the agent shall move the tracking issue label from `sdd:spec` to
  `sdd:triage` and comment linking the spec.

**Proof Artifacts:**

- File: `workflows/sdd-spec.md` contains `engine: copilot`, the five import
  lines, and the three trigger types from R4.1.
- File: `shared/sdd-proof-artifacts.md` contains the string "would pass
  against an empty PR".
- Test: a test issue labelled `sdd:spec` with a clear feature description
  produces, within one run, a PR adding a `docs/specs/NN-spec-*` file whose
  Demoable Units section contains at least one `R1.1` requirement and at least
  one `(informed by` citation.
- Test: a test issue with a deliberately vague body ("make it better") yields
  no PR, a clarifying-questions comment, and the `needs-human` label.

### Unit 5: `sdd-triage` agent

**Purpose:** Triage a merged spec into a persisted architecture record and
then a task graph of linked sub-issues. One workflow, three phases:
architecture, parent tasks, sub-tasks. `sdd-triage` is also the seam for
cross-repo task routing and for future automatic routing. Demoable: merge a
spec, get an architecture PR; merge that, get task sub-issues.
**Depends on:** Units 3, 4
**Affected areas:** `workflows/sdd-triage.md` (new),
`wrappers/sdd-triage.yml` (new)

**Functional Requirements:**

- **R5.1**: `workflows/sdd-triage.md` shall trigger on `issues` (`labeled`,
  matching `sdd:triage`) for phase A; `pull_request` (`closed`, merged) on the
  feature's architecture PR for phase B; `issue_comment` filtered to `/triage`,
  `/approve`, `/revise` from write-access authors; and `issues` (`unlabeled`,
  matching `needs-human`). It shall import `sdd-interaction.md`,
  `sdd-proof-artifacts.md`, `sdd-mcp-distillery.md`, `sdd-mcp-serena.md`,
  `repo-conventions.md`.
- **R5.2**: **Phase A, architecture.** On `sdd:triage` (or `/triage`): the
  agent shall map the affected code with Serena, query Distillery
  (`find_similar`, `relations`, scoped per R3.2) for prior architecture
  records and ADRs, and **always** produce a per-feature architecture record
  at `docs/specs/NN-spec-<slug>/architecture.md` capturing the chosen
  approach, rationale, data and interface changes, and alternatives
  considered. It opens this as a `create-pull-request` titled
  `arch(<slug>): <issue title>` and stops. For a feature with no significant
  decision the record is a short explicit "no significant architecture
  decision; approach: ..." note: the phase always runs and always persists a
  record.
- **R5.3**: When phase A makes a genuinely cross-cutting decision (one that
  constrains work beyond this feature), the same PR shall also add a numbered
  `decisions/NNNN-<slug>.md` ADR. A genuine architecture fork (more than one
  defensible approach with material tradeoffs) triggers `needs-human` with the
  options stated, rather than the agent deciding unilaterally.
- **R5.4**: **Phase B, parent tasks.** On merge of the architecture PR: the
  agent shall create one parent task sub-issue per demoable unit, linked to
  the tracking issue via `link-sub-issue`, post a phase-B summary comment with
  the dependency order, and stop. It shall not decompose into sub-tasks until
  `/approve`.
- **R5.5**: **Phase C, sub-tasks.** On `/approve`: the agent shall decompose
  each parent task into implementation sub-tasks (further linked sub-issues),
  each carrying a structured body block: the spec path and R-IDs covered, the
  files in scope (resolved against the real tree via Serena), the `repo:`
  field (R5.6), proof artifacts, and verification commands derived from the
  target repo's `CLAUDE.md` or `README.md` (no hardcoded toolchain). It shall
  assign each task a complexity and the matching `model:*` label. Dependencies
  shall be recorded as `blocked by` lines forming a DAG; a detected cycle
  triggers `needs-human`.
- **R5.6**: **Cross-repo task routing seam.** Every task sub-issue's structured
  body shall carry a `repo:` field, defaulting to the tracking issue's repo.
  The task DAG may span repos; a cross-repo dependency is recorded as
  `blocked by <owner>/<repo>#N`. The decomposition logic shall support a
  multi-repo graph. This is the seam a future automatic router populates and
  the field `sdd-execute` reads; cross-repo task execution is the documented
  next extension (see Non-Goals).
- **R5.7**: On phase C completion the agent shall move the tracking issue label
  to `sdd:ready` and apply `sdd:ready` to every task sub-issue with no open
  dependency.

**Proof Artifacts:**

- File: `workflows/sdd-triage.md` contains the three-phase trigger set from
  R5.1 and the `link-sub-issue` safe-output.
- Test: commenting `/triage` on a tracking issue whose spec PR is merged
  produces an `arch(<slug>)` PR adding `docs/specs/NN-spec-*/architecture.md`.
- Test: merging that architecture PR creates one parent sub-issue per demoable
  unit and a phase-B summary comment, and creates no sub-tasks.
- Test: commenting `/approve` then produces sub-task issues each carrying a
  `repo:` field, a `model:*` label, and a structured body block with R-IDs and
  proof artifacts.

### Unit 6: `sdd-execute` agent

**Purpose:** Turn a ready task sub-issue into an implementation PR with proof
artifacts captured, using symbol-level code intelligence, and address review
comments on its own PR. The workflow is compiled into three model-tier
variants so task complexity selects the model. Demoable: a task issue produces
a PR.
**Depends on:** Units 3, 5
**Affected areas:** `workflows/sdd-execute.md` (new),
`wrappers/sdd-execute.yml` (new)

**Functional Requirements:**

- **R6.1**: `workflows/sdd-execute.md` shall trigger on a daily `schedule`
  cron, `workflow_dispatch`, `issue_comment` filtered to `/execute`, and
  `pull_request_review_comment` (`created`) on its own PRs. It shall import the
  runtime fragment, `sdd-interaction.md`, `sdd-proof-artifacts.md`,
  `sdd-mcp-serena.md`, `repo-conventions.md`. The source shall be authored
  once and compiled into three model-tier variants (`sdd-execute-haiku`,
  `sdd-execute-sonnet`, `sdd-execute-opus`) differing only in the engine
  model; this realizes model-tier-by-complexity given gh-aw's compile-time
  model binding.
- **R6.2**: On a scheduled run each variant shall select one task sub-issue
  labelled `sdd:ready` and carrying the `model:*` label matching that variant,
  with no open `blocked by` dependency, no `needs-human` label, and a `repo:`
  field equal to the running repo, choosing highest `priority:*` then oldest
  `updated_at`, and move it to `sdd:in-progress`.
- **R6.3**: A `sdd:ready` task whose `repo:` field names a different repo
  shall be skipped (not an error, no `needs-human`): cross-repo execution is
  the documented next extension. The skip shall be recorded in the run log.
- **R6.4**: The agent shall implement the task using Serena symbol-level
  retrieval and editing within the files in the task's scope block, run the
  verification commands, capture each proof artifact's output, and open one
  `create-pull-request` (max 1) titled `<type>(<scope>): <task title>` with
  `Closes #<task>` and the captured proof output in the PR body.
- **R6.5**: The agent shall never edit protected paths (`.github/`,
  `decisions/`, `templates/.github/`, secrets). A task requiring such an edit
  triggers `needs-human` instead of a PR.
- **R6.6**: On `pull_request_review_comment`, the agent shall address
  actionable review comments by pushing further commits to the same branch (no
  second PR). A review comment it cannot resolve mechanically triggers
  `needs-human` on the PR.
- **R6.7**: When no eligible `sdd:ready` task exists, the agent shall emit
  `noop` and exit 0. When all task sub-issues of a tracking issue are closed,
  it shall move the tracking issue to `sdd:done` and apply `needs-human` with a
  comment that all tasks are complete and a final review and close is needed.
  The agent shall not close the tracking issue itself; a human closes it.

**Proof Artifacts:**

- File: `workflows/sdd-execute.md` contains the `cron` schedule, the
  `pull_request_review_comment` trigger, and a protected-paths list.
- CLI: `sdd-execute` compiles into three model-tier lock files; each variant's
  candidate filter names a distinct `model:*` label.
- Test: a `sdd:ready` task issue with a local `repo:` produces, within one
  run, a PR with `Closes #<task>` and a proof-artifact block in the body, and
  the task issue moves to `sdd:in-progress`.
- Test: a `sdd:ready` task with a non-local `repo:` is skipped and logged; no
  PR is opened for it.

### Unit 7: `sdd-validate` agent

**Purpose:** Run validation gates at all four phase boundaries and post
advisory findings. Demoable: a validation comment appears on a spec PR.
**Depends on:** Unit 4
**Affected areas:** `workflows/sdd-validate.md` (new),
`shared/sdd-gates.md` (new), `wrappers/sdd-validate.yml` (new)

**Functional Requirements:**

- **R7.1**: `workflows/sdd-validate.md` shall trigger on `pull_request`
  (`opened`, `synchronize`) and on `issues` (`labeled`, matching `sdd:ready`).
  It shall resolve the boundary as: a `*-spec-*.md` change is the spec
  boundary; an `architecture.md` or `decisions/**` change is the architecture
  boundary; any other PR change is the implementation boundary; an
  `sdd:ready` label event is the triage boundary (the task graph is sub-issues,
  not a PR).
- **R7.2**: `shared/sdd-gates.md` shall enumerate the four per-boundary gate
  sets: **spec gates** (acceptance criteria testable, no implementation
  leakage, assumptions explicit, proof artifacts present and behavioral);
  **architecture gates** (a decision and rationale present, alternatives
  considered, consistent with existing `decisions/`, no implementation detail
  masquerading as a decision); **triage gates** (every spec R-ID covered by a
  task, dependencies form a DAG, each task single-session sized, every task
  has a `repo:` field); **implementation gates** (proof artifacts re-executed
  and passing, changed files within task scope, no real credentials in the
  diff).
- **R7.3**: The agent shall post findings as a single comment on the PR or the
  tracking issue, with a severity per finding (Blocker, Warning, Info) and
  `file:line` evidence per `shared/rigor.md`, updating that one comment on
  re-runs rather than posting a new one each time.
- **R7.4**: Validation shall **not** be a required status check and shall not
  fail the workflow on Blocker findings: it is advisory by design. A Blocker
  finding instead triggers `needs-human` on the PR or tracking issue with the
  failed gate cited.
- **R7.5**: A clean validation pass at the implementation boundary shall move
  the linked tracking issue from `sdd:in-progress` to `sdd:review`.

**Proof Artifacts:**

- File: `shared/sdd-gates.md` contains all four named gate sets.
- File: `workflows/sdd-validate.md` shows no `required` status-check
  declaration, exits 0 on Blocker findings, and triggers on both
  `pull_request` and `issues: labeled`.
- Test: a PR adding a `docs/specs/**` file with an untestable acceptance
  criterion yields a comment with a Blocker finding and the `needs-human`
  label, and the workflow run still concludes successfully.

### Unit 8: `sdd-review` agent

**Purpose:** Code-review implementation PRs for correctness, security, and
spec compliance. Demoable: review comments appear on an implementation PR.
**Depends on:** Unit 6
**Affected areas:** `workflows/sdd-review.md` (new),
`wrappers/sdd-review.yml` (new)

**Functional Requirements:**

- **R8.1**: `workflows/sdd-review.md` shall trigger on `pull_request`
  (`opened`, `synchronize`) for PRs whose head branch matches the
  `sdd-execute` branch prefix, and shall import `sdd-interaction.md`,
  `sdd-mcp-serena.md`, `repo-conventions.md`.
- **R8.2**: The agent shall review the diff across three concerns: correctness
  (logic errors, edge cases), security (input validation, secret exposure),
  and spec compliance (does the change satisfy the task's R-IDs), using Serena
  to trace symbols beyond the diff where a finding depends on call sites. It
  shall post findings as PR review comments anchored to `file:line`.
- **R8.3**: A diff larger than 200 changed lines shall be reviewed in
  concern-partitioned batches so no single run reviews the whole diff for all
  three concerns at once.
- **R8.4**: A CRITICAL or HIGH finding, or a genuine spec-compliance ambiguity,
  shall trigger `needs-human` on the PR. Lower-severity findings are posted as
  comments only; the agent does not block.
- **R8.5**: The agent shall not approve or merge PRs. Merge authority stays
  with humans and consumer CI.

**Proof Artifacts:**

- File: `workflows/sdd-review.md` contains the three review concerns and the
  200-line batching rule, and no `merge` or `approve` safe-output.
- Test: an implementation PR with an injected obvious bug receives a PR review
  comment naming the bug at `file:line`.

### Unit 9: Consumer packaging and existing-codebase install

**Purpose:** Make the suite installable on another repo, including one with an
existing codebase, with one command. Demoable: `quick-setup.sh` installs the
suite on a fixture repo that already has code, and a feature issue runs end to
end on it.
**Depends on:** Units 1 to 8
**Affected areas:** `scripts/quick-setup.sh`, `workflows/README.md` (new),
`docs/sdd/install.md` (new)

**Functional Requirements:**

- **R9.1**: Each `sdd-*` workflow shall be authored as a reusable workflow
  (`on: workflow_call`) with a thin `wrappers/sdd-*.yml` caller, per the
  distribution model from Unit 1.
- **R9.2**: `scripts/quick-setup.sh` shall gain an `--suite sdd` option that
  installs the `sdd-*` wrappers (with `sdd-execute` in its three model-tier
  variants), `distillery-sync`, the `sdd:*` and `model:*` labels, and the
  issue templates on the target repo.
- **R9.3**: Install shall configure, not hardcode: the GitHub App identity,
  the Distillery HTTP endpoint and OAuth credentials, and the Serena
  language-server set are resolved at install time from operator-supplied
  values. Install shall detect the target repo's stack and provision the
  matching Serena language server, or record that none is available so the
  agents degrade gracefully. No `sdd-*` source carries an org-specific or
  private literal.
- **R9.4**: `docs/sdd/install.md` shall document the install, the required
  configuration (GitHub App, `COPILOT_GITHUB_TOKEN`, Distillery endpoint and
  OAuth, leak-scan denylist secret), a checklist for a repo with an existing
  codebase, and a post-install smoke test, ending with a `## Verification`
  section of copy-pasteable `gh` commands.

**Proof Artifacts:**

- File: `wrappers/` contains a wrapper for each agent, including the three
  `sdd-execute` model-tier variants.
- CLI: `bash scripts/quick-setup.sh --target-repo <owner>/test-fixture
  --suite sdd --dry-run` lists the `sdd-*` wrappers, `distillery-sync`, and the
  labels in its planned-writes output.
- CLI: the `leak-scan` workflow passes on the full tree at this unit's commit.
- Test: on a fixture repo seeded with existing code, a feature issue runs
  spec -> architecture -> triage -> execute -> validate -> review without
  source edits to the installed wrappers.

### Unit 10: Brand assets and docs-site theming

**Purpose:** Theme the mkdocs site with committed brand assets and set the
GitHub repository's social-preview card from those assets, so the public site
and the repo's link previews carry a consistent identity. Demoable: the docs
site builds with the brand logo, favicon, palette, and typography applied, and
the repository's social-preview card renders the brand card.
**Depends on:** Unit 1
**Affected areas:** `mkdocs.yml`, `assets/` (new), repository settings (the
social-preview card)

**Functional Requirements:**

- **R10.1**: An `assets/` directory shall be created and shall carry the brand
  assets committed to the repo: a logo image and a favicon image, produced per
  the brand tooling. The assets carry no employer name, private org slug, or
  other denylisted literal, so the `leak-scan` check (R1.3) still passes.
- **R10.2**: `mkdocs.yml` shall reference the `assets/` logo and favicon via
  the Material theme's `theme.logo` and `theme.favicon` keys, and shall set the
  theme `palette` (colors) and `font` (typography) to the brand values from the
  brand tooling.
- **R10.3**: The GitHub repository's social-preview card shall be set from the
  brand assets, so issue, PR, and repository link previews render the brand
  card. The card source shall live under `assets/` and the setting step shall
  be documented (the social card is a repository setting, not a tracked file).

**Proof Artifacts:**

- File: `mkdocs.yml` references the `assets/` logo and favicon through
  `theme.logo` and `theme.favicon`, and declares a `palette` and a `font`.
- CLI: `mkdocs build --strict` succeeds with the themed config, and the built
  site includes the logo and favicon assets.
- File: `assets/` contains the logo, the favicon, and the social-preview card
  image, and the full tree passes the `leak-scan` check at this unit's commit.

## Non-Goals (Out of Scope)

- **Cross-repo task execution.** The task schema and DAG support cross-repo
  routing (R5.6 builds the seam) and `sdd-execute` reads the `repo:` field
  (R6.3), but `sdd-execute` opening PRs in sibling repos, with per-repo App
  tokens, is a follow-up phase and is not built here. Single-repo execution is
  what this spec exercises.
- **Automatic routing.** Deciding a task's target repo from signals is a
  future extension that populates the R5.6 `repo:` seam. No routing behavior
  ships here.
- **Auto-merge.** No `sdd-*` agent merges a PR. Humans merge; consumer CI gates.
- **Hosting or scaling Distillery.** This spec consumes Distillery as a
  configured HTTP MCP endpoint; standing it up is operator infra.
- **Depending on or modifying any prior private system.** This spec creates an
  independent public repo. It reuses generic patterns only; it links to,
  references, and changes nothing private.

## Design Considerations

No UI work. The user-facing surface is GitHub issues, comments, labels, and
PRs with GitHub defaults. The lifecycle-label set is the task board; the
`label:needs-human` filter is the escalation queue. Validation is advisory by
design: no agent blocks a merge, and no agent is a required status check.

## Repository Standards

- The repository is public. No employer or company name, private org slug,
  private or internal repository name, internal URL, cost or budget figure, or
  contributor personal data appears in any committed file, issue, PR, or
  comment. The `leak-scan` CI check (R1.3) enforces this on the tree against a
  secret denylist; for issues, PRs, and comments it is an authoring discipline.
  Patterns reused from prior private work are described generically and never
  attributed by name.
- No em dashes in any prose, code comment, or workflow string.
- Markdown uses ATX headings and fenced code blocks with language tags.
- Workflow files are authored in `gh aw compile` source format; the compiled
  `.lock.yml` is generated by the toolchain on the runner, never hand-edited.
  No global find/replace on a `.md` source without a recompile.
- No org slug, bot name, hostname, or absolute path is a literal in any
  `sdd-*` workflow or `shared/sdd-*` fragment. The GitHub App, MCP endpoints,
  and org are configuration supplied at install.
- Agents read stack and convention from `CLAUDE.md` (fallback `README.md`);
  no toolchain is hardcoded into a source.
- Branch names: `sdd/<task-id>-<slug>` for `sdd-execute` PRs; `spec/<slug>`
  for `sdd-spec` PRs; `arch/<slug>` for `sdd-triage` architecture PRs.
- Every new runbook or doc ends with a `## Verification` section.

## Verification

**Project maturity:** Greenfield. Unit 1 establishes the CI gates (lint,
mkdocs strict build, actionlint, shellcheck, leak-scan) and gh-aw compilation;
every later unit runs against them.

**Available commands (after Unit 1):**

| Check | Command |
|-------|---------|
| Lint  | `npx markdownlint-cli2 docs/**/*.md` + `shellcheck` + `actionlint` |
| Build | `mkdocs build --strict` |
| Test  | `gh aw compile workflows/sdd-*.md` (frontmatter and schema validation) |
| Leak  | `leak-scan` CI job against the secret denylist |

**Greenfield bootstrapping:** Unit 1 is the bootstrapping unit. It sets
`verification.pre` and `verification.post` to empty for itself and establishes
the commands above for Units 2 to 10.

## Technical Considerations

- Agentic workflows have no interactive prompt. Every `AskUserQuestion`-shaped
  step is re-expressed as: post a comment, apply `needs-human`, exit `noop`;
  resume on `issues.unlabeled` of `needs-human`. Defined once in
  `shared/sdd-interaction.md`.
- The spec and the per-feature architecture record are committed files
  (PR-reviewable, version-controlled, mkdocs-rendered) while tasks are
  sub-issues. Reviewable artifacts need a diff; tasks need a queue.
- `sdd-triage` is one workflow with three phases gated by GitHub events: phase
  A on the `sdd:triage` label, phase B on the architecture PR merge, phase C
  on `/approve`. Architecture is a real phase: it always runs and always
  persists `docs/specs/NN-spec-<slug>/architecture.md`; a genuine cross-cutting
  decision is additionally promoted to a numbered ADR.
- Validation runs at four boundaries. Three are PRs (spec, architecture,
  implementation) and validate on `pull_request`. The triage boundary is a
  graph of sub-issues, not a PR, so `sdd-validate` also triggers on the
  `sdd:ready` label event and validates the task graph then. Validation is
  advisory by design: it posts findings and escalates Blockers via
  `needs-human`, never as a required check, so a draft is never wedged on the
  agent's own opinion.
- MCP tooling. Distillery attaches over HTTP transport authenticated via OAuth
  for retrieval and memory; `distillery-sync` keeps its store current via
  `gh-sync`. Because the store may be shared and may hold unrelated private
  content, every `sdd-*` Distillery query is scoped to this repo's own project
  so retrieval cannot surface private knowledge into public artifacts. Serena
  attaches over the checked-out working tree for symbol-level code retrieval
  and editing, and degrades gracefully to text-level reading when no language
  server exists for the repo's stack.
- Model tiering. gh-aw binds the engine model at compile time, so the
  `sdd-execute` source is compiled into three variants (haiku, sonnet, opus).
  `sdd-triage` assigns a task's `model:*` label by complexity; the matching
  variant is the one that picks the task up.
- Existing codebases. The suite's own repo is greenfield, but Serena is the
  reason it works on consumer repos that are not: `sdd-spec` assesses the real
  code before writing, `sdd-triage` maps blast radius from real symbols,
  `sdd-execute` edits at the symbol level, and `sdd-review` traces call sites
  beyond the diff.
- Cross-repo seam. `sdd-triage` produces a task DAG that may span repos via the
  `repo:` field; `sdd-execute` reads it and executes only local-repo tasks.
  The seam supports two future extensions on the same field: cross-repo
  execution and automatic routing.
- Public repo. Because the repo is public, thin-wrapper `workflow_call`
  distribution works as designed: consumers commit a small wrapper that calls
  the hosted reusable workflow. No private-to-private workaround is needed.
- gh-aw safe-outputs used: `create-pull-request`, `create-issue`,
  `link-sub-issue`, `add-comment`, `add-labels`, `noop`. All writes go through
  safe-outputs with threat detection; `permissions:` stays read-only.

## Security Considerations

- The repository is public. The `leak-scan` CI check (R1.3) fails any PR that
  introduces a denylisted private term; the denylist lives in a secret, never
  in the tree. Distillery queries are project-scoped (R3.2) so a shared
  knowledge store cannot leak unrelated private content into public specs,
  issues, or PRs.
- The suite writes via a configurable GitHub App identity (App ID and private
  key supplied as repo or org variables and secrets), minted per run and
  scoped to the running repo, not a broad PAT and not a hardcoded bot.
  `sdd-execute` opens same-repo PRs only.
- `sdd-execute` never edits `.github/`, `decisions/`, `templates/.github/`, or
  secrets; such a task escalates via `needs-human`.
- MCP outputs are untrusted input. Distillery search results and Serena code
  reads are tool data, not instructions; agent prompts wrap them as untrusted
  and threat detection on safe-outputs still applies. The Distillery OAuth
  credential and HTTP endpoint are secrets. Serena is granted read and write
  to the checked-out working tree only, never to `.github/` or secrets.
- Comment commands are gated to write-access authors via the gh-aw `command:`
  trigger; a non-write user commenting `/spec` or `/execute` is a no-op.
- No `sdd-*` agent has merge or approve authority: agents draft, humans and
  consumer CI gate.
- `needs-human` is never cleared by an agent (ADR 0001 clause 3), so an agent
  cannot release its own hand-off.

## Success Metrics

- All ten demoable units land with proof artifacts passing.
- Each `sdd-*` source compiles clean under `gh aw compile`, including the
  three `sdd-execute` model-tier variants.
- The `leak-scan` CI check passes on every commit; no private term ever
  reaches the public tree.
- Dogfood end-to-end in the suite's own repo: one feature issue travels
  issue -> spec PR -> merged -> architecture PR -> merged -> triage sub-issues
  -> implementation PR -> validation -> review, with human action limited to
  merging PRs, answering `needs-human` prompts, and the final close.
- Install proof: the same end-to-end run completes on a fixture consumer repo
  with an existing codebase, with no edits to the installed wrappers.
- Validation fires at all four boundaries: a deliberately flawed artifact at
  each of spec, architecture, triage, and implementation produces a Blocker
  finding and `needs-human`.
- The `label:needs-human` queue is the only place a blocked item appears: no
  agent exits silently, no agent posts a hand-off comment twice.

## Resolved Questions

Decisions from review, recorded for provenance.

1. **Home repo**: a new public repo, `norrietaylor/spectacles`. Prior
   private work is a generic pattern reference, never named.
2. **Visibility**: public from day one, so thin-wrapper distribution works.
3. **Spec number**: this is the first spec in the new repo, so `01`.
4. **ADRs**: there is no not-gating ADR. The single foundation ADR is
   `0001-needs-human`. Validation being advisory is stated as a design
   decision, not an ADR.
5. **Private details**: the repo is public, so a `leak-scan` CI check plus
   project-scoped Distillery queries plus a Repository Standard keep employer,
   private org, internal repo, cost, and PII data out of the tree, issues, and
   retrieval (R1.3, R3.2).
6. **Distillery transport**: HTTP, authenticated via OAuth (R3.1).
7. **Serena language-server coverage**: graceful degradation to text-level
   reading when no language server exists for the stack (R3.4, R9.3).
8. **Model tiering**: `sdd-execute` is compiled into three model-tier variants;
   a task's `model:*` label selects the variant that runs it (R6.1, R6.2).
9. **Tracking-issue close**: never closed by an agent; `sdd-execute` applies
   `needs-human` for a human to do the final review and close (R6.7).
10. **Cross-repo execution and automatic routing**: follow-up phases that
    extend the R5.6 `repo:` seam; neither is built in this spec.

## Open Questions

No open questions at this time.
