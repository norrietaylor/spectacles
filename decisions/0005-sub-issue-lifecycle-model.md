# ADR 0005: The sub-issue lifecycle model

- Status: Accepted
- Date: 2026-05-18
- Amended: 2026-05-19 — the spec and architecture sub-issues now close via a
  `Closes` keyword added to their pull request by `sdd-pr-sanitize`, not via an
  `update-issue` step in `sdd-spec` / `sdd-triage` (issue #58).

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

3. **Each deliverable sub-issue is closed by its pull request.** The spec,
   architecture, and task sub-issues each close on the merge of the pull
   request that delivers them, through a `Closes #<sub-issue>` keyword in that
   pull request's body. A task sub-issue pre-exists its implementation pull
   request, so `sdd-execute` writes `Closes #<task>` directly. A spec or
   architecture sub-issue is created in the *same* agent run as its pull
   request, so the agent cannot write the sub-issue number into the body;
   `sdd-pr-sanitize` adds `Closes #<sub-issue>` after both exist (ADR 0006).

4. **An agent closes the Unit parents.** A Unit sub-issue has no pull request
   of its own, so it cannot close on a merge. `sdd-execute` closes a Unit
   sub-issue once every task sub-issue under it is closed, and moves the
   feature to `sdd:done` — handing the final close to a human (ADR 0001) — once
   the spec, the architecture, and every Unit sub-issue is closed.

5. **Only the Unit close uses the `update-issue` safe-output.** The spec,
   architecture, and task sub-issues close through their pull request's
   `Closes` keyword and need no safe-output. `sdd-execute` declares
   `update-issue` with `status` enabled for the Unit close. No agent ever
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
- The spec and architecture sub-issues close on a pull-request keyword like
  the task sub-issue, even though the agent cannot write that keyword itself:
  `sdd-pr-sanitize` runs after the sub-issue and the pull request both exist,
  resolves the sub-issue, and adds it. Closing all three deliverable sub-issue
  kinds the same way — on the merge of their own pull request — is more uniform
  than a separate per-agent `update-issue` step, and it removes that step from
  `sdd-spec` and `sdd-triage` entirely.

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

- `sdd-spec` gains the `create-issue` safe-output. `sdd-execute` declares
  `update-issue` (`status` only) for the Unit close; `sdd-spec` and
  `sdd-triage` declare no `update-issue` — their deliverable sub-issues close
  on their pull request's `Closes` keyword. Sub-issues were originally nested
  with a separate `link-sub-issue` safe-output; ADR 0007 replaces that with the
  `create-issue` `parent` field.
- ADR 0004's correction — reference the tracking issue with `Refs #N`, never a
  closing keyword — stands and is reinforced here: the rule now also has a
  structural backstop.
- `sdd-triage` phase C links each task sub-issue under its Unit, not directly
  under the feature, so the tree nests Feature → Unit → task.
