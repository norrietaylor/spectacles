# spectacles

Spec-driven development as agentic GitHub Actions workflows.

`spectacles` is a suite of agentic workflows (built on
[gh-aw](https://github.com/githubnext/gh-aw)) that move a feature from a plain
GitHub issue to a merged implementation through a disciplined pipeline:
**spec then architecture then triage then execute then validate then review**.
The whole pipeline is operated through GitHub primitives only: issues,
comments, labels, and pull requests. There is no separate tool and no UI.

## Pipeline

| Stage | Agent | Output |
|---|---|---|
| Spec | `sdd-spec` | a structured spec, delivered as a PR |
| Architecture and triage | `sdd-triage` | an architecture record, then a task graph of linked sub-issues |
| Execute | `sdd-execute` | an implementation PR with captured proof artifacts |
| Validate | `sdd-validate` | advisory gate findings at every phase boundary |
| Review | `sdd-review` | correctness, security, and spec-compliance review comments |

`needs-human` is the single agent-to-human hand-off label: an agent applies it
when it cannot safely proceed, and a human clears it to resume the pipeline.
See [`decisions/0001-needs-human.md`](decisions/0001-needs-human.md).

## Status

Bootstrapping. The full design is in
[`docs/specs/01-spec-issue-native-sdd`](docs/specs/01-spec-issue-native-sdd/01-spec-issue-native-sdd.md);
its nine demoable units are tracked as issues #1 through #9. This commit lands
Unit 1, the repository foundation.

## Install

Once the agent units are built, `spectacles` installs onto a consumer repo
with `scripts/quick-setup.sh`. Installation docs arrive with Unit 9.

## License

MIT. See [`LICENSE`](LICENSE).
