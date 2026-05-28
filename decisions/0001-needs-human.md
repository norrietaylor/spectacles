# ADR 0001: The `needs-human` hand-off label

- Status: Accepted
- Date: 2026-05-16

## Context

The spectacles agents run unattended in GitHub Actions. They have no
interactive prompt: an agent cannot stop and ask a question the way a desktop
tool can. Some runs nonetheless reach a state only a human can resolve: an
ambiguous spec, an architecture fork with real tradeoffs, a proof artifact
that will not pass, a merge conflict that is not mechanically trivial.

Without a uniform signal for "I have done what I safely can; a human must take
over", each agent invents its own dead-end behaviour, and two failure modes
recur: re-attempt spam, where an agent re-evaluates the same item every run
and re-posts the same comment; and silent give-up, where an agent exits
leaving no operator-visible trace.

## Decision

A single repository label, **`needs-human`**, is the uniform agent-to-human
hand-off marker across the whole spectacles pipeline. The contract has four
clauses:

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

`needs-human` is a hand-off state, not a content category. It is kept distinct
from the `kind:*` labels.

### When each agent applies `needs-human`

| Agent | Applies `needs-human` when |
|---|---|
| `sdd-spec` | clarifying questions remain open after one comment round; the source issue is too vague to spec at 80% confidence or higher; scope is wrong and no split is obvious |
| `sdd-triage` | the architecture has a genuine fork with material tradeoffs; a spec requirement maps to no task; a dependency cycle is not mechanically resolvable |
| `sdd-execute` | a proof artifact cannot be made to pass; the task needs edits to protected paths; the task is underspecified to implement at 80% confidence or higher |
| `sdd-validate` | a blocking gate fails and the remediation is not mechanical; not for a proof artifact the agent cannot execute on a firewall/toolchain limit when a consumer required status check covers it (that case is recorded as deferred to consumer CI), but yes when no consumer gate covers the proof |
| `sdd-review` | a critical or high finding needs a human call; spec compliance is genuinely ambiguous |
| any agent | a merge conflict it will not resolve; retries are exhausted; self-rated confidence is below the 80% evidence-rigor threshold |

`sdd-execute` additionally applies `needs-human` to a tracking issue when every
task sub-issue is closed, handing the final review and close to a human. A
tracking issue is never closed by an agent.

## Reasoning

- **Uniform.** One label, one contract, every agent. An operator learns the
  convention once.
- **Idempotent by construction.** Clause 2 makes re-processing impossible, so
  the spam failure mode cannot recur and an agent needs no per-item "have I
  already given up?" bookkeeping.
- **Operator-visible.** A `label:needs-human` filter is the escalation queue:
  every item where an agent explicitly handed off. An empty queue means no
  agent is blocked.
- **One-way by design.** Clauses 3 and 4 make the hand-off unambiguous. The
  agent owns the item until it labels; the human owns it from the label until
  they clear it; clearing resumes the agent.

## Verification

- `templates/.github/labels.yml` contains a `needs-human` entry.
- `scripts/quick-setup.sh` syncs every label in `labels.yml`, including
  `needs-human`, onto a consumer repo, so the `add-labels` safe-output never
  fails for a missing label.
- Each agent that can hand off declares the `add-labels` safe-output with
  `needs-human` in its allowed set, applies it on the give-up path, and
  excludes `needs-human`-labelled items in candidate selection.

## Consequences

- A new agent that can reach a human-required state inherits a ready-made
  hand-off: it applies `needs-human` rather than inventing a bespoke
  escalation.
- The label is sticky until a human acts. An agent will not re-evaluate a
  labelled item even if the blocker later becomes mechanically resolvable.
  This is an accepted trade: a one-way gate is simpler and safer than an agent
  second-guessing a human-owned item.
