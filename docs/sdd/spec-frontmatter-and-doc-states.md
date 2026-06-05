# Spec frontmatter and document lifecycle states

A spec (`docs/specs/NN-spec-<slug>/NN-spec-<slug>.md`) and its sibling
architecture record (`architecture.md`) are committed Markdown files with a
YAML frontmatter block. This page documents the frontmatter fields and the
`status` lifecycle they carry, and how that lifecycle advances automatically as
the tracking issue moves through the SDD pipeline. The source of truth for the
frontmatter skeleton is `docs/specs/TEMPLATE.md`; the advance behaviour is
recorded in ADR 0021 (`decisions/0021-spec-arch-status-advance.md`).

## Frontmatter fields

```yaml
---
id: spec-<slug>
title: <human-readable feature title>
kind: spec
status: planned        # planned | in-progress | complete
tracking-issue: 123    # the GitHub tracking issue this doc was authored for
supersedes:            # optional: id of a doc this one replaces
---
```

| Field | Required | Meaning |
| --- | --- | --- |
| `id` | yes | Stable identifier — `spec-<slug>` for a spec, `arch-<slug>` for an architecture record. Matches the directory slug. distillery-sync indexes it and carries it as entry metadata. |
| `title` | yes | Human-readable feature title. distillery-sync indexes it into the entry's `title`. |
| `kind` | yes | Document kind (`spec` or `architecture`). distillery-sync carries document kind under its own `doctype/` tag, since the `kind/` tag prefix is reserved. |
| `status` | yes | Lifecycle state: `planned`, `in-progress`, or `complete`. See below. Mirrored by distillery-sync as the `state/<status>` tag and `metadata.lifecycle`. |
| `tracking-issue` | yes | The GitHub tracking issue number this doc was authored for. The status-advance workflow resolves the doc by grepping for this back-link. **distillery-sync does not read it** — it is an unknown key to the sync and is ignored. |
| `supersedes` | no | The `id` of a prior doc this one replaces. distillery-sync writes a `supersedes` relation between the two entries. |

distillery-sync reads only `id`, `title`, `status`, `supersedes`, and
`superseded-by` from frontmatter; any other key — `tracking-issue`, `kind`, or
anything else — is ignored. New frontmatter keys are therefore additive and
safe to introduce.

## Document lifecycle states

The `status` field tracks where a spec or architecture record sits in its own
lifecycle, independent of the tracking issue's `sdd:*` label:

| Status | Meaning |
| --- | --- |
| `planned` | The authoring default. The doc has been written but execution has not started. |
| `in-progress` | Implementation of the feature this doc describes is under way. |
| `complete` | The feature has merged. |

`sdd-spec` (for the spec) and `sdd-triage` (for the architecture record) set
`status: planned` at authoring time. Advancement is **forward-only**: a doc
moves `planned` → `in-progress` → `complete` and never backward. No label
advances a doc *to* `planned`; it is only ever the starting value.

## How states advance

A doc's `status` is not edited by hand after authoring. The
`sdd-doc-status.yml` workflow connects it to the real progress signal — the
tracking issue's `sdd:*` lifecycle labels:

1. The workflow fires on `issues.labeled`. It maps the added label to a target
   status (see the table below); any other label is a no-op.
2. It greps `docs/specs/**` for `tracking-issue: <N>` to resolve the spec and
   its sibling `architecture.md`. Both share a directory, so one match
   resolves both files.
3. For each matched file it compares the current `status` against the target
   using the forward-only rank `planned(0) < in-progress(1) < complete(2)`. A
   file already at or past the target is skipped, so a re-applied or
   out-of-order label produces no commit.
4. It rewrites the `status:` line of any file behind the target and commits the
   change straight to `main` (via the bypass-actor App described in ADR 0019).

The `docs/specs/**` commit then auto-fires distillery-sync, which re-mirrors
the new `state/<status>` into the knowledge store. The knowledge entry now
reads the live status instead of a frozen `state/planned`.

### Label-to-status map

| Tracking-issue label | Target doc status |
| --- | --- |
| `sdd:in-progress` | `in-progress` |
| `sdd:done` | `complete` |

These two labels are the only status transitions the workflow owns; the map
lives in `sdd-doc-status.yml` as its single source of truth. A label move that
resolves no matching file — for example a fast-path stub spec not yet merged to
`main` when `sdd:in-progress` fires — is a sanctioned no-op; the later
`sdd:done` corrects it.

## Amending a merged doc

A merged spec or architecture record can still be amended through the
`/revise` command. Run on a tracking issue whose spec (or architecture) PR has
already merged, `/revise <note>` re-authors the doc in place on a fresh branch
and opens an **amendment PR** for human review. The amendment **preserves the
existing `status`** and `tracking-issue` frontmatter — it changes content, not
lifecycle state. On merge, distillery-sync bumps the entry's `version` in
place. The amendment refuses while any task for the tracking issue is in
flight, posting one comment and pointing at the per-PR `/revise` loop instead.
See ADR 0021 for the full amendment contract.
