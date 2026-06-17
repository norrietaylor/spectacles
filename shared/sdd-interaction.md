# Human-interaction contract

Every `sdd-*` agent imports this fragment so the interaction contract is
defined once and never restated per workflow. It states the lifecycle-label
state machine, the comment-command vocabulary, and the `needs-human` hand-off
contract.

The pipeline is operated entirely through four GitHub primitives: issues,
comments, labels, and pull requests. There is no external task board and no
separate UI. A human steers; agents draft.

## Lifecycle-label state machine

Lifecycle state lives as exactly one `sdd:*` label on the tracking issue. The
agent that completes a phase moves the label to the next state. The label set
is the GitHub-native task board.

```text
Full path: sdd:spec -> sdd:triage -> sdd:ready -> sdd:in-progress -> sdd:review -> sdd:done
Single-PR (fast) path: sdd:spec -> sdd:fastpath -> sdd:fastpath-review -> sdd:fastpath -> sdd:in-progress -> sdd:done
  (with /approve while the spec PR is open — sdd:approved recorded — the
   merge skips the return hop: sdd:fastpath-review -> sdd:in-progress)
```

| Label | Meaning | Set by | Advances on |
|---|---|---|---|
| `sdd:spec` | the feature is being specified | `feature`/`bug` template, or `/spec` | spec PR merged, or `/fastpath` confirms fast-path |
| `sdd:fastpath` | the single-PR (fast) path is armed; awaiting spec merge or `/approve` | `sdd-spec` on `/fastpath` or `/agile`, or spec PR merge | spec PR opened (`sdd:fastpath-review`), or `/approve` on a merged-spec state |
| `sdd:fastpath-review` | single-PR-path spec PR (stub or light) is open and awaiting human merge or a pre-merge `/approve` | `sdd-spec` on the spec PR | spec PR merged (returns to `sdd:fastpath`; with `sdd:approved` recorded the merge dispatches and advances straight to `sdd:in-progress`, ADR 0024) |
| `sdd:triage` | architecture and triage are running | `sdd-spec` on spec-PR merge | architecture PR merged (plan-comment posted), then `/approve` |
| `sdd:ready` | tasks are decomposed and queued | `sdd-triage` on phase C completion | `/dispatch` arms the cascade |
| `sdd:in-progress` | the cascade is armed and tasks are being implemented (full path), or the single fast-path implementation is running | `sdd-dispatch` on the first `/dispatch` (full path), or `sdd-execute` on `/approve` (fast path) | every task sub-issue closes (full path), or the implementation PR merges (fast path) |
| `sdd:review` | the implementation awaits human review | `sdd-validate` on a clean implementation pass | all task sub-issues closed |
| `sdd:done` | every task is complete | `sdd-execute` when all tasks are closed (full path), or `sdd-execute` on the fast-path implementation PR merge | a human does the final close |

Exactly one lifecycle label is present at a time. `sdd:triage` covers all
three `sdd-triage` phases (architecture, plan comment, tree
materialization). `sdd:fastpath` and `sdd:fastpath-review` cover the
single-PR (fast-path) flow from ADR 0012 as generalized by ADR 0024; a
fast-path tracking issue never carries
`sdd:triage`, `sdd:ready`, or `sdd:review`. The `kind:*`, `priority:*`,
and `model:{haiku,sonnet,opus}` labels are orthogonal metadata and are
not part of this state machine.

`sdd:dispatched` is an **orthogonal cascade marker**, not a lifecycle
label. `sdd-dispatch` adds it to the tracking issue on the first
`/dispatch` and removes it when every task sub-issue is closed; while it
is present, every `issues.closed` event on a task sub-issue under the
tracking issue re-fires `sdd-dispatch` and the ready set is recomputed and
fanned out again. A human can remove `sdd:dispatched` by hand to pause
the cascade and replace it with another `/dispatch` to resume. It
coexists with the lifecycle label the same way `needs-human` does.

`sdd:approved` is an **orthogonal approval marker**, not a lifecycle
label (ADR 0024). The deterministic `/approve` handler in `sdd-spec`'s
wrapper records it when a write-access author comments `/approve` on a
single-PR-path tracking issue while the spec PR is still open
(`sdd:fastpath-review`), and — when `SDD_AUTO_MERGE` is set — arms
squash auto-merge on that spec PR. While it is present, the spec PR's
merge event dispatches the single `sdd-execute-{tier}` run
deterministically, clears the marker, and advances the lifecycle to
`sdd:in-progress`; merge and approve therefore commute. The marker is
cleared without dispatching when the approval goes stale: a
`/revise` after approval (the plan or spec changed, so re-approval is
required) or the spec PR closing unmerged. Like `sdd:dispatched` and
`needs-human`, it coexists with the lifecycle label.

`plan:provided` is an **orthogonal translation marker**, not a lifecycle
label. The `spec.md` issue template ("Specification (from Claude plan)")
sets it, and a human can apply it by hand, to declare that the tracking
issue body is a Claude plan document. `sdd-spec` reads it to translate the
plan into a spec, and `sdd-triage` Phase A reads it to translate the
plan's architecture section into `architecture.md`, instead of authoring
either from scratch (issue #102). It is cleared by `sdd-triage` Phase A
when the architecture PR opens — or, on the fast path where triage never
runs, by `sdd-spec` when the stub spec PR opens. Like `sdd:dispatched`
and `needs-human`, it coexists with whatever lifecycle label the tracking
issue carries and survives phase transitions untouched.

## Comment-command vocabulary

A small command vocabulary steers the pipeline. Every command is gated, via
the gh-aw `command:` trigger, to comment authors with write access to the
repository. A command from a non-write user is a no-op.

| Command | Where | Effect |
|---|---|---|
| `/spec` | tracking issue | trigger `sdd-spec` (also auto-applied by the `feature`/`bug` template label); on a fast-path tracking issue it is the misclassification-escalation reset that returns the lifecycle to `sdd:spec` |
| `/fastpath` | tracking issue, after `sdd-spec`'s proposal comment or up front before any agent run | confirm the single-PR classification; `sdd-spec` produces a spec PR (stub or light) and an execution plan comment in one run (ADR 0012, ADR 0024) |
| `/agile` | tracking issue | alias of `/fastpath` (ADR 0024); the two are interchangeable and collapse at routing |
| `/triage` | tracking issue, after the spec PR is merged | trigger `sdd-triage` phase A (architecture) |
| `/approve` | tracking issue | on a full-path tracking issue (`sdd:triage` with a plan-comment posted), materialize the Unit and task sub-issue tree per ADR 0010, collapsing any single-task Unit to a feature-parented task (ADR 0028); on a single-PR-path tracking issue with the spec merged (`sdd:fastpath`), dispatch one `sdd-execute-{tier}` against the execution plan comment per ADR 0012; with the spec PR still open (`sdd:fastpath-review`), record the approval as the `sdd:approved` marker and arm squash auto-merge on the spec PR — the merge then dispatches, so merge and approve commute (ADR 0024) |
| `/dispatch` | tracking issue, in `sdd:ready` or `sdd:in-progress` (full path) | arm cascade execution of every task in the feature's task tree; on a fast-path tracking issue carrying `sdd:fastpath` or `sdd:fastpath-review`, `/dispatch` is a noop with a one-comment explanation pointing at `/approve`; on a fast-path `sdd:in-progress` tracking issue, `/dispatch` is a noop with a one-comment explanation that execution is already running and `/approve` should not be used again (ADR 0012) |
| `/revise <note>` | spec PR, architecture PR, tracking issue, or implementation PR | re-run the owning agent with the note as an added instruction |
| `/execute` | a task sub-issue | trigger `sdd-execute` for that task immediately, outside the cascade |
| `/status` | tracking issue, or any sub-issue under one | force-refresh the deterministic `sdd-status` comment — the one self-updating status surface per tracking issue, located by its `<!-- sdd-status -->` sentinel and edited in place; the ack is an eyes reaction on the command comment, never a new comment (issue #254) |

Merging the spec PR advances to the architecture phase; merging the
architecture PR advances to a plan-comment phase. `/approve` is the one
non-PR decision point at which structure is committed to the tree (ADR
0010). `/dispatch` is the second non-PR decision point on the full
path: it arms the event-driven cascade that runs the tasks. Execution
is fully event-driven: `/approve` → `/dispatch` → cascade-on-close (ADR
0011). With the optional `SDD_AUTO_DISPATCH` repository variable set,
the cascade arms automatically when `sdd-triage` phase C completes (the
tracking issue reaches `sdd:ready` with a materialized tree);
`/dispatch` remains the manual command and — via removing and
re-arming `sdd:dispatched` — the pause/resume control (ADR 0025).

The single-PR (fast-path) flow — ADR 0012, generalized by ADR 0024 —
compresses the same gates for work that fits in one implementation PR.
`sdd-spec` proposes the path or honours an
explicit `/fastpath` (or `/agile`); on confirmation it produces a spec
PR — a compressed stub for trivial work, a light spec (multiple units,
full R-IDs, optional Design notes) for anything up to the
`SDD_AGILE_MAX` diff ceiling — and
posts the execution plan as one comment on the tracking issue. One
`/approve` then collapses the remaining gates: typed while the spec PR
is open, it records the `sdd:approved` marker and arms squash
auto-merge so the merge dispatches the single `sdd-execute-{tier}` run;
typed after the merge, it dispatches directly. Either order works. The
spec sub-issue closes via the
existing `Closes` keyword on merge. `/dispatch` is unused
on this flow: before the dispatch (lifecycle at `sdd:fastpath` or
`sdd:fastpath-review`), the noop comment points at `/approve`; after
it (lifecycle at `sdd:in-progress`), the noop comment states
that execution is already running.

## The `needs-human` contract

`needs-human` is the uniform agent-to-human hand-off marker for the whole
pipeline. It is defined by ADR 0001 (`decisions/0001-needs-human.md`); the
four clauses below are repeated here so an importing workflow has the contract
inline.

1. **Apply at the terminal state.** An agent applies `needs-human` (via the
   `add-labels` safe-output) at the step where it decides it cannot safely
   proceed, and posts exactly one comment stating the blocker and what it
   needs.
2. **Treat a labelled item as off-limits.** Every agent skips
   `needs-human`-labelled issues and pull requests during candidate
   selection. This is the idempotency guarantee: the hand-off comment posts
   once, never once per run.
3. **Never remove the label.** No agent ever clears `needs-human`. Only a
   human clears it, which is the signal that the human has taken over or
   resolved the blocker.
4. **Resume on removal.** Clearing `needs-human` fires an `unlabeled` event
   that re-triggers the agent that applied it. The agent re-reads the thread,
   including the human's new comment, and resumes.

`needs-human` is a hand-off state, not a content category, and is kept
distinct from the `kind:*` labels. For the per-agent table of when each agent
applies `needs-human`, see `decisions/0001-needs-human.md`.

## Verification

- `templates/.github/labels.yml` defines every `sdd:*` lifecycle label and
  every `model:*` tier label named above.
- This fragment references `decisions/0001-needs-human.md`, the ADR that owns
  the `needs-human` contract.
- Each `sdd-*` workflow imports this fragment, so the lifecycle state machine,
  the command vocabulary, and the hand-off contract are stated once.
