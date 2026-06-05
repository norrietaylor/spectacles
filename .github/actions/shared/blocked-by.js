'use strict';

// Shared, dependency-free blocked-by parsing and cycle detection.
//
// This module is required by both `.github/actions/sdd-dispatch-compute`
// (which parses each open task body for `blocked by` lines) and
// `.github/actions/sdd-cycle-detect` (which builds the edge map and runs the
// deterministic DAG check). It has no `@actions/*` or GitHub dependency, so it
// is unit-testable with plain `node` (see `scripts/test-cycle-detect.mjs`).

// Parse `blocked by #<N>` and `blocked by <owner>/<repo>#<N>` lines from an
// issue body. The regex is byte-for-byte the one extracted from
// sdd-dispatch-compute so the parse is identical at both call sites: optional
// leading list dash, the literal `blocked by`, an optional `<owner>/<repo>`
// prefix, and the issue number. Returns an array of
// `{ owner, repo, number }`; owner and repo are the empty string for a
// same-repo blocker.
function parseBlockers(body) {
  const blockerRegex =
    /^\s*-?\s*blocked by\s+(?:([\w.-]+)\/([\w.-]+))?#(\d+)/gim;
  const blockers = [];
  let m;
  blockerRegex.lastIndex = 0;
  while ((m = blockerRegex.exec(body || '')) !== null) {
    blockers.push({
      owner: m[1] || '',
      repo: m[2] || '',
      number: parseInt(m[3], 10),
    });
  }
  return blockers;
}

// Deterministic cycle detection over a node set.
//
// `nodeNumbers` is the array of task issue numbers in the graph; `edges` is a
// map from a node number to the array of node numbers it is blocked by (its
// out-edges in the dependency graph). Returns `{ hasCycle, path }`: when a
// cycle exists `path` is one concrete cycle as a list of node numbers that
// closes on itself (e.g. `[12, 15, 12]`); otherwise `path` is empty.
//
// Implemented as iterative depth-first search with a three-colour marking
// (white = unvisited, grey = on the current stack, black = fully explored).
// An edge into a grey node closes a back-edge and yields the cycle; the
// explicit stack keeps it safe on a deep graph where a recursive DFS could
// overflow.
function detectCycle(nodeNumbers, edges) {
  const WHITE = 0;
  const GREY = 1;
  const BLACK = 2;
  const colour = new Map();
  for (const n of nodeNumbers) {
    colour.set(n, WHITE);
  }

  const edgesOf = (n) => {
    const out = edges.get(n) || [];
    // Only follow edges to nodes that are part of the graph; an edge to a
    // number outside `nodeNumbers` is not a cycle participant here.
    return out.filter((t) => colour.has(t));
  };

  for (const start of nodeNumbers) {
    if (colour.get(start) !== WHITE) {
      continue;
    }
    // Each frame is [node, indexOfNextEdgeToVisit]. `stackNodes` mirrors the
    // grey path so a back-edge can be sliced into a cycle.
    const stack = [[start, 0]];
    const stackNodes = [start];
    colour.set(start, GREY);
    while (stack.length > 0) {
      const frame = stack[stack.length - 1];
      const node = frame[0];
      const out = edgesOf(node);
      if (frame[1] < out.length) {
        const next = out[frame[1]];
        frame[1] += 1;
        const c = colour.get(next);
        if (c === GREY) {
          // Back-edge: `next` is on the current stack. Slice the path from
          // `next` to the top and close it on `next`.
          const at = stackNodes.indexOf(next);
          const cycle = stackNodes.slice(at);
          cycle.push(next);
          return { hasCycle: true, path: cycle };
        }
        if (c === WHITE) {
          colour.set(next, GREY);
          stack.push([next, 0]);
          stackNodes.push(next);
        }
      } else {
        colour.set(node, BLACK);
        stack.pop();
        stackNodes.pop();
      }
    }
  }
  return { hasCycle: false, path: [] };
}

module.exports = { parseBlockers, detectCycle };
