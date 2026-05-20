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
Fast path: sdd:spec -> sdd:fastpath -> sdd:fastpath-review -> sdd:fastpath -> sdd:in-progress -> sdd:done
```

| Label | Meaning | Set by | Advances on |
|---|---|---|---|
| `sdd:spec` | the feature is being specified | `feature`/`bug` template, or `/spec` | spec PR merged, or `/fastpath` confirms fast-path |
| `sdd:fastpath` | fast-path is armed; awaiting stub spec merge or `/approve` | `sdd-spec` on `/fastpath` (full path), or stub spec PR merge | stub spec PR opened (`sdd:fastpath-review`), or `/approve` on a merged-stub state |
| `sdd:fastpath-review` | fast-path stub spec PR is open and awaiting human merge | `sdd-spec` on the stub spec PR | stub spec PR merged (returns to `sdd:fastpath`) |
| `sdd:triage` | architecture and triage are running | `sdd-spec` on spec-PR merge | architecture PR merged (plan-comment posted), then `/approve` |
| `sdd:ready` | tasks are decomposed and queued | `sdd-triage` on phase C completion | `/dispatch` arms the cascade |
| `sdd:in-progress` | the cascade is armed and tasks are being implemented (full path), or the single fast-path implementation is running | `sdd-dispatch` on the first `/dispatch` (full path), or `sdd-spec` on `/approve` (fast path) | every task sub-issue closes (full path), or the implementation PR merges (fast path) |
| `sdd:review` | the implementation awaits human review | `sdd-validate` on a clean implementation pass | all task sub-issues closed |
| `sdd:done` | every task is complete | `sdd-execute` when all tasks are closed (full path), or `sdd-execute` on the fast-path implementation PR merge | a human does the final close |

Exactly one lifecycle label is present at a time. `sdd:triage` covers all
three `sdd-triage` phases (architecture, plan comment, tree
materialization). `sdd:fastpath` and `sdd:fastpath-review` cover the
fast-path flow from ADR 0012; a fast-path tracking issue never carries
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

## Comment-command vocabulary

A small command vocabulary steers the pipeline. Every command is gated, via
the gh-aw `command:` trigger, to comment authors with write access to the
repository. A command from a non-write user is a no-op.

| Command | Where | Effect |
|---|---|---|
| `/spec` | tracking issue | trigger `sdd-spec` (also auto-applied by the `feature`/`bug` template label); on a fast-path tracking issue it is the misclassification-escalation reset that returns the lifecycle to `sdd:spec` |
| `/fastpath` | tracking issue, after `sdd-spec`'s proposal comment or up front before any agent run | confirm fast-path classification; `sdd-spec` produces a stub spec PR and an execution plan comment in one run (ADR 0012) |
| `/triage` | tracking issue, after the spec PR is merged | trigger `sdd-triage` phase A (architecture) |
| `/approve` | tracking issue | on a full-path tracking issue (`sdd:triage` with a plan-comment posted), materialize the Unit and task sub-issue tree per ADR 0010; on a fast-path tracking issue (`sdd:fastpath` with the stub spec merged), dispatch one `sdd-execute-{tier}` against the execution plan comment per ADR 0012 |
| `/dispatch` | tracking issue, in `sdd:ready` or `sdd:in-progress` (full path) | arm cascade execution of every task in the feature's task tree; on a fast-path tracking issue (`sdd:fastpath`, `sdd:fastpath-review`, or a fast-path `sdd:in-progress`), `/dispatch` is a noop with a one-comment explanation pointing to `/approve` (ADR 0012) |
| `/revise <note>` | spec PR, architecture PR, tracking issue, or implementation PR | re-run the owning agent with the note as an added instruction |
| `/execute` | a task sub-issue | trigger `sdd-execute` for that task immediately, outside the cascade |

Merging the spec PR advances to the architecture phase; merging the
architecture PR advances to a plan-comment phase. `/approve` is the one
non-PR decision point at which structure is committed to the tree (ADR
0010). `/dispatch` is the second non-PR decision point on the full
path: it arms the event-driven cascade that runs the tasks. Execution
is fully event-driven: `/approve` → `/dispatch` → cascade-on-close (ADR
0011).

The fast-path flow (ADR 0012) compresses the same gates for
single-session work. `sdd-spec` proposes fast-path or honours an
explicit `/fastpath`; on confirmation it produces a stub spec PR and
posts the execution plan as one comment on the tracking issue. The
human merges the stub spec PR (the spec sub-issue closes via the
existing `Closes` keyword) and comments `/approve` to dispatch one
`sdd-execute-{tier}` against the plan comment. `/dispatch` is unused
on this flow and is a noop with a comment pointing at `/approve`.

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
