#!/usr/bin/env bash
# Smoke test for issue #163. The sdd-execute host post-step runs `cargo fmt
# --all` on the agent's patch so the PR opens already satisfying a Rust
# consumer's `cargo fmt --all -- --check` gate. That only holds if the host's
# stable rustfmt can parse and normalize the same constructs the consumer's
# stable rustfmt does. An edition-2024 `let`-chain is the construct that broke
# it: an older host rustfmt silently failed to format it (the post-step guard
# swallowed the non-zero exit) and shipped non-canonical code the consumer
# rejected. This test pins that assumption as a PR gate against the fixture
# under tests/fixtures/fmt-letchain.
set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)
fixture="${repo_root}/tests/fixtures/fmt-letchain"

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
cp -R "${fixture}/." "${work}/"
cd "$work"

# 1. The fixture must be genuinely non-canonical, or the test is vacuous.
if cargo fmt --all -- --check >/dev/null 2>&1; then
  echo "FAIL: fixture is already rustfmt-clean; it cannot detect a fmt regression. Re-introduce non-canonical formatting in tests/fixtures/fmt-letchain/src/lib.rs." >&2
  exit 1
fi

# 2. cargo fmt must parse and format the edition-2024 let-chain (exit 0). A
#    rustfmt too old to parse the let-chain exits non-zero here — the #163
#    failure mode.
if ! cargo fmt --all; then
  echo "FAIL: 'cargo fmt --all' could not format the edition-2024 let-chain fixture; the rustfmt toolchain is too old (#163)." >&2
  exit 1
fi

# 3. The formatted result must satisfy the consumer's exact gate.
if ! cargo fmt --all -- --check; then
  echo "FAIL: 'cargo fmt --all -- --check' still reports a diff after formatting (#163)." >&2
  exit 1
fi

echo "ok: stable rustfmt parses and normalizes the edition-2024 let-chain fixture"
