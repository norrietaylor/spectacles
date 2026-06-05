# Assumption ledger

> This fragment is the canonical home of the assumption-ledger contract. It is
> currently **inlined** into `.github/workflows/sdd-triage.md` step 2 rather than
> imported: a new shared fragment cannot be imported from `@main` in the same
> pull request that introduces it, because `gh aw compile` resolves `@main`
> against remote `main`, where the file does not yet exist. Following the
> inline-then-import pattern (PR #179, commit c68117f), the contract ships inline
> in the agent source plus this canonical copy; a follow-up adds the
> `imports:` line once this file is on `@main`.

The assumption ledger promotes the knowledge-gap pass output (the imported
Distillery fragment: seed search → relation traverse → `exclude_linked` similar)
into a structured record of the load-bearing assumptions the chosen approach
rests on. It runs while `sdd-triage` designs the Phase A architecture, layered on
top of the knowledge-gap pass's step-4 outputs.

The ledger is a `## Assumption ledger` subsection **within** the
`architecture.md` record — not a new file. It is built from the knowledge-gap
pass output and sits alongside the `Knowledge gaps` subsection it derives from.

## What goes in the ledger

One row per **load-bearing** assumption. An assumption is anything the chosen
approach takes as given but does not itself establish — a behavior of an
existing component, the shape of an interface, a property of the data, a
guarantee a dependency makes. Each row carries:

- a **stable slug row-key** — kebab-case, derived from the assumption statement,
  so the same assumption keeps the same key across re-runs (`/revise`);
- a one-line **statement** of the assumption;
- the **bucket** — `needs-spike` or `settled`;
- the **evidence / citation** that places it in its bucket, scoped and cited the
  same way the knowledge-gap pass cites (`(informed by #N)`,
  `(informed by ADR-0001)`, or a Serena file/symbol reference);
- a **depends-on** field that binds the assumption only to architecture
  decisions or spec requirement IDs — never to tasks (tasks do not exist yet at
  Phase A, and an assumption is a property of the design, not of an execution
  step).

## Per-row gate chain (applied in order)

For each candidate surfaced by the knowledge-gap pass, apply the gates in order;
the first gate that disqualifies the candidate stops the chain.

1. **Load-bearing gate.** Is this assumption load-bearing for the *chosen*
   approach — would the approach change if the assumption were false? A
   non-load-bearing assumption is **not** ledgered at all; drop it here.
2. **Settled gate.** Is the assumption already settled by a prior decision or
   precedent? This is the `supersedes` / `corrects` traversal from the
   knowledge-gap pass: a decision record or merged work that establishes the
   assumption settles it. A settled assumption is ledgered in the `settled`
   bucket with its citation.
3. **Repo-state gate.** Is the assumption settleable from the repository working
   tree — confirmable at the Serena symbol-level baseline (the symbol, file, or
   interface is in-tree and wired in, not a stub)? A repo-settleable assumption
   is ledgered in the `settled` bucket with its file/symbol evidence.
4. **needs-spike residue.** An assumption that is load-bearing **and** not
   settleable from repo state **nor** settled by precedent is the residue: it
   gets the `needs-spike` marker and is ledgered in the `needs-spike` bucket.

## Trigger

The **trigger for a spike** is exactly: load-bearing **and** not settleable from
repo state, nor settled by precedent. That residue is the `needs-spike` bucket;
everything else that is ledgered is `settled`. The two buckets are the whole
partition of the ledger — `needs-spike` versus `settled`.

`needs-spike` is a **ledger marker**, not a GitHub label. It lives in the
architecture record's prose; it is not applied to any issue and is not in the
label catalog.

## Relationship to the baseline pass

The ledger pass is **strictly additive** to the existing step-5
baseline-against-repo pass. It reads the same Serena symbol-level baseline and
the same Distillery retrieval, and it informs the baseline — but it never
removes or overrides a baseline finding. A requirement the baseline marks
already-satisfied stays so; the ledger only adds the assumption rows the
chosen approach depends on.

## both-tools-down ceiling

The gate chain needs both retrieval layers: Serena for the repo-state gate,
Distillery for the settled gate and the knowledge-gap seeds. If a single layer
is unreachable, degrade per its outage rule (prefer the conservative bucket).
If **both** Serena and Distillery are unreachable, the agent cannot run the
gates and must not guess buckets: hand off via the `needs-human` contract rather
than ledgering on a coin-flip.

## plan:provided mode

The ledger pass **still runs** under the `plan:provided` marker. A translated
plan is not exempt: its assumptions are load-bearing for the architecture exactly
as a from-scratch design's are, and grounding them against repo state and prior
decisions is what keeps the translation honest. Run the gate chain over the
plan's assumptions the same way.
