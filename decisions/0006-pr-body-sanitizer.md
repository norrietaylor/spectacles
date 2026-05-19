# ADR 0006: Mechanical sanitizer for spec and architecture pull-request bodies

- Status: Accepted
- Date: 2026-05-18

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
request — opened, edited, or reopened — it rewrites any GitHub closing keyword
(`close`/`fix`/`resolve`, with the `s`/`d`/`ed` forms) that precedes an issue
reference to `Refs`, which GitHub does not treat as closing. The issue number
is left intact.

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
- It runs on `edited` as well as `opened`, so a `/revise` that rewrites the
  body is re-sanitized.

## Verification

- A `spec/*` or `arch/*` pull request whose body contains `Fixes #N` has it
  rewritten to `Refs #N` within seconds of opening; the feature tracking issue
  is not closed when the pull request merges.
- An `sdd/*` implementation pull request keeps its `Closes #<task>`.

## Consequences

- `scripts/quick-setup.sh` installs `sdd-pr-sanitize` with the agent wrappers;
  `workflows/README.md` and `docs/sdd/install.md` list it.
- ADR 0004's prompt rule and ADR 0005's sub-issue model stand — the sanitizer
  is the backstop that makes them reliable, not a replacement for them.
