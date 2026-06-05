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

A gate the agent cannot execute because of an infrastructure limit (a
firewalled network or a toolchain the agent's container does not carry) is not
a Blocker on that basis alone. When a required status check on the consumer
repository covers the same property, the gate is recorded as deferred to
consumer CI (an Info finding) and the cascade proceeds; `needs-human` is
reserved for a genuine validation failure or a proof that no gate covers. See
the implementation gates for the proof-artifact case.

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
   implementation leakage and is a Warning. **Translation-mode relaxation
   (`plan:provided`).** When the tracking issue carries the `plan:provided`
   marker, the spec is translated from a Claude plan document, whose steps are
   implementation directives, so some leakage is inherent. Under that marker
   this gate is relaxed **only** for a leaked statement that carries an inline
   `(translated from plan: step N)` citation mirroring a specific plan step:
   such a statement is not a finding. A leaked statement **without** that
   citation stays a Warning exactly as above — a translated spec mirrors the
   plan, it does not invent implementation (issue #102). The empty-PR rule on
   proof artifacts (gate 4, a Blocker) is not relaxed under `plan:provided`.
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

Resolve the **task sub-issues** before applying any gate below. The feature
tracking issue is a tree with two levels of sub-issues (ADR 0005, ADR 0007):
the tracking issue's direct sub-issues include a spec sub-issue, an
architecture sub-issue, and one **Unit sub-issue per demoable unit**; each Unit
sub-issue's own sub-issues are the **task sub-issues** that carry the
structured body block (the `## Task` block with `repo:`, `spec:`,
`requirements:`, `files in scope:`, `proof artifacts:`, `verification:`, and
`depends on:` fields — see `.github/workflows/sdd-triage.md` step 6). All four
gates below inspect those task sub-issues, that is, the **grandchildren** of
the feature — Feature → Unit → task — not the Units themselves. A Unit
sub-issue has no structured body block, no `repo:` field, and no `blocked by`
lines; treating a Unit as a task would produce false-positive findings on
every gate in this set. Walk the sub-issue list twice: once from the tracking
issue to enumerate Units, and once from each Unit to enumerate its tasks.

1. **Every spec R-ID covered by a task.** Every requirement ID in the feature's
   spec maps to at least one **task sub-issue** (a grandchild of the feature,
   the child of a Unit). A spec requirement that maps to no task is a Blocker.
   The `requirements:` field of the structured body block lives on tasks, not
   on Units.
2. **Dependency edges are complete and acyclic.** This gate has two parts:
   - **2a. Latent-edge pass completed.** The plan's implied edges — an artifact
     a task's proof consumes that a sibling task produces — were enumerated and
     written as `blocked by` lines, not left latent (see
     `.github/workflows/sdd-triage.md` step 5). A missing latent-edge pass is a
     Warning.
   - **2b. Dependencies form a DAG.** The declared **and** implied `blocked by`
     edges across the **task sub-issues** form a directed acyclic graph. A
     dependency cycle is a Blocker. Read `blocked by` from each task's
     `depends on:` field; Unit sub-issues carry no `depends on:` field and
     contribute no edges. The deterministic `.github/actions/sdd-cycle-detect`
     wrapper job is the **authoritative** DAG gate; this `sdd-validate` gate is
     an LLM advisory restatement (a validation agent cannot `uses:` the action).
3. **Each task single-session sized.** Every **task sub-issue** is scoped to be
   implementable in a single agent session. A task that is too large for one
   session is a Warning. Apply this to tasks, not to Units; a Unit is a
   demoable unit and is expected to span multiple tasks by design.
4. **Every task has a `repo:` field.** Every **task sub-issue**'s structured
   body carries a `repo:` field. A task missing the `repo:` field is a Blocker:
   `sdd-execute` reads that field to decide whether the task is local. Unit
   sub-issues do not carry a structured body and are not inputs to this gate;
   a Unit "missing" `repo:` is by design and not a finding.

## Implementation gates

Applied at the implementation boundary: any pull request change that is not a
spec file and not an architecture or decisions file.

1. **Proof artifacts re-executed and passing.** Each proof artifact named in
   the task is re-run and observed to pass. Distinguish two failure modes
   before assigning a severity:
   - A proof artifact that **fails on re-execution** — the test ran and
     reported a failure, the CLI ran and returned the wrong output or a
     non-zero exit unrelated to the environment, the URL returned the wrong
     response, the browser assertion did not hold, or the file assertion was
     not satisfied — is a genuine validation failure and is a **Blocker**.
   - A proof artifact that **cannot be executed because of an infrastructure
     limit** — the agent runs inside gh-aw's network-restricted firewall with
     no toolchain for the consumer's language and no egress to its package
     registry, so the command fails before exercising the change (a package
     registry 403/CONNECT-tunnel error, "command not found" for an
     uninstalled toolchain, a missing-dependency fetch error) — is **not** a
     Blocker. It is an infrastructure limit, not a code defect, and must not
     trigger `needs-human` on its own. Resolve it as follows:
     - If a **required status check on the consumer repository** runs the same
       command (or a superset that exercises the same proof — e.g. the
       consumer's CI runs `cargo test` / `just verify` covering the named
       test), record the gate as **deferred to consumer CI** and file an
       **Info** finding naming the proof artifact, the infrastructure error
       observed, and the consumer check that covers it. The cascade proceeds;
       the consumer's required check remains the gate.
     - If **no consumer gate covers the proof artifact**, the proof is
       satisfied by no gate — neither agent re-execution nor consumer CI. That
       is a **Blocker**: file the finding and hand off via `needs-human` so a
       human verifies the proof or adds a covering check. Degrading without a
       covering gate would let a PR pass whose declared proof was never
       satisfied, which this gate must never allow.

   Identify a covering check from the check runs and commit statuses reported
   on the pull request head SHA — the signal this agent can read with
   `pull-requests: read` — and corroborate against the base branch's
   `required_status_checks` contexts when that branch-protection read is
   available (it may not be on a least-privilege token; treat it as
   best-effort, not a prerequisite). A covering check is one that is required
   on the base branch (or, when branch protection is unreadable, one whose name
   maps to the proof's command as documented in `CLAUDE.md`) and is reported
   green on the head SHA. Match a check to a proof artifact by the command it
   runs as named in the task and in `CLAUDE.md`. When the match is uncertain,
   apply the 80% confidence floor: below it, treat the proof as uncovered and
   hand off rather than silently deferring.
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
- The proof-artifacts gate distinguishes a genuine re-execution failure
  (Blocker, `needs-human`) from an infrastructure limit that blocks execution.
  An infrastructure limit covered by a consumer required status check is
  recorded as deferred to consumer CI (Info, no hand-off); an infrastructure
  limit covered by no gate is a Blocker.
