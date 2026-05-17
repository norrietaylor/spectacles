# ADR 0002: Workflow layout and shared-fragment imports

- Status: Accepted
- Date: 2026-05-16

## Context

The issue-native SDD spec (`docs/specs/01-spec-issue-native-sdd/`) made two
layout assumptions that building the early units against gh-aw v0.74.3 showed
to be wrong:

1. The spec placed agentic-workflow sources under a top-level `workflows/`
   directory. `gh aw compile` only processes `.github/workflows/*.md`.
2. The spec described `shared/*.md` fragments that agents `import` as local
   paths. gh-aw's local import resolver rejects any import path outside
   `.github/`, so a workflow cannot import a repo-root `shared/` fragment as a
   local path.

## Decision

1. **Workflow sources live at `.github/workflows/*.md`.** `gh aw compile`
   generates the adjacent `*.lock.yml`. Both the `.md` source and the
   generated `.lock.yml` are committed; the `.lock.yml` is never hand-edited.
2. **Shared fragments stay at the repo-root `shared/` directory.** They are
   not relocated under `.github/`.
3. **Agents consume shared fragments via pinned-ref imports**, the
   `owner/repo/path@ref` form gh-aw accepts:
   `imports: norrietaylor/spectacles/shared/<file>.md@<ref>`. Before the first
   release the ref is `main`; it moves to a release tag once releases are cut.
4. The pinned-ref import is also how a consumer repo pulls these fragments, so
   the suite has one import path, not a separate internal one.

## Reasoning

- Pinned-ref imports work today, are the documented gh-aw cross-repo
  mechanism, and unify the internal and consumer import paths.
- Relocating `shared/` under `.github/` would satisfy local imports but would
  split the import path (local internally, pinned-ref for consumers) and bury
  human-facing fragments inside `.github/`.
- Dogfooding spectacles on its own repository is not a goal, so a
  self-referential `@main` import during the build is acceptable.

## Consequences

- The spec's `workflows/` source location and its local-import assumption are
  superseded by this ADR. A correction note in the spec points here.
- Agent units 4 to 8 declare shared fragments with the pinned-ref `imports:`
  form.
- An import pinned to `@main` resolves to whatever is on `main` at compile
  time; switching to release tags makes imports immutable once releases ship.

## Verification

- `gh aw compile` succeeds on an agent workflow whose `imports:` use the
  pinned-ref form.
- The early gh-aw workflows compile from `.github/workflows/`.
