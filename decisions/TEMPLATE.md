---
id: adr-NNNN
title: <decision title>
kind: adr
status: proposed       # proposed | accepted | superseded
supersedes:            # optional: id of an ADR this one replaces
superseded-by:         # optional: id of an ADR that replaces this one
---

# ADR NNNN: <decision title>

<!--
Template for a numbered ADR. The frontmatter is additive: the body keeps the
`- Status:` line that existing ADRs use, and distillery-sync reads the
frontmatter `status` when present and falls back to parsing the body
`- Status:` line otherwise. Set `supersedes` / `superseded-by` to the id of the
related ADR; distillery-sync writes a `supersedes` relation between the two
knowledge entries for full provenance. `NNNN` is the next four-digit number not
already used under `decisions/`.
-->

- Status: Proposed
- Date: <YYYY-MM-DD>

## Context

The problem and the forces at play.

## Decision

1. ...

## Reasoning

- ...

## Verification

How to verify the decision was implemented.

## Consequences

What changes as a result, and what this supersedes.

## Cross-links

Related ADRs (optional).
