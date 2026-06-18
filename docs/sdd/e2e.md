# End-to-end pipeline testing

`e2e-dispatch` drives a synthetic feature through the full SDD lifecycle on a
dedicated **staging repo**, asserts the terminal state, and reports duration and
a coarse cost estimate. It runs on `/e2e` from a write-access author and nightly
on a schedule. See [#89](https://github.com/norrietaylor/spectacles/issues/89).

## How it works

1. A write-access author comments `/e2e [scenario]` on a spectacles issue or PR
   (or the nightly schedule fires with the default scenario).
2. The dispatcher installs the SDD suite onto the staging repo with
   `quick-setup.sh --ref <pr-head-sha>`, pinning the staging wrappers to the
   spectacles ref under test. The staging wrappers call the hosted locks via
   `uses: …@<ref>`, so the staging run exercises the PR's code — no lock push.
3. It seeds a synthetic tracking issue from
   `tests/fixtures/e2e/<scenario>/issue.md` (≤ 50 tokens to bound cost), with
   the labels declared in that scenario's `expectations.yml`.
4. It polls the tracking issue's `sdd:*` label until a terminal state
   (`sdd:done`, `needs-human`, or timeout — default 30 min).
5. `scripts/e2e-assert.py` checks the staging state against
   `expectations.yml` (terminal label, artifact files, PRs opened and merged).
6. It posts a summary back on the originating issue/PR (or a dated nightly
   issue): scenario, final state, assertion result, cost, and a link to the
   dispatcher run.

The dispatcher is a plain GitHub Actions workflow (`no` gh-aw agent step); only
the staging agents consume tokens.

## One-time setup

Provision the staging repo once with `scripts/e2e-setup-staging.sh`:

```bash
STAGING_APP_PRIVATE_KEY=… ANTHROPIC_API_KEY=… \
  scripts/e2e-setup-staging.sh --staging norrietaylor/spectacles-staging
```

It clears branch protection on the staging default branch, installs the SDD
suite, and sets repo variables/secrets. It then prints the manual steps it
cannot perform (install the GitHub App on the staging repo; set `OTLP_*`
telemetry secrets per ADR 0020).

## Configuration

Set these on the **spectacles** repo:

| Variable | Purpose | Default |
| --- | --- | --- |
| `SPECTACLES_E2E_STAGING_REPO` | Staging repo as `owner/name`. Required. | — |
| `SPECTACLES_E2E_TIMEOUT_MIN` | Lifecycle poll timeout, minutes. | `30` |
| `SPECTACLES_E2E_DISABLED` | `1`/`true` silences the nightly schedule without a workflow edit. | unset |

## Scenarios

Each scenario is one directory under `tests/fixtures/e2e/`:

```text
tests/fixtures/e2e/<scenario>/
  issue.md           # the synthetic feature body (≤ 50 tokens)
  expectations.yml   # the assertion contract
```

`expectations.yml` keys (all optional):

| Key | Meaning |
| --- | --- |
| `seed_labels` | Labels applied to the seeded tracking issue. |
| `terminal_label` | Required final `sdd:*` label (`null` = none, e.g. needs-human). |
| `require_label` | A label that must be present at terminal state. |
| `forbid_labels` | Labels that must be absent at terminal state. |
| `artifacts` | Globs; each must match ≥ 1 file on the staging default branch. |
| `prs.opened_min` | Minimum PRs opened since the seed. |
| `prs.all_merged` | Every such PR must be merged. |

Shipped: `happy-path-feature`. Planned follow-ups: `happy-path-bug`,
`revise-loop-spec`, `needs-human-handoff` — each adds a fixture directory only,
no dispatcher change.

## Cost

The summary reports staging Actions minutes (summed from the staging repo's
workflow runs since the seed) plus a fixed per-scenario token estimate. Lock
metadata carries no token cost, so the token figure is coarse until a real
usage source is wired (issue #89 follow-up). A typical scenario is under $5.
