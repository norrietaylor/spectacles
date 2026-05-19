# Distribution model: hosted reusable workflows and thin wrappers

This document describes how the spectacles SDD suite is distributed onto a
consumer repository. It is the reference for the `--suite sdd` install path of
`scripts/quick-setup.sh`, for requirement R9.1 of spec 01, and for ADR 0004.

## Two layers

Every agent — the seven `sdd-*` agents and `distillery-sync` — ships as two
layers.

1. **A hosted reusable workflow.** The agent is a gh-aw source file at
   `.github/workflows/<agent>.md` whose frontmatter declares
   `on: workflow_call`. `gh aw compile` turns that source into the adjacent
   `.github/workflows/<agent>.lock.yml`. The `.lock.yml` is the reusable
   workflow: it carries the agent's prompt, its MCP server declarations, its
   safe-output configuration, and a `workflow_call` trigger. Both the `.md`
   source and the generated `.lock.yml` are committed to the spectacles
   repository; the `.lock.yml` is never hand-edited (ADR 0002). Each source
   sets `inlined-imports: true` and `strict: false`, so the lock is
   self-contained and safe to invoke cross-repo (ADR 0004).

2. **A thin wrapper.** A hand-written GitHub Actions workflow at
   `wrappers/<agent>.yml`. The wrapper carries the real event triggers
   (`issues`, `issue_comment`, `pull_request`, `schedule`, `workflow_dispatch`),
   routes the triggering event to an `aw_context` value where the agent needs
   one, gates comment commands to authors with repository write access, and
   then calls the hosted reusable workflow:

   ```yaml
   uses: norrietaylor/spectacles/.github/workflows/<agent>.lock.yml@<ref>
   ```

   The wrapper is the only file a consumer repository installs for an agent.

The split exists because gh-aw owns the `.lock.yml`: regenerating it on a
recompile would discard any hand-authored trigger or gate. Keeping triggers
and permission gates in a separate hand-written wrapper means a recompile of
the agent never disturbs them, and a consumer reads and audits one small
wrapper instead of a large generated lock.

## Why hosted, not copied

The consumer does not carry the `.lock.yml`. It calls the copy hosted in the
spectacles repository by cross-repo `uses:`. This is the GitHub-native way to
distribute a reusable workflow, and it has three consequences:

- A consumer carries eight small, auditable wrappers — plus the
  `sdd-pr-sanitize` utility workflow — not ~700 KB of generated locks plus a
  vendored import cache.
- A suite update is a ref bump, not a re-install on every consumer.
- The compiled locks must be self-contained. A lock that resolves imports or
  re-checks itself at run time fails when called cross-repo, because that
  resolution targets the *caller* repository. `inlined-imports: true` embeds
  every import into the lock; `strict: false` omits the run-time lock-file
  check. See ADR 0004.

## Why a wrapper, not the gh-aw `command:` trigger

gh-aw has a `command:` (slash-command) trigger with a `roles:` gate. That
trigger is gh-aw frontmatter: it only takes effect when `gh aw compile`
processes a workflow. The wrappers are plain hand-written GitHub Actions
workflows, not gh-aw sources, so `gh aw compile` never sees them. Each wrapper
therefore performs its command gating explicitly, with a real repository
permission check (`repos.getCollaboratorPermissionLevel`), rather than relying
on the gh-aw `command:` trigger.

## The agents and their wrappers

| Agent | Hosted reusable workflow | Wrapper |
|---|---|---|
| `sdd-spec` | `.github/workflows/sdd-spec.lock.yml` | `wrappers/sdd-spec.yml` |
| `sdd-triage` | `.github/workflows/sdd-triage.lock.yml` | `wrappers/sdd-triage.yml` |
| `sdd-execute` (haiku) | `.github/workflows/sdd-execute-haiku.lock.yml` | `wrappers/sdd-execute-haiku.yml` |
| `sdd-execute` (sonnet) | `.github/workflows/sdd-execute-sonnet.lock.yml` | `wrappers/sdd-execute-sonnet.yml` |
| `sdd-execute` (opus) | `.github/workflows/sdd-execute-opus.lock.yml` | `wrappers/sdd-execute-opus.yml` |
| `sdd-validate` | `.github/workflows/sdd-validate.lock.yml` | `wrappers/sdd-validate.yml` |
| `sdd-review` | `.github/workflows/sdd-review.lock.yml` | `wrappers/sdd-review.yml` |
| `distillery-sync` | `.github/workflows/distillery-sync.lock.yml` | `wrappers/distillery-sync.yml` |

`sdd-execute` is authored once and compiled into three model-tier variants
that differ only in the engine model (haiku, sonnet, opus). Each variant is a
full reusable workflow with its own wrapper, so a task's `model:*` label
selects the variant that picks it up.

`distillery-sync` is the scheduled knowledge-store sync. Unlike the
event-driven `sdd-*` agents its wrapper carries a daily `schedule` rather than
issue and pull-request triggers, but it is distributed the same way: a hosted
reusable workflow fronted by a thin wrapper.

## What the installer places on a consumer repository

`scripts/quick-setup.sh --suite sdd` writes, under the consumer repository's
`.github/workflows/`, the eight thin wrappers listed in the table above and
the `sdd-pr-sanitize` utility workflow — and nothing else under that
directory. No `.lock.yml`, no agent `.md` source, and no `.github/aw/imports/`
tree is copied: the locks are hosted, and they are self-contained.

`sdd-pr-sanitize` is not an agent wrapper: it is a plain workflow that, on
every `spec/*` and `arch/*` pull request, rewrites a stray issue-closing
keyword in the body to `Refs` so a merge cannot auto-close the feature
tracking issue (ADR 0006).

The installer also syncs the `sdd:*` and `model:*` labels and installs the
issue templates. `--ref <ref>` pins the `uses:` lines in the installed
wrappers to a spectacles ref (default `main`); a release tag pins a consumer
to an immutable suite version. Run `scripts/quick-setup.sh --suite sdd
--dry-run` to see the full planned-writes list without applying anything.

## Configuration, not source edits

A consumer installs every wrapper unchanged except for the `--ref` pin the
installer applies. No wrapper carries an org slug, a bot name, a hostname, or
an absolute path. The GitHub App identity, the Distillery HTTP endpoint and
OAuth credentials, and the Serena language-server set are all configuration
resolved at install time from operator-supplied values. See
`docs/sdd/install.md` for the required variables and secrets.

## Verification

- `ls wrappers/` lists a `.yml` wrapper for each of the eight agents,
  including the three `sdd-execute` model-tier variants and `distillery-sync`.
- Each `wrappers/<agent>.yml` ends in a job with
  `uses: norrietaylor/spectacles/.github/workflows/<agent>.lock.yml@main`.
- Each `.github/workflows/<agent>.md` source declares `on: workflow_call` and
  sets `inlined-imports: true` and `strict: false`.
- Each `.github/workflows/<agent>.lock.yml` contains no `{{#runtime-import}}`
  directive and no "Check workflow lock file" step.
- `bash scripts/quick-setup.sh --target-repo <owner>/<name> --suite sdd
  --dry-run` lists the eight wrappers, the issue templates, and the `sdd:*`
  and `model:*` labels in its planned-writes output, lists no `.lock.yml`,
  and writes nothing.
