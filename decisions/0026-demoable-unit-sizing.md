---
id: adr-0026
title: Specs size demoable units to a review-sized floor
kind: adr
status: accepted
supersedes:
superseded-by:
---

# ADR 0026: Specs size demoable units to a review-sized floor

- Status: Accepted
- Date: 2026-06-15

## Context

`sdd-spec` breaks a feature into demoable units; `sdd-triage` then creates one
Unit sub-issue per demoable unit and at least one task sub-issue under it, and
each task is a full agent cascade — one `sdd-execute` run, one pull request, one
CI pipeline, one `sdd-validate` pass, one `sdd-review` pass, one merge. A
feature's sub-issue count is therefore `2 + N + M` for N demoable units and M
tasks, and the per-task overhead is fixed: it does not shrink with the diff.

ADR 0022 gave `sdd-triage` a cohesion rule and a `SDD_TRIAGE_MIN_TASK` floor
(default 300) to fold cohesive sibling tasks **within a Unit**. It did nothing
about N. `sdd-spec` carried **no** lower bound on demoable-unit size — step 5
said only "break the work into demoable units, split as the work naturally
falls." The model defaulted to fine-grained units, observed at ~100 net lines
where an engineer's natural pull request is ~500. Small units inflate N
directly and M indirectly (more units, each with its own task), so the tree
over-decomposes one layer above where ADR 0022 acts (issue #272).

## Decision

1. **`sdd-spec` sizes a demoable unit to a reviewable pull request, with a
   lower bound, not to the smallest testable slice.** Step 5 states a ~400
   net-line target and a unit-cohesion rule symmetric to ADR 0022's task rule:
   two prospective units fold into one when their implementation file sets
   overlap, or they form a strict produce-then-consume chain with no other
   consumer — unless a dependency edge to a third unit forces them apart.
2. **A configurable estimated-diff floor breaks ties.** A candidate unit whose
   pre-implementation estimate is under `SDD_SPEC_MIN_UNIT` net changed lines
   (default 400) and that has a cohesive sibling is folded into it.
   `SDD_SPEC_MIN_UNIT = 0` disables bundling and restores the natural split.
   The value reaches the prompt through a `min_unit` workflow_call input on the
   spec lock, exactly as `SDD_TRIAGE_MIN_TASK` reaches `sdd-triage` via
   `min_task` (ADR 0022): the `sdd-spec` wrapper maps
   `${{ vars.SDD_SPEC_MIN_UNIT }}` into it and the prompt reads
   `${{ inputs.min_unit }}`; an unset variable passes blank and the agent falls
   back to 400.
3. **The spec gate gains a lower-bound companion.** Spec gate 5 in
   `shared/sdd-gates.md` ("Demoable unit sized to a reviewable PR") flags an
   under-sized unit as a Warning, symmetric to triage gate 5's under-decomposed
   task. Advisory, never a Blocker.
4. **The task floor is retuned to match.** `SDD_TRIAGE_MIN_TASK`'s default is
   raised from 300 to 400 so the unit grain and the task grain target the same
   review size. This amends ADR 0022's default; its cohesion mechanism is
   unchanged.

## Reasoning

- Cohesion (a shared implementation file set or a producer/consumer chain) is
  the real signal that two units belong together; the line-count floor is a
  soft backstop layered on it, never an independent trigger, so two unrelated
  units are never merged. This is exactly ADR 0022's argument, one level up.
- The floor is the agent's pre-implementation estimate and therefore inexact,
  which is why both the floor and the gate are advisory, matching ADR 0022's
  severities rather than hard-failing a spec.
- Sizing units larger is the highest-leverage reduction available without
  touching the tree-walkers: it shrinks N at the source and, because
  `sdd-triage` decomposes per unit, shrinks M downstream. Collapsing the Unit
  sub-issue itself when it would hold a single task is the complementary
  structural change, deferred because it touches the Feature -> Unit -> task
  walkers in `sdd-execute`, `sdd-cycle-detect`, and `sdd-validate` (issue #272,
  Lever 2).
- Retuning `SDD_TRIAGE_MIN_TASK` to 400 keeps the two floors one sizing story:
  a unit targets ~400 lines and tasks bundle up to the same ~400, so the spec
  and triage layers do not pull against each other.

## Verification

- `sdd-spec.md` step 5 states the ~400-line unit target, the unit-cohesion
  rule, the `min_unit` floor (`${{ inputs.min_unit }}`, blank -> 400), and the
  `0`-disables path; the `sdd-spec` wrapper maps `vars.SDD_SPEC_MIN_UNIT` into
  that input.
- `shared/sdd-gates.md` spec gate 5 flags an under-sized demoable unit as a
  Warning and exempts a unit separated by a real dependency edge.
- `sdd-triage.md` step 5 carries the retuned 400 default; `docs/sdd/install.md`
  documents `SDD_SPEC_MIN_UNIT` (default 400) and the raised
  `SDD_TRIAGE_MIN_TASK` (default 400).
- A feature whose total scope is ~400 lines across a handful of files specifies
  as one demoable unit, not three or four.

## Consequences

- A new optional repository variable, `SDD_SPEC_MIN_UNIT`. Unset, `sdd-spec`
  bundles units at the 400-line default; consumers that want the old
  fine-grained units set it to `0`.
- The spec gate set gains gate 5, taking it from four gates to five.
- `SDD_TRIAGE_MIN_TASK`'s default changes from 300 to 400; consumers who set it
  explicitly are unaffected.
- This addresses N (unit count); M's structural component — the single-task
  Unit grouping sub-issue — is tracked separately (issue #272, Lever 2).

## Cross-links

- ADR 0022 — triage task bundling: the intra-Unit precedent this generalizes to
  the unit grain, and whose default this retunes.
- ADR 0012 — fastpath: the whole-feature collapse both floors descend from.
- ADR 0010 — plan-comment-before-tree: where `sdd-triage` consumes the units.
- Issue #272 — the over-decomposition report this answers (Levers 1 and 3).
