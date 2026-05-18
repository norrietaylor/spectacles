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
# --suite sdd therefore installs, onto the target repo: the eight thin
# wrappers (the seven sdd-* agents and distillery-sync), the sdd:* and model:*
# labels, and the issue templates. No .lock.yml, no agent .md source, and no
# .github/aw/imports tree is copied — the locks are self-contained (compiled
# with inlined-imports) and hosted, not vendored.
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
  --suite sdd    Install the full SDD agent suite: the eight thin wrappers
                 (the seven sdd-* agents and distillery-sync), the sdd:* and
                 model:* labels, and the issue templates. Without this flag
                 only the base labels are synced.
  --ref <ref>    The spectacles ref the installed wrappers pin their hosted
                 reusable workflows to. Default: main. Set this to a release
                 tag to pin a consumer to an immutable suite version.
  --dry-run      Print planned actions without applying them.
  -h, --help     Show this help.

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

# The eight thin wrappers the --suite sdd install places on a consumer repo.
# Each is a hand-written GitHub Actions workflow that carries the real event
# triggers and calls a hosted reusable workflow in the spectacles repository
# (see ADR 0004 and workflows/README.md). The seven sdd-* agents are
# event-driven; distillery-sync is scheduled. sdd-execute ships in three
# model-tier variants.
wrappers=(
  "sdd-spec"
  "sdd-triage"
  "sdd-execute-haiku"
  "sdd-execute-sonnet"
  "sdd-execute-opus"
  "sdd-validate"
  "sdd-review"
  "distillery-sync"
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
  local existing_sha=""
  existing_sha="$(gh api \
    "repos/$target_repo/contents/$dest" \
    --jq '.sha' 2>/dev/null || true)"
  local content
  content="$(base64 <"$src" | tr -d '\n')"
  if [ -n "$existing_sha" ]; then
    gh api --method PUT "repos/$target_repo/contents/$dest" \
      -f message="$message" \
      -f content="$content" \
      -f sha="$existing_sha" >/dev/null
  else
    gh api --method PUT "repos/$target_repo/contents/$dest" \
      -f message="$message" \
      -f content="$content" >/dev/null
  fi
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

# Install the eight thin wrappers. No .lock.yml, .md source, or imports tree is
# copied: under the ADR 0004 distribution model the wrappers call self-contained
# hosted reusable workflows by pinned ref.
install_sdd_workflows() {
  echo "quick-setup: installing the sdd-* agent suite wrappers (ref: $ref)."
  local agent
  for agent in "${wrappers[@]}"; do
    install_wrapper "$agent"
  done
}

# Install the feature, bug, and chore issue templates.
install_issue_templates() {
  echo "quick-setup: installing the issue templates."
  local tpl
  for tpl in feature bug chore; do
    install_file "$templates_dir/$tpl.md" \
      ".github/ISSUE_TEMPLATE/$tpl.md" \
      "chore: install $tpl issue template (spectacles quick-setup)"
  done
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
# GitHub App identity, the Copilot engine token, and the leak-scan denylist
# stay operator-supplied. See docs/sdd/install.md for the full table.
report_configuration() {
  echo "quick-setup: configuration the operator must supply on $target_repo:"
  echo "  variables (gh variable set <NAME> --repo $target_repo):"
  echo "    SERENA_LANGUAGE_SERVERS  Serena language server set (auto-detected"
  echo "                             above when the stack is recognised)"
  echo "  secrets (gh secret set <NAME> --repo $target_repo):"
  echo "    COPILOT_GITHUB_TOKEN     token for the Copilot engine"
  echo "    GH_AW_GITHUB_TOKEN       GitHub App installation token (agent"
  echo "                             write identity; App ID and private key"
  echo "                             configured per docs/sdd/install.md)"
  echo "    LEAK_DENYLIST            leak-scan denylist, one term per line"
}

if [ ! -f "$labels_file" ]; then
  echo "error: labels file not found at $labels_file" >&2
  exit 1
fi
sync_labels
echo "quick-setup: label sync complete."

if [ "$suite" = "sdd" ]; then
  install_sdd_workflows
  install_issue_templates
  detect_serena_language_server
  provision_distillery_config
  report_configuration
  echo "quick-setup: --suite sdd install complete."
  echo "quick-setup: next, supply the configuration listed above, then run"
  echo "             the smoke test in docs/sdd/install.md."
else
  echo "quick-setup: base labels synced. Pass --suite sdd to install the"
  echo "             full SDD agent suite."
fi
