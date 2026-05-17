![spectacles](assets/svg/banner-light.svg#only-light)
![spectacles](assets/svg/banner-dark.svg#only-dark)

# spectacles

Spec-driven development as agentic GitHub Actions workflows.

`spectacles` moves a feature from a plain GitHub issue to a merged
implementation through a disciplined pipeline: spec, architecture, triage,
execute, validate, review. Every step runs as an agentic GitHub Actions
workflow, and the whole pipeline is operated through GitHub primitives only:
issues, comments, labels, and pull requests.

## Where to start

- The full design is the
  [issue-native SDD spec](specs/01-spec-issue-native-sdd/01-spec-issue-native-sdd.md).
- The agent-to-human hand-off contract is recorded in ADR 0001
  (`decisions/0001-needs-human.md` in the repository root).

## Status

The repository foundation, the human-interaction contract, the shared MCP
tooling, and all five pipeline agents (`sdd-spec`, `sdd-triage`,
`sdd-execute`, `sdd-validate`, `sdd-review`) are built. Consumer packaging,
the one-command install onto another repo, is the last unit.
