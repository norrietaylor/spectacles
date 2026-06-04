export const meta = {
  name: 'pr-fleet-spectacles',
  description: 'Per-issue pipeline: implement in worktree, expert review, apply fixes, open PR (gh-aw workflow repo)',
  phases: [
    { title: 'Implement', detail: 'fix + recompile locks in isolated worktree, push branch (no PR)' },
    { title: 'Review', detail: 'expert reviewer checks out branch detached, finds must-fix items' },
    { title: 'Finalize+PR', detail: 'apply review fixes, open PR' },
  ],
}

const REPO = 'norrietaylor/spectacles'
const BASE = 'main'

const TOOLCHAIN = `TOOLCHAIN — this repo is a gh-aw AGENTIC-WORKFLOW COLLECTION, not a typical app. There is NO runtime test harness for workflow behavior; "tests" = the repo's STATIC lint gates. Do NOT fabricate vacuous tests.
SOURCES (edit these):
  - .github/workflows/*.md          agent prompts; COMPILE to *.lock.yml
  - shared/*.md                     included into workflow .md
  - wrappers/*.yml                  hand-authored github-script; the RUNTIME for sdd-dispatch/execute routing
  - .github/actions/*/action.yml    hand-authored github-script actions
NEVER hand-edit a *.lock.yml — it is GENERATED. If you change any .github/workflows/*.md or shared/*.md you MUST regenerate locks and commit them with the source:
  gh aw compile --no-check-update            # global gh extension; runs in this worktree
  git add .github/workflows/<name>.md .github/workflows/<name>.lock.yml
Editing only a wrappers/*.yml or .github/actions/*/action.yml does NOT change any lock (those are not .md sources) — no recompile needed for those.
VALIDATION GATES (run the ones relevant to your change; ALL must pass — this is what CI checks):
  - lock parity:  gh aw compile --no-check-update && (git status --porcelain -- '.github/workflows' | grep '\\.lock\\.yml' && echo DRIFT-FAIL || echo lock-clean)
  - markdownlint: /opt/homebrew/bin/npx --yes markdownlint-cli2 "<changed .md paths>"
  - actionlint (hand-authored yml ONLY, never *.lock.yml): bash <(curl -sSfL https://raw.githubusercontent.com/rhysd/actionlint/v1.7.12/scripts/download-actionlint.bash) 1.7.12 && ./actionlint <changed wrappers/*.yml or action.yml>
  - shellcheck:   shellcheck <changed *.sh>      (only if you touched a shell script)
  - python static gates (pyyaml is installed):
      /opt/homebrew/bin/python3 scripts/test-safe-output-allowlists.py     # if you changed a safe-output allowlist or labels
      /opt/homebrew/bin/python3 scripts/test-command-table.py              # if you added/changed a slash command
      /opt/homebrew/bin/python3 scripts/test-lifecycle-state-machine.py    # if you changed sdd:* label transitions
      /opt/homebrew/bin/python3 scripts/test-requirement-ids.py
  If you add a slash command, safe-output, or sdd:* transition you MUST update its paired source-of-truth (shared/sdd-interaction.md command table; the frontmatter allowlist; scripts/lifecycle-states.yml) or the gate fails.
ABSOLUTE PATHS (bare names may be proxied): gh, /opt/homebrew/bin/npx, /opt/homebrew/bin/python3.
Acceptance here is BEHAVIORAL (GitHub Actions runtime) and not locally executable. Prove what IS statically checkable (lock parity + the lint gates + extend a scripts/test-*.py assertion where your change is statically verifiable). Document the behavioral acceptance in the PR body. Surgical changes only. Conventional Commits. End commit messages with the co-author trailer: Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

const ISSUES = [
{"n":216,"scope":"fix(sdd-spec)","branch":"fix/216-repo-grounded-planning","overlap":false,"title":"sdd-spec/sdd-triage: ground planning in existing repo state (Serena/Distillery) — don't create tasks for already-implemented requirements","fixSpec":"sdd-spec/sdd-triage decompose requirements into tasks WITHOUT first checking what the target repo already implements, so they create tasks for already-done work (empty/no-PR runs, manual closing). The Serena (symbol-level code intelligence) and Distillery (repo knowledge base) MCPs are imported but the spec/triage stages never instruct a 'what already exists?' baseline pass before task creation. FIX (prose additions to .md sources — then `gh aw compile --no-check-update` and commit regenerated locks): (a) In .github/workflows/sdd-spec.md add a REQUIRED baseline-against-repo step before task/plan creation: for each requirement, use Serena (find_symbol / find_referencing_symbols for the types/functions/files the requirement would add) and Distillery (distillery_search / find_similar for prior decisions/components/merged PRs) to determine whether it is ALREADY satisfied in-tree. (b) In .github/workflows/sdd-triage.md (Phase B plan composition, before /approve) require the same baseline: an already-satisfied requirement must NOT become an implementation task — mark it done in the plan with evidence (file/symbol refs) or create a verification-only task, and surface 'ALREADY EXISTS: <evidence>' in the plan preview. (c) In shared/sdd-mcp-serena.md and shared/sdd-mcp-distillery.md add an explicit 'When to use during planning' section stating the baseline pass is a required phase (the existing fragments document capability/how but not when). Make repo-grounding a documented REQUIRED phase, not an optional capability. Keep prose surgical. Run markdownlint on changed .md; confirm lock parity after compile. If you reference MCP tools, ensure no safe-output/command-table gate breaks (run the relevant scripts/test-*.py)."},
{"n":200,"scope":"fix(sdd-dispatch)","branch":"fix/200-claim-time-in-progress","overlap":true,"siblings":[207],"mergeNote":"Potentially shares .github/actions/sdd-route-execute/action.yml with #207 — PREFER the dispatch-side approach (wrappers/sdd-dispatch.yml + scripts/lifecycle-states.yml) to avoid touching route-execute and conflicting with #207. If you must touch route-execute, merge #200 before #207.","title":"sdd-dispatch/execute: move task sub-issue to sdd:in-progress at claim time, not mid-run","fixSpec":"A task sub-issue reaches sdd:in-progress only mid-run (inside sdd-execute step 2), not when claimed — so during the gap a dispatched task is indistinguishable from an un-dispatched sdd:ready task. FIX (prefer the deterministic dispatch-side transition; #143 made this safe because the execute route trigger ignores issues label events except 'unlabeled needs-human'): In wrappers/sdd-dispatch.yml, the per-task fan-out step that currently adds sdd:ready to each dispatched task (issue cites ~lines 192-212; locate by content — grep for the per-task addLabels of sdd:ready after posting /execute) should instead, immediately after posting /execute, add sdd:in-progress AND remove sdd:ready on the task, mirroring the tracking-issue transition pattern already in the lifecycle job (~lines 265-292). Use the App/GITHUB token (label writes via it do not re-trigger workflows). CRITICAL lifecycle gate: scripts/lifecycle-states.yml declares sdd-execute as the writer of sdd:in-progress; a dispatch-side write will FAIL scripts/test-lifecycle-state-machine.py unless you add sdd-dispatch as an authorized co-writer of sdd:in-progress (and sdd:ready removal) in scripts/lifecycle-states.yml. Update it and run python3 scripts/test-lifecycle-state-machine.py until green. Also reconcile the prose: sdd-execute step 2 still moves sdd:ready->sdd:in-progress — make it idempotent/tolerant of the task ALREADY being sdd:in-progress (don't fail if sdd:ready is absent). Edit the three sdd-execute-*.md step-2 prose for that tolerance and recompile locks. Compatibility: #211 made sdd-dispatch-compute admit non-in-flight sdd:in-progress tasks — confirm still green. Run actionlint on wrappers/sdd-dispatch.yml; markdownlint + lock parity for any .md; the lifecycle + safe-output python gates. Do NOT regress #143 (no cancel/re-fire from the claim-time write)."},
{"n":207,"scope":"fix(sdd-execute)","branch":"fix/207-impl-pr-rebase-conflict","overlap":true,"siblings":[200],"mergeNote":"Potentially shares .github/actions/sdd-route-execute/action.yml with #200 (which is steered dispatch-side to avoid it). Cross-reference #200; if both touch route-execute, merge #200 first then rebase #207.","title":"sdd-execute: no rebase/conflict-resolution for impl PRs — sibling PRs strand as CONFLICTING when base advances","fixSpec":"sdd-execute has NO mechanism to keep an impl PR branch current with its base: when the cascade merges one task's PR to main, other open sdd/ PRs touching the same files go CONFLICTING and strand (nothing rebases/refreshes/resolves). /revise only appends commits via push-to-pull-request-branch; it never rebases onto base or merges main, and there is no conflict detection. FIX (bounded, behavioral): (a) AUTO-REFRESH — when an open sdd/ PR falls behind its base (detect via the PR mergeable/mergeStateStatus and 'behind' state), update the branch (merge base in / GitHub update-branch) and let CI re-run. Trigger this when main advances — e.g. a push-to-main / pull_request closed(merged) handler in wrappers/sdd-execute-*.yml + .github/actions/sdd-route-execute/action.yml that sweeps open sdd/ PRs and refreshes those behind base. (b) CONFLICT -> REVISE, not needs-human first: when update-branch hits a textual conflict (mergeable=CONFLICTING), dispatch an implicit /revise to sdd-execute with a 'resolve merge conflict with base' directive (it has task context; most collisions are mechanical append-only Cargo.toml/lib.rs unions). Bound the attempts; escalate needs-human only after a failed automated resolve. MIRROR the existing revise dispatch path (the #203 check_suite handler and the changes_requested path are good models). Keep it surgical and within the route handler + wrapper triggers. wrappers/*.yml and action.yml are hand-authored (no lock recompile) — run actionlint; node --check the action.yml github-script. If you add label writes (needs-human / a retry marker), run scripts/test-safe-output-allowlists.py + scripts/test-lifecycle-state-machine.py. Cross-reference sibling #200 (avoid both rewriting the same route-execute block)."},
]

const IMPLEMENT_SCHEMA = {
  type: 'object',
  required: ['issue', 'branch', 'pushed', 'headSha', 'filesChanged', 'testSummary', 'gatesClean', 'acceptanceMapping', 'notes'],
  properties: {
    issue: { type: 'number' }, branch: { type: 'string' }, pushed: { type: 'boolean' },
    headSha: { type: 'string' }, filesChanged: { type: 'array', items: { type: 'string' } },
    testSummary: { type: 'string' }, gatesClean: { type: 'boolean' },
    acceptanceMapping: { type: 'array', items: { type: 'object', required: ['criterion', 'addressedBy'], properties: { criterion: { type: 'string' }, addressedBy: { type: 'string' } } } },
    notes: { type: 'string' },
  },
}
const REVIEW_SCHEMA = {
  type: 'object',
  required: ['issue', 'branch', 'verdict', 'findings', 'mustFix', 'acceptanceGaps', 'summary'],
  properties: {
    issue: { type: 'number' }, branch: { type: 'string' },
    verdict: { type: 'string', enum: ['approve', 'request_changes'] },
    findings: { type: 'array', items: { type: 'object', required: ['severity', 'file', 'claim'], properties: { severity: { type: 'string' }, file: { type: 'string' }, line: { type: 'string' }, claim: { type: 'string' }, suggestedFix: { type: 'string' }, valid: { type: 'boolean' } } } },
    mustFix: { type: 'array', items: { type: 'string' } },
    acceptanceGaps: { type: 'array', items: { type: 'string' } }, summary: { type: 'string' },
  },
}
const FINALIZE_SCHEMA = {
  type: 'object',
  required: ['issue', 'branch', 'prNumber', 'prUrl', 'appliedFixes', 'finalTestSummary', 'prTitle'],
  properties: {
    issue: { type: 'number' }, branch: { type: 'string' }, prNumber: { type: 'number' },
    prUrl: { type: 'string' }, appliedFixes: { type: 'array', items: { type: 'string' } },
    finalTestSummary: { type: 'string' }, prTitle: { type: 'string' },
  },
}

const implementPrompt = (it) => `You are an expert engineer fixing issue #${it.n} in ${REPO}, in an ISOLATED git worktree (CWD = worktree root, branched from origin/${BASE}).
${TOOLCHAIN}
ISSUE #${it.n}: ${it.title}
FIRST: gh issue view ${it.n} — read root cause, file:line pointers, fix recipe, acceptance criteria. Line numbers DRIFT; locate code by CONTENT (grep), not numbers.
FIX SPEC: ${it.fixSpec}
${it.overlap ? `OVERLAP: this issue edits files shared with sibling issues ${JSON.stringify(it.siblings)} in this same batch. Stay STRICTLY within the lines your fix needs; do not reformat or rewrite surrounding blocks, to keep the merge conflict with siblings minimal.` : ''}
REQUIREMENTS: implement faithfully and surgically. Run every VALIDATION GATE relevant to your change (above) — they must pass. Do NOT chase unrelated/infra flakes — note them.
GIT — push to a REMOTE branch by refspec; do NOT create a local branch of that name (avoids "already checked out in another worktree"):
  git add -A && git commit -m "${it.scope}: <imperative subject> (#${it.n})" -m "<body>" -m "Closes #${it.n}" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  git push origin HEAD:refs/heads/${it.branch}
  git rev-parse HEAD   (headSha)
DO NOT create the PR. DO NOT touch ${BASE}. If you cannot finish, still commit+push partial work (pushed=true) with notes; if you could not push, pushed=false.
Return IMPLEMENT_SCHEMA (branch="${it.branch}").`

const reviewPrompt = (it, impl) => `You are an EXPERT CODE REVIEWER in an isolated worktree. Adversarially-but-fairly review the fix for issue #${it.n} on remote branch ${it.branch} BEFORE it becomes a PR. Implementer reported pushed=${impl ? impl.pushed : 'unknown'}, files=${impl ? JSON.stringify(impl.filesChanged) : '[]'}.
If pushed is false/unknown: verdict=request_changes, mustFix=["did not land on origin/${it.branch} — re-implement"], return.
SETUP (safe, detached — no branch-name conflict): git fetch origin ${it.branch} && git checkout --detach FETCH_HEAD && git diff origin/${BASE}...HEAD
${TOOLCHAIN}
You MAY run the validation gates to VERIFY claims. READ-ONLY: never commit/push.
Read the issue: gh issue view ${it.n}.
LENS (this is a gh-aw workflow repo — judge accordingly): (1) correctness vs the issue's root cause — does the prose/github-script/frontmatter actually produce the claimed behavior, incl. event-trigger semantics and concurrency? (2) lock parity — if a .md changed, were the *.lock.yml regenerated and committed? run the lock-parity gate; (3) gate compliance — do the relevant python/markdownlint/actionlint gates pass? (4) NO generated *.lock.yml was hand-edited; (5) surgical scope — only the issue's files; no unrelated drift; (6) for prose-only fixes to agent prompts, is the instruction unambiguous and enforceable, or does it need a deterministic guard?
mustFix = ONLY blocking items (wrong/missing behavior vs root cause, failing gate, stale lock, hand-edited lock, scope creep that breaks a sibling). Nits → low-severity findings, NOT mustFix. Reproduce each finding; cite file:line / command output.
Return REVIEW_SCHEMA (branch="${it.branch}").`

const overlapBody = (it) => it.overlap
  ? `\n\n## Related\n- Shares files with sibling PRs for issues ${it.siblings.map(s => '#' + s).join(', ')} in this batch; they WILL conflict on merge. ${it.mergeNote}`
  : ''

const finalizePrompt = (it, review) => `You are the implementing engineer finalizing issue #${it.n} → opening its PR, in an isolated worktree. Branch ${it.branch} is already on origin.
Review mustFix: ${JSON.stringify(review ? review.mustFix : [])}
Review summary: ${review ? review.summary : '(none)'} ; acceptance gaps: ${JSON.stringify(review ? review.acceptanceGaps : [])}
${TOOLCHAIN}
STEP 1 — apply mustFix (skip if empty): git fetch origin ${it.branch} && git checkout --detach FETCH_HEAD ; apply each as a MINIMAL change; re-run the relevant gates (must pass); if you changed a .md, recompile locks; if changed: git add -A && git commit -m "${it.scope}: address review for #${it.n}" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>" && git push origin HEAD:refs/heads/${it.branch}
STEP 2 — open the PR (if one exists for ${it.branch}, gh pr edit it — never duplicate):
  gh issue view ${it.n}
  git diff origin/${BASE}...origin/${it.branch}
  gh pr create --base ${BASE} --head ${it.branch} --title "${it.scope}: <concise> (#${it.n})" --body "<BODY>"
BODY — engineering style (lead with facts, code before prose, plain headings, no narrative framing): ## Root cause / ## Fix / ## Acceptance (checked list mapping EACH issue acceptance criterion → how met / which gate or static assertion proves it; mark behavioral-only items explicitly) / ## Validation (exact gate commands + results)${it.overlap ? ' / ## Related' : ''}. End with "Closes #${it.n}".${overlapBody(it)}
Return FINALIZE_SCHEMA (branch="${it.branch}").`

log(`pr-fleet: ${ISSUES.length} issues → implement | review | PR (isolated worktrees, no barrier)`)
const results = await pipeline(
  ISSUES,
  (it) => agent(implementPrompt(it), { label: `impl:#${it.n}`, phase: 'Implement', isolation: 'worktree', schema: IMPLEMENT_SCHEMA }),
  (impl, it) => agent(reviewPrompt(it, impl), { label: `review:#${it.n}`, phase: 'Review', isolation: 'worktree', schema: REVIEW_SCHEMA }),
  (review, it) => agent(finalizePrompt(it, review), { label: `pr:#${it.n}`, phase: 'Finalize+PR', isolation: 'worktree', schema: FINALIZE_SCHEMA }),
)
const clean = results.filter(Boolean)
log(`pr-fleet done: ${clean.filter(r => r.prNumber > 0).length}/${ISSUES.length} PRs opened`)
return clean
