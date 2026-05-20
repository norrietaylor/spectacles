# ADR 0009: `sdd:ready` set at task-creation time

- Status: Accepted
- Date: 2026-05-20

## Context

ADR 0005 makes the sub-task the unit of work that `sdd-execute` picks up. A
sub-task is eligible only when it carries the `sdd:ready` label (and has no
open `blocked by` dependency, and matches the model tier, etc.). `sdd-triage`
phase C is the agent that creates the sub-tasks and the agent that turns the
unblocked ones into `sdd:ready` candidates.

Phase C step 8 originally split that into two moves: one `create-issue` per
sub-task with the `model:*` tier label, then a separate `add_labels` call per
unblocked sub-task to attach `sdd:ready`. Issue #63 records the failure mode:
in the failing end-to-end run for feature #53, the agent emitted exactly one
`add_labels` message — for the feature itself — and zero per-task ones. The
two unblocked tasks (#64, #65) were created with `model:haiku` only. With no
`sdd:ready` label they failed `sdd-execute`'s eligibility check, and only a
manual `/execute` could move the work forward.

This is the same family of failure ADR 0007 fixed for `link-sub-issue`: a
per-item step the agent must remember to emit once per item, and forgets. The
`add-labels` safe-output is provisioned `max: 20` and `sdd:ready` is on the
allowed list, so the cap is not the cause — the agent simply does not emit the
per-task messages.

## Decision

`sdd:ready` for an unblocked task sub-issue is set in the `labels` field of
the same `create-issue` safe-output call that creates it, alongside the
`model:*` tier label.

1. `gh-aw`'s `create-issue` safe-output takes a `labels` array. The validation
   schema places no allow-list restriction on `create-issue.labels` — it is a
   plain string array — so `sdd:ready` is a legal value there even though the
   `add-labels` safe-output's allow-list is `[sdd:ready, needs-human]`.

2. In `sdd-triage` phase C (step 6), the `create-issue` call for each sub-task
   carries:
   - the `model:*` tier label (unchanged), and
   - `sdd:ready` when, and only when, the sub-task has zero `blocked by`
     dependency lines in its structured body block.

3. Phase C step 8 no longer applies `sdd:ready` to task sub-issues via
   `add-labels`. The bullet that asked the agent to do so is removed. The
   step still moves the **feature tracking issue** from `sdd:triage` to
   `sdd:ready` via `remove-labels` and `add-labels`, because the feature
   tracking issue is a single, pre-existing issue and that move is one message,
   not one-per-item.

## Reasoning

- The unblocked-or-not predicate is a property of the task the agent is
  composing in step 6; it is already deciding the task's body, its `model:*`
  tier, and its `blocked by` lines in the same call. Folding the lifecycle
  label into that decision adds no new piece of information and no new step.
- Labelling is now a field of a message the agent already emits, not a second
  message it can omit. The failure mode — `create` without per-task
  `add_labels` — no longer has a separate step to drop. This is the structural
  fix in the same spirit as ADR 0007 (link-on-create) and ADR 0006 (sanitize
  rather than re-prompt): a step the agent skipped is removed, not re-worded.
- The `create-issue.labels` field is not allow-list-restricted in the
  safe-outputs validation schema, so `sdd:ready` and `model:*` can co-exist in
  one call. The allow-list on `add-labels` is a runtime-only restriction; it
  does not propagate to `create-issue.labels`.

## Out of scope

A sub-task born with one or more `blocked by` lines is not born `sdd:ready`.
When the last blocker closes, that sub-task is structurally eligible but still
carries no `sdd:ready` label, so `sdd-execute`'s eligibility check rejects it.
Issue #63 calls this the post-merge gap. Closing it requires a new
event-driven hook (an agent that listens on issue-close events for blocked
sub-tasks and promotes them), which is a different change and is tracked
separately. This ADR keeps the scope to creation time.

## Verification

- `sdd-triage` declares no extra `add-labels` allow-list entry: `sdd:ready`
  was already permitted for the feature-level move, and `model:*` is set only
  via `create-issue.labels`.
- After `sdd-triage` phase C runs against a Unit whose sub-tasks include at
  least one unblocked task and one blocked task: every unblocked task carries
  `sdd:ready` and `model:*`; every blocked task carries only `model:*` and no
  `sdd:ready`.
- The safe-outputs log shows zero `add_labels` messages targeting a task
  sub-issue. The only `add_labels` message phase C emits is the feature-level
  `sdd:ready` move (step 8).

## Consequences

- Phase C step 8 emits one fewer message class. The feature-level lifecycle
  move is unchanged.
- The post-merge promotion of a blocked task to `sdd:ready` (when its last
  blocker closes) remains unimplemented and is the only remaining path by
  which a created-blocked task becomes eligible. It is tracked separately
  from this ADR.
