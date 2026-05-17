#!/usr/bin/env bash
# quick-setup.sh - install the spectacles agent contract onto a consumer repo.
#
# Unit 1 provided the skeleton: argument parsing and label sync. Unit 9 adds
# the --suite sdd option, which installs the full SDD agent suite (the sdd-*
# thin wrappers and their reusable workflows, the distillery-sync workflow, the
# sdd:* and model:* labels, and the issue templates) onto a target repo.
#
# Nothing in this script is org-specific. The GitHub App identity, the
# Distillery HTTP endpoint and OAuth credentials, and the Serena language-server
# set are configuration, resolved at install time from operator-supplied
# values; see docs/sdd/install.md. This script provisions placeholders and
# detects the target stack, but writes no private literal of its own.
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: quick-setup.sh --target-repo <owner>/<name> [--suite sdd] [--dry-run]

Options:
  --target-repo  Repository to install into (required).
  --suite sdd    Install the full SDD agent suite (wrappers, reusable
                 workflows, distillery-sync, sdd:* and model:* labels, and
                 the issue templates). Without this flag only the base
                 labels are synced.
  --dry-run      Print planned actions without applying them.
  -h, --help     Show this help.
USAGE
}

target_repo=""
suite=""
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
workflows_dir="$repo_root/.github/workflows"
templates_dir="$repo_root/templates/.github/ISSUE_TEMPLATE"

echo "quick-setup: target repo: $target_repo"
if [ -n "$suite" ]; then
  echo "quick-setup: suite: $suite"
fi
if [ "$dry_run" -eq 1 ]; then
  echo "quick-setup: dry-run; no changes will be applied."
fi

# The seven sdd-* agents. Each has a thin wrapper in wrappers/ and an adjacent
# reusable workflow (sdd-<agent>.lock.yml) in .github/workflows/. sdd-execute
# ships in three model-tier variants. See workflows/README.md for the
# distribution model.
sdd_agents=(
  "sdd-spec"
  "sdd-triage"
  "sdd-execute-haiku"
  "sdd-execute-sonnet"
  "sdd-execute-opus"
  "sdd-validate"
  "sdd-review"
)

# distillery-sync is a scheduled gh-aw workflow, not a workflow_call reusable
# workflow, so it has no thin wrapper: the installer copies its compiled lock
# file directly.
standalone_workflows=(
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

# Install the sdd-* thin wrappers and their adjacent reusable workflows.
install_sdd_workflows() {
  echo "quick-setup: installing the sdd-* agent suite."
  local agent
  for agent in "${sdd_agents[@]}"; do
    install_file "$wrappers_dir/$agent.yml" \
      ".github/workflows/$agent.yml" \
      "chore: install $agent wrapper (spectacles quick-setup)"
    install_file "$workflows_dir/$agent.lock.yml" \
      ".github/workflows/$agent.lock.yml" \
      "chore: install $agent reusable workflow (spectacles quick-setup)"
  done
  local wf
  for wf in "${standalone_workflows[@]}"; do
    install_file "$workflows_dir/$wf.lock.yml" \
      ".github/workflows/$wf.lock.yml" \
      "chore: install $wf workflow (spectacles quick-setup)"
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
  if [ "$dry_run" -eq 1 ]; then
    echo "quick-setup: would set variable SERENA_LANGUAGE_SERVERS=$server"
  else
    gh variable set SERENA_LANGUAGE_SERVERS \
      --repo "$target_repo" --body "$server"
    echo "quick-setup: set variable SERENA_LANGUAGE_SERVERS=$server"
  fi
}

# Provision the configuration the suite resolves at install time. The GitHub
# App identity, the Distillery endpoint and OAuth credentials, and the
# leak-scan denylist are operator-supplied; this records the names the suite
# expects so an operator fills them in. No value is hardcoded. See
# docs/sdd/install.md for the full table.
report_configuration() {
  echo "quick-setup: configuration the operator must supply on $target_repo:"
  echo "  variables (gh variable set <NAME> --repo $target_repo):"
  echo "    DISTILLERY_MCP_URL       Distillery HTTP MCP endpoint"
  echo "    DISTILLERY_PROJECT       Distillery project slug for this repo"
  echo "    SERENA_LANGUAGE_SERVERS  Serena language server set (auto-detected"
  echo "                             above when the stack is recognised)"
  echo "  secrets (gh secret set <NAME> --repo $target_repo):"
  echo "    COPILOT_GITHUB_TOKEN     token for the Copilot engine"
  echo "    GH_AW_GITHUB_TOKEN       GitHub App installation token (agent"
  echo "                             write identity; App ID and private key"
  echo "                             configured per docs/sdd/install.md)"
  echo "    DISTILLERY_OAUTH_TOKEN   Distillery OAuth bearer token"
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
  report_configuration
  echo "quick-setup: --suite sdd install complete."
  echo "quick-setup: next, supply the configuration listed above, then run"
  echo "             the smoke test in docs/sdd/install.md."
else
  echo "quick-setup: base labels synced. Pass --suite sdd to install the"
  echo "             full SDD agent suite."
fi
