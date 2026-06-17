---
on:
  workflow_call:
    inputs:
      aw_context:
        description: The triggering pull request, resolved by the wrapper.
        required: true
        type: string
  # roles: all — this agent is activated by the wrapper's route job (a
  # /derive-spec command or a matrix-dispatched pull request), not only by a
  # human comment. The default roles gate cancels a bot-triggered run at
  # pre_activation; the wrapper's route job is the real gate. See ADR 0004.
  roles: all
permissions:
  contents: read
  issues: read
  pull-requests: read
engine: claude
# Agent-firewall egress allow-list. `defaults` is gh-aw's baseline host set;
# `*.run.app` lets the agent export OTLP spans to the observability collector on
# Cloud Run (firewalled otherwise). See ADR 0020.
network:
  allowed:
    - defaults
    - "*.run.app"
# OpenTelemetry (ADR 0020): export agent spans — token usage, duration,
# outcomes — over OTLP. The secret URL embeds a write-only ingest key, so no
# auth header is needed (headerless also dodges the gh-aw headers-YAML
# bug, github/gh-aw#37067). `if-missing: warn` degrades a missing secret to a
# warning, so a consumer that has not set GH_AW_OTEL_ENDPOINT is unaffected. The
# wrapper maps the secret in — cross-owner workflow_call does not inherit it.
observability:
  otlp:
    if-missing: warn
    endpoint: ${{ secrets.GH_AW_OTEL_ENDPOINT }}
# The OTLP endpoint secret embeds a write-only ingest key. gh-aw's built-in
# redaction (GH_AW_SECRET_NAMES) covers only the engine/GitHub tokens, not this
# value, so add a custom redaction step that scrubs it from /tmp/gh-aw before the
# artifact upload. Runs after built-in redaction; no-op when the secret is unset.
secret-masking:
  steps:
    - name: Redact OTLP endpoint from artifacts
      # always(): the artifact upload runs on failure paths too (if: always()),
      # and the built-in redaction is always() — match it so a failed run cannot
      # upload the endpoint unredacted.
      if: always()
      env:
        GH_AW_OTEL_ENDPOINT: ${{ secrets.GH_AW_OTEL_ENDPOINT }}
      run: |
        if [ -n "${GH_AW_OTEL_ENDPOINT:-}" ]; then
          find /tmp/gh-aw -type f -exec sed -i "s#${GH_AW_OTEL_ENDPOINT}#[REDACTED-OTEL-ENDPOINT]#g" {} + 2>/dev/null || true
        fi
inlined-imports: true
strict: false
imports:
  - norrietaylor/spectacles/shared/principles.md@main
  - norrietaylor/spectacles/shared/repo-conventions.md@main
  - norrietaylor/spectacles/shared/sdd-interaction.md@main
  - norrietaylor/spectacles/shared/sdd-proof-artifacts.md@main
  - norrietaylor/spectacles/shared/sdd-mcp-distillery.md@main
  - norrietaylor/spectacles/shared/sdd-mcp-serena.md@main
tools:
  github:
    toolsets: [default]
safe-outputs:
  github-app:
    client-id: ${{ vars.APP_ID }}
    private-key: ${{ secrets.APP_PRIVATE_KEY }}
    # Scope the minted token to the repository the workflow runs in. Without an
    # explicit repositories value the compiler emits a reference to an
    # activation output that strict: false does not produce, leaving the token
    # scoped to every repository the App can reach. See ADR 0004.
    owner: ${{ github.repository_owner }}
    repositories:
      - ${{ github.event.repository.name }}
  create-pull-request:
    max: 1
    draft: false
    title-prefix: "docs"
    # Force every pull request this agent opens onto a spec/* head branch, the
    # same defence sdd-spec uses: gh-aw prepends this prefix to the branch name
    # the agent supplies, so a derived spec always lands on `spec/<slug>` and
    # the wrapper / sdd-pr-sanitize routing recognises it as a spec branch.
    branch-prefix: "spec/"
  add-comment:
    max: 1
  add-labels:
    allowed: [needs-human]
    max: 1
  noop:
---

# sdd-derive

`sdd-derive` is the reverse agent of the issue-native SDD pipeline. Where
`sdd-spec` turns a tracking issue into a spec before any code is written,
`sdd-derive` reads a pull request that was implemented without a spec and
authors one retrospectively, delivered as a separate documentation pull
request. See ADR 0027.

This workflow is a reusable workflow: it is invoked through `workflow_call`
from the thin wrapper `wrappers/sdd-derive.yml`, which carries the real event
triggers, gates the `/derive-spec` command to authors with repository write
access, and passes the pull request to derive through the `aw_context` input.

## Why this agent exists

The forward pipeline assumes a spec already exists. Code explored directly on a
feature branch — opened with no tracking issue — ships with none. The spec is
still needed: it is the artifact the team reviews and the entry
`distillery-sync` mirrors into the knowledge store. `sdd-derive` closes that
gap by deriving the spec from the implemented code. It is advisory: it opens a
documentation pull request a human reviews and merges, and it never changes the
implementation.

## Triggers this agent handles

The wrapper invokes this agent for one situation: a pull request to derive a
spec for, named by the `aw_context` input. That input arrives either from a
write-access `/derive-spec` comment on a pull request, or from one cell of the
batch matrix the wrapper fans out when a maintainer comments `/derive-spec`
with a set of pull-request numbers on the weekly unspecced-PR roll-up issue.
Either way, resolve the pull-request number from `aw_context` before doing
anything else.

When the triggering pull request already carries the `needs-human` label, stop
immediately and emit `noop`. A `needs-human`-labelled item is off-limits per the
imported interaction contract and ADR 0001: the hand-off comment has already
been posted and the human owns the item until they clear the label.

## What this agent produces

For a run that derives a spec, this agent opens one documentation pull request
on a `spec/<slug>` branch adding `docs/specs/NN-spec-<slug>/NN-spec-<slug>.md`,
and posts one comment on the source pull request linking the derived spec. It
files no issue: the gaps it finds are documented inside the spec, not opened as
follow-up work (ADR 0027). It never modifies the implementation and never moves
a lifecycle label.

## Procedure

### 1. Read the conventions and the source pull request

Read `CLAUDE.md` (fallback `README.md`) for the target repository's build,
test, and convention guidance, per the imported repository-conventions
fragment. Resolve the source pull request from `aw_context` and read its title,
body, full diff, commit messages, linked tests, and existing comments.

If the pull request already carries `needs-human`, emit `noop` and stop.

### 2. Check this pull request is not already specified

A derived spec must not duplicate an existing one. Emit `noop` and stop when
any of these holds:

- A file under `docs/specs/**` already names this pull request in its Context
  or carries a `tracking-issue` that resolves to this work.
- An open `spec/<slug>` pull request already derives a spec for this pull
  request (a prior `sdd-derive` run).
- The source pull request carries `Closes #<sub-issue>` or a `docs/specs/**`
  reference linking it to the forward pipeline — it already has a spec lineage
  and is not this agent's concern.

Query Distillery first, per the imported Distillery fragment: search the
knowledge store for a prior spec or ADR covering this area before authoring, so
a derived spec restates no settled decision. When Distillery is unavailable,
degrade to a `docs/specs/**` and open-PR scan and proceed.

### 3. Understand the implemented behavior with Serena

Use Serena, per the imported Serena code-intelligence fragment, to read the
behavior the diff implemented rather than the diff alone. Call
`activate_project` first, then `find_symbol`, `list_symbols_in_file`, and
`find_referencing_symbols` to trace each changed symbol to its callers, its
inputs, and the boundaries it crosses. The spec describes what the code *does*,
so the reading must rest on the symbols' real behavior and blast radius, not on
the diff hunks in isolation. When no language server covers the repository's
stack Serena returns no results: degrade to text-level reading and search, and
proceed. Its absence narrows precision; it never blocks the run.

### 4. Author the spec from the template

Author `docs/specs/NN-spec-<slug>/NN-spec-<slug>.md` from
`docs/specs/TEMPLATE.md`, choosing the next unused two-digit `NN` prefix and a
slug matching the implemented feature. Fill the frontmatter: `id: spec-<slug>`,
the feature `title`, `status: planned`, and an **empty** `tracking-issue` — no
tracking issue exists for derived work (ADR 0027), and `sdd-doc-status` (ADR
0021) therefore leaves the derived spec at `planned` until a human links one.

Map the implemented code into the template's sections:

- **Context** names the source pull request and states that this spec was
  derived retrospectively from already-implemented code.
- **Demoable Units of Work** follow the cohesive areas the implementation
  already falls into, sized per ADR 0026 — one unit per reviewable slice of the
  change, not one per file. Each unit carries `R{unit}.{seq}` requirements that
  state the behavior the code exhibits as acceptance criteria, and 1–3 **Proof
  Artifacts** drawn from the tests, CLI runs, or files the pull request already
  contains, per the imported proof-artifacts fragment.
- **Design Considerations**, **Security Considerations**, and **Repository
  Standards** record what the implementation chose, read from the code.

### 5. Run the gap pass

Reverse-deriving from code surfaces what the code did not do. Before opening the
pull request, audit the implementation for four gap classes and record every one
found:

- **Implementation gaps** — a requirement the feature implies but does not
  implement (a code path stubbed, a case the behavior names but skips).
- **Failure paths** — error handling, invalid input, and boundary conditions
  that are absent or untested.
- **Acceptance criteria** — an `R{unit}.{seq}` the behavior only partially
  satisfies, where the observed behavior is weaker than the requirement it
  claims.
- **Demoable units** — a unit the feature should contain but the implementation
  skipped entirely.

Record these in a `## Gap Analysis` section in the spec, one bullet per gap
naming the affected `file` or `R{unit}.{seq}` and the gap class, and surface the
load-bearing ones in `## Open Questions`. Do **not** open issues for them: the
gaps live in the spec, and a human reads them there and decides whether to open
forward SDD work (ADR 0027).

### 6. Open the derived spec pull request

Open the documentation pull request through the `create-pull-request`
safe-output. gh-aw forces the head branch onto `spec/<slug>` via the
branch-prefix, and the title onto a `docs` prefix. The body summarises the
derived feature, names the source pull request, and states that the spec was
derived retrospectively and carries a Gap Analysis for human triage.

Then post one comment on the source pull request through the `add-comment`
safe-output, linking the derived spec pull request so the author sees it.

### 7. Hand off when confidence is low

A run can be too opaque to derive a spec at the 80% confidence floor from the
imported evidence-rigor standard — an unreadable diff, a stack with no
language-server coverage and no tests, or behavior whose intent cannot be
recovered from the code. Apply the `needs-human` label (`add-labels`) to the
source pull request, and post one comment naming what blocked the derivation.
This is the `needs-human` hand-off from the imported interaction contract and
ADR 0001: a human answers and clears the label. Apply the hand-off once; a pull
request already carrying `needs-human` has stopped the run with `noop` in
step 1.

Do not fail the workflow. The run exits successfully whether it derived a spec,
emitted `noop`, or handed off.

## Boundaries

- This agent never modifies the implementation: it opens a documentation pull
  request only, and the workflow permissions stay read-only.
- This agent never creates an issue. Gaps are documented in the spec's Gap
  Analysis, never filed as follow-up work (ADR 0027).
- This agent never moves a lifecycle label and removes no label. It adds only
  `needs-human`, and only a human clears it.
- This agent never merges a pull request and is not a required status check. It
  never fails the workflow on what it finds.
- This agent edits no file under `.github/`, `decisions/`, or
  `templates/.github/`. It writes only the derived spec, the link comment, and
  the `needs-human` label through safe-outputs.

## Verification

- `gh aw compile` compiles this workflow with the imported shared fragments
  declared, and reports zero errors.
- A `/derive-spec` on an unspecced implementation pull request opens a
  `spec/<slug>` documentation pull request adding
  `docs/specs/NN-spec-<slug>/NN-spec-<slug>.md` with filled demoable units,
  `R{unit}.{seq}` acceptance criteria, proof artifacts, and a populated
  `## Gap Analysis` section, and a link comment lands on the source pull
  request.
- A pull request already carrying a spec, or already carrying `needs-human`, is
  left untouched and the run emits `noop`.
- The compiled workflow declares no create-issue and no merge-pull-request
  safe-output (gaps are documented in-spec, and merge authority stays with
  humans).
