# Latent-edge pass

> This fragment is the canonical home of the latent-edge-pass contract. It is
> currently **inlined** into `.github/workflows/sdd-triage.md` step 5 rather than
> imported: a new shared fragment cannot be imported from `@main` in the same
> pull request that introduces it, because `gh aw compile` resolves `@main`
> against remote `main`, where the file does not yet exist. Following the
> inline-then-import pattern (PR #179, commit c68117f), the contract ships inline
> in the agent source plus this canonical copy; a follow-up adds the
> `imports:` line once this file is on `@main`.

The latent-edge pass runs while `sdd-triage` composes the phase B plan preview,
before the cycle check, so the implied edges are visible to the human in the
plan comment and phase C materializes them unchanged (ADR 0010: phase C
materializes exactly the plan comment).

A declared `depends on:` edge is not the only dependency a plan implies. A task
whose proof artifacts consume an artifact another task produces depends on that
producer even when the author wrote no `blocked by` line — a latent edge.

For each previewed sub-task, enumerate every artifact its proof artifacts
**consume** that the task does not itself produce (a stub, a fixture, a
generated binary or schema, and the like). Classify each consumed artifact:

- It exists in the repository working tree (confirm with Serena, per the
  imported Serena fragment) → **no edge**.
- Exactly **one** other planned task produces it, at **80% confidence or
  higher** → add an implied dependency: write a literal `blocked by` line into
  **that consuming task's** `depends on:` preview, referencing the producer task
  by the same preview identity the plan uses for its other depends-on edges. It
  must read as a real depends-on line, not a parenthetical annotation. Phase C
  materializes it verbatim into the task body's `blocked by #<n>` line.
- No producer found **and** absent from the repository → a **dangling-input
  note**, filed Info, or Warning when the artifact is clearly required. Keep it
  **distinct** from the requirement-coverage finding; the two are different
  failures.
- Ambiguous, or below the 80% confidence floor → **no edge**, plus a
  **knowledge-gap note**. Never fabricate an edge, or a cycle, on uncertainty.

The implied edges this pass adds participate in the same DAG check as the
declared `blocked by` edges. The deterministic `.github/actions/sdd-cycle-detect`
wrapper job is the authoritative DAG gate over the materialized tree; this
in-prompt pass is what makes the latent edges exist for that gate to check.
