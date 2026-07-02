---
id: spec-eval-actor
title: Eval actor — bounded actions on run-evaluation findings
kind: spec
status: planned
tracking-issue:
supersedes:
---

# 04-spec-eval-actor

> The repository is public. This file carries no consumer identity, no
> internal URL, no cost figure. Companion sketch to
> `docs/specs/03-spec-run-evaluation/` — deliberately short; it becomes a
> full spec when the eval surfaces have run long enough to trust.

## Context

The run-evaluation suite (spec 03) is report-only by design: the collector
and judge write scorecards and snapshots, never labels or issues. The
evaluated run showed why the acting half matters — every detected condition
(stranded tasks, stale `needs-human`, recurrence fingerprints, integrity
tripwires) still required a human to translate detection into action. The
actor agent is that translation, kept separate so the reporting surface
stays side-effect-free and the mutation surface carries its own, stricter
trust posture.

## Introduction / Overview

`sdd-eval-actor` is a deterministic utility workflow (no `engine:` in v1 —
every v1 action is a mechanical mapping from a snapshot condition to a
bounded action; an engine-bearing escalation writer can come later). It
consumes `eval_snapshot.json` artifacts and the roll-up issue state, applies
an **action table**, and performs only allowlisted, idempotent, audited
actions. Eval reports; the actor acts; the human still decides anything
irreversible.

## Goals

1. Close the detection→action gap for the conditions the collector already
   proves deterministically.
2. Keep every action bounded (rate-limited, capped, idempotent) and audited
   (one ledger line per action on the roll-up issue).
3. Stay subordinate to the human: the actor never overrides an explicit
   human decision recorded on the item, and `needs-human` remains a
   human-owned hand-off per ADR 0001 — the actor may *apply* it with the
   standard hand-off comment, never *clear* it.

## User Stories

- As an operator, I want stale `needs-human` labels re-validated and flagged
  (not silently cleared) when their cause no longer holds, so I stop
  clearing labels the run outgrew.
- As an operator, I want a stranded task re-dispatched once the blocking
  condition (e.g. a quota window) has passed, instead of hand-typing
  `/execute` two dozen times.
- As a suite maintainer, I want a recurrence fingerprint or integrity
  tripwire to open exactly one well-evidenced framework issue, once,
  with the snapshot attached.

## Demoable Units of Work

### Unit 1: Action table and actuator

**Purpose:** The v1 action table, mechanically applied. Demoable: a seeded
snapshot condition produces exactly the mapped action plus a ledger line.
**Depends on:** spec 03 Units 1–2 (snapshots, roll-up)
**Affected areas:** `wrappers/sdd-eval-actor.yml` (new),
`.github/actions/sdd-eval-actor/action.yml` (new),
`shared/sdd-interaction.md`, `scripts/quick-setup.sh`.

**Functional Requirements:**

- **R1.1**: The actor shall trigger on collector completion (`workflow_run`)
  and on a write-access `/act` comment; it shall be **opt-in**
  (`SDD_EVAL_ACTOR=1`) — unlike the eval surfaces it mutates state, so it
  follows the monitor's opt-in posture, with the spec-03 R1.3 unset-safe
  predicate form.
- **R1.2**: v1 action table (exhaustive; anything not listed is out of
  scope):
  | Snapshot condition | Action | Bound |
  |---|---|---|
  | Stranded task, cause class retriable (quota window elapsed, timeout kill) | one `/dispatch` nudge comment on the tracker | ≤1 per task per 6 h, ≤3 total per task, then hand-off comment + `needs-human` |
  | `needs-human` whose recorded cause tests false against current state | comment on the item naming the stale cause and the passing check | ≤1 per label application; never removes the label |
  | Recurrence fingerprint matching a closed framework issue | open one issue on the framework repository, evidence per `shared/rigor.md`, deduped by fingerprint marker | one issue per fingerprint, ever |
  | Integrity tripwire (net-diff deletion/revert of main-advanced files) on an open PR | request-changes-style comment on the PR quoting the scan; apply `needs-human` with hand-off comment | once per head sha |
  | Judge post-mortem `merged-unnoticed` integrity incident | open one framework issue + comment on the merged PR | once per incident |
- **R1.3**: Every action shall be recorded as one ledger line (timestamp,
  condition, action, target) in a dedicated section of the roll-up issue.
- **R1.4**: The actor shall never: merge, close, or block a PR; edit
  tracking-issue bodies; write lifecycle labels; clear `needs-human`; act on
  any item whose last human comment post-dates the snapshot it is acting on.
- **R1.5**: Identity: the suite App token; permissions the union of what the
  table needs (`issues: write`, `pull-requests: write`, `actions: read`)
  and nothing more.

**Proof Artifacts:**

- Test: seeded stranded-task snapshot → exactly one `/dispatch` nudge and
  one ledger line; second run within the bound window → no action, one
  "bound-suppressed" ledger note. Fails before this unit.
- Test: seeded recurrence fingerprint → exactly one framework issue with the
  fingerprint marker; re-run → no duplicate. Fails before this unit.

## Non-Goals

- No engine in v1; no free-text judgment about what to do.
- No auto-remediation of code (no revert-fixing, no restore PRs) — those are
  pipeline guards' and humans' work.
- No cross-repository actions beyond the single framework-issue table row.
- Not a replacement for sdd-monitor; it acts on eval snapshots, monitor
  stays the dispatch backstop (their overlap — stranded-task nudges — is
  resolved by the actor deferring when monitor attempts are still unspent).

## Design Considerations

The actor is deterministic because every v1 action is condition→action with
no judgment; this keeps it out of ADR 0020 scope and its blast radius
enumerable. The bound columns are the design: each is chosen so the worst
case (a wedged condition looping) produces bounded noise then a hand-off,
never a storm — the evaluated run's monitor demonstrated both the need
(0/6 recoveries) and the failure mode (attempts burned inside minutes
against multi-hour causes).

## Security Considerations

Same injection posture as the collector: snapshot and issue text are data;
commands are token-strict and write-access-gated. The framework-issue row
writes across repositories — its content is generated exclusively from
snapshot fields and never quotes consumer file contents beyond paths.

## Open Questions

- Whether the stranded-task nudge should invoke the dispatch cascade
  directly instead of commenting `/dispatch` (a comment keeps the actor
  inside the human command vocabulary and visible; a direct call is quieter
  but less auditable).
- Whether a later engine-bearing tier should draft escalation summaries for
  the hand-off comments (inference on top of the same bounded actions).

## Gap Analysis

Empty — forward-authored spec.

## Verification

Seed each table row's condition on a test repository and assert the mapped
action, its ledger line, and its bound; assert the four "never" rules of
R1.4 by attempting each and observing refusal; lint gates green.
