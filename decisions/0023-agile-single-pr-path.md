---
id: adr-0023
title: Agile single-PR path generalizes the fast path
kind: adr
status: accepted
supersedes:
superseded-by:
---

# ADR 0023: Agile single-PR path generalizes the fast path

- Status: Accepted (amends ADR 0012)
- Date: 2026-06-12

## Context

ADR 0012's fast path compresses spec, architecture, and plan into one
agent run, but its classifier admits only trivial work: six heuristics
including a 1–2-file scope cap and a flat ban on new public API surface.
Field feedback from a consumer pilot run showed the gap that leaves: a
small-to-medium feature an operator would ship as one PR took ~2 days
across 4 human gates (merge spec PR, merge architecture PR, `/approve`,
`/dispatch`), produced 6 task sub-issues, and the operator abandoned the
pipeline midway — closing green task PRs and consolidating by hand —
because one task PR shipped a primitive with no consumer wired up
("dead code").

Two distinct costs compound there: ceremony (four gates and two
artifact PRs for work that needs one) and fragmentation (a task tree
that ships primitives apart from their consumers). ADR 0022 addressed
fragmentation *within* a tree by bundling cohesive small tasks; this
ADR addresses the ceremony by letting a whole small-to-medium feature
skip the tree entirely (issue
[#255](https://github.com/norrietaylor/spectacles/issues/255)).

## Decision

1. **Widen the classifier; keep it binary.** `sdd-spec` proposes the
   single-PR path when ALL hold: estimated net diff ≤ `SDD_AGILE_MAX`
   (a new optional repository variable, default `800`, plumbed as an
   `agile_max` workflow_call input on the spec lock per the ADR 0022
   `min_task` pattern — gh-aw rejects new `${{ vars.* }}` references in
   prompt prose); no new external dependency; no schema/data-format
   migration; no cross-cutting boundary change; and no decision
   meriting an ADR — the last is a **hard veto** (a light spec's Design
   notes may carry local reasoning, never an ADR-worthy decision).
   Explicitly relaxed from ADR 0012: the 1–2-file scope cap (soft
   guidance ~10 files) and **new public API surface** — safe because
   the consumer of any new surface ships in the same PR, which makes
   the dead-code failure mode structurally impossible. There is no
   third tier: the decision stays single-PR vs full path, so every
   existing `sdd:fastpath` carve-out (triage skip, dispatch noop,
   validate/review relaxations, doc-status, execute entry, completion
   sweep) is reused as-is.

2. **Spec depth scales: stub → light spec.** The six ADR 0012
   heuristics survive only as the agent's internal signal for spec
   depth. All six pass → the ADR 0012 stub. Single-PR fits but any of
   the six fails → a **light spec**: multiple demoable units, full
   `R{unit}.{seq}` requirement IDs, 1–3 proof artifacts per unit, an
   optional "Design notes" section in lieu of `architecture.md`, and
   the same `tracking-issue: N` frontmatter. The spec stays a file in
   a PR; spec-as-comment is rejected because it breaks `sdd-validate`'s
   spec gates, `sdd-review`'s R-ID resolution, ADR 0021 doc-status
   (which greps `docs/specs/**`), distillery-sync mirroring, and the
   post-merge `/revise` amendment path.

3. **One `/approve`, commutative with the merge.** While the spec PR is
   open (`sdd:fastpath-review`), `/approve` on the tracking issue
   records approval via the orthogonal **`sdd:approved`** marker label
   and — when `SDD_AUTO_MERGE` is set — arms squash auto-merge on the
   spec PR. The spec PR's merge event then deterministically dispatches
   the single `sdd-execute-{tier}` run against the execution plan
   comment, removes `sdd:approved`, and advances the lifecycle to
   `sdd:in-progress` (`sdd:fastpath-review → sdd:in-progress`, skipping
   the return hop to `sdd:fastpath`). `/approve` after the merge
   dispatches directly, exactly as ADR 0012 §5. Merge/approve ordering
   is therefore commutative; the former ordering-refusal branch in
   `sdd-fastpath-approve` is replaced by the recording branch.
   Staleness: a `/revise` after approval clears `sdd:approved`
   (re-approval required), and a spec PR closed unmerged clears it.

4. **`/agile` is an alias of `/fastpath`.** Routed identically
   (`sdd-route-spec` collapses it to `command: 'fastpath'`); both stay
   valid. Labels keep the `sdd:fastpath*` names — no consumer label
   churn; an eventual rename to `sdd:single-pr*` is deferred.

5. **Misclassification valve unchanged** (ADR 0012 §8). `sdd-execute`'s
   fast-path entry re-checks the widened criteria against the approved
   plan (files-in-scope explosion, discovered schema change, needed
   dependency, ADR-worthy decision) → `needs-human`; `/spec` bounces to
   the full path with the existing spec as the starting point. Never
   silently split into multiple PRs — escalate instead.

6. **Full path unchanged**, except the opt-in `SDD_AUTO_DISPATCH`
   companion (ADR 0024).

## Reasoning

- **Binary, not ternary.** ADR 0012 already rejected a medium tier; a
  wider binary boundary preserves that simplicity while moving the line
  to where the artifacts earn their cost. Every fast-path carve-out is
  reused verbatim, so the change concentrates in the classifier, the
  spec depth, and the approve mechanics.
- **Same-PR consumer is the safety argument.** The dead-code failure
  mode that motivated the "no new public API" heuristic only exists
  when a primitive can merge apart from its consumer. One PR for the
  whole feature removes that decoupling, so the heuristic can relax
  without reopening the failure.
- **A marker, not a state.** `sdd:approved` mirrors `sdd:dispatched`
  and `plan:provided`: it records an orthogonal fact (a human approved)
  without disturbing the one-lifecycle-label invariant, and it makes
  the merge event self-sufficient — the dispatch needs no comment
  archaeology to know the human said go.
- **Ceiling defaults to 800.** A consumer pilot feature of ~800 net
  lines is the observed shape of the abandonment case; 800 errs toward
  ceremony reduction while validate, review, CodeRabbit, and per-unit
  proof artifacts still gate the single PR. The value is per-consumer
  (`SDD_AGILE_MAX`) and documented alongside `SDD_TRIAGE_MIN_TASK`
  (300) as one sizing story; tune down if single-session execution
  failures erode trust.

## Verification

- `sdd-spec.md` step 3a states the five single-PR criteria, resolves
  the ceiling from `${{ inputs.agile_max }}` (blank → 800), names the
  ADR-worthy-decision hard veto, and keeps the six old heuristics as
  the stub-vs-light depth signal; the `sdd-spec` wrapper maps
  `vars.SDD_AGILE_MAX` into that input.
- `sdd-spec.md` step 7a authors either depth; the light spec carries
  multiple units, full R-IDs, 1–3 proof artifacts per unit, and an
  optional Design-notes section; the plan comment lists every R-ID as
  one task.
- `/approve` while the spec PR is open records `sdd:approved` and arms
  squash auto-merge; the merge dispatches `sdd-execute-{tier}`, clears
  the marker, and advances to `sdd:in-progress` — in either order of
  merge and `/approve`.
- `/revise` after approval and a spec PR closed unmerged both clear
  `sdd:approved` without dispatching.
- `/agile` routes identically to `/fastpath`
  (`scripts/test-command-table.py` holds W == T with both commands).
- `templates/.github/labels.yml` defines `sdd:approved`;
  `scripts/lifecycle-states.yml` classifies it as a marker and adds the
  `sdd:fastpath-review → sdd:in-progress` edge
  (`scripts/test-lifecycle-state-machine.py` green).

## Consequences

- One new marker label, `sdd:approved`, joins the catalogue; the
  lifecycle state set is unchanged and the transition graph gains one
  edge (`sdd:fastpath-review → sdd:in-progress`).
- One new optional repository variable, `SDD_AGILE_MAX` (default 800).
- `sdd-fastpath-approve` becomes the three-mode approval handler
  (approve / merged / clear); `wrappers/sdd-spec.yml` gains the
  `approved-merge-dispatch` and `approved-clear` jobs; `sdd-route-spec`
  resolves the approved tracking issue from a closing spec PR.
- `sdd-validate` accepts the light spec at the spec boundary and the
  Design-notes leakage carve-out enters the spec gates; `sdd-review`
  resolves R-IDs from either depth; `sdd-execute`'s step 4a re-checks
  the widened criteria.
- Old wrappers + new locks degrade gracefully: old wrappers pin the
  composite actions `@main` but call `sdd-fastpath-approve` without a
  `mode` input, and the action's default mode is `legacy` — the
  pre-ADR-0023 behavior. `/approve`-in-review then posts the merge-first
  guidance comment and records nothing (so `sdd-route-spec` never
  suppresses the agent on the merge, which advances
  `sdd:fastpath-review → sdd:fastpath` as before, and the post-merge
  `/approve` dispatches). Only the new wrapper, which carries the
  `approved-merge-dispatch` job, passes `mode: approve` explicitly.

## Cross-links

- **ADR 0012** — the fast path this amends: states, carve-outs, the
  stub, and the misclassification valve are all reused.
- **ADR 0022** — task sizing (`SDD_TRIAGE_MIN_TASK`): the intra-tree
  half of the same over-decomposition feedback, and the `min_task`
  input-plumbing pattern `agile_max` copies.
- **ADR 0024** — the `SDD_AUTO_DISPATCH` companion for the full path.
- **ADR 0010 / ADR 0011** — `/approve` gate semantics and the cascade
  the single-PR path bypasses.
- **ADR 0021** — doc-status; one reason the light spec stays a file.
- Issue [#255](https://github.com/norrietaylor/spectacles/issues/255) —
  the consumer pilot feedback this answers.
