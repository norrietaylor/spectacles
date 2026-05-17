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

The suite is being built unit by unit. Unit 1, the repository foundation, is
in place: continuous integration, the hand-off ADR, the label set, the shared
prompt fragments, and the installer skeleton.
