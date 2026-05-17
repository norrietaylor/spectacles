# Validation gates

The `sdd-validate` agent imports this fragment so the per-boundary gate sets
are defined once and never restated in the workflow prompt. A gate is a single
checkable property of an artifact. Each phase boundary has its own gate set;
the agent resolves the boundary first (see `.github/workflows/sdd-validate.md`)
and then applies only that boundary's gates.

Validation is advisory by design. A gate that fails produces a finding, never
a failed required status check. Every finding carries a severity (Blocker,
Warning, Info) and `file:line` evidence per the imported evidence-rigor
standard. A Blocker finding triggers the `needs-human` hand-off; it never fails
the workflow.

## Severity

- **Blocker.** The artifact has a defect that a human must resolve before the
  phase can safely advance. A Blocker finding triggers `needs-human` on the
  pull request or the tracking issue.
- **Warning.** The artifact has a weakness worth addressing but the phase can
  proceed. No hand-off.
- **Info.** An observation for the author's awareness. No hand-off.

A gate maps to a severity by how load-bearing the failure is: a gate that
guards a correctness property of the phase is a Blocker when it fails; a gate
that guards a quality property is a Warning. Apply the 80% confidence floor
from the evidence-rigor standard before filing any finding.

## Spec gates

Applied at the spec boundary: a pull request that adds or changes a
`*-spec-*.md` file under `docs/specs/`.

1. **Acceptance criteria testable.** Every acceptance criterion is a testable
   statement, observable as pass or fail, not a vague aspiration. A criterion
   that cannot be checked is a Blocker.
2. **No implementation leakage.** The spec states what the feature does and why,
   not how it is coded. A criterion that prescribes a function, a class, a data
   structure, or a file name where a behavioral statement belongs is
   implementation leakage and is a Warning.
3. **Assumptions explicit.** Every assumption the spec rests on is stated
   plainly. An unstated assumption that a reader must infer is a Warning.
4. **Proof artifacts present and behavioral.** Every demoable unit carries one
   to three proof artifacts, each of one of the five types, and each passes the
   empty-PR rule from the imported proof-artifacts fragment. A demoable unit
   with no proof artifact, or a proof artifact that would pass against an empty
   pull request, is a Blocker.

## Architecture gates

Applied at the architecture boundary: a pull request that adds or changes an
`architecture.md` file under `docs/specs/`, or any file under `decisions/`.

1. **Decision and rationale present.** The record states the chosen approach
   and the reasoning behind it. A record that names an approach with no
   rationale is a Blocker.
2. **Alternatives considered.** The record lists the alternatives that were
   weighed and why each was not chosen. A decision presented with no
   alternatives is a Warning; a feature with no significant decision is the
   documented short "no significant architecture decision" note and is not
   itself a finding.
3. **Consistent with existing decisions.** The record does not contradict an
   accepted record under `decisions/`. A decision that reverses or conflicts
   with an accepted ADR without saying so is a Blocker.
4. **No implementation detail masquerading as a decision.** The record captures
   a cross-cutting choice, not a line-level coding detail. An entry that is a
   coding preference dressed as an architecture decision is a Warning.

## Triage gates

Applied at the triage boundary: an `sdd:ready` label event on a tracking issue.
The task graph is a set of linked sub-issues, not a pull request, so this
boundary validates the sub-issues of the tracking issue.

1. **Every spec R-ID covered by a task.** Every requirement ID in the feature's
   spec maps to at least one task sub-issue. A spec requirement that maps to no
   task is a Blocker.
2. **Dependencies form a DAG.** The `blocked by` lines across the task
   sub-issues form a directed acyclic graph. A dependency cycle is a Blocker.
3. **Each task single-session sized.** Every task is scoped to be implementable
   in a single agent session. A task that is too large for one session is a
   Warning.
4. **Every task has a `repo:` field.** Every task sub-issue's structured body
   carries a `repo:` field. A task missing the `repo:` field is a Blocker:
   `sdd-execute` reads that field to decide whether the task is local.

## Implementation gates

Applied at the implementation boundary: any pull request change that is not a
spec file and not an architecture or decisions file.

1. **Proof artifacts re-executed and passing.** Each proof artifact named in
   the task is re-run and observed to pass. A proof artifact that fails on
   re-execution, or that cannot be re-executed, is a Blocker.
2. **Changed files within task scope.** Every file the pull request changes is
   within the files-in-scope block of the task it closes. A change outside that
   scope is a Warning; a change to a protected path (`.github/`, `decisions/`,
   `templates/.github/`, secrets) is a Blocker.
3. **No real credentials in the diff.** The diff introduces no real secret,
   token, key, or other credential. A credential in the diff is a Blocker.

## Verification

- This fragment names all four gate sets: spec gates, architecture gates,
  triage gates, and implementation gates.
- `.github/workflows/sdd-validate.md` imports this fragment and resolves the
  boundary before applying a gate set.
- Each gate set names the artifact it applies to and the boundary that selects
  it.
