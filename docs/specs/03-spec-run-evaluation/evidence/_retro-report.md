# Retro (genericized): an SDD full-pipeline run, June 2026

> Genericized copy of the retro delivered to the consumer repository's
> tracker (its issue #616). Consumer identity, stack-specific names, and
> spend figures are removed per the leak-scan contract; issue/PR numbers
> refer to the consumer repository except where prefixed "spectacles".

Retroactive evaluation of the full-pipeline SDD run behind consumer tracking issue #478 (June 19-24, 2026; suite pinned v0.3.0; repository variables at defaults; a third-party reviewer installed). Every number is computed from the run's own exhaust.

**Verdict in one line:** the factory *manufactured* the feature but did not *deliver* it — it shipped 8.3k net lines with a strong plan and honest per-task discipline, then declared `sdd:done` on a feature no user could run, having spent over half its wall-clock waiting on a human, with every unit of review-loop convergence and every stranding recovery performed manually by the operator.

---

## 1. Executive summary

- **The pipeline completed**: `/spec` (06-19 22:48 UTC) → `sdd:done` (06-24 22:31), **119.7 h** end-to-end. It produced the spec (PR #482), architecture + assumption ledger (#484, #491), 3 spikes (#485/#486/#511), a 12-task tree across 4 units, and **11 merged implementation PRs** (~8.3k net lines) with 30/30 requirement IDs textually traceable spec→task→PR.
- **The output was not user-demoable.** At `sdd:done`, **8 of 30 R-IDs were delivered working end-to-end, 19 partial, 3 missing**; of the spec's declared proof artifacts, **1 was delivered as specified, 9 weakened** (`#[ignore]`-gated, env-gated, CI-lane-only, or behind a cargo feature no binary compiled), **5 missing**. No R-ID, proof artifact, or gate required an *executed user-visible demo*, so `sdd:done` was reachable with none.
- **Remediation cost (PRs #581 + #589): 5,671 changed lines**, classified hunk-by-hunk:
  - **45% (2,560 lines) specced-but-not-delivered** — behavior R-IDs required that the pipeline didn't deliver in working form (the VM-side transport transport, a rootless per-sandbox networking mode, proxies built-but-never-served, delivered-but-broken isolated-mode task enforcement);
  - **30% (1,702 lines) needed-but-unspecced** — integration the feature needed that no R-ID covered (guest boot/init plumbing: 295 lines in a file **no pipeline PR touched**; daemon egress; demo scaffolding; e2e test plan);
  - **25% (1,409 lines) quality/refactor** of pipeline output that worked.
- **Human effort was the pipeline's hidden engine**: 80 human touches — **23 manual `/execute`**, 17 `/revise`, 3 `/dispatch`, 33 substantive decision comments — plus per-finding triage of every review loop and hand-restoration of reverted files. Human-gate share of wall-clock ≈ **56%** (yardstick: <50%).
- **Automated recovery recovered nothing**: sdd-monitor escalated 6 stranding episodes, **0/6 recovered without a human** (spectacles #320 confirmed live). **The status surface never ran**: `sdd-status` has **0 successes in 10,633 runs ever** on this repo — the wrapper's `vars.SDD_STATUS != '0'` gate is false when the variable is unset (GitHub expressions coerce `null` and `'0'` to `0`), so "default-on" is actually default-off. The tracking issue never had a status comment; the operator watched raw Actions streams for 5 days.
- **The silent-revert class (spectacles #326) fired live, twice**: agent arch PR **#491 deleted the 308-line name-resolution spike doc** merged 10 minutes earlier (all checks green, auto-merged; restore PR #543 closed unmerged — **the doc is still absent from main today**), and PR #556's initial diff was a 5-way stale-base revert bundle (deleted the #552 a process-signalling spec, reverted #537's hardening) that sat **warning-only for 13.5 h**. The dedicated merged-change revert guard was **INCONCLUSIVE on every invocation all run** (shallow clone, no credentials). No integrity condition hard-blocked a merge at any point.
- **Cost (lower bound; some artifacts already expired)**: ≈ **81.2M effective tokens** across ≥90 agentic runs attributable to the #478 tree — ≈ **9.8k effective tokens per net line kept** (91% of traffic is cache reads; fresh output was ~0.94M tokens), plus ~15% of it (12.1M) in runs that produced no accepted output (crashes, cancels, quota kills). Detail in appendix C.

The operator's pre-evidence priors held up well: "proven only in CI behind a feature flag" is **confirmed**; "unspiked risks caused late needs-human" is **half the story** (late episodes split ~5 unspiked-risk vs ~6 framework failures); the three pleasant surprises (spike workflow, PR scope, plan quality) are all **real but overstated** (§6).

---

## 2. Run reconstruction

### Phase timeline (from tracker label events)

| Phase | Interval | Wall-clock |
|---|---|---|
| `/spec` → `sdd:spec` → `sdd:triage` (spec PR #482 merged) | 06-19 22:48 → 06-20 02:52 | 3.8 h |
| `sdd:triage` → `sdd:ready` (arch #484/#491, spikes #485/#486, plan, `/approve`, materialize) | → 06-20 06:21 | 3.5 h |
| `sdd:ready` → `sdd:in-progress` (`/dispatch`) | → 06-20 06:27 | 0.1 h |
| `sdd:in-progress` → `sdd:review` | → 06-22 16:13 | 57.8 h |
| `sdd:review` → `sdd:done` | → 06-24 22:31 | 54.3 h |

The front half (spec through materialized tree: 7.4 h, one human decision gate on the second spike) is the design working as intended. The back 112 h are dominated by stranding dwell, review-loop convergence, and human gates.

### Tree shape

4 units; Unit 3 correctly collapsed to a single task (ADR 0028 — zero uncollapsed single-task units). 8 planned tasks (#495–#502) + 1 planned-then-split (the operator `/revise`-split Task 1.2 into three before `/approve`) + **3 operator-filed mid-run tasks** (#526 hardening deferrals, #542 "wire the built component into the live launch path", #550 process-signalling) + 1 human-only hardware-gated task (#535/PR #540). Spike #511 (the network-switch attach protocol) was also mid-run — the protocol was load-bearing and unspiked at plan time.

### maps task → merged PR

495→507, 496→525, 497→522, 498→521, 499→556, 500→546, 501→561, 502→554, 526→537, 542→547, 550→555 (fastpath). All 11 merged by the operator (mostly by arming auto-merge). Zero green agent PRs closed unmerged (the pilot-era trust-loss event did not recur); one mis-routed duplicate (#538) was human-closed.

---

## 3. Scorecard vs the pre-run yardsticks

Yardsticks are the framework's own, from its pre-run design issues (spectacles #247/#252/#254/#255/#257/#272).

| Yardstick (pre-run standard) | Target | Measured | Verdict |
|---|---|---|---|
| Median merged sdd-PR net diff | ≈400 | **694** (79–1765; three PRs >1300) | ❌ oversize — the floors fixed the pilot's 100-line problem and overshot; no ceiling exists |
| Single-task-Unit count | 0 | 0 (Unit 3 collapsed) | ✅ |
| Over-decomposition (tasks ≫ scope) | 1–2 tasks / ~250 lines | 11 PRs / 8,265 net lines ≈ 751/PR | ✅ class did not recur |
| Human-gate share of wall-clock | <50% | **≈56%** | ❌ |
| `needs-human` position | early OK, late = failure | **17 episodes; 11 after the 50% mark**; median dwell 3.8 h, max 34.2 h, total 134.5 h | ❌ |
| Green agent PRs closed unmerged (trust loss) | 0 | 0 | ✅ |
| One fresh status comment per tracker | 1, newer than last event | **0 — surface never ran (gate bug)** | ❌ hard miss |
| Every external wait bounded | 30-min-class SLA | monitor flags fired, but recovery 0/6; strandings dwelt 12–34 h | ❌ |
| Revise grounded in PR thread | yes | ✅ assembled directive consumed threads (#247 worked) | ✅ |
| Every thread closed with reasoned verdict | yes | ❌ human performed ~80 inline dispositions; blanket resolution + re-raise loops (#311/#327 confirmed) | ❌ |
| Cost ratio trended (`aic`) | trended per feature | computed here (appendix C); nothing trends it automatically | ❌ (no automation) |

**Score: 4 of 12.** Every miss was *detectable during the run from API state alone* — none required inference (§8).

---

## 4. The demoability shortfall (the B3 question)

The pipeline hit `sdd:done` with the feature un-runnable by a user. The remediation delta apportions responsibility precisely:

### 4a. Specced-but-not-delivered (2,560 lines, 45%) — factory execution

The five big items, all covered by explicit R-IDs:

1. **the VM-side control transport (R1.4/R1.5, R2.3/R2.4)** — R1.5 explicitly requires the fd-pass attach over the VM-side channel. No pipeline diff contains it; PR #522's title promised it and its body deferred it ("split + merge on green scope," operator-approved under stranding pressure). #581 added the missing transport implementation and its attach gating.
2. **A rootless per-sandbox networking mode (R1.5/R1.6)** — the pipeline's mechanism never worked without root; #589 replaced it with a different userspace-network stack after external reviewer advice (PR still open at time of writing; verified working 07-01).
3. **Proxies built but never served (R3.3/R3.4, R4.4)** — PR #546 built a complete B5 egress proxy (+549 lines, passing tokio tests) and #554 a complete mTLS reverse proxy — **the daemon only bind-checked them; nothing called `serve()` outside tests**. R3.3's own curl proof artifact was unpassable at merge. #581's `start_host_proxies` wired them to the live registry.
4. **Delivered-but-broken enforcement (R1.2)** — a task-launch path hardcoded the permissive network mode for every task, leaking host egress to an isolated session's tasks; caught only at integration.
5. **Registry not routable (R3.3/R3.6)** — hostnames registered but no live routing; rename lifecycle broken.

### 4b. Needed-but-unspecced (1,702 lines, 30%) — spec/plan gap the framework should have exposed early

- **Guest boot/init integration: the guest-init source file — 295 lines in a file zero pipeline PRs touched** (mount, pty, root-switch, and daemon-egress plumbing). Every in-guest sandbox died exit-125 without it. No R-ID mentions the guest boot path; the spec's "Affected areas" never named it, so *end-to-end wiring was nobody's task* — the same gap the operator had to file #542 for mid-run.
- Daemon's own egress, demo scaffolding (empty-workspace launch), PTY fixes, and the **e2e test plan (`test-plan.md`/`test-plan.sh`, 415 lines) — the demoability artifact itself arrived in remediation**.

### 4c. Quality/refactor (1,409 lines, 25%)

Mostly code-motion of *working* pipeline output (moving working attach code behind a network abstraction and extracting a shared crate). This is the healthy fraction: it means the humans found the pipeline's code worth keeping and restructuring rather than rewriting.

**Split of blame:** ~45% factory execution (R-IDs not delivered working, several knowably so — a grep for `#[ignore]`/`required-features` at validate time would have flagged 9 of 15 proofs), ~30% spec input (C1: unvalidated implementation hypotheses transcribed as settled R-IDs — see §6; integration wiring structurally unowned), ~25% ordinary engineering iteration.

---

## 5. What worked (with evidence)

1. **The front half is genuinely good.** Spec in 3.8 h with a real human gate that caught real gaps (operator `/revise` at hour 3.6 added two missing requirement areas → R3.6/R4.9). Triage produced an architecture doc, an assumption ledger, and two spikes by hour 4.
2. **The spike workflow.** #485 (name-resolution) and #486 (implementation-choice) turned around in 2.4 h/1.1 h, and the plan comment demonstrably folded both ("Spike wave drained…"). Mid-run spike #511 produced a 615-line protocol doc that unblocked the run's worst stall. This is the operator's surprise #1, and it is real — with the caveat that #486 contained a math error and wrong protocol name (human-fixed next day, PR #490), and #511 existed only because the risk wasn't spiked up front.
3. **The plan comment** (17.6 kB): units in dependency order, per-task `Depends on` edges, R-ID coverage lines, `ALREADY EXISTS` reuse anchors with `file:line`, model tiers, per-task proofs, ADR-0028 collapse note. Materialization matched it exactly (ADR 0010 held).
4. **Sizing reform held**: no over-decomposition recurrence; 1:1 task→PR; conventional commits; clean branch join keys.
5. **The assembled revise directive (#247) worked**: the surviving revise runs consumed all unresolved threads — feedback never had to be re-typed (what *didn't* work is loop closure, §6).
6. **Fastpath**: #550 → `/fastpath` → spec stub → `/approve` → PR #555 merged in ~5.5 h. The single-PR path works when scoped right.
7. **The code itself**: 75% of remediation was *not* rework of broken pipeline code; the humans kept the substance (the mesh core, policy types, proxy implementations, and the IP allocator) and mostly wired, hardened, or restructured it.
8. **sdd-monitor as a detector** flagged every stranding (6/6) with accurate audit lines and correct attempt accounting — as a *recovery* mechanism it failed completely (§6).

---

## 6. What didn't work

### 6a. `sdd:done` ≠ demoable — the contract gap
Nothing in gates, proofs, or lifecycle requires an *executed end-to-end demo*. All heavy proofs ran `#[ignore]`+env-gated in a CI lane **the human added** (PRs #508/#510), or sat behind cargo features (`networking-wg`, `networking-proxy`) that no shipped binary compiled. The empty-PR rule was honored per-PR while the *feature* stayed undemonstrable. (Operator pain #1: **confirmed**.)

### 6b. Integration wiring was structurally nobody's job
The spec's per-unit "Affected areas" never included the launch path or guest boot; the plan planned units, not the seam between them. The operator had to notice (#499's investigation found the new mode handled identically to an existing one) and file #542 mid-run; the guest-init source was never touched at all until remediation.

### 6c. Evidence standards inside the ledger — spec risk didn't surface early (C1)
The input spec was an unusually strong PRD fusing requirements with an implementation *hypothesis overlay* (transport, filter-API, no-root, and resolver assumptions). The pipeline transcribed hypotheses into R-IDs, and the assumption ledger marked the costliest unknowns **"settled" citing the spec itself** ("settled | spec R1.5") — circular evidence. Consequences: the two spikes went to a cheap library choice while the *actual* top risks (the component attach protocol (34 h stall, mid-run spike #511); the rootless mechanism (#589 pivot, still open); a filter-API assumption (R2.2 dead, its use case never shipped, split to #553)) went unspiked. Spike #485's own Finding A contradicted its recommendation and nothing caught it until the operator's "**Hold — do not merge**" on PR #546 forced the mid-run mechanism re-scope. Answer to C1: **yes — the framework had the right early artifacts (ledger, spikes, spec gate) and they under-verified; the operator's `/revise` was the only substantive spec review.**

### 6d. Stranding and recovery: every recovery was a human
6 monitor escalations, 4 episode groups, **0/6 auto-recovered** (#320 confirmed): protected-path `.github/` capability gap (#495), a dispatch that produced no run (#497), a ~60 m timeout kill (#498), an engine crash from netns thrashing (#496), and **Anthropic usage-window quota exhaustion** (#499/#500 — operator-confirmed), a failure mode the framework doesn't model at all (monitor's 3 attempts fire within ~24 min against multi-hour quota windows, and only after `needs-human` already excludes the task). Net: **23 manual `/execute`**. Of the cascade's 12 automatic `/execute` fan-outs, only 1 led to a PR without further human action.

### 6e. The review loop does not converge on its own
sdd-review re-raised identical findings across passes (same path+rule: R1.4 finding ×5 on #522; `_ => "tcp"` ×4 on #556) with no memory of dispositions (#327). sdd-execute pushed fixes but never closed threads with verdicts (#311). The operator closed everything: 5 batch "N findings validated against HEAD remain" `/revise` comments, ~80 inline dispositions (last commenter in 29/35 threads on #556), plus a deferral sink (#526→#537) whose fixes were then **silently reverted by stale-base sibling branches** (#554/#556) and re-raised — a cross-PR recurrence loop. False signals compounded it: **172 thumbs-down, 0 thumbs-up** stamped on consumed findings (#310), and `needs-human` flags on #554/#556/#561 that were stale, mis-graded, or catch-22 by the time a human looked (each hand-cleared on 06-24). CodeRabbit: 0 `CHANGES_REQUESTED` ever; it caught one HIGH security bug and one revise regression as plain comments; it was paused (`@coderabbitai ignore`) an hour before #556 merged.

### 6f. Integrity: the highest-severity class ran unguarded
Beyond the two live incidents in §1: the **merged-change revert guard (the #287 fix) was inconclusive on every invocation** — shallow clone without credentials, so it could never see origin/main. Gate-2 treats merged-doc deletions as clearable Warnings by design; a spec deletion demotes the boundary to the lighter gate set; validator check runs always conclude success. **At no point in the run did any framework check hard-block a merge for an integrity reason.** Detection remained what it was in the pilot era: red consumer CI or a human reading net-diffs.

### 6g. Observability inverted
The one surface built to fix "human watching" (#254 → ADR 0023) was dead-on-arrival for every consumer (the `vars.SDD_STATUS != '0'` unset-coercion bug — 10,633 runs, 0 successes, and its own skip-storm produced 1,947 no-op runs *inside this window*). Meanwhile live signals actively lied: thumbs-down on consumed findings, red "agent" checks on PR commits from concurrency-cancelled runs, `needs-human` labels outliving their cause. Gate/consumer-CI parity also failed twice exactly as #312/#318 predicted (commitlint red on #554 human-reworded; `build-macos`/`clippy` and KVM-lane failures reaching already-open PRs #507/#525).

---

## 7. Priors audit (B7)

| Prior | Verdict | Evidence |
|---|---|---|
| Pain: proven only in CI behind a feature flag | **Confirmed** | every heavy proof `#[ignore]`/env-gated in the human-added netns lane or feature-gated; `--network` CLI + test-plan arrived in #581 |
| Pain: unspiked risks → late `needs-human` | **Partially confirmed** | 11/17 episodes late, but ~5 trace to unspiked risk (the VM-side transport, launch-path wiring, R2.2, component ownership) vs ~6 to framework failures (quota, engine crash, stale labels); the single worst unspiked-risk hit (the attach protocol, 34.2 h) landed at the 25% mark |
| Surprise: spike workflow | **Partially confirmed** | fast + plan-folded; but #486 partial+erroneous (human fix #490) and #511 only existed because the risk was missed up front |
| Surprise: PR scope & size | **Scope confirmed, size refuted** | clean 1:1 task→PR; median 694 net (target ~400), three PRs >1300 carried the heaviest review loops |
| Surprise: well-defined plan | **Partially confirmed** | structurally excellent; needed an immediate human split of Task 1.2, missed integration wiring entirely, two mid-run re-scopes |

---

## 8. What to improve (prioritized; each maps to a detection-gap-matrix row and open spectacles issues)

**P0 — correctness/integrity (blocks trusting merges):**
1. **Ship the base-agnostic net-diff-vs-main guard as a required, re-run-on-push check** (spectacles #326; subsumes #317). This run added two more recurrences (#491's doc deletion — merged and never restored; #556's revert bundle). Also *fix the existing revert guard's environment* (full fetch + credentials) — a guard that always answers INCONCLUSIVE is absence with extra steps.
2. **Demoability gate**: `sdd:done` requires an *executed* end-to-end proof — a committed test-plan-style artifact whose run is a check, not prose. Add a proof-artifact *delivery* audit at validate time (deterministic: grep merged diffs for `#[ignore]`, env gates, `required-features` vs. the spec's declared proofs). New issue; extends #256/sdd-gates.
3. **Fix `SDD_STATUS` unset-coercion** (one-line wrapper fix; new spectacles issue). Every "found by human watching" failure in this run had a dead status surface behind it.

**P1 — the two loops that consumed the operator:**
4. **Review-loop convergence contract** (#311/#327): per-thread close requires "Fixed in `<sha>`" or a rebuttal; re-review only the diff-since-last-pass; finding fingerprints deduped across pushes *and across sibling PRs of the same tracker* (the #537-revert recurrence). Fix reaction semantics on cancelled runs (#310).
5. **Recovery that recovers** (#320): model quota exhaustion as *retriable-later* (respect the window, don't burn attempts in 24 min), reset labels on timeout kills, allow monitor re-dispatch to fire while `needs-human` is present when the cause is infrastructural, and make `/execute` on a stranded task always produce either a run or a visible refusal reason.
6. **Plan must emit integration**: a mandatory per-feature "wiring/e2e demo" task (or per-unit integration criterion in Affected-areas) so the #542-class seam is owned before dispatch.

**P2 — inputs and sizing:**
7. **Adversarial evidence standard for the assumption ledger** (C1): an entry citing only the spec cannot be "settled"; unvalidated mechanisms on the critical path must spike before materialization (the spike *workflow* is the proven asset here — point it at the right targets).
8. **Sizing ceiling** to pair with the ADR-0026 floor (median 694, max 1765; the three >1300 PRs carried the worst loops); split-at-PR-time guidance.
9. **Gate/CI parity** (#312/#318): commitlint + consumer lanes (`--locked`, feature-matrix builds) in the Pre-PR gate; both bit again this run.

**P3 — hygiene:** stale `needs-human` auto-revalidation on each push; route rejections must leave a visible trace on the item (silent route declines cost several of the 23 manual `/execute`); quota/window telemetry on every engine failure.

Items 1–3 are the eval-agent's first customers: every metric in this report was computed from API state after the fact; the eval agent's job is to compute them *during* the run (spec follows separately, per the engagement plan).

---

## Appendix A — needs-human episodes (17)

| # | Issue | Applied | Dwell h | Run position | Cause class |
|---|---|---|---|---|---|
| 1 | 478 | 06-20 03:33 | 1.8 | 4% | spike boundary decision (design-intended) |
| 2 | 495 | 06-20 06:34 | 12.8 | 6% | protected-path gap + quota-class engine failures |
| 3 | 478 | 06-20 08:02 | 11.3 | 8% | mirror of #495 |
| 4 | 478 | 06-20 19:43 | 5.5 | 17% | monitor re-escalation |
| 5 | 496 | 06-21 04:55 | 34.2 | 25% | unspiked the network-switch attach protocol (→ spike #511) |
| 6 | 478 | 06-21 05:51 | 33.3 | 26% | mirror (496/497/498 strand group: dispatch gap, 60 m timeout, engine crash) |
| 7 | 478 | 06-23 03:13 | 1.0 | 64% | usage-window quota |
| 8 | 526 | 06-23 03:30 | 0.6 | 64% | hardware-gated proof unverifiable + protected ci yml |
| 9 | 499 | 06-23 06:13 | 15.5 | 66% | quota, then real plan gap (R2.2 decision) |
| 10 | 500 | 06-23 06:22 | 7.8 | 67% | sdd-spec engine crash + mechanism re-scope decision |
| 11 | 478 | 06-23 06:51 | 7.3 | 67% | mirror |
| 12 | 500 | 06-23 14:32 | 0.1 | 73% | residual |
| 13 | 478 | 06-23 14:46 | 0.3 | 74% | sdd-spec failure surface |
| 14 | 542 | 06-23 15:17 | 0.7 | 74% | switch-ownership contradiction (operator decision) |
| 15 | 478 | 06-23 19:32 | 2.2 | 78% | monitor re-escalation of 499 |
| 16 | 499 | 06-23 22:44 | 0.2 | 80% | re-scope ack |
| 17 | 550 | 06-24 04:23 | — (never cleared) | 85% | fastpath residual; task done, label orphaned |

Total dwell 134.5 h (episodes overlap); median 3.8 h. 4 episodes ≤25% mark, 11 after 50%.

## Appendix B — per-PR review forensics

| PR | net | auto-revise | CodeRabbit reviews | review comments | 👎 on comments | human inline comments |
|---|---|---|---|---|---|---|
| 507 | 79 | 0 | 0 | 2 | 0 | 1 |
| 521 | 253 | 1 | 1 | 6 | 5 | 0 |
| 522 | 694 | 3 | 1 | 27 | 23 | 7 |
| 525 | 1351 | 3 | 4 | 42 | 41 | 4 |
| 537 | 196 | 2 | 1 | 19 | 15 | 0 |
| 546 | 901 | 3 | 3 | 23 | 18 | 3 |
| 547 | 423 | 1 | 1 | 17 | 14 | 0 |
| 554 | 944 | 3 | 6 | 24 | 19 | 3 |
| 555 | 137 | 1 | 1 | 1 | 0 | 0 |
| 556 | 1504 | 2 | 1 | 66 | 50 | 2 |
| 561 | 1765 | 2 | 8 | 28 | 21 | 1 |

Gate-passed-then-CI-failed: #507 (`build-macos`, `clippy`), #525 (KVM e2e lane); commitlint bit #554 (#312 class). Red `sdd-execute-*/agent` checks on commits of 521/522/525/547/555/556 are concurrency-cancel/crash noise — misleading signal (#310 class).

## Appendix C — cost

Attributable to the #478 tree, June 19–24 (lower bound — artifacts for a few runs, e.g. task #500's spec-crash era, had already expired):

| Workflow | Runs (with artifacts) | Effective tokens |
|---|---|---|
| sdd-execute-sonnet | 25 | 24.5M |
| sdd-execute-opus | 16 | 16.4M |
| sdd-review | 14 | 13.0M |
| sdd-validate | 20 | 11.0M |
| sdd-spec | 9 | 10.4M |
| sdd-triage | 5 | 5.9M |
| sdd-execute-haiku | 1 | 0.08M |
| **Total** | **90** | **81.2M** |

Composition: 73.6M cache-read + 6.6M cache-write + 0.94M output + 44k fresh input. Waste share: 10 non-success runs carrying 12.1M effective (~15%) — crashes, concurrency cancels, quota kills. Per net line kept (8,265): ≈9.8k effective tokens (≈114 output tokens). The evaluation/review half (review+validate = 24.0M) cost more than either execute tier individually — the convergence loop is a first-class cost center, consistent with its role as the run's throughput bottleneck.

Attribution: agent artifacts (`agent_usage.json` for pre-06-19 runs; the engine result record in `agent-stdio.log` post-migration), joined run→tree via prompt targets. "Effective tokens" = input + output + cache-read + cache-write (raw traffic; the AWF 25M rail weights cache reads lower). Baselines for comparison: the pilot-era dead triage run alone burned ~25M effective (spectacles #271); pilot PRs were 70–98 net lines.

## Appendix D — method

Evidence bundle: full issue-tree timelines (label events with actors), all comments incl. minimized flags (GraphQL), all spec/arch/sdd + remediation PRs with reviews/threads/diffs/check-runs, 16k workflow runs June 15–24, and per-run agent artifacts, harvested via `gh` API. Deterministic metrics computed by script; hunk classification of #581/#589 and R-ID delivery audit performed per-file against the spec and every pipeline diff, cross-checked against issue/PR comment streams. Numbers marked ≈ are bounded by artifact retention and run-list pagination limits.

## Addendum (2026-07-02): spec transcription drift — the generated spec contradicted its source's topology

Operator-supplied evidence from remediation PR #589 (a spec-amending commit
inside the remediation), strengthening §6c:

The spec-generation step did not just transcribe unvalidated hypotheses —
it **inverted the source document's topology**. The source is explicit that
the daemon is *not* on the internal switch and that host→sandbox access
goes through published loopback ports; the generated spec wrote, as
normative requirements (R3.1/R3.3/R4.4 and a proof artifact), that
hostnames resolve to switch addresses reached *via the switch* — routes the
daemon could never take under the source's own deployment topology.

Nothing in the pipeline caught it: the ledger was built *on top of* the
generated spec; validate/review checked implementations against the drifted
R-IDs, so they validated conformance to a contradiction; the human spec-PR
review at hour 3.6 added missing scope but did not cross-check the source's
diagrams. The contradiction surfaced during human remediation ~9 days after
the spec merged, and the fix was an 18/−11 amendment **to the spec itself**
inside the remediation PR.

Two consequences for the analysis above. First, part of the §4a
"specced-but-not-delivered" ledger shifts: some remediated routing was a
faithful implementation of drifted requirements — a spec-input defect, not
factory execution. Second, the C1 verdict gains a class: **generation-time
source infidelity**, to which every downstream stage is blind by
construction because each treats the generated spec as ground truth. The
eval-agent rubric gains a judge item for it (RB-input-3: generated
requirements cross-checked against the source document at the spec
boundary, where a correction is cheap and everything downstream inherits
it).

### Root cause of the drift (investigated 2026-07-02)

Traced through the spec-generation run's full transcript, git pickaxe on the
spec file, and the source document. Four stages:

1. **Origin — generation wrote *both* models, three lines apart.** The
   initial generated spec was internally contradictory from birth: one
   requirement resolved local hostnames to an internal-switch address
   (wrong), while the adjacent requirement correctly said requests route
   through the published loopback port. The transcript proves the agent read
   the full source in one pass (retrieval was not the cause), but its
   visible reasoning modeled only the *remote* mesh case — where
   switch-address reachability is correct — and the name-resolution
   *mechanism* question; the local host→sandbox path is never engaged
   ("published", "not on the switch" appear zero times in its thinking).
   The source set the trap: its requirements-level use-case diagram reads
   "DNS resolves → sandbox (own IP via the switch)", while the correction
   (daemon off-switch; access via published loopback ports) lives ~200
   lines later in an implementation overlay, with the tension never
   flagged. The generator sampled a different topology model per
   requirement and ran no reconciliation pass over its own output.
   **Root cause at origin: a dual-model source × a single-pass generator
   with no cross-requirement or source-topology consistency check.** Not
   hallucination — both sentences have direct source antecedents; the
   missing piece is the join.
2. **Survival — no stage checks spec semantics.** The contradiction passed
   the structural spec gates (units, R-ID grammar, proof presence), the
   hour-3.6 human `/revise` (scope-focused), the architecture/ledger stage
   (which cites the generated spec as evidence, institutionalizing it as
   ground truth), and the third-party reviewer (zero reviews on the
   docs-only spec PR).
3. **Spread — execution harmonized toward the wrong pole.** During the
   operator-directed Unit-3 mechanism re-scope, the execute agent rewrote
   the correct requirement **and deleted the only correct sentence**,
   aligning it with the wrong one — predictable, since the wrong
   requirement was the normative-looking anchor ("shall resolve to…") and
   the correct phrase was welded to the mechanism sentence being replaced.
   The operator's directives specified mechanism and naming, not routing
   target, so nothing in the loop contested it. The vector — **an
   implementation PR editing a merged spec** — has no guard analogous to
   the plan-fidelity guarantee of ADR 0010.
4. **Correction — only when routing became load-bearing**, 11 days after
   origin, as a spec amendment inside the remediation PR.

What would have caught it, and when:

| Check | Stage caught | Cost |
|---|---|---|
| Internal-consistency pass on the generated spec (requirement-vs-requirement contradiction) | origin, pre-PR | needs no source document at all |
| Source-fidelity judge (RB-input-3) over diagrams/topology sections | origin, spec boundary | one judge pass |
| Spec-edit tripwire: implementation PR touching a merged `docs/specs/**` file re-triggers both checks | spread, deterministic | one changed-files join |

Encoded in the eval-agent spec (collector R1.4 spec-edit tripwire) and
rubric (RB-input-3, extended). The general lesson: the pipeline has a
fidelity guarantee plan→tree (ADR 0010) but none source→spec or
spec→spec-edit, and every downstream stage compounds whichever model the
spec asserts.
