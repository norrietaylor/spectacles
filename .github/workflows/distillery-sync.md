---
on:
  workflow_call:
permissions:
  contents: read
  issues: read
  pull-requests: read
engine: copilot
inlined-imports: true
strict: false
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
      - distillery_list
      - distillery_get
      - distillery_relations
tools:
  github:
    toolsets: [default]
---

# Distillery sync

This agentic workflow keeps the Distillery knowledge store current for this
repository. It runs when a spec or ADR merges to the default branch (its
wrapper's `push` trigger on `docs/specs/**` and `decisions/**`), once per day on
a schedule, and on manual dispatch.

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
   `github` entries. It dedups by an `external_id` it derives, so re-running it
   updates existing entries in place. `distillery_gh_sync` ingests issues and
   pull requests only; it does not read, take, or ingest spec or ADR files.
2. **Specs, architecture records, and ADRs.** Stored as Distillery knowledge
   entries, one per file, keyed deterministically by the file's repository path
   so the entry stays a 1:1 mirror of the file as it evolves. The spec files
   and per-feature `architecture.md` records under `docs/specs/` and the
   numbered ADR files under `decisions/` are read from the checked-out working
   tree. On a first run against an empty project store, the workflow also
   backfills pre-existing documentation discovered across common locations
   (see the backfill step), so spectacles can be installed onto a repository
   that never followed the SDD process and still bring its existing knowledge
   into the store.

The run is read-only with respect to GitHub: it adds no comment, opens no
issue, and opens no pull request. Both passes are idempotent: `distillery_gh_sync`
is incremental on the GitHub side, and the document pass is made incremental by
the per-file source-path key described in the procedure below — re-running never
creates a duplicate.

## Project scoping

All ingested content is filed under this repository's own Distillery project
(the configured project slug). The store may be shared, so this workflow
ingests only this repository's content and files it under this repository's
project. It never ingests, reads, or writes another project's content.

## Deterministic per-file identity

Each document maps to exactly one knowledge entry, keyed by a stable
**source-path tag**: `srcpath/<path>`, where `<path>` is the file's
repository-relative path with every `/` replaced by `__` (for example
`docs/specs/01-spec-foo/01-spec-foo.md` becomes
`srcpath/docs__specs__01-spec-foo__01-spec-foo.md`). The source-path tag is the
dedup key, not a fuzzy content match: `distillery_find_similar` content
similarity is brittle and is not used to decide create-vs-update here. Look the
key up with `distillery_list` filtered by `project` and that one tag.

## Procedure

1. Determine the repository from the workflow context. Resolve the project
   slug from `vars.DISTILLERY_PROJECT`; every entry is filed under it.
2. **Sync issues and pull requests.** Call `distillery_gh_sync` with this
   repository (`owner/repo`, derived from the workflow context, not a file
   path) and the resolved project. `distillery_gh_sync` fetches the
   repository's issues and pull requests and stores them as `github` entries.
3. **Decide the document set.** Probe the store with
   `distillery_list(project=<slug>, limit=1)`. If it returns no entries for
   this project, this is a **backfill** run (step 3a). Otherwise it is an
   **incremental** run (step 3b).
   - **3a. Backfill set (empty store).** Enumerate, in the working tree:
     `docs/specs/**/*.md`, `decisions/*.md`, and pre-existing documentation —
     `README*`, `docs/**/*.md`, `ARCHITECTURE.md`, `DESIGN.md`, `adr/**/*.md`,
     `doc/adr/**/*.md`, `docs/adr/**/*.md`. De-duplicate the file list (a file
     matched by two globs is ingested once, by its source-path key). Cap the
     count at 500 files; if more match, ingest the first 500 by path order and
     **log every path skipped by the cap** — never truncate silently.
   - **3b. Incremental set (non-empty store).** Enumerate only
     `docs/specs/**/*.md` and `decisions/*.md`. These are the SDD artifacts a
     merge changes.
   - In both sets, **skip** `docs/specs/TEMPLATE.md`, `decisions/TEMPLATE.md`,
     and any file whose basename starts with `_`. These are skeletons, not
     knowledge.
4. **Store, update, or skip each file.** For each file in the set, read its
   contents, compute its source-path tag, classify its `kind`
   (`spec`/`architecture` for `docs/specs/**`, `adr` for `decisions/**`,
   `doc` for a backfilled location), and read its frontmatter when present
   (`id`, `title`, `status`, `supersedes`, `superseded-by`). The workflow runs
   unattended in CI: it cannot prompt a human, so it acts deterministically.
   - Look the entry up: `distillery_list(project=<slug>,
     tags=["srcpath/<path>"], output_mode="ids", include_archived=true)`.
   - **No match → create.** Call `distillery_store` with the file contents,
     the resolved `DISTILLERY_PROJECT`, `entry_type: reference`,
     `source: documentation` (Distillery has no `spec`, `decision`, or
     `document` entry type; a stored document is a `reference` entry), tags
     `project/<slug>/<specs|architecture|decisions|imported>`,
     `kind/<spec|architecture|adr|doc>`, `state/<status>` (from frontmatter
     `status`, or for an ADR without frontmatter the body `- Status:` value,
     lowercased; omit when no status is declared), and `srcpath/<path>`, and
     metadata `{ title, kind, lifecycle: <status>, source_path: <path>,
     id: <frontmatter id> }`.
   - **Match → compare and update.** `distillery_get` the entry. If its stored
     content equals the file contents, **skip** (no write, no version churn).
     Otherwise call `distillery_update` on that entry id with the new content,
     refreshed tags (including an updated `state/<status>`), and refreshed
     metadata. The entry's `version` bumps in place — the update history is the
     provenance trail; no duplicate entry is created.
5. **Write provenance relations.** After a file's entry is stored or updated,
   capture lineage with `distillery_relations`:
   - **Supersession.** When the frontmatter declares `supersedes: <id>` (or, for
     an ADR without frontmatter, the body says `Status: Superseded by NNNN` /
     `Supersedes NNNN`), resolve the referenced document's entry — by its `id`
     metadata or its `srcpath` tag — and add
     `distillery_relations(action="add", from_id=<this entry>,
     to_id=<referenced entry>, relation_type="supersedes")`. Add the relation
     once; if it already exists, leave it.
   - **Citation.** For each inline `(informed by ADR-NNNN)` reference in the
     file, resolve the referenced ADR's entry and add a `citation` relation
     from this entry to it. Skip a reference whose target is not yet in the
     store.
6. Log a short summary: how many issues and pull requests `distillery_gh_sync`
   ingested or refreshed; whether this was a backfill or incremental run; how
   many documents were created, updated, or skipped; how many supersedes and
   citation relations were written; and every path dropped by the backfill cap.
7. If the Distillery store cannot be reached on either mechanism, log the
   failure and exit. Do not retry in a loop and do not open an issue: a missed
   sync is recovered by the next merge, the next scheduled run, or a manual
   dispatch.

## Verification

- `gh aw compile` compiles this workflow with the Distillery MCP server
  declared and reports zero errors.
- A run logs both mechanisms: a non-zero count of issues and pull requests
  ingested by `distillery_gh_sync`, and a non-zero count of documents created,
  updated, or skipped by the deterministic source-path pass.
- A second run with no source changes logs every document as **skipped** and
  creates no duplicate entry (idempotence).
- A follow-up `distillery_search` from an `sdd-*` agent, scoped to this
  repository's project, returns a non-empty result for both an issue or pull
  request and a spec or ADR this sync ingested.
- After an ADR with `supersedes` is synced,
  `distillery_relations(action="get", entry_id=<new ADR entry>)` shows a
  `supersedes` edge to the prior ADR's entry.
