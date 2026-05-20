# ADR 0011: Event-driven cascade dispatch

- Status: Accepted
- Date: 2026-05-20

## Context

Until this ADR, `sdd-execute` ran on a daily cron in each of its three
model-tier variants. A feature with N independent tasks took N days to
drain: each run picked one task off the `sdd:ready` queue, and the next
task had to wait for the next day's cron tick. The user had no first-class
way to say "run the plan now," and no way to express parallelism across
independent tasks. The cron was a queue with depth 1 and a 24-hour latency
floor.

Three things compounded the cost. First, selection was label-driven: a task
became eligible only when `sdd:ready` was on it, and `sdd:ready` was only
set on **unblocked** tasks at creation (ADR 0009). A task born blocked
that later became structurally unblocked still carried no `sdd:ready`, so
the post-merge promotion gap (issue #78) had to be patched separately for
the cron model to make any forward progress on a chain longer than one.
Second, the cron tied execution to wall-clock time rather than the
GitHub event that actually marks "now we can do more." A `/approve` at
9am had to wait until 7am the next morning to see any task start.
Third, parallelism was zero by construction: one cron tick selected one
task per tier, and three tiers competing for the same `sdd:ready` queue
selected at most three tasks total per day, none of which was the desired
"run every ready task at once."

The right model is event-driven cascade execution. An explicit human
command — `/dispatch` — arms the cascade. A new agent computes the ready
set from the dependency graph (not from the `sdd:ready` label), fans out
to `sdd-execute` variants in a bounded matrix, and the same event-driven
loop re-fires on every task close until the tree is drained. The
`sdd:ready` label becomes a UI hint rather than a gate, the cron goes
away entirely, and parallelism is a single repo variable.

## Decision

1. **A new `sdd-dispatch` agent owns cascade execution.** A `/dispatch`
   comment on a tracking issue from a write-access author arms persistent
   matrix fan-out of `sdd-execute` runs across every ready task in the
   feature's task tree. The agent ships as a `.md` source compiled to a
   `.lock.yml` (for ADR 0004 distribution parity and the lint compile-drift
   gate) and a hand-written wrapper at `wrappers/sdd-dispatch.yml` that
   carries the real triggers and does the deterministic work. The wrapper
   is the source of truth for runtime behavior; the `.md` is the source of
   truth for the contract.
2. **Selection is graph-driven, not label-driven.** At each fire,
   `sdd-dispatch` walks the tracking issue's sub-issue tree (Feature →
   Unit → task per ADR 0005), parses each open task's `## Task` block's
   `depends on:` lines, and admits a task only when every `blocked by`
   reference resolves to a closed issue and the task is not already in
   flight. The `sdd:ready` label is not part of the eligibility
   predicate; the dispatcher applies it to each dispatched task as a UI
   hint for humans browsing the tree. A task born blocked that is now
   structurally unblocked is ready; a task carrying `sdd:ready` that has
   a new open blocker is not. The graph wins.
3. **Parallelism is bounded matrix fan-out.** The wrapper expands the
   ready set into a GitHub Actions matrix with `max-parallel:
   ${{ fromJSON(vars.SDD_DISPATCH_MAX_PARALLEL || '5') }}`, defaulting
   to 5 and overridable per repo. Each cell dispatches a single
   `sdd-execute-{tier}` run for one task via the `workflow_dispatch`
   REST endpoint, with the task issue number passed through as
   `aw_context`. A ready set larger than the cap queues at the matrix
   level and starts more cells as earlier ones finish.
4. **Persistence is a `sdd:dispatched` cascade marker on the tracking
   issue.** On the first `/dispatch`, `sdd-dispatch` applies
   `sdd:dispatched` to the tracking issue and moves the lifecycle from
   `sdd:ready` to `sdd:in-progress`. While `sdd:dispatched` is present,
   every `issues.closed` event on a task sub-issue under the tracking
   issue re-fires `sdd-dispatch`; it recomputes the ready set against
   the new tree state (the just-closed task's dependants may now be
   unblocked) and fans out again. When every task sub-issue is closed,
   the dispatcher removes `sdd:dispatched`; the `sdd:done` transition
   itself stays in `sdd-execute`'s completion path (ADR 0005). A human
   can remove `sdd:dispatched` by hand to pause; replacing it with
   another `/dispatch` resumes. `sdd:dispatched` is **not** a lifecycle
   label — it coexists with the `sdd:*` lifecycle label the same way
   `needs-human` does.
5. **The daily cron is removed from every `sdd-execute` variant.** The
   `schedule:` block is deleted from each of
   `wrappers/sdd-execute-{haiku,sonnet,opus}.yml`, and from each of
   `.github/workflows/sdd-execute-{haiku,sonnet,opus}.md`. Execution
   is fully event-driven: `sdd-execute` runs only on
   `workflow_dispatch` (from `sdd-dispatch`) and `issue_comment`
   filtered to `/execute`. The chain is `/approve` → `/dispatch` →
   cascade-on-close. `/execute` from a human stays available as the
   bypass for one-off task runs.
6. **Authorization for `/dispatch` is write-access only.** The wrapper's
   route job calls `repos.getCollaboratorPermissionLevel` and admits
   only `write`, `maintain`, or `admin`, the same gate `/triage`,
   `/approve`, and `/execute` use.
7. **Preconditions on `/dispatch`.** Valid only when the tracking issue
   carries `sdd:ready` or `sdd:in-progress`. Earlier states (`sdd:spec`,
   `sdd:triage`) get a one-comment refusal explaining the prerequisite;
   later states (`sdd:review`, `sdd:done`) get a one-comment noop. The
   cascade path (`issues.closed`) implies the precondition because the
   route job's filter is `sdd:dispatched`-on-the-tracking-issue, and
   `sdd:dispatched` is only applied alongside `sdd:in-progress`.
8. **Noops.** If the ready set is empty:
   - **Every task is closed.** Remove `sdd:dispatched` and post one
     comment naming the disarm. `sdd-execute` owns the `sdd:done`
     transition.
   - **Some tasks are open but every one is blocked or in flight.** This
     is the normal mid-cascade idle state. Leave `sdd:dispatched` in
     place — the next `issues.closed` event will resume the cascade —
     and post one comment naming the reason on the `/dispatch` path;
     the cascade path posts no comment, to keep the tracking-issue
     thread quiet between fan-outs.
9. **In-flight detection.** A task is "in flight" if it carries
   `sdd:in-progress` or if there is an open pull request linked to it
   (head branch matching `sdd/<task-id>-<slug>`, or body carrying
   `Closes #<task>`). The dispatcher removes in-flight tasks from the
   ready set. As a defence in depth, each `sdd-execute-{tier}` wrapper
   declares a concurrency group keyed on the task issue number so a
   double-trigger (a stale dispatch racing with a manual `/execute`)
   collapses to one running cell.

## Reasoning

- **Latency.** Cron-driven execution had a 24-hour latency floor on every
  hop in a dependency chain. Event-driven cascade replaces it with the
  GitHub event latency (seconds), so a tree of N independent tasks
  finishes in roughly one task-runtime rather than N days.
- **Parallelism.** Three tiers × one task per cron tick = at most three
  concurrent tasks. The matrix model expresses parallelism directly: the
  default cap of 5 covers typical features without needing a per-repo
  setting, and the cap is one variable away on a repo whose CI capacity
  allows more.
- **Graph as source of truth.** `sdd:ready` was always a derived state —
  "the graph says you can run me now" — but the cron model treated the
  label as primary. The post-merge promotion gap (issue #78) is the visible
  symptom of that inversion. Moving the predicate to the graph makes the
  label redundant for eligibility but useful as a UI signal, the way it
  shows up in the GitHub label filter and the tree view. The two failure
  modes #78 was meant to backstop (a blocked task born without `sdd:ready`
  whose blocker closed; a task whose `sdd:ready` was stripped manually)
  both stop being failure modes because the dispatcher reads the graph,
  not the label.
- **Persistence as a marker, not a state.** A cascade that turns off when
  it idles, the way the cron stopped after picking one task, is the wrong
  default for a multi-task feature. `sdd:dispatched` is the persistence
  primitive: it stays on through every mid-cascade idle moment (some
  tasks open and blocked, none ready) and only comes off when the tree
  is empty. A human's pause is "remove the label"; a human's resume is
  another `/dispatch`. The on/off pair is the minimal interface for
  user control.
- **Determinism in the wrapper.** This agent's work is entirely
  deterministic — walk a tree, parse `blocked by`, compute a set, call
  REST. There is no LLM-grade judgement to add. The wrapper carries the
  implementation; the `.md` source documents the contract. This is a
  deliberate deviation from the rest of the suite, where the LLM in the
  agent does the work and the wrapper carries triggers only, justified
  by the absence of any natural-language judgement on this code path.
- **Cron removal, not retention.** Keeping the cron alongside the
  cascade would mean a `sdd:ready` task that is structurally not
  dispatched (the human never commented `/dispatch`) could still get
  picked up unattended. The whole point of the `/dispatch` gate is to
  make execution explicit; a residual cron undermines the gate. The cron
  is removed.

## Cross-links

- **ADR 0005** — the Feature → Unit → task tree. `sdd-dispatch` walks
  this tree to find the open task sub-issues for the ready-set
  computation, and the tree shape is unchanged.
- **ADR 0009** — `sdd:ready` set at task-creation time. The label is
  still applied at creation by `sdd-triage`'s phase C; it just stops
  being the eligibility predicate at execution time. The cascade
  re-applies it to every dispatched task as a UI hint.
- **ADR 0010** — plan-comment before tree. `/dispatch` is the second
  human gate in the human-driven sequence (`/approve` is the first). The
  full chain `/approve` → `/dispatch` → cascade is the event-driven
  pipeline.
- **Issue #78** — the post-merge `sdd:ready` promotion gap. The backstop
  it described becomes redundant when the dispatcher reads the graph
  rather than the label. The label-hygiene aid #78 contemplated still
  has value for humans browsing the tree, so the label stays as a UI
  signal even though it is no longer load-bearing.

## Verification

- A tracking issue at `sdd:ready` with five independent open task
  sub-issues, given a `/dispatch` from a write-access author, opens five
  implementation pull requests concurrently — bounded by
  `SDD_DISPATCH_MAX_PARALLEL` — and the tracking issue moves to
  `sdd:in-progress` and gains `sdd:dispatched`.
- Closing a task whose closure removes the last `blocked by` of two
  sibling tasks under a tracking issue carrying `sdd:dispatched` triggers
  `sdd-dispatch` and opens two new implementation pull requests within
  seconds, with no `/dispatch` comment needed.
- `/dispatch` on a tracking issue in `sdd:spec` or `sdd:triage` posts
  one refusal comment naming the required state and does not fan out;
  `sdd:dispatched` is not applied.
- Removing `sdd:dispatched` by hand stops the cascade: a subsequent task
  close does not re-fire dispatch. A subsequent `/dispatch` resumes.
- Every task sub-issue closes → `sdd-dispatch` removes `sdd:dispatched`.
  `sdd-execute`'s completion path moves the tracking issue to
  `sdd:done`.
- `grep -R "schedule:" .github/workflows/sdd-execute-*.md
  wrappers/sdd-execute-*.yml` returns no lines.
- A second `/dispatch` while the cascade is armed dispatches only tasks
  not already in flight; the concurrency group on `sdd-execute-*`
  prevents double-execution of an in-flight task.
- `scripts/quick-setup.sh --target-repo <owner>/<name> --suite sdd
  --dry-run` lists `sdd-dispatch.yml` in its planned-writes output and
  surfaces `SDD_DISPATCH_MAX_PARALLEL` in the operator-supplied-config
  summary.

## Consequences

- A new agent `sdd-dispatch` joins the suite. The agent count goes from
  five to six in the docs and from seven to eight in the installer
  manifest (seven `sdd-*` + `distillery-sync` becomes eight `sdd-*` +
  `distillery-sync` = nine wrappers).
- A new label `sdd:dispatched` joins `templates/.github/labels.yml`,
  coexisting with the lifecycle labels the same way `needs-human` does.
- A new repo variable `SDD_DISPATCH_MAX_PARALLEL` is documented in
  `docs/sdd/install.md` and surfaced by `scripts/quick-setup.sh`.
- Every `sdd-execute-{tier}` wrapper loses its `schedule:` block and
  gains a concurrency group keyed on the task issue number. The agent
  `.md` source loses the prose about "scheduled runs" and the
  six-situation enumeration becomes five.
- The post-merge `sdd:ready` promotion gap (issue #78) is no longer
  load-bearing for execution. The label is now a UI hint applied by
  `sdd-dispatch` to whatever it dispatches; the issue #78 backstop
  remains useful as a label-hygiene aid for humans but is not the
  selection gate.
- The pipeline chain becomes
  `/spec → /approve → /dispatch → cascade-on-close → /done-human-close`.
  Three explicit human commands gate three transitions; nothing else
  runs without one of them.
