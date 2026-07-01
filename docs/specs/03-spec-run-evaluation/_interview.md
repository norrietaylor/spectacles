# Run-evaluation interview — questions before we begin

> Working document for the run-evaluation effort. The leading underscore keeps
> it out of distillery-sync ingestion; it is not a spec. Per
> `shared/repo-conventions.md` this file names no consumer repository: the run
> under evaluation is referred to as "the evaluated run" (tracking issue #478,
> implementation PRs #589 and #581 on the consumer repository).

## Purpose

Two deliverables hang off this interview:

1. **A retroactive evaluation** of the completed SDD pipeline run behind
   tracking issue #478: what worked, what didn't, and what needs to improve in
   the agent factory.
2. **A spec for an evaluation agent** that monitors future runs, measuring
   them qualitatively and quantitatively, through both deterministic
   computation and inference.

The questions below cover only what the spectacles repository cannot answer
about itself. Already mined from the tree, and not asked again here: the
machine-readable exhaust of every pipeline stage (lifecycle labels and their
authorized writers in `scripts/lifecycle-states.yml`, comment sentinels such
as `<!-- sdd-triage:plan -->` and the auto-revise retry markers, the `## Task`
block grammar and `blocked by #N` edges, branch-prefix join keys per ADR 0023,
per-run Actions artifacts including `agent_usage.json` and `prompt.txt`, the
opt-in OTLP export of ADR 0020); what `sdd-status`, `sdd-monitor`,
`sdd-validate`, and `sdd-review` already observe; and the conventions a new
distributed workflow must follow (ADR 0004 two-layer distribution, the ten
`lint.yml` gates, the installer wrapper list).

Answer inline, tersely. "Unknown" and "don't care" are valid answers.
Questions marked **[blocking]** gate the start of the retroactive evaluation;
the rest shape scope and the eval-agent spec.

---

## A. Access to evidence

**A1. [blocking] Consumer-repo access.** This session's GitHub scope is
limited to the spectacles repository; the run's evidence (issue timelines,
minimized comments, PR review threads, workflow runs, artifacts) lives on the
consumer repository. Which route do you want?

- (a) widen this session's repository scope so the evaluator reads the
  consumer repo directly (needs GraphQL for `isMinimized` comments and
  timeline actor/timestamp data);
- (b) run the evaluation *on* the consumer repository via the wrapper model,
  the same way the suite itself is distributed;
- (c) you export a forensic bundle (issue + sub-issue timelines with label
  events, all comments including minimized ones, PR diffs and review threads,
  the workflow-run list, downloaded run artifacts) into a fixtures directory
  on this branch.

**A2. [blocking] Artifact retention.** Are the Actions run artifacts for the
runs behind the spec PR and implementation PRs #589/#581 —
`prompt.txt`, `aw_info.json`, `agent_usage.json`, `otel.jsonl`,
`agent-stdio.log`, `safe-output-items.jsonl` — still retrievable? The run was
roughly two weeks ago, so a default 90-day retention window closes around
mid-September: token/cost and transcript evidence expires with it. Can
someone with access run `gh aw audit <run-id>` for the relevant runs? Were
any issues or comments deleted (not minimized) during the run?

**A3. OTLP telemetry.** Was `GH_AW_OTEL_ENDPOINT` set on the consumer
repository during the run? If yes: where does the collector live, what
backend stores the spans, what is retained, and what is the *read* path (the
in-repo key is write-only by design, ADR 0020)?

**A4. Distillery store.** Was Distillery configured on the consumer
repository (`DISTILLERY_PROJECT` et al.), and can the evaluator query the
store as a reconstruction surface, or must everything come from GitHub APIs?

**A5. Baselines.** The ADRs cite observed-run evidence from a pilot
repository (issues #252, #255, #272 — e.g. "~2 days across 4 human gates",
"70–98-line PRs"). Do you consider those the regression baselines for the
evaluated run, and can the evaluator access them?

---

## B. Ground truth about the evaluated run

**B1. [blocking] Success definition.** What did "success" mean for this
feature? "User demoable" is the phrase used — who was the demo audience, did
the demo happen, and did it pass? Rank these for this run: functional
correctness, spec fidelity, autonomy (zero `needs-human`), wall-clock
latency, cost.

**B2. [blocking] Path taken.** Did the run take the full pipeline (plan
comment, Unit/task tree, `/dispatch` cascade) or the fastpath/agile single-PR
path? More than 3000 lines across two implementation PRs sits oddly against
the 400-line demoable-unit floor (ADR 0026) and `SDD_AGILE_MAX=800` — was the
two-PR shape the planned task tree, or the result of consolidation, retries,
or rework?

**B3. [blocking] Provenance of PRs #589 and #581.** The task statement says
that *after completion* the spec "required these two PRs … to be user
demoable." Which is it:

- (a) the two PRs *are* the pipeline's designed output;
- (b) the pipeline finished but its output was not demoable, and these PRs
  are remediation written by humans;
- (c) remediation written by agents re-prompted outside the pipeline;
- (d) something else.

The answer decides whether the retro evaluates the pipeline's output or the
pipeline's *shortfall*, so precision here matters more than anywhere else.

**B4. Out-of-band human interventions.** Inventory what humans did that left
no timeline trace: direct pushes to `sdd/` branches, manual merges or
rebases, verbal or chat-channel scope decisions, label removals to pause the
cascade. Roughly how many human touches happened end-to-end, and which do you
regard as legitimate design-intended gates versus framework failures?

**B5. Consumer configuration during the run window.** Values of
`SDD_AUTO_MERGE`, `SDD_AUTO_DISPATCH`, `SDD_MONITOR`, `SDD_STATUS`,
`SDD_AGILE_MAX`, `SDD_SPEC_MIN_UNIT`, `SDD_TRIAGE_MIN_TASK`,
`SDD_MAX_REVIEW_ITERATIONS`, `SDD_REVISE_ON_CHECKS`, any
`GH_AW_MODEL_*` overrides — and which spectacles ref the wrappers were pinned
to (`@main` or a tag). Also: ADRs 0029/0030 are `status: proposed` — which
behavior was live during the window?

**B6. Third-party reviewers.** Was CodeRabbit (or any other automated
reviewer) installed on the consumer repository? Its `CHANGES_REQUESTED`
reviews drive the auto-revise loop and its silence drives monitor nudges —
both change the marker counts the retro will score.

**B7. Your priors.** Before evidence: your top three pain points and top
three pleasant surprises from this run. The retro will verify these against
the record rather than assume them, but they anchor where to dig.

---

## C. Retro-evaluation scope and rubric

**C1. Is the input spec in scope?** The original networking spec was provided
to the pipeline as-is. Should the retro also evaluate the *spec itself* as a
factory input (testability of its requirements, diagram fidelity,
demoable-unit decomposability), or only the factory's handling of it?

**C2. Rubric authority.** For qualitative scoring, the candidates overlap and
none is machine-checkable as written: `shared/rigor.md`,
`shared/sdd-proof-artifacts.md`, `shared/sdd-gates.md`, the specs' Success
Metrics prose. Should a ratified scoring rubric be one of the retro's
deliverables, and who ratifies it?

**C3. Cost economics.** Is cost a target dimension — tokens per feature, per
task, per model tier; Actions minutes? Is there billing-side data outside the
repositories that the evaluator can join against?

**C4. Report destination and audience.** Who reads the retro report, and
where does it live? Note the constraint: spectacles is public and its
leak-scan forbids committing consumer identities, so a report that names the
consumer repository needs a home outside this tree (consumer repo doc, private
issue, or externally) — or a genericized version lands here.

---

## D. The evaluation agent (spec for future runs)

**D1. Posture.** The repo's philosophy is "no LLM where API state suffices."
The natural shape is a two-part design: a deterministic collector
(sdd-status/sdd-monitor pattern: composite action, no engine, OTLP-exempt)
computing hard metrics, plus a separate engine-bearing judge for inference
scoring (spec fidelity, artifact quality, code quality). Do you want that
split, or a single engine-bearing agent doing both?

**D2. Trigger tiers.** When should evaluation fire: per agent run
(`workflow_run` completion), per phase boundary (lifecycle label
transitions), per feature (`sdd:done` post-mortem), scheduled cross-run
aggregation — or several of these as tiers?

**D3. Results destination.** Sentinel comment edited in place (loses
history), roll-up issue in the `sdd-unspecced-scan` pattern (history in
comments), committed scorecard doc with frontmatter so distillery-sync
ingests it (the spike `budget_hours`/`actual_hours` fields are the repo's
only quantitative-self-report precedent), OTLP spans toward a dashboard — or
a combination?

**D4. Identity and rollout.** May the eval agent write to consumer
repositories, and under which identity (App token per ADR 0019 vs plain
`GITHUB_TOKEN`)? Opt-in repository variable in the house style
(`SDD_EVAL=1`, like the monitor) or default-on (like the status surface)?

**D5. Metric priorities and enforcement.** The genuinely unmeasured
dimensions found in the tree: phase latency from label timelines,
`needs-human` rate and dwell time, auto-revise/nudge/re-dispatch loop counts,
R-ID coverage from spec through tasks to PRs, sizing-estimate error against
the 400/800-line floors, gate-finding fire rates, cost per feature,
fastpath-versus-full-path outcomes, proof-artifact quality. Which matter
most? And is the agent report-only, or may it act (apply labels, open
issues, block)?

**D6. Judge reproducibility and budget.** For the inference part: pinned
model and rubric version stamped into every score (so scores are comparable
across runs)? What per-run inference budget is acceptable?

**D7. Dogfooding.** Should the eval-agent spec itself be run through the SDD
pipeline (filed as a feature issue, `/spec`, the works) as its own next live
test — or built directly on a branch like this one?

---

## E. Engagement logistics

**E1. [blocking] What does "build a workflow" mean here?** Two readings:

- (a) a one-off orchestrated analysis performed now, producing the retro
  report and the eval-agent spec;
- (b) a durable, re-runnable retro-evaluation workflow artifact (a slash
  command or wrapper that can retro-eval any tracking issue), of which this
  run is the first invocation.

Or (c): do (a) now, and fold the durable version into the eval-agent spec.

**E2. Sequencing.** Retro report first and eval-agent spec second (the retro
findings feed the spec's metric choices), or in parallel? Any deadline —
noting the artifact-retention clock from A2?

**E3. Environment changes in flight.** Anything about to change in the
factory (ADR 0029/0030 rollout, model changes, new consumers) that the
evaluation should account for so its findings aren't stale on arrival?
