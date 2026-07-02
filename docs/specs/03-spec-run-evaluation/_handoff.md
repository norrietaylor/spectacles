# Handoff brief — SDD run evaluation (retro + eval-agent spec)

> Working document; the leading underscore keeps it out of distillery-sync.
> This file names no consumer identities (the repository is public and
> leak-scanned): `<consumer-repo>` and `<obs-repo>` are placeholders the
> operator maps at session start. Do not commit the real names to this
> repository — including in commit messages.

## Mission (original intent)

A full spec was run through the SDD pipeline on `<consumer-repo>`, tracked
by its issue **#478** (the networking spec,
`docs/specs/03-spec-networking/networking-with-diagrams.md` on the
consumer). After the pipeline completed, **two human-written PRs (#581 and
`#589`, >3000 lines total)** were required before the feature was
user-demoable. Deliverables, in order:

1. **Retroactive evaluation** of that run: detailed *what worked, what
   didn't, what needs to improve* in the spectacles agent factory.
   Delivered as an issue on the private consumer repo.
2. **A spec for an evaluation agent** that monitors future runs so
   performance can be measured qualitatively and quantitatively —
   deterministic where API state suffices, inference-based where judgment
   is required. The durable, re-runnable retro workflow is folded into
   this spec (interview answer E1-c). Includes a plan for machine-checking
   the scoring rubric plus a ratification gate (C2), and a companion
   sketch for a separate **actor agent** that acts on eval findings (D5).

Sequencing: retro first, spec second (E2). Nothing in the factory changes
until after the post-mortem (E3).

## Binding decisions from the operator interview

Full Q&A: `_interview.md` (same directory). The load-bearing ones:

- **Success ranking (B1)**: functional correctness > spec adherence >
  wall-clock > cost. `needs-human` is acceptable but must occur *early*.
- **Run shape (B2/B3/B5/B6)**: full pipeline path; all `SDD_*` variables at
  defaults; wrappers pinned to tag 0.3.0; CodeRabbit installed; the two
  remediation PRs are human-written integration plumbing + refactor —
  i.e. the retro evaluates a **demoability shortfall**, not just the
  pipeline's own output.
- **Operator priors to verify (B7)**: pain — output proven only in CI
  behind a feature flag (not end-to-end); risks not spiked up front caused
  late `needs-human`. Surprises — spike workflow, PR scope/size, plan
  quality.
- **Spec quality is in scope (C1)**: if the input spec could have been
  better, the framework should have exposed that early.
- **Eval agent (D1-D7)**: deterministic collector + separate engine judge;
  all trigger tiers; results to a roll-up issue on the private repo; App
  identity, default-on; all metric dimensions matter; judge budget
  baseline = the networking run's own usage; build directly (no
  dogfooding).

## State of work (what a fresh session inherits)

All on branch `claude/spectacles-eval-workflow-e66d2n`:

- `_interview.md` — questions + operator answers.
- `evidence/_run-window-evidence.md` — **the evidence backbone**: a
  structured harvest of the 39 spectacles issues around the run window
  (June 15–24, 2026). Contains: failure timeline, failure taxonomy,
  fix-cost accounting, the three safety-critical silent-revert incidents,
  a detection-gap matrix (feeds the eval-agent spec directly), and the
  pre-run baseline yardsticks (§6) the run must be scored against.
- `evidence/_run-window-issue-records.json` — the per-issue structured
  records behind the synthesis.
- `evidence/_export-run-evidence.sh` — one-command `gh` export of a run's
  full forensic surface (issue tree, timelines, comments, minimized flags,
  PRs + diffs, workflow runs, optional artifacts). Useful even with direct
  access, as a bulk fetcher.

Established facts to reuse (verified, do not re-derive):

- **Suite version**: tag v0.3.0 == current `main` (d928c5f, tagged
  2026-06-24). The run's tail ran exactly this tree; its start rode the
  v0.2.0→v0.3.0 fix storm (81 commits, most of them fixes prompted by the
  run itself).
- **Machine-readable exhaust** an evaluator can parse: lifecycle labels
  with single authorized writers (`scripts/lifecycle-states.yml`), comment
  sentinels (`<!-- sdd-triage:plan -->`, `<!-- sdd-status -->`,
  `<!-- sdd-execute:auto-revise -->` retry markers, monitor audit lines),
  the `## Task` block grammar with `blocked by #N` edges, branch-prefix
  join keys (`sdd/<task>-`, `spec/`, `arch/` — ADR 0023 says branch regex,
  not closingIssuesReferences), per-run Actions artifacts
  (`agent_usage.json` = tokens, `prompt.txt` = governing prompt,
  `safe-output-items.jsonl` = every requested mutation), and opt-in OTLP
  spans (ADR 0020; the consumer had it enabled — read path per the
  operator's observability runbook in `<obs-repo>/observability`).
- **Nothing aggregates any of this today** — no phase-latency, dwell-time,
  loop-count, cost-per-feature, or R-ID-coverage computation exists.
- **Artifact retention clock**: run artifacts expire ~90 days after the
  June run — extract token/transcript data before ~mid-September.

## Phase 1 — retroactive evaluation (do this first)

Reconstruct the consumer-side run, compute the metrics, score against the
yardsticks, verify the operator's priors, write the report.

1. **Fetch** (direct `gh`/API access, or run the export script): tracking
   issue #478 + full sub-issue tree (bodies, comments, label timelines
   with actors/timestamps), all `spec/`/`arch/`/`sdd/` PRs (reviews,
   review threads incl. minimized/resolved state, diffs, check runs),
   remediation PRs #581/#589, workflow-run index for June, artifacts for
   the agent runs (at minimum `agent_usage.json`, `aw_info.json`,
   `prompt.txt`), OTel data per the runbook, and the pilot baselines
   (runs behind spectacles issues #252/#255/#272).
2. **Compute the deterministic metrics** (the yardstick set is
   `evidence/_run-window-evidence.md` §6):
   - end-to-end wall-clock, split per phase from label events; human-gate
     latency share (target <50%)
   - `needs-human` count, cause, dwell time, and *position* in the run
     (operator standard: early OK, late is a failure — B1/B7)
   - task tree shape vs the plan comment (ADR 0010 guarantees the plan
     was materialized exactly); units/tasks counts; single-task-Unit
     fraction; median + distribution of net-diff per `sdd/` PR (yardstick
     ≈400 lines)
   - revise-loop counts per PR (auto-revise / check-revise /
     conflict-resolve markers) vs caps; finding-recurrence
     (re-raised-after-resolved fingerprints, issue #327 class)
   - dispatch health: monitor audit lines, stranded re-dispatches, manual
     `/dispatch`/`/execute` count (human-touch inventory, B4)
   - gate-pass-then-consumer-CI-fail count per PR (parity class: #312,
     #318)
   - integrity audit: net-diff-vs-main scan of every `sdd/` PR for the
     silent-revert class (#287/#317/#326)
   - cost: tokens per run/phase/tier from `agent_usage.json` + OTel;
     cost-per-net-line ("aic", #272); include the ~25M-token dead triage
     run (#271)
   - R-ID coverage: spec requirement IDs → task bodies → PR diffs
3. **Analyze the remediation delta (the B3 question, most important
   single analysis)**: classify every hunk of PRs #581/#589 as
   (a) specced-but-not-delivered, (b) needed-but-unspecced (spec gap the
   framework should have exposed early — C1), or (c) quality/refactor.
   This quantifies the demoability shortfall and apportions it between
   spec quality and factory execution.
4. **Audit the operator's priors (B7)** against evidence: proof-artifacts
   proven only in CI behind a feature flag (e2e gap); which risks were
   spiked vs which caused late `needs-human`.
5. **Write the retro report**: exec summary → scorecard vs yardsticks →
   what worked (with evidence) → what didn't (timeline + taxonomy, both
   framework-side from the evidence backbone and consumer-side from the
   reconstruction) → what to improve (prioritized; map each item to the
   detection-gap matrix row and open spectacles issues) → metric appendix.
   Deliver as a **new issue on the private consumer repo** (C4). A
   genericized copy may be committed here.

## Phase 2 — evaluation-agent spec (after the retro)

Spec at `docs/specs/03-spec-run-evaluation/` (this directory becomes the
spec dir; follow `docs/specs/TEMPLATE.md` frontmatter and demoable-unit
format), plus an ADR (`decisions/`, next free number) per house style.
Requirements fixed by the interview:

- **Two-part posture (D1)**: deterministic collector (composite action,
  no engine, OTLP-exempt per ADR 0020 §5 — the sdd-status/sdd-monitor
  pattern) + engine-bearing judge (full ADR 0020 observability burden).
- **All trigger tiers (D2)**: per agent run (`workflow_run` completion),
  per phase boundary (label transitions), per feature (`sdd:done`
  post-mortem), scheduled cross-run aggregation.
- **Delivery (D3)**: roll-up issue upsert (the `sdd-unspecced-scan`
  pattern — history preserved in comments) on the private repo.
- **Identity/rollout (D4)**: App token; default-on (like sdd-status).
- **Metric catalogue (D5)**: start from the detection-gap matrix
  (evidence doc §5) — its "deterministic signal" column is the
  collector's backlog; its "inference signal" column is the judge's. The
  retro's computed metrics become the launch set; all dimensions in
  scope.
- **Rubric (C2)**: committed rubric doc, machine-checkable plan per item,
  version-stamped scores, and a ratification gate (operator sign-off
  workflow) before a rubric version takes effect.
- **Judge reproducibility (D6)**: pinned model + rubric version stamped
  into every score; budget baseline = the networking run's usage.
- **Durable retro workflow (E1-c)**: the spec includes a re-runnable
  retro-eval entry point (give it a tracking-issue number, get the full
  Phase-1 analysis) — the one-off retro is its first manual execution.
- **Actor-agent sketch (D5)**: separate short spec for the agent that
  consumes eval findings and acts (labels, issues, escalation) — eval
  agent reports, actor agent acts.
- Distribution and CI conventions are mapped in the evidence doc and
  `workflows/README.md`: gh-aw source + lock + thin wrapper + installer
  entry + the ten `lint.yml` gates (incl. wrapper-lock contract,
  lifecycle state machine, command table).

## Constraints

- This repository is **public** with a leak-scan CI gate: no consumer org
  or repo names, no internal URLs, no cost figures in any committed file
  or commit message. Underscore-prefixed files are excluded from
  distillery ingestion.
- Branch: all work on `claude/spectacles-eval-workflow-e66d2n`; commit in
  conventional-commit style; push with `-u origin`.
- The retro report (with real names) goes to the private repo issue, not
  here.
