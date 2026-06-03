---
id: adr-0018
title: Auto-recompile locks after fragment merges (self-import ordering)
kind: adr
status: accepted
supersedes:
superseded-by:
---

# ADR 0018: Auto-recompile locks after fragment merges

- Status: Accepted
- Date: 2026-06-02

## Context

Every agent lock inlines its imported `shared/*.md` fragments at compile time.
gh-aw resolves a pinned-ref import (`norrietaylor/spectacles/shared/<f>.md@main`)
from the **remote** `main` branch — not the working tree, not the PR branch
(verified empirically: pointing local `main` at an unmerged fix and clearing the
import cache still re-fetched the committed remote fragment). A lock can
therefore only inline the fragment version that is **already on `main`**.

This creates an ordering constraint a single PR cannot satisfy. A PR that edits
a `shared/` fragment *and* the agent locks that import it compiles those locks
against the **pre-merge** fragment. The moment the PR merges, the `@main`
fragment advances, a fresh `gh aw compile` produces different locks, and the
committed locks are stale. The `compile` drift gate in `lint.yml` then fails on
that push to `main` and on **every downstream PR** (whose compile step recompiles
against the now-updated `@main` fragment), until someone recompiles `main` by
hand.

This bit twice in one day: the `sdd-spec`/`sdd-triage` locks after the
knowledge-gap pass was added to `shared/sdd-mcp-distillery.md` (issue work behind
PR #183), and the `sdd-execute` locks after the `exclude-standard` fix landed in
`shared/sdd-rust-cleanup.md` (PR #178). Both left `main` red and forced manual
recompile PRs. A local `gh aw compile` does **not** surface the drift if the
`.github/aw/imports/` cache holds a stale fragment keyed by the unchanged `main`
SHA — which is why local "no drift" disagreed with CI.

## Decision

1. **Add a `recompile-locks` workflow** (`.github/workflows/recompile-locks.yml`)
   that runs on `push` to `main` filtered to `.github/workflows/*.md` and
   `shared/**`. It mints a token from the configured GitHub App
   (`vars.APP_ID` / `secrets.APP_PRIVATE_KEY`), clears the import cache,
   runs `gh aw compile`, and if any `*.lock.yml` drifted, commits the
   regenerated locks straight back to `main`.
2. **The heal is loop-safe by construction.** The heal commit touches only
   `*.lock.yml`, which is not in the trigger's `paths`, so it never re-triggers
   the workflow. The `compile` gate in `lint.yml` (push to `main`, no `paths`
   filter) does re-run on the heal commit and passes, because recompilation is
   idempotent — leaving `main` green with a verifying check.
3. **The commit is attributed to the App identity, resolved at run time.** The
   App slug comes from the token action's `app-slug` output and the numeric id
   from `gh api /users/<slug>[bot]`; no App slug is written into the repo, so the
   "no private literals" rule (ADR 0004) holds.

## Reasoning

- The constraint is structural, not a bug to fix in any one PR: locks are
  generated from `@main` fragments, so a fragment edit and its lock recompile are
  inherently two steps across the merge boundary.
- Auto-commit is the only option that keeps `main` green without a human in the
  loop. An auto-opened recompile PR still leaves a red-`main` window in which
  every downstream PR's `compile` gate fails — the exact failure this removes.
- Pushing only generated `*.lock.yml` artifacts via the App identity is within
  the pipeline's existing trust model: the App already authors agent PRs, and the
  drift gate continues to verify the result.

## Verification

- Merge a PR that edits a `shared/*.md` fragment imported by another agent. The
  `recompile-locks` run commits the regenerated locks to `main` within one run,
  and the subsequent `compile` gate on that heal commit is green.
- A merge that changes no lock-affecting path does not trigger the workflow
  (`paths` filter); a fragment edit that produces no lock change triggers it but
  commits nothing ("Locks already current").
- Re-running `gh aw compile` after the heal yields no further drift.

## Consequences

- The GitHub App must be allowed to push to protected `main` — add it to branch
  protection's "allow specified actors to bypass required pull requests." This is
  the one setup prerequisite; `GITHUB_TOKEN` cannot bypass protection.
- Fragment-edit PRs no longer need a manual follow-up recompile PR. They may
  still show a transient red `compile` on `main` for the seconds between merge and
  the heal commit.
- A rare race (another lock-affecting merge lands while a heal compiles) fails the
  push; the next lock-affecting push heals it. The `concurrency` group serializes
  this workflow's own runs.

## Cross-links

- `decisions/0004-uses-distribution-model.md` — locks are generated from
  `@main` fragments and committed alongside their sources.
- `decisions/0002-workflow-layout-and-imports.md` — the pinned-ref import form.
