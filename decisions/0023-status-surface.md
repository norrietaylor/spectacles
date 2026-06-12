---
id: adr-0023
title: A deterministic self-updating status surface per tracking issue
kind: adr
status: accepted
supersedes:
superseded-by:
---

# ADR 0023: A deterministic self-updating status surface per tracking issue

- Status: Accepted
- Date: 2026-06-12

## Context

Field feedback from a consumer pilot run: there is no single place to see
where the pipeline is on a feature. State is scattered across labels,
sub-issue trees, PR checks, and Actions runs — "buried in a CI job
somewhere." Operators want one surface to check in with and nudge, the way
they would a single agent session (issue #254).

Every input to such a surface is already API-derivable: the lifecycle label,
the `sdd:dispatched` marker, the Unit/task tree (ADR 0005), `blocked by`
lines, open `sdd/` pull requests with their check and review rollups, and
in-flight `sdd-execute-*` runs. The question is where the surface lives and
what maintains it.

## Decision

1. Ship a deterministic utility workflow `sdd-status`
   (`wrappers/sdd-status.yml`, no `engine:`) whose composite action
   (`.github/actions/sdd-status/action.yml`) maintains **exactly one**
   status comment per tracking issue, located by the `<!-- sdd-status -->`
   sentinel and **edited in place**. Comment edits do not notify, so
   `needs-human` and agent hand-off comments stay the only pings (ADR 0001).
   Sentinel precedents: `<!-- sdd-triage:plan -->` (ADR 0010), the
   auto-revise markers in `sdd-route-execute`.
2. Each refresh derives: a phase line (lifecycle label + plan-comment link),
   a "Your move" line from a deterministic first-match-wins decision table
   keyed on lifecycle + derived facts, a per-task state table, progress
   counts with in-flight run links, and a last-updated footer.
3. Triggers: `issues` (labeled/unlabeled/closed/reopened), `issue_comment`
   (the token-strict `/status` forced refresh), `pull_request` and
   `pull_request_review` on `sdd/` refs, `check_suite` completions on `sdd/`
   branches, and `workflow_run` completions of the `sdd-*` agents.
4. Plain `GITHUB_TOKEN` (`issues: write`, `pull-requests: read`,
   `actions: read`, `checks: read`) — no App mint. Concurrency is
   `cancel-in-progress: true` per repository: the latest pass wins.
5. **Default-on** once installed; the `SDD_STATUS=0` repository variable
   opts out. This deviates from `SDD_MONITOR`'s opt-in because status never
   mutates pipeline state — its only write is one non-command comment.
6. `/status` joins the command vocabulary (`shared/sdd-interaction.md`),
   gated to write-access authors via the explicit repository-permission
   check from `sdd-route-dispatch` (not `author_association`). The ack is
   an `eyes` reaction, never a new comment.
7. Shared code is extracted, not duplicated: the monitor's GraphQL
   `walkToTracker` moved to `.github/actions/shared/parent-walk.js`, and
   both `sdd-monitor` and `sdd-status` consume it (the
   `shared/blocked-by.js` precedent).
8. V1 scope cuts, resolved per issue #254's own recommendations: fuzzy
   `workflow_run` correlation (a completed run refreshes every active
   tracker rather than resolving its exact tracker), no opt-in notifying
   ping, no pinned tracking issue, and no cron backstop — `/status` is the
   manual backstop and the footer makes staleness visible.

## Reasoning

- **Deterministic, not an agent.** The output is 100% derivable from API
  state; an LLM adds cost, latency, and drift, and would drag in the
  ADR 0020 OTLP block. With no `engine:` the wrapper compiles no
  `.lock.yml` and is exempt under ADR 0020 §5.
- **Not an sdd-monitor extension.** (1) The monitor's repository-wide
  in-flight gate defers exactly when status matters most (during execute
  runs). (2) Opposite concurrency semantics (monitor:
  `cancel-in-progress: false` — its mutating pass is worth finishing).
  (3) Different trust posture: the monitor is an opt-in mutator on an App
  token; status is a reporter whose only write is one non-command comment.
- **Edited comment, not the issue body.** The tracking-issue body is a
  parsed input (`plan:provided`, `blocked by #N`) — editing it risks
  corrupting the pipeline's own inputs.
- **Branch conventions, not closing references, for early-phase PR
  discovery.** `sdd-pr-sanitize` neutralizes issue-closing keywords in
  spec/architecture PR bodies (ADR 0006), so GraphQL
  `closingIssuesReferences` cannot find them; the `sdd/<issue>-` branch
  prefix is the reliable join key, walked to its tracker via the shared
  parent walk.

## Rejected alternatives

- **LLM-generated digest** — cost and latency for fully derivable output,
  plus the OTLP block.
- **A check run on the tracking issue** — impossible; checks attach to
  commits.
- **A Projects v2 board** — contradicts the four-GitHub-primitives
  principle in `shared/sdd-interaction.md`.
- **Editing the tracking-issue body** — corruption risk on a parsed input.

## Verification

- `wrappers/sdd-status.yml` exists with the trigger set above, no
  `engine:`, and no compiled `.lock.yml`.
- `.github/actions/sdd-status/action.yml` upserts on the
  `<!-- sdd-status -->` sentinel and routes `/status` through the
  `firstWord === '/status'` idiom (picked up by
  `scripts/test-command-table.py`).
- `/status` appears in the `shared/sdd-interaction.md` command table;
  `scripts/test-command-table.py` passes.
- `.github/actions/shared/parent-walk.js` is required by both the monitor
  and sdd-status actions; the inline copy in
  `.github/actions/sdd-monitor/action.yml` is gone.
- `scripts/quick-setup.sh` installs the wrapper with the suite.

## Consequences

- Operators get one self-updating surface per feature and a `/status`
  nudge, with zero new notification noise.
- A follow-up (phase 2, after issue #232) can layer a local-harness
  `sdd status <issue>` skill that reads the sentinel comment as its data
  contract and nudges via the existing command vocabulary; no new server
  surface is required.
- The fuzzy `workflow_run` correlation means a busy repo refreshes all
  active trackers on every agent-run completion; exact run-per-task
  attribution needs `aw_context` reads and is deferred.

## Cross-links

- ADR 0001 (`needs-human` is the only ping), ADR 0005 (sub-issue tree),
  ADR 0006 (PR-body sanitizer / branch conventions), ADR 0010 (plan-comment
  sentinel), ADR 0011/0014 (cascade), ADR 0015 (wrapper logic in composite
  actions), ADR 0020 §5 (deterministic exemption).
