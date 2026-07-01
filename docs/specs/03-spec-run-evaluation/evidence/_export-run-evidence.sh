#!/usr/bin/env bash
# Export a forensic bundle of an SDD pipeline run for retroactive evaluation.
#
# Run this from any machine where `gh` is authenticated with read access to
# the target repository. Produces <out-dir>.tar.gz containing the tracking
# issue, its full sub-issue tree, timelines (label events with actors and
# timestamps), all comments, minimized-comment flags (GraphQL), every
# spec/arch/sdd pull request with reviews + review threads + diffs, the
# workflow-run index for the window, and (optionally) per-run jobs and
# agent artifacts.
#
# Usage:
#   _export-run-evidence.sh <owner/repo> <tracking-issue> [out-dir] [--artifacts]
#
#   EXTRA_PRS="581 589" _export-run-evidence.sh acme/widgets 478
#     also exports PRs whose head branches are not sdd/ spec/ arch/ prefixed
#     (e.g. human remediation PRs).
#
#   WINDOW_FROM=2026-06-01 overrides the workflow-run window start.
#
# GraphQL comment/thread queries fetch the first 100 nodes per item; for the
# rare item with more, the REST exports still contain every comment body.

set -euo pipefail

REPO="${1:?usage: $0 <owner/repo> <tracking-issue> [out-dir] [--artifacts]}"
TRACKER="${2:?usage: $0 <owner/repo> <tracking-issue> [out-dir] [--artifacts]}"
OUT="${3:-run-evidence-${TRACKER}}"
ARTIFACTS="${4:-}"
WINDOW_FROM="${WINDOW_FROM:-2026-06-01}"

OWNER="${REPO%%/*}"
NAME="${REPO##*/}"

mkdir -p "$OUT/issues" "$OUT/prs" "$OUT/runs" "$OUT/graphql"

api() { gh api -H "Accept: application/vnd.github+json" "$@"; }
note() { printf '>> %s\n' "$*" >&2; }

fetch_json() { # fetch_json <path> <outfile> ; writes [] on failure
  if ! api --paginate "$1" > "$2" 2>/dev/null; then echo '[]' > "$2"; fi
}

numbers_in() { jq -r '.[].number' "$1" 2>/dev/null || true; }

# ---- 1. tracking issue + two-level sub-issue tree -------------------------
note "tracking issue #$TRACKER and sub-issue tree"
api "repos/$REPO/issues/$TRACKER" > "$OUT/issues/$TRACKER.json"
fetch_json "repos/$REPO/issues/$TRACKER/sub_issues" "$OUT/issues/$TRACKER.sub_issues.json"

: > "$OUT/.issuelist"
echo "$TRACKER" >> "$OUT/.issuelist"
while IFS= read -r unit; do
  [ -n "$unit" ] || continue
  echo "$unit" >> "$OUT/.issuelist"
  fetch_json "repos/$REPO/issues/$unit/sub_issues" "$OUT/issues/$unit.sub_issues.json"
  while IFS= read -r task; do
    [ -n "$task" ] || continue
    echo "$task" >> "$OUT/.issuelist"
  done <<< "$(numbers_in "$OUT/issues/$unit.sub_issues.json")"
done <<< "$(numbers_in "$OUT/issues/$TRACKER.sub_issues.json")"
sort -un "$OUT/.issuelist" -o "$OUT/.issuelist"

while IFS= read -r n; do
  [ -n "$n" ] || continue
  note "issue #$n: body, comments, timeline"
  api "repos/$REPO/issues/$n" > "$OUT/issues/$n.json"
  fetch_json "repos/$REPO/issues/$n/comments" "$OUT/issues/$n.comments.json"
  fetch_json "repos/$REPO/issues/$n/timeline" "$OUT/issues/$n.timeline.json"
done < "$OUT/.issuelist"

# ---- 2. pull requests ------------------------------------------------------
note "pull-request index"
gh pr list --repo "$REPO" --state all --limit 300 \
  --json number,title,headRefName,baseRefName,state,createdAt,closedAt,mergedAt,additions,deletions,changedFiles,author,labels,url \
  > "$OUT/prs/index.json"

: > "$OUT/.prlist"
jq -r '.[] | select(.headRefName | test("^(sdd|spec|arch)/")) | .number' \
  "$OUT/prs/index.json" >> "$OUT/.prlist"
for x in ${EXTRA_PRS:-}; do echo "$x" >> "$OUT/.prlist"; done
sort -un "$OUT/.prlist" -o "$OUT/.prlist"

while IFS= read -r n; do
  [ -n "$n" ] || continue
  note "PR #$n: body, reviews, threads, files, commits, diff"
  api "repos/$REPO/pulls/$n" > "$OUT/prs/$n.json"
  fetch_json "repos/$REPO/pulls/$n/reviews" "$OUT/prs/$n.reviews.json"
  fetch_json "repos/$REPO/pulls/$n/comments" "$OUT/prs/$n.review_comments.json"
  fetch_json "repos/$REPO/issues/$n/comments" "$OUT/prs/$n.comments.json"
  fetch_json "repos/$REPO/issues/$n/timeline" "$OUT/prs/$n.timeline.json"
  fetch_json "repos/$REPO/pulls/$n/files" "$OUT/prs/$n.files.json"
  fetch_json "repos/$REPO/pulls/$n/commits" "$OUT/prs/$n.commits.json"
  api "repos/$REPO/pulls/$n" -H "Accept: application/vnd.github.v3.diff" \
    > "$OUT/prs/$n.diff" 2>/dev/null || true
done < "$OUT/.prlist"

# ---- 3. minimized flags + review threads (GraphQL; REST omits both) --------
# shellcheck disable=SC2016  # $owner/$name/$num are GraphQL variables, not shell
GQL='query($owner:String!,$name:String!,$num:Int!){
  repository(owner:$owner,name:$name){
    issueOrPullRequest(number:$num){
      __typename
      ... on Issue { comments(first:100){nodes{
        databaseId isMinimized minimizedReason createdAt author{login}}}}
      ... on PullRequest {
        comments(first:100){nodes{
          databaseId isMinimized minimizedReason createdAt author{login}}}
        reviewThreads(first:100){nodes{
          isResolved isOutdated path
          comments(first:50){nodes{databaseId isMinimized author{login}}}}}
      }
    }
  }
}'
sort -un "$OUT/.issuelist" "$OUT/.prlist" | while IFS= read -r n; do
  [ -n "$n" ] || continue
  note "GraphQL flags for #$n"
  gh api graphql -f query="$GQL" -F owner="$OWNER" -F name="$NAME" -F num="$n" \
    > "$OUT/graphql/$n.json" 2>/dev/null || echo '{}' > "$OUT/graphql/$n.json"
done

# ---- 4. workflow runs in the window ----------------------------------------
note "workflow runs since $WINDOW_FROM"
api --paginate -X GET "repos/$REPO/actions/runs" \
  -f created=">=$WINDOW_FROM" -F per_page=100 \
  --jq '.workflow_runs[] | {id,name,event,status,conclusion,head_branch,head_sha,run_started_at,updated_at,html_url}' \
  > "$OUT/runs/index.jsonl" || : > "$OUT/runs/index.jsonl"

# ---- 5. optional: per-run jobs + agent artifacts ----------------------------
if [ "$ARTIFACTS" = "--artifacts" ]; then
  jq -r 'select(.name | test("sdd-|distillery")) | .id' "$OUT/runs/index.jsonl" \
    > "$OUT/.runlist"
  while IFS= read -r rid; do
    [ -n "$rid" ] || continue
    note "run $rid: jobs + artifacts"
    fetch_json "repos/$REPO/actions/runs/$rid/jobs" "$OUT/runs/$rid.jobs.json"
    fetch_json "repos/$REPO/actions/runs/$rid/artifacts" "$OUT/runs/$rid.artifacts.json"
    while IFS=$'\t' read -r aid aname; do
      [ -n "$aid" ] || continue
      note "  artifact $aname"
      api "repos/$REPO/actions/artifacts/$aid/zip" \
        > "$OUT/runs/$rid.$aname.zip" 2>/dev/null || true
    done <<< "$(jq -r '.artifacts[]? | [.id, .name] | @tsv' "$OUT/runs/$rid.artifacts.json")"
  done < "$OUT/.runlist"
fi

# ---- 6. repo labels (variables need admin; ignore failures) -----------------
fetch_json "repos/$REPO/labels" "$OUT/labels.json"
gh variable list --repo "$REPO" > "$OUT/variables.txt" 2>/dev/null || true

tar -czf "$OUT.tar.gz" "$OUT"
note "done: $OUT.tar.gz"
