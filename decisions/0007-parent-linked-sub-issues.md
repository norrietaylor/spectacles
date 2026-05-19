# ADR 0007: Parent-linked sub-issue creation

- Status: Accepted
- Date: 2026-05-18

## Context

ADR 0005 makes a feature a tree of sub-issues: a spec sub-issue, an
architecture sub-issue, one Unit sub-issue per demoable unit, and task
sub-issues under each Unit. The agents built that tree in two safe-output steps
per node — a `create-issue` to make the issue, then a `link-sub-issue` to nest
it under its parent.

An end-to-end run showed the two-step pattern is unreliable. `sdd-triage` phase
B created both Unit sub-issues for a feature with `create-issue` and emitted
zero `link-sub-issue` messages. Both Units were created unparented. `sdd-spec`,
which creates a single sub-issue, had emitted its one `link-sub-issue`
correctly; phase B, creating two, dropped both. The link is a separate message
the agent must remember to emit once per created issue, and it forgot.

An unparented Unit is not cosmetic. `sdd-execute` decides a feature is complete
by walking the tracking issue's sub-issue list (ADR 0005 point 4); a Unit
missing from that list is invisible to the completion check, and the feature
never reaches `sdd:done`.

## Decision

Every sub-issue is created with its parent set in the same step.

1. `gh-aw`'s `create-issue` safe-output takes a `parent` field — the issue
   number of the parent. When set, `create-issue` nests the new issue as a
   sub-issue of `parent` as it creates it.

2. Every agent that creates a sub-issue sets `parent` on the `create-issue`
   call:
   - `sdd-spec` creates the spec sub-issue with `parent` set to the tracking
     issue.
   - `sdd-triage` phase A creates the architecture sub-issue with `parent` set
     to the tracking issue.
   - `sdd-triage` phase B creates each Unit sub-issue with `parent` set to the
     tracking issue.
   - `sdd-triage` phase C creates each task sub-issue with `parent` set to its
     Unit issue.

3. The `link-sub-issue` safe-output is removed from `sdd-spec` and
   `sdd-triage`. No agent emits a separate link step.

## Reasoning

- The parent is always a pre-existing issue with a known number — the tracking
  issue for the spec, architecture, and Unit sub-issues; the Unit for task
  sub-issues. The agent never has to correlate a just-created issue's number,
  so `parent` is always a plain value already in hand.
- Linking is now a field of a message the agent already emits, not a second
  message it can omit. The failure mode — `create` without `link` — no longer
  has a separate step to drop. This is the structural fix, in the spirit of
  ADR 0006: a step the agent skipped is removed, not re-worded.

## Verification

- After `sdd-spec` runs, the spec sub-issue appears in the tracking issue's
  sub-issue list.
- After `sdd-triage` phase B runs, every Unit sub-issue appears in the tracking
  issue's sub-issue list.
- After `sdd-triage` phase C runs, every task sub-issue appears in its Unit's
  sub-issue list.
- `sdd-spec` and `sdd-triage` declare no `link-sub-issue` safe-output.

## Consequences

- ADR 0005's two-step `create-issue` plus `link-sub-issue` mechanism is
  replaced. The tree model of ADR 0005 is unchanged; only how a node attaches
  to its parent changes.
