# ADR 0005: The sub-issue lifecycle model

- Status: Accepted
- Date: 2026-05-18

## Context

The feature tracking issue is the pipeline's lifecycle anchor: it carries the
`sdd:*` label and must stay open from the spec phase through to a human's
final close (ADR 0001).

Two end-to-end runs showed it does not stay open. `sdd-spec`'s spec pull
request and `sdd-triage`'s architecture pull request both reference the
tracking issue, and the agent wrote a closing keyword for it — `Closes #N` in
the first run, `Fixes #N` in the second — even though ADR 0004's prompt rule
forbids exactly that. Merging the pull request auto-closed the tracking issue
mid-pipeline. A prompt rule has failed twice; the failure mode has to be
removed structurally, not re-worded.

Separately, the phase-B "Unit" parent issues are never closed. `sdd-execute`'s
implementation pull request closes its leaf task sub-issue, but nothing closes
the Unit issue above it. The issue tree is left half-open.

## Decision

1. **A feature is a tree of sub-issues.** The feature tracking issue is the
   root. Its sub-issues are a **spec** sub-issue, an **architecture**
   sub-issue, and one **Unit** sub-issue per demoable unit. Each Unit's
   sub-issues are its implementation **task** sub-issues.

2. **No pull request closes the feature.** No pull request an `sdd-*` agent
   opens names the feature tracking issue with a closing keyword (`Closes`,
   `Fixes`, `Resolves`) — not in its body, not in any commit message. The
   feature is referenced, when at all, as a bare `#N`.

3. **Each deliverable is closed at its own sub-issue.** The leaf task
   sub-issue is closed by its implementation pull request's `Closes #<task>` —
   the one correct closing keyword, because the task pre-exists the pull
   request. The spec and architecture sub-issues are created in the same agent
   run as their pull request, so the pull request cannot carry their number;
   they are closed by an agent step when the pull request merges.

4. **Agents close completed parents.** `sdd-spec` closes the spec sub-issue
   when the spec pull request merges. `sdd-triage` closes the architecture
   sub-issue when the architecture pull request merges. `sdd-execute` closes a
   Unit sub-issue once every task sub-issue under it is closed, and moves the
   feature to `sdd:done` — handing the final close to a human (ADR 0001) — once
   the spec, the architecture, and every Unit sub-issue is closed.

5. **Closing uses the `update-issue` safe-output.** Each agent that closes a
   sub-issue declares `update-issue` with `status` enabled. No agent ever
   closes the feature tracking issue itself.

## Reasoning

- A slipped closing keyword is now harmless: every pull request's closing
  keyword targets a sub-issue that *should* close when that pull request
  merges. The feature is never a closing target, so it cannot be auto-closed.
  This is the structural fix the twice-failed prompt rule could not be.
- The tree gives the feature a complete, inspectable progress view: GitHub
  renders the spec, architecture, Unit, and task sub-issues under it.
- The Unit issues now close, so a finished feature's tree is fully closed
  except the root, which a human reviews and closes.
- The spec and architecture sub-issues are closed by an agent step rather than
  a pull-request keyword because the agent creates the sub-issue and the pull
  request in one run and cannot know the sub-issue number when it writes the
  pull-request body. Closing them on merge, with `update-issue`, is uniform
  with how Unit issues close.

## Verification

- A spec pull request and an architecture pull request carry no closing
  keyword for the feature tracking issue; the feature stays open across both
  merges.
- After a feature's spec pull request merges, a spec sub-issue exists under it
  and is closed.
- After every task sub-issue of a Unit is closed, the Unit sub-issue is
  closed; after every Unit, the spec, and the architecture sub-issue is
  closed, the feature carries `sdd:done` and `needs-human` and is not closed
  by an agent.

## Consequences

- `sdd-spec` gains the `create-issue`, `link-sub-issue`, and `update-issue`
  safe-outputs. `sdd-triage` gains `update-issue`. `sdd-execute` gains
  `update-issue`. Each `update-issue` enables `status` only.
- ADR 0004's correction — reference the tracking issue with `Refs #N`, never a
  closing keyword — stands and is reinforced here: the rule now also has a
  structural backstop.
- `sdd-triage` phase C links each task sub-issue under its Unit, not directly
  under the feature, so the tree nests Feature → Unit → task.
