---
id: spec-run-evaluation
title: Run evaluation — deterministic collector and rubric-ratified judge for SDD pipeline runs
kind: spec
status: planned
tracking-issue:
supersedes:
---

# 03-spec-run-evaluation

> The repository is public. This file, and everything committed to the repo,
> carries no employer name, no private org slug, no internal repository name,
> no internal URL, no cost figure, and no contributor personal data. The run
> that motivated this spec is referred to only as "the evaluated run."

## Context

A full feature was run through the SDD pipeline on a consumer repository (the
evaluated run: full-pipeline path, suite pinned to v0.3.0, June 2026). The
pipeline reached `sdd:done`; the feature was not user-demoable, and two
human-written remediation PRs followed. A retroactive evaluation reconstructed
the run from its own exhaust and found that every one of its headline failures
was **detectable during the run from API state alone**:

- the tracking issue's status surface had zero successful runs ever (an
  enablement-predicate bug: `vars.X != '0'` is false when the variable is
  unset, because GitHub expressions coerce `null` and `'0'` to the same
  number);
- 17 `needs-human` episodes totalling ~134 h of dwell, 11 of them in the back
  half of the run, every recovery manual (23 human `/execute` comments);
- the automated stranding recovery recovered 0 of 6 escalations;
- review loops re-raised identical findings across passes and across sibling
  PRs, closed only by ~80 human inline dispositions;
- two live silent-revert incidents (a merged spike doc deleted by a green
  agent PR and never restored; a five-way stale-base revert bundle that sat
  warning-only for 13 h), while the dedicated revert guard answered
  INCONCLUSIVE on every invocation;
- proof artifacts declared in the spec were delivered `#[ignore]`-gated,
  env-gated, or behind cargo features no binary compiled — `sdd:done` was
  reachable with no executed end-to-end demonstration.

During the evaluated run, exactly one failure class was caught by automation
the framework owned; everything else was caught by red consumer CI
(post-damage) or a human watching. Nothing in the suite aggregates phase
latency, dwell time, loop counts, cost per feature, or requirement coverage.

This spec adds a **run-evaluation capability**: a deterministic collector
that computes hard metrics from API state at every pipeline boundary, and a
separate engine-bearing judge that scores what requires inference, under a
version-ratified rubric. It also makes the retroactive evaluation itself a
durable, re-runnable workflow so any tracking issue can be evaluated after
the fact with one command.

## Introduction / Overview

Two cooperating components, following the repo's "no LLM where API state
suffices" posture:

1. **`sdd-eval-collect`** — a deterministic utility workflow (thin wrapper +
   composite action, no `engine:`, OTLP-exempt per ADR 0020 §5 — the
   sdd-status/sdd-monitor pattern). It fires on all four trigger tiers,
   computes the metric catalogue from GitHub API state and run artifacts,
   writes a machine-readable snapshot artifact, and upserts a human-readable
   scorecard onto a roll-up issue (history preserved in comments — the
   weekly-roll-up pattern `sdd-derive` already uses).

2. **`sdd-eval-judge`** — an engine-bearing agent (gh-aw source + compiled
   lock + thin wrapper, full ADR 0020 observability burden). It consumes the
   collector's snapshots plus the underlying diffs/threads and scores the
   dimensions that need judgment (spec fidelity of merged diffs, proof
   deliverability, revert suspicion, review-loop convergence quality, ledger
   evidence quality), each score stamped with the pinned model and the
   ratified rubric version.

The **evaluation agent reports; it never acts**. Labels, issues, nudges, and
escalations driven by eval findings belong to a separate actor agent
(`docs/specs/04-spec-eval-actor/`).

## Goals

1. Replace "a human watching" as the primary failure detector: every
   detection-gap-matrix row whose signal is deterministic is computed by the
   collector during the run, not reconstructed weeks later.
2. Make `sdd:done ≠ demoable` visible at the moment it happens: proof-delivery
   and demoability metrics are part of the per-feature post-mortem.
3. Make runs comparable: one metric catalogue, version-stamped rubric,
   pinned judge model, so scores trend across runs and suite versions.
4. Make the retro re-runnable: `/retro-eval <issue>` reproduces the full
   retroactive evaluation for any tracking issue.
5. Keep the deterministic path free: the collector runs with no engine, no
   OTLP block, and negligible latency, like sdd-status.

## User Stories

- As an operator, I want a scorecard that updates at each phase boundary so
  that I see stranding, dwell, loop counts, and cost while I can still act.
- As an operator, I want a post-mortem comment when a feature reaches
  `sdd:done` that tells me which requirement IDs are delivered / partial /
  missing and which declared proofs actually executed, so that "done" is a
  claim I can trust or challenge immediately.
- As a suite maintainer, I want recurrence fingerprints (the same finding or
  failure signature re-appearing after a fix) surfaced automatically, so a
  point fix that needed a guard is caught by the second incident, not the
  third.
- As a suite maintainer, I want cost per feature and per phase trended across
  runs so sizing and prompt changes show up as slope changes.
- As an operator, I want the judge's scores reproducible — same rubric
  version, same pinned model — so a score delta means the run changed, not
  the yardstick.

## Demoable Units of Work

### Unit 1: `sdd-eval-collect` — deterministic collector and scorecard delivery

**Purpose:** Compute the hard-metric catalogue from API state and run
artifacts on every trigger tier; persist a machine-readable snapshot; upsert
the human-readable roll-up. Demoable: label events on a seeded test tracker
produce a scorecard comment and a snapshot artifact with the documented
schema.
**Depends on:** none (foundation)
**Affected areas:** `wrappers/sdd-eval-collect.yml` (new),
`.github/actions/sdd-eval-collect/action.yml` (new),
`.github/actions/shared/parent-walk.js` (reuse), `templates/.github/labels.yml`
(no new labels; read-only), `scripts/quick-setup.sh` (installer entry),
`shared/sdd-interaction.md` (command table), `docs/sdd/` (surface doc).

**Functional Requirements:**

- **R1.1**: `sdd-eval-collect` shall be a deterministic utility workflow: a
  thin wrapper plus composite action with no `engine:` and no compiled
  `.lock.yml`, exempt from the OTLP mandate per ADR 0020 §5.
- **R1.2**: The wrapper shall fire on all four trigger tiers: (a)
  `workflow_run` completion of every `sdd-*` agent workflow; (b) lifecycle
  label transitions on tracking issues (`issues: labeled/unlabeled` for
  `sdd:*` and `needs-human`); (c) feature post-mortem on the `sdd:done`
  transition; (d) a weekly `schedule` for cross-run aggregation. A token-strict
  `/eval` comment command (write-access-gated, `eyes` ack) forces a refresh.
- **R1.3**: The enablement predicate shall be **default-on with a correct
  unset case**: the opt-out gate must evaluate to enabled when the repository
  variable is unset. It shall be written as an explicit disable comparison
  (`vars.SDD_EVAL == '0'` negated at the job level via
  `vars.SDD_EVAL != '0' || vars.SDD_EVAL == ''` or an equivalent
  `format()`-normalized form) and covered by a lint assertion, because the
  evaluated run demonstrated that `vars.X != '0'` alone is false for unset
  variables (GitHub expression coercion) and silently disabled a default-on
  surface fleet-wide.
- **R1.4**: On tiers (a)–(c) the collector shall resolve the affected
  tracking issue (branch-prefix join keys per ADR 0023's reasoning, shared
  parent walk) and compute the **per-feature metric set**:
  - phase wall-clock per lifecycle transition, and human-gate share of
    elapsed wall-clock;
  - `needs-human` episodes: applier, clearer, dwell, and position in the run
    (fraction of elapsed run time), flagging late episodes (position > 0.5);
  - stranding: any task `sdd:in-progress` with no open PR and no queued or
    in-flight execute run beyond the execute timeout plus slack; monitor
    re-dispatch attempts observed vs. recoveries achieved;
  - run-shape anomalies on the completed run that triggered tier (a):
    conclusion success with empty safe-output items on an implementation
    directive, `num_turns == 1` with zero tool calls, `startup_failure`,
    activation-cancelled after successful route/ack, fan-wide
    `startup_failure` across agentic wrappers while pure-actions wrappers
    pass;
  - review-loop counters per open `sdd/` PR: auto-revise / check-revise /
    conflict-resolve marker counts vs. caps, review-comment and reaction
    tallies, thumbs-down reactions attached to runs whose conclusion was
    `cancelled` (false-signal detection), finding fingerprints
    (path + rule/quote hash) re-raised after a thread was resolved, both
    within a PR and across sibling PRs of the same tracker;
  - thread-resolution audit via GraphQL: bot-resolved threads whose last
    comment is not a bot reply containing a commit sha or a rebuttal;
  - integrity: for every open `sdd/`, `spec/`, `arch/` PR, the net diff
    against current origin/main — deletions or reversions of files/hunks that
    main has independently advanced, docs-only assertion for spec-agent PRs,
    size/file-count tripwires on "docs" PRs; recurrence-fingerprint match of
    new incidents against closed "fixed" framework issues; a spec-edit
    tripwire flagging any implementation PR that modifies a merged
    `docs/specs/**` spec file (the evaluated run's spec drift was spread by
    exactly such an edit) so the judge's fidelity item re-runs on the edited
    spec;
  - sizing: net-diff distribution of merged `sdd/` PRs vs. the ADR 0026
    floor and this spec's advisory ceiling (§ Design Considerations);
    single-task-Unit count; tasks vs. plan-comment tree (ADR 0010 guarantees
    exact materialization);
  - proof delivery: the spec's declared proof artifacts joined against the
    merged diffs — `#[ignore]`/environment-gate/`required-features` guards
    detected on the tests that implement declared proofs, and proofs with no
    implementing artifact at all;
  - gate/CI parity: gate-passed-then-first-consumer-CI-fail joins per PR;
    bot commit subjects pre-checked against discovered commitlint config;
  - requirement coverage: R-ID presence joins spec → task bodies → PR
    diffs/titles/bodies;
  - dispatch health: cascade fan-outs vs. run starts they produced; manual
    `/execute`/`/dispatch` counts (the human-touch inventory);
  - status-surface health: exactly one status comment per tracker, fresher
    than the last pipeline event;
  - cost: per-run token usage parsed from run artifacts — both artifact
    layouts (`agent_usage.json` where present; the engine result record in
    the agent stdio log otherwise) — aggregated per phase, per model tier,
    and per feature, with cost-per-net-line computed at post-mortem.
- **R1.5**: Every tier-(a)–(c) invocation shall upload an
  `eval_snapshot.json` artifact conforming to a documented, versioned schema
  (`schema_version` field; documented in `docs/sdd/sdd-eval.md`). The
  snapshot is the machine surface the judge and the actor agent consume.
- **R1.6**: The collector shall upsert one roll-up issue per repository,
  located by the `<!-- sdd-eval -->` sentinel (title prefix `[sdd-eval]`),
  editing the issue body in place with the latest per-feature scorecards and
  appending one comment per feature post-mortem (tier c) so history is
  preserved in comments — the established weekly-roll-up pattern. It shall
  never edit tracking-issue bodies and never write lifecycle labels; its only
  writes are the roll-up issue, its own comments/reactions, and artifacts.
- **R1.7**: On tier (d), the collector shall aggregate across features:
  trend tables for phase latency, needs-human rate/dwell/position, loop
  counts, recurrence fingerprints, cost per feature and per net line, and
  gate-latency share — appended to the roll-up issue as a dated comment.
- **R1.8**: The collector shall run under the suite's App identity (ADR
  0019) so scorecard writes attribute to the bot, with `issues: write`,
  `pull-requests: read`, `actions: read`, `checks: read`, `contents: read`.
- **R1.9**: All wrapper logic beyond trigger routing shall live in the
  composite action (ADR 0015); shared join code (parent walk, branch-prefix
  resolution) shall be extracted and reused, not duplicated.
- **R1.10**: `/eval` shall join the command vocabulary in
  `shared/sdd-interaction.md` and pass the command-table consistency gate;
  the wrapper-lock contract, lifecycle state-machine (no lifecycle writes by
  this workflow), and leak-scan lint gates shall pass unchanged.

**Proof Artifacts:**

- Test: on a seeded test repository, applying `sdd:in-progress` to a task
  with no PR and waiting past the timeout threshold produces a scorecard
  entry flagging one stranded task; the `eval_snapshot.json` artifact
  validates against the documented schema. Fails before this unit (no
  workflow exists).
- CLI: `gh api` for the roll-up issue after a seeded `sdd:done` transition
  shows a post-mortem comment containing phase wall-clock, needs-human, and
  proof-delivery sections. Fails before this unit.
- File: `wrappers/sdd-eval-collect.yml` exists, carries no `engine:`, and
  the repository compiles no `sdd-eval-collect.lock.yml`; the enablement
  predicate matches the R1.3 unset-safe form and a lint test asserts it.

### Unit 2: Scoring rubric, machine-check plan, and ratification gate

**Purpose:** Commit the qualitative scoring rubric as a versioned document
with a machine-check plan per item, and gate rubric versions behind operator
ratification so judge scores are comparable and auditable. Demoable: the
rubric file passes its lint, and an unratified rubric version is refused by
the judge.
**Depends on:** none (parallel to Unit 1)
**Affected areas:** `docs/specs/03-spec-run-evaluation/rubric.md` (new),
`scripts/test-eval-rubric.py` (new lint), `.github/workflows/lint.yml`
(gate registration), `shared/sdd-interaction.md` (`/ratify-rubric`).

**Functional Requirements:**

- **R2.1**: `rubric.md` shall enumerate every judged dimension as an item
  with: a stable id (`RB-<area>-<n>`), the question being scored, an anchored
  scale (each point defined by observable evidence, not adjectives), the
  evidence sources (which snapshot fields, diffs, threads), and a
  **machine-check plan** classifying the item as `deterministic` (collector
  computes it; the judge must not re-score it), `assisted` (collector
  computes inputs, judge scores), or `inference` (judge-only), with the
  concrete check named for the first two classes.
- **R2.2**: The rubric shall carry a `version:` in frontmatter. Any change to
  item ids, scales, or machine-check classes requires a version bump; the
  lint (`test-eval-rubric.py`) asserts id stability, scale anchoring
  (every scale point cites an evidence source), and version-bump-on-change
  (hash recorded in the file).
- **R2.3**: A rubric version shall take effect only after **ratification**:
  a write-access `/ratify-rubric <version>` comment on the roll-up issue (or
  the spectacles-side PR approval when the rubric changes in-repo), recorded
  by the collector as a dated ledger comment. The judge shall refuse to score
  with an unratified version and fall back to the last ratified one, saying
  so in its output.
- **R2.4**: The launch rubric (v1) shall cover at minimum: spec fidelity of
  merged diffs per R-ID (delivered / partial / missing, judged on wired-in
  behavior, not text presence), proof-artifact deliverability (executed vs.
  gated vs. missing), demoability at `sdd:done` (does an executed end-to-end
  artifact exist), silent-revert suspicion on PR diffs vs. origin/main,
  revise-diff-addresses-threads quality, assumption-ledger evidence quality
  (settled-by-circular-citation detection), source fidelity of the
  generated spec (contradictions between generated normative requirements
  and the source document they were derived from — every downstream stage
  validates against the generated spec and is blind to this class by
  construction, so it is judged at the spec boundary), plan quality, and
  contributor-facing tone of bot copy. Each anchored to the failure classes
  the evaluated run exhibited.

**Proof Artifacts:**

- File: `rubric.md` exists with ≥8 items, every item carrying id, anchored
  scale, evidence sources, and machine-check class; `scripts/test-eval-rubric.py`
  passes in `lint.yml` and fails when an item's scale point lacks an evidence
  citation (demonstrated by a fixture).
- Test: the ratification ledger flow on a test roll-up issue — `/ratify-rubric v1`
  recorded, a judge dry-run with `v2-unratified` refuses and names the
  fallback. Fails before this unit.

### Unit 3: `sdd-eval-judge` — engine-bearing inference scoring

**Purpose:** Score the rubric's assisted and inference items on real run
evidence, reproducibly and within budget. Demoable: a post-mortem judge run
on a completed feature produces a rubric-versioned, model-stamped score
comment on the roll-up issue.
**Depends on:** Unit 1 (snapshots), Unit 2 (ratified rubric)
**Affected areas:** `.github/workflows/sdd-eval-judge.md` (new gh-aw
source + compiled lock), `wrappers/sdd-eval-judge.yml` (new),
`scripts/quick-setup.sh`, `docs/sdd/sdd-eval.md`.

**Functional Requirements:**

- **R3.1**: `sdd-eval-judge` shall be a gh-aw agent distributed per ADR 0004
  (hosted lock + thin wrapper) carrying the full ADR 0020 observability
  block, importing `shared/rigor.md` (evidence standards) and the eval
  interaction contract.
- **R3.2**: The judge shall fire on tier (c) (`sdd:done` post-mortem) and
  tier (d) (scheduled aggregation), and on demand via a write-access
  `/eval judge` comment. Per-run (tier a) judging is **sampled, not
  universal**: only runs the collector flags anomalous (run-shape anomalies,
  integrity tripwires) are judged, to hold budget.
- **R3.3**: Every score the judge emits shall be stamped with: rubric
  version, engine model id (pinned in the workflow source, not floating),
  prompt/source revision (the suite ref), and the snapshot `schema_version`
  it consumed. Scores without all four stamps are invalid by definition.
- **R3.4**: The judge shall score only `assisted` and `inference` rubric
  items; for `deterministic` items it shall quote the collector's value and
  may annotate but not override it.
- **R3.5**: Per-feature judge budget shall default to **5% of the feature's
  own recorded pipeline token usage** (from the collector's cost metric),
  with an absolute floor and cap set as repository variables
  (`SDD_EVAL_JUDGE_MIN`/`_MAX`); the baseline figure is seeded from the
  evaluated run's recorded usage. On budget exhaustion the judge emits a
  partial scorecard that names the unscored items — never a silent
  truncation.
- **R3.6**: The judge's output is one comment per invocation on the roll-up
  issue (post-mortem scores under the feature's section), plus its standard
  artifacts. It shall write no labels, no issues, and no PR comments.
- **R3.7**: The judge's remediation-delta mode: when invoked on a feature
  whose tracking issue gained post-`sdd:done` human PRs referencing it, it
  shall classify the remediation diff hunks into
  specced-but-not-delivered / needed-but-unspecced / quality-refactor and
  report the split — the evaluated run's B3 analysis, productized.

**Proof Artifacts:**

- Test: a post-mortem judge run on a seeded completed feature emits a score
  comment carrying all four reproducibility stamps and per-R-ID verdicts;
  re-running with the same inputs and pins yields the same rubric version and
  verdict set. Fails before this unit.
- CLI: with the budget variable set below the run's needs, the judge output
  names the unscored items explicitly. Fails before this unit.

### Unit 4: Durable retro-eval entry point

**Purpose:** Make the one-off retroactive evaluation re-runnable: given any
tracking-issue number, reproduce the full Phase-1 analysis (fetch, compute,
classify, report). The retro of the evaluated run is this workflow's first
(manual) execution. Demoable: `/retro-eval <issue>` on a completed tracker
yields the full retro scorecard as a roll-up comment.
**Depends on:** Units 1–3
**Affected areas:** `wrappers/sdd-eval-collect.yml` (backfill mode),
`.github/workflows/sdd-eval-judge.md` (retro directive),
`shared/sdd-interaction.md` (`/retro-eval`), `docs/sdd/sdd-eval.md`.

**Functional Requirements:**

- **R4.1**: A write-access `/retro-eval <issue>` comment (and a
  `workflow_dispatch` input equivalent) shall run the collector in
  **backfill mode**: reconstructing phase timelines, episodes, loop counts,
  integrity scans, proof delivery, coverage, and cost for the named tracking
  issue from historical API state and any still-retained artifacts, tolerant
  of expired artifacts (cost fields degrade to "unavailable", never fail the
  run).
- **R4.2**: Backfill shall then invoke the judge post-mortem (R3.7 included
  when remediation PRs exist), producing the complete retro scorecard —
  executive metrics, yardstick table, per-R-ID verdicts, remediation split —
  as one roll-up comment thread for the feature.
- **R4.3**: The entry point shall be idempotent per issue: re-running
  `/retro-eval` on the same issue upserts the feature's section rather than
  duplicating it, and records each execution in the ledger.
- **R4.4**: `docs/sdd/sdd-eval.md` shall document the retro procedure,
  including the artifact-retention caveat (run artifacts expire; retro-eval
  within the retention window preserves cost evidence, after it the retro is
  timeline-only).

**Proof Artifacts:**

- Browser/CLI: `/retro-eval` on a seeded historical tracker produces the
  full scorecard comment; a second invocation updates rather than duplicates
  it. Fails before this unit.
- File: `docs/sdd/sdd-eval.md` documents backfill mode and the retention
  caveat.

## Non-Goals

- **Acting on findings.** No labels applied or cleared, no issues opened on
  findings, no nudges, no blocking. That is the actor agent
  (`04-spec-eval-actor`), deliberately separated so the reporting surface
  stays trustworthy and side-effect-free.
- **Replacing sdd-validate's gates.** The collector observes and reports
  gate outcomes; it does not become a merge gate itself in v1. (The retro's
  recommendation to make the net-diff integrity signal a required check is a
  pipeline change, tracked separately.)
- **Dashboards.** OTLP spans from the judge flow to the existing collector
  infrastructure; standing up dashboards/alerting is outside this spec.
- **Fixing the failures it measures.** Stranding recovery, review-loop
  convergence, status-surface enablement are pipeline issues with their own
  tracks; this spec only guarantees they are *seen*.

## Design Considerations

- **Two parts, not one.** Every headline detection in the motivating retro
  was deterministic (timeline joins, run-shape checks, diff properties,
  greps). An engine-bearing evaluator for those would add cost, latency,
  drift, and the ADR 0020 burden to signals that must be trustworthy and
  cheap — the ADR 0023 reasoning, reapplied. Inference is reserved for
  judgment calls (R-ID semantics, revert intent, tone).
- **Roll-up issue, not committed scorecards.** Scorecards are operational
  telemetry about a run, not knowledge about the system; committing them
  would churn the repo and drag distillery-sync into ingesting run noise.
  The issue surface keeps history in comments, supports the ratification
  ledger, and is already the pattern operators know.
- **Default-on, correctly.** The status surface was default-on by intent and
  default-off in fact for its entire life because of one expression-coercion
  subtlety. R1.3 encodes the lesson as a requirement plus a lint, not a code
  comment.
- **Sizing ceiling (advisory).** The evaluated run's floors worked and
  overshot: median merged net diff ~1.7× the 400-line target, with the three
  largest PRs carrying the heaviest review loops. The collector reports an
  advisory ceiling breach at 2× the floor (800 net lines); ratifying a hard
  ceiling is a rubric/process decision left to the operator.
- **Judge sampling.** Universal per-run judging at the evaluated run's scale
  (hundreds of agentic runs per feature) would dwarf the pipeline's own
  cost. Anomaly-gated sampling plus post-mortem depth keeps the default
  budget inside R3.5's 5% envelope.
- **Cross-layout cost parsing.** The engine migration mid-June changed the
  artifact layout; the collector must parse both (`agent_usage.json` and the
  engine result record in the agent stdio log) or cost silently
  under-reports — the retro hit exactly this.

## Repository Standards

Distribution per ADR 0004 (judge: source + self-contained lock + thin
wrapper; collector: wrapper + composite action, ADR 0015). All ten `lint.yml`
gates apply, most relevantly: wrapper-lock contract (secrets ⊆ declared;
caller ≥ callee permissions), lifecycle state-machine validator (this suite
writes no lifecycle labels — the validator must show no writer additions),
command-table consistency (`/eval`, `/ratify-rubric`, `/retro-eval`),
requirement-ID cross-references, and leak-scan. Conventional commits;
`needs-human` contract per ADR 0001 (the eval surfaces never apply it — that
is the actor's decision under its own spec).

## Technical Considerations

- Tracking-issue resolution reuses `.github/actions/shared/parent-walk.js`
  and the branch-prefix join keys; no `closingIssuesReferences` (ADR 0023).
- Finding fingerprints: hash of (file path, rule id or normalized quote)
  per review thread; recurrence = same fingerprint after a resolved thread
  or across sibling `sdd/` PRs of one tracker. Persisted in the snapshot so
  recurrence detection is stateless per invocation.
- The integrity scan shells `git diff --name-status origin/main...HEAD`
  against a **full-history fetch with credentials** — the evaluated run's
  revert guard failed precisely because it ran on a shallow, credential-less
  checkout; the collector must not repeat that (assert non-shallow before
  scanning, else report the scan itself as failed).
- GraphQL is required for thread-resolution state and minimized-comment
  flags; REST alone cannot compute the resolution audit.
- Snapshot schema is versioned independently of the rubric; the judge
  records both.
- The weekly tier reuses the collector's own snapshots as input — it never
  recomputes history it already recorded.

## Security Considerations

- The collector runs on an App token with write access only to issues; it
  edits only content carrying its own sentinel. Prompt-injection surface:
  issue/PR text flows into scorecards — the collector treats all body text
  as data (no command interpretation beyond the token-strict `/eval` gate,
  which checks actor write access via the repository-permission API, not
  `author_association`).
- The judge reads diffs and threads from the repository it evaluates;
  its safe-outputs are restricted to comments on the roll-up issue. It
  carries the standard firewall/egress allowlist; OTLP endpoint handling per
  ADR 0020 §3 (secret URL, masked, artifact-scrubbed).
- Snapshots and scorecards live on the consumer repository and may quote
  consumer code; nothing from them is ever committed to this public
  repository.

## Open Questions

- Whether the advisory 2×-floor sizing ceiling should become a blocking
  triage constraint after a few scored runs (informed by ADR 0026 and the
  evaluated run's oversize/review-loop correlation).
- Whether tier-(a) collector runs on very busy repositories need their own
  concurrency shaping — the status surface's cancel-in-progress storm
  produced misleading `cancelled` conclusions during the evaluated run
  (informed by #310-class false signals).
- Whether the judge's remediation-delta mode should also fire on *pre*-done
  human PRs that reference the tracker (mid-run human interventions were a
  material fraction of the evaluated run).
- Where the cross-consumer aggregation lives once more than one consumer
  runs the suite (the roll-up issue is per-repo by design; a fleet view is
  out of scope here).

## Gap Analysis

Empty — forward-authored spec.

## Verification

- On a seeded test repository with the suite installed: drive a miniature
  feature through spec → done with one deliberate stranding, one oversized
  PR, one `#[ignore]`-gated proof, and one stale-base deletion; assert the
  scorecard flags all four, the post-mortem carries per-R-ID verdicts and
  the proof-delivery table, and `eval_snapshot.json` validates against its
  schema.
- Ratify rubric v1, run the judge post-mortem twice with identical pins;
  assert identical rubric/model stamps and verdict sets.
- Run `/retro-eval` against the seeded feature after deleting its artifacts;
  assert cost fields degrade to "unavailable" and everything else completes.
- All ten `lint.yml` gates green, including the new rubric lint and the
  R1.3 enablement-predicate assertion.
