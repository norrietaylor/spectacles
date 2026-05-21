---
on:
  workflow_call:
    inputs:
      aw_context:
        description: The triggering entity, resolved by the wrapper.
        required: true
        type: string
  # roles: all — this agent is activated by automation events (App-authored
  # label writes, issues.closed on a sub-issue under a sdd:dispatched tracking
  # issue) and by /dispatch from a write-access human. The default roles gate
  # (admin/maintainer/write) cancels a bot-triggered run at pre_activation; the
  # wrapper's route job is the real gate. See ADR 0004.
  roles: all
permissions:
  contents: read
  issues: read
  pull-requests: read
engine: copilot
inlined-imports: true
strict: false
imports:
  - norrietaylor/spectacles/shared/principles.md@main
  - norrietaylor/spectacles/shared/repo-conventions.md@main
  - norrietaylor/spectacles/shared/sdd-interaction.md@main
tools:
  github:
    toolsets: [default]
safe-outputs:
  github-app:
    client-id: ${{ vars.APP_ID }}
    private-key: ${{ secrets.APP_PRIVATE_KEY }}
    # Scope the minted token to the repository the workflow runs in. Without an
    # explicit repositories value the compiler emits a reference to an
    # activation output that strict: false does not produce, leaving the token
    # scoped to every repository the App can reach. See ADR 0004.
    owner: ${{ github.repository_owner }}
    repositories:
      - ${{ github.event.repository.name }}
  add-comment:
    max: 1
  noop:
---

# sdd-dispatch

`sdd-dispatch` is the cascade orchestrator of the issue-native SDD pipeline.
It turns a `/dispatch` comment on a tracking issue into bounded matrix
fan-out of `sdd-execute` runs across every ready task in the feature's task
tree, then keeps that cascade alive on every task-close event under the same
tracking issue until the tree is drained.

## A deterministic agent

This agent is unusual in the spectacles suite: its work is entirely
deterministic — walk a sub-issue tree, parse `blocked by` lines, compute a
set, post `/execute` on each ready task issue via the App installation
token, apply two labels — and there is no natural-language judgement for an
LLM to add. The dispatcher is therefore implemented in the wrapper at
`wrappers/sdd-dispatch.yml` as a chain of `actions/github-script` jobs
(`route`, `compute`, `dispatch`, `lifecycle`, `noop-comment`), and **this
`.md` agent is not invoked at runtime**. It exists for two reasons:

1. **Contract documentation.** This file is the canonical statement of
   the cascade contract — selection, parallelism, persistence, lifecycle,
   noops, in-flight detection — that the wrapper implements. A reader who
   wants to know what the dispatcher does reads this file, not the
   wrapper.
2. **ADR 0004 compile-drift parity.** The lint workflow's `compile` job
   runs `gh aw compile` and fails on any committed `.lock.yml` that has
   drifted from its `.md` source. Authoring `sdd-dispatch.md` here keeps
   the suite's compile gate uniform: every `.lock.yml` in the suite is the
   compiled output of a sibling `.md` source.

The wrapper's deterministic implementation is the source of truth for the
runtime behavior. This document is the source of truth for the contract.
When they disagree, the wrapper is the bug; reconcile by editing the
wrapper to match this document.

## The cascade contract

Selection is **graph-driven**, not label-driven. At each fire, the
dispatcher computes the ready set from the dependency graph: every open
task sub-issue under the tracking issue whose `blocked by` set is empty
(every referenced blocker is closed). The `sdd:ready` label is a
downstream artifact applied to whatever the dispatcher dispatches, kept as
a hint for humans browsing the tree, not the source of truth for
eligibility. A task that was born blocked and is now structurally
unblocked is ready even if nobody has flipped its `sdd:ready` label yet;
a task that carries `sdd:ready` but has gained a new open blocker is not
ready. The graph wins.

The two triggers the dispatcher handles:

1. **A write-access author commented `/dispatch` on a tracking issue.**
   The dispatcher validates the precondition (the tracking issue must
   carry `sdd:ready` or `sdd:in-progress`), computes the ready set, fans
   out to `sdd-execute` variants, applies `sdd:dispatched` on the tracking
   issue, and on the first dispatch moves the tracking issue from
   `sdd:ready` to `sdd:in-progress`. This is the explicit human start.
2. **A task sub-issue closed under a `sdd:dispatched` tracking issue.**
   The route job walks the closed sub-issue's parent chain (task → Unit →
   tracking issue per ADR 0005) and only proceeds when the tracking issue
   carries `sdd:dispatched`. The same dispatcher run: recompute the ready
   set against the new tree state (the just-closed task's dependants may
   now be unblocked) and fan out again. On the cascade path the lifecycle
   label is not touched; the first `/dispatch` already advanced it, and
   the completion sweep in `sdd-execute` still owns the `sdd:done`
   transition.

## Preconditions

`/dispatch` is valid only when the tracking issue carries `sdd:ready` or
`sdd:in-progress`. Earlier states (`sdd:spec`, `sdd:triage`) get a
one-comment refusal explaining the prerequisite; later states
(`sdd:review`, `sdd:done`) get a noop comment. The cascade path implies
the precondition (only a tracking issue carrying `sdd:dispatched` reaches
the dispatcher on that path, and `sdd:dispatched` is only applied
alongside `sdd:in-progress`), so the precondition check is skipped on a
cascade fire as a fast path; the wrapper's `compute` job still records
the lifecycle state for the lifecycle job to read.

A tracking issue carrying `needs-human` defers unconditionally. A
`needs-human`-labelled item is off-limits during candidate selection (see
the imported interaction contract); the hand-off comment has already been
posted and must not be posted again.

**Fast-path tracking issues are not eligible for `/dispatch`** (ADR
0012). A tracking issue carrying `sdd:fastpath` or `sdd:fastpath-review`
runs a single-task flow; the cascade fan-out machinery is unused. On
that input, the wrapper's `route` job emits `trigger_kind:
'fastpath_noop'`, the `compute`, `dispatch`, and `lifecycle` jobs all
short-circuit, and the `fastpath-noop-comment` job posts one comment
pointing the human at `/approve` (which `sdd-spec`'s wrapper handles
on a fast-path issue). `sdd:dispatched` is never applied on this
input.

## Parallelism

Bounded matrix fan-out. The dispatcher expands the ready set into a
GitHub Actions matrix; each cell posts `/execute` on one task issue via
the App installation token, and the matching `sdd-execute-{tier}` wrapper
picks the comment up through its existing `issue_comment` trigger (the
wrapper's job-level `if:` gate filters to the matching tier on the basis
of the task's `model:*` label). `max-parallel` defaults to **5**,
overridable per repo via the `SDD_DISPATCH_MAX_PARALLEL` repo variable
(any positive integer). A ready set larger than the cap queues at the
matrix level; cells start as earlier ones finish. The comment side-effect
mechanism replaces the prior `workflow_dispatch` REST fan-out, which
required an `actions: write` scope on the App that consumer installs did
not reliably grant (issue #121, ADR 0014).

## In-flight detection

A task is **in flight** if it carries `sdd:in-progress` or if there is an
open pull request linked to it (the head branch matches
`sdd/<task-id>-<slug>` for this task, or the body carries a
`Closes #<task>` reference). The dispatcher removes in-flight tasks from
the ready set before fanning out. As a defence in depth, the
`sdd-execute-{tier}` wrappers carry a concurrency group keyed on the
task issue number AND the tier (`sdd-execute-<tier>-<task>`), so a
double-`/execute` on the same task in the same tier collapses to one
running cell and the second is treated as an idempotent no-op. The tier
discriminator is required because the three tier wrappers all subscribe
to the same event triggers; the per-tier dimension keeps a non-matching
wake from cancelling the matching one (issue #124).

## Lifecycle

On the first `/dispatch` for a tracking issue (the tracking issue still
carries `sdd:ready`, and `sdd:dispatched` is not yet present), the
dispatcher moves `sdd:ready` → `sdd:in-progress` on the tracking issue
and adds `sdd:dispatched`. Exactly one lifecycle label is present at a
time, so the move is a single remove plus add. `sdd:dispatched` is **not**
a lifecycle label — it is the cascade marker that coexists with the
lifecycle label, the same way `needs-human` does (see the imported
interaction contract).

On a re-`/dispatch` while `sdd:dispatched` is already present, or on a
cascade fire, the lifecycle label is left alone. The first `/dispatch`
already advanced it.

When every task sub-issue under the tracking issue is closed (the ready
set is empty and no open task exists), the dispatcher removes
`sdd:dispatched` so the cascade disarms. The `sdd:done` transition itself
stays in `sdd-execute`'s completion path (ADR 0005). A human can remove
`sdd:dispatched` by hand at any time to pause the cascade; replacing it
with another `/dispatch` resumes.

## Noops

If the precondition fails, the dispatcher posts one short comment naming
the required state and exits without dispatching. If the ready set is
empty:

- **Every task sub-issue is closed.** Remove `sdd:dispatched` and post
  one comment confirming the cascade has disarmed. `sdd-execute` owns the
  `sdd:done` transition.
- **Some tasks are open but every one is blocked or in flight.** Leave
  `sdd:dispatched` in place — this is the normal mid-cascade idle state,
  and the next `issues.closed` event will resume the cascade. Post one
  comment naming the reason on the `/dispatch` path; the cascade path
  posts no comment, to keep the tracking-issue thread quiet between
  fan-outs.

A second `/dispatch` while the cascade is armed is idempotent: it
recomputes the ready set against the current tree state and dispatches
anything not already in flight.

## Boundaries

- The dispatcher edits no file in the repository. Its writes are: label
  changes on the tracking issue and on each dispatched task; one comment
  on noop or refusal paths; one `/execute` comment per dispatched task
  (the cascade fan-out — see ADR 0014). All token-bearing operations use
  the App-minted installation token per ADR 0004, scoped to the running
  repository.
- The dispatcher never opens or closes a pull request, never closes the
  tracking issue, and never closes a task sub-issue. The `sdd:dispatched`
  on-arm and off-disarm transitions on the tracking issue are the only
  lifecycle effects on the cascade path; the `sdd:ready →
  sdd:in-progress` move happens once, on the first `/dispatch`.
- The dispatcher never removes `needs-human`.
- The dispatcher runs no Distillery or Serena query. It declares no MCP
  server. The imports it carries (`principles`, `repo-conventions`,
  `sdd-interaction`) define the conventions and the lifecycle vocabulary
  the dispatcher reads from labels.

## Verification

- `gh aw compile` compiles this workflow with the three imported shared
  fragments and reports zero errors.
- A tracking issue carrying `sdd:ready` with five independent open task
  sub-issues, given a `/dispatch` from a write-access author, posts
  `/execute` on each of the five task issues; the matching
  `sdd-execute-{tier}` wrapper runs for each (bounded by
  `SDD_DISPATCH_MAX_PARALLEL`); the dispatcher applies `sdd:dispatched`
  and moves the tracking issue from `sdd:ready` to `sdd:in-progress`.
- Closing a task whose closure removes the last `blocked by` of two
  sibling tasks under a tracking issue carrying `sdd:dispatched` causes
  the dispatcher to re-fire and dispatch the two newly-unblocked
  siblings, with no `/dispatch` comment needed.
- `/dispatch` on a tracking issue in `sdd:spec` or `sdd:triage` posts one
  refusal comment naming the required state and emits no `/execute`
  fan-out; `sdd:dispatched` is not applied.
- Removing `sdd:dispatched` by hand stops the cascade: a subsequent task
  close does not re-fire dispatch. A subsequent `/dispatch` resumes.
- Every task sub-issue closes → the dispatcher removes `sdd:dispatched`.
  The `sdd:done` transition itself stays in `sdd-execute`'s completion
  path.
- A second `/dispatch` while the cascade is armed dispatches only tasks
  not already in flight; the concurrency group on `sdd-execute-*`
  prevents double-execution of an in-flight task.
