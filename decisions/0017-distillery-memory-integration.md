---
id: adr-0017
title: Distillery memory integration for spec-driven development
kind: adr
status: accepted
supersedes:
superseded-by:
---

# ADR 0017: Distillery memory integration for spec-driven development

- Status: Accepted
- Date: 2026-06-02

## Context

Distillery is the SDD suite's retrieval and memory layer. The original
integration ingested specs and ADRs on a daily schedule, deduplicated them by
fuzzy `distillery_find_similar` content match, stored them as `reference`
entries, and never recorded lineage. Planning agents (`sdd-spec`, `sdd-triage`)
cited prior work but did no gap analysis. Install provisioned configuration only;
a repository that never followed the SDD process brought none of its existing
knowledge into the store.

The goal is for Distillery to track spec-driven development across every repo
that has spectacles installed: specs and decisions land as they merge, stay
current with provenance as they change, inform planning including the gaps in
existing work, and are seeded from a repo's pre-existing docs on install.

## Decision

1. **Per-repo scoping is retained.** Every `sdd-*` query stays scoped to the
   repo's `DISTILLERY_PROJECT`. Cross-repo tracking is satisfied at the
   aggregate-store level — lifecycle state is recorded in entry tags and
   metadata, queryable across projects by a human or dashboard — not by relaxing
   planning-time scope. The privacy guarantee in `shared/sdd-mcp-distillery.md`
   is unchanged.
2. **Merge-triggered sync.** `distillery-sync` runs on `push` to the default
   branch under `docs/specs/**` and `decisions/**`, in addition to the daily
   schedule and manual dispatch. A merged spec or ADR lands in the store
   immediately.
3. **Deterministic per-file identity.** Each document maps to one entry keyed by
   a stable `srcpath/<path>` tag, looked up with `distillery_list`. Fuzzy
   content match is no longer the dedup key. Re-running never duplicates.
4. **Hybrid provenance.** A changed file updates its entry in place
   (`distillery_update`; the entry `version` bumps). Spec/ADR lineage declared
   in frontmatter (`supersedes` / `superseded-by`, or an ADR's body `Status:
   Superseded by` line) is written as a `supersedes` relation; in-doc
   `(informed by ADR-NNNN)` references are written as `citation` relations.
   `distillery_correct` (which archives the original) is reserved for explicit
   retractions and is out of this version.
5. **Knowledge-gap pass.** `shared/sdd-mcp-distillery.md` defines a gap pass
   (seed search → relation traverse → `find_similar exclude_linked`) replicating
   the `pour`/`investigate` skills with the read allow-list, since an `sdd-*`
   agent cannot invoke those skills. `sdd-spec` records the gaps in the spec's
   Open Questions; `sdd-triage` records them in the architecture record. A
   contradiction with prior work is a `needs-human` signal.
6. **Backfill on install.** The first sync against an empty project store
   discovers and ingests pre-existing documentation (`README*`, `docs/**`,
   `ARCHITECTURE.md`, `DESIGN.md`, `adr/**`) alongside any `docs/specs/` and
   `decisions/` files. `scripts/quick-setup.sh` kicks this run after install
   (suppressible with `--no-backfill`).
7. **Metadata header.** `docs/specs/TEMPLATE.md` and `decisions/TEMPLATE.md`
   carry a YAML frontmatter header (`id`, `title`, `kind`, `status`,
   `supersedes`). `status` records lifecycle (spec: planned/in-progress/complete;
   ADR: proposed/accepted/superseded). The header is additive: existing ADRs keep
   their body `Status:` line and sync falls back to parsing it.

## Reasoning

- A deterministic path key makes sync idempotent and the file→entry mapping 1:1;
  fuzzy similarity risked both duplicates and mis-merges.
- Update-in-place plus lineage relations preserve provenance without archiving
  historically valid records, which `distillery_correct` would do.
- Gap exposure turns retrieval from passive citation into active surfacing of
  decided questions, missing context, and contradictions — the highest-value
  use of accumulated memory at the planning stages.
- Backfill is what makes adoption on an extant repo worthwhile from day one.

## Verification

- `gh aw compile` regenerates the affected locks with zero drift.
- A second `distillery-sync` run with no source changes logs every document as
  skipped and creates no duplicate (idempotence).
- A merged spec PR triggers a sync; the entry carries `status: planned`. Editing
  and re-merging bumps the entry `version` in place.
- An ADR with `supersedes` produces a `supersedes` relation
  (`distillery_relations action=get`).
- An install against an empty store ingests pre-existing docs; `sdd-spec` /
  `sdd-triage` runs surface cited knowledge gaps, scoped and self-filtered.

## Consequences

- `distillery-sync`'s MCP allow-list gains `distillery_list`, `distillery_get`,
  and `distillery_relations`.
- Editing `shared/sdd-mcp-distillery.md` recompiles the `sdd-spec` and
  `sdd-triage` locks; source and lock are committed together (CI drift gate).
- The push trigger lists `main` and `master`; a repo with a different default
  branch relies on the daily schedule until the wrapper is adjusted.
- Lifecycle `status` is set at authoring and advanced through in-progress and
  complete by the deterministic `sdd-doc-status` workflow, driven by the
  tracking issue's `sdd:*` labels via a `tracking-issue` frontmatter back-link
  (ADR 0021). `distillery-sync` mirrors each advance into `state/<status>`.

## Cross-links

- `decisions/0004-uses-distribution-model.md` — distillery-sync as a wrapped
  reusable workflow.
- `decisions/0003-bootstrapping-policy.md` — Distillery as a bootstrapping
  prerequisite.
- `decisions/0021-spec-arch-status-advance.md` — advances the lifecycle
  `status` this integration mirrors, closing the follow-up deferred above.
