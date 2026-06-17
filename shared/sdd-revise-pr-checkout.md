---
# Host-side PR-branch checkout, pre-agent, for the /revise path.
#
# A /revise comment fires the workflow on an issue_comment event whose
# AW_CONTEXT carries item_type=pull_request. gh-aw's default agent checkout for
# a comment event is the repository default branch (main) with
# persist-credentials: false. Two failures follow when the agent then emits
# push_to_pull_request_branch:
#   1. The agent's commit is based on main, not the PR head — a divergent base.
#   2. The host-side safeoutputs push handler builds an incremental patch by
#      diffing against origin/<pr-head>. That ref is absent (main-only,
#      fetch-depth 1), so it runs a live `git fetch origin/<pr-head>` — which,
#      with the checkout credentials stripped, fails:
#        fatal: could not read Username for 'https://github.com'
#      The handler returns an error, the agent never records a push output, the
#      safe_outputs push job is skipped, and the revision is lost. The run still
#      reports success (the agent falls back to report_incomplete). First seen
#      on a consumer pilot run (sdd-triage, /revise on an arch PR).
#
# This pre-agent step runs on the host runner in the repo workspace, before the
# agent container starts. On a pull_request-typed trigger it re-authenticates
# origin, fetches the PR head ref, and checks it out so:
#   - the agent commits on top of the real PR tip, and
#   - origin/<pr-head> is present locally, so the push handler reads the base
#     from the existing tracking ref instead of attempting a live fetch.
# The token is stripped from the remote URL again after the fetch so the agent
# container never sees it (preserving the intent of persist-credentials: false).
# A non-PR trigger (issue) is a no-op. Every failure is best-effort and exits 0
# so a resolution miss never blocks the run.
#
# Imported by the workflows that declare push-to-pull-request-branch
# (sdd-triage-arch, sdd-execute-{haiku,sonnet,opus}, sdd-derive, sdd-review)
# via the pinned-ref form `norrietaylor/spectacles/shared/sdd-revise-pr-checkout.md@<ref>`
# (ADR 0002). Editing it requires `gh aw compile` to propagate into the inlined
# locks; the lint workflow's drift gate enforces that.
pre-agent-steps:
  - name: Check out the PR head branch for /revise
    shell: bash
    env:
      GH_TOKEN: ${{ github.token }}
      AW_CONTEXT: ${{ inputs.aw_context }}
      GITHUB_REPOSITORY: ${{ github.repository }}
      GITHUB_SERVER_URL: ${{ github.server_url }}
    run: |
      set -uo pipefail
      skip() { echo "pr-checkout: $1; skipping" >&2; exit 0; }
      command -v gh >/dev/null 2>&1 || skip "no gh"
      command -v jq >/dev/null 2>&1 || skip "no jq"
      ctx="${AW_CONTEXT:-}"
      item_type="$(printf '%s' "$ctx" | jq -r '.item_type // empty' 2>/dev/null || true)"
      item_number="$(printf '%s' "$ctx" | jq -r '.item_number // empty' 2>/dev/null || true)"
      [ "$item_type" = "pull_request" ] || skip "not a PR trigger (${item_type:-none})"
      [ -n "$item_number" ] || skip "no item number"
      repo="${GITHUB_REPOSITORY:-}"
      [ -n "$repo" ] || skip "no repo"
      head_ref="$(gh api "repos/${repo}/pulls/${item_number}" --jq '.head.ref' 2>/dev/null || true)"
      [ -n "$head_ref" ] || skip "could not resolve head ref for PR ${item_number}"
      # Re-authenticate origin only for the fetch — the agent checkout stripped
      # credentials (persist-credentials: false). Strip the token afterward so
      # the agent container never reads it from .git/config.
      server="${GITHUB_SERVER_URL#https://}"
      tokenless="https://${server}/${repo}.git"
      git remote set-url origin "https://x-access-token:${GH_TOKEN}@${server}/${repo}.git"
      if ! git fetch --depth=1 origin "$head_ref"; then
        git remote set-url origin "$tokenless"
        skip "fetch of ${head_ref} failed"
      fi
      git remote set-url origin "$tokenless"
      git checkout -B "$head_ref" "origin/${head_ref}" || skip "checkout of ${head_ref} failed"
      echo "pr-checkout: on ${head_ref} @ $(git rev-parse --short HEAD 2>/dev/null || echo '?')" >&2
---

<!-- This fragment contributes a pre-agent host step only; it has no prompt body. -->
