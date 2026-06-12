# The `sdd-monitor` agent

`sdd-monitor` is a defense-in-depth utility workflow that watches in-flight
`/dispatch` cascades and nudges them when they fall idle. It is a safety net
for transient GitHub races and run cancellations, not a replacement for fixing
the underlying dispatch bugs.

This page describes **Tier 1** of the design in issue #148, plus the
stranded-task recovery tier added for issue #201 (re-dispatch a
silently-dropped task, then escalate to `needs-human` after a bounded
number of attempts) and the CodeRabbit stall detection added for
issue #257 (bounded `@coderabbitai review` nudges on a
silently-unreviewed `sdd/` PR, then `needs-human`). The remaining Tier 2
healing cases
(merging UNSTABLE PRs, advancing `sdd:review` to `sdd:done`) are deferred
to follow-up pull requests.

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
5. When CodeRabbit is detected (or forced on), runs the CodeRabbit stall
   detection pass over open non-draft `sdd/` pull requests (below).

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

## CodeRabbit stall detection

CodeRabbit sometimes never reviews an agent-created PR at all (its usage
limits are one cause), and without a handler the operator has to notice
the silence and intervene by hand. The framework reacts to a CodeRabbit
`CHANGES_REQUESTED` review (implicit `/revise`, issue #128), but a
CodeRabbit **stall** — no review at all — previously had none
(issue #257).

The monitor closes that gap with a deterministic pass that runs on every
firing, after the tracker nudge:

1. **Enablement.** The pass considers CodeRabbit present when a
   `.coderabbit.yaml` or `.coderabbit.yml` exists at the repository root,
   or when `SDD_CODERABBIT=1` (the config file is optional for a
   CodeRabbit install, hence the override). `SDD_CODERABBIT=0`
   force-disables the pass. Like everything else here, nothing runs
   unless `SDD_MONITOR=1`.
2. **Stall predicate.** For each open non-draft `sdd/` pull request not
   labeled `needs-human`: the PR is stalled when its head commit is at
   least `SDD_CODERABBIT_STALL_MIN` minutes old (default 30) **and**
   `coderabbitai[bot]` has left no review, review comment, or issue
   comment since that commit.
3. **Bounded nudges.** A stalled PR draws one App-authored nudge comment
   per pass: a hidden marker
   `<!-- sdd-monitor:coderabbit-nudge sha=<head_sha> -->`, an audit line,
   and `@coderabbitai review` on its own line. The markers are the
   durable budget counter: at most `SDD_CODERABBIT_NUDGE_MAX` nudges
   (default 2) per head sha. A new push mints a new head sha and resets
   the budget, matching CodeRabbit's per-push review model.

   ```text
   sdd-monitor: CodeRabbit has not reviewed head 1a2b3c4 after 34m;
   nudging (attempt 1 of 2).

   @coderabbitai review
   ```

4. **Escalation.** When the budget is exhausted and the PR is still
   stalled on a later pass, the monitor applies `needs-human` to the PR
   and posts one audit comment carrying a one-shot escalation marker, so
   a silent stall becomes the framework's standard visible hand-off.

   ```text
   sdd-monitor: CodeRabbit has not reviewed after 2 nudges; review
   manually or merge per policy. Applying needs-human.
   ```

Whether CodeRabbit honors `@coderabbitai review` from a GitHub App author
is unverified (issue #257, open question 1); the escalation path delivers
the value even if the nudge itself is ignored. Human-authored PRs (any
branch not prefixed `sdd/`) are out of scope in V1 — a nudge would be
safe, but widening scope is a demand-driven follow-up.

Unlike the tracker nudge, this pass is **not** deferred by the in-flight
gate: a live `sdd-execute` run says nothing about CodeRabbit's silence on
an already-open PR, and the pass posts no `/dispatch`, so the
cancellation-storm concern behind that gate does not apply.

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

Five repository variables tune the monitor:

| Variable | Default | Purpose |
| --- | --- | --- |
| `SDD_MONITOR` | unset (off) | Set to `1` to enable monitor dispatches. |
| `SDD_MONITOR_DEBOUNCE_MIN` | `5` | Minutes between consecutive `/dispatch` comments on the same tracker, counting both monitor-issued and operator-issued comments. |
| `SDD_CODERABBIT` | unset (auto-detect) | Force-toggle for CodeRabbit stall detection. Unset, the pass enables itself when `.coderabbit.yaml` / `.coderabbit.yml` exists at the repository root; `1` force-enables, `0` force-disables. |
| `SDD_CODERABBIT_STALL_MIN` | `30` | Minutes an open non-draft `sdd/` PR's head commit must age with no `coderabbitai[bot]` review or comment before the PR counts as stalled. |
| `SDD_CODERABBIT_NUDGE_MAX` | `2` | `@coderabbitai review` nudges per head sha before escalation to `needs-human`. A new push resets the budget. |

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

- `contents: read` — workflow boilerplate, and the CodeRabbit config
  presence probe (`.coderabbit.yaml` / `.yml` via `getContent`).
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
The CodeRabbit pass also runs on the App token: the nudge and escalation
comments must be App-authored (`issues: write`), and the review / PR
commit reads ride the App's `pull-requests: read`; only the config
presence probe rides `GITHUB_TOKEN`, because the App token deliberately
carries no Contents permission.

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
- With a `.coderabbit.yaml` present (or `SDD_CODERABBIT=1`), confirm an
  open non-draft `sdd/` PR whose head commit is older than
  `SDD_CODERABBIT_STALL_MIN` minutes with no CodeRabbit review or comment
  draws one nudge comment per pass (marker, audit line, then
  `@coderabbitai review` on its own line), capped at
  `SDD_CODERABBIT_NUDGE_MAX` per head sha; that a push to the PR resets
  the budget; and that the pass after the cap applies `needs-human` and
  posts the `review manually or merge per policy` escalation comment
  once.
- Confirm that whether CodeRabbit actually honors `@coderabbitai review`
  from the configured App author (issue #257, open question 1) — if it
  does not, the escalation path above is the operative remedy.

## References

- Issue #148 — the design document for `sdd-monitor` Tier 1, Tier 2, and
  Tier 3.
- Issue #133 — the re-dispatch-on-close race that motivates Tier 1.
- Issue #257 — CodeRabbit stall detection with bounded nudges.
- Issue #128 — the `CHANGES_REQUESTED` implicit `/revise` that handles a
  CodeRabbit review once one exists.
- ADR 0006 — the deterministic-backstop pattern that `sdd-pr-sanitize`,
  `sdd-triage-promote-ready`, and `sdd-monitor` all follow.
