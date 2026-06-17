---
id: adr-0027
title: Retrospective spec derivation for unspecced code
kind: adr
status: accepted
supersedes:
superseded-by:
---

# ADR 0027: Retrospective spec derivation for unspecced code

- Status: Accepted
- Date: 2026-06-16

## Context

The SDD pipeline is forward-only: `sdd-spec` authors a spec from a tracking
issue, `sdd-triage` decomposes it, `sdd-execute` implements it. Every agent
downstream of `sdd-spec` assumes a spec already exists.

Developers also explore directly in code. A feature branch opened without a
tracking issue produces a pull request — and, on merge, shipped code — that
carries no spec. `sdd-review` runs on `pull_request: [opened, synchronize]` but
gates to `sdd/` head branches (the `sdd-execute` implementation prefix), so an
exploratory human branch is exactly the case nothing covers. The spec is still
needed in the repo: it is the artifact the team reviews, the source the
requirement-ID checker resolves against, and the entry `distillery-sync`
mirrors into the knowledge store.

There was no path from existing code back to a spec.

## Decision

Add `sdd-derive`, a reverse agent that reads an implemented pull request and
authors a spec retrospectively, plus the deterministic detection and batch
surfaces that route work to it.

1. **Size-gated detection at review time (deterministic).** The `sdd-derive`
   wrapper's `route` + `offer` jobs run on every pull request. When a PR
   **lacks SDD lineage** (head ref not `sdd/`, `spec/`, or `arch/`; body has no
   `Closes #<sub-issue>`; no `docs/specs/**` file references it) **and** its net
   diff is at or above `SDD_SPEC_MIN_UNIT` (default 400, the same floor ADR 0026
   uses), the wrapper posts one offer comment. The check is mechanical — no
   engine — and idempotent: a prior offer comment suppresses a repeat on the
   next `synchronize`. Docs-only diffs and bot authors are excluded.

2. **The derived spec is a separate docs PR.** `sdd-derive` opens a `spec/<slug>`
   pull request adding `docs/specs/NN-spec-<slug>/NN-spec-<slug>.md`, the same
   shape `sdd-spec` produces. A separate PR works whether or not the source PR
   has merged, and keeps the spec reviewable on its own. The spec frontmatter's
   `tracking-issue` is left blank (no tracking issue exists); the source PR is
   named in the spec's Context and linked by a comment on the source PR.

3. **Gaps are documented in-spec, not filed as issues.** Reverse-deriving from
   code surfaces what the code did not do: requirements implied but
   unimplemented, failure paths absent or untested, acceptance criteria the
   behavior only partially satisfies, and demoable units the implementation
   skipped. `sdd-derive` records these in a `## Gap Analysis` section in the
   spec and in `## Open Questions`. It files no follow-up issues — a human reads
   the gaps from the doc and decides whether to open forward SDD work.

4. **Batch is a weekly roll-up plus a maintainer command.** A deterministic
   `sdd-unspecced-scan` workflow runs weekly, applies the same lineage+size
   predicate to recently merged PRs, and upserts one roll-up issue listing every
   unspecced PR. A maintainer with write access derives a set by commenting
   `/derive-spec #12 #34` on that issue (or `/derive-spec` on a single PR);
   the wrapper fans out one `sdd-derive` run per PR through a bounded matrix.
   Ignoring a per-PR offer is the deferral: the weekly roll-up re-surfaces it.

5. **`needs-spec` is an orthogonal marker.** The offer and scan apply a
   `needs-spec` label so the scan can dedupe and humans can filter or suppress
   the offer. It is not a lifecycle state and never participates in an `sdd:*`
   transition.

## Reasoning

- Detection and batch are deterministic walks — does a file exist, is a diff
  over a floor, list merged PRs — so they live in composite actions and a plain
  workflow (ADR 0015, ADR 0011), and the engine cost falls only on the explicit
  `/derive-spec`.
- A separate docs PR, rather than a commit onto the source branch, is the only
  option that works after the source PR merges, which is the common case for
  exploratory code that already shipped.
- Filing gaps in-spec rather than as issues keeps the reverse path advisory and
  single-artifact: it documents reality (including its holes) without spawning a
  backlog the author did not ask for. The forward pipeline remains the place
  work is created.
- The OTLP mandate (ADR 0020) applies: `sdd-derive` carries the observability
  block and its wrapper maps `GH_AW_OTEL_ENDPOINT`. The deterministic
  detection, offer, and scan carry no engine and are exempt.

## Verification

- `wrappers/sdd-derive.yml` routes `/derive-spec` (gated to write access in
  `.github/actions/sdd-route-derive`), offers on a size-gated unspecced PR, and
  fans out a PR set in a bounded matrix.
- `.github/workflows/sdd-derive.md` carries the ADR 0020 OTLP block, imports the
  interaction and MCP fragments, and declares `create-pull-request`
  (`branch-prefix: spec/`), `add-comment`, and `add-labels: [needs-human]`.
- `.github/workflows/sdd-unspecced-scan.yml` runs weekly, lists unspecced merged
  PRs, and upserts one roll-up issue with `/derive-spec` instructions.
- `docs/specs/TEMPLATE.md` carries a `## Gap Analysis` section; a derived spec
  fills it, a forward-authored spec leaves it empty.
- `templates/.github/labels.yml` defines `needs-spec`.

## Consequences

- A new agent (`sdd-derive`), its wrapper, two composite actions
  (`sdd-route-derive`, `sdd-scan-unspecced`), and one weekly workflow.
- The command vocabulary gains `/derive-spec`; the label catalogue gains
  `needs-spec`.
- The spec template gains a `## Gap Analysis` section, optional for the forward
  path.
- `sdd-derive` authors specs with a blank `tracking-issue`; `sdd-doc-status`
  (ADR 0021) advances status from a tracking issue's labels and therefore does
  not act on a derived spec until a human links one. A derived spec stays at its
  authored `status: planned` until then. This is intended: a retrospective spec
  documents shipped code, not in-flight lifecycle.

## Cross-links

- ADR 0026 — demoable-unit sizing: the `SDD_SPEC_MIN_UNIT` floor reused as the
  detection threshold.
- ADR 0020 — observability mandate: the OTLP block `sdd-derive` carries.
- ADR 0015 — route logic in composite actions: where detection and command
  gating live.
- ADR 0001 — `needs-human`: the failure hand-off `sdd-derive` raises.
