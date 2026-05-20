# ADR 0010: Plan comment before tree

- Status: Accepted
- Date: 2026-05-20

## Context

`sdd-triage` runs three phases gated by GitHub events: phase A designs the
architecture, phase B turns the merged architecture into something the human
approves, and phase C decomposes that into the task graph `sdd-execute` picks
up. The phase boundary at `/approve` is where the human signs off on the
plan.

Until this ADR, phase B created the Unit sub-issues on the merge of the
architecture pull request, and phase C — on `/approve` — created the
implementation task sub-issues under those Units. The result: the human was
asked to approve a plan **after** the issue tree had already been populated
with Units. A `/revise` between merge and `/approve` had to delete or rewrite
the Unit sub-issues the agent had already created, and the failure mode for a
cycle or an unmapped requirement detected in phase C was "partial tree, needs
cleanup," because the Units had committed in phase B.

The artifact tree was committing before the human signed off on it. That is
the wrong gate semantics: `/approve` should be the single point at which the
plan turns into structure. Until it is given, the plan is a proposal — a
comment, not a tree.

## Decision

1. **Phase B posts the proposed plan as one comment on the tracking issue.**
   The comment lists the demoable units in dependency order, and under each
   Unit gives a **full preview** of every sub-task `/approve` would create:
   title, `files in scope:`, 1 to 3 proof artifacts, `depends on:` edges, and
   `model:*` tier. The comment opens with the sentinel
   `<!-- sdd-triage:plan -->` so subsequent runs can locate it. Phase B
   creates **no** sub-issues.

2. **Phase C, on `/approve`, materializes the plan as the Unit and task
   sub-issue tree.** It creates the Unit sub-issues parented to the tracking
   issue and the task sub-issues parented to their Units, in one phase,
   keeping the Feature → Unit → task nesting of ADR 0005. Unblocked tasks
   carry `sdd:ready` at creation (ADR 0009). The tracking issue moves from
   `sdd:triage` to `sdd:ready`.

3. **The cycle check and the spec-requirement-coverage check run before any
   `create-issue` is emitted in phase C.** A cycle or an unmapped requirement
   produces a `needs-human` hand-off comment and zero `create-issue`
   safe-outputs; the tree is never partially created. The failure mode is
   "plan rejected, no tree created," not "partial tree, needs cleanup."

4. **`/approve` materializes exactly what the plan comment shows.** A
   sub-task that appears in phase C but not in the latest plan comment, or
   that diverges from its preview (title, scope, proof artifacts,
   dependencies, model tier), is a correctness bug.

5. **`/revise` between architecture-merge and `/approve` re-runs phase B.**
   The agent composes the revised plan, posts it as a new `add-comment`
   carrying the same sentinel, and hides every prior plan comment as
   `OUTDATED` so the latest plan is the only active one. No sub-issues exist
   yet; there is nothing else to reconcile.

6. **`/revise` after `/approve`, with no task in flight, re-runs phase B and
   reconciles the tree.** The active plan comment is replaced and the tree
   is reconciled against the revised plan:
   - A Unit or sub-task that is **not** in the revised plan and is **still
     open** is closed via `close-issue` with `state-reason: not_planned`. An
     already-closed Unit or sub-task is left alone.
   - A Unit or sub-task that is in the revised plan and **does not yet
     exist** is created via `create-issue` with `parent` set per the Feature
     → Unit → task rule.
   - A Unit or sub-task that exists and is in the revised plan, unchanged in
     scope, is left alone.
   Reconciliation must be idempotent: a re-run with no plan diff emits no
   tree safe-outputs. The cycle and coverage gates re-run before any
   reconciliation safe-output is emitted; a failure means no reconciliation
   runs and the agent hands off via `needs-human`.

7. **`/revise` after `/approve`, with any task in flight, is refused.** Any
   open task sub-issue under the tracking issue that carries
   `sdd:in-progress`, or any task sub-issue that has an open linked
   implementation pull request, is "in flight." On a tracking-issue
   `/revise` while any task is in flight, the agent posts **one** comment
   naming the in-flight task and pointing the human at the per-PR `/revise`
   loop on the implementation pull request, and emits `noop`. The plan
   comment is not edited; the tree is not changed; `needs-human` is not
   applied (the refusal is not a hand-off — the human's `/revise` was simply
   mistimed).

The hide-on-`/revise` mechanic is the closest the gh-aw safe-output set
gets to a literal in-place edit: `add-comment` posts a new comment and
`hide-comment` collapses the prior one as `OUTDATED`, so a reader sees one
active plan and GitHub's own edit log on each comment preserves the per-run
history. There is no `update-comment` safe-output in gh-aw at the time of
this ADR; when one exists, the plan comment can become a literal edit
without changing the gate semantics in clauses 1 to 7.

## Reasoning

- **Reversibility.** A proposal in a comment is cheap to revise: each
  `/revise` re-runs phase B, posts the new plan, and hides the old. A
  proposal already committed as a Unit sub-issue is expensive to revise: the
  agent has to undo writes it already made. Keeping the proposal in a comment
  until `/approve` aligns the cost of revision with the human's gate.
- **Atomicity of the gate.** `/approve` is now the **only** point at which
  the tree commits. The cycle and coverage checks run before any
  `create-issue` is emitted, so the failure mode is "plan rejected, no tree
  created" rather than "partial tree, needs cleanup." That matches what the
  human expects when they approve a plan — they approve or they don't, and
  nothing in between gets created.
- **The full preview is the contract.** A plan comment that lists only Unit
  groupings would still leave the sub-task decomposition opaque until phase
  C creates the sub-issues; the human would then have to revise on a tree.
  Listing every sub-task `/approve` would create — title, scope, proof
  artifacts, dependencies, model tier — means the human approves the actual
  decomposition, not just the unit grouping. The comment is long; that is
  the point.
- **Reconciliation, not regeneration.** After `/approve`, a `/revise` does
  not blow up the existing tree and rebuild it. Items that intersect between
  the old and new plan are left alone, so a task that has already moved to
  `sdd:in-progress` (and would block the `/revise` anyway under clause 7) is
  never accidentally closed. The set-difference reconciliation makes
  re-running idempotent.
- **In-flight refusal.** A `/revise` that would close a sub-issue with work
  already in flight is the case where the per-PR `/revise` loop on the
  implementation pull request is the right tool. Refusing at the tracking
  issue points the human at that tool rather than tearing down work the
  human did not ask to tear down. The refusal is not a `needs-human`
  hand-off because the agent has not given up — the human can wait for the
  in-flight task to land, or use `/revise` on the implementation pull
  request, and then re-issue the tracking-issue `/revise`.
- **Cross-links.** This ADR layers on top of ADR 0005 (the Feature → Unit →
  task tree) and ADR 0009 (`sdd:ready` set at creation): the tree shape and
  the label-at-creation rule are unchanged. Only the **phase** at which the
  Unit nodes are created moves — from phase B to phase C.

## Verification

- Merging an architecture pull request produces **zero** new sub-issues and
  **one** plan comment on the tracking issue. The comment carries the
  `<!-- sdd-triage:plan -->` sentinel and lists each Unit in dependency
  order with its full sub-task preview.
- `/revise <note>` on the tracking issue between architecture-merge and
  `/approve` posts a new plan comment and hides the prior plan comment as
  `OUTDATED`. No sub-issues are created.
- `/approve` from a write-access author creates Unit sub-issues parented to
  the tracking issue and task sub-issues parented to their Units, in one
  phase. Each sub-task matches its plan-comment preview. The tracking issue
  moves from `sdd:triage` to `sdd:ready`.
- A cycle in the proposed dependency graph or an unmapped requirement
  detected at phase C produces a `needs-human` comment and zero
  `create-issue` safe-outputs.
- `/revise <note>` after `/approve`, with no task in `sdd:in-progress` and
  no open implementation pull request linked to a task sub-issue, posts a
  new plan comment, hides the prior plan comment as `OUTDATED`, closes
  Units and tasks dropped from the revised plan with
  `state-reason: not_planned`, creates Units and tasks added by the revised
  plan, and leaves intersecting items alone. A second `/revise` run with
  the same note emits no tree safe-outputs (idempotent).
- `/revise <note>` after `/approve`, with at least one task carrying
  `sdd:in-progress` or with at least one open implementation pull request
  linked to a task sub-issue, produces one refusal comment naming the
  in-flight task. The plan comment is not edited; the tree is not changed.

## Consequences

- `sdd-triage` declares two additional safe-outputs: `hide-comment`
  (capped at 30 per run) to collapse prior plan comments as `OUTDATED`,
  and `close-issue` with `target: '*'` (capped at 30 per run) to close
  Units and tasks dropped by a post-approve `/revise`. `add-comment`
  stays at `max: 1`; `create-issue`'s cap rises from 20 to 30 to cover
  Unit creations alongside sub-tasks in one phase-C run. The
  `hide-comment` cap matches the tree-level cap so repeated `/revise`
  flows never leave a stale active plan comment.
- ADR 0005's lifecycle model is unchanged. Unit and task sub-issues still
  close on the merge of their pull request or on `sdd-execute`'s
  completion sweep; this ADR's `close-issue` path is reserved for the
  reconciliation case in clause 6.
- The pre-existing rule "the agent never closes a sub-issue" is loosened
  to "the agent only closes a Unit or task sub-issue when reconciliation
  drops it from the revised plan, with `state-reason: not_planned`." No
  other path closes a sub-issue from `sdd-triage`.
- The phase-B summary comment that previously linked the just-created Unit
  sub-issues is removed: phase B's only output is the plan comment.
- `sdd-validate`'s triage-boundary check (which currently walks Feature →
  Unit → task) continues to work unchanged on the post-`/approve` tree.
  Between architecture-merge and `/approve` the tree is empty by design and
  `sdd-validate` has nothing to walk, which is the correct state for that
  window.
- The phase-C task de-duplicator (ADR 0008) continues to apply. A
  duplicate `create-issue` under the same Unit in the materialization step
  is still closed deterministically by `sdd-triage-dedupe-tasks`.
- The hide-on-revise mechanic substitutes for a literal in-place edit
  because gh-aw has no `update-comment` safe-output today. If one is added
  later, the agent can switch to editing the existing plan comment in place
  without changing any of the gate semantics in clauses 1 to 7.
