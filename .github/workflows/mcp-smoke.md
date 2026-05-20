---
on:
  workflow_dispatch:
  pull_request:
    types: [opened, synchronize, reopened]
    paths:
      - ".github/workflows/mcp-smoke.md"
      - ".github/workflows/mcp-smoke.lock.yml"
      - ".github/workflows/*.md"
      - "shared/sdd-mcp-*.md"
permissions:
  contents: read
engine: copilot
safe-outputs:
  noop:
mcp-servers:
  distillery:
    url: "${{ vars.DISTILLERY_MCP_URL }}"
    headers:
      Authorization: "Bearer ${{ secrets.DISTILLERY_OAUTH_TOKEN }}"
    allowed:
      - distillery_search
  serena:
    container: "ghcr.io/github/serena-mcp-server:latest"
    args:
      - "--network"
      - "host"
    entrypoint: "serena"
    entrypointArgs:
      - "start-mcp-server"
      - "--context"
      - "codex"
      - "--project"
      - ${GITHUB_WORKSPACE}
    mounts:
      - ${GITHUB_WORKSPACE}:${GITHUB_WORKSPACE}:ro
    allowed:
      - activate_project
      - find_symbol
      - get_project_structure
---

# MCP smoke test

This workflow is the install-verification smoke test for the two shared MCP
servers. It resolves both servers and returns one non-empty result from each.
It runs in two modes:

- **`workflow_dispatch`**: manual install verification. Run it after
  installing the suite to confirm the MCP configuration is correct.
- **`pull_request`**: a required PR check. The smoke runs automatically when a
  pull request modifies the MCP-touching surface (this workflow, any other
  agent workflow `.md`, or the `shared/sdd-mcp-*.md` fragments). Without this
  gate, a PR that breaks a Distillery URL, an auth credential, or a Serena
  declaration would land green and break every later agent run.

Both servers are declared from configuration: the Distillery endpoint and
OAuth credential come from `vars.DISTILLERY_MCP_URL` and
`secrets.DISTILLERY_OAUTH_TOKEN`, and Serena attaches over the runner's
`GITHUB_WORKSPACE`. No endpoint, host, organization slug, or absolute path is
a literal in this file.

## Fork carve-out

Pull requests opened from a fork do not receive `secrets.DISTILLERY_OAUTH_TOKEN`,
so the Distillery resolution would fail for a reason unrelated to the change.
On a fork PR — when `github.event.pull_request.head.repo.full_name` does not
equal `github.repository` — this workflow does no MCP resolution. The agent
emits a single `noop` with the message "mcp-smoke skipped on fork PR — a
reviewer dispatches the check manually before merge" and exits 0. The check
appears as a skipped step rather than a failure, and a maintainer dispatches
the manual run before approving merge. This carve-out is documented in
`docs/sdd/mcp-tools.md`.

## Procedure

1. **Detect the fork case first.** If the event is `pull_request` and
   `github.event.pull_request.head.repo.full_name` is not the same as
   `github.repository`, emit a `noop` with the fork-skip message above and
   exit 0. Do not resolve any MCP server. Do not call any MCP tool.
2. **Distillery.** Call the Distillery `distillery_search` tool with a short
   query (for example, the repository name or a term from a known spec),
   scoped to this repository's project via the `project` filter. Confirm the
   call returns a result set.
3. **Serena.** Call `activate_project` for the working tree, then call
   `get_project_structure` or `find_symbol`. Confirm the call returns a
   structural result. If no language server is available for this
   repository's stack, Serena returns an empty symbol set; that is graceful
   degradation, not a failure, and the smoke test records it as such.
4. Log a single summary line stating, for each server: resolved or not, and
   whether a result was returned.

This workflow is read-only. It posts no comment, opens no issue, and opens no
pull request.

## Verification

- `gh aw compile` compiles this workflow with both MCP server declarations
  present and reports zero errors.
- A `workflow_dispatch` run logs a non-empty `distillery_search` result scoped
  to this repository's project.
- The same run logs a Serena result: either a non-empty symbol or structure
  query, or an explicit graceful-degradation note when no language server is
  available.
- A `pull_request` run on a same-repo branch that touches an MCP-relevant
  path runs the full smoke; a fork PR exits 0 with the documented skip
  message.
