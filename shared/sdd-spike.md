# Spike protocol

A `kind:spike` task is a bounded experiment that resolves a load-bearing
assumption before planning commits to it. Its deliverable is a written
finding, never a code change. This fragment states the spike protocol once so
every agent that executes a spike applies it identically.

This fragment is the canonical source for the spike protocol; an executing
agent inlines its content (a "Spike protocol" subsection) until the fragment is
importable from `@main`, then switches to importing it. Editing it here updates
the canonical text; the inline copies are kept in sync.

## What a spike deliverable is

A `kind:spike` task writes exactly one file: `docs/spikes/<date>-<slug>.md`,
where `<date>` is the spike's open date (`YYYY-MM-DD`) and `<slug>` is a short
hyphenated subject derived from the spike sub-issue's title. It writes **no
other path** — a spike never edits source, config, or any build surface. The
written finding **is** the deliverable.

The branch and pull-request conventions are the **standard implementation
conventions** from the imported repository-conventions fragment, with no spike
exception:

- The branch is `sdd/<spike-issue-id>-<slug>` — the same
  `sdd/<task-id>-<slug>` convention every implementation PR uses. **Never** use
  a custom `sdd/spike-` prefix or any other branch shape. A non-standard prefix
  breaks the in-flight branch regex (`^sdd/(\d+)-`) that `sdd-dispatch-compute`
  and `sdd-route-execute` use to recognise a task already in flight, which
  produces a duplicate pull request for the same spike.
- The pull request body carries `Closes #<spike-issue>` so merging it closes
  the spike sub-issue, exactly as a normal task PR closes its task.
- The commit subject and PR title use the conventional-commit type `docs`
  (the `kind:spike` → `docs` mapping from the repository-conventions fragment),
  since a spike's deliverable is its written finding, not a code change.

## The doc format

`docs/spikes/<date>-<slug>.md` carries YAML frontmatter followed by a fixed set
of sections.

Frontmatter fields:

- `id` — the spike sub-issue number.
- `title` — the spike's one-line subject.
- `status` — one of `proved`, `disproved`, `partial`, or `parked`.
- `date` — the spike's open date (`YYYY-MM-DD`).
- `authors` — the executing agent and any human collaborators.
- `budget_hours` — the time box the spike was given.
- `actual_hours` — the time the experiment actually took.
- `related` — issues, PRs, or ADRs the spike informs.
- `tags` — free-form topic tags.

Body sections, in order:

- **Question** — the load-bearing assumption the spike resolves, stated as a
  question.
- **Hypothesis** — the expected answer before the experiment ran.
- **Method** — how the experiment was run, reproducibly.
- **Findings** — what was observed, **with evidence**: the exact commands run
  and their output, measurement tables, and links to the sources inspected.
  Every claim carries its evidence inline, per the imported evidence-rigor
  standard.
- **Conclusion** — the verdict: `proved`, `disproved`, or `partial`. A spike
  **may** partially resolve its question and queue follow-up spikes for the
  remainder; that is a `partial` conclusion, not a failure.
- **Action items** — what the finding changes downstream, grouped as: spec
  amendments, ADR follow-ups, risk-register entries, and follow-up spikes.
- **Artifacts** — the concrete proof: command transcripts, measurement files,
  and source links that a reader can re-run or re-inspect.

The doc write **is** the File-type proof artifact: the committed
`docs/spikes/<date>-<slug>.md`, asserted to exist and to carry the required
sections, satisfies the empty-PR/proof rule directly (see
`sdd-proof-artifacts.md`). A spike PR is therefore **exempt** from the
empty-PR/proof rule's normal demand for a behavior-demonstrating artifact — not
a bypass of it: the doc is itself the File artifact, and a PR carrying it is
never empty.

## The park path

When the experiment needs runtime or hardware the sandbox lacks, or a guardrail
denies an action the experiment requires, the spike **parks** rather than
fabricating a result:

- Commit a **partial** doc with `status: parked`. Record the question,
  hypothesis, and method as usual; in Findings, quote the denial or the missing
  capability **verbatim** as the evidence for why the experiment could not run
  to completion. Never invent results, measurements, or a conclusion the
  evidence does not support.
- Queue the remaining work as follow-up spikes in the doc's Action items.
- Hand off via the imported `needs-human` contract: apply `needs-human` to the
  spike sub-issue (`add-labels`) and post exactly **one** comment that quotes
  the same denial. The human takes over from there; clearing `needs-human`
  resumes the spike (the standard resume-on-removal contract).

The `create-pull-request` safe-output is configured with `draft: false` and is
static — it cannot be set per call — so a parked spike opens a **normal**
(non-draft) pull request carrying the `status: parked` doc plus the
`needs-human` hand-off. State this in the PR-facing summary: the parked PR is a
normal GitHub pull request that needs a human, **not** a literal GitHub draft
PR. This is a deliberate deviation from any description that calls the parked
state a "draft PR" — the deviation is the static `draft: false` config, and the
parked doc plus `needs-human` carries the same "do not merge yet" signal a
draft would.

## Verification

- A spike PR's diff lists only `docs/spikes/` paths; it touches no source,
  config, or build surface.
- The spike branch matches `sdd/<spike-issue-id>-<slug>`, never an
  `sdd/spike-` prefix.
- The committed `docs/spikes/<date>-<slug>.md` carries the frontmatter fields
  and the Question / Hypothesis / Method / Findings / Conclusion / Action items
  / Artifacts sections.
- A parked spike commits a `status: parked` partial doc, quotes the denial
  verbatim, applies `needs-human`, and opens a normal (non-draft) pull request.
