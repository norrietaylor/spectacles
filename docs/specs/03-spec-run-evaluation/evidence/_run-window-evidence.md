# Retro Evidence Backbone — SDD Agent-Factory Run (June 2026, consumer tracking issue #478, networking feature, full-pipeline path, v0.3.0-era)

All issue numbers refer to the spectacles repository unless noted. The pilot target is referred to only as "the consumer repo." Data reflects state as of 2026-07-01.

---

## 1. Run-window failure timeline (June 15–24)

Chronological by `created_at`. One line each: date, issue, stage, what happened, consumer impact.

- **2026-06-15 · #271 · triage** — sdd-triage phase-A run died on the AWF hard rail: "429 Maximum effective tokens exceeded (25096706.10 / 25000000)"; 2.5M input tokens over 33 calls, per-call context 33K→122K, mid-run cache break, zero safe output (`{"items":[]}`). Impact: hard stall of the feature's triage plus ~25M effective tokens wasted.
- **2026-06-15 · #272 · spec/triage** — over-decomposition persisted a layer up from #252: "Demoable units land at ~100 net lines when an engineer's natural PR is ~500"; "Sub-issue count = 2 + N + M," each task paying the full per-task pipeline cost. Impact: structurally inflated token/CI/review cost per net line shipped. Still open (Lever 4).
- **2026-06-18 · #283 · installer/infra** — after the Copilot→Claude engine migration, all 10 agentic wrappers still passed `COPILOT_GITHUB_TOKEN`; undeclared secret to a reusable workflow is a hard `startup_failure` ("`sdd-spec`, `sdd-triage`, `sdd-validate` all `startup_failure` in ~1s"). Impact: total pipeline stall on every main-pinned install; pure-actions wrappers masked the breadth.
- **2026-06-18 · #285 · spec/MCP infra** — unconfigured `DISTILLERY_MCP_URL` resolved to empty string; gateway schema validation exited 1 before the agent ran ("the whole pipeline is dead at `sdd-spec`"). Impact: hard stall at sdd-spec for any consumer without Distillery; first fix attempt had to be retracted (compiler reuses the URL expression in the firewall allowDomains).
- **2026-06-18 · #287 · execute** — **safety-critical**: SDD PR #463 on the consumer repo (branch sdd/453-net-module — the networking module) regenerated connection.rs from a stale base and silently reverted merged fix #449, reinstating `.await.unwrap()` where `?`-propagation had been added; "In the guest, `<daemon>` is pid-1, so a panic here kills init and takes down the whole VM." Impact: red CI, manual restore (ab7eca9a); a pid-1 VM-killer had CI not caught it.
- **2026-06-18 · #289 · dispatch** — fast-path /approve never dispatched: route job lacked `pull-requests:read`, the 403 was swallowed, the job stayed green, and "the spec PR merges but the implementation is never dispatched." Impact: fast path dead for every consumer; expensive diagnosis because the failing job succeeded.
- **2026-06-18 · #292 · dispatch** — next 403 in the same chain: fast-path dispatch used `workflow_dispatch` (needs App `actions:write`, absent from documented install; contradicts ADR-0014). Impact: fast path still dead on any documented install; docs-only fix leaves the ADR-0014 contradiction latent.
- **2026-06-18 · #294 · process/UX** — no acknowledgment between a slash command and first agent output: "They re-comment, assume it failed, or wait blind." Impact: duplicate commands and blind waiting on every command round-trip (enhancement, fixed with deterministic ack reactions).
- **2026-06-18 · #295 · triage** — "Confirmed 15/15 startup_failure on a staging consumer": plan/materialize wrapper jobs granted `pull-requests: read` while the called locks' nested jobs need `write`; workflow rejected at load, no logs/jobs. Impact: full path dead at spec→triage; declared v0.3.0 release blocker.
- **2026-06-18 · #298 · spec/derive/spike-reentry** — two more instances of the #295 class: spike-reentry "fired startup_failure on every issue close/unlabel — 20/20 on a staging consumer"; "/derive-spec was dead." Impact: silent dead surfaces plus failure noise; contract gate blind spot fixed (fa7df42).
- **2026-06-19 · #300 · triage** — App-applied `sdd:triage` never activated the agent (no `roles: all`; gate saw actor `spectacles-bot[bot]`, permission "none"); "run reports success — a silent no-op." Impact: full path silently stalled at spec→triage; human re-label required at every transition.
- **2026-06-19 · #301 · dispatch** — close-event cascade hardcoded a 2-hop walk vs ADR-0028's collapsed 1-hop trees: "Closed issue #36 is not a task sub-issue closure (walked 1 hops); ignoring." Impact: full-path E2E tracker (consumer/staging #29) sat with all work merged but not `sdd:done` until a manual /dispatch.
- **2026-06-19 · #303 · execute/dispatch** — haiku-tier fast-path execute concluded "success" with `agent_output.json = {"items":[]}`; per transcript it decided nobody had asked it to do anything and "replied 'What would you like to help with?'" Impact: fast-path implementation no-oped, issue stranded at `sdd:in-progress`, full run's tokens wasted; tier floored at sonnet.
- **2026-06-22 · #308 · execute (concurrency)** — re-triggered /execute run cancelled at activation by an unrelated same-tier task's PR events: "route → success / ack → success / activation → cancelled"; "touching one task's PR can kill another task's freshly-dispatched run." Impact: silent stranded task, no auto-recovery, manual re-bump.
- **2026-06-22 · #310 · execute/status** — concurrency-cancelled revise runs stamped thumbs-down on consumed review comments: "nearly every review comment on a PR… carried a [thumbs-down] reaction, reading as 'these findings failed'" while the PR progressed normally. Impact: misleading signal that also camouflages real failures. Open.
- **2026-06-22 · #311 · execute/review** — revise closes no loops: the resolver "blanket-resolves the App bot's own unresolved threads… resolves even findings that were never addressed — silently hiding them"; worked example: 7 findings needed manual triage (3 valid, 4 already fixed), red for ~an hour until manual takeover. Impact: throughput bottleneck absorbed by the maintainer on every review-fix PR of the cascade. Open.
- **2026-06-22 · #312 · execute** — Pre-PR gate omits consumer commitlint: "A 104-char commit header (`header-max-length` = 100)" and a subject-case violation each "left the PR `BLOCKED` on `commitlint` until a human reworded the offending commit (a force-push history rewrite)." Impact: merge-blocking rework, twice in one pilot run. Open.
- **2026-06-22 · #313 · dispatch/review** — human /revise silently gated behind `needs-human`: "No execute dispatches. The `/revise` sits silently behind the label" — despite validate reporting no blockers. Impact: every post-hand-off revise needed a manual label-clear with zero feedback. Open.
- **2026-06-22 · #314 · validate** — validate attempted egress-dependent builds in a sandbox with "no toolchain and no registry egress," classifying firewall blocks as blockers: the recurring "PR keeps getting `needs-human`, clear it, it comes back on the next push" loop. Impact: label churn and stalls with no real defect. Open.
- **2026-06-22 · #315 · distillery/status** — every scheduled distillery-sync run failed: Haiku read its own prompt as a spec, "`num_turns=1`, zero tool calls," asked a clarifying question headless; the status issue silently went stale (last updated 06-18, failures from 06-20). Impact: knowledge store stopped syncing; failure hidden from the status surface.
- **2026-06-22 · #317 · spec** — **safety-critical near-miss**: an sdd-spec derive PR "changed +3125 / -2665 across ~30 code files in addition to the spec document," gutting merged work (composer.rs -2188, RESOLUTION.md -194) behind an innocuous spec-derivation title. Impact: human force-push recovery; would have silently reverted merged code. Open.
- **2026-06-23 · #318 · execute** — Pre-PR gate ran cargo without `--locked`; a Cargo.toml dep change without lock regen shipped a PR that failed the consumer's `--locked` lane ("error: cannot update the lock file ... because --locked was passed" exit 101). Impact: already-red PR, misleading failure signature, human rework.
- **2026-06-23 · #320 · dispatch/execute/monitor** — "Two next-layer tasks both hit the 60m timeout, stayed `sdd:in-progress` with no PR, and could not be re-dispatched — a manual `/execute` no-op'd"; monitor recovery "just burns its 3 attempts and escalates to `needs-human` — a dead end." Impact: hard stall of two networking-feature tasks; operator hand-edited labels. Open.
- **2026-06-23 · #324 · distillery/status** — duplicate status issue plus a numberless `update_issue` ("Target is \"*\" but no item_number/issue_number specified") marked otherwise-successful sync runs red intermittently. Impact: false-red runs eroding trust in run status; human dedupe required. Open.
- **2026-06-24 · #326 · execute/validate/review** — **safety-critical class**: stale-base SDD PRs silently deleted/reverted out-of-scope merged work, "observed three times on the consumer pilot" (deleted another feature's merged spec doc; reverted a merged crate-split refactor; re-introduced a fixed bug). "Each was caught only because a human read the net-diff and hand-restored the file. The framework did not block the merge." Open.
- **2026-06-24 · #327 · review/validate** — full base..head re-scan on every push: "the same already-fixed findings re-surfaced run after run (re-resolved by hand each time)"; auto-revise churned PR heads, compounding CI/token waste; only stable state is "0 unresolved threads + green CI." Open.
- **2026-06-24 · #328 · spec (adoption)** — derive-spec offer copy reads as a callout ("you skipped a step") on human contributors' PRs on the consumer repo. Impact: social/adoption cost, no functional breakage. Open (fix in-flight, d9e6fc6).

Filed in-window but not run failures: #275 (sdd-derive coverage-gap enhancement, 06-17), #307 (bot-filed spec-debt surface, 06-22 — the ADR 0027 backstop working, ~4,400 unspecced lines in the pipeline's own repo), #322 (premise outdated; v0.3.0 already correct, 06-23).

---

## 2. Failure taxonomy

All 39 issues, grouped by category.

### permission-contract — #259, #269, #289, #292, #295, #298, #300

**Pattern:** a mismatch between what a job/token/actor is granted and what the code it runs actually needs — made invisible by error-swallowing (`#259`, `#289`: 403 → default-deny in a green job), by load-time rejection with no logs (`#295`, `#298`: caller job permissions < callee lock nested-job permissions), or by activation-gate semantics (`#300`: App actor fails `roles` check, run reports success). #292 is ADR drift (fast-path never migrated off `workflow_dispatch` per ADR-0014); #269 is the config-side sibling (consumer var silently re-models an agent).
**Status: fixed as instances; class partially guarded.** All seven closed (#269 not_planned — superseded by the Claude engine port, 6a0be81). The wrapper-lock contract gate now enforces secrets (#284-class) and caller>=callee permissions (fa7df42), but #292 was fixed docs-only — "the code still uses workflow_dispatch, so the ADR-0014 contradiction remains latent" — and no static API-call→scope lint exists yet.

### safety/code-integrity — #287, #317, #326

**Pattern:** an agent writes from a base that trails origin/main (stale checkout/regeneration or `git add -A` scope capture) and the resulting PR silently deletes or reverts merged work; GitHub's 3-way merge raises no conflict, the pipeline raises no flag, and the bot's own description masks the damage.
**Status: OPEN as a class.** #287 fixed with a point guard in the execute Pre-PR gate (PR #288); #317 (spec-side variant) and #326 (the generalized net-diff guard, three recurrences post-#287) are open. #326 states it directly: the prior fix "patched one instance without generalizing."

### state-machine/lifecycle — #257, #301, #313, #320

**Pattern:** the pipeline's event-driven state machine has holes — waits with no timeout (#257 CodeRabbit never reviews), transitions whose predicates encode stale structural invariants (#301's hardcoded `walked === 2` vs ADR-0028), labels that gate the very input they request (#313 human /revise behind `needs-human`), and optimistic labels with no failure-path reset (#320's permanent `sdd:in-progress` strand).
**Status: partially fixed.** #257 and #301 closed; #313 and #320 open — the two open ones are precisely the recovery paths (post-hand-off and post-crash).

### infra/config — #269, #283, #285, #314, #318

**Pattern:** configuration surfaces treated as consistent when they were not: incomplete migrations (#283 wrappers vs locks), optional consumer vars interpolated into schema-validated config (#285), consumer-overridable model vars (#269), gate commands not mirroring consumer CI flags (#318 `--locked`), and sandbox constraints not encoded in classifiers (#314).
**Status: partially fixed.** #283, #285, #318 fixed; #269 superseded; #314 open.

### prompt/model-behavior — #247, #258, #303, #315

**Pattern:** the compiled prompt and the model diverge: missing context assembly (#247 revise ignores PR threads), internally contradictory fragments where "the loudest stack-specific instruction won over the generic gate" (#258), and descriptive/procedural prompts that weaker tiers do not execute — haiku treating its directive as "all system context" and asking a question in a headless run (#303, #315).
**Status: fixed per instance; class recurring.** All four closed, but the haiku-fragility shape hit twice in five days (#303 → tier floored at sonnet; #315 → imperative reframe), with no compile-time contradiction lint or tier-capability gate yet.

### cost/context-efficiency — #252, #271, #327

**Pattern:** fixed pipeline overhead and unbounded context dominate delivered work: per-task PR overhead exceeding the diff (#252, "~25M tokens" for one triage), a mega-prompt loading all phases/tools every run until the 25M rail (#271), and stateless full re-review on every push (#327).
**Status: partially fixed.** #252 (ADR 0022) and #271 (invocation cap #270, prefetch #278, per-phase split #279/ADR 0029) fixed; #327 open.

### observability-gap — #254, #294, #310, #324

**Pattern:** the pipeline either emits no signal (no status surface #254, no command ack #294) or a wrong signal (#310 thumbs-down on consumed findings, #324 green work marked red by status bookkeeping). #254's framing generalizes: the gap "amplified every other failure class."
**Status: partially fixed.** #254 and #294 shipped; #310 and #324 open — both are false-signal defects in the very surfaces #254/#294 added.

### process-design — #255, #256, #272, #275, #307, #311, #312, #322, #328

**Pattern:** the pipeline's process model diverges from how the work actually flows: ceremony exceeding value (#255's 4 gates/2 days → operator abandonment), verification framework-guessed instead of repo-defined (#256), sizing floors absent (#272), forward-only spec coverage (#275, #307), merge-unblock sweeps instead of reasoned thread resolution (#311), commit policy unenforced in-loop (#312), wrong-tool fit (#322, premise outdated), compliance-toned contributor copy (#328).
**Status: partially fixed.** #255, #256, #275, #322 closed; #272 (Levers 1–3 shipped, Lever 4 open), #307, #311, #312, #328 open.

### concurrency/race — #308

**Pattern:** the execute wrapper's concurrency group was not strictly per-item across trigger types, so cancel-in-progress let cross-task same-tier events kill unrelated runs at activation.
**Status: fixed** (d641900, per-item keying) — but its downstream interaction effects remain open (#310's false thumbs-down, #311's cancelled-mid-revise churn).

---

## 3. What the run cost in framework fixes

**Issues filed during the run window (2026-06-15 → 2026-06-24): 30 of the 39** (#271, #272, #275, #283, #285, #287, #289, #292, #294, #295, #298, #300, #301, #303, #307, #308, #310, #311, #312, #313, #314, #315, #317, #318, #320, #322, #324, #326, #327, #328).

**Severity distribution (impact-based; only #287 carries an explicit `severity:high` label):**

- Safety/code-integrity (silent reversion of merged work): **3** — #287, #317, #326 (#326 alone records three live recurrences)
- Hard stall / pipeline-or-path-dead: **13** — #271, #283, #285, #289, #292, #295, #298, #300, #301, #303, #308, #313, #320
- Degraded operation / rework / false signals: **9** — #272, #310, #311, #312, #314, #315, #318, #324, #327
- Non-failure (enhancement, preventive, backstop-working, outdated premise, tone): **5** — #275, #294, #307, #322, #328

**startup_failure / permission-contract class:** 6 in-window issues — #283 (wrapper/lock secret contract; all 10 agentic wrappers dead on main-pinned installs), #289, #292, #295 ("15/15 startup_failure"), #298 ("20/20"), #300. Three of these (#283, #295, #298) are literal GitHub `startup_failure` at workflow load; the whole family reached main because the contract gate initially checked neither secrets nor caller>=callee permissions. Note the diagnostic tax of the sequential-403 chain: #289's fix exposed #292, whose fix exposed #295, whose class sweep found #298, and full App-driven operation then exposed #300 — five contract failures peeled one at a time across 06-18/06-19.

**Silent-failure class (zero operator-visible signal at failure time): 11** — #287 (pipeline raised no flag; only consumer CI went red), #289 (swallowed 403 in a green job), #292 (merged spec PR, then nothing), #300 ("run reports success — a silent no-op"), #301 (route decline only in logs), #303 ("success" with empty output), #308 (stranded, "no run, no PR, no `needs-human`, no `[aw]`"), #313 ("total silence"), #317 (masked by innocuous PR title), #320 (no reset, no escalation that works), #326 (green checks on a revert). #315 aggravates the class: the status surface itself went silently stale while runs failed.

**Still open as of 2026-07-01: 13 of 30 window issues** (43%) — #272, #307, #310, #311, #312, #313, #314, #317, #320, #324, #326, #327, #328. These are all 39 issues' open set; nothing pre-window remains open. Notably, **2 of the 3 safety-critical issues are open** (#317, #326), and the open set clusters in the revise/review convergence loop (#310, #311, #313, #327) and lifecycle recovery (#320).

**Fix throughput:** roughly 20 framework fix PRs/commits landed in or immediately after the window against these issues (#270, #273, #276 + follow-ups, #278, #279, #284, #286, #288, #290, #293, #296, #297 + a0c2ee7, #299 incl. contract-gate fa7df42, #302, #304, #305, #309, #316, #323/d395045, 4e3559a), plus four ADRs (0026–0029). Direct waste on the consumer/staging side includes one ~25M-token dead triage run (#271), a wasted dispatch+execute run (#303), every scheduled distillery-sync run from 06-20 (#315), 15/15 + 20/20 red staging runs (#295, #298), and sustained maintainer manual triage across the review cascade (#311, #327).

---

## 4. Safety-critical incidents

These three dominate a correctness-first evaluation: the failure mode is not a stall but the agent **destroying merged work with green-looking artifacts**.

### #287 — SDD pipeline silently reverted merged fix #449 (guest pid-1 panic-safety) in PR #463 — *closed, severity:high*

- **What happened:** SDD-generated consumer PR #463 (branch `sdd/453-net-module` — the networking module itself) regenerated `crates/<daemon>/src/connection.rs` from a base that did not carry merged fix #449, reverting `Connection::from_socket` from `Result<…, ConnectionError>` + `.await?` back to a bare tuple + `.await.unwrap()`. "In the guest, `<daemon>` is pid-1, so a panic here kills init and takes down the whole VM." The deleted code included the explanatory safety comment. "Nothing in the pipeline flagged that the generated diff reverted hunks from an already-merged commit."
- **Root cause:** regeneration from a working base trailing origin/main, with no guard diffing against origin/main — "the diff looked clean against the stale base."
- **Impact & recovery:** red CI (build/clippy/test) on consumer PR #463; human restore commit ab7eca9a. Had CI not caught it: a client that connects then drops kills init and the whole VM.
- **Fix:** PR #288 — merged-change revert guard in the execute Pre-PR gate that "blocks the PR when the branch is behind origin/main AND touches a file origin/main has independently advanced — the exact silent-revert signature"; remedy is rebase (silent revert → visible conflict) or needs-human.
- **Detection was luck:** red consumer CI plus a human diffing against origin/main instead of the stale base.

### #317 — sdd-spec opened a non-docs-only PR: derive commit reverted merged files and added a code refactor — *OPEN*

- **What happened:** a spec-derivation PR's single commit "changed **+3125 / -2665 across ~30 code files** in addition to the spec document": "`crates//src/core/compose.rs` **+1758** (new code) … `crates//src/client/composer.rs` **-2188** (gutted) … `crates//docs/RESOLUTION.md` **-194** (deleted)," plus Cargo churn and file moves. The bot's title/report described only a spec derivation, masking the corruption.
- **Root cause:** the derive commit captured the full working-tree diff (effectively `git add -A`) instead of only `docs/specs/**`; where base was ahead, divergence inverted into reverts. No docs-only assertion existed before publishing. Explicitly the spec-side analogue of #287.
- **Impact & recovery:** "Recovery required a human to force-push the branch back to `base + spec-doc-only` (the bot reported it as deriving the spec from the source issue, so the corruption was not obvious from the title)." Near-miss: merge would have silently reverted recently-merged code across ~30 files.
- **Fix state:** open. Proposed: branch from current default HEAD, stage only `docs/specs/**`, hard docs-only diff assertion before publishing.

### #326 — Net-diff guard: stale-base PRs silently delete/revert out-of-scope merged work — *OPEN; the generalization the class needs*

- **What happened:** three separate live recurrences on the consumer repo: "a PR deleted a merged spec document for a **different** feature (its branch predated that spec's merge)"; a PR reverted a merged crate-split refactor; a PR re-introduced a previously fixed bug by regenerating a file from a base lacking the fix. GitHub's 3-way merge honors the branch's explicit deletion "with no conflict and no signal."
- **Root cause:** no base-agnostic net-diff-vs-current-main guard. "#287 patched one instance without generalizing, #317 covers only the sdd-spec derive variant, and `sdd-validate` gate 2 **does detect** out-of-scope deletions — but emits a **Warning that escalates to `needs-human`**, not a blocking check, and never restores."
- **Impact:** "Each was caught only because a human read the net-diff and hand-restored the file. The framework did not block the merge." The issue calls this "the highest-severity class in the run: merged features/fixes would be erased with green checks."
- **Meta-finding for the retro:** #326's own eval signal notes that "an eval agent should flag when a closed 'fixed' issue (#287) shares a failure fingerprint with new incidents, indicating a point fix where a guard was needed." The class recurred three times *after* #287 was closed.

**Correctness-first summary:** the integrity class was detected exclusively by red consumer CI or a human reading net-diffs; the pipeline itself never blocked one of these merges. The fully deterministic guard (`git diff origin/main...HEAD` deletions/reverts joined against declared files-in-scope, as a required status check) remains unshipped.

---

## 5. Detection-gap matrix

Consolidated from the `eval_agent_signal` fields. "Caught today by" reflects the recorded `detection_path` during the run.

| Failure class (issues) | Caught today by | Deterministic signal that would catch it | Inference signal (if needed) |
|---|---|---|---|
| Silent revert / stale-base integrity loss (#287, #317, #326) | Red consumer CI + human net-diff read; nothing in-pipeline | Merge-base-behind + origin/main-advanced-file check pre-PR; `git diff origin/main...HEAD` deletions/reverts joined vs declared files-in-scope, as a required check re-run on every push; docs-only changed-files assertion for spec-agent PRs; >500-line/>3-file tripwire on "spec" PRs; recurrence-fingerprint match against closed "fixed" issues | LLM judge on PR-diff-vs-origin/main: "does this PR delete or undo code introduced by merged commits?" (deleted safety comment + `?`→`.unwrap()` is a high-precision tell) |
| Wrapper/lock contract breaks → startup_failure (#283, #295, #298) | #89 E2E harness / red staging runs (no lint pre-merge) | Static CI lint: wrapper `secrets:` ⊆ lock's `workflow_call.secrets` ("a wrapper passing an undeclared secret is always a startup failure"); caller job permissions >= per-scope max over callee nested jobs (now fa7df42); runtime: any `startup_failure` conclusion / ~1s zero-job run on sdd-*, especially fan-wide across agentic wrappers while pure-actions ones pass | None needed — class is fully enumerable from YAML |
| Swallowed 403 / token-scope mismatch (#259, #289, #292, #300) | Human staging repro + log reading; failing jobs were green | Static map of every `github.rest.*` call in composite actions → required scope ⊆ job `permissions`; docs-as-contract lint vs `docs/sdd/install.md` (also flags ADR-0014 drift mechanically); log scan for "Resource not accessible by integration" inside jobs that concluded success; stranded-label joins (`sdd:approved` + merged spec PR, no `sdd:in-progress` in N min); run-shape: success with agent/safe_outputs all skipped after `pre_activation` (#300) | Flag fix PRs adopting an option the issue labeled "not recommended" against an ADR (#292) |
| Lifecycle stalls / stranded states (#257, #301, #308, #313, #320) | Human watching the run, every time | Bounded-wait invariant on every external wait (reviewer bot, CI, human gate) — e.g. 30-min CodeRabbit SLA; `sdd:in-progress` + no open PR + no queued/running execute run beyond 60m+slack; route-decline log marker "walked 1 hops; ignoring" on `## Task` bodies; run shape route=success/ack=success/activation=cancelled with no agent job; human /revise while `needs-human` with no keyed run in N min (actor-type discrimination); monitor /dispatch comments yielding zero run starts | None needed — pure API/timeline joins |
| Model-tier no-op / prompt-framing failure (#303, #315) | Human reading transcripts after red or hollow runs | Run conclusion "success" + `agent_output.json` items==[] on a run whose context promises an implementation; `num_turns == 1` and `tool_calls == 0` on any headless run; per-tier safe-output emission rate telemetry; status-issue `updated_at` older than last scheduled run start | LLM judge (or regex for "Please clarify"/trailing "?") over the final message of non-interactive runs; "treated the directive as system context" single-turn shape |
| Context/token burn (#252, #271, #327) | Human reading token bills; 429 hard rail post-hoc | Budget-fraction alerts (e.g. 50% of 25M); monotonic per-call context growth (33K→122K) with no plateau; cache_read reset mid-run; duplicate identical reads (same issue ≥3x); loaded-vs-called MCP ratio (Serena: 0 calls); calls-completed vs safe-output-buffer; per-PR review token/duration growing linearly with pushes while diff-since-last-review stays small; cost-per-net-line ("aic") trend | LLM comparison of consecutive review outputs for semantic finding duplication |
| Gate/consumer-CI parity gaps (#256, #258, #312, #318) | Red consumer CI after the PR was already open | Gate-pass-then-first-CI-fail rate join per stack; transcript must show verify.sh / package-manager / toolchain invocations before PR creation; flag Cargo.toml (manifest) diff without matching lock hunk, or run `cargo fetch --locked` as a check; flag-parity linter (gate missing `--locked` / `--frozen-lockfile` the consumer enforces); pre-push commitlint of bot commit subjects against discovered config; "bot push → commitlint failure → human force-push" timeline shape | LLM lint over compiled locks for contradictory directives (generic gate vs stack fragment) plus fact-check of sandbox-capability claims against the firewall allowlist (#258) |
| Missing revise context / non-converging review loop (#247, #311, #327) | Human re-transcribing feedback / manual per-thread triage | Revise runs with zero comment/review fetch calls while unresolved threads > 0; GraphQL thread audit: bot-resolved threads whose last comment is not a bot reply with a sha or rebuttal ("resolved-without-reasoned-reply > 0 means findings are being buried"); unresolved third-party threads with zero bot replies over N cycles; finding-fingerprint recurrence after resolution with no touch to the anchored region; needs-human oscillation > K per PR | LLM judge: does the revise diff address the unresolved comments; per resolved thread, does the closing reply actually validate or rebut ("Fixed in \<sha\>" contract) |
| False/missing operator signals (#254, #294, #310, #324) | Human field feedback / human noticing red bookkeeping | Time-to-first-ack per routed command (+ near-duplicate command pairs = retrying blind); reaction-vs-run join: thumbs-down backed by conclusion "cancelled" is a false failure signal; burst shape (≥2 thumbs-down same minute + one surviving revise run); exactly-one open "[distillery-sync] Status" issue invariant; agent/detection green + safe_outputs failed with "no item_number" signature; schema lint: every update-issue carries explicit issue_number; status-comment freshness vs last pipeline event | LLM judge of a PR's reaction trail vs run outcomes / thread state for signal-reality divergence |
| Over-decomposition / process ceremony (#252, #255, #272) | Human watching PR-to-overhead ratio; operator abandonment *was* the signal | Median task-PR net diff vs floors (100 vs 300/400); task count > ceil(total_diff / SDD_TRIAGE_MIN_TASK); sibling small PRs on same file set; single-task-Unit fraction via sub-issue tree walk; green sdd/ PRs closed unmerged by a human (+ superseding human PR) = abandonment; gate-latency ratio (>50% wall-clock in human-gate waits); triage token threshold (>10M for a sub-500-line feature) | LLM/static dead-code judge per task PR: new exports with zero in-repo call sites and no consumer wired in the same PR |
| Config interpolation / model drift (#269, #285) | E2E harness; #248 incident review | Lint: every `${{ vars.* }}` in an MCP url paired with an installer default or compile guard; gateway-schema log signature ("is not valid 'uri'") before agent step = config death, not agent failure; corrupted allowDomains grep (`${{` + truncated scheme); resolved-model-per-run (OTLP) diffed against a committed per-agent manifest; per-agent token-cost step-change alert | None needed |
| Validate false blockers (#314) | Human correlating label flaps with firewall-blocked build logs | Egress-denial log markers co-occurring with needs-human safe-output in the same validate run (any co-occurrence = policy violation); needs-human applied→removed→re-applied across pushes with no new findings; identical inputs yielding "No Blockers" vs needs-human flags the nondeterminism | None needed |
| Spec coverage / adoption (#275, #307, #328) | Automated (#307 — sdd-derive's own scan; the one machine-detected class) / human tone judgment | Lineage audit: merged non-bot PR ≥ SDD_SPEC_MIN_UNIT (400) without sdd/ lineage or spec reference; offer-comment idempotency (exactly one + needs-spec marker); staleness: open batch issue with unchecked items and zero /derive-spec events after N days; unspecced-lines ratio per release window (~3354-line outlier threshold); post-sync idempotency/doctype/chunk assertions (#322) | LLM tone-judge over contributor-facing bot copy (leads with value, no fault-list, cost-free decline); uptake/negative-reaction telemetry on offer comments |

**Headline for the eval spec:** during the run, exactly **one** class was caught by automation the framework itself owned (#307's derive scan). Everything else was caught by red consumer CI (post-damage), the #89 E2E harness (staging), or a human watching. Nearly every row's primary detector is deterministic — timeline joins, run-shape checks, static lints, diff properties — with inference needed only as a backstop.

---

## 6. Baseline expectations (from the pre-run design issues #247, #252, #254, #255, #257, #272)

The framework's own pre-run history sets explicit yardsticks the networking run should be measured against.

**Task sizing and decomposition (#252, #272):**

- The pre-run standard from #252: "A feature whose total scope is ~250 lines across a handful of files produces 1–2 tasks, not 6." Its live counter-example: "These three are a single cohesive change (~265 lines) split across three task issues, three agent runs, three PRs, three CI cycles, three reviews, three merges."
- #272 raised the floors mid-window: "Demoable units land at ~100 net lines when an engineer's natural PR is ~500" — ADR 0026 set a ~400-net-line demoable-unit floor (SDD_SPEC_MIN_UNIT), SDD_TRIAGE_MIN_TASK moved 300→400, and ADR 0028 collapsed single-task Units. Yardstick: median merged sdd PR net diff should sit near 400, not ~100; single-task-Unit count should be zero; sub-issue arithmetic ("Sub-issue count = 2 + N + M") should be minimal for the feature's size.

**Per-task PR overhead (#252, #272):**

- Every task pays a fixed cost: "one sdd-execute run, one PR, one CI pipeline, one sdd-validate, one sdd-review, one merge" (#272), with review adding "up to SDD_MAX_REVIEW_ITERATIONS revise cycles" (#252). Cost yardsticks from #252: "The triage pass that produced the split consumed ~25M tokens; each `sdd-execute` run adds ~1M+ on top" — and #272's acceptance section demands the pipeline-cost ratio "(agent runs + CI pipelines + review passes) / net lines merged" be trended as an `experiments:` entry. The retro should compute exactly that ratio for issue #478.

**Ceremony vs value / the abandonment threshold (#255):**

- The known failure ceiling: "a feature an operator would ship as one PR took ~2 days across 4 human gates (merge spec PR, merge architecture PR, `/approve`, `/dispatch`), produced 6 task sub-issues, and the operator abandoned the pipeline midway — closed green task PRs and consolidated by hand, because one task PR shipped a primitive with no consumer wired up ('dead code')."
- Yardsticks shipped pre-run: SDD_AGILE_MAX "default ~800" for the single-PR path; a collapsed single /approve gate; gate-latency ratio (>50% of wall-clock in human-gate waits = ceremony overload); green agent PRs closed unmerged by a human = trust-loss event; no task PR should ship exports with zero in-repo call sites. Also the acknowledged trade-off: "One ~800-line PR is harder to review than three 250-line PRs."

**Status surface and operator legibility (#254):**

- Pre-run diagnosis: "State is scattered across labels, sub-issue trees, PR checks, and Actions runs — 'buried in a CI job somewhere'"; "Operators want one surface to check in with and nudge, like a single agent session." sdd-status shipped before the run (ADR 0023, ~500–650-line action).
- Yardsticks: exactly one status comment per tracking issue whose last-updated footer is newer than the last pipeline event; measurable interval between the pipeline entering a human-action-required state and the first human event. The run-window evidence (#300, #303, #308, #313, #315, #320 all found by "human watching") measures how far reality fell short.

**Bounded waits on external dependencies (#257):**

- The pre-run invariant: no open wait without an SLA — "head-commit age ≥ `SDD_CODERABBIT_STALL_MIN` (default 30 min) AND no review or comment by `coderabbitai[bot]` since that commit" triggers bounded nudges ("cap `SDD_CODERABBIT_NUDGE_MAX` (default 2) per head sha"), then needs-human. Yardstick for the retro: every wait state in the networking run (reviewer bot, CI, human gate, dispatch hand-off) should have had a bounded-wait invariant; #313 and #320 show where the generalization was missing.

**Revision context discipline (#247):**

- Pre-run contract: "The `/revise` agent should be smart enough to read the comments on the PR and use them as revision context, rather than relying on the user to restate intent," so that "the user does not have to manually paste or re-summarize feedback already present in the thread." The assembled-directive substrate shipped (PR #262) and demonstrably worked during the run (#310 notes "the surviving revise run's assembled directive from #247 consumes all unresolved threads") — but #311 and #327 show the closing half of the loop (per-thread resolution, incremental review state) was never specified, and became the run's throughput bottleneck.

**Summary yardstick set for the retro:** median PR net diff ≈ 400 lines; 1–2 tasks per ~250-line scope; per-feature cost ratio trended (aic); <50% wall-clock in gate waits; zero green agent PRs closed unmerged; one fresh status comment per tracker; every external wait bounded (30-min-class SLA); every revise grounded in the PR thread and every thread closed with a reasoned verdict. The networking run should be scored against each, with sections 1 and 4 supplying the incidents and section 5 the signals a future eval agent needs so that "human watching" stops being the primary detector.
