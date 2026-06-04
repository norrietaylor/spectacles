# The `sdd-monitor` agent

`sdd-monitor` is a defense-in-depth utility workflow that watches in-flight
`/dispatch` cascades and nudges them when they fall idle. It is a safety net
for transient GitHub races and run cancellations, not a replacement for fixing
the underlying dispatch bugs.

This page describes **Tier 1** of the design in issue #148, plus the
stranded-task recovery tier added for issue #201 (re-dispatch a
silently-dropped task, then escalate to `needs-human` after a bounded
number of attempts). The remaining Tier 2 healing cases (merging
UNSTABLE PRs, advancing `sdd:review` to `sdd:done`) are deferred to
follow-up pull requests.

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
      open tasks whose every `blocked by #<N>` dependency is closed, and
      flags any deps-closed open task that already carries `sdd:ready` or
      `sdd:in-progress` but has no open `sdd/` PR as **stranded**.
    - If at least one task is stranded, runs the stranded-task recovery
      tier (below). Otherwise, if at least one task is ready, posts one
      comment whose body begins with `/dispatch` and carries an
      `sdd-monitor:` audit line. The dispatch wrapper picks up the
      `/dispatch` and fans out to the ready set.

The audit comment looks like this:

```text
/dispatch

sdd-monitor: armed-but-idle on #201 with 2 tasks ready; dispatching.
```

Operators reading the tracker timeline see exactly which monitor pass
nudged the cascade and how many tasks were eligible.

## Stranded-task recovery (pre-agent execute failures)

An `sdd-execute` run can die **before its agent job** — cancelled by the
per-issue concurrency group, or failing in the `activation` stage — and
that failure is silent: `report-failure-as-issue` only fires on an
agent-stage engine failure, so a pre-agent death files no failure issue,
leaves the task at `sdd:ready` / `sdd:in-progress` with no PR and no run,
and nothing retries it (issue #201).

The monitor closes that gap. Because the repository-wide in-flight gate
above has already proved no `sdd-execute-*` run is `in_progress` or
`queued`, any deps-closed open task that still carries `sdd:ready` or
`sdd:in-progress` **and** has no open `sdd/` implementation PR has been
silently dropped. The monitor treats it as stranded and:

1. **Re-dispatches it (bounded).** It posts one `/dispatch` comment whose
   audit line names the stranded task(s) and records the attempt number.
   The dispatch wrapper recomputes the ready set and re-fires `/execute`
   on the stranded task, the same lever an operator would pull manually.

   ```text
   /dispatch

   sdd-monitor: re-dispatching stranded task #324 on #201
   (no PR, no in-flight run; attempt 1 of 3).
   ```

2. **Escalates after N attempts.** The re-dispatch audit lines on the
   tracker are the durable attempt counter — they survive across monitor
   passes and are visible to operators. After three re-dispatch attempts
   the monitor stops re-dispatching, applies the `needs-human` marker
   label to the tracker, and posts a digest comment so an operator can
   intervene instead of the monitor looping forever.

   ```text
   sdd-monitor: stranded task #324 on #201 did not recover after
   3 re-dispatch attempts; applying needs-human for operator review.
   ```

Both outcomes are observable on the tracker timeline, so a cancelled or
activation-failed run no longer leaves a task sitting indefinitely at
`sdd:ready` with no run and no signal. The debounce window applies to the
re-dispatch the same way it applies to the armed-but-idle nudge, which
spaces the bounded retries out across monitor passes.

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
  `needs-human` on a tracker that cannot self-heal beyond the
  stranded-task case already covered above — a pull request red on a real
  failure, or a malformed sub-issue tree.

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
and would be rejected. The stranded-task recovery tier writes its
re-dispatch comment, its escalation comment, and the `needs-human` label
with the same App token, which carries `issues: write` through the App
installation (the workflow's own `GITHUB_TOKEN` is `issues: read` only).

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
- Confirm that a task left at `sdd:ready` / `sdd:in-progress` with no
  open `sdd/` PR and no in-flight run (a cancelled or activation-failed
  execute) draws a `sdd-monitor: re-dispatching stranded task #<N>`
  comment whose first non-blank line is `/dispatch`, and that after three
  such attempts the next pass applies `needs-human` and posts the
  `did not recover after 3 re-dispatch attempts` digest instead.

## References

- Issue #148 — the design document for `sdd-monitor` Tier 1, Tier 2, and
  Tier 3.
- Issue #133 — the re-dispatch-on-close race that motivates Tier 1.
- ADR 0006 — the deterministic-backstop pattern that `sdd-pr-sanitize`,
  `sdd-triage-promote-ready`, and `sdd-monitor` all follow.
