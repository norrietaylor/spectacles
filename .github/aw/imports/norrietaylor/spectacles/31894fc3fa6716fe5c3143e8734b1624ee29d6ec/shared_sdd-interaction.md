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
sdd:spec -> sdd:triage -> sdd:ready -> sdd:in-progress -> sdd:review -> sdd:done
```

| Label | Meaning | Set by | Advances on |
|---|---|---|---|
| `sdd:spec` | the feature is being specified | `feature`/`bug` template, or `/spec` | spec PR merged |
| `sdd:triage` | architecture and triage are running | `sdd-spec` on spec-PR merge | architecture PR merged, then `/approve` |
| `sdd:ready` | tasks are decomposed and queued | `sdd-triage` on phase C completion | a task is picked up |
| `sdd:in-progress` | a task is being implemented | `sdd-execute` on task selection | validation passes |
| `sdd:review` | the implementation awaits human review | `sdd-validate` on a clean implementation pass | all task sub-issues closed |
| `sdd:done` | every task is complete | `sdd-execute` when all tasks are closed | a human does the final close |

Exactly one lifecycle label is present at a time. `sdd:triage` covers all
three `sdd-triage` phases (architecture, parent tasks, sub-tasks). The
`kind:*`, `priority:*`, and `model:{haiku,sonnet,opus}` labels are orthogonal
metadata and are not part of this state machine.

## Comment-command vocabulary

A small command vocabulary steers the pipeline. Every command is gated, via
the gh-aw `command:` trigger, to comment authors with write access to the
repository. A command from a non-write user is a no-op.

| Command | Where | Effect |
|---|---|---|
| `/spec` | tracking issue | trigger `sdd-spec` (also auto-applied by the `feature`/`bug` template label) |
| `/triage` | tracking issue, after the spec PR is merged | trigger `sdd-triage` phase A (architecture) |
| `/approve` | tracking issue | confirm the parent-task list; `sdd-triage` proceeds to sub-tasks |
| `/revise <note>` | spec PR, architecture PR, triage comment, or implementation PR | re-run the owning agent with the note as an added instruction |
| `/execute` | a task sub-issue | trigger `sdd-execute` for that task ahead of the cron |

Merging the spec PR advances to the architecture phase; merging the
architecture PR advances to the parent-task phase. `/approve` is the one
non-PR decision point: it confirms the parent-task list before sub-task
decomposition.

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
