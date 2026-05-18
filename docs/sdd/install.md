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

Pass the Distillery endpoint and machine token in the installer's environment.
`quick-setup.sh` provisions them onto the target repo and reads them from the
environment, so the token never appears on a command line.

```sh
# Preview every planned write without applying anything.
bash scripts/quick-setup.sh --target-repo <owner>/<name> --suite sdd --dry-run

# Apply the install.
DISTILLERY_MCP_URL=https://<distillery-host>/mcp \
DISTILLERY_OAUTH_TOKEN=<machine-token> \
  bash scripts/quick-setup.sh --target-repo <owner>/<name> --suite sdd
```

`--suite sdd` installs, onto the target repository:

- the eight thin wrappers — the seven `sdd-*` agents (`sdd-spec`,
  `sdd-triage`, the three `sdd-execute` model-tier variants, `sdd-validate`,
  `sdd-review`) and `distillery-sync`. Each wrapper calls a reusable workflow
  hosted in the spectacles repository; no `.lock.yml` is copied onto the
  consumer (see `workflows/README.md` and ADR 0004);
- the `sdd:*` lifecycle labels and the `model:*` tier labels;
- the `feature`, `bug`, and `chore` issue templates.

Without `--suite sdd` the installer only syncs the base labels, which is the
Unit 1 behavior and is left intact.

The installed wrappers call the hosted reusable workflows at a pinned
spectacles ref. `--ref <ref>` sets that ref (default `main`); pass a release
tag to pin the consumer to an immutable suite version.

During a real run the installer also detects the target repository's primary
language and, when a Serena language server is known for it, sets the
`SERENA_LANGUAGE_SERVERS` variable. When the stack is not recognised it records
that no language server was provisioned and the agents degrade gracefully to
text-level reading (see `shared/sdd-mcp-serena.md`).

The installer also provisions the target repo's Distillery configuration:
`DISTILLERY_PROJECT` is set to the repository name, and `DISTILLERY_MCP_URL`
and the `DISTILLERY_OAUTH_TOKEN` secret are set from the installer's
environment when present. A value absent from the environment is reported for
a manual set; the install does not fail.

## Required configuration

The installer provisions the workflow files, the labels, and — from its own
environment — the Distillery configuration (see above). The operator still
supplies the GitHub App identity, the Copilot engine token, and the leak-scan
denylist. None of these is hardcoded in any `sdd-*` source; they are read at
run time from repository (or organization) variables and secrets.

### Variables

Set with `gh variable set <NAME> --repo <owner>/<name> --body <value>`.

| Variable | Purpose |
|---|---|
| `DISTILLERY_MCP_URL` | The Distillery HTTP MCP endpoint the agents query for retrieval and memory. The installer sets it from `DISTILLERY_MCP_URL` in its environment. |
| `DISTILLERY_PROJECT` | The Distillery project slug for this repository. All queries are scoped to it so a shared store cannot surface unrelated content. The installer sets it to the target repository's name. |
| `SERENA_LANGUAGE_SERVERS` | The Serena language server set for this repository's stack. The installer auto-detects and sets this when the stack is recognised; set it by hand otherwise, or leave it unset to run Serena in text-level fallback. |
| `APP_ID` | The ID of the GitHub App that is the agents' write identity. Each agent run mints its own short-lived installation token from it; see "The GitHub App identity" below. |

### Secrets

Set with `gh secret set <NAME> --repo <owner>/<name>`.

| Secret | Purpose |
|---|---|
| `COPILOT_GITHUB_TOKEN` | The token for the Copilot engine that runs the agents. |
| `APP_PRIVATE_KEY` | The private key (PEM) of the GitHub App that is the agents' write identity. Each agent run mints its own installation token from `APP_ID` and this key; nothing static is stored. The agents open PRs, create issues, and apply labels through that token. |
| `DISTILLERY_OAUTH_TOKEN` | The Distillery machine token — a pre-shared static bearer credential the workflows present to the Distillery MCP endpoint. Operator-issued; the installer sets it from `DISTILLERY_OAUTH_TOKEN` in its environment. See "The Distillery machine token" below. Despite the secret name, it is **not** a GitHub OAuth token. |
| `LEAK_DENYLIST` | The leak-scan denylist, one term per line. Supplied as a secret so the private terms are never themselves committed to the public tree. Comment lines begin with `#`. |

### The GitHub App identity

The agents write through a configurable GitHub App, not a personal access
token and not a hardcoded bot. Provision it once:

1. Create a GitHub App with these repository permissions: `contents: write`,
   `discussions: write`, `issues: write`, and `pull-requests: write`. The
   agents' `safe-outputs` mint an installation token scoped to exactly this
   set; a narrower grant fails the mint with "the permissions requested are
   not granted to this installation."
2. Install the App on the target repository. When the App's permissions
   change later, the installation must approve the update before the next run
   can mint a token.
3. Set the App's ID as the `APP_ID` variable and its private key (PEM) as the
   `APP_PRIVATE_KEY` secret. Repository or organization level both work; an
   organization variable and secret cover every consumer at once. The agent
   workflows declare `safe-outputs.github-app` with those two values, so each
   run mints its own short-lived installation token, scopes it to the run's
   permissions, and revokes it when the run ends. No long-lived token is
   stored, and no token-minting is left to the operator. The App ID and the
   private key are the only App inputs, and they are read at run time from the
   repository's configuration — never written into a workflow source.

The App identity is the only write identity the suite uses, and it is scoped
to the repository it is installed on. `sdd-execute` opens same-repo PRs only.
A write that carries the App identity, not the workflow's default token, is
also what lets one agent's output (a label, a merged pull request) trigger the
next agent.

### The Distillery machine token

`DISTILLERY_OAUTH_TOKEN` carries the credential the workflows present to the
Distillery MCP endpoint. The secret name is historical — the value is a
**pre-shared machine token**, not a GitHub OAuth token. Distillery's MCP
endpoint normally authenticates through an interactive browser OAuth flow;
agentic workflows run unattended and cannot complete it, so Distillery accepts
a static machine token as the credential for them.

The token is **operator-issued**. The operator who runs the Distillery
deployment generates a high-entropy token and sets it as Distillery's
`DISTILLERY_MCP_MACHINE_TOKEN`. To install the suite onto a consumer
repository, that operator runs `quick-setup.sh` with the same value in the
environment as `DISTILLERY_OAUTH_TOKEN` (see "Install command"); the installer
provisions it as the repo's `DISTILLERY_OAUTH_TOKEN` secret. Provisioning per
repo, as the installer runs, scopes the token to exactly the repositories that
install the suite.

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

1. **Workflows present.** Confirm the eight wrappers — the seven `sdd-*`
   wrappers and `distillery-sync.yml` — appear under `.github/workflows/` on
   the target repository. The `.lock.yml` reusable workflows are hosted in the
   spectacles repository and are not copied onto the consumer.
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

# 2. Confirm the sdd-* and distillery-sync wrappers are present.
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
gh workflow run distillery-sync.yml --repo <owner>/<name>
gh run list --repo <owner>/<name> --workflow distillery-sync.yml --limit 1

# 8. Open a test issue from the feature template and confirm its labels.
gh issue create --repo <owner>/<name> --template feature.md \
  --title "smoke test" --body "install smoke test"
gh issue list --repo <owner>/<name> --label sdd:spec --label kind:feature
```
