# The `sdd-status` surface

`sdd-status` is a deterministic utility workflow that maintains exactly one
self-updating status comment per tracking issue: a single surface to check in
with on where the pipeline is, instead of piecing the answer together from
labels, sub-issue trees, PR checks, and Actions runs.

The comment is located by its `<!-- sdd-status -->` sentinel and **edited in
place** on every refresh. Comment edits do not notify, so `needs-human` and
agent hand-off comments stay the only pings (ADR 0001). The sentinel pattern
follows the `<!-- sdd-triage:plan -->` plan comment (ADR 0010) and the
auto-revise markers in `sdd-route-execute`.

There is no LLM in this loop. Every line of the comment is derived from API
state — labels, the sub-issue tree, open `sdd/` pull requests, and workflow
runs — so an agent would only add cost, latency, and drift. With no `engine:`
the wrapper compiles no `.lock.yml` and is exempt from the OTLP observability
block (ADR 0020 §5).

## What the comment contains

Each refresh rewrites the whole comment:

- **Phase line.** The lifecycle label (`sdd:spec` … `sdd:done`), whether the
  cascade is armed (`sdd:dispatched`), and a link to the plan comment when
  one has been posted.
- **"Your move" line.** One deterministic instruction derived from a
  first-match-wins decision table keyed on the lifecycle label plus derived
  facts. Examples: `needs-human` present → link the escalation comment;
  `sdd:ready` → "comment `/dispatch`"; a task PR green but unapproved →
  "review PR #N"; agents running → "nothing — agents are working."
- **Per-task table.** One row per task sub-issue: Unit, task link, and state
  (closed; PR open with a checks + review rollup; agent running with run
  links; blocked by `#N`; queued; waiting).
- **Progress counts.** Closed/total tasks, plus links to in-flight
  `sdd-execute-*` runs.
- **Footer.** Last-updated timestamp, the triggering event, and a note that
  the comment is edited in place and does not notify.

## When it refreshes

The wrapper fires on every event that can change the surface:

| Trigger | Why |
|---|---|
| `issues` labeled/unlabeled (`sdd:*`, `needs-human`), closed, reopened | lifecycle and tree-shape changes anywhere in the tracker's tree |
| `issue_comment` created | the token-strict `/status` forced refresh |
| `pull_request` opened/closed/reopened/ready_for_review on `sdd/` refs | spec, architecture, and implementation PRs appearing and landing |
| `pull_request_review` submitted on `sdd/` refs | review decisions feed the "Your move" table |
| `check_suite` completed on `sdd/` branches | check rollups feed the per-task and "Your move" rows |
| `workflow_run` completed on the `sdd-*` agents | re-derive "agent running" rows and run links |

The triggering issue, branch, or PR is walked back to its tracking issue
through the shared GraphQL parent walk
(`.github/actions/shared/parent-walk.js`, the same `walkToTracker` the
monitor uses). A `workflow_run` completion is not reliably attributable to a
single tracker, so that event refreshes every open issue that looks like an
active tracking issue (an `sdd:*` lifecycle label or `sdd:dispatched`, and no
parent) — the V1 fuzzy correlation from issue #254.

Concurrency is `cancel-in-progress: true` per repository: a refresh is an
idempotent re-derivation, so the latest pass wins. This is deliberately the
opposite of `sdd-monitor`, whose mutating pass is worth finishing.

## `/status`

`/status` on a tracking issue (or any sub-issue under one) forces a refresh.
It is gated to authors with real repository write access via the same
explicit permission check `sdd-dispatch` uses — `author_association` is not
trusted. The acknowledgement is an `eyes` reaction on the command comment;
the refreshed status comment is the response, and no new comment is posted.

`/status` is also the manual staleness backstop: there is no cron in V1, and
the footer's last-updated line makes a stale surface visible.

## Enablement

`sdd-status` is **default-on** once the wrapper is installed
(`scripts/quick-setup.sh` installs it with the suite). It never mutates
pipeline state — its only write is the one non-command status comment plus
the `/status` reaction — so the opt-in posture of `SDD_MONITOR` is not
needed. To opt out, set the repository variable:

```text
SDD_STATUS=0
```

## Permissions and trust posture

The wrapper runs on the plain `GITHUB_TOKEN` — no App mint. The status
comment is a report, never a command, so it does not need to pass any
wrapper's App-author carve-out:

| Permission | Used for |
|---|---|
| `issues: write` | the status comment upsert and the `eyes` reaction |
| `pull-requests: read` | open `sdd/` PRs and their review decisions |
| `actions: read` | in-flight `sdd-execute-*` runs |
| `checks: read` | the `statusCheckRollup` per open `sdd/` PR |

## Why not extend `sdd-monitor`

1. The monitor's repository-wide in-flight gate defers exactly when status
   matters most (during execute runs).
2. Opposite concurrency semantics (monitor: `cancel-in-progress: false`).
3. Different trust posture: the monitor is a mutator (opt-in, App token);
   status is a reporter on the plain `GITHUB_TOKEN`.

Shared code is extracted instead: the monitor's GraphQL `walkToTracker`
moved to `.github/actions/shared/parent-walk.js` and both consume it,
following the `shared/blocked-by.js` precedent.

See ADR 0023 (`decisions/0023-status-surface.md`) for the full decision
record, including the rejected alternatives (LLM digest, check runs,
Projects v2 board, editing the tracking-issue body) and the V1 scope cuts
(no notifying ping, no pinned issue, no cron backstop).
