'use strict';

// Shared sub-issue parent walk (task -> Unit -> tracking issue).
//
// Extracted from `.github/actions/sdd-monitor/action.yml` (issue #254) so the
// monitor and `.github/actions/sdd-status` resolve a tracking issue with one
// source of truth, following the `shared/blocked-by.js` precedent. The module
// takes the `github` client as an argument (it is loaded inside
// actions/github-script), so it has no dependency of its own.
//
// The parent link is read via GraphQL `Issue.parent`, NOT via the REST
// `parent_issue_url` field. REST does not populate the child->parent pointer
// for native sub-issues reliably: the field comes back empty on the close
// webhook and on an immediate REST re-fetch (issue #133, the cascade-stall
// repro on that issue). sdd-dispatch's own route job switched to GraphQL for
// exactly this reason; every consumer of this module mirrors it.
//
// Fail-closed contract: parentViaGraphql and the walkers distinguish a
// *resolved* walk (returns a value, or 0/null when the walk legitimately
// reaches the top of the tree) from an *unresolved* walk caused by a lookup
// error (rethrows). A swallowed error that collapsed to "no parent" would
// make an open sdd/ PR look unrelated to its tracker in the monitor's
// in-flight guard (the cancellation-storm issue #148 exists to prevent
// that). Callers wrap in try/catch and decide their own safe default.

// Resolve one parent hop via GraphQL. Returns `{ id, number }` for the
// parent issue, or null when the node has no parent. A query failure
// rethrows so the caller fails closed.
async function parentViaGraphql(github, nodeId) {
  if (!nodeId) { return null; }
  const result = await github.graphql(
    'query($id: ID!) {' +
    '  node(id: $id) {' +
    '    ... on Issue { parent { id number } }' +
    '  }' +
    '}',
    { id: nodeId });
  const parent = result && result.node && result.node.parent;
  return parent || null;
}

// Walk a task sub-issue up to its tracking issue (task -> Unit -> tracker,
// two hops per ADR 0005). Returns the tracker issue number, or 0 if the walk
// does not resolve to a two-hop root (the seed was a Unit or the tracker
// itself, not a task). A seed or parent lookup error rethrows so the caller
// fails closed; it must not be confused with a fully-walked tree that has no
// parent.
async function walkToTracker(github, owner, repo, taskNum) {
  const { data } = await github.rest.issues.get({
    owner, repo, issue_number: taskNum,
  });
  let nodeId = data.node_id;
  let parent = null;
  let walked = 0;
  while (nodeId && walked < 2) {
    const next = await parentViaGraphql(github, nodeId);
    if (!next) { break; }
    parent = next;
    nodeId = next.id;
    walked += 1;
  }
  // A task closure is exactly two hops below a tracking issue. A shorter
  // walk means the seed was a Unit or the tracker itself, not a task — not
  // a tracker match for this guard.
  if (parent && walked === 2) {
    return parent.number;
  }
  return 0;
}

// Walk any issue up to the root of its sub-issue tree (at most two hops per
// ADR 0005: task -> Unit -> tracker). Returns `{ number, hops }` where
// `number` is the topmost ancestor reached (the seed itself when it has no
// parent) and `hops` is how many parent links were followed. Used by
// sdd-status, where the triggering issue may be the tracking issue itself, a
// Unit, or a task. Lookup errors rethrow (same fail-closed contract as
// walkToTracker).
async function walkToRoot(github, owner, repo, issueNum) {
  const { data } = await github.rest.issues.get({
    owner, repo, issue_number: issueNum,
  });
  let nodeId = data.node_id;
  let number = issueNum;
  let hops = 0;
  while (nodeId && hops < 2) {
    const next = await parentViaGraphql(github, nodeId);
    if (!next) { break; }
    number = next.number;
    nodeId = next.id;
    hops += 1;
  }
  return { number, hops };
}

module.exports = { parentViaGraphql, walkToTracker, walkToRoot };
