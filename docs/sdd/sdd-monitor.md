# The `sdd-monitor` agent

`sdd-monitor` is a defense-in-depth utility workflow that watches in-flight
`/dispatch` cascades and nudges them when they fall idle. It is a safety net
for transient GitHub races and run cancellations, not a replacement for fixing
the underlying dispatch bugs.

This page describes **Tier 1** of the design in issue #148. Tier 2 (healing
known-safe stalls) and Tier 3 (escalating unrecoverable stalls to
`needs-human`) are deferred to follow-up pull requests.

## What it does

On every firing, `sdd-monitor`:

1. Reads the `SDD_MONITOR` repository variable. If it is not `1`, the
   workflow exits without acting.
2. Confirms no `sdd-execute-{haiku,sonnet,opus}` run is `in_progress` or
   `queued` in this repository. If any is, the pass defers and the next
   firing tries again.
3. Searches for active tracking issues: open, labeled `sdd:dispatched`, not
   labeled `needs-human` or `sdd:done`.
4. For each active tracker:
    - Skips if the most recent `/dispatch` comment on the tracker (any
      author) is younger than the debounce window.
    - Skips if any open `sdd/` implementation pull request rolls up to this
      tracker (a layer is already in flight on the pull-request side of
      the cascade).
    - Walks the tracker's sub-issue tree (tracker → Unit → task), counts
      open tasks whose every `blocked by #<N>` dependency is closed.
    - If at least one task is ready, posts one comment whose body begins
      with `/dispatch` and carries an `sdd-monitor:` audit line. The
      dispatch wrapper picks up the `/dispatch` and fans out to the
      ready set.

The audit comment looks like this:

```text
/dispatch

sdd-monitor: armed-but-idle on #201 with 2 tasks ready; dispatching.
```

Operators reading the tracker timeline see exactly which monitor pass
nudged the cascade and how many tasks were eligible.

## How to enable it

The monitor is disabled by default. To turn it on in a consumer repository,
set the repository variable:

```sh
gh variable set SDD_MONITOR --body 1
```

Unset the variable (or set it to anything other than `1`) to turn the
monitor off again. The wrapper itself stays installed.

The consumer repository must already have `APP_ID` and the `APP_PRIVATE_KEY`
secret configured (the standard spectacles install) for the monitor to mint
the token used to post `/dispatch`. The same App identity drives
`sdd-dispatch`'s cascade fan-out, so any repository running the SDD suite
already has it in place.

## Configuration

Two repository variables tune the monitor:

| Variable | Default | Purpose |
| --- | --- | --- |
| `SDD_MONITOR` | unset (off) | Set to `1` to enable monitor dispatches. |
| `SDD_MONITOR_DEBOUNCE_MIN` | `5` | Minutes between consecutive `/dispatch` comments on the same tracker, counting both monitor-issued and operator-issued comments. |

## Triggers

`sdd-monitor` is event-driven with a cron backstop:

- `workflow_run` completion on any `sdd-execute-{haiku,sonnet,opus}`: the
  moment a run finishes (success, failure, or cancellation), the monitor
  re-evaluates every active tracker.
- `pull_request` `closed` on an `sdd/` branch: a merging or closing
  implementation pull request marks the moment a task can close and the
  next layer could be armed.
- `schedule: */10 * * * *`: a ten-minute cron backstop catches events
  lost to webhook drops or runner outages.

## Idempotency

The monitor is designed so that re-running a pass — whether by accident,
by event storm, or by the cron retrying — never doubles up an action:

- The disabled-by-default check is the first statement; without an
  explicit opt-in the workflow does nothing.
- The in-flight gate is repository-wide: any one `sdd-execute-*` run that
  is `in_progress` or `queued` defers the entire pass. This is
  intentionally conservative — correlating each run back to its tracker
  requires walking from the run's `aw_context.item_number` task up two
  parent hops, and the cron retry every ten minutes recovers any
  delayed nudge on the next cycle. The safety case (no stacked
  `/dispatch` comments triggering the cancellation storm described in
  issue #148) dominates.
- The debounce window collapses bursty triggers into one comment per
  tracker per `SDD_MONITOR_DEBOUNCE_MIN` minutes.

## What it does NOT do (Tier 2 and Tier 3 follow-ups)

Out of scope for this Tier 1 release; tracked as follow-ups on issue #148:

- **Tier 2 (healing).** Merging an `sdd/` pull request that is green on
  required checks but `UNSTABLE` because of cancelled non-required checks
  (issue #135). Resetting a task stuck `sdd:in-progress` with an empty or
  orphaned branch back to `sdd:ready`. Advancing `sdd:review` to
  `sdd:done` when every task sub-issue is closed (issue #147).
- **Tier 3 (escalation).** Posting a digest comment and applying
  `needs-human` on a tracker that cannot self-heal (a pull request red
  on a real failure, a task that has failed N times, a malformed
  sub-issue tree).

Each tier ships in its own pull request so the change set is small enough
to review against `shared/rigor.md`.

## Permissions and identity

`sdd-monitor` runs with the minimum scopes required to do its work:

- `contents: read` — workflow boilerplate.
- `actions: read` — list `sdd-execute-*` workflow runs for the in-flight
  gate.
- `pull-requests: read` — list open `sdd/` pull requests for the
  in-flight gate.
- `issues: read` — walk the sub-issue tree, read labels, list existing
  comments.

The `/dispatch` comment itself is posted with an App installation token
(the same `APP_ID` + `APP_PRIVATE_KEY` pair that drives the cascade
fan-out in `sdd-dispatch`). The dispatch wrapper's App-author carve-out
admits the comment past the human-permission gate; the default
`GITHUB_TOKEN`'s `github-actions[bot]` is not a repository collaborator
and would be rejected.

## Verification

Once enabled in a consumer repository:

- Confirm the workflow appears under `Actions → sdd-monitor` and runs on
  the `*/10 * * * *` schedule.
- Confirm that with `SDD_MONITOR` unset or `0`, a scheduled run logs
  `SDD_MONITOR is not set to "1"; monitor is disabled.` and exits.
- Confirm that with `SDD_MONITOR=1` and an active `sdd:dispatched`
  tracker carrying at least one ready task, a scheduled run posts one
  `/dispatch` comment whose first non-blank line is `/dispatch` and
  whose audit line begins `sdd-monitor: armed-but-idle on #`.
- Confirm a second scheduled firing within `SDD_MONITOR_DEBOUNCE_MIN`
  minutes logs `< Nm debounce; skipping.` and does not post a second
  comment.

## References

- Issue #148 — the design document for `sdd-monitor` Tier 1, Tier 2, and
  Tier 3.
- Issue #133 — the re-dispatch-on-close race that motivates Tier 1.
- ADR 0006 — the deterministic-backstop pattern that `sdd-pr-sanitize`,
  `sdd-triage-promote-ready`, and `sdd-monitor` all follow.
