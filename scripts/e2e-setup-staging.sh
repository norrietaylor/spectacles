#!/usr/bin/env bash
# e2e-setup-staging.sh — one-time provisioning of the E2E staging repo.
#
# The e2e-dispatch workflow (.github/workflows/e2e-dispatch.yml) drives a
# synthetic feature through the full SDD lifecycle on a dedicated staging repo.
# That repo must exist, carry the SDD wrappers and labels, have its default
# branch unprotected (so the agents and the dispatcher can write directly), and
# hold the secrets and variables the agents need. This script provisions all of
# that. It is documented and run by an operator once per staging repo; CI never
# runs it.
#
# It is intentionally idempotent: re-running it re-syncs the wrappers and
# re-applies the variables without error.
#
# Manual prerequisite this script cannot do for you: install the GitHub App
# (the one whose APP_ID/APP_PRIVATE_KEY the suite uses) on the staging repo.
# The script prints a checklist of the manual steps at the end.

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: e2e-setup-staging.sh --staging <owner>/<name> [--ref <ref>] [--dry-run]

  --staging <owner>/<name>  The dedicated E2E staging repository.
  --ref <ref>               spectacles ref the staging wrappers pin to. The
                            dispatcher re-pins this per run to the PR head SHA;
                            this initial value only seeds the install
                            (default: main).
  --dry-run                 Print what would happen; make no changes.

Required environment (for the non-dry-run path):
  STAGING_APP_PRIVATE_KEY   PEM private key for the suite's GitHub App.
  ANTHROPIC_API_KEY         Model key the sdd-* agents authenticate with.
  OTLP_*                    OTLP endpoint + headers per the ADR 0020 OTEL
                            mandate (passed through to the agents' wrapper
                            secret map). Optional if telemetry is disabled.
EOF
}

staging=""
ref="main"
dry_run=0

while [ $# -gt 0 ]; do
  case "$1" in
    --staging)
      [ $# -ge 2 ] || { echo "error: --staging needs a value" >&2; exit 2; }
      staging="$2"; shift 2 ;;
    --ref)
      [ $# -ge 2 ] || { echo "error: --ref needs a value" >&2; exit 2; }
      ref="$2"; shift 2 ;;
    --dry-run)
      dry_run=1; shift ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "error: unknown argument: $1" >&2; usage; exit 2 ;;
  esac
done

if [ -z "$staging" ]; then
  echo "error: --staging is required" >&2
  usage
  exit 2
fi

repo_root="$(cd "$(dirname "$0")/.." && pwd)"

run() {
  if [ "$dry_run" -eq 1 ]; then
    echo "DRY-RUN: $*"
  else
    "$@"
  fi
}

echo "e2e-setup-staging: provisioning $staging (ref=$ref, dry_run=$dry_run)"

# 1. Verify the staging repo exists and is reachable.
if ! gh repo view "$staging" >/dev/null 2>&1; then
  echo "error: cannot reach $staging. Create it first (gh repo create $staging --private)." >&2
  exit 1
fi

# 2. Turn off branch protection on the default branch. The staging repo is a
#    throwaway target; the dispatcher and agents write directly to its default
#    branch, so protection would block them. Ignore a 404 (no protection set).
default_branch="$(gh repo view "$staging" --json defaultBranchRef --jq '.defaultBranchRef.name')"
echo "e2e-setup-staging: clearing branch protection on $staging@$default_branch"
if [ "$dry_run" -eq 1 ]; then
  echo "DRY-RUN: gh api -X DELETE repos/$staging/branches/$default_branch/protection"
else
  gh api -X DELETE "repos/$staging/branches/$default_branch/protection" >/dev/null 2>&1 \
    || echo "e2e-setup-staging: no branch protection to clear (ok)"
fi

# 3. Install the SDD suite (wrappers + labels + templates) onto the staging
#    repo via quick-setup, writing straight to the default branch (--direct,
#    safe because protection is now off).
echo "e2e-setup-staging: installing SDD suite via quick-setup"
run bash "$repo_root/scripts/quick-setup.sh" \
  --target-repo "$staging" --suite sdd --ref "$ref" --direct

# 4. Repo variables the dispatcher and agents read.
echo "e2e-setup-staging: setting repository variables"
run gh variable set SPECTACLES_E2E_STAGING_REPO --repo "$staging" --body "$staging"

# 5. Secrets. Set only those present in the environment; warn on the rest.
set_secret() {
  local name="$1" value="$2"
  if [ -z "$value" ]; then
    echo "e2e-setup-staging: WARNING $name not in environment; set it manually"
    return
  fi
  run gh secret set "$name" --repo "$staging" --body "$value"
}
echo "e2e-setup-staging: setting secrets from the environment"
set_secret APP_PRIVATE_KEY "${STAGING_APP_PRIVATE_KEY:-}"
set_secret ANTHROPIC_API_KEY "${ANTHROPIC_API_KEY:-}"

cat <<EOF

e2e-setup-staging: done.

Manual steps this script cannot perform:
  1. Install the suite's GitHub App on $staging (Settings -> GitHub Apps).
  2. Set APP_ID as a repository variable on $staging if it differs from the
     org default:  gh variable set APP_ID --repo $staging --body <app-id>
  3. Set the OTLP_* telemetry secrets per the ADR 0020 OTEL mandate if the
     agents emit traces from this repo.
  4. On the spectacles repo, set the dispatcher's variables:
       SPECTACLES_E2E_STAGING_REPO = $staging
       (optional) SPECTACLES_E2E_TIMEOUT_MIN, SPECTACLES_E2E_DISABLED
EOF
