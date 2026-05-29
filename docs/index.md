# spectacles {.sr-only}

![spectacles: a spec-driven agent suite for GitHub Actions](assets/svg/banner-light.svg#only-light)
![spectacles: a spec-driven agent suite for GitHub Actions](assets/svg/banner-dark.svg#only-dark)

`spectacles` moves a feature from a plain GitHub issue to a merged
implementation through a disciplined pipeline: spec, architecture, triage,
execute, validate, review. Every step runs as an agentic GitHub Actions
workflow, and the whole pipeline is operated through GitHub primitives only:
issues, comments, labels, and pull requests.

## Where to start

<div class="grid cards" markdown>

- **[The SDD pipeline](sdd/index.md)**

  How a plain GitHub issue becomes a merged implementation, and what a
  human does at each step.

- **[Installing the SDD suite](sdd/install.md)**

  Run `quick-setup.sh --suite sdd` to install the suite on another
  repository, including one with an existing codebase.

- **[MCP tools](sdd/mcp-tools.md)**

  Distillery for retrieval and memory; Serena for symbol-level code
  intelligence.

- **[The issue-native SDD spec](specs/01-spec-issue-native-sdd/01-spec-issue-native-sdd.md)**

  The full design: ten demoable units, the `needs-human` contract, and the
  human-interaction model.

</div>

## Status

The repository foundation, the human-interaction contract, the shared MCP
tooling, the six pipeline agents (`sdd-spec`, `sdd-triage`, `sdd-dispatch`,
`sdd-execute`, `sdd-validate`, `sdd-review`), and the consumer packaging — the
one-command install onto another repo — are built. See
[Installing the SDD suite](sdd/install.md).

The source, including the workflow definitions, shared fragments, and ADRs,
is at [github.com/norrietaylor/spectacles](https://github.com/norrietaylor/spectacles).
