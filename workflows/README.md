# Distribution model: reusable workflows and thin wrappers

This document describes how the spectacles SDD suite is distributed onto a
consumer repository. It is the reference for the `--suite sdd` install path of
`scripts/quick-setup.sh` and for requirement R9.1 of spec 01.

## Two layers

Every `sdd-*` agent ships as two layers:

1. **A reusable workflow.** The agent itself is a gh-aw source file at
   `.github/workflows/sdd-<agent>.md` whose frontmatter declares
   `on: workflow_call`. `gh aw compile` turns that source into the adjacent
   `.github/workflows/sdd-<agent>.lock.yml`. The `.lock.yml` is the reusable
   workflow: it carries the agent's prompt, its MCP server declarations, its
   safe-output configuration, and a single `workflow_call` trigger with an
   `aw_context` input. Both the `.md` source and the generated `.lock.yml` are
   committed; the `.lock.yml` is never hand-edited (see ADR 0002).

2. **A thin wrapper.** A hand-written GitHub Actions workflow at
   `wrappers/sdd-<agent>.yml`. The wrapper carries the real event triggers
   (`issues`, `issue_comment`, `pull_request`, `schedule`, and so on), routes
   the triggering event to an `aw_context` value, gates comment commands to
   authors with repository write access, and then calls the reusable workflow
   with `uses: ./.github/workflows/sdd-<agent>.lock.yml`. The wrapper is what a
   consumer repository installs into its own `.github/workflows/` directory.

The split exists because gh-aw owns the `.lock.yml`: regenerating it on a
recompile would discard any hand-authored trigger or gate. Keeping triggers and
permission gates in a separate hand-written wrapper means a recompile of the
agent never disturbs them, and a consumer can read and audit the small wrapper
without reading the large generated lock file.

## Why a wrapper, not the gh-aw `command:` trigger

gh-aw has a `command:` (slash-command) trigger with a `roles:` gate. That
trigger is gh-aw frontmatter: it only takes effect when `gh aw compile`
processes a workflow. The wrappers are plain hand-written GitHub Actions
workflows, not gh-aw sources, so `gh aw compile` never sees them. Each wrapper
therefore performs its command gating explicitly, with a real repository
permission check (`repos.getCollaboratorPermissionLevel`), rather than relying
on the gh-aw `command:` trigger.

## The agents and their wrappers

| Agent | Reusable workflow | Wrapper |
|---|---|---|
| `sdd-spec` | `.github/workflows/sdd-spec.lock.yml` | `wrappers/sdd-spec.yml` |
| `sdd-triage` | `.github/workflows/sdd-triage.lock.yml` | `wrappers/sdd-triage.yml` |
| `sdd-execute` (haiku) | `.github/workflows/sdd-execute-haiku.lock.yml` | `wrappers/sdd-execute-haiku.yml` |
| `sdd-execute` (sonnet) | `.github/workflows/sdd-execute-sonnet.lock.yml` | `wrappers/sdd-execute-sonnet.yml` |
| `sdd-execute` (opus) | `.github/workflows/sdd-execute-opus.lock.yml` | `wrappers/sdd-execute-opus.yml` |
| `sdd-validate` | `.github/workflows/sdd-validate.lock.yml` | `wrappers/sdd-validate.yml` |
| `sdd-review` | `.github/workflows/sdd-review.lock.yml` | `wrappers/sdd-review.yml` |

`sdd-execute` is authored once and compiled into three model-tier variants that
differ only in the engine model (haiku, sonnet, opus). Each variant is a full
reusable workflow with its own wrapper, so a task's `model:*` label selects the
variant that picks it up.

## `distillery-sync` is not a wrapped agent

`distillery-sync` is a scheduled gh-aw workflow, not a `workflow_call` reusable
workflow: it triggers on a daily `schedule` and on `workflow_dispatch`. It has
no thin wrapper. The installer copies the compiled
`.github/workflows/distillery-sync.lock.yml` directly into the consumer
repository, where its own triggers fire it. It is part of the `--suite sdd`
install because the `sdd-*` agents depend on the knowledge store it keeps
current.

## What the installer places on a consumer repository

`scripts/quick-setup.sh --suite sdd` writes, under the consumer repository's
`.github/workflows/`:

- the seven `sdd-*` thin wrappers listed in the table above;
- the seven adjacent `sdd-*.lock.yml` reusable workflows the wrappers call;
- the `distillery-sync.lock.yml` scheduled workflow.

It also syncs the `sdd:*` and `model:*` labels and installs the issue
templates. Run `scripts/quick-setup.sh --suite sdd --dry-run` to see the full
planned-writes list without applying anything.

## Configuration, not source edits

A consumer installs every wrapper and lock file unchanged. No `sdd-*` source
carries an org slug, a bot name, a hostname, or an absolute path. The GitHub
App identity, the Distillery HTTP endpoint and OAuth credentials, and the
Serena language-server set are all configuration resolved at install time from
operator-supplied values. See `docs/sdd/install.md` for the required variables
and secrets.

## Verification

- `ls wrappers/` lists a `.yml` wrapper for each of the seven `sdd-*` agents,
  including the three `sdd-execute` model-tier variants.
- Each `wrappers/sdd-*.yml` ends in a job with
  `uses: ./.github/workflows/sdd-<agent>.lock.yml`.
- Each `.github/workflows/sdd-*.md` source declares `on: workflow_call` (or, in
  the compiled `.lock.yml`, a `workflow_call:` trigger).
- `bash scripts/quick-setup.sh --target-repo <owner>/<name> --suite sdd
  --dry-run` lists the `sdd-*` wrappers, the reusable workflows,
  `distillery-sync`, and the `sdd:*` and `model:*` labels in its planned-writes
  output, and writes nothing.
