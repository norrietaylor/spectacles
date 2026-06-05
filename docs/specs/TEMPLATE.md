---
id: spec-<slug>
title: <human-readable feature title>
kind: spec
status: planned        # planned | in-progress | complete
tracking-issue:        # the GitHub tracking issue number this spec was authored for
supersedes:            # optional: id of a spec this one replaces
---

# NN-spec-<slug>

> The repository is public. This file, and everything committed to the repo,
> carries no employer name, no private org slug, no internal repository name,
> no internal URL, no cost figure, and no contributor personal data.

<!--
Template for an SDD spec. sdd-spec authors a real spec from this skeleton and
fills the frontmatter:
  - id:        spec-<slug>, matching the directory slug.
  - title:     the human-readable feature title.
  - status:    lifecycle state. sdd-spec sets `planned` at authoring;
               advance to `in-progress` when execution starts and `complete`
               when the feature merges. distillery-sync mirrors this field into
               the knowledge store as the entry's `state/<status>` tag and
               `metadata.lifecycle`, so SDD progress is queryable per repo.
               sdd-doc-status advances it forward-only from the tracking
               issue's `sdd:*` labels (ADR 0021).
  - tracking-issue: the GitHub tracking issue number this spec was authored
               for. sdd-spec records it so the status-advance workflow can
               resolve this file by grep over docs/specs/**. distillery-sync
               does not read it (it indexes id/title/status/supersedes only);
               an unknown frontmatter key is ignored.
  - supersedes: set to the id of a prior spec this one replaces; distillery-sync
               writes a `supersedes` relation between the two entries.
distillery-sync skips this TEMPLATE.md and any file whose name starts with `_`.
-->

## Context

Why this work exists: the problem or need it addresses, what prompted it, and
the intended outcome.

## Introduction / Overview

A high-level summary of the feature.

## Goals

1. ...

## User Stories

As a <persona>, I want <capability> so that <outcome>.

## Demoable Units of Work

Each unit is independently demoable and carries requirement IDs in the
`R{unit}.{seq}` format (the first unit's requirements start at `R1.1`).

### Unit 1: <name>

- **Purpose:** ...
- **Depends on:** none | Unit N
- **Affected areas:** <file paths>
- **Functional Requirements:**
  - **R1.1** ...
  - **R1.2** ...
- **Proof Artifacts:** CLI / File / Test / Browser — a behavioral artifact, not
  a health check.

## Non-Goals

- ...

## Design Considerations

Architectural rationale and constraints surfaced by the codebase assessment.

## Repository Standards

Coding and style standards the implementation follows.

## Technical Considerations

Implementation notes.

## Security Considerations

Threats and mitigations.

## Open Questions

Knowledge gaps surfaced by the Distillery gap pass (prior constraints,
referenced-but-missing artifacts, contradictions, thin areas), each cited as
`(informed by #N)` or `(informed by ADR-NNNN)`. Empty if none.

## Verification

How to verify the spec is complete and the feature demonstrable end to end.
