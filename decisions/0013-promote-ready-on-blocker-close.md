# ADR 0013: Promote a task to `sdd:ready` when its last blocker closes

- Status: Accepted
- Date: 2026-05-21

## Context

ADR 0009 attaches `sdd:ready` at task-creation time on tasks born without a
`blocked by` dependency. A task born **with** a `blocked by` dependency is
intentionally created without `sdd:ready` and stays that way until something
promotes it.

ADR 0009 explicitly excludes that promotion from its scope (Out of scope
section) and points to issue #78 for the post-merge gap. The pipeline as it
stands leaves the gap open: `sdd-triage` phase C runs once per `/approve`
and does not re-fire on a task close; `sdd-execute` skips a task without
`sdd:ready`. The result is a stalled cascade where a task is structurally
ready (every blocker is closed) but the label is missing, so no
`sdd-execute` variant picks it up. A human workaround is to apply the label
by hand; that is the failure mode this ADR removes.

## Decision

A new deterministic wrapper, `sdd-triage-promote-ready.yml`, listens on
`issues.closed` in the consumer repository and applies `sdd:ready` to every
task whose last blocker just closed.

1. The wrapper triggers on `issues: { types: [closed] }`. Every issue close
   in the repository invokes it once.
2. The closed issue must be a phase-C task sub-issue. Identification is the
   same triplet `sdd-triage-dedupe-tasks` uses: a `## Task` heading, a `repo:`
   field, and a `proof artifacts:` heading. A non-task close exits with no
   work.
3. The wrapper uses **one** GitHub code search for open issues that contain
   the literal phrase `"blocked by #<closed-number>"` in their body. The
   search is repository-scoped and excludes pull requests. This is the right
   primitive because dependencies cross Unit boundaries: a task in Unit 2 may
   depend on a task in Unit 1, and walking only the closed task's parent
   Unit's siblings would miss cross-Unit promotions (issue #78's "Unit's
   sub-issues" wording is the conservative case; this implementation
   subsumes it).
4. For every search hit:
   - Skip if the hit already carries `sdd:ready` (idempotent).
   - Skip if the hit is not itself a phase-C task (the same triplet
     check).
   - Parse the hit's **full** `depends on:` block for every
     `blocked by #<N>` reference (deduplicated). Multiple-blocker tasks are
     correctly handled: only when **every** blocker is closed does the task
     become ready.
   - Fetch each blocker's state. If any blocker is still open (or the
     fetch fails), leave the hit unpromoted. Conservative: a missed
     promotion can be re-tried on the next blocker close; a false promotion
     would let `sdd-execute` pick a task whose dependencies are still open.
   - When every blocker is closed, apply `sdd:ready` via the GitHub
     `add_labels` REST endpoint. `add_labels` is a set-union: a race with
     a concurrent promotion of the same task is a no-op on the second run.

## Reasoning

- The same backstop pattern as ADR 0006 (`sdd-pr-sanitize`) and ADR 0008
  (`sdd-triage-dedupe-tasks`): a deterministic workflow does the per-item
  work the agent has no event to react to. The agent has no
  `task-close-of-a-blocker` trigger in its schema; a wrapper does.
- The trigger is the cheap, narrow event that already exists. Listening on
  the closed-issue event scales with the close rate, not the open-task count.
  A polling loop would be wasteful here.
- A code search per close, plus one issue-fetch per candidate, plus one
  fetch per blocker, is bounded by the dependency fan-in. In a typical
  feature where a Unit's impl task blocks one or two test tasks, the cost is
  three or four API calls per close. The wrapper does not walk the whole
  tree.
- The wrapper does not need the agent's safe-outputs allow-list because it
  writes through GitHub's REST `addLabels`, not through the `add-labels`
  safe-output. The allow-list on `add-labels` is a `gh-aw` runtime check; a
  github-script step under `permissions: { issues: write }` is not subject
  to it. `sdd:ready` is a free string label here.
- Cross-repo `blocked by owner/repo#<N>` references would not match the
  regex `\bblocked by #(\d+)\b` and so leave their task unpromoted. That is
  conservative: cross-repo task routing is a documented future extension
  (sdd-triage's "seam" comment), and a future change will replace the regex
  and add the cross-repo fetch path together. This ADR does not commit a
  cross-repo design.

## Out of scope

- **Cross-repo dependencies.** A `blocked by owner/repo#<N>` form is not
  promoted by this wrapper. When cross-repo task routing lands, the regex
  and the blocker-fetch step will be extended together. Until then, an
  all-in-repo task graph is fully covered and a graph with cross-repo
  dependencies leaves those edges unhandled.
- **Reopened blockers.** A blocker that closes and is then reopened (within
  the same wall-clock window the promotion runs) can cause a one-time false
  promotion. The model assumes a closed task stays closed; reopening one is
  rare in normal flow and handled by a human at that point. No defence-in-depth
  here.
- **PR-level blockers.** A `blocked by` referencing a PR rather than an
  issue is ignored (the wrapper treats a PR as a non-blocker once GitHub
  returns its `pull_request` payload field). Phase C does not produce such
  references in the current model.

## Verification

- A repository in steady state has zero open tasks referencing
  `blocked by #<N>` for any closed `<N>` without that task also carrying
  `sdd:ready`.
- After `sdd-triage` phase C runs against a Unit whose tasks include
  `Task A` (no blockers) and `Task B` (`blocked by #A`): Task A carries
  `sdd:ready` immediately (ADR 0009); Task B carries only `model:*`.
  After Task A's implementation PR merges (which closes Task A via the
  PR's `Closes #A`), this wrapper fires and Task B gains `sdd:ready`
  before the next `sdd-dispatch` re-fire.
- The two-blocker case (Task C `blocked by #A, blocked by #B`): closing
  Task A alone does not promote C; closing Task B (or whichever closes
  second) does.
- Two near-simultaneous closes that both unblock the same task converge
  on the same label state — `add_labels` is set-union, and the second
  run's idempotency check exits before writing.

## Consequences

- The post-merge promotion gap closes. `sdd-execute`'s eligibility check
  no longer needs a human workaround for blocked tasks.
- One new wrapper file installed by `quick-setup.sh`. The wrapper is
  self-contained (one job, one step) and does not consume an `sdd-*`
  reusable workflow.
- A consumer repository where the gap was masked by an external label
  bot will receive two `add_labels` writes: one from the bot and one
  from this wrapper. Both write the same label, so the combined effect
  is unchanged. The bot can be removed once this wrapper lands.
