#!/usr/bin/env bash
# quick-setup.sh - install the spectacles agent contract onto a consumer repo.
#
# Unit 1 provided the skeleton: argument parsing and label sync. Unit 9 added
# the --suite sdd option. ADR 0004 changed the distribution model: a consumer
# repository no longer carries the compiled .lock.yml workflows. Each agent is
# a hosted reusable workflow in the spectacles repository, and the consumer
# installs only the thin wrappers, which call those reusable workflows
# cross-repo with
# `uses: norrietaylor/spectacles/.github/workflows/<agent>.lock.yml@<ref>`.
#
# --suite sdd therefore installs, onto the target repo: the nine thin
# wrappers (the eight sdd-* agents and distillery-sync), the
# sdd-pr-sanitize, sdd-triage-dedupe-tasks, and sdd-triage-promote-ready
# utility workflows, the sdd:* and model:* labels, and the issue
# templates. No .lock.yml, no agent .md source, and no .github/aw/imports
# tree is copied — the locks are self-contained (compiled with
# inlined-imports) and hosted, not vendored.
#
# Nothing in this script is org-specific. The GitHub App identity, the
# Distillery HTTP endpoint and OAuth credentials, and the Serena language-server
# set are configuration, resolved at install time from operator-supplied
# values; see docs/sdd/install.md. This script writes no private literal of
# its own: the Distillery endpoint and token are read from the operator's
# environment (DISTILLERY_MCP_URL, DISTILLERY_OAUTH_TOKEN) and provisioned
# onto the target repo; DISTILLERY_PROJECT is derived from the repo name.
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: quick-setup.sh --target-repo <owner>/<name> [--suite sdd] [--ref <ref>] [--dry-run]

Options:
  --target-repo  Repository to install into (required).
  --suite sdd    Install the full SDD agent suite: the nine thin agent
                 wrappers (the eight sdd-* agents and distillery-sync), the
                 sdd-pr-sanitize, sdd-triage-dedupe-tasks, and
                 sdd-triage-promote-ready utility workflows, the sdd:*
                 and model:* labels, and the issue templates. Without
                 this flag only the base labels are synced.
  --ref <ref>    The spectacles ref the installed wrappers pin their hosted
                 reusable workflows to. Default: main. Set this to a release
                 tag to pin a consumer to an immutable suite version.
  --direct       Write file artifacts straight to the target's default branch
                 instead of opening an installer PR. Fails on a repo whose
                 default branch is protected; use only on unprotected repos.
  --dry-run      Print planned actions without applying them.
  -h, --help     Show this help.

By default the file artifacts (workflow wrappers, issue templates, .gitignore)
are written to a 'spectacles/install' branch and an installer PR is opened, so
a target repo with a protected default branch accepts the install. Labels,
variables, and secrets are not branch-scoped and apply directly in both modes.

With --suite sdd the installer also provisions the target repo's Distillery
configuration. DISTILLERY_PROJECT is set to the repo name. DISTILLERY_MCP_URL
and the DISTILLERY_OAUTH_TOKEN secret are read from the environment of this
script when set:

  DISTILLERY_MCP_URL=https://host/mcp DISTILLERY_OAUTH_TOKEN=<token> \
    quick-setup.sh --target-repo <owner>/<name> --suite sdd

Either one absent is not an error — the installer reports what to set by hand.
USAGE
}

target_repo=""
suite=""
ref="main"
dry_run=0
# PR mode is the default: file artifacts (workflows, issue templates,
# .gitignore) land on a branch and an installer PR is opened, so a target
# repo with a protected default branch accepts the install. --direct restores
# the legacy behavior of writing straight to the default branch. Labels,
# variables, and secrets are never branch-scoped and apply directly in both
# modes.
direct=0
install_branch="spectacles/install"
pr_base=""
while [ $# -gt 0 ]; do
  case "$1" in
    --target-repo)
      if [ $# -lt 2 ]; then
        echo "error: --target-repo needs a value" >&2
        exit 2
      fi
      target_repo="$2"
      shift 2
      ;;
    --suite)
      if [ $# -lt 2 ]; then
        echo "error: --suite needs a value" >&2
        exit 2
      fi
      suite="$2"
      if [ "$suite" != "sdd" ]; then
        echo "error: --suite only supports 'sdd'" >&2
        exit 2
      fi
      shift 2
      ;;
    --ref)
      if [ $# -lt 2 ]; then
        echo "error: --ref needs a value" >&2
        exit 2
      fi
      ref="$2"
      shift 2
      ;;
    --dry-run)
      dry_run=1
      shift
      ;;
    --direct)
      direct=1
      shift
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [ -z "$target_repo" ]; then
  echo "error: --target-repo is required" >&2
  usage >&2
  exit 2
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
labels_file="$repo_root/templates/.github/labels.yml"
wrappers_dir="$repo_root/wrappers"
templates_dir="$repo_root/templates/.github/ISSUE_TEMPLATE"

echo "quick-setup: target repo: $target_repo"
if [ -n "$suite" ]; then
  echo "quick-setup: suite: $suite"
  echo "quick-setup: pinned ref: $ref"
fi
if [ "$dry_run" -eq 1 ]; then
  echo "quick-setup: dry-run; no changes will be applied."
fi

# The hand-written workflows the --suite sdd install places on a consumer
# repo. The first nine are the thin agent wrappers: each carries the real
# event triggers and calls a hosted reusable workflow in the spectacles
# repository (see ADR 0004 and workflows/README.md). The eight sdd-* agents
# are event-driven; distillery-sync is scheduled; sdd-execute ships in three
# model-tier variants. sdd-dispatch is the cascade orchestrator added in
# ADR 0011: /dispatch on a tracking issue arms event-driven matrix fan-out
# of sdd-execute runs, replacing the daily cron the variants previously
# ran on. sdd-pr-sanitize and sdd-triage-dedupe-tasks are utility
# workflows, not agent wrappers: sdd-pr-sanitize neutralizes a stray
# issue-closing keyword in a spec or architecture pull request body so a
# merge cannot auto-close the feature tracking issue (ADR 0006), and
# sdd-triage-dedupe-tasks closes a phase-C task sub-issue when an
# earlier-numbered sibling under the same Unit already carries the same
# title (ADR 0008). sdd-triage-promote-ready applies `sdd:ready` to a
# task when its last `blocked by` blocker closes (ADR 0013), closing
# the gap ADR 0009 names as out-of-scope. sdd-monitor is a scheduled
# backstop that nudges an armed-but-idle `sdd:dispatched` tracker with a
# `/dispatch` when the close-driven cascade stalls (issue #148 Tier 1); it
# is disabled by default behind the SDD_MONITOR repo variable, so a
# consumer that has not opted in carries the wrapper but pays no cost.
wrappers=(
  "sdd-spec"
  "sdd-triage"
  "sdd-dispatch"
  "sdd-execute-haiku"
  "sdd-execute-sonnet"
  "sdd-execute-opus"
  "sdd-validate"
  "sdd-review"
  "distillery-sync"
  "sdd-pr-sanitize"
  "sdd-triage-dedupe-tasks"
  "sdd-triage-promote-ready"
  "sdd-monitor"
)

# Sync the labels. labels.yml is a flat list of '- name:' records, so it is
# parsed line by line without a YAML dependency. With --suite sdd this syncs
# the full set, which includes the base, sdd:*, and model:* labels.
sync_labels() {
  local name="" color="" desc=""
  while IFS= read -r line; do
    case "$line" in
      "- name: "*)
        name="${line#- name: }"
        ;;
      "  color: "*)
        color="${line#  color: }"
        ;;
      "  description: "*)
        desc="${line#  description: }"
        if [ "$dry_run" -eq 1 ]; then
          echo "quick-setup: would sync label '$name' ($color)"
        else
          gh label create "$name" --repo "$target_repo" \
            --color "$color" --description "$desc" --force
        fi
        name=""
        color=""
        desc=""
        ;;
    esac
  done <"$labels_file"
}

# Install one file into the target repo's tree via the GitHub Contents API.
# In dry-run it only reports the planned write. dest is a repo-relative path.
install_file() {
  local src="$1" dest="$2" message="$3"
  if [ ! -f "$src" ]; then
    echo "error: source file not found: $src" >&2
    exit 1
  fi
  if [ "$dry_run" -eq 1 ]; then
    echo "quick-setup: would write $dest"
    return 0
  fi
  # In PR mode reads and writes are scoped to the install branch; in --direct
  # mode install_branch is empty and the calls target the default branch.
  local read_path="repos/$target_repo/contents/$dest"
  if [ -n "$install_branch" ]; then
    read_path="$read_path?ref=$install_branch"
  fi
  local existing_sha=""
  existing_sha="$(gh api "$read_path" --jq '.sha' 2>/dev/null || true)"
  local content
  content="$(base64 <"$src" | tr -d '\n')"
  local args=(--method PUT "repos/$target_repo/contents/$dest"
    -f message="$message" -f content="$content")
  [ -n "$existing_sha" ] && args+=(-f sha="$existing_sha")
  [ -n "$install_branch" ] && args+=(-f branch="$install_branch")
  gh api "${args[@]}" >/dev/null
  echo "quick-setup: wrote $dest"
}

# Install one thin wrapper onto the target repo. The wrappers in wrappers/ pin
# their hosted reusable workflows to @main; this rewrites that ref to --ref
# before the wrapper is written, so a consumer can be pinned to a release tag
# without the wrapper sources carrying a per-consumer literal. When --ref is
# its default (main) the rewrite is a no-op.
install_wrapper() {
  local agent="$1"
  local src="$wrappers_dir/$agent.yml"
  if [ ! -f "$src" ]; then
    echo "error: wrapper not found: $src" >&2
    exit 1
  fi
  local rendered
  rendered="$(mktemp)"
  sed -E \
    "s|(uses: norrietaylor/spectacles/\.github/workflows/[A-Za-z0-9_-]+\.lock\.yml)@[^[:space:]]+|\1@${ref}|" \
    "$src" >"$rendered"
  install_file "$rendered" ".github/workflows/$agent.yml" \
    "chore: install $agent wrapper (spectacles quick-setup)"
  rm -f "$rendered"
}

# Install the consumer workflows: the nine thin agent wrappers and the
# sdd-pr-sanitize and sdd-triage-dedupe-tasks utility workflows. No .lock.yml,
# .md source, or imports tree is copied: under the ADR 0004 distribution
# model the wrappers call self-contained hosted reusable workflows by pinned
# ref.
install_sdd_workflows() {
  echo "quick-setup: installing the sdd-* agent suite wrappers (ref: $ref)."
  local agent
  for agent in "${wrappers[@]}"; do
    install_wrapper "$agent"
  done
}

# Install the feature, bug, chore, and spec issue templates.
install_issue_templates() {
  echo "quick-setup: installing the issue templates."
  local tpl
  for tpl in feature bug chore spec; do
    install_file "$templates_dir/$tpl.md" \
      ".github/ISSUE_TEMPLATE/$tpl.md" \
      "chore: install $tpl issue template (spectacles quick-setup)"
  done
}

# Ensure the target repository's .gitignore excludes Serena's working-tree
# state directory. Serena's `activate_project` writes `.serena/.gitignore` and
# `.serena/project.yml` into the project root by design — that state is
# Serena's view of the project, not a project artifact. Without an ignore
# entry those files become dirty paths in the working tree, the
# `create_pull_request` safe-output sweeps them into the patch, and gh-aw's
# `protect_top_level_dot_folders: true` rejects the whole PR (issue #65).
#
# The fix is structural: teach git to ignore `.serena/` on the consumer repo,
# and the safe-output's "what is dirty in the working tree" question becomes
# blind to it. This runs at install time so every freshly provisioned consumer
# carries the entry from the start, and re-running quick-setup on an existing
# consumer back-fills the entry idempotently. It does not clobber: it only
# appends when the line is absent. When no .gitignore exists yet, it creates a
# minimal one carrying only the spectacles entry.
ensure_serena_gitignore() {
  echo "quick-setup: ensuring .gitignore excludes Serena's .serena/ state."
  local dest=".gitignore"
  local marker=".serena/"
  if [ "$dry_run" -eq 1 ]; then
    echo "quick-setup: dry-run; would ensure $dest contains '$marker'."
    return 0
  fi
  local existing_sha="" existing_b64="" existing=""
  # In PR mode read from the install branch; --direct reads the default branch.
  local read_path="repos/$target_repo/contents/$dest"
  if [ -n "$install_branch" ]; then
    read_path="$read_path?ref=$install_branch"
  fi
  # Read the current .gitignore, if any. A 404 yields an empty sha and we fall
  # through to the create path. `gh api` exits non-zero on 404; the `|| true`
  # suppresses that so the script's `set -e` does not trip.
  existing_sha="$(gh api "$read_path" --jq '.sha' 2>/dev/null || true)"
  if [ -n "$existing_sha" ]; then
    existing_b64="$(gh api "$read_path" --jq '.content' 2>/dev/null || true)"
    if [ -n "$existing_b64" ]; then
      # GitHub returns Contents API bodies as base64 with embedded newlines.
      existing="$(printf '%s' "$existing_b64" | tr -d '\n' | base64 -d)"
    fi
  fi
  # Idempotent: skip when the line is already present as a whole-line match.
  if printf '%s\n' "$existing" | grep -Fxq "$marker"; then
    echo "quick-setup: .gitignore already excludes $marker; no change."
    return 0
  fi
  local block
  # The blank line and header keep the appended block readable when it lands
  # next to existing entries. When .gitignore is empty or absent, the leading
  # blank line is harmless.
  block=$'\n# Serena MCP working-tree state (spectacles quick-setup).\n'
  block+=$'.serena/\n'
  local updated
  if [ -n "$existing" ]; then
    updated="${existing}${block}"
  else
    # Strip the leading blank line for a fresh file so the first line is the
    # header comment.
    updated="${block#$'\n'}"
  fi
  local content
  content="$(printf '%s' "$updated" | base64 | tr -d '\n')"
  local message="chore: ignore Serena .serena/ state (spectacles quick-setup)"
  local args=(--method PUT "repos/$target_repo/contents/$dest"
    -f message="$message" -f content="$content")
  [ -n "$install_branch" ] && args+=(-f branch="$install_branch")
  if [ -n "$existing_sha" ]; then
    gh api "${args[@]}" -f sha="$existing_sha" >/dev/null
    echo "quick-setup: appended $marker to existing $dest."
  else
    gh api "${args[@]}" >/dev/null
    echo "quick-setup: created $dest with $marker."
  fi
}

# Detect the target repository's primary stack from the languages GitHub
# reports, and name the Serena language server that matches it. When no
# language server is known for the stack, the suite degrades gracefully to
# text-level reading (see shared/sdd-mcp-serena.md); this only records the
# fact, it never fails the install.
detect_serena_language_server() {
  echo "quick-setup: detecting the target repository stack for Serena."
  if [ "$dry_run" -eq 1 ]; then
    echo "quick-setup: dry-run; would query repos/$target_repo/languages and"
    echo "             set SERENA_LANGUAGE_SERVERS to the matching server."
    return 0
  fi
  local langs="" primary=""
  # --jq with a non-200 body produces no key list, so a failed call yields an
  # empty string rather than a raw JSON error body.
  langs="$(gh api "repos/$target_repo/languages" \
    --jq 'keys | join(",")' 2>/dev/null || true)"
  if [ -z "$langs" ]; then
    echo "quick-setup: could not read repository languages."
    echo "quick-setup: Serena will degrade to text-level reading; set the"
    echo "             SERENA_LANGUAGE_SERVERS variable by hand if needed."
    return 0
  fi
  primary="$(gh api "repos/$target_repo/languages" \
    --jq 'to_entries | sort_by(-.value) | .[0].key' 2>/dev/null || true)"
  echo "quick-setup: target languages: $langs"
  local server=""
  case "$primary" in
    Python) server="pyright" ;;
    TypeScript | JavaScript) server="typescript-language-server" ;;
    Go) server="gopls" ;;
    Rust) server="rust-analyzer" ;;
    Java) server="jdtls" ;;
    "C#") server="omnisharp" ;;
    Ruby) server="solargraph" ;;
    *) server="" ;;
  esac
  if [ -z "$server" ]; then
    echo "quick-setup: no known Serena language server for '$primary'."
    echo "quick-setup: the agents will degrade gracefully to text-level"
    echo "             reading; no language server is provisioned."
    return 0
  fi
  echo "quick-setup: matched Serena language server: $server"
  gh variable set SERENA_LANGUAGE_SERVERS \
    --repo "$target_repo" --body "$server"
  echo "quick-setup: set variable SERENA_LANGUAGE_SERVERS=$server"
}

# Provision the target repo's Distillery configuration. DISTILLERY_PROJECT is
# always the target repository's name. DISTILLERY_MCP_URL and the
# DISTILLERY_OAUTH_TOKEN secret are operator-supplied: they are read from this
# script's own environment so the token never appears in argv. When either is
# absent the install does not fail — it reports what to set by hand, matching
# the graceful-degradation style of the Serena step.
provision_distillery_config() {
  local project="${target_repo##*/}"
  if [ "$dry_run" -eq 1 ]; then
    echo "quick-setup: would set variable DISTILLERY_PROJECT=$project"
  else
    gh variable set DISTILLERY_PROJECT --repo "$target_repo" --body "$project"
    echo "quick-setup: set variable DISTILLERY_PROJECT=$project"
  fi

  if [ -n "${DISTILLERY_MCP_URL:-}" ]; then
    if [ "$dry_run" -eq 1 ]; then
      echo "quick-setup: would set variable DISTILLERY_MCP_URL (from environment)"
    else
      gh variable set DISTILLERY_MCP_URL --repo "$target_repo" --body "$DISTILLERY_MCP_URL"
      echo "quick-setup: set variable DISTILLERY_MCP_URL"
    fi
  else
    echo "quick-setup: DISTILLERY_MCP_URL not in environment — set it by hand:"
    echo "             gh variable set DISTILLERY_MCP_URL --repo $target_repo --body <url>"
  fi

  if [ -n "${DISTILLERY_OAUTH_TOKEN:-}" ]; then
    if [ "$dry_run" -eq 1 ]; then
      echo "quick-setup: would set secret DISTILLERY_OAUTH_TOKEN (from environment)"
    else
      printf '%s' "$DISTILLERY_OAUTH_TOKEN" \
        | gh secret set DISTILLERY_OAUTH_TOKEN --repo "$target_repo"
      echo "quick-setup: set secret DISTILLERY_OAUTH_TOKEN"
    fi
  else
    echo "quick-setup: DISTILLERY_OAUTH_TOKEN not in environment — set it by hand:"
    echo "             gh secret set DISTILLERY_OAUTH_TOKEN --repo $target_repo"
  fi
}

# Report the remaining configuration the operator must supply by hand. The
# Distillery values are provisioned by provision_distillery_config above; the
# GitHub App identity and the Copilot engine token stay operator-supplied.
# LEAK_DENYLIST is not reported: no installed workflow consumes it — it gates
# only the spectacles repository's own leak-scan CI, which is not installed
# onto a consumer. See docs/sdd/install.md for the full table.
report_configuration() {
  echo "quick-setup: configuration the operator must supply on $target_repo:"
  echo "  variables (gh variable set <NAME> --repo $target_repo):"
  echo "    SERENA_LANGUAGE_SERVERS    Serena language server set (auto-detected"
  echo "                               above when the stack is recognised)"
  echo "    APP_ID                     ID of the GitHub App that is the agents'"
  echo "                               write identity"
  echo "    SDD_DISPATCH_MAX_PARALLEL  optional matrix parallelism cap for"
  echo "                               sdd-dispatch's fan-out to sdd-execute"
  echo "                               runs. Default 5; any positive integer."
  echo "                               Lower it to stay under CI billing caps,"
  echo "                               raise it on a repo with capacity for"
  echo "                               more concurrent runs."
  echo "    GH_AW_MODEL_AGENT_COPILOT  optional Copilot model override for the"
  echo "                               agents. Unset uses the compiled default"
  echo "                               (claude-sonnet-4.6)."
  echo "    GH_AW_MODEL_DETECTION_COPILOT  optional Copilot model override for"
  echo "                               the detection step. Unset uses the"
  echo "                               compiled default (claude-sonnet-4.6)."
  echo "  secrets (gh secret set <NAME> --repo $target_repo):"
  echo "    COPILOT_GITHUB_TOKEN       token for the Copilot engine"
  echo "    APP_PRIVATE_KEY            private key (PEM) of the GitHub App;"
  echo "                               each agent run mints its own token"
  echo "                               from it"
}

# Create the install branch off the target repo's default branch so the file
# writes that follow target a branch, not the protected default. Records the
# default branch in pr_base for open_install_pr. Idempotent: an existing branch
# is reused, so re-running quick-setup updates the same install PR. In --direct
# mode this is never called and install_branch stays empty.
ensure_install_branch() {
  pr_base="$(gh repo view "$target_repo" --json defaultBranchRef \
    --jq '.defaultBranchRef.name')"
  if [ "$dry_run" -eq 1 ]; then
    echo "quick-setup: dry-run; would create branch '$install_branch' off"
    echo "             '$pr_base' and write the suite onto it."
    return 0
  fi
  if gh api "repos/$target_repo/git/refs/heads/$install_branch" \
    >/dev/null 2>&1; then
    echo "quick-setup: reusing existing branch '$install_branch'."
  else
    local base_sha
    base_sha="$(gh api "repos/$target_repo/git/refs/heads/$pr_base" \
      --jq '.object.sha')"
    gh api --method POST "repos/$target_repo/git/refs" \
      -f ref="refs/heads/$install_branch" -f sha="$base_sha" >/dev/null
    echo "quick-setup: created branch '$install_branch' off '$pr_base'."
  fi
}

# Open the installer pull request from the install branch onto the default
# branch. Idempotent: when a PR for the branch is already open it is reported,
# not duplicated. In --direct mode this is never called.
open_install_pr() {
  if [ "$dry_run" -eq 1 ]; then
    echo "quick-setup: dry-run; would open a PR from '$install_branch' into"
    echo "             '$pr_base'."
    return 0
  fi
  local existing
  existing="$(gh pr list --repo "$target_repo" --head "$install_branch" \
    --state open --json url --jq '.[0].url' 2>/dev/null || true)"
  if [ -n "$existing" ]; then
    echo "quick-setup: install PR already open: $existing"
    return 0
  fi
  local url
  url="$(gh pr create --repo "$target_repo" --base "$pr_base" \
    --head "$install_branch" \
    --title "Install spectacles SDD suite (ref: $ref)" \
    --body "Installs the spectacles SDD agent suite (ADR 0004) via \`scripts/quick-setup.sh\`. Wrappers pin hosted reusable workflows at \`@$ref\`. Labels, variables, and secrets were applied directly; the file artifacts in this PR honor the protected default branch. Merge to activate the workflows.")"
  echo "quick-setup: opened install PR: $url"
}

if [ ! -f "$labels_file" ]; then
  echo "error: labels file not found at $labels_file" >&2
  exit 1
fi
sync_labels
echo "quick-setup: label sync complete."

if [ "$suite" = "sdd" ]; then
  # PR mode (default): scope the file writes to an install branch and open a
  # PR. --direct clears install_branch so the writes hit the default branch.
  if [ "$direct" -eq 1 ]; then
    install_branch=""
  else
    ensure_install_branch
  fi
  install_sdd_workflows
  install_issue_templates
  ensure_serena_gitignore
  detect_serena_language_server
  provision_distillery_config
  report_configuration
  if [ "$direct" -ne 1 ]; then
    open_install_pr
  fi
  echo "quick-setup: --suite sdd install complete."
  echo "quick-setup: next, supply the configuration listed above, then run"
  echo "             the smoke test in docs/sdd/install.md."
else
  echo "quick-setup: base labels synced. Pass --suite sdd to install the"
  echo "             full SDD agent suite."
fi
