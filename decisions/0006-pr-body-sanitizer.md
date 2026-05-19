# ADR 0006: Mechanical sanitizer for spec and architecture pull-request bodies

- Status: Accepted
- Date: 2026-05-18
- Amended: 2026-05-19 — `sdd-pr-sanitize` now also adds `Closes #<sub-issue>`
  for the deliverable sub-issue, so the spec and architecture pull requests
  close their sub-issue on merge (issue #58).

## Context

A spec pull request and an architecture pull request must close nothing on
merge: the pipeline closes the matching sub-issue itself (ADR 0005), and the
feature tracking issue must stay open as the lifecycle anchor.

ADR 0004 told the agents never to write a closing keyword for the feature.
ADR 0005 added the sub-issue tree on the premise that a slipped keyword would
be harmless, because it would target a sub-issue. Three acceptance runs
disproved both: the agent wrote `Closes #2`, then `Fixes #17`, then
`Fixes #20` — each time naming the feature tracking issue, not a sub-issue, in
a "Next step" footer of the pull-request body. Merging the pull request
auto-closed the feature mid-pipeline every time.

A prompt rule has failed three times across three prompt iterations. It cannot
be relied on.

## Decision

A deterministic workflow, `sdd-pr-sanitize`, is installed on the consumer
repository alongside the agent wrappers. On every `spec/*` and `arch/*` pull
request — opened, edited, or reopened — it makes two corrections to the body:

1. **It neutralizes a stray closing keyword on the feature.** Any GitHub
   closing keyword (`close`/`fix`/`resolve`, with the `s`/`d`/`ed` forms) that
   precedes an issue reference is rewritten to `Refs`, which GitHub does not
   treat as closing; the issue number is left intact. The feature tracking
   issue therefore cannot be auto-closed by a merge.

2. **It adds the link to the deliverable sub-issue.** A spec pull request
   delivers the spec sub-issue; an architecture pull request delivers the
   architecture sub-issue. The agent creates that sub-issue and the pull
   request in one run and cannot know the sub-issue number when it writes the
   body. The sanitizer runs after both exist: it resolves the deliverable
   sub-issue under the feature and adds `Closes #<sub-issue>`, so merging the
   pull request closes the deliverable sub-issue (ADR 0005). The keyword
   rewrite in (1) exempts this one reference.

Implementation pull requests on `sdd/*` branches are not touched: their
`Closes #<task>` closes the task sub-issue, which is correct.

## Reasoning

- The sanitizer is deterministic. It does not depend on the agent obeying a
  prompt, which three runs showed it does not.
- It is scoped to the two branch prefixes whose pull requests must close
  nothing, so it cannot disturb the correct `Closes #<task>` on an
  implementation pull request.
- `Refs` keeps the reference human-readable: the link to the feature survives,
  only the auto-close is removed.
- The deliverable link is added here, not by the agent, for the same reason
  the keyword rewrite is: the agent structurally cannot. It creates the
  sub-issue and the pull request in one run and never sees the sub-issue
  number. The sanitizer runs after both objects exist, so it can — and it
  resolves the sub-issue deterministically, by its `spec:` / `architecture:`
  title under the feature.
- It runs on `edited` and `reopened` as well as `opened`, so any later edit to
  the body is re-checked; both corrections are idempotent, so a re-run on the
  sanitizer's own edit changes nothing.

## Verification

- A `spec/*` or `arch/*` pull request whose body contains `Fixes #N` for the
  feature has it rewritten to `Refs #N` within seconds of opening; the feature
  tracking issue is not closed when the pull request merges.
- A `spec/*` or `arch/*` pull request gains a `Closes #<sub-issue>` for its
  deliverable sub-issue within seconds of opening; merging it closes that
  sub-issue and leaves the feature tracking issue open.
- An `sdd/*` implementation pull request keeps its `Closes #<task>`.

## Consequences

- `scripts/quick-setup.sh` installs `sdd-pr-sanitize` with the agent wrappers;
  `workflows/README.md` and `docs/sdd/install.md` list it.
- ADR 0004's prompt rule and ADR 0005's sub-issue model stand — the sanitizer
  is the backstop that makes them reliable, not a replacement for them.
- ADR 0005's spec and architecture sub-issue close is performed here: because
  the `Closes #<sub-issue>` keyword is added by this workflow, `sdd-spec` and
  `sdd-triage` no longer declare the `update-issue` safe-output.
- The workflow needs `issues: read` to resolve the deliverable sub-issue under
  the feature, in addition to the `pull-requests: write` it already held.
