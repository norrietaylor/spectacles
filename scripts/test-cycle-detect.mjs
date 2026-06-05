#!/usr/bin/env node
// Self-check for .github/actions/shared/blocked-by.js — the acceptance
// latent-cycle fixture for issue #229. Run standalone: `node
// scripts/test-cycle-detect.mjs`. Exits non-zero on the first failed
// assertion, 0 when all pass. No dependencies beyond Node's stdlib.

import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const require = createRequire(import.meta.url);
const here = dirname(fileURLToPath(import.meta.url));
const { parseBlockers, detectCycle } = require(
  join(here, '..', '.github', 'actions', 'shared', 'blocked-by.js'));

let failures = 0;
function check(name, cond) {
  if (cond) {
    console.log('ok   - ' + name);
  } else {
    failures += 1;
    console.log('FAIL - ' + name);
  }
}
function eq(name, actual, expected) {
  check(name + ' (got ' + JSON.stringify(actual) + ')',
    JSON.stringify(actual) === JSON.stringify(expected));
}

// (i) parseBlockers: same-repo and cross-repo lines.
{
  const body = [
    '## Task',
    '',
    'depends on:',
    '  - blocked by #12',
    '  - blocked by octo/widgets#34',
    'noise line referencing #99 that is not a blocker',
  ].join('\n');
  const blockers = parseBlockers(body);
  eq('parseBlockers parses two blocked-by lines', blockers.length, 2);
  eq('same-repo blocker', blockers[0], { owner: '', repo: '', number: 12 });
  eq('cross-repo blocker', blockers[1],
    { owner: 'octo', repo: 'widgets', number: 34 });
  eq('parseBlockers ignores a bare #N that is not a blocker',
    parseBlockers('see #99 for context'), []);
}

// (ii) detectCycle finds the latent cycle in the acceptance fixture.
// Task X's proof consumes an artifact produced by downstream task Y, so the
// latent-edge pass adds the edge X <- Y... but Y also (incorrectly) depends on
// X, the back-edge X <- Y plus Y <- X closes a cycle. Model it as:
//   12 (X) blocked by 15 (Y)   and   15 (Y) blocked by 12 (X).
{
  const nodes = [12, 15, 18];
  const edges = new Map([
    [12, [15]],
    [15, [12]],
    [18, [12]],
  ]);
  const res = detectCycle(nodes, edges);
  check('detectCycle reports a cycle', res.hasCycle === true);
  // The returned path must be a real cycle: it closes on its first node and
  // every consecutive pair is an edge in the graph.
  const path = res.path;
  const closes = path.length >= 2 && path[0] === path[path.length - 1];
  check('cycle path closes on itself (got '
    + JSON.stringify(path) + ')', closes);
  let everyPairIsEdge = closes;
  for (let i = 0; i + 1 < path.length; i += 1) {
    const out = edges.get(path[i]) || [];
    if (!out.includes(path[i + 1])) {
      everyPairIsEdge = false;
    }
  }
  check('every consecutive pair in the path is a real edge', everyPairIsEdge);
  check('cycle path involves the latent back-edge nodes 12 and 15',
    path.includes(12) && path.includes(15));
}

// (iii) a forward-only DAG returns hasCycle === false.
{
  const nodes = [1, 2, 3, 4];
  const edges = new Map([
    [1, []],
    [2, [1]],
    [3, [1, 2]],
    [4, [3]],
  ]);
  const res = detectCycle(nodes, edges);
  check('forward-only DAG has no cycle', res.hasCycle === false);
  eq('DAG path is empty', res.path, []);
}

// Bonus: a self-loop (task blocked by itself) is a cycle.
{
  const res = detectCycle([7], new Map([[7, [7]]]));
  check('self-loop is a cycle', res.hasCycle === true);
}

if (failures > 0) {
  console.error('\n' + failures + ' assertion(s) failed.');
  process.exit(1);
}
console.log('\nAll cycle-detect assertions passed.');
