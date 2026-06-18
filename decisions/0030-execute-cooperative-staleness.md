---
id: adr-0030
title: Cooperative staleness for sdd-execute instead of cancelling PR-attached runs
kind: adr
status: proposed
supersedes:
superseded-by:
---

# ADR 0030: Cooperative staleness for sdd-execute instead of cancelling PR-attached runs

- Status: Proposed
- Date: 2026-06-17

## Context

The `sdd-execute-{haiku,sonnet,opus}` wrappers subscribe to PR-attached events
(`pull_request`, `pull_request_review`, `pull_request_review_comment`,
`check_suite`) plus issue events, and use `concurrency` with
`cancel-in-progress: true`, keyed per-task-per-tier. The cancellation is
deliberate: it collapses racing *actionable* runs — a stale `sdd-dispatch`
fan-out vs a manual `/execute` on the same task (issue #124), and concurrent
failed-check `check_suite` runs that would each spawn a `/revise` on the same PR
head (issues #227, #228).

The side effect: when a run triggered by a **PR-attached** event is cancelled by
`cancel-in-progress`, GitHub renders that cancelled run as a check on the PR.
A cancelled check reads as **failed CI** even though nothing failed — the run
was only superseded. Across the three tiers, every PR-attached wake multiplies
the noise. Reviewers see red on green PRs.

## Decision

1. **Scope `cancel-in-progress` to issue-keyed runs only.** In each wrapper's
   `concurrency.group`, route every PR-attached trigger
   (`pull_request`, `pull_request_review`, `pull_request_review_comment`,
   `check_suite`, and a `/revise` `issue_comment` whose
   `github.event.issue.pull_request` is set) to a unique `github.run_id` group.
   Those runs never cancel, so they never render as a red check. Cancellation
   survives only for the issue-keyed runs that do not attach to a PR — a
   `/execute` comment on a task sub-issue and a `workflow_dispatch` from
   `sdd-dispatch` — which keep the per-task-per-tier group (issue #124). The
   `issues.unlabeled` resume and non-command `issue_comment` carve-outs to
   `run_id` (issues #143, #142) are preserved.

2. **Replace the cancellation-based revise collapse with a cooperative
   sha-keyed claim** in `sdd-route-execute`. For the auto-revise paths (a
   `CHANGES_REQUESTED`/actionable review and a failed `check_suite`), capture the
   PR head sha and, in the post-tier-gate auto-revise block, post a
   `<!-- sdd-execute:revise-claim sha=<head_sha> -->` marker before proceeding.
   A run that finds an existing claim for the same head sha **defers** (exits
   `should_run=false`, a no-op success) instead of being cancelled. This keeps
   the single-revise guarantee of issues #227/#228 cooperatively. The claim
   marker uses a distinct prefix from the auto-revise iteration marker, so it
   does not inflate the cap count.

## Reasoning

- A cancelled PR check is indistinguishable from a failed one in the GitHub UI,
  so the only durable fix is to stop cancelling runs that attach to PRs.
- The route action already carries the cooperative primitives: it ignores a
  `check_suite` whose `head_sha` is no longer the PR head (so a suite a revise
  already superseded is dropped), and it counts hidden marker comments to bound
  the auto-revise loop. The sha-keyed claim extends that same marker pattern to
  the concurrent-same-head case, which is the only window the cancellation was
  still covering.
- Issue-keyed cancellations (dispatch vs `/execute`) are kept because they
  collapse genuine double-execution and never attach to a PR, so they cause no
  false red checks.

## Verification

- A PR that receives two failed `check_suite` events for the same head sha runs
  exactly one `/revise`: the first posts the claim and runs; the second finds
  the claim and no-ops (success), leaving no cancelled run on the PR.
- A superseded PR-attached run shows as a skipped/successful check, never
  `cancelled`, on the PR.
- A stale `sdd-dispatch` cell and a manual `/execute` on the same task still
  collapse to one run (issue #124) — unchanged, and invisible on any PR.
- `actionlint` accepts the rewritten `concurrency.group` expression in all three
  wrappers.

## Consequences

- Edits `wrappers/sdd-execute-{haiku,sonnet,opus}.yml` (concurrency) and
  `.github/actions/sdd-route-execute/action.yml` (sha-keyed claim). No lock
  recompilation: wrappers and composite actions do not compile to `.lock.yml`.
- Residual: a microsecond check-then-post race could let two truly-simultaneous
  runs both claim the same head and both revise. This is bounded by the existing
  auto-revise cap and is redundant work, not wrong work — an acceptable trade for
  removing the false-red-CI signal. A stricter run-election (querying in-progress
  runs and deferring by `run_id` order) was rejected as more complex and still
  racy.

## Cross-links

- Issue #271 (sdd-execute cancelled runs read as failed CI on PRs — option 3).
- Issues #124, #143, #142, #227, #228 (the concurrency-group incident history
  this decision preserves the intent of).
- ADR 0012 (fast-path), ADR 0015 (wrapper logic in composite actions).
