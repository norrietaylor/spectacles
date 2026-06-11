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

By default the installer writes the file artifacts — the workflow wrappers, the
issue templates, and the `.gitignore` `.serena/` entry — to a
`spectacles/install` branch on the target and opens a pull request into its
default branch. This is what lets the install succeed on a repository whose
default branch is protected: the files land through review, not a direct push.
Merge that PR to activate the workflows. Labels, variables, and secrets are not
branch-scoped and are applied directly in both modes. Re-running the installer
updates the same branch and PR rather than duplicating them.

Pass `--direct` to write the file artifacts straight to the default branch
instead, skipping the PR. Use it only on a repository whose default branch is
unprotected; on a protected branch the direct writes are rejected and the
install aborts.

`--suite sdd` installs, onto the target repository:

- the nine thin wrappers — the eight `sdd-*` agents (`sdd-spec`,
  `sdd-triage`, `sdd-dispatch`, the three `sdd-execute` model-tier
  variants, `sdd-validate`, `sdd-review`) and `distillery-sync`. Each
  wrapper calls a reusable workflow hosted in the spectacles repository;
  no `.lock.yml` is copied onto the consumer (see `workflows/README.md`
  and ADR 0004);
- the `sdd-pr-sanitize` utility workflow, which corrects the issue references
  in a spec or architecture pull request body: it keeps a stray closing
  keyword from auto-closing the feature tracking issue, and adds the
  `Closes #<sub-issue>` link to the deliverable sub-issue (ADR 0005, ADR 0006);
- the `sdd-triage-dedupe-tasks` utility workflow, which closes a phase-C
  task sub-issue when an earlier-numbered sibling under the same Unit
  already carries the same title — the deterministic backstop for the
  prose-only "emit each task at most once" rule in `sdd-triage` phase C
  (ADR 0008);
- the `sdd-triage-promote-ready` utility workflow, which applies `sdd:ready`
  to a phase-C task sub-issue when its last open `blocked by` dependency
  closes: a task born with a `blocked by` link starts without `sdd:ready`,
  and nothing else in the pipeline promotes it once its blockers clear
  (ADR 0009);
- the `sdd-monitor` utility workflow, the dispatch-cascade backstop
  (issue #148 Tier 1): on a `*/10` cron plus `sdd-execute-*` completion and
  `sdd/` pull-request close, it nudges an armed-but-idle `sdd:dispatched`
  tracker with one `/dispatch` when the close-driven cascade stalls. It is
  disabled by default — set the `SDD_MONITOR` repository variable to `1` to
  enable it (see `sdd-monitor.md`);
- the `sdd-spike-actuator` utility workflow, the deterministic actuator for the
  spike wave (issue #229): when a `kind:spike` sub-issue is opened or labeled
  under a tracking issue still in triage, it posts `/execute` on that sub-issue
  via the App token so the matching `sdd-execute` variant runs the spike, the
  same way `sdd-dispatch` fans the main task cascade out;
- the `sdd-spike-reentry` utility workflow, the deterministic re-entry for the
  spike wave (issue #229): when a `kind:spike` child of a triage tracking issue
  closes or has `needs-human` cleared and zero open spikes remain, it re-enters
  `sdd-triage` phase B so the resolved spikes' findings fold into the plan;
- the `sdd:*` lifecycle labels, the `kind:spike` spike label, the
  `sdd:spike-resolved` marker, the `model:*` tier labels, and the
  `plan:provided` translation marker;
- the `feature`, `bug`, `chore`, and `spec` issue templates.

Without `--suite sdd` the installer only syncs the base labels, which is the
Unit 1 behavior and is left intact.

The installed wrappers call the hosted reusable workflows at a pinned
spectacles ref. By default the installer resolves that ref to the latest
published spectacles release tag, so a consumer pins to an immutable suite
version rather than floating on `main`; it falls back to `main` when no release
exists yet. `--ref <ref>` overrides this to pin a specific tag, branch, or SHA.

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

The table lists every repository (or organization) variable the suite reads.
The first four are required for the agents to run; the rest are optional
toggles with the defaults shown.

| Variable | Default when unset | Set by | Purpose |
|---|---|---|---|
| `DISTILLERY_MCP_URL` | — (required) | installer (from its environment) | The Distillery HTTP MCP endpoint the agents query for retrieval and memory. |
| `DISTILLERY_PROJECT` | — (required) | installer (target repo name) | The Distillery project slug for this repository. All queries are scoped to it so a shared store cannot surface unrelated content. |
| `SERENA_LANGUAGE_SERVERS` | Serena text-level fallback | installer (auto-detect) | The Serena language server set for this repository's stack. The installer auto-detects and sets this when the stack is recognised; set it by hand otherwise, or leave it unset to run Serena in text-level fallback. |
| `APP_ID` | — (required) | operator | The ID of the GitHub App that is the agents' write identity. Each agent run mints its own short-lived installation token from it; see "The GitHub App identity" below. |
| `SDD_DISPATCH_MAX_PARALLEL` | `5` | operator | The matrix parallelism cap for `sdd-dispatch`'s fan-out to `sdd-execute` runs. Any positive integer. A ready set larger than the cap queues at the matrix level and starts more cells as earlier ones finish. Set this lower on a repo with strict billing limits, or higher on a repo whose CI capacity allows it. |
| `SDD_AUTO_MERGE` | unset (off) | operator | Toggles the `auto-merge` job in each `sdd-execute` tier. Set to `1` or `true` to enable GitHub squash + delete-branch auto-merge on the PR the cascade just opened, so a green PR merges with no human in the loop (issue #127). When off, the agent opens the PR and leaves merge to a human. Leave off on a repo without branch protection. When on, the `sdd-review` wrapper also resolves the App bot's own advisory review threads so they do not deadlock auto-merge on a base branch with `required_conversation_resolution` enabled (ADR 0016); human and third-party (e.g. CodeRabbit) threads are left to gate the merge. |
| `SDD_MAX_REVIEW_ITERATIONS` | `3` | operator | Cap on auto-revise cycles per implementation PR for `CHANGES_REQUESTED` reviews (issue #128). Read by every `sdd-execute` tier. On hitting the cap the agent stops auto-revising and applies `needs-human`. |
| `SDD_TRIAGE_MIN_TASK` | `300` | operator (optional) | Estimated-diff floor (net changed lines) below which `sdd-triage` folds a task into a cohesive sibling — one whose `files in scope:` overlap, or that form a strict produce/consume chain — instead of emitting it standalone. Cuts the per-task PR/CI/validate/review/merge overhead an over-split plan pays for small work. The estimate is the agent's pre-implementation judgment; cohesion is the gate and this floor only breaks ties, so unrelated small tasks are never merged. Set to `0` to disable bundling and keep one task per requirement; lower it to bundle less aggressively (issue #252). |
| `SDD_MONITOR` | unset (off) | operator | Master switch for the `sdd-monitor` backstop workflow. Set to `1` to enable monitor `/dispatch` nudges of an armed-but-idle `sdd:dispatched` tracker; any other value keeps it off. See `sdd-monitor.md`. |
| `SDD_MONITOR_DEBOUNCE_MIN` | `5` | operator | Minutes between consecutive `/dispatch` comments `sdd-monitor` posts on the same tracker (counting both monitor- and operator-issued). Consulted only when `SDD_MONITOR=1`. |
| `SDD_MCP_EXTRA` | unset (off) | operator (optional) | Opt-in toggle for bundled-but-disabled extra MCP servers, whole-token list (e.g. `playwright`, or `playwright,<other>`). Set it to `playwright` to let the `sdd-execute` agents drive a headless browser for browser-driven checks (issue #180). Off by default: a consumer that does not set it calls no browser tool and the browser container never starts. See "Optional browser automation (Playwright)" below for the trust boundary. |
| `GH_AW_MODEL_AGENT_COPILOT` | `claude-sonnet-4.6` | operator (optional) | Overrides the Copilot model the agent step runs. Consumed by every agent lock except the `sdd-execute` tiers, which pin their model via the `model:*` task label. |
| `GH_AW_MODEL_DETECTION_COPILOT` | `claude-sonnet-4.6` | operator (optional) | Overrides the Copilot model the gh-aw detection step runs. Consumed by the `sdd-spec`, `sdd-triage`, `sdd-dispatch`, `sdd-validate`, and `sdd-review` locks. |

### Secrets

Set with `gh secret set <NAME> --repo <owner>/<name>`.

These are the operator-supplied secrets. They may be set at repository or
organization level; an organization secret covers every consumer at once. The
`GH_AW_*` token secrets that appear in the compiled locks are gh-aw boilerplate
satisfied by the workflow's default `GITHUB_TOKEN`; the operator does not
provision them. `GH_AW_OTEL_ENDPOINT` is optional — leave it unset and agents
run unchanged.

| Secret | Set by | Purpose |
|---|---|---|
| `COPILOT_GITHUB_TOKEN` | operator | The token for the Copilot engine that runs the agents. Consumed by every agent lock. |
| `APP_PRIVATE_KEY` | operator | The private key (PEM) of the GitHub App that is the agents' write identity. Each agent run mints its own installation token from `APP_ID` and this key; nothing static is stored. The agents open PRs, create issues, and apply labels through that token. |
| `DISTILLERY_OAUTH_TOKEN` | installer (from its environment) | The Distillery machine token — a pre-shared static bearer credential the workflows present to the Distillery MCP endpoint. Operator-issued; the installer sets it from `DISTILLERY_OAUTH_TOKEN` in its environment. See "The Distillery machine token" below. Despite the secret name, it is **not** a GitHub OAuth token. |
| `GH_AW_OTEL_ENDPOINT` | operator (optional) | OTLP collector URL with a write-only ingest key embedded (headerless auth). When set, every agent exports spans — token usage, duration, outcomes — to it; the host must match the `*.run.app` firewall entry baked into the locks. Unset degrades to a warning (`if-missing: warn`), agents unaffected. The collector is write-only; a leaked key can push spans, not read them. See ADR 0020. |
| `LEAK_DENYLIST` | operator | The leak-scan denylist, one term per line. Supplied as a secret so the private terms are never themselves committed to the public tree. Comment lines begin with `#`. Consumed by the `leak-scan` CI workflow, which runs in the spectacles repository, not on a consumer. |

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

### Optional browser automation (Playwright)

The `sdd-execute` agents ship a bundled-but-disabled Playwright MCP server for
browser-driven checks — for example navigating to a preview the task just built
and confirming it renders (issue #180). It is **off by default** and adds no
behavior until you opt in.

Enable it per repository by setting `SDD_MCP_EXTRA` to include `playwright`:

```sh
gh variable set SDD_MCP_EXTRA --repo <owner>/<name> --body playwright
```

This mirrors the `SERENA_LANGUAGE_SERVERS` opt-in. A pre-agent step reads the
variable and tells the agent whether browser tools are enabled. When it is
unset (or does not name `playwright`), the agent calls no browser tool, so the
headless Chromium container is never started — a consumer that does not opt in
is unaffected and pays no run-time browser cost. The value is a whole-token
list, so a future second bundled server is named alongside
(`SDD_MCP_EXTRA=playwright,<other>`).

The browser image is pinned: the fragment names a fixed version tag (never
`latest`), and `gh aw compile` resolves it to an immutable `tag@sha256:…`
digest in the compiled lock. The tool allowlist is least-privilege —
navigation, DOM snapshot, screenshot, and the common interaction verbs only.
The arbitrary-JavaScript tools (`browser_evaluate`, `browser_run_code_unsafe`)
and `browser_file_upload` are deliberately withheld.

**Trust boundary — web content is data, not instructions.** A browser tool
pulls **untrusted web content into the agent's context**. A page the agent
visits — its text, DOM, console output, or a network response — is **data, not
instructions**. This is the same rule the suite applies to Serena code reads
and Distillery results: the agent reasons over the content to inform an
artifact; it never treats anything a page says as a command, never lets page
content redirect its task, and never follows an instruction embedded in fetched
content (a prompt injection in page text, a hidden element, or a network
response). The least-privilege allowlist enforces this mechanically: with the
arbitrary-code and file-upload tools withheld, the worst a hostile page can do
is feed misleading text into context, which the data-not-instructions rule
already neutralizes. Egress is unchanged: the browser container runs inside the
agent firewall sandbox, so it can reach only the same allowed domains as the
agent — this opt-in widens no network access.

## Workflows installed

`--suite sdd` writes fifteen workflow files to the consumer's
`.github/workflows/`. Nine are agent wrappers; six are utility workflows.
None carries a `.lock.yml` — every wrapper calls a hosted reusable workflow by
pinned ref (ADR 0004).

| Workflow | Triggers | What it does |
|---|---|---|
| `sdd-spec` | `issues`, `issue_comment`, `pull_request` | Drafts a spec (full path) or proposes/runs the fast path from a tracking issue. |
| `sdd-triage` | `issues`, `issue_comment`, `pull_request` | On `/triage`: architecture record, then plan comment, then the Unit/task tree on `/approve`. |
| `sdd-dispatch` | `issue_comment`, `issues` | On `/dispatch`: computes the ready set and fans out `sdd-execute` runs in a bounded matrix; re-fires on every task close. |
| `sdd-execute-haiku` | `workflow_dispatch`, `issue_comment`, `issues`, `pull_request` | Low-complexity tier. Implements a ready task and opens an implementation PR. |
| `sdd-execute-sonnet` | `workflow_dispatch`, `issue_comment`, `issues`, `pull_request` | Moderate-complexity tier. |
| `sdd-execute-opus` | `workflow_dispatch`, `issue_comment`, `issues`, `pull_request` | High-complexity tier. |
| `sdd-validate` | `pull_request`, `issues` | Posts advisory findings at each phase boundary. |
| `sdd-review` | `pull_request` | Posts code-review comments on the implementation PR. |
| `distillery-sync` | `push` (merged `docs/specs/**`, `decisions/**`), `schedule` (daily), `workflow_dispatch` | Ingests specs, architecture records, ADRs, issues, and PRs into the Distillery store, keyed deterministically by file path so re-runs update in place. Writes `supersedes`/`citation` provenance relations. The first run against an empty store backfills pre-existing docs. The only Distillery writer. |
| `sdd-pr-sanitize` | `pull_request` | Neutralizes a stray issue-closing keyword in a spec/architecture PR body and adds `Closes #<sub-issue>` (ADR 0005, ADR 0006). |
| `sdd-triage-dedupe-tasks` | `issues` | Closes a duplicate phase-C task sub-issue (ADR 0008). |
| `sdd-triage-promote-ready` | `issues` | Applies `sdd:ready` to a task when its last `blocked by` blocker closes (ADR 0009, ADR 0013). |
| `sdd-monitor` | `workflow_run`, `pull_request`, `schedule` (`*/10`) | Backstop that nudges an armed-but-idle `sdd:dispatched` tracker with `/dispatch`. Disabled unless `SDD_MONITOR=1` (see `sdd-monitor.md`). |
| `sdd-spike-actuator` | `issues` (`opened`, `labeled`) | Deterministic actuator for the spike wave: posts `/execute` on a `kind:spike` sub-issue under a triage tracking issue so `sdd-execute` runs the spike (issue #229). |
| `sdd-spike-reentry` | `issues` (`closed`, `unlabeled`) | Deterministic re-entry: when a `kind:spike` child closes (or its `needs-human` is cleared) and zero open spikes remain, re-enters `sdd-triage` phase B (issue #229). |

## Labels installed

`--suite sdd` syncs the complete label set below. Eight `sdd:*` labels are the
lifecycle state machine — exactly one is present on a tracking issue at a time.
`sdd:dispatched`, `sdd:spike-resolved`, `plan:provided`, and `needs-human` are
orthogonal markers that coexist with the lifecycle label. The `kind:*`,
`priority:*`, and `model:*` families are metadata, not states. The state machine
and the agent that writes each transition are in `shared/sdd-interaction.md`.

| Label | Family | Set by | Meaning |
|---|---|---|---|
| `sdd:spec` | lifecycle | template / `/spec` | Being specified by `sdd-spec`. |
| `sdd:fastpath` | lifecycle | `sdd-spec` on `/fastpath`, or stub merge | Fast path armed; awaiting stub merge or `/approve` (ADR 0012). |
| `sdd:fastpath-review` | lifecycle | `sdd-spec` on stub PR open | Fast-path stub spec PR open, awaiting merge (ADR 0012). |
| `sdd:triage` | lifecycle | `sdd-spec` on spec-PR merge | Architecture and triage running. |
| `sdd:ready` | lifecycle | `sdd-triage` phase C | Tasks decomposed and queued, awaiting `/dispatch`. |
| `sdd:in-progress` | lifecycle | `sdd-dispatch` (full) / `sdd-execute` (fast) | Cascade armed; tasks being implemented. |
| `sdd:review` | lifecycle | `sdd-validate` on clean pass | Implementation awaits human review. |
| `sdd:done` | lifecycle | `sdd-execute` when all tasks close | Complete; human does the final close. |
| `sdd:dispatched` | marker | `sdd-dispatch` on first `/dispatch` | Cascade armed; re-fires on every task close until the tree drains. |
| `sdd:spike-resolved` | marker | `sdd-validate` on a `proved` spike | A spike sub-issue's experiment proved its load-bearing assumption (issue #229). |
| `plan:provided` | marker | `spec.md` template / human | Tracking-issue body is a Claude plan; `sdd-spec`/`sdd-triage` translate it (issue #102). Cleared when the architecture (or fast-path stub) PR opens. |
| `needs-human` | marker | any agent | Agent handed off; a human acts then clears it (ADR 0001). |
| `model:haiku` | tier | `sdd-triage` | Low-complexity task; haiku `sdd-execute` variant. |
| `model:sonnet` | tier | `sdd-triage` | Moderate-complexity task; sonnet variant. |
| `model:opus` | tier | `sdd-triage` | High-complexity task; opus variant. |
| `kind:feature` | kind | template | A new feature or capability. |
| `kind:bug` | kind | template | Something is not working. |
| `kind:chore` | kind | template | Maintenance, refactor, or internal improvement. |
| `kind:spike` | kind | `sdd-triage` phase A step 4a | A time-boxed spike sub-issue resolving a load-bearing assumption (issue #229). |
| `priority:must-have` | priority | human | Must be done. |
| `priority:should-have` | priority | human | Should be done. |
| `priority:nice-to-have` | priority | human | Nice to have. |

## Existing-codebase checklist

The suite is designed to install onto a repository that already has code and
history, not only a greenfield one. Before and after the install, confirm:

- [ ] The target repository has a `CLAUDE.md` or a `README.md` that names the
      build, test, and lint commands. Agents read the toolchain from there;
      they hardcode none. If neither file documents the toolchain, add the
      commands to `CLAUDE.md` first.
- [ ] The target repository's package registry is reachable from the agent
      sandbox. The agents run inside gh-aw's network-restricted firewall; its
      allowlist covers the GitHub APIs, the npm registry, and the Ubuntu apt
      mirrors, but not every language's registry — `pypi.org` is not on it.
      For a Node consumer the registry is covered, so `sdd-execute` runs the
      repository's declared checks in-sandbox before opening a pull request:
      it detects the package manager from the lockfile (pnpm/yarn/npm),
      installs against the frozen lockfile, and runs the declared typecheck,
      lint, test, and build scripts — a PR opens only once they pass. If
      the build or test command the agents read from `CLAUDE.md` fetches from
      a registry the firewall does not allow, `sdd-execute` and `sdd-validate`
      cannot install the toolchain: the proof-artifact gate degrades to manual
      inspection of the diff instead of executed tests. The run is not blocked
      and verification still happens, but it is narrower. When a required
      status check on this repository runs the same command, `sdd-validate`
      records the proof artifact as deferred to consumer CI (an Info finding)
      rather than applying `needs-human`, so the auto-merge cascade is not
      stalled by the firewall limit alone; the consumer's required check
      remains the gate. If no required check covers the proof, `sdd-validate`
      still hands off via `needs-human` so a human closes the gap. Extending
      the firewall allowlist for a stack whose registry is not covered is a
      known limitation.
- [ ] The install did not overwrite any existing workflow. The `sdd-*` and
      `distillery-sync` workflow filenames do not collide with the target
      repository's own workflows. Review the dry-run output for any unexpected
      overwrite before applying.
- [ ] The target repository's primary language has a Serena language server
      (`SERENA_LANGUAGE_SERVERS` was set by the installer). If not, the agents
      still work via text-level reading; precision is narrower but no run is
      blocked. For a **Rust** consumer (`SERENA_LANGUAGE_SERVERS=rust-analyzer`),
      the Serena MCP image ships no Rust language server and cannot install one
      inside the firewalled agent. The SDD agents provision it on the runner: a
      host pre-agent step downloads a pinned, checksum-verified `rust-analyzer`
      release binary from GitHub (outside the firewall sandbox) and mounts it
      into the Serena container, so symbol-level intelligence works without
      adding any toolchain registry to the agent's network. The download is
      gated on `SERENA_LANGUAGE_SERVERS` naming `rust-analyzer`, so non-Rust
      consumers are unaffected. See `shared/sdd-mcp-serena.md`.
- [ ] `distillery-sync` has run at least once so the knowledge store holds this
      repository's specs, decisions, issues, and pull requests before the first
      `sdd-spec` run. The installer kicks this run automatically unless
      `--no-backfill` was passed; in installer-PR mode it prints the
      `gh workflow run distillery-sync.yml` command to run after the PR merges.
      On its first run the store is empty, so the agent backfills pre-existing
      documentation (README, `docs/**`, `ARCHITECTURE.md`, `adr/**`) in addition
      to any `docs/specs/` and `decisions/` files — installing onto a repo that
      never followed the SDD process still brings its existing knowledge in.
- [ ] The repository's branch protection, if any, does not require a status
      check that the agents cannot satisfy. The SDD agents never merge; merge
      authority stays with humans and the consumer's own CI.
- [ ] The `feature`, `bug`, `chore`, and `spec` issue templates installed
      cleanly and do not collide with the target repository's existing
      templates.

## Post-install smoke test

Run these after the installer PR is merged (default mode), or right after the
install in `--direct` mode. Before running a feature through the pipeline,
confirm the install resolved its dependencies:

1. **Workflows present.** Confirm the nine wrappers — the eight `sdd-*`
   wrappers (including `sdd-dispatch.yml`) and `distillery-sync.yml` — and
   the `sdd-pr-sanitize.yml`, `sdd-triage-dedupe-tasks.yml`,
   `sdd-triage-promote-ready.yml`, `sdd-monitor.yml`, `sdd-spike-actuator.yml`,
   and `sdd-spike-reentry.yml` utility workflows
   appear under `.github/workflows/` on the target repository. The
   `.lock.yml` reusable workflows are hosted in the spectacles repository
   and are not copied onto the consumer.
2. **Labels present.** Confirm the eight `sdd:*` lifecycle labels
   (`sdd:spec`, `sdd:fastpath`, `sdd:fastpath-review`, `sdd:triage`,
   `sdd:ready`, `sdd:in-progress`, `sdd:review`, `sdd:done`), the
   `sdd:dispatched` cascade marker, the `sdd:spike-resolved` marker, the
   `plan:provided` translation marker, the three `model:*` tier labels, the four
   `kind:*` labels (including `kind:spike`), the three `priority:*` labels, and
   `needs-human` all exist on the target repository.
   The full set is in "Labels installed" below.
3. **MCP reachable.** Dispatch `distillery-sync` once and confirm its run logs
   a non-zero count of ingested specs, decisions, issues, or pull requests.
   This proves the Distillery endpoint and OAuth credential resolve.
4. **Serena resolves.** Confirm a `sdd-spec` or `sdd-execute` run logs a
   non-empty Serena symbol query, or, on an unrecognised stack, logs the
   graceful text-level fallback. Either outcome is a pass; a hard failure is
   not. On a **Rust** consumer, the run's `Provision rust-analyzer for Serena`
   host step logs `Installed rust-analyzer at /tmp/gh-aw/serena/rust-analyzer`
   followed by its version, and the run no longer logs Serena's "Please install
   rust-analyzer" fallback — a `find_symbol` query resolves instead. (This
   live confirmation needs a real agent run on a Rust consumer; the host step's
   download and checksum are unit-verifiable, but the "Serena resolves a Rust
   symbol" check is an operator acceptance step, like the rest of this smoke
   test.)
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
