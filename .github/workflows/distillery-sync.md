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
      - distillery_gh_sync
      - distillery_find_similar
      - distillery_store
      - distillery_update
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

This workflow keeps the Distillery knowledge store current for this repository
through two distinct mechanisms, because the store holds two distinct kinds of
content. Later `sdd-*` agents retrieve both.

1. **Issues and pull requests.** The Distillery `distillery_gh_sync` tool.
   `distillery_gh_sync` takes a repository, not a file path: it fetches that
   repository's issues and pull requests, open and closed, and stores them as
   `github` entries. `distillery_gh_sync` ingests issues and pull requests
   only; it does not read, take, or ingest spec or ADR files.
2. **Specs and ADRs.** Stored as Distillery knowledge entries, one per file,
   the way the `distill` skill stores knowledge: a `distillery_find_similar`
   duplicate check followed by `distillery_store` (or `distillery_update` when
   the check resolves to a merge). The spec files under `docs/specs/` and the
   numbered ADR files under `decisions/` are read from the checked-out working
   tree.

The run is read-only with respect to GitHub: it adds no comment, opens no
issue, and opens no pull request. `distillery_gh_sync` is incremental on the
GitHub side, indexing new and changed issues and pull requests and leaving
unchanged content alone. The spec and ADR pass is made incremental by the
`distillery_find_similar` duplicate check described in the procedure below.

## Project scoping

All ingested content is filed under this repository's own Distillery project
(the configured project slug). The store may be shared, so this workflow
ingests only this repository's content and files it under this repository's
project. It never ingests, reads, or writes another project's content.

## Procedure

1. Determine the repository from the workflow context. Resolve the project
   slug from `vars.DISTILLERY_PROJECT`; every entry is filed under it.
2. **Sync issues and pull requests.** Call `distillery_gh_sync` with this
   repository (`owner/repo`, derived from the workflow context, not a file
   path) and the resolved project. `distillery_gh_sync` fetches the
   repository's issues and pull requests and stores them as `github` entries.
3. **Store specs and ADRs as entries.** Enumerate the spec files under
   `docs/specs/` and the ADR files under `decisions/` in the checked-out
   working tree. For each file, read its contents and:
   - Call `distillery_find_similar` with the file contents and `dedup_action`
     enabled to get a resolved `action`.
   - Apply the resolved `action`. The workflow runs unattended in CI: it
     cannot show a preview or prompt a human, so it acts on the `action` the
     server returns rather than asking.
     - `create`: call `distillery_store` with the file contents, the resolved
       `DISTILLERY_PROJECT`, `entry_type: reference` and `source: documentation`
       (Distillery has no `spec`, `decision`, or `document` entry type; a
       stored spec or ADR is a `reference` entry), and hierarchical tags
       (`project/<slug>/specs` for a file under `docs/specs/`,
       `project/<slug>/decisions` for an ADR under `decisions/`, where
       `<slug>` is this repository's name).
     - `skip`: the entry already exists unchanged; leave it and move on.
     - `merge`: call `distillery_update` on the most similar existing entry
       with the file contents.
     - `link`: call `distillery_store` as for `create`, additionally passing
       the related entry identifiers as `related_entries`.
4. Log a short summary: how many issues and pull requests `distillery_gh_sync`
   ingested or refreshed, and how many spec and ADR files were created,
   updated, skipped, or linked.
5. If the Distillery store cannot be reached on either mechanism, log the
   failure and exit. Do not retry in a loop and do not open an issue: a missed
   daily sync is recovered by the next scheduled run.

## Verification

- `gh aw compile` compiles this workflow with the Distillery MCP server
  declared and reports zero errors.
- A manual `workflow_dispatch` run logs both mechanisms: a non-zero count of
  issues and pull requests ingested by `distillery_gh_sync`, and a non-zero
  count of spec and ADR files created, updated, skipped, or linked by the
  `distillery_find_similar` and `distillery_store` pass.
- A follow-up `distillery_search` from an `sdd-*` agent, scoped to this
  repository's project, returns a non-empty result for both an issue or pull
  request and a spec or ADR this sync ingested.
