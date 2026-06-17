---
id: adr-0028
title: Triage collapses a single-task Unit to a feature-parented task
kind: adr
status: accepted
supersedes:
superseded-by:
---

# ADR 0028: Triage collapses a single-task Unit to a feature-parented task

- Status: Accepted
- Date: 2026-06-16

## Context

`sdd-triage` phase C materializes a feature's task graph as a tree of linked
sub-issues: the tracking issue gets a spec sub-issue, an architecture
sub-issue, and one **Unit sub-issue per demoable unit**, and each task sub-issue
nests under its Unit (ADR 0005). The Unit sub-issue is a pure grouping
container — it carries no `## Task` body block, no `repo:` field, and no
`blocked by` edges; only its task children execute.

A feature's sub-issue count is `2 + N + M` for N demoable units and M tasks
(issue #272). ADR 0026 attacked N by sizing demoable units to a reviewable
floor in `sdd-spec`, and retuned the `sdd-triage` task floor (ADR 0022) to
match. But a Unit that ends up holding **exactly one** task still costs a
sub-issue with no execution purpose: it groups nothing. In practice Units are
near 1:1 with tasks, so the grouping layer is mostly overhead. ADR 0026 named
this the complementary structural change and deferred it because it touches the
Feature → Unit → task tree-walkers (issue #272, Lever 2).

## Decision

1. **`sdd-triage` phase C collapses a single-task Unit.** When a Unit in the
   approved plan would hold exactly one task, phase C emits **no** Unit
   `create-issue` for it and parents that one task **directly to the tracking
   issue**, so the tree nests Feature → task with no intervening Unit. A Unit
   sub-issue is created only when it groups **≥2** tasks. The task is otherwise
   unchanged — same title, `## Task` body block, `model:*` tier, and born-ready
   `sdd:ready` rule — only its `parent` differs.
2. **The plan-comment preview reflects the same collapse.** Phase B (step 5)
   marks a single-task unit as collapsing, so the human approves exactly the
   tree phase C builds: a single-task group reads as a feature-parented task, a
   multi-task group reads as a Unit. Phase C materializes exactly the previewed
   plan (ADR 0010).
3. **The tree-walkers admit a feature-parented task.** A task is distinguished
   from a Unit, spec, or architecture sub-issue at the feature level by carrying
   the `## Task` block (deterministically: exactly one `model:*` tier label,
   which only tasks carry). Three walkers learn the Feature → task shape
   alongside Feature → Unit → task:
   - `sdd-execute-{haiku,sonnet,opus}` step 8 completion sweep — a
     feature-parented task is a leaf with no Unit to close; the feature-complete
     check now requires every feature-parented task closed too.
   - `.github/actions/sdd-cycle-detect/action.yml` — the deterministic DAG walk
     takes a feature-level task directly instead of descending for it.
   - `sdd-validate` gate 1 in `shared/sdd-gates.md` — enumerates feature-parented
     tasks as well as Unit-nested ones.

   The `.github/actions/sdd-dispatch-compute/action.yml` ready-set walk is
   updated for the same reason: a feature-parented task must enter the dispatch
   matrix, and must never be nominated for Unit closure.

## Reasoning

- The Unit's only job is grouping; a group of one is the identity. Removing it
  costs nothing structurally and removes one sub-issue per single-task unit —
  the largest count drop available (issue #272, Lever 2).
- A `model:*` tier label is already the disambiguator the dispatch ready-set
  loop uses to route a task to its `sdd-execute-{tier}` variant. Reusing it as
  the "is this direct child a task?" test keeps the walkers single-sourced and
  needs no new label or body convention.
- Parenting agnosticism already exists where it matters: `sdd-triage-dedupe-tasks`
  resolves a task's direct parent (whatever it is) and dedupes among that
  parent's children, so a feature-parented task is deduped against the tracking
  issue's children exactly as a Unit-nested task is deduped against its Unit's.
- Collapse is per-unit: a feature may mix collapsed feature-parented tasks and
  multi-task Unit sub-issues in one tree, so the change never forces a feature
  into one shape.

## Verification

- `sdd-triage.md` phase B (step 5) previews the collapse; phase C (step 6)
  parents a single-task Unit's task to the tracking issue and creates a Unit
  sub-issue only for a multi-task unit.
- `sdd-execute-{haiku,sonnet,opus}.md` step 8 treats a feature-parented task as
  a leaf with no Unit to close and requires it closed for feature completion.
- `sdd-cycle-detect` and `sdd-dispatch-compute` admit a feature-parented task to
  the task set; `sdd-dispatch-compute` never nominates it for Unit closure.
- `shared/sdd-gates.md` gate 1 enumerates feature-parented tasks; the requirement
  coverage gate sees them.
- A feature whose plan groups a single task per unit materializes as Feature →
  task with no Unit sub-issue, and the completion sweep, cycle-detect, dispatch,
  and validate gates all pass on that shape.

## Consequences

- A feature's sub-issue count drops by one per single-task unit; a feature of
  all single-task units carries no Unit sub-issues at all.
- The tree is no longer uniformly two levels deep below the feature: a leaf task
  may be a direct child of the tracking issue or a grandchild via a Unit. Every
  deterministic tree-walk and the validate/gates prose now branch on the
  `## Task`/`model:*` task test at the feature level.
- The fastpath single-PR collapse (ADR 0012) is untouched; this is a
  within-tree collapse of the grouping layer, not a tree-vs-no-tree decision.

## Cross-links

- ADR 0026 — demoable-unit sizing: shrinks N at the spec layer and names this
  collapse as the complementary structural change (issue #272, Levers 1 and 3).
- ADR 0022 — triage task bundling: the intra-Unit task floor whose grain this
  grouping collapse complements.
- ADR 0010 — plan-comment-before-tree: the rule that phase C materializes exactly
  the previewed plan, which the collapsed preview upholds.
- ADR 0008 — phase-C task dedupe: the parent-agnostic dedupe backstop that already
  covers a feature-parented task.
- ADR 0005 — sub-issue lifecycle model: the Feature → Unit → task tree this
  selectively flattens to Feature → task.
- Issue #272 — the over-decomposition report this answers (Lever 2).
