# ADR 0016: Resolve sdd-review's advisory threads so auto-merge is not deadlocked by required_conversation_resolution

- Status: Accepted
- Date: 2026-05-30

## Context

`sdd-review` is advisory by design (see `workflows/sdd-review.md`): it posts
line-anchored findings as pull-request review comments and **never** submits an
approving or change-requesting review and never merges. The stated contract is
"a merge is gated by human review and the consumer repository's own CI, never
by this agent. `sdd-review` is therefore not a required status check."

That contract silently breaks when the consumer's base branch enables
`required_conversation_resolution`. Every line-anchored review comment opens a
GitHub review thread, and under that branch-protection rule an unresolved
thread is a hard merge blocker. So the advisory agent becomes a gate.

Combined with `SDD_AUTO_MERGE` (ADR 0015 / issue #127), the failure is a
permanent deadlock:

1. `sdd-execute` opens the implementation PR and arms native auto-merge
   (squash, delete-branch). The `auto-merge` job runs once, at PR-open, before
   `sdd-review` has posted anything.
2. `sdd-review` fires on the same `opened` event and posts its findings as
   review-comment threads.
3. The PR's `mergeStateStatus` goes to `BLOCKED`: every required status check
   is green and the review is irrelevant to the merge gate, but the unresolved
   advisory threads fail the conversation-resolution rule.
4. Nothing re-runs the `auto-merge` job (it is gated on
   `created_pr_number != ''`, true only in the run that opened the PR), and
   nothing resolves the threads. Native auto-merge waits forever. The cascade
   stalls on the first implementation PR.

Observed on `gominimal/minspec-test` PR #49: `mergeable: MERGEABLE`,
`reviewDecision: APPROVED`, required checks `cargo-deny`/`verify`/`miri` all
SUCCESS, auto-merge armed — yet `mergeStateStatus: BLOCKED` on two unresolved
`sdd-review` threads, indefinitely.

The existing `sdd-auto-merge` fallback (issue #135) handles an `UNSTABLE` PR
whose only blockers are non-required check-runs. It does not cover a `BLOCKED`
PR whose only blocker is conversation resolution, and it could not: the
auto-merge job has already exited by the time the threads appear.

## Decision

Resolve the App bot's **own** advisory review threads once `sdd-review` has
posted them, in a deterministic post-step of the `sdd-review` wrapper.

1. A new hosted composite action
   `.github/actions/sdd-resolve-review-threads` resolves every unresolved
   review thread on a PR whose first comment is authored by a given
   `bot-login`, via the GraphQL `resolveReviewThread` mutation. It is scoped by
   author: a human reviewer's thread, or a CodeRabbit `CHANGES_REQUESTED`
   thread, is left unresolved so it still gates the merge. This matches the
   wrapper-logic-in-composite-actions model of ADR 0015.

2. The `sdd-review` wrapper gains a `resolve-advisory-threads` job that
   `needs: [route, sdd-review]` — so the reusable workflow's `safe_outputs`
   job has posted the inline comments before the job reads them — mints an App
   token (`pull-requests: write`), and calls the action with
   `bot-login = <app-slug>[bot]` (the `create-github-app-token` `app-slug`
   output) and the PR number from the `pull_request` event payload.

3. The job is gated on `SDD_AUTO_MERGE`, the same switch that arms auto-merge
   in the `sdd-execute` tiers. A repo that opted into hands-off merging
   auto-resolves advisory threads; a repo that leaves merge to a human keeps
   the threads open for triage. Behavior is unchanged when the switch is unset.

A resolved thread is collapsed, not deleted: the advisory finding stays visible
and a human can re-open it. `CRITICAL`/`HIGH` findings continue to escalate
through the `needs-human` label, which gates by its own mechanism and is
untouched here.

## Consequences

- Under `SDD_AUTO_MERGE` with `required_conversation_resolution`, an
  implementation PR with only advisory `sdd-review` threads merges hands-off
  once its required checks are green. The deadlock is removed.
- `sdd-review`'s advisory contract is restored: its threads no longer act as a
  silent merge gate.
- Human and third-party review threads still gate the merge — the fix is scoped
  to the App bot's own threads by author login.
- The resolution runs on every `opened`/`synchronize` review pass, so a thread
  re-posted on a later pass is re-resolved on that pass.
- A repo not using `SDD_AUTO_MERGE` sees no change; advisory threads remain for
  human triage as before.
