# ADR 0008: Deterministic de-duplication of phase-C task sub-issues

- Status: Accepted
- Date: 2026-05-20

## Context

`sdd-triage` phase C decomposes each Unit sub-issue into one implementation
task sub-issue per single-session unit of work (ADR 0005, ADR 0007). The
agent emits one `create-issue` safe-output per task, with `parent` set to
the Unit. The "each task is single-session sized" rule and the implicit
"emit each task at most once" rule are enforced only in prose.

An end-to-end acceptance run (issue #62) showed the agent emitting two
`create_issue` safe-outputs with identical titles and identical bodies for
the same single-session Unit, parented to the same Unit sub-issue. Two
duplicate task sub-issues were created as siblings under that Unit. The
gh-aw safe-output handler does not collapse identical sibling `create_issue`
payloads within one run, and the prompt does not prevent the agent from
emitting one in the first place.

A prompt rule has failed. It is the same pattern ADR 0006 and ADR 0007 are
about: when a prompt rule does not hold, the failure mode is removed
structurally, not re-worded.

## Decision

A deterministic workflow, `sdd-triage-dedupe-tasks`, is installed on the
consumer repository alongside the agent wrappers. On every `issues.opened`
event in the consumer repository it:

1. **Identifies a phase-C task sub-issue.** The new issue must carry the
   structured `## Task` block documented in `sdd-triage.md` step 6 — that
   is, `## Task`, a `repo:` field, and a `proof artifacts:` field. A
   regular hand-filed issue, a Unit sub-issue, the spec sub-issue, and the
   architecture sub-issue do not carry that block and are ignored.

2. **Resolves the parent Unit.** It calls the sub-issues preview API's
   parent lookup. An issue without a parent is not a sub-issue and is left
   alone.

3. **Lists the parent Unit's sub-issues.** Any sibling with a strictly
   lower issue number and an identical (case-insensitive, trimmed) title is
   an earlier original of the new issue. The original is the
   lowest-numbered sibling that matches.

4. **Closes the new issue as a duplicate.** When an original is found, the
   workflow posts one comment on the new issue naming the original and
   then closes it with `state_reason: not_planned`. When no original is
   found the new issue is the first of its title and is left alone.

Lower issue number always wins, so two near-simultaneous duplicate runs
converge on the same survivor. The check is idempotent: a re-run on an
already-closed duplicate is a no-op.

## Reasoning

- The workflow is deterministic. It does not depend on the agent obeying a
  prompt, which one acceptance run already showed it does not (issue #62).
- It is scoped narrowly: only an issue carrying the phase-C structured
  body block is a candidate, and only a sibling under the same Unit can be
  its original. A hand-filed issue, a Unit sub-issue, the spec sub-issue,
  the architecture sub-issue, and an implementation pull request's task
  sub-issue created without a parent collision are all left alone.
- Lower issue number is the deterministic tiebreaker. It is monotonic, it
  is visible to both concurrent runs, and it lets the workflow be
  idempotent without coordinating state. The earlier-filed original is
  kept; the later duplicate is closed.
- The wrong-layer alternatives were considered and rejected:
  - **In-prompt de-duplication.** Adding "do not emit two `create-issue`
    calls with the same title" to phase C is prose, which ADR 0006 and
    ADR 0007 are explicitly about replacing with structure.
  - **Restructuring phase C to a two-step list-then-emit pattern.** Less
    skippable than a plain instruction but still prose-bound: the agent
    can still emit a duplicate when expanding the list.
  - **De-duplication in the gh-aw safe-output handler.** The handler lives
    outside this repository; a fix there is not in this repository's gift.
    A consumer-side backstop is.
- The `not_planned` close reason marks the duplicate visibly without
  implying the work it described was completed.

## Verification

- A phase-C run that emits two `create-issue` safe-outputs with the same
  title under the same Unit results in one open task sub-issue and one
  closed-as-duplicate sub-issue; the closed one carries a comment naming
  the open one.
- A phase-C run that emits unique titles under a Unit leaves every task
  sub-issue open.
- A hand-filed issue, a Unit sub-issue, a spec sub-issue, and an
  architecture sub-issue are not closed by this workflow.

## Consequences

- `scripts/quick-setup.sh` installs `sdd-triage-dedupe-tasks` alongside
  `sdd-pr-sanitize`; `workflows/README.md` and `docs/sdd/install.md` list
  it.
- The prompt rule in `sdd-triage.md` step 6 stands. This workflow is the
  backstop that makes the rule reliable, not a replacement for it. ADR
  0006's and ADR 0007's structural-fix posture is reinforced.
- The workflow needs `issues: write` to close the duplicate and post the
  comment; it reads sub-issue relationships through the preview API.
