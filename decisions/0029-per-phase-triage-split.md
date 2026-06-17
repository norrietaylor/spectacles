---
id: adr-0029
title: Per-phase sdd-triage split for prompt + MCP scoping
kind: adr
status: proposed
supersedes:
superseded-by:
---

# ADR 0029: Per-phase sdd-triage split for prompt + MCP scoping

- Status: Proposed
- Date: 2026-06-17

## Context

`sdd-triage` was a single ~1085-line, multi-phase workflow. Its compiled prompt
was ~103KB / ~33K base tokens and loaded on **every** run regardless of which
event fired: all three phases (architecture / plan / materialize), both heavy
MCP fragments (`sdd-mcp-serena.md`, `sdd-mcp-distillery.md`), and the full GitHub
toolset whose tool schemas sit in context every turn.

A consumer phase-A run tripped the AWF effective-token hard rail
(`429 Maximum effective tokens exceeded (25096706 / 25000000)`) and produced zero
safe output. Per-call context grew monotonically as the conversation accumulated;
the prompt cache broke mid-run and re-billed the full context uncached. In that
run Serena was loaded but never called — its tool schemas were pure per-turn
overhead. The invocation cap (issue #270) is a coarse backstop that converts a
rail-death into a recoverable `noop` but does not stop context from growing.
Issue #271 tracks the structural cure: keep per-call context small enough that
the rail is never approached.

gh-aw loads MCP servers **per-workflow, not per-phase**, and an MCP server's tool
schemas sit in the compiled prompt every turn it is declared. A runtime
marker-gate (the Playwright `SDD_MCP_EXTRA` pattern) only defers container start;
it does **not** remove tool definitions from context. So scoping MCP to the
phases that use it requires splitting the monolith into separate compiled
workflows — the same precedent as the `sdd-execute-{haiku,sonnet,opus}` family.

## Decision

1. **Split `sdd-triage` into three per-phase reusable workflows.**
   - `sdd-triage-arch` — designs and persists `architecture.md` (Assumption
     ledger, knowledge-gap pass, repo-baseline pass), opens the architecture PR,
     materializes the spike wave. Imports **Serena + Distillery**.
   - `sdd-triage-plan` — posts the proposed plan as one comment on the merge of
     the architecture PR (and on spike-wave drain re-entry). Imports **no MCP**;
     it consumes the repo-baseline grounding from the merged `architecture.md`.
   - `sdd-triage-materialize` — gated on `/approve`, commits the Unit/task tree
     and advances `sdd:triage → sdd:ready`. Imports **no MCP**; it materializes
     exactly what the plan comment specifies.

2. **Routing is fully deterministic by (event, lifecycle label).** The
   `sdd-route-triage` action emits a `target` ∈ {`arch`, `plan`, `materialize`,
   `''`} the wrapper maps to the matching lock. The wrapper fans the single
   former call job into three phase-gated jobs; `cycle-detect` gates on
   `target == 'materialize'`.

3. **`/revise` is a pull-request-only command.** Triage routes a `/revise` only
   on an open `arch/<slug>` PR (→ arch, push to the existing branch). A `/revise`
   on a tracking issue, or on a non-architecture PR, is not routed.

4. **Drop the tracker-`/revise` paths** the monolith carried: the post-`/approve`
   tree reconcile (former step 9) and the post-merge `architecture.md` amendment
   (former step 10 / situation 6). They were the only paths whose routing could
   not be made deterministic without reading note intent, and both were
   tracker-`/revise` handlers. A plan is revised by revising the architecture PR
   before merge; a merged `architecture.md` is amended by an ordinary human PR.

5. **Reuse the existing fastpath classifier (ADR 0012 / ADR 0024).** No new
   complexity gate inside triage: fastpath features bypass triage entirely as
   today; full-path features (carrying `sdd:triage`) always run the arch phase.
   Architecture composes automatically when `sdd-spec` applies `sdd:triage` on
   spec-PR merge — no manual `/triage` is required.

## Reasoning

- The biggest, structural win is removing each phase's unused MCP tool schemas
  and the other phases' prose from its per-turn context. Marker-gating cannot do
  this; only a compiled-workflow split can.
- The architecture phase (the failing case) legitimately uses Serena and
  Distillery, so it keeps both; the win there is dropping the materialize/plan
  prose and the per-phase prefetch focus. Plan and materialize are MCP-free.
- The plan phase's requirement-baselining moves into the arch phase (which holds
  both MCP servers) and is recorded as `ALREADY EXISTS:` lines in
  `architecture.md`; the plan phase reads that grounding instead of re-querying.
  This preserves "an already-implemented requirement does not become a task"
  without giving the plan phase MCP.
- PR-only `/revise` removes the note-intent ambiguity that otherwise forces a
  workflow to carry the union of plan + arch-amend prose (defeating the split).
- Per-phase safe-output allowlists are tighter (least privilege): plan only
  comments/labels; materialize creates issues and labels (no PR, no close);
  arch opens PRs and closes only its own spikes.

## Verification

- `gh aw compile` compiles each of the three sources with zero errors; the
  declared MCP servers match the matrix (arch: Serena + Distillery; plan: none;
  materialize: none).
- Compiled lock sizes: `sdd-triage-materialize.lock.yml` and
  `sdd-triage-plan.lock.yml` are markedly smaller than the retired
  `sdd-triage.lock.yml`; `sdd-triage-arch.lock.yml` drops the materialize/plan
  prose.
- The former `## Verification` scenarios, distributed across the three
  workflows, pass: `/triage`/label → arch PR with Assumption ledger; `/revise`
  on the arch PR → push to branch, no second PR; arch PR merged → one plan
  comment, zero sub-issues; `/approve` → Unit/task tree + `sdd:triage → sdd:ready`;
  induced cycle at materialize → zero `create-issue` + `needs-human` +
  `cycle-detect` backstop.
- Route-action assertions cover the `target` enum across event × label × branch,
  including the resume plan-comment discriminator and the PR-only `/revise` gate.
- AIC (average input cost) before/after is compared via OTEL (ADR 0020):
  monolith historical phase-A AIC vs `sdd-triage-arch` AIC.

## Consequences

- Replaces `sdd-triage.md` / `sdd-triage.lock.yml` with three
  `sdd-triage-{arch,plan,materialize}` sources/locks. The wrapper
  `wrappers/sdd-triage.yml` fans to three phase-gated jobs; `sdd-spike-reentry`
  calls the plan lock; `sdd-route-triage` emits `target`.
- Supersedes ADR 0010 clause 7 (the post-`/approve` tracker-`/revise` reconcile)
  and ADR 0021's tracker-`/revise` arch-amendment path — both behaviors are
  removed from triage. The `architecture.md` amendment is now an ordinary human
  PR; `sdd-doc-status` and `distillery-sync` handle a human-edited record the
  same way they handled an agent-edited one.
- The item-B deterministic pre-fetch (issue #271) is carried into each phase
  file as an unconditional pre-agent step; the `triage_prefetch` A/B experiment
  is retired (the experiment mechanism cannot compare across a topology change).

## Cross-links

- Issue #271 (context reduction), issue #270 (invocation-cap backstop).
- ADR 0010 (plan-comment-before-tree, all-or-nothing materialization).
- ADR 0012 / ADR 0024 (fastpath / agile single-PR path).
- ADR 0021 (forward-only doc status; merged-record amendment).
- ADR 0020 (observability mandate; AIC measurement).
- ADR 0015 (wrapper logic in composite actions).
