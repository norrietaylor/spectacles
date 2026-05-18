---
on:
  workflow_dispatch:
permissions:
  contents: read
engine: copilot
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

This `workflow_dispatch` workflow is the install-verification smoke test for
the two shared MCP servers. It resolves both servers and returns one non-empty
result from each. Run it after installing the suite to confirm the MCP
configuration is correct.

Both servers are declared from configuration: the Distillery endpoint and
OAuth credential come from `vars.DISTILLERY_MCP_URL` and
`secrets.DISTILLERY_OAUTH_TOKEN`, and Serena attaches over the runner's
`GITHUB_WORKSPACE`. No endpoint, host, organization slug, or absolute path is
a literal in this file.

## Procedure

1. **Distillery.** Call the Distillery `distillery_search` tool with a short
   query (for example, the repository name or a term from a known spec),
   scoped to this repository's project via the `project` filter. Confirm the
   call returns a result set.
2. **Serena.** Call `activate_project` for the working tree, then call
   `get_project_structure` or `find_symbol`. Confirm the call returns a
   structural result. If no language server is available for this
   repository's stack, Serena returns an empty symbol set; that is graceful
   degradation, not a failure, and the smoke test records it as such.
3. Log a single summary line stating, for each server: resolved or not, and
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
