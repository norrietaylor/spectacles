# ADR 0015: Wrapper route logic lives in hosted composite actions

- Status: Accepted
- Date: 2026-05-28

## Context

ADR 0004 defines a thin wrapper as a hand-written workflow carrying triggers, a
permission gate, and a cross-repo `uses:` call to the hosted lock. The wrappers
drifted far from thin. They totalled 6,515 lines; `sdd-execute-{haiku,sonnet,opus}`
were 963 lines each.

Two causes:

1. **Triplication.** The three `sdd-execute` variants were line-identical except
   `const TIER`, the `model:<tier>` job gate, the concurrency prefix, and the
   lock ref. ~1,900 lines were pure copy: the same ~625-line `actions/github-script`
   decide block and the same ~80-line auto-merge bash in all three.
2. **No shared-code mechanism for wrappers.** `shared/*.md` fragments are gh-aw
   prompt imports consumed by agent *sources*, unusable by hand-written
   wrappers. There were no composite actions. Every wrapper re-inlined its
   decide block plus shared helpers (permission gate, GraphQL parent-walk,
   sub-issue tree-walk, `/`-command parsing). The `actions/github-script` SHA
   pin (ADR-less hardening) appeared 21 times.

A wrapper's triggers, concurrency, permission gate, and lock call must stay in
the wrapper: ADR 0004 §7 makes the route job "the real gate," and a consumer
audits the wrapper. The deterministic decide *body* has no such requirement.

## Decision

1. **Heavy deterministic wrapper logic moves into composite actions hosted in
   this repo**, referenced cross-repo by pinned ref:
   `uses: norrietaylor/spectacles/.github/actions/<name>@<ref>`. This is the
   same distribution mechanism ADR 0004 uses for locks and ADR 0002 uses for
   `shared/` fragments. Consumers do not carry the actions; they reference them.

2. **Each action is `using: composite`** with an inline `actions/github-script`
   (or bash) step. No Node build toolchain, no committed `dist/`, consistent
   with the repo having no application code.

3. **`secrets` and `vars` never enter a composite action.** Composite actions
   cannot read those contexts reliably. Every `vars.*` value and token the
   logic needs becomes an explicit action **input** passed by the wrapper
   (`app-id: ${{ vars.APP_ID }}`, `github-token: ${{ github.token }}`). Secrets
   stay in the wrapper: the auto-merge App token is minted in the wrapper and
   passed to the action as `github-token`.

4. **`uses:` cannot be dynamic, so the three `sdd-execute` files stay three
   files.** They share one `sdd-route-execute` action parameterised by a `tier`
   input; the per-variant `model:<tier>` job gate, concurrency prefix, and lock
   ref remain in each wrapper.

5. **The installer pins action refs too.** `quick-setup.sh` rewrites both the
   `.github/workflows/*.lock.yml@<ref>` and the `.github/actions/*@<ref>` refs
   to `--ref`. Leaving actions on `@main` while the lock is pinned would break
   the pin guarantee.

First applied to `sdd-execute`: `sdd-route-execute` and `sdd-auto-merge`. The
three wrappers drop 963 → 245 lines. The remaining agents (dispatch, spec,
triage, monitor, validate, review, utilities) follow the same pattern, one per
change.

## Reasoning

- Composite actions are the GitHub-native way to share workflow steps across
  hand-written workflows, exactly parallel to the existing lock and fragment
  distribution. No new distribution concept is introduced.
- The extraction is mechanical and parity-preserving: the decide body and the
  auto-merge bash are copied verbatim; the only edits are `vars.*`/`TIER` →
  inputs. This is auditable by diffing the moved block against its origin.
- The `actions/github-script` SHA pin is now centralised in each action instead
  of repeated per call site.
- `gh aw compile` and the lint drift gate operate only on `.github/workflows`
  (`*.lock.yml` / `*.md`); composite actions are untouched by them.

## Verification

- Diff each moved block against the original wrapper region: only the
  `vars→inputs` / `TIER` substitutions differ.
- `actionlint` passes on every `wrappers/*.yml`. (actionlint validates
  workflows, not `action.yml`; composite actions are covered by YAML parse plus
  the end-to-end run.)
- `gh aw compile --no-check-update` leaves `.github/workflows` clean — the drift
  gate is unaffected.
- `quick-setup.sh --ref <tag>` renders wrappers whose `.lock.yml@` *and*
  `.github/actions/...@` lines both pin `<tag>`.
- End-to-end on a sandbox consumer: `/execute` per tier (the `model:<tier>` gate
  selects exactly one variant), a CodeRabbit CHANGES_REQUESTED review
  (auto-revise + iteration cap), a `needs-human` label-removal resume, and a
  merged fast-path PR all fire as before.

## Consequences

- A third hosted asset class — composite actions in `.github/actions/` —
  joins locks and `shared/` fragments. ADR 0004's "consumer carries only
  wrappers" still holds: actions are referenced cross-repo, not installed.
- Editing a route action changes behaviour for every consumer pinned to a
  moving ref, the same property locks already have. Tag-pinned consumers are
  stable until re-installed.
- Cross-action helper duplication (the permission gate, parent-walk) is reduced
  from "every wrapper" to "the few actions that use it"; eliminating it entirely
  would require a shared JS lib or a node20 action with a build, deliberately
  not adopted here.
