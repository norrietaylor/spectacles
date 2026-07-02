---
version: v1-draft
status: unratified
---

# Run-evaluation scoring rubric

> The repository is public: no consumer identity, no internal URL, no cost
> figure. Draft — takes effect only after ratification per spec R2.3
> (`/ratify-rubric v1` recorded on the roll-up issue).

Each item: stable id, the question, an anchored scale (every point cites
observable evidence), evidence sources, and a machine-check class —
`deterministic` (collector computes; judge quotes, never re-scores),
`assisted` (collector computes inputs, judge scores), `inference`
(judge-only).

Scores are per feature (post-mortem tier) unless marked per-run. A scored
item always names its evidence; an item whose evidence is unavailable is
reported `unscored(reason)`, never guessed (per `shared/rigor.md`).

---

## RB-fid — Spec fidelity

**RB-fid-1 · R-ID delivery** — For each requirement ID: is the behavior
implemented **and wired into the live user-reachable path** at `sdd:done`?
Class: `assisted` (collector supplies R-ID → task → PR joins and diffs;
judge issues verdicts).
Scale: `delivered` = behavior exercised by a non-gated executable artifact
on the default branch; `partial` = code exists but unwired, feature-gated,
env-gated, or broken at integration; `missing` = no implementing change.
Evidence: spec R-ID text, merged PR diffs, proof-artifact audit
(RB-proof-1), task-issue re-scope decisions.

**RB-fid-2 · Remediation split** — When post-`sdd:done` human PRs reference
the tracker: fraction of remediation lines that are (a)
specced-but-not-delivered, (b) needed-but-unspecced, (c) quality/refactor.
Class: `assisted` (collector detects and sizes the PRs; judge classifies
hunks).
Scale: reported as the (a)/(b)/(c) percentage split; no target — the trend
is the metric. A rising (a) indicts execution; a rising (b) indicts
spec/plan coverage.
Evidence: remediation PR diffs vs. spec R-IDs vs. pipeline PR diffs.

## RB-proof — Proof and demoability

**RB-proof-1 · Proof delivery** — For each proof artifact the spec declares:
executed, weakened, or missing at `sdd:done`?
Class: `deterministic` — grep merged diffs for the implementing test/command;
detect `#[ignore]`, env-var gates, `required-features`, CI-lane-only
execution.
Scale: `executed` = runs in default CI or a committed runnable artifact ran
in a check; `weakened` = exists but gated so no default path executes it;
`missing` = declared, not implemented.
Evidence: spec proof declarations, merged diffs, check-run history.

**RB-proof-2 · Demoability at done** — Does an executed end-to-end,
user-visible demonstration exist at `sdd:done`?
Class: `assisted` (collector lists candidate artifacts; judge decides
whether any is genuinely end-to-end and user-visible, not a health check —
the empty-PR rule applied at feature scope).
Scale: 2 = an executed e2e artifact demonstrates the feature's headline user
story; 1 = e2e artifact exists but covers a fragment or requires unshipped
scaffolding; 0 = none (the evaluated run's state).
Evidence: proof audit, test-plan-style artifacts, CI runs at the done
boundary.

## RB-int — Integrity

**RB-int-1 · Silent-revert exposure** — Did any agent PR delete or revert
work that main had independently advanced, without a blocking signal?
Class: `deterministic` (net-diff-vs-main scan, docs-only assertion on spec
PRs, tripwires) with an `inference` backstop (judge reviews flagged diffs
for revert intent — deleted safety comments, `?` → `.unwrap()` tells).
Scale: count of incidents by outcome: blocked / warned-then-human-cleared /
merged-unnoticed. Any `merged-unnoticed` > 0 is the run's headline defect.
Evidence: per-PR net-diff scans, gate outputs, restore commits.

**RB-int-2 · Recurrence fingerprints** — Did a failure signature matching a
closed "fixed" framework issue re-appear?
Class: `deterministic` (fingerprint join against the closed-issue corpus).
Scale: count; each recurrence names the closed issue it matches — a point
fix that needed a guard.
Evidence: snapshot fingerprints, framework issue tracker.

## RB-loop — Convergence

**RB-loop-1 · Review-loop closure** — Who closed review threads, and how?
Class: `deterministic` for the counts (threads resolved with a bot
reply carrying a sha or rebuttal vs. resolved bare vs. human-disposed);
`assisted` for the quality score of a sample of closing replies (does the
reply actually validate or rebut the finding).
Scale: closure-integrity ratio = reasoned-bot-closures / all closures;
human-disposition count reported alongside (the evaluated run: ~80).
Evidence: GraphQL thread audit, comment authorship.

**RB-loop-2 · Finding recurrence** — Same finding re-raised after
resolution (within a PR or across sibling PRs)?
Class: `deterministic`.
Scale: recurrence count per feature; target 0 — each instance names the
fingerprint and passes.
Evidence: snapshot fingerprints.

**RB-loop-3 · Revise grounding** — Did each revise run consume the
unresolved thread context, and did its diff address it?
Class: `assisted` (collector: did the run fetch threads; judge: does the
diff address the sampled findings).
Scale: 2 = grounded and addressing; 1 = grounded, diff partially addresses;
0 = revise ignored available thread context.
Evidence: run transcript fetch calls, revise diffs, thread texts.

## RB-flow — Flow and autonomy

**RB-flow-1 · Recovery efficacy** — Of stranding/monitor escalations, what
fraction recovered without a human?
Class: `deterministic`.
Scale: recovered-auto / escalations, with per-episode cause class (timeout,
quota, engine crash, dispatch gap, route decline). Evaluated-run baseline:
0/6.
Evidence: monitor audit lines, run index, human-touch inventory.

**RB-flow-2 · needs-human discipline** — Episode count, dwell, and
position; late episodes (>50% of run) flagged.
Class: `deterministic`.
Scale: reported distribution; regression = late-episode count above the
prior runs' trend. The operator standard: early is acceptable, late is a
failure.
Evidence: label timelines.

**RB-flow-3 · Human-touch inventory** — Manual `/execute`, `/dispatch`,
`/revise`, label surgery, and decision comments, split
design-intended-gate vs. framework-failure compensation.
Class: `deterministic` for counts, `assisted` for the split.
Scale: compensation touches per feature; trend down.
Evidence: comment streams, label events.

## RB-input — Inputs

**RB-input-1 · Ledger evidence quality** — Are assumption-ledger entries
"settled" on independent evidence?
Class: `assisted` (collector extracts entries + citations; judge flags
circular settlement — an entry whose only evidence is the spec it
parameterizes).
Scale: circular-settlement count; each names the entry and the risk it
buried. Evaluated-run baseline: the two costliest unknowns were
circular-settled and later caused the worst stall and an unshipped
mechanism.
Evidence: architecture ledger, spike docs, downstream incident joins.

**RB-input-2 · Plan integration coverage** — Does the plan own the seams:
an integration/wiring/e2e task whose scope names the launch path and
entry-point files?
Class: `assisted`.
Scale: 2 = explicit integration task(s) with concrete files; 1 = wiring
mentioned but unowned; 0 = units only (the evaluated run — the two largest
unspecced remediation areas were files no pipeline PR touched).
Evidence: plan comment, task tree, remediation (b)-class concentration.

**RB-input-3 · Source fidelity of the generated spec** — Does each generated
normative requirement agree with the source document it was derived from
(diagrams and topology sections included), with contradictions listed?
Class: `inference` (judge-only; run at the spec boundary, where a correction
is cheap and everything downstream inherits it).
Scale: contradiction count; each names the R-ID and quotes the source
passage it contradicts. Evaluated-run baseline: three requirements inverted
the source's topology (routing via an internal switch the daemon was
explicitly not on), survived every downstream gate — which validate
conformance *to the generated spec* and are blind to source drift by
construction — and were corrected only by amending the spec inside a
remediation PR ~9 days after merge.
Evidence: source document, generated spec R-IDs, spec-PR review thread.

## RB-sig — Signals

**RB-sig-1 · Signal truthfulness** — False or missing operator signals:
thumbs-down stamped by cancelled runs, red agent checks from concurrency
noise, stale `needs-human`, dead status surface.
Class: `deterministic`.
Scale: false-signal count by class; status-surface uptime (fresh comment at
last pipeline event: yes/no per boundary).
Evidence: reaction-vs-run joins, check-run conclusions, status comment
freshness.

**RB-sig-2 · Contributor-facing tone** — Bot copy on human contributors'
items leads with value, no fault-listing, cost-free decline.
Class: `inference`.
Scale: 2/1/0 anchored on the derive-offer copy standard.
Evidence: bot comments on non-bot-authored items.

## RB-cost — Economics

**RB-cost-1 · Cost per feature / per net line** — Token usage per phase,
tier, feature; cost-per-net-line-kept.
Class: `deterministic` (both artifact layouts; degrade to
`unscored(retention)` when artifacts expired).
Scale: trended; regression = per-net-line cost rising across runs at equal
scope class.
Evidence: run artifacts, PR net diffs.

**RB-cost-2 · Waste share** — Tokens in runs that produced no accepted
output (crashed, cancelled, no-op'd, quota-killed), as a share of feature
total.
Class: `deterministic`.
Scale: trended share; each top waste run named with cause.
Evidence: run conclusions × usage records.

---

## Ratification ledger

| Version | Ratified by | Where | Date |
|---|---|---|---|
| v1-draft | — (unratified) | — | — |
