---
id: adr-0031
title: Run evaluation is a deterministic collector plus a rubric-ratified judge, reporting to a roll-up issue
kind: adr
status: proposed
supersedes:
superseded-by:
---

# ADR 0031: Run evaluation is a deterministic collector plus a rubric-ratified judge, reporting to a roll-up issue

- Status: Proposed
- Date: 2026-07-02

## Context

A retroactive evaluation of a completed full-pipeline run on a consumer
repository (spec `docs/specs/03-spec-run-evaluation/`) established that the
suite's failures were overwhelmingly detectable during the run from API state
alone — label timelines, run shapes, diff properties, artifact greps — yet
were detected by a human watching, or not at all. The pipeline reached
`sdd:done` on a feature that was not demoable; recovery, review-loop closure,
and integrity restoration were all manual; the one surface built to fix
operator legibility (ADR 0023) had never run on any consumer because its
default-on predicate (`vars.SDD_STATUS != '0'`) evaluates false when the
variable is unset (GitHub expressions coerce `null` and `'0'` to the same
number). Nothing in the suite aggregates phase latency, dwell, loop counts,
requirement coverage, or cost.

The evaluation capability must therefore be trustworthy (its own signals
cannot lie or die silently), cheap enough to run on every boundary, and
comparable across runs and suite versions.

## Decision

1. **Two parts.** A deterministic collector (`sdd-eval-collect`: thin
   wrapper + composite action, no `engine:`, OTLP-exempt per ADR 0020 §5)
   computes every hard metric; a separate engine-bearing judge
   (`sdd-eval-judge`: gh-aw source + hosted lock + wrapper, full ADR 0020
   burden) scores only what requires inference.
2. **Four trigger tiers** on the collector: `workflow_run` completion of
   `sdd-*` agents; lifecycle label transitions; `sdd:done` feature
   post-mortem; weekly scheduled aggregation. The judge fires at post-mortem
   and on schedule; per-run judging is anomaly-sampled only.
3. **Delivery is a roll-up issue upsert** (sentinel `<!-- sdd-eval -->`,
   history in comments — the weekly-roll-up pattern), plus a versioned
   `eval_snapshot.json` artifact as the machine surface. No committed
   scorecards, no tracking-issue body edits, no lifecycle label writes.
4. **App identity, default-on** — with the enablement predicate written
   unset-safe and lint-asserted (the ADR 0023 surface's coercion failure is
   the motivating incident).
5. **Rubric ratification.** Qualitative scoring runs only under a committed,
   versioned rubric in which every item carries an anchored scale and a
   machine-check class (`deterministic`/`assisted`/`inference`); a rubric
   version takes effect only after an explicit operator ratification recorded
   on the roll-up issue. The judge stamps rubric version, pinned model,
   suite ref, and snapshot schema version into every score.
6. **Budget is anchored to the run being judged**: per-feature judge budget
   defaults to 5% of the feature's own recorded pipeline usage (floor/cap
   via repository variables), seeded from the evaluated run's baseline.
7. **The retro is a workflow**: `/retro-eval <issue>` re-runs the entire
   retroactive analysis (collector backfill + judge post-mortem) for any
   tracking issue; the original retro is its first manual execution.
8. **Eval reports; a separate actor acts.** Any mutation driven by findings
   (labels, issues, nudges, escalation) belongs to the actor agent
   (`docs/specs/04-spec-eval-actor/`), which is opt-in and separately
   trusted.

## Reasoning

- The repo's standing posture — no LLM where API state suffices (ADR 0023) —
  fits the evidence exactly: the motivating retro computed all of its
  headline findings deterministically and needed inference only for R-ID
  semantics, revert intent, and quality judgments.
- Splitting reporter from actor keeps the reporting surface side-effect-free
  and its trust posture minimal (one issue write), mirroring the
  status/monitor split that already exists.
- Ratified, versioned rubrics are what make scores comparable; an unratified
  rubric silently changing between runs would reintroduce the drift the
  judge exists to measure.
- Anchoring the judge budget to the evaluated feature's own cost keeps the
  evaluator strictly cheaper than the thing it evaluates, at any scale.

## Verification

- `wrappers/sdd-eval-collect.yml` exists with no `engine:` and no compiled
  lock; its enablement predicate passes the unset-safe lint.
- `.github/workflows/sdd-eval-judge.md` declares the ADR 0020 block and a
  pinned model; its wrapper maps the OTLP secret.
- A seeded run produces: snapshot artifact validating against its schema,
  scorecard upsert on the roll-up issue, post-mortem comment with all four
  reproducibility stamps.
- `scripts/test-eval-rubric.py` gates rubric changes in `lint.yml`; a judge
  dry-run refuses an unratified rubric version.
- The lifecycle state-machine validator shows no new lifecycle-label
  writers.

## Consequences

- Operators get boundary-time detection of the failure classes the evaluated
  run surfaced (stranding, false signals, integrity tripwires, proof
  weakening, cost anomalies) and a comparable post-mortem per feature.
- The suite gains its first feedback instrument: suite-version regressions
  become visible as scorecard trends.
- Two new wrappers per consumer (collector, judge) plus roll-up issue noise
  bounded to one issue per repository.
- The `sdd:done ≠ demoable` gap becomes measurable; closing it (demoability
  gates, integration-task planning, recovery fixes) remains pipeline work
  tracked outside this ADR.

## Cross-links

- ADR 0020 (observability mandate; §5 exemption), ADR 0023 (deterministic
  status surface — pattern and the coercion lesson), ADR 0019 (App
  identity), ADR 0015 (wrapper logic in composite actions), ADR 0004
  (distribution), ADR 0001 (`needs-human` stays the human hand-off; eval
  never applies it).
- `docs/specs/03-spec-run-evaluation/` (this capability's spec),
  `docs/specs/04-spec-eval-actor/` (the actor).
