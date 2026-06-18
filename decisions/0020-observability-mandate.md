---
id: adr-0020
title: Every agent workflow exports OTLP telemetry
kind: adr
status: accepted
supersedes:
superseded-by:
---

# ADR 0020: Every agent workflow exports OTLP telemetry

- Status: Accepted
- Date: 2026-06-05

## Context

The SDD suite runs LLM agents as hosted reusable workflows across consumer
repositories, with no central view of token spend, run duration, or outcome
rates. Each agent is a gh-aw source (`.github/workflows/<agent>.md`) compiled to
a self-contained lock that a consumer invokes cross-owner by `uses:` (ADR 0004).
gh-aw v0.77.5 emits an `observability.otlp` frontmatter block that, on compile,
inlines OTLP span export — token usage, duration, outcomes — into the lock: a
workflow-level `OTEL_*` env, the collector host in the firewall allowlist, an
MCP-gateway `opentelemetry` block, an observability-summary step, and an
`otel.jsonl` artifact.

Because the agent runs inside the **hosted** lock, baking OTLP into the
spectacles sources and recompiling the spectacles locks delivers telemetry to
every consumer on its next `@main` run — no consumer recompile. One seam needs a
consumer action: cross-owner `workflow_call` does not inherit secrets, so the
endpoint secret reaches the lock only if each wrapper maps it.

## Decision

1. **Every agent workflow — present and future — must export OTLP spans.** A new
   `.github/workflows/<agent>.md` that declares an `engine:` is not complete
   until it carries the `observability.otlp` block, a `*.run.app` egress entry,
   and a `secret-masking` step redacting the endpoint from artifacts, and its
   wrapper maps `GH_AW_OTEL_ENDPOINT` into the called lock's `secrets:`.

2. **The endpoint is a secret, not a variable.** `observability.otlp.endpoint`
   reads `${{ secrets.GH_AW_OTEL_ENDPOINT }}`. A secret is log-masked; a
   repository variable is not, and the URL embeds an ingest key. The cost — each
   wrapper must map the secret, and a consumer takes the updated wrapper once —
   is accepted.

3. **Auth is write-only and headerless.** The secret URL embeds a write-only
   ingest key, so a leak can push spans but never read telemetry. No auth header
   is sent: `observability.otlp.headers` emits invalid YAML in the safe-outputs
   job on gh-aw (`github/gh-aw#37067`), and headerless sidesteps it.

   The endpoint value is masked twice: GitHub Actions auto-masks the secret in
   job logs, and a `secret-masking` step scrubs it from the `/tmp/gh-aw`
   artifact tree before upload. gh-aw's built-in redaction (`GH_AW_SECRET_NAMES`)
   covers only the engine/GitHub tokens, not `observability.otlp.endpoint`, so
   the custom step is required — the built-in pass alone leaves the URL
   recoverable in uploaded artifacts.

4. **A missing secret degrades, never fails.** `if-missing: warn` makes a
   consumer that has not set `GH_AW_OTEL_ENDPOINT` run clean with a warning, so
   the wrapper change is backward-safe and telemetry is opt-in per consumer.

5. **Deterministic utility workflows are exempt.** `sdd-monitor`,
   `sdd-pr-sanitize`, and the triage backstops carry no `engine:` and emit no
   agent spans; the mandate covers `engine:`-bearing agents only.

## Reasoning

- The hosted-lock model (ADR 0004) is what makes a fleet-wide change a source
  edit plus a recompile rather than a re-install on every consumer. The mandate
  rides that property.
- A variable would have removed the wrapper change entirely, but unmasked
  credential material in Actions logs outweighs the convenience for a
  write-scoped key whose blast radius is already bounded.
- The collector host is fixed at bake time (`*.run.app`) because the firewall
  allowlist is compiled into the lock and cannot read a consumer variable at run
  time. Standardizing the collector on Cloud Run keeps one allowlist entry.

## Verification

- Every `.github/workflows/*.md` with `engine:` contains an `observability.otlp`
  block with `endpoint: ${{ secrets.GH_AW_OTEL_ENDPOINT }}` and `if-missing:
  warn`, and lists `*.run.app` under `network.allowed`.
- Every wrapper that calls a `.lock.yml` maps `GH_AW_OTEL_ENDPOINT` in its
  `secrets:` block.
- After `recompile-locks`, each lock carries the workflow-level `OTEL_*` env,
  `*.run.app` in the firewall allowlist, the MCP-gateway `opentelemetry` block,
  the observability-summary step, and `otel.jsonl` in its artifact list.
- Each lock has a `Redact OTLP endpoint from artifacts` step ordered after the
  built-in `Redact secrets in logs` step and before `Upload agent artifacts`.
- `distillery-sync`'s recompiled lock still carries the `DISTILLERY_MCP_URL`
  host in its allowlist: the explicit `network:` block added for OTLP must not
  drop the MCP host gh-aw injects from `mcp-servers`.

## Consequences

- A one-time consumer wrapper update (`quick-setup.sh --suite sdd`) is required
  to pick up the secret map; thereafter suite updates remain ref bumps (ADR
  0004).
- Operators must stand up an OTLP collector on a `*.run.app` host and set
  `GH_AW_OTEL_ENDPOINT` (write-only key embedded) to receive telemetry; unset
  leaves agents unaffected.
- The mandate is a review gate: a new agent that omits the block or the wrapper
  map is incomplete.

## Cross-links

- ADR 0004 — the inlined-imports / `uses:` distribution model that lets a source
  edit reach consumers without a recompile.
- ADR 0019 — the auto-recompile that regenerates the locks carrying the OTLP
  inlining once the sources merge.
- A consumer's in-repo OTLP precedent (write path) — this adapts that to the
  cross-owner reusable-workflow model.
