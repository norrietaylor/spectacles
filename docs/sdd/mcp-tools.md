# MCP tools

The SDD agents draw on two Model Context Protocol (MCP) servers. Both are
shared infrastructure: an `sdd-*` agent imports a fragment rather than
declaring a server itself, and every connection detail is configuration
supplied at install, never a literal in a source file.

| Server | Role | Transport | Fragment |
|---|---|---|---|
| Distillery | Retrieval and memory | HTTP, machine token | `shared/sdd-mcp-distillery.md` |
| Serena | Code intelligence | Working-tree container | `shared/sdd-mcp-serena.md` |

## Distillery: retrieval and memory

Distillery is a semantic knowledge store. It indexes this repository's specs,
decisions, issues, and pull requests, and answers semantic queries over them so
each new spec is informed by prior work.

- **Transport.** HTTP, authenticated with a pre-shared machine token.
- **Configuration.** The endpoint is the variable `DISTILLERY_MCP_URL`, the
  machine token is the secret `DISTILLERY_OAUTH_TOKEN`, and the project slug
  for this repository is the variable `DISTILLERY_PROJECT`. All three are
  repository or organization variables and secrets; none is a literal in any
  fragment or workflow. `DISTILLERY_OAUTH_TOKEN` is a static bearer credential
  issued by the Distillery operator, not a GitHub OAuth token. Agentic
  workflows run unattended and cannot complete a browser OAuth flow. See the
  install guide's "The Distillery machine token" section.
- **Tools.** `sdd-*` agents are read-only consumers and call
  `distillery_search`, `distillery_find_similar`, `distillery_relations`,
  `distillery_get`. The `distillery-sync` workflow is the only writer and
  additionally calls `distillery_gh_sync`, `distillery_store`, and
  `distillery_update`.
- **Project scoping.** Every query an `sdd-*` agent issues is scoped to this
  repository's own ingested content via the `project` filter. The store may be
  shared and may hold unrelated knowledge; scoping is the guarantee that
  retrieval cannot surface unrelated or private content into a public spec,
  issue, or pull request.
- **Keeping the store current.** The `distillery-sync` workflow runs daily and
  keeps the store current through two mechanisms. Issues and pull requests are
  ingested via the Distillery `distillery_gh_sync` tool, which takes this
  repository and stores its issues and pull requests as `github` entries.
  Specs under `docs/specs/` and ADRs under `decisions/` are stored as
  Distillery knowledge entries, one per file, via `distillery_store` after a
  `distillery_find_similar` duplicate check.

## Serena: code intelligence

Serena is a Language Server Protocol backed MCP server. It lets an agent find,
navigate, and edit code by symbol rather than by reading whole files, which is
what makes the suite viable on a consumer repository that already carries
substantial code.

- **Transport.** A container attached over the checked-out working tree
  (`GITHUB_WORKSPACE`).
- **No pinned language.** The fragment pins no language. Serena's
  language-server set is resolved at install time from the consumer
  repository's stack.
- **Tools.** `activate_project`, `find_symbol`, `find_referencing_symbols`,
  `get_symbol_documentation`, `list_symbols_in_file`, `get_project_structure`,
  and the symbol-level edit tools `replace_symbol_body`, `insert_after_symbol`,
  `insert_before_symbol`.
- **Graceful degradation.** When no language server exists for a repository's
  stack, symbol-level tools return no results. An agent does not treat that as
  a failure: it falls back to text-level file reading and plain-text search
  over the working tree and proceeds.
- **Scope.** Serena has read and write to the working tree only. It is never
  used on `.github/`, `decisions/`, `templates/.github/`, or secrets.

## Required configuration

Set these before running any workflow that uses the MCP servers. They are
repository or organization variables and secrets.

| Name | Kind | Purpose |
|---|---|---|
| `DISTILLERY_MCP_URL` | variable | Distillery HTTP MCP endpoint |
| `DISTILLERY_OAUTH_TOKEN` | secret | Distillery machine token, pre-shared and operator-issued (not a GitHub OAuth token) |
| `DISTILLERY_PROJECT` | variable | Project slug scoping queries to this repository |

Serena needs no secret: it runs locally against the checked-out working tree.
Its language-server set is provisioned at install time from the repository's
detected stack.

## Verification

- `gh aw compile` compiles `distillery-sync` with the MCP server declarations
  present and reports zero errors.
- The `leak-scan` check passes: `shared/sdd-mcp-distillery.md` and
  `shared/sdd-mcp-serena.md` carry no hostname, organization slug, bot name, or
  absolute path.
