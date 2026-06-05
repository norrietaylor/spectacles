---
on:
  workflow_call:
permissions:
  contents: read
  issues: read
  pull-requests: read
engine: copilot
# Agent-firewall egress allow-list. `defaults` is gh-aw's baseline host set;
# `*.run.app` lets the agent export OTLP spans to the observability collector on
# Cloud Run (firewalled otherwise). The Distillery MCP host is injected
# separately by gh-aw from mcp-servers below, so this explicit list does not
# affect it. See ADR 0020.
network:
  allowed:
    - defaults
    - "*.run.app"
# OpenTelemetry (ADR 0020): export agent spans — token usage, duration,
# outcomes — over OTLP. The secret URL embeds a write-only ingest key, so no
# auth header is needed (headerless also dodges the gh-aw headers-YAML
# bug, github/gh-aw#37067). `if-missing: warn` degrades a missing secret to a
# warning, so a consumer that has not set GH_AW_OTEL_ENDPOINT is unaffected. The
# wrapper maps the secret in — cross-owner workflow_call does not inherit it.
observability:
  otlp:
    if-missing: warn
    endpoint: ${{ secrets.GH_AW_OTEL_ENDPOINT }}
# The OTLP endpoint secret embeds a write-only ingest key. gh-aw's built-in
# redaction (GH_AW_SECRET_NAMES) covers only the engine/GitHub tokens, not this
# value, so add a custom redaction step that scrubs it from /tmp/gh-aw before the
# artifact upload. Runs after built-in redaction; no-op when the secret is unset.
secret-masking:
  steps:
    - name: Redact OTLP endpoint from artifacts
      # always(): the artifact upload runs on failure paths too (if: always()),
      # and the built-in redaction is always() — match it so a failed run cannot
      # upload the endpoint unredacted.
      if: always()
      env:
        GH_AW_OTEL_ENDPOINT: ${{ secrets.GH_AW_OTEL_ENDPOINT }}
      run: |
        if [ -n "${GH_AW_OTEL_ENDPOINT:-}" ]; then
          find /tmp/gh-aw -type f -exec sed -i "s#${GH_AW_OTEL_ENDPOINT}#[REDACTED-OTEL-ENDPOINT]#g" {} + 2>/dev/null || true
        fi
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
safe-outputs:
  github-app:
    client-id: ${{ vars.APP_ID }}
    private-key: ${{ secrets.APP_PRIVATE_KEY }}
    # Scope the minted token to the repository the workflow runs in. Without an
    # explicit repositories value the compiler emits a reference to an
    # activation output that strict: false does not produce, leaving the token
    # scoped to every repository the App can reach. See ADR 0004.
    owner: ${{ github.repository_owner }}
    repositories:
      - ${{ github.event.repository.name }}
  # One persistent status issue per repo, maintained by upsert. The first run
  # (or a run after the prior status issue was deleted) creates it; every later
  # run updates the existing issue and adds a run-summary comment. target: "*"
  # lets update-issue/add-comment address the status issue by number on a
  # scheduled or push run that has no triggering issue.
  create-issue:
    max: 1
  update-issue:
    title:
    body:
    target: "*"
    max: 1
  add-comment:
    target: "*"
    max: 1
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

The run opens no pull request. It maintains exactly **one persistent status
issue** per repository by upsert: the first run (or a run after the prior status
issue was deleted) creates it; every later run updates that same issue in place
and adds a run-summary comment, never opening a second issue (step 7). Both
Distillery passes are idempotent: `distillery_gh_sync` is incremental on the
GitHub side, and the document pass is made incremental by the per-file
source-path key described in the procedure below — re-running never creates a
duplicate.

## Project scoping

All ingested content is filed under this repository's own Distillery project
(the configured project slug). The store may be shared, so this workflow
ingests only this repository's content and files it under this repository's
project. It never ingests, reads, or writes another project's content.

## Deterministic per-file identity

Each document maps to exactly one knowledge entry, keyed by a stable
**source-path tag**: `srcpath/<slug>`. Distillery's tag validator requires every
tag segment to match `[a-z0-9][a-z0-9-]*` (lowercase alphanumeric and hyphens
only, no leading hyphen), so the file path is canonicalized to `<slug>` by this
exact, deterministic algorithm — any run, any model, computes the same slug for
the same path:

1. Take the file's repository-relative path and **strip its extension**
   (`.md`).
2. **Lowercase** it.
3. Replace every maximal run of characters outside `[a-z0-9]` (including `/`,
   `_`, `.`, and spaces) with a **single** `-`.
4. **Strip** any leading or trailing `-`.

For example `docs/specs/01-spec-foo/01-spec-foo.md` becomes
`srcpath/docs-specs-01-spec-foo-01-spec-foo`. The source-path tag is the dedup
key, not a fuzzy content match: `distillery_find_similar` content similarity is
brittle and is not used to decide create-vs-update here. Look the key up with
`distillery_list` filtered by `project` and that one tag.

## Procedure

1. Determine the repository from the workflow context. Resolve the project
   slug: use `vars.DISTILLERY_PROJECT` when it is set; otherwise fall back to
   the repository **name** (the segment after `/` in `owner/repo`), which is the
   value the installer provisions. Resolve it once and deterministically so the
   fallback never files this run's content under a different project than a
   provisioned run; every entry is filed under the resolved slug.
2. **Sync issues and pull requests.** Call `distillery_gh_sync` with this
   repository (`owner/repo`, derived from the workflow context, not a file
   path) and the resolved project. `distillery_gh_sync` fetches the
   repository's issues and pull requests and stores them as `github` entries.
   - **A cold backfill can exceed the MCP client request timeout and fail with
     `-32001` even though the server-side sync completed.** A `-32001` (or any
     client timeout) on this call is **not** a confirmed failure. Do **not**
     retry with `background=true`: that parameter is rejected by the
     HTTP-transport deployment this workflow uses (`INVALID_PARAMS`) and wastes
     the turn. Do **not** re-call `distillery_gh_sync` synchronously to "get a
     count" either — a second call dedups and returns `0/0`, which is the dedup
     result, **not** the real ingest count, and must never be reported as one
     (step 6). Instead let step 3's `distillery_list` probe stand as the
     confirmation of whether entries landed, and record the issue/PR result for
     the summary as "sync dispatched; result unconfirmed (client timeout)"
     qualified by that probe (store non-empty vs empty). At most one such probe;
     do not poll (step 8's no-loop rule).
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
   contents, compute its source-path tag (the `srcpath/<slug>` canonicalization
   above), classify its `doctype`
   (`spec`/`architecture` for `docs/specs/**`, `adr` for `decisions/**`,
   `doc` for a backfilled location), and read its frontmatter when present
   (`id`, `title`, `status`, `supersedes`, `superseded-by`). The workflow runs
   unattended in CI: it cannot prompt a human, so it acts deterministically.
   Every tag segment must satisfy the validator's `[a-z0-9][a-z0-9-]*` rule, so
   the project slug and any status value are lowercased and have non-alphanumeric
   runs collapsed to a single `-` (the same canonicalization as the source-path
   slug) before they appear in a tag.
   - Look the entry up: `distillery_list(project=<slug>,
     tags=["srcpath/<slug>"], output_mode="ids", include_archived=true)`.
   - **No match → create.** Call `distillery_store` with the file contents,
     the resolved project slug, `entry_type: reference`,
     `source: documentation` (Distillery has no `spec`, `decision`, or
     `document` entry type; a stored document is a `reference` entry), tags
     `project/<slug>/<specs|architecture|decisions|imported>`,
     `doctype/<spec|architecture|adr|doc>` (the `kind/` prefix is reserved by
     Distillery, so document kind is carried under `doctype/`),
     `state/<status>` (from frontmatter `status`, or for an ADR without
     frontmatter the body `- Status:` value, lowercased and canonicalized; omit
     when no status is declared), and `srcpath/<slug>`, and metadata
     `{ title, doctype, lifecycle: <status>, source_path: <path>,
     id: <frontmatter id> }` (metadata values are free-form and carry the
     original, un-canonicalized path).
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
6. **Compose the run summary.** Capture: how many issues and pull requests
   `distillery_gh_sync` ingested or refreshed; whether this was a backfill or
   incremental run; how many documents were created, updated, or skipped; how
   many supersedes and citation relations were written; the resolved project
   slug; a UTC timestamp; and every path dropped by the backfill cap. Log it to
   the run, and reuse it as the status-issue payload in step 7.
   - **When step 2 hit a client timeout,** report the issue/PR line as
     "dispatched; result unconfirmed (client timeout); store <empty|non-empty>"
     using the step-3 probe result — **never** `0 ingested`. A `0/0` from a
     synchronous dedup retry is not the ingest count and must not appear in the
     summary; an unconfirmed timeout over a server-side success is not a
     failure.
7. **Upsert the persistent status issue.** Maintain exactly one status issue per
   repository, identified by the `distillery-sync` label plus the stable title
   marker `[distillery-sync] Status` (gh-aw prefixes `create-issue` titles with
   `[distillery-sync]`, so a created issue carries that prefix). The date and
   run type go in the rest of the title, never in the marker, so the find step
   is reliable across runs.
   - **Find it.** Search this repository's issues for an **open** issue carrying
     the `distillery-sync` label whose title begins with the
     `[distillery-sync] Status` marker (use the `github` toolset:
     `search_issues` / `list_issues`).
   - **None found → create.** Emit one `create-issue` (label `distillery-sync`,
     title `Status — <run type>, <UTC date>`, body = the step 6 summary). This
     is the first run, or the prior status issue was deleted or closed and is
     gone.
   - **Found → update and comment.** Emit one `update-issue` targeting that
     issue number to refresh its title (`[distillery-sync] Status — <run type>,
     <UTC date>`) and its body to the step 6 summary, and one `add-comment` on
     the same issue number carrying this run's summary. Do **not** emit a
     `create-issue` — never open a second status issue.
8. If the Distillery store cannot be reached on either mechanism, log the
   failure, upsert the status issue (step 7) recording the failure in the
   summary, and exit. Do not retry in a loop: a missed sync is recovered by the
   next merge, the next scheduled run, or a manual dispatch.

## Verification

- `gh aw compile` compiles this workflow with the Distillery MCP server
  declared and reports zero errors.
- A run logs both mechanisms. The document pass logs a non-zero count of
  documents created, updated, or skipped. The `distillery_gh_sync` pass logs
  either a count of issues and pull requests ingested or refreshed, **or**, when
  the call hit a client timeout, "dispatched; result unconfirmed" qualified by
  the store probe — an unconfirmed timeout over a server-side success is not a
  failure and is not reported as `0 ingested`.
- A cold backfill whose `distillery_gh_sync` call times out (`-32001`) emits no
  `background=true` retry and no synchronous `0/0` dedup retry, and its summary
  reports "dispatched; result unconfirmed (client timeout)" with the store-probe
  result, never `0 ingested`.
- A second run with no source changes logs every document as **skipped** and
  creates no duplicate entry (idempotence). Each document's `srcpath/<slug>` tag
  stores successfully (the validator accepts it) and is recomputed identically,
  so the dedup lookup hits.
- A second run does **not** open a new status issue: it updates the existing
  `[distillery-sync] Status` issue and adds one comment. Only the first run (or
  one after the prior status issue was deleted) emits a `create-issue`.
- A follow-up `distillery_search` from an `sdd-*` agent, scoped to this
  repository's project, returns a non-empty result for both an issue or pull
  request and a spec or ADR this sync ingested.
- After an ADR with `supersedes` is synced,
  `distillery_relations(action="get", entry_id=<new ADR entry>)` shows a
  `supersedes` edge to the prior ADR's entry.
