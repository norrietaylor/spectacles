#!/usr/bin/env bash
# quick-setup.sh — install the spectacles agent contract onto a consumer repo.
#
# Unit 1 provides the skeleton: argument parsing and label sync. The
# `--suite sdd` agent-wrapper installation lands in Unit 9.
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: quick-setup.sh --target-repo <owner>/<name> [--dry-run]

Options:
  --target-repo  Repository to install into (required).
  --dry-run      Print planned actions without applying them.
  -h, --help     Show this help.
USAGE
}

target_repo=""
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

echo "quick-setup: target repo: $target_repo"
if [ "$dry_run" -eq 1 ]; then
  echo "quick-setup: dry-run; no changes will be applied."
fi

# Sync the base labels. labels.yml is a flat list of '- name:' records, so it
# is parsed line by line without a YAML dependency.
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

if [ ! -f "$labels_file" ]; then
  echo "error: labels file not found at $labels_file" >&2
  exit 1
fi
sync_labels

echo "quick-setup: label sync complete."
echo "quick-setup: the --suite sdd agent-wrapper install arrives with Unit 9."
