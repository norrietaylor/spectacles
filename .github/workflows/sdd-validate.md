---
on:
  workflow_call:
    inputs:
      aw_context:
        description: The triggering entity, resolved by the wrapper.
        required: true
        type: string
  # roles: all — this agent is activated by an upstream agent's output
  # (App-authored pull requests and labels), not only by humans. The default
  # roles gate (admin/maintainer/write) cancels a bot-triggered run at
  # pre_activation; the wrapper's route job is the real gate. See ADR 0004.
  roles: all
permissions:
  contents: read
  issues: read
  pull-requests: read
engine: copilot
# Agent-firewall egress allow-list. `defaults` is gh-aw's baseline host set;
# `*.run.app` lets the agent export OTLP spans to the observability collector on
# Cloud Run (firewalled otherwise). See ADR 0020.
network:
  allowed:
    - defaults
    - "*.run.app"
# OpenTelemetry (ADR 0020): export agent spans — token usage, duration,
# outcomes — over OTLP. The secret URL embeds a write-only ingest key, so no
# auth header is needed (headerless also dodges the gh-aw headers-YAML
# bug, github/gh-aw#37067). `if-missing: warn` degrades a missing secret to a
# warning, so a consumer that has not set GH_AW_OTEL_ENDPOINT is unaffected. The
# wrapper maps the secret in — cross-owner workflow_call does not inherit it.
observability:
  otlp:
    if-missing: warn
    endpoint: ${{ secrets.GH_AW_OTEL_ENDPOINT }}
# The OTLP endpoint secret embeds a write-only ingest key. gh-aw's built-in
# redaction (GH_AW_SECRET_NAMES) covers only the engine/GitHub tokens, not this
# value, so add a custom redaction step that scrubs it from /tmp/gh-aw before the
# artifact upload. Runs after built-in redaction; no-op when the secret is unset.
secret-masking:
  steps:
    - name: Redact OTLP endpoint from artifacts
      # always(): the artifact upload runs on failure paths too (if: always()),
      # and the built-in redaction is always() — match it so a failed run cannot
      # upload the endpoint unredacted.
      if: always()
      env:
        GH_AW_OTEL_ENDPOINT: ${{ secrets.GH_AW_OTEL_ENDPOINT }}
      run: |
        if [ -n "${GH_AW_OTEL_ENDPOINT:-}" ]; then
          find /tmp/gh-aw -type f -exec sed -i "s#${GH_AW_OTEL_ENDPOINT}#[REDACTED-OTEL-ENDPOINT]#g" {} + 2>/dev/null || true
        fi
inlined-imports: true
strict: false
imports:
  - norrietaylor/spectacles/shared/principles.md@main
  - norrietaylor/spectacles/shared/repo-conventions.md@main
  - norrietaylor/spectacles/shared/sdd-interaction.md@main
  - norrietaylor/spectacles/shared/sdd-gates.md@main
tools:
  github:
    toolsets: [default]
safe-outputs:
  github-app:
    client-id: ${{ vars.APP_ID }}
    private-key: ${{ secrets.APP_PRIVATE_KEY }}
    # Scope the minted token to the repository the workflow runs in. Without an
    # explicit repositories value the compiler emits a reference to an
    # activation output that strict: false does not produce, leaving the token
    # scoped to every repository the App can reach. See ADR 0004.
    owner: ${{ github.repository_owner }}
    repositories:
      - ${{ github.event.repository.name }}
  add-comment:
    max: 1
    hide-older-comments: true
  add-labels:
    allowed: [needs-human, sdd:review, sdd:spike-resolved]
    max: 1
  remove-labels:
    allowed: [sdd:in-progress]
    max: 1
  noop:
---

# sdd-validate

`sdd-validate` is the validation agent of the issue-native SDD pipeline. It
runs the per-boundary gate sets at all four phase boundaries (spec,
architecture, triage, implementation) and posts the findings as a single
advisory comment. It never blocks a merge: validation is advisory by design.

This workflow is a reusable workflow: it is invoked through `workflow_call`
from the thin wrapper `wrappers/sdd-validate.yml`, which carries the real event
triggers. The wrapper passes the triggering pull request or issue through the
`aw_context` input so this agent knows which entity it is operating on.

## Why this agent is advisory

A merge is gated by human review and the consumer repository's own CI, never
by this agent. `sdd-validate` is therefore not a required status check, and it
exits successfully even when it reports a Blocker finding. A Blocker is
surfaced to a human through the `needs-human` hand-off, not through a failed
check. A draft is never wedged on the agent's own opinion.

## Triggers this agent handles

The wrapper invokes this agent for one of two situations. Determine which one
applies from the `aw_context` input before doing anything else.

1. **A pull request was opened or synchronized.** Validate the pull request at
   the boundary its changed files resolve to (see step 2 of the procedure, the
   boundary-resolution step).
2. **A tracking issue gained the `sdd:ready` label.** Validate the triage
   boundary: the task graph is a set of linked sub-issues, not a pull request,
   so the `sdd:ready` label event is the non-pull-request triage boundary.
   `sdd:ready` is also applied by `sdd-triage` phase C to every unblocked task
   sub-issue, so the wrapper's `route` job filters out an event whose subject
   has a parent (a Unit or a task is not a tracking issue). The agent
   re-confirms the same precondition at the bottom of this section as
   defense in depth.

This agent has no `needs-human`-removal resume trigger. A Blocker it escalates
on a pull request is resumed by a fresh `pull_request: synchronize`: the human
clears `needs-human` and pushes a fix commit, and that event re-runs the gate
set against the corrected diff. Resuming on `synchronize` ties re-validation to
an actual fix — clearing `needs-human` alone would only re-run the same gates
against the unchanged diff and re-post the same Blocker. A Blocker at the
triage boundary is escalated on the tracking issue and is purely advisory:
validation never gates a merge or the `/approve` step, so the human reads the
findings, addresses the task graph as they judge fit, and proceeds — there is
no agent re-run. The wrapper therefore subscribes to no `unlabeled` event.

When the triggering item already carries the `needs-human` label, stop
immediately and emit `noop`. A `needs-human`-labelled item is off-limits during
candidate selection (see the imported interaction contract); the hand-off
comment has already been posted and must not be posted again.

When the trigger is situation 2 (`sdd:ready` on an issue), confirm the
labelled issue is a tracking issue before applying the triage gate set. A
tracking issue has no parent; a Unit and a task each have a parent in the
feature tree. Read the issue's `parent` (`parent_issue_url` in the REST issue
object) and, when it resolves to another issue, stop and emit `noop` — the
labelled item is a sub-issue, not a tracking issue, and the wrapper's routing
filter has been bypassed somehow. This is the agent-level defense in depth
for the wrapper's parent-absence filter.

## What this agent produces

For every run, this agent posts exactly one findings comment on the pull
request or the tracking issue. It applies `needs-human` when a gate produces a
Blocker finding. On a clean implementation-boundary pass against a full-path
feature it moves the linked tracking issue from `sdd:in-progress` to
`sdd:review`. On a fast-path feature (ADR 0012) it does **not** move the
lifecycle: `sdd-execute` writes `sdd:done` when the implementation pull
request merges, and this agent is not the declared writer of `sdd:done`. On a
spike-boundary pass it resolves the spike outcome instead: a `proved` spike
gains `sdd:spike-resolved` on the spike sub-issue; a `disproved` or `partial`
spike parks the tracking issue at `needs-human` with one pointer comment. It
opens no pull request and creates no issue.

## Procedure

### 1. Read the conventions and the triggering item

Read `CLAUDE.md` (fallback `README.md`) for the target repository's build,
test, and convention guidance, per the imported repository-conventions
fragment. Read the triggering item resolved from `aw_context`: for a pull
request, its title, body, diff, and comments; for an `sdd:ready` issue, the
tracking issue and every linked task sub-issue.

### 2. Resolve the boundary

The four phase boundaries each have their own gate set. Resolve which boundary
this run is validating before applying any gate:

- **Spec boundary.** The pull request adds or changes a `*-spec-*.md` file
  under `docs/specs/`.
- **Architecture boundary.** The pull request adds or changes an
  `architecture.md` file under `docs/specs/`, or any file under `decisions/`.
- **Spike boundary.** The pull request adds or changes a `*.md` file under
  `docs/spikes/`. The spike's written finding is the deliverable; the spike's
  own gate set (step 3) applies, not the implementation gate set.
- **Implementation boundary.** The pull request changes any other file, that
  is, a change that is neither a spec file, nor an architecture or decisions
  file, nor a spike file.
- **Triage boundary.** The trigger is an `sdd:ready` label event on a tracking
  issue. The task graph is the set of linked sub-issues, not a pull request.

A pull request resolves to exactly one boundary. When a pull request touches
files of more than one boundary, resolve to the boundary of the most
significant change in this order: spec, then architecture, then spike, then
implementation. Placing spike ahead of implementation stops a spike PR — which
carries no behavior-demonstrating proof artifact by design — from falling
through to the implementation catch-all and drawing a false Blocker on the
empty-PR rule. State the resolved boundary in the findings comment.

**Fast-path awareness** (ADR 0012). When the tracking issue linked to
the triggering item carries `sdd:fastpath`, `sdd:fastpath-review`, or
shows fast-path history (the tracking issue was a fast-path tracking
issue on the implementation-boundary check, identifiable by the
absence of a sub-issue tree under it), apply the boundary's gate set
with the following adjustments:

- The spec boundary check accepts a stub spec (the structural minimum
  from ADR 0012 §3: a one-paragraph problem statement, at least one
  R-ID, 1–3 proof artifacts, one Unit, and the single-line "Fast-path:
  no cross-cutting design" note) and a light spec (the single-PR depth
  from ADR 0024: multiple demoable units, full `R{unit}.{seq}` IDs,
  1–3 proof artifacts per unit, and an optional Design-notes section
  in lieu of an architecture record). The "no architecture record" is
  not a finding for either depth.
- The architecture boundary does not fire on a fast-path issue: there
  is no architecture PR. A run that nonetheless resolves to the
  architecture boundary on a fast-path issue (e.g. a fast-path PR that
  edits only `decisions/`) is treated as a normal
  architecture-boundary check; the absence of a per-feature
  architecture record is not raised.
- The triage boundary does not fire on a fast-path issue. A
  fast-path tracking issue is never labelled `sdd:ready` by an agent
  (its lifecycle goes
  `sdd:fastpath → sdd:fastpath-review → sdd:fastpath → sdd:in-progress`),
  so the `sdd:ready` label event that selects this boundary cannot
  occur. If the wrapper nonetheless routes this case (a fast-path
  tracking issue with a hand-applied `sdd:ready`), confirm there is
  no sub-issue tree to walk and emit a single Info finding naming the
  inconsistency; do not file Blockers for "no R-ID covered" or "no
  task" on an empty tree.
- The implementation boundary gate set still applies in full. The
  "changed files within task scope" gate reads the files-in-scope
  block from the execution plan comment (the
  `[sdd-spec:fastpath-plan]` marker on the tracking
  issue) instead of from a task sub-issue body; the rest of the gate
  set is unchanged.

### 3. Apply that boundary's gate set

Apply only the resolved boundary's gate set from the imported validation-gates
fragment. The four gate sets are defined there, not here:

- **Spec gates:** acceptance criteria testable, no implementation leakage,
  assumptions explicit, proof artifacts present and behavioral.
- **Architecture gates:** a decision and rationale present, alternatives
  considered, consistent with existing `decisions/`, no implementation detail
  masquerading as a decision.
- **Triage gates:** every spec R-ID covered by a task, dependencies form a
  DAG, each task single-session sized, every task carries a `repo:` field.
- **Spike gates:** a Conclusion is present; for a `disproved` or `partial`
  conclusion, Action items are present; no real credentials in the diff.
- **Implementation gates:** proof artifacts re-executed and passing, changed
  files within task scope, no real credentials in the diff.

Apply each gate as one checkable property. Apply the 80% confidence floor from
the imported evidence-rigor standard before filing any finding: an uncertain
pattern is a note, not a Blocker.

On a spike boundary, read the spike doc's Conclusion (`proved`, `disproved`, or
`partial`) and apply the spike gate set only. Do **not** re-run the
implementation gate set on a spike PR: a spike carries no behavior-demonstrating
proof artifact, so the proof-re-execution and files-in-scope gates do not apply
— the doc write under `docs/spikes/` is itself the File-type proof (see the
imported proof-artifacts fragment). The spike gates are Blocker-only: a missing
Conclusion is a Blocker; missing Action items on a `disproved` or `partial`
conclusion is a Blocker; a real credential in the diff stays a Blocker.

For the implementation gate **proof artifacts re-executed and passing**, apply
this refinement, which **supersedes** the imported validation-gates fragment's
shorter "a proof artifact that … cannot be re-executed … is a Blocker"
phrasing wherever the two appear to differ: distinguish a genuine re-execution
failure from an infrastructure limit before assigning a severity. A proof
artifact that **runs and fails** is a Blocker. A proof artifact that **cannot
be executed because of an infrastructure limit** — this agent runs inside the
firewalled gh-aw container with no toolchain for the consumer's language and no
egress to its package registry, so a command such as `cargo test` fails on a
registry 403/CONNECT-tunnel error before exercising the change — is **not** a
proof-artifact failure and must not trigger `needs-human` on that basis alone.
When a required status check on the consumer repository runs the same command,
record the gate as **deferred to consumer CI** and file an Info finding (no
hand-off, the cascade proceeds); only when no consumer gate covers the proof is
the unverified proof a Blocker. Identify the covering check from the check runs
and commit statuses on the pull request head SHA (readable with
`pull-requests: read`), corroborating against the base branch's
`required_status_checks` contexts only when that branch-protection read is
available. A `needs-human` for the firewall limit alone stalls the auto-merge
cascade even though the consumer's own CI is running the identical tests;
reserve `needs-human` for a genuine validation failure or a proof no gate
covers.

### 4. Post the findings as a single comment

Post exactly one comment, via the `add-comment` safe-output, on the triggering
item: the pull request for a pull request trigger (the spec, architecture, or
implementation boundary), or the tracking issue for the triage boundary. On the
**spike boundary**, step 7 is the sole authority for comment placement and
content — do not post here; that step posts the one permitted comment (and folds
in the Action-items pointer) on the issue it selects. The comment lists every
finding with:

- A severity: **Blocker**, **Warning**, or **Info**, per the imported
  validation-gates fragment.
- `file:line` evidence per the imported evidence-rigor standard: a file path
  and line number, a command and its output, or a direct quote.
- The gate that produced the finding and the boundary that selected it.

A re-run posts a fresh findings comment and the `hide-older-comments` option
minimizes the agent's earlier findings comments, so a single current findings
comment is what a reader sees. Do not post a second comment in one run.

When the gate set produces no finding, post a short comment stating that the
boundary passed clean and naming the boundary and the gate set applied.

### 5. Escalate a Blocker, never fail the run

When any gate produced a Blocker finding, apply the `needs-human` label via the
`add-labels` safe-output to the triggering item — the pull request for a spec,
architecture, or implementation boundary; the tracking issue for the triage
boundary — and make sure the findings comment names the failed gate and its
citing evidence. This is the `needs-human` hand-off from the imported
interaction contract and ADR 0001. On the **spike boundary**, do not apply the
hand-off here: step 7 is the sole authority for label placement and already
parks the **tracking issue** at `needs-human` on a `disproved` or `partial`
conclusion (including when a completeness Blocker fired), so labelling here as
well would mistarget `needs-human` to the pull request and collide with step 7's
single permitted `add-labels`.

A proof artifact recorded as **deferred to consumer CI** is an Info finding,
not a Blocker: it does not apply `needs-human` and does not stall the cascade.
Apply `needs-human` only for a genuine validation failure (a proof artifact
that ran and failed, or any other Blocker) or for a proof artifact blocked by
an infrastructure limit that **no** consumer required status check covers — in
the latter case the proof is verified by no gate and a human must close the
gap. Do not apply `needs-human` for an infrastructure limit that a consumer
required check already covers.

A Blocker on a pull request is resumed when the human clears `needs-human` and
pushes a fix commit: the `pull_request: synchronize` event re-runs this agent
against the corrected diff. A Blocker at the triage boundary is advisory — this
agent gates neither a merge nor `/approve` — so it triggers no agent re-run;
the human acts on the findings and proceeds.

Do not fail the workflow on a Blocker finding and do not declare a required
status check. The run exits successfully regardless of severity. Warning and
Info findings are posted in the comment only and trigger no hand-off.

Apply the hand-off once: when the triggering item already carries
`needs-human`, the off-limits check in the "Triggers this agent handles"
section has already stopped the run with `noop`.

### 6. Advance the lifecycle on a clean implementation pass

When the boundary is the implementation boundary and the gate set produced no
Blocker finding, the implementation has passed validation. Move the **feature
tracking issue** to the next lifecycle state, but only on a full-path feature:

- Remove the `sdd:in-progress` label from the feature tracking issue
  (`remove-labels`).
- Add the `sdd:review` label to the feature tracking issue (`add-labels`).

Skip this lifecycle move entirely on a fast-path feature. A feature is
fast-path when the linked tracking issue carries `sdd:fastpath` or
`sdd:fastpath-review`, or shows fast-path history (no sub-issue tree under
it). Per ADR 0012 the fast-path lifecycle is
`sdd:fastpath → sdd:fastpath-review → sdd:fastpath → sdd:in-progress →
sdd:done`; the human-review gate is the implementation pull request itself,
which the human merges, and `sdd-execute` is the declared writer of
`sdd:done` (it moves the feature on the implementation PR merge). This
agent's clean pass on a fast-path implementation PR therefore posts the
findings comment and stops short of any lifecycle move, leaving the
`sdd:in-progress → sdd:done` transition to `sdd-execute`.

The lifecycle label lives on the feature tracking issue, never on a task
sub-issue. For a pull request trigger the pull request's `Closes #N` reference
is **not** the feature: an implementation pull request closes its own task
sub-issue, so `Closes #N` names that task (ADR 0005 point 3). To reach the
feature, resolve it from that task by walking the GitHub sub-issue parent links
task → its parent Unit sub-issue → the Unit's parent feature, and move the
label on that feature.

Make the move idempotent. A feature with more than one task may already have
been advanced to `sdd:review` by an earlier task's clean pass — `sdd-execute`
moved the feature to `sdd:in-progress` when the first of its tasks was picked
up, and the first task to validate clean carries it to `sdd:review`. Move the
feature **only** when it still carries `sdd:in-progress`; if it already carries
`sdd:review` (or any later state), change nothing. This still moves exactly one
issue's labels per run — the feature — never the task sub-issue.

Move the label only at the implementation boundary, only on a full-path
feature, and only on a clean pass: a spec, architecture, or triage pass does
not move a lifecycle label; an implementation pass with a Blocker finding hands
off via `needs-human` instead; and an implementation pass on a fast-path
feature posts findings only (the `sdd:in-progress → sdd:done` move is
`sdd-execute`'s responsibility on PR merge). Exactly one lifecycle label is
present at a time, so the removal and the addition are a single move. When the
human pushes a fix for an earlier Blocker and the `pull_request: synchronize`
re-validation passes clean against a full-path feature, this same step
advances the feature from `sdd:in-progress` to `sdd:review`.

### 7. Resolve the lifecycle on a spike boundary

When the boundary is the spike boundary, the outcome is read from the spike
doc's Conclusion and the spike gate set, and the lifecycle move is on the
**spike sub-issue** or the **tracking issue**, never the implementation
feature flow.

On the spike boundary this step is the **sole authority** for both the comment
and the label: steps 4 and 5 defer here and post nothing and label nothing, so
exactly one `add-comment` and at most one `add-labels` are emitted, staying
within the `max: 1` budget. The single permitted comment is the findings comment
described below, and the single permitted label move is this step's.

Resolve the two issue numbers first. The spike PR body carries
`Closes #<spike-issue>`, which names the spike sub-issue. Walk the GitHub
sub-issue parent link from the spike sub-issue to its parent to reach the
**tracking issue** (the architecture-ledger entry that queued the spike). Both
moves below target one of these two issues by `item_number`, not the PR.

- **Proved.** When the Conclusion is `proved` and no spike gate produced a
  Blocker, the experiment resolved its assumption. Apply the
  `sdd:spike-resolved` label (`add-labels`) to the **spike sub-issue**
  (`item_number` = the spike sub-issue number). This mirrors `sdd:dispatched`:
  one marker on the sub-issue, no tracking-issue move. Post the single permitted
  findings comment (the comment step 4 deferred here) on the **pull request**,
  naming the resolved spike boundary and the clean spike gate set.
- **Disproved or partial.** When the Conclusion is `disproved` or `partial`,
  the assumption did not hold (or held only in part) and a human must decide
  how the plan adapts. Park the **tracking issue**: apply the `needs-human`
  label (`add-labels`) to the tracking issue (`item_number` = the tracking
  issue number) and post the single permitted `add-comment` on the tracking
  issue. Fold the Action-items pointer into that one findings comment — it is
  the same comment step 4 deferred here, now carrying both the spike findings
  (with the Blocker evidence, if any) and a pointer at the spike doc's Action
  items; do not emit a second comment. Do **not** auto-replan and do **not** set
  `sdd:spike-resolved`. A `disproved` or `partial` conclusion **always** parks
  the tracking issue, even when a completeness Blocker (missing Action items)
  also fired on the same run — otherwise phase C wedges forever on a
  disproven-but-untidy doc that can never reach `sdd:spike-resolved`.
- **Any other Blocker.** When a spike gate produces a Blocker outside the clean
  `proved` path — a missing Conclusion (gate 1), or a `proved` Conclusion that
  still carries a credential-in-diff Blocker — do **not** set
  `sdd:spike-resolved`. Park the **tracking issue**: apply the `needs-human`
  label (`add-labels`, `item_number` = the tracking issue) and post the single
  permitted findings comment on the tracking issue, folding in the Blocker
  evidence. This is the same one-comment, one-label budget as the
  disproved/partial path.

`sdd:spike-resolved` is a marker on the spike sub-issue, orthogonal to the
tracking-issue lifecycle; it pairs with no `remove-labels`. A run resolves to exactly
one of these branches, so exactly one label move happens — either
`sdd:spike-resolved` on the spike sub-issue (clean `proved`) or `needs-human`
on the tracking issue (`disproved`/`partial`, or any other Blocker). As with every boundary, the run exits successfully
regardless of the Conclusion; a Blocker hands off via `needs-human` and never
fails the workflow.

## Boundaries

- This agent never edits `.github/`, `decisions/`, `templates/.github/`, or
  secrets. It writes only a comment and label moves through safe-outputs.
- This agent never opens a pull request and never creates an issue.
- On a spike boundary this agent moves a label on the spike sub-issue
  (`sdd:spike-resolved`) or on the tracking issue (`needs-human`) through
  safe-outputs; it never edits the spike doc and never auto-replans a
  disproved or partial spike.
- This agent never merges or approves a pull request. Merge authority stays
  with humans and the consumer repository's CI.
- This agent never removes the `needs-human` label. Only a human clears it.
- This agent is not a required status check and never fails the workflow on a
  finding. All writes go through safe-outputs; the workflow permissions stay
  read-only.

## Verification

- `gh aw compile` compiles this workflow with the four imported shared
  fragments declared, and reports zero errors.
- The compiled workflow shows no required status-check declaration and exits 0
  even when a Blocker finding is reported.
- A pull request adding a `docs/specs/**` file with an untestable acceptance
  criterion yields one comment carrying a Blocker finding and the
  `needs-human` label, and the workflow run still concludes successfully.
- A clean implementation-boundary pass on a full-path feature moves the feature
  tracking issue from `sdd:in-progress` to `sdd:review`. On a fast-path
  feature (linked tracking issue carrying `sdd:fastpath` or
  `sdd:fastpath-review`, or with fast-path history) the same clean pass posts
  the findings comment but does not move the lifecycle; `sdd-execute` is the
  declared writer of `sdd:done` and performs the
  `sdd:in-progress → sdd:done` move on the implementation PR merge (ADR 0012).
- A Blocker on a pull request is re-validated when the human clears
  `needs-human` and pushes a fix: the `pull_request: synchronize` event re-runs
  the gate set. The wrapper subscribes to no `unlabeled` event, so clearing
  `needs-human` on its own re-triggers nothing.
- A spike pull request (a `docs/spikes/**` change on an `sdd/` branch) resolves
  to the spike boundary and is checked against the spike gate set only. A
  `proved` spike with no Blocker gains `sdd:spike-resolved` on the spike
  sub-issue; a `disproved` or `partial` spike parks the tracking issue at
  `needs-human` with one pointer comment, even when a missing-Action-items
  Blocker also fired. The implementation gate set does not run on a spike PR,
  so its empty-PR proof rule files no false Blocker on the doc-only diff.
