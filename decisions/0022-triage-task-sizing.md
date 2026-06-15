---
id: adr-0022
title: Triage bundles cohesive small tasks to a review-sized floor
kind: adr
status: accepted
supersedes:
superseded-by:
---

# ADR 0022: Triage bundles cohesive small tasks to a review-sized floor

- Status: Accepted
- Date: 2026-06-10

> **Amended by [ADR 0026](0026-demoable-unit-sizing.md) (2026-06-15):** the
> default `SDD_TRIAGE_MIN_TASK` floor is raised from 300 to 400 net lines to
> match the new demoable-unit target. The cohesion mechanism in this ADR is
> unchanged.

## Context

`sdd-triage` decomposes a feature into task sub-issues, and each task is a full
agent cascade: one `sdd-execute` run, one pull request, one CI pipeline, one
`sdd-validate` pass, one `sdd-review` pass (up to `SDD_MAX_REVIEW_ITERATIONS`
revise cycles), and one merge. That overhead is fixed per task — it does not
shrink with the diff.

The decomposition prose carried only an **upper** size bound ("sized for a
single agent session per sub-task", `sdd-triage.md` step 5) and a matching
too-large Warning (triage gate 3 in `shared/sdd-gates.md`). It had no lower
bound and no cohesion rule, so a requirement that maps to a 40-line change still
earned its own task and paid the full per-task overhead.

Observed in a real run (issue
[#252](https://github.com/norrietaylor/spectacles/issues/252)): one feature was
split into six tasks whose implementation PRs were 70–98 lines across 2–4 files;
three of them were a single cohesive ~265-line change (a helper, the component
that uses it, and the wiring into one tab — overlapping file sets) fanned across
three PRs, three reviews, and three merges. The ratio of pipeline cost to
delivered diff was poor.

## Decision

1. **Triage sizes a task to a cohesive unit of review, with a lower bound, not
   one task per function or file.** Under a Unit, two previewed sub-tasks are
   folded into one task when either holds — unless a `blocked by` edge to a
   *third* task forces them apart:
   - their `files in scope:` overlap (one a subset of, or sharing a file with,
     the other), or
   - they form a strict produce-then-consume chain with no other consumer.
2. **A configurable estimated-diff floor breaks ties.** A candidate task whose
   pre-implementation estimate is under `SDD_TRIAGE_MIN_TASK` net changed lines
   (default `300`) and that has a cohesive sibling is folded into it.
   `SDD_TRIAGE_MIN_TASK = 0` disables bundling and restores one task per
   requirement. The value reaches the prompt through a `min_task` workflow_call
   input on the triage lock: the `sdd-triage` wrapper maps
   `${{ vars.SDD_TRIAGE_MIN_TASK }}` into it, and the prompt reads
   `${{ inputs.min_task }}`. gh-aw rejects a new `${{ vars.* }}` reference in
   prompt prose (only an allowlisted set of variable names is permitted there),
   so a `workflow_call` input — which gh-aw does allow in the prompt — is the
   channel; an unset variable passes blank and the agent falls back to 300.
3. **The validate gate gains a lower-bound companion.** Triage gate 5 in
   `shared/sdd-gates.md` ("No under-decomposed task") flags a Warning, symmetric
   to gate 3's too-large Warning. It is advisory, never a Blocker.

## Reasoning

- Cohesion (a shared file set or a producer/consumer chain) is the real signal
  that two tasks belong together; the line-count floor is a soft backstop layered
  on it, never an independent trigger, so two unrelated small tasks are never
  merged.
- The floor is the agent's pre-implementation estimate and therefore inexact,
  which is why both the floor and the gate are advisory (Warning), matching the
  existing single-session bound's severity rather than hard-failing a plan.
- Folding two tasks unions their `depends on:` edges to other tasks and dissolves
  any edge between the pair. Removing edges cannot create a cycle, so the
  latent-edge pass and the `sdd-cycle-detect` backstop (ADR 0010) keep the DAG
  sound with no new machinery.
- This is the fastpath instinct (ADR 0012) applied within a tree: fastpath
  collapses a whole single-session feature to one execution plan with no tree;
  bundling collapses cohesive single-session siblings within a tree.
- No deterministic actuator is added. The rule is the agent's job; a backstop
  wrapper (in the shape of `sdd-triage-dedupe-tasks`, ADR 0008) is deferred until
  drift from the prose rule is actually observed.

## Verification

- `sdd-triage.md` step 5 states the cohesion rule, the `min_task` floor
  (`${{ inputs.min_task }}`, blank → 300), and the `0`-disables path; the
  `sdd-triage` wrapper maps `vars.SDD_TRIAGE_MIN_TASK` into that input.
- `shared/sdd-gates.md` triage gate 5 flags an under-decomposed task as a
  Warning and exempts tasks separated by a real `blocked by` edge.
- `docs/sdd/install.md` documents `SDD_TRIAGE_MIN_TASK` (default `300`).
- A feature whose total scope is ~250 lines across a handful of files
  materializes as one or two tasks, not six.

## Consequences

- A new optional repository variable, `SDD_TRIAGE_MIN_TASK`. Unset, triage
  bundles at the 300-line default; consumers that want the old fine granularity
  set it to `0`.
- Triage gate 5 is added to the triage gate set, taking it from four gates to
  five. No change to gate severities elsewhere.

## Cross-links

- ADR 0012 — fastpath: the terminal collapse this generalizes to within-tree
  bundling.
- ADR 0010 — plan-comment-before-tree: phases B/C where the rule is applied, and
  the cycle-detect backstop bundling relies on.
- ADR 0008 — the deterministic dedupe backstop whose shape a future bundling
  actuator would take if the prose rule proves insufficient.
- Issue [#252](https://github.com/norrietaylor/spectacles/issues/252) — the
  over-decomposition report this answers.
