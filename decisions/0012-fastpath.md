# ADR 0012: Fast-path for single-session features and bugs

- Status: Accepted (amended by ADR 0023, which widens the classifier,
  scales the stub to a light spec, and makes `/approve` commutative
  with the spec-PR merge via the `sdd:approved` marker)
- Date: 2026-05-20

## Context

Every feature and bug pays the full spec → architecture → plan → approve
cost of the SDD pipeline, even when the work is a one-file copy change, a
single-symbol bugfix, or a label-colour update. The reviewable artifacts
the pipeline produces — spec PR, architecture PR, plan comment, task tree
— are load-bearing for a real feature and ceremonial for a trivial one.
The friction has a measurable cost: trivial changes get pushed outside
the pipeline as raw PRs against `main`, and the system loses its trace of
exactly the work it most wants traced.

The cheapest way to keep that trace is to compress spec, architecture,
and plan into one agent run, gated by a single `/approve`, while still
producing enough of a written artifact that `sdd-validate` and
`sdd-review` continue to function on the result.

This ADR layers on top of ADR 0010 (plan comment before tree) and
ADR 0011 (event-driven cascade dispatch). 0010 made `/approve` the single
non-PR decision point at which structure is materialized; 0012 reuses
that gate for fast-path issues, where "materialize" means "dispatch one
`sdd-execute-{tier}` against the execution plan comment" instead of
"create the Unit and task tree." 0011 left `/dispatch` as the cascade
trigger for the full path; on a fast-path issue there is one task and
the fan-out machinery is unused, so `/dispatch` is a noop with a
one-comment explanation.

## Decision

1. **`sdd-spec` classifies tracking issues on intake and proposes
   fast-path.** Heuristics live in the agent prompt: file scope estimate
   ≤ 1–2 files, no new dependency, no schema change, no new public API
   surface, no cross-cutting concern, no test-suite scaffolding required.
   When every heuristic passes, the agent posts **one proposal comment**
   on the tracking issue — "this looks fast-path; comment `/fastpath` to
   confirm, or `/spec` to keep the full flow" — and stops. The lifecycle
   stays at `sdd:spec`. The proposal does not block the full path; the
   default action is the full flow, and silence is not consent.

2. **`/fastpath` from a write-access author is the human confirmation.**
   On `/fastpath`, the wrapper moves the tracking issue's lifecycle label
   from `sdd:spec` to `sdd:fastpath` and re-invokes `sdd-spec`. The agent
   then produces, in one run, a **stub spec PR** and an **execution plan
   comment** on the tracking issue. The lifecycle moves to
   `sdd:fastpath-review` while the stub spec PR is open.

   A human who knows up front that the work is small may apply
   `sdd:fastpath` directly on issue creation (the `feature` and `bug`
   templates prompt for `/fastpath` in their body) or comment `/fastpath`
   on the tracking issue immediately; the agent honours either path and
   skips the proposal step.

3. **The stub spec preserves the trace.** The stub spec PR commits a
   `docs/specs/NN-spec-<slug>/NN-spec-<slug>.md` file with the structural
   minimum `sdd-validate` and `sdd-review` need: a one-paragraph problem
   statement and motivation, requirement IDs (`R1.1`, `R1.2`, …, at least
   one), 1 to 3 proof artifacts, and one named demoable unit. The stub
   carries a single-line "Fast-path: no cross-cutting design; the
   implementation plan is in the tracking issue comment" note where the
   architecture cross-link would normally sit. No architecture record is
   produced.

4. **The execution plan is a comment, not a sub-issue tree.** The plan
   body has the same shape as a full-path sub-task block (file scope,
   proof artifacts, `depends on:` typically empty, `model:*` tier) and
   lives only as a comment on the tracking issue carrying the
   `[sdd-spec:fastpath-plan]` sentinel. There is exactly one task;
   the Feature → Unit → task tree from ADR 0005 is collapsed to "tracking
   issue → one execution plan."

5. **`/approve` is the shared gate.** Merging the stub spec PR closes
   the spec sub-issue via the existing `sdd-pr-sanitize` `Closes` keyword
   (ADR 0005, ADR 0006) and the lifecycle returns to `sdd:fastpath`,
   awaiting `/approve`. `/approve` on a `sdd:fastpath` tracking issue
   dispatches `sdd-execute-{tier}` against the execution plan comment
   (the wrapper reads the `model:*` tier from the plan comment, mints an
   App token, and calls `workflow_dispatch` on the matching variant). The
   tracking issue moves to `sdd:in-progress`. **No Unit sub-issues are
   created, no task sub-issues are created.**

6. **`/dispatch` is a noop on fast-path.** The cascade fan-out from
   ADR 0011 is unused on a one-task issue. `/dispatch` on a
   `sdd:fastpath`, `sdd:fastpath-review`, or `sdd:in-progress` tracking
   issue carrying any fast-path history posts a one-comment explanation
   pointing the human at `/approve` and emits `noop`. The
   `sdd:dispatched` cascade marker is never applied on the fast-path
   flow.

7. **`/revise <note>` between the plan comment and `/approve` edits the
   plan in place.** Same mechanics as ADR 0010 phase B: the agent
   re-runs, posts a new plan comment carrying the same sentinel, and
   hides the prior plan comment as `OUTDATED`. No new sub-issues exist
   to reconcile.

8. **Misclassification escalates via `needs-human`.** If during
   execution the implementer determines the work is materially bigger
   than fast-path assumed (more than one PR, requires schema changes,
   requires architecture decisions, file scope explodes), it posts one
   comment naming the specific mismatch ("file scope grew from 2 to 11;
   spans the auth boundary; requires a new dependency"), applies
   `needs-human`, and stops. The implementation PR (if open) is left
   in place for the human to inspect or close. The human's recourse is
   the existing `needs-human` contract (ADR 0001):
   - Comment `/spec` to bounce the issue into the full pipeline. The
     wrapper re-applies `sdd:spec`, the stub spec becomes the starting
     point of a fuller spec, and the lifecycle resets to `sdd:spec`.
   - Or tighten the fast-path scope explicitly in the answer ("just
     rename the function, drop the rest") and the executor resumes via
     the standard `needs-human` removal trigger.

   An automatic-downgrade path is explicitly **not** chosen. The
   mismatch is a real decision and should reach a human, not be papered
   over.

9. **Lifecycle state machine.** Fast-path adds two lifecycle states to
   the machine from `shared/sdd-interaction.md`. Exactly one lifecycle
   label remains present at a time.

   ```text
   sdd:spec → sdd:fastpath              (on /fastpath)
   sdd:fastpath → sdd:fastpath-review   (stub spec PR opened)
   sdd:fastpath-review → sdd:fastpath   (stub spec PR merged)
   sdd:fastpath → sdd:in-progress       (on /approve; dispatch execute)
   sdd:in-progress → sdd:done           (implementation PR merged)
   sdd:fastpath → sdd:spec              (on /spec from misclassification escalation)
   ```

   `sdd:dispatched` does not appear on the fast-path flow.

## Reasoning

- **Agent proposes, human confirms.** A purely-automatic fast-path
  decision is a quiet correctness risk: the heuristics are heuristics,
  and a wrong call lands a one-comment plan where a real spec was
  needed. A purely-human decision wastes the agent's read of the issue
  body. The proposal-confirm split puts the read in front of a human
  who is in the loop anyway, with the full flow as the default if no
  confirmation arrives. This mirrors the `/approve` semantics of
  ADR 0010: the agent does the work, the human commits the structure.

- **The stub spec is the minimum that keeps `sdd-validate` and
  `sdd-review` honest.** Both agents key off R-IDs (`sdd-review`
  resolves the task's R-IDs from the spec; `sdd-validate`'s
  triage-boundary check walks the tree). A fast-path issue has no
  tree, so the triage-boundary check has nothing to walk; the
  implementation-boundary check still applies and still needs the
  R-IDs in a spec file. Dropping the spec entirely would force a
  parallel "fast-path validator" or a special-case in the existing
  validator. A two-page spec stub is cheaper to write than that
  parallel surface area.

- **`/approve` as the shared gate.** Reusing `/approve` for both flows
  keeps the human's vocabulary stable: one command name, one moment of
  commitment per tracking issue. The difference is what `/approve`
  materializes: a tree for the full path, a single `workflow_dispatch`
  for the fast path. The lifecycle label tells the wrapper which.

- **`/dispatch` noop, not `/dispatch` removal.** Removing `/dispatch`
  from the vocabulary on fast-path issues would force the human to
  notice the lifecycle label before commenting, which is the wrong
  direction for a "small change, less ceremony" path. A one-comment
  noop pointing at `/approve` is the cheapest possible correction.

- **Escalation through `needs-human`, not auto-downgrade.** An
  auto-downgrade would silently tear up the fast-path artifact and
  re-run the full pipeline, possibly while the implementer's branch
  is open. The mismatch is a decision: keep the fast-path scope by
  tightening the work, or accept the full path. Both branches need
  human input; `needs-human` is the existing primitive for that.

- **Two states, not three.** A "medium-path" tier (one PR with a small
  Unit tree, say) was explicitly rejected. Keeping the decision binary
  — fast or full — keeps the classifier simple and the human's mental
  model simple. A third tier is a future change with its own ADR.

- **Cross-repo task routing is out of scope.** The `repo:` seam from
  R5.6 is exercised only on the full path; fast-path defaults to the
  tracking issue's own repo. A cross-repo fast-path is a follow-up.

- **Issue-template label limitation.** GitHub Markdown issue templates
  do not support conditional labels: a checkbox in the template body
  cannot toggle the `labels:` frontmatter. The pragmatic resolution is
  to prompt the user "Comment `/fastpath` if this is a one-session
  change" in the template body and let `sdd-spec` do the rest. The
  user who knows up front the work is small types one comment; the
  agent honours it on the next run. This trades a one-line manual step
  for not having to introduce a YAML-template variant.

## Cross-links

- **ADR 0001** — `needs-human` hand-off. Fast-path's misclassification
  escalation is exactly this contract.
- **ADR 0005** — Feature → Unit → task sub-issue tree. Fast-path
  collapses this to "tracking issue → one execution plan" and
  documents the collapse explicitly.
- **ADR 0010** — plan-comment before tree. Fast-path is the
  one-comment variant of phase B: a plan in a comment, gated by
  `/approve`, materialized as a single dispatch instead of as a
  sub-issue tree.
- **ADR 0011** — event-driven cascade dispatch. Fast-path does not
  enter the cascade; `/dispatch` is a noop with a comment.

## Verification

- An issue body whose work plausibly fits a single session gets,
  within one `sdd-spec` run, one proposal comment on the tracking
  issue and no spec PR. The lifecycle stays at `sdd:spec`.
- A `/fastpath` from a write-access author then produces, within one
  `sdd-spec` run, one stub spec PR (structurally complete: problem,
  requirement IDs, proof artifacts, one Unit) and one execution plan
  comment carrying the `[sdd-spec:fastpath-plan]` sentinel on
  the tracking issue. The lifecycle moves to `sdd:fastpath-review`.
- Merging the stub spec PR closes the spec sub-issue (via the
  `Closes #<spec-sub-issue>` keyword `sdd-pr-sanitize` added) and
  moves the lifecycle from `sdd:fastpath-review` to `sdd:fastpath`.
- `/approve` on a `sdd:fastpath` tracking issue dispatches one
  `sdd-execute-{tier}` matched to the plan comment's `model:*` tier
  with `entry: "fastpath"` in `aw_context`, and moves the lifecycle
  to `sdd:in-progress`. No `create-issue` safe-output is emitted; no
  Unit or task sub-issues are created.
- The implementation PR opens. On merge, the tracking issue moves
  from `sdd:in-progress` to `sdd:done` directly (no remaining-tasks
  check, since there is one task).
- `/revise <note>` between the plan comment and `/approve` posts a
  new plan comment and hides the prior plan comment as `OUTDATED`.
  No new sub-issues are created.
- An issue body that fails any of the six classifier heuristics
  produces no fast-path proposal; the full path runs as today.
- A misclassification escalation during execution posts one comment
  naming the specific failed heuristic(s), applies `needs-human`,
  leaves the implementation PR in place, and exits. A subsequent
  `/spec` from the human resets the lifecycle to `sdd:spec` and runs
  the full pipeline with the stub spec as the starting point.
- `/dispatch` on a fast-path tracking issue produces one noop
  comment pointing at `/approve` and dispatches no
  `sdd-execute-{tier}` runs. `sdd:dispatched` is not applied.
- `sdd-validate` and `sdd-review` run cleanly against a fast-path
  issue: the absence of an architecture record and a sub-task tree
  is not raised as a finding when `sdd:fastpath` or
  `sdd:fastpath-review` is present.

## Consequences

- Two new lifecycle labels join `templates/.github/labels.yml`:
  `sdd:fastpath` and `sdd:fastpath-review`. Both are exclusive with
  the existing `sdd:*` lifecycle labels.
- The lifecycle state machine in `shared/sdd-interaction.md` grows
  two states and one re-entry edge (`sdd:fastpath → sdd:spec` on
  misclassification escalation).
- `sdd-spec` gains a classifier branch and two new operating modes:
  proposal-only on intake, and stub-spec + plan-comment on
  `/fastpath`.
- The three `sdd-execute-{tier}` agents gain one new entry path: a
  `workflow_dispatch` carrying `aw_context.entry: "fastpath"` reads
  the task spec from the named execution plan comment on the
  tracking issue instead of a task sub-issue body, and on the
  implementation PR's merge moves the tracking issue directly to
  `sdd:done`.
- `sdd-dispatch`'s wrapper gains a precondition branch: a fast-path
  tracking issue (carrying `sdd:fastpath`, `sdd:fastpath-review`, or
  a lifecycle label set on a tracking issue whose history shows a
  fast-path arming) is a noop with a one-comment explanation.
- `sdd-validate` and `sdd-review` gain a fast-path-awareness rule:
  the absence of an architecture record and a sub-task tree is not a
  finding when the tracking issue carries `sdd:fastpath` or its
  successor states.
- The `feature` and `bug` issue templates gain a prompt asking the
  reporter to comment `/fastpath` for a one-session change. The
  prompt is text-only; no conditional label is applied at template
  time because GitHub Markdown templates do not support conditional
  labels.
- The pipeline chain becomes two parallel sequences sharing one gate:

  ```text
  Full path:  /spec → /triage → /approve → /dispatch → cascade → /merge → /close
  Fast path:  /spec → /fastpath → merge-stub → /approve → dispatch-one → /merge → /close
  ```

  Three explicit human commands on the full path; two (`/fastpath`,
  `/approve`) plus the same merge-and-close sequence on the fast path.
