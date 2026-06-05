---
id: adr-0021
title: Advance spec/architecture status through the SDD lifecycle
kind: adr
status: accepted
supersedes:
superseded-by:
---

# ADR 0021: Advance spec/architecture status through the SDD lifecycle

- Status: Accepted
- Date: 2026-06-05

## Context

A spec (`docs/specs/NN-spec-<slug>/NN-spec-<slug>.md`) and its sibling
architecture record (`architecture.md`) each carry a `status` frontmatter
field (`planned | in-progress | complete`). `sdd-spec` and `sdd-triage` set
`planned` at authoring and nothing advanced it afterward. `distillery-sync`
mirrors the frozen value, so every spec/architecture entry read
`state/planned` in the knowledge store forever — mid-execution and after the
feature merged. ADR 0017 acknowledged this and deferred the advance as a
follow-up: "the field and its sync mirror exist now."

Real progress is already tracked on the tracking issue's `sdd:*` lifecycle
labels, which advance through `sdd:in-progress` (first `/dispatch`, or
fast-path `/approve`) and `sdd:done` (completion sweep / dispatch fallback).
The frontmatter `status` was a dead field disconnected from that signal.

Two gaps blocked closing the loop. First, a spec/architecture file recorded no
link back to its tracking issue: the frontmatter carried `id: spec-<slug>` /
`id: arch-<slug>` but no issue number, and the only link — the GitHub
sub-issue `parent` chain — is awkward to resolve from a file edit. Second,
amending a doc already merged to `main` was undefined: `/revise` assumed an
open PR and no-opped post-merge.

## Decision

1. **Record a `tracking-issue` back-link at authoring.** `sdd-spec` writes
   `tracking-issue: <N>` into the spec frontmatter and `sdd-triage` writes it
   into `architecture.md`; both authoring runs already hold
   `github.event.issue.number`. The template (`docs/specs/TEMPLATE.md`)
   documents the key. Resolution from a file edit becomes a `grep` over
   `docs/specs/**`; the spec and its `architecture.md` share a directory, so
   one match resolves both. The key is additive and safe: `distillery-sync`
   reads only `id`/`title`/`status`/`supersedes`/`superseded-by` and ignores
   unknown frontmatter keys.

2. **A deterministic workflow advances `status` from the lifecycle label.**
   `.github/workflows/sdd-doc-status.yml` — a plain Actions workflow, **not**
   a gh-aw agent (no `.md` fragment, no `.lock.yml`) — fires on
   `issues.labeled`. When the added label is `sdd:in-progress` (→
   `in-progress`) or `sdd:done` (→ `complete`), it greps
   `tracking-issue: <N>` to resolve the spec and `architecture.md`, rewrites
   their `status:` lines, and pushes the change to `main`. The label → status
   map lives in this one workflow as the single source of truth. The
   `docs/specs/**` push auto-fires `distillery-sync`, which re-mirrors
   `state/<status>`.

3. **The advance is forward-only and idempotent.** Status is ranked
   `planned(0) < in-progress(1) < complete(2)`; a file already at or past the
   target is skipped, so a re-applied or out-of-order label produces no
   commit. A label move that resolves no file (a fast-path stub spec not yet
   on `main` when `sdd:in-progress` fires) is a sanctioned no-op — the later
   `sdd:done` corrects it.

4. **The commit-to-main path is the bypass-actor App, not a safe-output.** No
   safe-output can commit to `main` (safe-outputs are PR-centric). The
   workflow mints a short-lived App installation token
   (`actions/create-github-app-token`, `permission-contents: write`) and
   pushes `HEAD:main`; that App is a `main` ruleset bypass actor (ADR 0019).
   It follows `recompile-locks.yml` exactly: `persist-credentials: false` +
   `fetch-depth: 0` checkout, `[skip ci]` commit, `git pull --rebase` before
   push, per-issue concurrency group.

5. **Define the post-merge `/revise` amendment.** A `/revise <note>` on a
   tracking issue whose spec (or architecture) PR has already merged re-authors
   the doc **in place** on a fresh branch and opens an **amendment PR** via
   `create-pull-request` — not `push-to-pull-request-branch`, which has no open
   branch to target. The amendment preserves the existing `status` and
   `tracking-issue` frontmatter; on merge `distillery-sync` bumps the entry's
   `version` in place. It refuses while any task is in flight, reusing the
   ADR 0010 clause-7 guard: one comment naming the in-flight task and pointing
   at the per-PR `/revise` loop, then `noop`.

## Reasoning

- A `grep`-resolvable back-link is the smallest mechanism that connects a file
  edit to its tracking issue. The sub-issue `parent` chain exists but needs a
  GitHub API round-trip from inside a file-editing workflow; a frontmatter
  number needs none.
- One deterministic workflow — rather than teaching each `sdd-*` agent to
  advance the field — keeps the label → status map in a single place and keeps
  the agents' only file write the doc itself, through safe-outputs.
- Forward-only ranking makes the workflow safe to re-fire: GitHub re-emits
  `labeled` on manual re-application, and the fast-path / full-path branches
  reconverge at `sdd:in-progress`, so the same target can arrive more than
  once. Idempotence means a redundant fire pushes nothing.
- The amendment opens a reviewable PR rather than committing the doc edit to
  `main` directly: a content change to a merged spec/architecture is
  human-reviewable work, unlike the mechanical `status:` bump, which is a
  deterministic mirror of an already-reviewed label transition.

## Verification

- An authored spec and its `architecture.md` carry `tracking-issue: <N>`.
- `actionlint .github/workflows/sdd-doc-status.yml` is clean; `gh aw compile`
  reports zero drift after the `sdd-spec` / `sdd-triage` fragment edits.
- Driving a tracking issue to `sdd:in-progress` commits `status: in-progress`
  to both files on `main`, and `distillery-sync` shows `state/in-progress`;
  draining to `sdd:done` flips both to `status: complete` and
  `state/complete`.
- Re-applying or applying an out-of-order label is a no-op (forward-only
  guard, no second commit). `sdd:in-progress` on an issue with no matching
  file logs and exits 0 with no commit.
- A `/revise` on a merged spec with no task in flight opens an amendment PR
  that preserves `status`/`tracking-issue`; merge bumps `version`. With a task
  in flight it posts a refusal comment and emits `noop`, opening no PR.

## Consequences

- Closes the ADR 0017 follow-up: lifecycle `status` now advances through
  `in-progress` and `complete` instead of staying frozen at `planned`.
- Adds one frontmatter key (`tracking-issue`) to the spec/architecture
  template and both authoring workflows; editing the `sdd-spec` / `sdd-triage`
  fragments recompiles their locks (committed together, CI drift gate).
- Adds one deterministic workflow that pushes to `main` via the bypass-actor
  App (ADR 0019), widening the set of automated commit-to-main paths from one
  (`recompile-locks`) to two. Both are mechanical mirrors of already-reviewed
  state.
- `/revise` is now defined for the whole doc lifecycle: open-PR push,
  pre-`/approve` plan re-post, and post-merge amendment PR.

## Cross-links

- ADR 0017 — the distillery memory integration whose deferred `status`-advance
  follow-up this closes.
- ADR 0019 — the bypass-actor App and commit-to-main pattern this workflow
  reuses.
- ADR 0010 — the clause-7 in-flight guard the post-merge `/revise` amendment
  reuses to refuse while tasks are running.
- ADR 0012 — the fast-path branch whose stub-spec timing motivates the
  no-match no-op.
