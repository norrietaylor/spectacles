# Spikes

A **spike** is a time-boxed exploration that resolves a load-bearing assumption
before the plan commits to it. Its deliverable is a written finding, never a
code change. The spike primitive lets `sdd-triage` hold the plan until the
assumptions the plan rests on are settled, rather than committing a task tree on
ground the design has not yet proven.

This page is the deep dive on the primitive. The operator-facing hygiene for
running a spike on a consumer repository lives in `docs/spikes/README.md`; the
canonical protocol is the suite's spike fragment.

## Why a spike exists

`sdd-triage` phase A designs the architecture, and a design always rests on
things it takes as given: a behavior of an existing component, the shape of an
interface, a property of the data, a guarantee a dependency makes. Most of those
are confirmable — a prior decision settles them, or the symbol is in the
repository working tree and wired in. The dangerous ones are the assumptions
that are **load-bearing** (the chosen approach changes if they are false) **and**
not confirmable from repo state or precedent. Committing a plan on an unproven
load-bearing assumption is how a task tree ends up built on a wrong premise. A
spike is the bounded experiment that settles such an assumption first.

## The assumption ledger and the needs-spike trigger

While phase A designs the architecture, it builds an **assumption ledger** as a
`## Assumption ledger` subsection inside the per-feature architecture record —
not a separate file. The ledger carries one row per load-bearing assumption,
each with:

- a **stable slug row-key** (kebab-case, derived from the assumption statement),
  so the same assumption keeps the same key across `/revise` re-runs;
- a one-line **statement**;
- the **bucket** — `needs-spike` or `settled`;
- the **evidence / citation** that places it in its bucket;
- a **depends-on** field binding the assumption to architecture decisions or
  spec requirement IDs, never to tasks.

A per-row gate chain decides the bucket, stopping at the first gate that
disqualifies a candidate:

1. **Load-bearing gate.** Would the chosen approach change if the assumption were
   false? A non-load-bearing assumption is not ledgered at all.
2. **Settled gate.** Is it already settled by a prior decision or precedent? If
   so, ledger it `settled` with its citation.
3. **Repo-state gate.** Is it settleable from the working tree, confirmable at
   the Serena symbol-level baseline? If so, ledger it `settled` with its
   file/symbol evidence.
4. **needs-spike residue.** Load-bearing **and** not settleable from repo state
   **nor** settled by precedent — that residue is marked `needs-spike`.

The **trigger for a spike** is exactly that residue. `needs-spike` is a **ledger
marker**, not a GitHub label: it lives in the architecture record's prose, is
applied to no issue, and is not in the label catalog. `needs-spike` versus
`settled` are the whole partition of the ledger.

## The kind:spike sub-issue

Phase A step 4a materializes the wave: for each `needs-spike` row it emits one
`kind:spike` sub-issue, a **direct child of the tracking issue** (parented the
same way the architecture sub-issue is). The title is
`spike: <one-line assumption statement>`, and the body carries a structured
`## Spike` block — deliberately a distinct heading from the `## Task` block of
phase C, so the task-dedupe backstop (which filters on `## Task`) ignores spike
sub-issues entirely. The block carries:

- **repo** — the target repository in `<owner>/<repo>` form (defaults to the
  tracking issue's own repository);
- **question** — the load-bearing question, taken verbatim from the ledger row,
  the experiment must answer;
- **hypothesis** — the design's current expected answer, phrased so the
  experiment can confirm or falsify it;
- **load-bearing-assumption** — the ledger row's stable slug row-key, so the
  spike stays bound to the same assumption across `/revise`;
- **depends-on** — the architecture decisions or spec requirement IDs the
  assumption binds to;
- **proof-of-resolution** — the observable artifact that settles the question.

The `kind:spike` label and a `model:*` tier label are set in the same
`create-issue` call, never through `add-labels`. The tier is what the matching
`sdd-execute` variant keys on when the spike runs.

**Create-or-reuse by spike title** makes a `/revise` re-run idempotent on the
spike layer: a re-derived ledger that keeps an assumption keeps its spike rather
than spawning a duplicate. **Orphan cleanup on `/revise`** closes an open spike
whose assumption is no longer in the revised ledger's `needs-spike` bucket, so
the open spike set always equals the revised residue.

## The actuator: fanning out /execute

`sdd-triage` materializes the spike sub-issues and then ends its turn — nothing
fires `sdd-execute` on a freshly-created spike. The `sdd-spike-actuator` wrapper
closes that gap. When a `kind:spike` sub-issue is opened (or gains the
`kind:spike` label) under a tracking issue still in triage, the actuator posts
`/execute` on the spike sub-issue via the GitHub App installation token. The
matching `sdd-execute-{tier}` wrapper picks that comment up through its existing
`issue_comment` trigger and runs the spike — the same mechanism `sdd-dispatch`
uses to fan the main task cascade out, so it inherits the same cross-install
behavior. The actuator is deterministic: no LLM, no engine.

## The spike doc

A spike writes exactly one file: `docs/spikes/<date>-<slug>.md`, where `<date>`
is the spike's open date (`YYYY-MM-DD`) and `<slug>` is a short hyphenated
subject from the spike sub-issue's title. It writes no other path — a spike
never edits source, config, or any build surface. The written finding **is** the
deliverable, and the committed doc is itself the File-type proof artifact, so a
spike PR is exempt from the empty-PR proof rule's normal demand for a
behavior-demonstrating artifact.

The branch and pull-request conventions are the **standard implementation
conventions**, with no spike exception: the branch is `sdd/<spike-issue-id>-<slug>`
(never a custom `sdd/spike-` prefix, which would break the suite's in-flight
detection), the PR body carries `Closes #<spike-issue>` so merging closes the
spike sub-issue, and the commit subject and PR title use the `docs`
conventional-commit type.

### Doc format

YAML frontmatter followed by a fixed set of sections.

Frontmatter:

- `id` — the spike sub-issue number;
- `title` — the spike's one-line subject;
- `status` — one of `proved`, `disproved`, `partial`, or `parked`;
- `date` — the open date (`YYYY-MM-DD`);
- `authors` — who ran the experiment;
- `budget_hours` — the time box the spike was given;
- `actual_hours` — the time the experiment actually took;
- `related` — issues, PRs, or ADRs the spike informs;
- `tags` — free-form topic tags.

Body sections, in order:

- **Question** — the load-bearing assumption, stated as a question;
- **Hypothesis** — the expected answer before the experiment ran;
- **Method** — how the experiment was run, reproducibly;
- **Findings** — what was observed, with evidence inline: the exact commands run
  and their output, measurement tables, and links to the sources inspected;
- **Conclusion** — the verdict: `proved`, `disproved`, or `partial`;
- **Action items** — what the finding changes downstream, grouped as spec
  amendments, ADR follow-ups, risk-register entries, and follow-up spikes;
- **Artifacts** — the concrete proof: command transcripts, measurement files,
  and source links a reader can re-run or re-inspect.

## Outcomes and how sdd-validate resolves them

A spike PR (a `docs/spikes/**` change) resolves to the **spike boundary** in
`sdd-validate`, which sits ahead of the implementation boundary so a doc-only
spike PR never falls through to the implementation catch-all and draws a false
Blocker. The spike gate set is Blocker-only: a Conclusion must be present, and a
`disproved` or `partial` Conclusion must carry Action items. The implementation
gate set does not run on a spike PR — there is nothing to re-execute.

`sdd-validate` reads the doc's Conclusion and resolves the boundary:

- **proved** — the experiment resolved its assumption. `sdd-validate` applies
  `sdd:spike-resolved` to the **spike sub-issue** (one marker, mirroring
  `sdd:dispatched`) and posts the findings comment on the PR. No tracking-issue
  move.
- **disproved or partial** — the assumption did not hold, or held only in part,
  and a human must decide how the plan adapts. `sdd-validate` **parks the
  tracking issue** at `needs-human` with one pointer comment that folds in the
  spike doc's Action items. It does **not** auto-replan and does **not** set
  `sdd:spike-resolved`. A `disproved` or `partial` conclusion always parks the
  tracking issue, even when a completeness Blocker (missing Action items) also
  fired — otherwise the plan would wedge forever on a disproven-but-untidy doc.

## Re-entry: phase B when the wave drains

Phase B's natural trigger — the architecture PR merging — already fired before
any spike existed, so a draining wave cannot re-fire phase B through a real
webhook. The `sdd-spike-reentry` wrapper synthesizes that re-entry. When a
`kind:spike` child of a triage tracking issue closes (its experiment resolved),
or a parked spike's `needs-human` is cleared, and **zero** open `kind:spike`
children remain, the wrapper re-enters `sdd-triage` phase B for the tracking
issue. On re-entry, each resolved spike's written finding (its
`proof-of-resolution`, read from the closed spike sub-issue) folds into the plan
as settled ground, and phase B composes and posts the plan comment.

Phase B and phase C both **hold** while any open `kind:spike` child exists:
phase B posts no plan comment, and phase C — the backstop for a `/approve` typed
against a stale plan — emits no Unit or task tree. Clearing `needs-human` on a
parked spike does **not** re-run the failed experiment (the actuator fires only
on opened/labeled, never on unlabeled); it only lets the re-entry re-check the
wave, and phase B proceeds only once the wave is genuinely drained to zero open
spikes. A still-open parked spike leaves the wave armed, and the human who
cleared the label owns the next move on that spike.

The re-entry wrapper is deterministic in its drain check and fails closed: on any
listing error it treats the wave as not drained, so the failure mode is "phase B
re-entry delayed", never "plan posted on an undrained wave". A missed drain is
recovered by the next spike-close event, or by an operator `/revise`.

## The park path

When the experiment needs runtime or hardware the sandbox lacks, or a guardrail
denies an action it requires, the spike **parks** rather than fabricating a
result:

- It commits a **partial** doc with `status: parked`, recording Question,
  Hypothesis, and Method as usual and, in Findings, quoting the denial or the
  missing capability **verbatim** as the evidence for why the experiment could
  not finish. It never invents results, measurements, or a conclusion the
  evidence does not support.
- It queues the remaining work as follow-up spikes in the doc's Action items.
- It hands off via the `needs-human` contract: applies `needs-human` to the
  spike sub-issue and posts exactly one comment quoting the same denial.

A parked spike opens a **normal (non-draft) pull request**, not a literal GitHub
draft. The suite's `create-pull-request` safe-output is configured with
`draft: false` statically and cannot be set per call, so a parked spike's PR is a
normal pull request that needs a human. The `status: parked` doc plus the
`needs-human` label together carry the same "do not merge yet" signal a draft
would — state this in the PR summary, since any description that calls the parked
state a "draft PR" is wrong for this suite.
