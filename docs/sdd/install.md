# Installing the SDD suite

This page is the operator's guide to installing the spectacles spec-driven
development (SDD) suite onto a consumer repository, including a repository that
already carries a substantial codebase. It covers the install command, the
configuration the operator must supply, an existing-codebase checklist, a
post-install smoke test, and a fixture acceptance run.

The suite installs as a set of thin wrapper workflows that call hosted
reusable workflows. See `workflows/README.md` for the distribution model.
Nothing in the suite carries an org-specific or private literal: the GitHub
App identity, the Distillery endpoint and OAuth credentials, and the Serena
language-server set are all configuration, resolved at install time from the
values the operator supplies.

## Prerequisites

- The `gh` CLI, authenticated against an account with admin access to the
  target repository (admin is needed to set variables and secrets).
- A clone of the spectacles repository, from which `scripts/quick-setup.sh`
  runs.
- The operator infrastructure described under "Required configuration" below:
  a GitHub App, a reachable Distillery MCP endpoint, and the engine token.

## Install command

Run the installer from a spectacles checkout. Always do a dry run first.

```sh
# Preview every planned write without applying anything.
bash scripts/quick-setup.sh --target-repo <owner>/<name> --suite sdd --dry-run

# Apply the install.
bash scripts/quick-setup.sh --target-repo <owner>/<name> --suite sdd
```

`--suite sdd` installs, onto the target repository:

- the seven `sdd-*` thin wrappers and their adjacent reusable workflows
  (`sdd-spec`, `sdd-triage`, the three `sdd-execute` model-tier variants,
  `sdd-validate`, `sdd-review`);
- the `distillery-sync` scheduled workflow;
- the `sdd:*` lifecycle labels and the `model:*` tier labels;
- the `feature`, `bug`, and `chore` issue templates.

Without `--suite sdd` the installer only syncs the base labels, which is the
Unit 1 behavior and is left intact.

During a real run the installer also detects the target repository's primary
language and, when a Serena language server is known for it, sets the
`SERENA_LANGUAGE_SERVERS` variable. When the stack is not recognised it records
that no language server was provisioned and the agents degrade gracefully to
text-level reading (see `shared/sdd-mcp-serena.md`).

## Required configuration

The installer provisions workflow files and labels, but the operator must
supply the configuration values. None of these is hardcoded in any `sdd-*`
source; they are read at run time from repository (or organization) variables
and secrets.

### Variables

Set with `gh variable set <NAME> --repo <owner>/<name> --body <value>`.

| Variable | Purpose |
|---|---|
| `DISTILLERY_MCP_URL` | The Distillery HTTP MCP endpoint the agents query for retrieval and memory. |
| `DISTILLERY_PROJECT` | The Distillery project slug for this repository. All queries are scoped to it so a shared store cannot surface unrelated content. |
| `SERENA_LANGUAGE_SERVERS` | The Serena language server set for this repository's stack. The installer auto-detects and sets this when the stack is recognised; set it by hand otherwise, or leave it unset to run Serena in text-level fallback. |

### Secrets

Set with `gh secret set <NAME> --repo <owner>/<name>`.

| Secret | Purpose |
|---|---|
| `COPILOT_GITHUB_TOKEN` | The token for the Copilot engine that runs the agents. |
| `GH_AW_GITHUB_TOKEN` | The GitHub App installation token that is the agents' write identity. The agents open PRs, create issues, and apply labels through it. |
| `DISTILLERY_OAUTH_TOKEN` | The Distillery machine token — a pre-shared static bearer credential the workflows present to the Distillery MCP endpoint. Operator-issued; see "The Distillery machine token" below. Despite the secret name, it is **not** a GitHub OAuth token. |
| `LEAK_DENYLIST` | The leak-scan denylist, one term per line. Supplied as a secret so the private terms are never themselves committed to the public tree. Comment lines begin with `#`. |

### The GitHub App identity

The agents write through a configurable GitHub App, not a personal access
token and not a hardcoded bot. Provision it once:

1. Create a GitHub App with `contents: read`, `issues: write`, and
   `pull-requests: write` repository permissions.
2. Install the App on the target repository.
3. Mint an installation token for each run, or configure a token-minting step,
   and expose it to the workflows as the `GH_AW_GITHUB_TOKEN` secret. The App
   ID and the App private key are the operator's inputs to that step; they are
   never written into a workflow source.

The App identity is the only write identity the suite uses, and it is scoped
to the repository it is installed on. `sdd-execute` opens same-repo PRs only.

### The Distillery machine token

`DISTILLERY_OAUTH_TOKEN` carries the credential the workflows present to the
Distillery MCP endpoint. The secret name is historical — the value is a
**pre-shared machine token**, not a GitHub OAuth token. Distillery's MCP
endpoint normally authenticates through an interactive browser OAuth flow;
agentic workflows run unattended and cannot complete it, so Distillery accepts
a static machine token as the credential for them.

The token is **operator-issued** — the operator who runs the Distillery
deployment generates it, configures it on the Distillery service, and
distributes it. The two roles:

- **Operator.** Generate a high-entropy token, set it as Distillery's
  `DISTILLERY_MCP_MACHINE_TOKEN`, and hand the same value to each consumer
  repository.
- **Consumer.** You do not mint this token. Obtain it from your Distillery
  operator and set it as the `DISTILLERY_OAUTH_TOKEN` secret.

Set it once as an **organization** secret, scoped to the repositories that
install the suite, rather than per repository: there is a single machine
token, so an org-level secret is one grant for every consumer and one place to
rotate.

One shared token means one shared identity and one shared blast radius. A leak
from any consumer repository exposes the token for all of them, and
per-consumer revocation is not possible — rotation replaces the token
everywhere at once. Keep access to the secret minimal. Isolation between
repositories' knowledge is enforced by `DISTILLERY_PROJECT` scoping, not by
the token.

## Existing-codebase checklist

The suite is designed to install onto a repository that already has code and
history, not only a greenfield one. Before and after the install, confirm:

- [ ] The target repository has a `CLAUDE.md` or a `README.md` that names the
      build, test, and lint commands. Agents read the toolchain from there;
      they hardcode none. If neither file documents the toolchain, add the
      commands to `CLAUDE.md` first.
- [ ] The install did not overwrite any existing workflow. The `sdd-*` and
      `distillery-sync` workflow filenames do not collide with the target
      repository's own workflows. Review the dry-run output for any unexpected
      overwrite before applying.
- [ ] The target repository's primary language has a Serena language server
      (`SERENA_LANGUAGE_SERVERS` was set by the installer). If not, the agents
      still work via text-level reading; precision is narrower but no run is
      blocked.
- [ ] `distillery-sync` has run at least once (it is daily; dispatch it
      manually for the first run) so the knowledge store holds this
      repository's specs, decisions, issues, and pull requests before the
      first `sdd-spec` run.
- [ ] The repository's branch protection, if any, does not require a status
      check that the agents cannot satisfy. The SDD agents never merge; merge
      authority stays with humans and the consumer's own CI.
- [ ] The `feature`, `bug`, and `chore` issue templates installed cleanly and
      do not collide with the target repository's existing templates.

## Post-install smoke test

Before running a feature through the pipeline, confirm the install resolved
its dependencies:

1. **Workflows present.** Confirm the seven `sdd-*` wrappers, their reusable
   workflows, and `distillery-sync` appear under `.github/workflows/` on the
   target repository.
2. **Labels present.** Confirm all six `sdd:*` labels and all three `model:*`
   labels exist on the target repository.
3. **MCP reachable.** Dispatch `distillery-sync` once and confirm its run logs
   a non-zero count of ingested specs, decisions, issues, or pull requests.
   This proves the Distillery endpoint and OAuth credential resolve.
4. **Serena resolves.** Confirm a `sdd-spec` or `sdd-execute` run logs a
   non-empty Serena symbol query, or, on an unrecognised stack, logs the
   graceful text-level fallback. Either outcome is a pass; a hard failure is
   not.
5. **Issue template applies a label.** Open a test issue from the `feature`
   template and confirm it carries both `kind:feature` and `sdd:spec`.

## Fixture acceptance run

Per ADR 0003 (`decisions/0003-bootstrapping-policy.md`), the first real
end-to-end pipeline run is an operator acceptance step, not part of the build.
This build PR delivers the code and the docs (R9.1 to R9.4). The live
end-to-end run is the operator's to perform once the prerequisites are met.

The acceptance run is **not** executed during the build, because it requires:

- the GitHub App provisioned and installed on the fixture repository;
- the Distillery MCP endpoint reachable and authenticated;
- Serena's language server resolved for the fixture's stack (or the
  text-level fallback confirmed).

To run the acceptance test, an operator:

1. Picks a throwaway fixture repository that already carries some code (per
   ADR 0003 the first run targets a fixture, never spectacles itself).
2. Installs the suite onto it with `--suite sdd` and supplies the
   configuration above.
3. Opens a feature issue from the `feature` template and lets the pipeline run
   spec then architecture then triage then execute then validate then review,
   with human action limited to merging PRs and answering `needs-human`.
4. Confirms no installed wrapper needed a source edit for the run to complete.

A clean fixture run is the suite's install proof. It is recorded as the
operator's acceptance result, separate from this build PR.

## Verification

```sh
# 1. Preview the full SDD install without writing anything.
bash scripts/quick-setup.sh --target-repo <owner>/<name> --suite sdd --dry-run

# 2. Confirm the sdd-* wrappers and reusable workflows are present.
gh api repos/<owner>/<name>/contents/.github/workflows \
  --jq '.[].name' | grep -E '^sdd-|^distillery-sync'

# 3. Confirm the sdd:* and model:* labels are present.
gh label list --repo <owner>/<name> --search sdd
gh label list --repo <owner>/<name> --search model

# 4. Confirm the issue templates are present.
gh api repos/<owner>/<name>/contents/.github/ISSUE_TEMPLATE \
  --jq '.[].name'

# 5. Confirm the required variables are set.
gh variable list --repo <owner>/<name>

# 6. Confirm the required secrets are set (values are never shown).
gh secret list --repo <owner>/<name>

# 7. Dispatch distillery-sync and confirm the run starts.
gh workflow run distillery-sync.lock.yml --repo <owner>/<name>
gh run list --repo <owner>/<name> --workflow distillery-sync.lock.yml --limit 1

# 8. Open a test issue from the feature template and confirm its labels.
gh issue create --repo <owner>/<name> --template feature.md \
  --title "smoke test" --body "install smoke test"
gh issue list --repo <owner>/<name> --label sdd:spec --label kind:feature
```
