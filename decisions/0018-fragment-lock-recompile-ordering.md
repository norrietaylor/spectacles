---
id: adr-0018
title: Shared-fragment edits require a follow-up lock recompile on main
kind: adr
status: accepted
supersedes:
superseded-by:
---

# ADR 0018: Shared-fragment edits require a follow-up lock recompile on main

- Status: Accepted
- Date: 2026-06-02

## Context

Every agent lock inlines its imported `shared/*.md` fragments at compile time.
gh-aw resolves a pinned-ref import
(`norrietaylor/spectacles/shared/<f>.md@main`) from the **remote** `main`
branch — not the working tree, not the PR branch. This was verified
empirically: pointing local `main` at an unmerged fix and clearing the import
cache still re-fetched the committed remote fragment. A lock can therefore only
inline the fragment version that is **already on `main`**.

That creates an ordering constraint a single PR cannot satisfy. A PR that edits a
`shared/` fragment *and* the agent locks that import it compiles those locks
against the **pre-merge** fragment. The instant the PR merges, the `@main`
fragment advances, a fresh `gh aw compile` produces different locks, and the
committed locks are stale. The `compile` drift gate in `lint.yml` then fails —
on that push to `main` **and on every subsequent PR**, whose `compile` step
recompiles against the now-updated `@main` fragment — until someone recompiles
`main`.

This bit twice in one day:

- The knowledge-gap pass added to `shared/sdd-mcp-distillery.md` left the
  `sdd-spec`/`sdd-triage` locks stale after [#183](https://github.com/norrietaylor/spectacles/pull/183) merged.
- The `exclude-standard` fix added to `shared/sdd-rust-cleanup.md` left the three
  `sdd-execute` locks stale after [#178](https://github.com/norrietaylor/spectacles/pull/178) merged.

Both reddened `main` and forced a manual recompile PR ([#186](https://github.com/norrietaylor/spectacles/pull/186)).

A local `gh aw compile` does **not** reveal the drift when `.github/aw/imports/`
holds a cached fragment keyed by the unchanged `main` SHA — which is why a local
"no drift" disagreed with CI. The cache must be cleared to reproduce CI.

## Decision

1. **A shared-fragment edit and its lock recompile are two steps across the
   merge boundary.** Land the fragment (and any source edits) first; once it is
   on `main`, recompile the importing agents' locks in a follow-up commit. They
   cannot be the same PR.
2. **The recompile is a manual follow-up after merge,** done with this recipe:

   ```sh
   git fetch origin && git switch -c build/recompile origin/main
   rm -rf .github/aw/imports/norrietaylor   # clear the stale cache (the step that makes local match CI)
   gh aw compile
   git add .github/workflows/*.lock.yml \
     && git commit -m "build: recompile locks after fragment merge"
   git push -u origin build/recompile && gh pr create --base main --fill
   ```

3. **Automated auto-commit-to-`main` was evaluated and declined.** A workflow
   that recompiles and pushes the locks back to `main` on every fragment merge
   would keep `main` green without a human, but it requires a privileged push
   identity: `main` is protected by a ruleset whose only bypass actor is the
   repository-admin role, and this repository carries no GitHub App credentials
   (the App identity is provisioned on consumer repos, not here — ADR 0003). The
   standing setup (a PAT or App added to the ruleset bypass, plus rotation) is
   not justified by the frequency of fragment edits. Revisit if that frequency
   rises.

## Reasoning

- The constraint is structural, not a bug in any one PR: locks are generated
  from `@main` fragments, so a fragment edit and its recompile are inherently
  ordered across the merge.
- A manual follow-up is cheap and infrequent; the failure is loud (a red
  `compile` gate) and the fix is one idempotent command.
- The cache-clear is the non-obvious part and is the most common reason a
  contributor's local check passes while CI fails — so it is captured in the
  recipe.

## Verification

- After a `shared/*.md` edit merges, `git fetch && rm -rf
  .github/aw/imports/norrietaylor && gh aw compile` regenerates exactly the
  importing agents' locks; committing them turns `main`'s `compile` gate green.
- A second `gh aw compile` after the recompile yields no further drift
  (idempotent).

## Consequences

- Contributors editing a `shared/` fragment imported by another agent must
  expect a transient red `compile` on `main` between merge and the follow-up
  recompile PR, and must not be surprised when an unrelated PR's `compile` fails
  for the same reason — the fix is the recompile, not their change.
- The `compile` job in `lint.yml` stays the detection mechanism; this ADR is the
  documented response to it.

## Cross-links

- `decisions/0004-uses-distribution-model.md` — locks are generated from `@main`
  fragments and committed alongside their sources.
- `decisions/0002-workflow-layout-and-imports.md` — the pinned-ref import form.
- `decisions/0003-bootstrapping-policy.md` — spectacles does not self-host the
  agents, so no App identity is provisioned here.
