---
on:
  schedule: daily
  workflow_dispatch:
permissions:
  contents: read
  issues: read
  pull-requests: read
engine: copilot
mcp-servers:
  distillery:
    url: "${{ vars.DISTILLERY_MCP_URL }}"
    headers:
      Authorization: "Bearer ${{ secrets.DISTILLERY_OAUTH_TOKEN }}"
    allowed:
      - gh-sync
      - search
tools:
  github:
    toolsets: [default]
---

# Distillery sync

This scheduled agentic workflow keeps the Distillery knowledge store current
for this repository. It runs once per day and may also be dispatched manually.

The Distillery MCP server attaches over HTTP transport, authenticated via
OAuth. The endpoint and the OAuth credential are configuration, read from
`vars.DISTILLERY_MCP_URL` and `secrets.DISTILLERY_OAUTH_TOKEN`; no endpoint,
host, or organization slug is a literal in this file.

## What to ingest

Use the Distillery `gh-sync` tool to ingest this repository's knowledge into
the store so later `sdd-*` agents can retrieve it. Ingest:

1. **Specs.** Every file under `docs/specs/`.
2. **Decisions.** Every file under `decisions/` (the numbered ADRs).
3. **Issues and pull requests.** This repository's issues and pull requests,
   open and closed.

`gh-sync` is incremental: it indexes new and changed content and leaves
unchanged content alone. The run is read-only with respect to GitHub; it adds
no comment, opens no issue, and opens no pull request.

## Project scoping

All ingested content is filed under this repository's own Distillery project
(the configured project slug). The store may be shared, so this workflow
ingests only this repository's content and files it under this repository's
project. It never ingests, reads, or writes another project's content.

## Procedure

1. Determine the repository from the workflow context.
2. Call `gh-sync` for the `docs/specs/` path, the `decisions/` path, and this
   repository's issues and pull requests, scoped to this repository's project.
3. Log a short summary: how many spec files, decision files, issues, and pull
   requests were ingested or refreshed.
4. If `gh-sync` cannot reach the store, log the failure and exit. Do not
   retry in a loop and do not open an issue: a missed daily sync is recovered
   by the next scheduled run.

## Verification

- `gh aw compile` compiles this workflow with the Distillery MCP server
  declared and reports zero errors.
- A manual `workflow_dispatch` run logs a non-zero count of ingested specs,
  decisions, issues, or pull requests.
- A follow-up `distillery.search` from an `sdd-*` agent, scoped to this
  repository's project, returns a non-empty result for content this sync
  ingested.
