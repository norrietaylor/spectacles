---
id: adr-0024
title: Opt-in auto-dispatch on phase C completion
kind: adr
status: accepted
supersedes:
superseded-by:
---

# ADR 0024: Opt-in auto-dispatch on phase C completion

- Status: Accepted (companion to ADR 0023)
- Date: 2026-06-12

## Context

On the full path, `/approve` materializes the task tree (ADR 0010) and
the tracking issue reaches `sdd:ready` — and then the pipeline stops
until a human types `/dispatch` (ADR 0011). The same consumer pilot
feedback behind ADR 0023 counted that second command among the four
human gates that made a small feature take ~2 days: after `/approve`,
`/dispatch` adds no new decision — the human already committed the
structure — it only adds latency.

## Decision

A new optional repository variable, **`SDD_AUTO_DISPATCH`** (unset =
off). When set to `1` or `true`, the tracking issue gaining `sdd:ready`
— the label `sdd-triage` applies when phase C completes — routes
through `wrappers/sdd-dispatch.yml` as a first `/dispatch`
(`trigger_kind: 'command'`): the cascade arms (`sdd:dispatched`), the
lifecycle moves `sdd:ready → sdd:in-progress`, and the ready set fans
out.

Two deterministic guards in `sdd-route-dispatch`:

- **Tracking issues only.** `sdd:ready` is also applied to each ready
  *task* sub-issue; the labeled issue must have no parent (GraphQL
  `Issue.parent`, the authoritative source per issue #133; a lookup
  error declines, fail closed).
- **A materialized tree.** At least one sub-issue must exist under the
  tracking issue. If the label lands before the tree (a safe-output
  ordering race), arming would let the lifecycle job mistake the empty
  tree for a drained one and stamp `sdd:done`; auto-dispatch declines
  instead and a manual `/dispatch` is the fallback.

`/dispatch` remains the manual command and the pause/resume control:
removing `sdd:dispatched` pauses the cascade, a `/dispatch` resumes it
(ADR 0011 unchanged).

## Reasoning

- **No new decision is automated away.** `/approve` is the structural
  commitment; auto-dispatch only removes the latency between commitment
  and execution. Operators who want the pause keep the default (off).
- **Reuse, not new machinery.** The labeled event routes as the
  existing `command` kind, so compute, dispatch, lifecycle, and
  noop-comment jobs run untouched; the entire feature is one trigger
  branch plus one wrapper gate.
- **Shipped now, not on demand.** The variable costs one routing branch
  and removes a documented gate from the pilot's critical path; waiting
  for a second request would re-pay the discovery cost.

## Verification

- `wrappers/sdd-dispatch.yml` listens for `issues: labeled` and its
  route gate admits only `sdd:ready` with `SDD_AUTO_DISPATCH` set.
- `sdd-route-dispatch` arms only for a parentless issue with at least
  one sub-issue, and declines (with a log line) otherwise.
- With the variable unset, a `sdd:ready` label gain spawns no dispatch.
- `docs/sdd/install.md` documents `SDD_AUTO_DISPATCH` (unset = off).

## Consequences

- One new optional repository variable, `SDD_AUTO_DISPATCH`.
- `sdd:ready` label events now spawn a route runner when the variable
  is set (task-level `sdd:ready` labels are filtered in the route
  step); unset consumers see no new runs.

## Cross-links

- **ADR 0023** — the agile single-PR path; this is its full-path
  companion from the same feedback (issue
  [#255](https://github.com/norrietaylor/spectacles/issues/255)).
- **ADR 0011** — the dispatch cascade this arms automatically.
- **ADR 0010** — `/approve` as the structure-commitment gate that
  precedes it.
