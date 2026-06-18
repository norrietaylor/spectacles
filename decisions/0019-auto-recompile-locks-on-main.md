---
id: adr-0019
title: Auto-recompile drifted locks on main with a bypass-actor App
kind: adr
status: accepted
supersedes:
superseded-by:
---

# ADR 0019: Auto-recompile drifted locks on main with a bypass-actor App

- Status: Accepted
- Date: 2026-06-04

## Context

Every agent lock inlines its imported `shared/*.md` fragments at compile time,
and gh-aw resolves a pinned-ref import (`...@main`) from the **remote** `main`
branch (ADR 0018). A fragment edit therefore advances the `@main` ref the
instant it merges, which makes the committed locks stale and reddens the
`compile` drift gate in `lint.yml` — on that push and on every later PR — until
someone recompiles `main`.

ADR 0018 §3 evaluated automating that recompile and **declined it**, for one
reason: pushing the regenerated locks back to protected `main` needs a
privileged push identity, and at the time this repository carried no GitHub App
credentials (the App identity was provisioned on consumer repos only, ADR 0003).
ADR 0018 §3 said to revisit "if that frequency rises." It has:
[#178](https://github.com/norrietaylor/spectacles/pull/178),
[#183](https://github.com/norrietaylor/spectacles/pull/183), and
[#198](https://github.com/norrietaylor/spectacles/pull/198) each left `main` red
and forced a manual recompile PR
([#186](https://github.com/norrietaylor/spectacles/pull/186),
[#206](https://github.com/norrietaylor/spectacles/pull/206)).

## Decision

1. **A workflow recompiles drifted locks on `main` and pushes them back
   automatically.** `recompile-locks.yml` fires on a push to `main` that touches
   a lock-affecting source (`shared/**` or `.github/workflows/*.md`), runs
   `gh aw compile`, refreshes `scripts/digest-snapshot.yml`, and — only when the
   regenerated `.lock.yml` files differ — commits and pushes them to `main`.
2. **The push identity is a GitHub App installed on this repository,** added to
   the `main` ruleset (16496590) bypass actors as `actor_type: Integration`,
   `bypass_mode: always`. The workflow mints a short-lived installation token
   (`actions/create-github-app-token`, scoped to `contents: write` +
   `workflows: write`) and pushes with it; that App actor bypasses the
   `pull_request` rule. The default `GITHUB_TOKEN`'s `github-actions[bot]` is not
   a bypass actor and is rejected.
3. **This widens ADR 0003's App scope to include this repository.** ADR 0003
   provisioned the App on consumer repos only; the build App `spectacles-bot`
   (app-id 3958001, distinct from any consumer's own automation bot) is now also
   installed on `norrietaylor/spectacles` for this one build purpose.

## Reasoning

- The two-step constraint from ADR 0018 is structural and unchanged; ADR 0019
  only removes the **manual** half of it. The fragment edit still lands first;
  the recompile still happens after `@main` advances — now by a workflow instead
  of a human.
- `workflows: write` is required, not just `contents: write`: the locks live
  under `.github/workflows/`, and GitHub blocks a token without the workflows
  scope from pushing changes to that path.
- No infinite loop: the workflow's only outputs (`.github/workflows/*.lock.yml`,
  `scripts/digest-snapshot.yml`) are outside its `paths:` trigger, so the bot's
  push never re-fires it. `[skip ci]` on the commit is belt-and-suspenders.
- A bypass-actor App was chosen over the rejected alternatives: auto-opening a
  recompile PR still leaves a PR to merge (does not close the two-step); a
  fine-grained PAT is a long-lived personal credential with main-write; a
  merge-queue compile is the largest change to the merge setup. The App mints a
  short-lived per-run token and stores no long-lived secret beyond the PEM.

## Verification

- Ruleset 16496590 `bypass_actors` includes `{actor_type: Integration,
  actor_id: 3958001, bypass_mode: always}` alongside the admin RepositoryRole.
- Merging a `shared/*.md` edit to `main` without its recompiled locks triggers
  `recompile-locks`, which pushes a `build: recompile locks…` commit, after
  which the `compile` gate on the next push is green.
- A no-op run (sources and locks already in sync) logs "nothing to push" and
  pushes no commit.

## Consequences

- Revisits and reverses ADR 0018 §3's "decline automation" decision; the manual
  recompile recipe in ADR 0018 §3 becomes the fallback, not the norm.
- Extends ADR 0003: this repository now carries `APP_ID` + `APP_PRIVATE_KEY` and
  has the build App installed, where previously the App lived on consumers only.
- A standing credential (the App PEM as `APP_PRIVATE_KEY`) now exists on this
  repository and carries the usual rotation responsibility.

## Cross-links

- ADR 0018 — the two-step recompile constraint this automates; §3 is the
  decision revisited here.
- ADR 0003 — the bootstrapping policy whose consumer-only App scope this widens.
- ADR 0004 — the inlined-imports / `uses:` distribution model that makes locks
  generated artifacts in the first place.
