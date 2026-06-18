# ADR 0014: Dispatch fan-out via /execute comment

- Status: Accepted
- Date: 2026-05-21

## Context

ADR 0011 specified that `sdd-dispatch` fans the cascade out to the
`sdd-execute-{tier}` variants via the GitHub `workflow_dispatch` REST
endpoint, one call per ready task. The wrapper mints an App installation
token for each call because the default `GITHUB_TOKEN` cannot trigger
another workflow run, and ADR 0004 already establishes the App-minted
token as the cross-agent write seam.

The 2026-05-21 walk of `e2e-plan-dispatch-stress.md` against
a consumer pilot run (tracked in that consumer's private repo) found
that `createWorkflowDispatch` returned `403 Resource not accessible by
integration` on every fan-out cell (issue #121). The App token's
installation permissions did not include `actions: write`, the scope
`workflow_dispatch` requires. The cascade only progressed today through
side-effects of the dispatcher's other writes (label adds), not through
the documented fan-out path. Compounding this, every
`issues.closed`-triggered re-fire of the cascade replayed the same 403,
so the cascade-on-close loop was structurally broken.

Two paths back to a working fan-out exist:

1. **Grant `actions: write` to the App.** Adds an operator action to every
   consumer install (update the App permissions, re-install, accept the
   new scope on every existing install). Couples the cascade to an extra
   permission that has no other use in the suite.
2. **Switch the fan-out to a different GitHub primitive that the App's
   existing scopes already cover.** The App token already carries
   `issues: write` (the dispatcher uses it to apply `sdd:ready` to each
   dispatched task), and an App-authored issue comment does trigger
   downstream workflows just like an App-authored API call (the same
   property that made the App token the chosen substitute for
   `GITHUB_TOKEN` in the first place). Posting `/execute` on each ready
   task issue gives the matching `sdd-execute-{tier}` wrapper a route
   that already exists (its `issue_comment.created` trigger), and a route
   step that already validates `/execute`. No new App scope is required.

This ADR adopts path 2. It is consistent with ADR 0001 (GitHub-native
primitives only) and with ADR 0011's intent: a deterministic fan-out from
the dispatcher to the per-tier executor; the mechanism shifts but the
contract does not.

## Decision

1. **`sdd-dispatch` fans the cascade out by posting `/execute` on each
   ready task issue.** The wrapper's `dispatch` job mints the App
   installation token (unchanged), expands the ready set into a matrix
   (unchanged shape, except the matrix cell is now one task issue
   number — no tier dimension), and posts a single `/execute` comment
   per cell via `github.rest.issues.createComment`. The matching
   `sdd-execute-{tier}` wrapper picks the comment up through its
   existing `issue_comment.created` trigger.
2. **The `sdd-execute-{tier}` wrappers accept `/execute` from the
   configured GitHub App in addition to write-access humans.** The
   route step checks `payload.comment.performed_via_github_app.id`
   against the configured `APP_ID` repo variable; a match admits the
   command past the human repo-permission check. Any other bot's
   `/execute` is still rejected.
3. **The per-tier `sdd-execute-{tier}` wrappers carry a wrapper-level
   command + tier gate.** The `route` job's `if:` expression filters
   `issue_comment` events to `/execute` or `/revise`, and gates
   `/execute` on the issue carrying `model:<tier>`. The route step's
   existing tier-resolution logic stays as a defence-in-depth check;
   the wrapper-level gate eliminates the runner-minute waste that
   issue #119 documented and the route-step skip-races that issue #114
   documented.
4. **The per-tier concurrency group gains a tier discriminator.** Each
   `sdd-execute-{tier}` wrapper's `concurrency.group` becomes
   `sdd-execute-<tier>-<task>` (rather than `sdd-execute-<task>`). The
   three tier wrappers no longer share a group, so a non-matching-tier
   wake on a `/execute` comment can no longer cancel the matching-tier
   run via `cancel-in-progress: true` (issue #124).
5. **The App's installation permissions do not need to add `actions:
   write`.** The cascade's only token operations are issue label
   changes and comment posts, which the existing `issues: write` scope
   covers. Operators do not need to reconfigure the App.
6. **ADR 0011 stays in force for everything else.** Selection is still
   graph-driven; persistence is still `sdd:dispatched`; preconditions
   are unchanged; bounded matrix parallelism via
   `SDD_DISPATCH_MAX_PARALLEL` is unchanged; in-flight detection is
   unchanged. The change is the wire protocol between dispatcher and
   executor, not the cascade contract.

## Reasoning

- **Smaller install footprint.** The App's documented scopes are
  `contents: read/write`, `issues: read/write`, `pull-requests:
  read/write`, `discussions: write`. Adding `actions: write` for a
  single internal use case bloats the installation prompt that every
  consumer sees and grants the App power well beyond what it needs.
  Reusing `issues: write` (already needed for `sdd:ready`) keeps the
  scope set minimal.
- **One primitive for the cascade.** Every other agent-to-agent hand-off
  in the suite is a label flip or a comment. The `workflow_dispatch`
  call was the only exception; replacing it with a comment makes the
  whole pipeline uniform on GitHub-native primitives (ADR 0001).
- **Idempotency stays cheap.** The dispatcher already de-duplicates
  in-flight tasks against open PRs and the `sdd:in-progress` label; the
  per-tier wrappers' per-task-per-tier concurrency group is the
  defence-in-depth backstop. A second `/execute` on an in-flight task
  collapses at the concurrency gate exactly as before.
- **The cancellation race goes away.** Under the old model each tier
  wrapper subscribed to the same `workflow_dispatch` and the same
  `issue_comment` events; the per-task concurrency group made the three
  wrappers compete for the same lock, and `cancel-in-progress: true`
  let a non-matching tier kill the matching one (issue #124). Under
  the new model only the matching tier wakes (via the wrapper-level
  tier gate) and only the matching tier holds the per-tier group; a
  non-matching wake is no longer possible to cancel the matching one.
- **The 17-wake noise goes away.** Under the old model every wrapper
  that subscribed to `issue_comment.created` woke on every comment
  and route-skipped after consuming a runner minute. The new
  wrapper-level `if:` gates filter at workflow-evaluation time, so
  irrelevant wakes never allocate a runner (issue #119).

## Cross-links

- **ADR 0001** — `needs-human` and the GitHub-native-primitives
  principle. The shift to comment side-effect honours both.
- **ADR 0004** — the App-token-as-cross-agent-write-seam model. The App
  still mints the token; only the API call changes.
- **ADR 0011** — the cascade contract. Selection, persistence,
  preconditions, parallelism, in-flight detection, and the lifecycle
  ownership stay as ADR 0011 specifies. ADR 0011's verification step
  that asserted on `workflow_dispatch` calls is reworded to assert on
  `/execute` comments; the behaviour it verifies is unchanged.
- **Issues #114, #119, #121, #124** — the four bugs this ADR closes.
  #114 (all-3-tier fire) is closed by the wrapper-level tier gate.
  #119 (17-wake noise) is closed by the wrapper-level command gate.
  #121 (fan-out 403) is closed by the wire-protocol switch. #124
  (concurrency cancel) is closed by the per-tier concurrency
  discriminator.

## Verification

- A tracking issue at `sdd:ready` with five independent open task
  sub-issues, given a `/dispatch` from a write-access author, posts
  five `/execute` comments — one per task — within seconds; each
  task's matching `sdd-execute-{tier}` wrapper runs to completion;
  the tracking issue moves to `sdd:in-progress` and gains
  `sdd:dispatched`. No `workflow_dispatch` REST call appears in any
  run log; no `403 Resource not accessible by integration` appears.
- A `/dispatch` comment on a tracker fires exactly one wrapper
  run-evaluation per per-task fan-out plus `sdd-dispatch` itself; no
  `sdd-spec`, `sdd-triage`, `sdd-validate`, or non-matching-tier
  `sdd-execute-*` run is allocated.
- A `/execute` comment posted by the configured App on a task issue
  carrying `model:sonnet` admits the comment at the `sdd-execute-sonnet`
  wrapper's route step; the same comment on a task carrying
  `model:haiku` is filtered out at the wrapper-level `if:` gate on
  `sdd-execute-sonnet` and admitted at `sdd-execute-haiku`. A `/execute`
  from any other bot is rejected.
- A simultaneous `/execute` on the same task in two different tiers
  (an unreachable state via the dispatcher, but reachable via manual
  operator comments) runs both wrappers without one cancelling the
  other; the route step's tier-resolution skip then ensures only one
  agent run produces a PR.
- `LEAK_DENYLIST="$(cat denylist.txt)" bash scripts/leak-scan.sh`
  passes (no App slug literal — `APP_ID` is a `vars.APP_ID`
  reference).

## Consequences

- The `actions: write` scope is **not** added to the App. Operators
  with an existing App installation do not need to reconfigure
  anything.
- `wrappers/sdd-dispatch.yml`'s matrix loses its `tier` dimension;
  cells are now `{ task: <issue-number> }`. The strategy.matrix
  expansion shape is unchanged in size; only the per-cell shape
  shrinks.
- The three `sdd-execute-{tier}` wrappers carry an extra `env: APP_ID`
  on their route step and an extra `fromConfiguredApp` branch in the
  route-step's permission gate.
- The three `sdd-execute-{tier}` concurrency groups change from
  `sdd-execute-<task>` to `sdd-execute-<tier>-<task>`. Any existing
  in-flight run on the old group name is not affected because GitHub
  Actions concurrency is evaluated per-workflow-run; runs already in
  flight at the moment of the change complete on the old group name.
- The wrapper-level `if:` gates on the four wrappers (`sdd-spec`,
  `sdd-triage`, `sdd-dispatch`, `sdd-execute-{tier}`) reduce per-
  comment fan-out from ~17 wake-ups to ≤ 1 + N (where N is the ready
  set on a `/dispatch`).
