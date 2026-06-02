---
# Host-side Rust cleanup, post-agent, pre-PR. The agent edits Rust from inside
# the firewalled container (no crates.io egress, no Rust toolchain) so it cannot
# run `cargo fmt`/`clippy`/`update` to self-verify; the safe-output patch carries
# rustfmt-dirty, clippy-dirty code and a stale Cargo.lock. Any consumer CI that
# runs `cargo fetch --locked`, `fmt --check`, or `clippy -D warnings` rejects the
# PR (first seen on gominimal/minspec-test#20, #26). These post-steps run on the
# host runner (outside the firewall sandbox, per gh-aw's post-steps contract),
# detect a Rust edit (*.rs or Cargo.toml) in the agent's patch, install the Rust
# toolchain (with rustfmt + clippy components) on the host, then in a single
# refresh: run `cargo update --workspace` (when a Cargo.toml changed),
# `cargo fmt --all`, and `cargo clippy --fix` (machine-applicable lints only),
# amend the agent's last commit with whatever changed, and re-emit the patch +
# bundle transport files that the safe_outputs job replays. The toolchain step
# is gated on the patch actually touching Rust — no install on doc-only or
# non-Rust task runs. The amend lands inside the agent's existing commit, so
# gh-aw's signed-commit push (ADR 0004) re-attributes the cleanup to the App
# identity at PR-create time. Genuine compile errors and non-machine-applicable
# lints are NOT masked: this only applies `--fix`-safe changes (issue #158).
# Dead-code suppression is out of scope (#158 non-goal) — `clippy --fix` never
# adds `#[allow(dead_code)]` or gates a module.
#
# This fragment is imported by the three sdd-execute tier sources (haiku,
# sonnet, opus) via the pinned-ref form
# `norrietaylor/spectacles/shared/sdd-rust-cleanup.md@<ref>` (ADR 0002),
# replacing the block that was previously duplicated inline in all three
# (#176). Editing it requires `gh aw compile` to propagate into the inlined
# locks; the lint workflow's drift gate enforces that.
post-steps:
  - name: Detect Rust edits in the agent's patch
    id: cargo_detect
    shell: bash
    run: |
      set -euo pipefail
      tmpdir=/tmp/gh-aw
      # Scan every aw-*.patch (a run may emit a create_pull_request and a
      # push_to_pull_request_branch in the same job; pick the patch that
      # touches Rust — *.rs or Cargo.toml). The trailing-boundary on the
      # regex avoids substring matches like `Cargo.toml.bak`; a `.rs` edit
      # gates fmt/clippy even when no manifest changed. `cargo_toml` records
      # whether a manifest changed so the refresh step runs `cargo update`
      # (lock refresh) only then.
      shopt -s nullglob
      matched_patch=""
      matched_count=0
      cargo_toml=false
      for f in "${tmpdir}/aw-"*.patch; do
        if grep -qE '^diff --git .*(\.rs|Cargo\.toml)([[:space:]]|$)' "$f"; then
          matched_patch="$f"
          matched_count=$((matched_count + 1))
          if grep -qE '^diff --git .*Cargo\.toml([[:space:]]|$)' "$f"; then
            cargo_toml=true
          fi
        fi
      done
      shopt -u nullglob
      if [ "$matched_count" -eq 0 ]; then
        echo "No agent patch touches Rust; cargo cleanup is a no-op."
        echo "changed=false" >> "$GITHUB_OUTPUT"
        exit 0
      fi
      if [ "$matched_count" -gt 1 ]; then
        echo "::error::Multiple aw-*.patch files touch Rust; refusing to guess which to clean up."
        exit 1
      fi
      patch_file="$matched_patch"
      # The patch filename's branch token is sanitized (slashes → dashes)
      # by gh-aw's getPatchPath, so it does not round-trip to a git ref.
      # Read the current HEAD instead: by post-step time the agent has
      # already committed and switched to its sdd/<task-id>-<slug> branch,
      # so HEAD names the real ref the patch came from.
      branch=$(git rev-parse --abbrev-ref HEAD)
      if [ "$branch" = "HEAD" ]; then
        echo "Detached HEAD at post-step time; skipping cargo cleanup."
        echo "changed=false" >> "$GITHUB_OUTPUT"
        exit 0
      fi
      # The bundle file mirrors the patch filename — derive the same
      # sanitized stem rather than the live branch name.
      bundle_stem=$(basename "$patch_file" .patch)
      bundle_file="${tmpdir}/${bundle_stem}.bundle"
      [ -f "$bundle_file" ] || bundle_file=""
      echo "Agent patch ${patch_file} touches Rust (cargo_toml=${cargo_toml}); will run cargo cleanup."
      {
        echo "changed=true"
        echo "cargo_toml=${cargo_toml}"
        echo "patch_file=${patch_file}"
        echo "bundle_file=${bundle_file}"
        echo "branch=${branch}"
      } >> "$GITHUB_OUTPUT"
  - name: Install Rust toolchain (host)
    if: steps.cargo_detect.outputs.changed == 'true'
    uses: dtolnay/rust-toolchain@29eef336d9b2848a0b548edc03f92a220660cdb8 # stable
    with:
      toolchain: stable
      components: rustfmt, clippy
  - name: Refresh Cargo.lock, format, and lint-fix the agent patch
    if: steps.cargo_detect.outputs.changed == 'true'
    shell: bash
    env:
      AGENT_BRANCH: ${{ steps.cargo_detect.outputs.branch }}
      AGENT_PATCH: ${{ steps.cargo_detect.outputs.patch_file }}
      AGENT_BUNDLE: ${{ steps.cargo_detect.outputs.bundle_file }}
      CARGO_TOML_CHANGED: ${{ steps.cargo_detect.outputs.cargo_toml }}
    run: |
      set -euo pipefail
      # Pick the base ref the patch was generated against. Mirror the
      # precedence gh-aw's generate_git_patch.cjs uses: GITHUB_BASE_REF on
      # PR events; otherwise the repository's default branch (gh-aw exports
      # DEFAULT_BRANCH at the agent job's env block, derived from
      # github.event.repository.default_branch). Hardcoding "main" would
      # break repos whose default branch is master/trunk/main-line/etc.
      base_ref="${GITHUB_BASE_REF:-}"
      if [ -z "$base_ref" ]; then
        base_ref="$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null \
                    | sed 's@^origin/@@' || true)"
      fi
      if [ -z "$base_ref" ]; then
        base_ref="${DEFAULT_BRANCH:-main}"
      fi
      git fetch --no-tags --depth=1 origin "$base_ref" || \
        git fetch --no-tags origin "$base_ref"
      base_sha=$(git merge-base "origin/${base_ref}" "$AGENT_BRANCH")
      echo "Base ref: ${base_ref} (sha=${base_sha})"
      echo "Agent branch: ${AGENT_BRANCH}"
      git checkout "$AGENT_BRANCH"
      # Enumerate the directories the agent touched that are cargo invocation
      # points: every changed Cargo.toml's dir, plus every changed *.rs file's
      # dir. cargo walks up to find the workspace root, so running it from any
      # member works. The empty-string-to-"." mapping covers a root-level path
      # whose diff entry has no directory prefix.
      mapfile -t touched_dirs < <(
        git diff --name-only "${base_sha}..HEAD" \
          | awk '
              /Cargo\.toml$/ { sub(/\/?Cargo\.toml$/, ""); print ($0=="" ? "." : $0) }
              /\.rs$/         { sub(/\/?[^\/]+\.rs$/, ""); print ($0=="" ? "." : $0) }
            ' \
          | sort -u
      )
      if [ "${#touched_dirs[@]}" -eq 0 ]; then
        echo "No Rust paths in the diff after recheck; skipping cargo cleanup."
        exit 0
      fi
      # Resolve each touched dir to its workspace root so fmt/clippy run once
      # per workspace, not once per touched member. Run `cargo locate-project
      # --workspace` from inside each touched dir: cargo's default discovery
      # walks up to the enclosing Cargo.toml and `--workspace` resolves it to
      # the workspace-root Cargo.toml; its dir is the invocation point. (The
      # `--manifest-path "$dir/Cargo.toml"` form would require that exact file
      # to exist, which it doesn't for a *.rs-derived dir like crates/foo/src.)
      # Skip dirs cargo can't resolve (e.g. a path outside any cargo project).
      declare -A seen_roots=()
      ws_roots=()
      for dir in "${touched_dirs[@]}"; do
        [ -d "$dir" ] || continue
        root_manifest="$(
          cd "$dir" && cargo locate-project --workspace --message-format plain 2>/dev/null
        )" || true
        [ -n "$root_manifest" ] || continue
        root_dir="$(dirname "$root_manifest")"
        if [ -z "${seen_roots[$root_dir]:-}" ]; then
          seen_roots[$root_dir]=1
          ws_roots+=("$root_dir")
        fi
      done
      if [ "${#ws_roots[@]}" -eq 0 ]; then
        echo "No resolvable cargo workspace from the touched dirs; skipping cleanup."
        exit 0
      fi
      echo "Cargo workspace roots to clean up:"
      printf '  %s\n' "${ws_roots[@]}"
      # Refresh the lockfile first (only when a manifest changed): a stale
      # Cargo.lock breaks `cargo fetch --locked` (#153). Run cargo update from
      # each touched manifest dir so workspace-root locks above a member crate
      # are caught too.
      if [ "$CARGO_TOML_CHANGED" = "true" ]; then
        mapfile -t manifest_dirs < <(
          git diff --name-only "${base_sha}..HEAD" \
            | awk '/Cargo\.toml$/ { sub(/\/?Cargo\.toml$/, ""); print ($0=="" ? "." : $0) }' \
            | sort -u
        )
        for dir in "${manifest_dirs[@]}"; do
          [ -d "$dir" ] || continue
          ( cd "$dir" && cargo update --workspace )
        done
      fi
      # Format and apply machine-applicable clippy fixes per workspace. fmt
      # rewrites whitespace/layout; `clippy --fix` rewrites only lints rustc
      # marks machine-applicable (collapsible_if, redundant clones, etc.).
      # Both operate on the whole workspace (`--all` / `--workspace`), so one
      # run per root covers every member. Both are best-effort: a genuine
      # compile error (or code rustfmt cannot parse) makes the tool exit
      # non-zero, but it leaves the source untouched (no false "fixed"), so the
      # dirty code still surfaces for the consumer CI / human rather than being
      # masked (#158). A tool failure must not abort the post-step — that would
      # block PR creation and lose the agent's work — so each is guarded.
      for root in "${ws_roots[@]}"; do
        ( cd "$root" && cargo fmt --all ) || \
          echo "::warning::cargo fmt --all in ${root} exited non-zero (likely unparseable source); leaving formatting for consumer CI."
        ( cd "$root" && cargo clippy --fix --allow-dirty --allow-staged \
            --workspace --all-targets ) || \
          echo "::warning::cargo clippy --fix in ${root} exited non-zero (likely a non-machine-applicable lint or compile error); leaving those for consumer CI."
      done
      # Self-verify against the consumer's exact fmt gate, and self-heal a
      # host/consumer rustfmt skew. The host `cargo fmt` above and the consumer
      # CI both run stable rustfmt with the edition derived from Cargo.toml, so
      # they normally agree — but when the host's stable rustfmt is older than
      # the consumer's at run time and cannot format a construct the consumer's
      # newer rustfmt rewrites (an edition-2024 `let`-chain is the observed
      # case), the `cargo fmt` above exits non-zero, its guard swallows that,
      # and unformatted code would ship green and then fail the consumer's
      # `cargo fmt --all -- --check` (#163). Detect that with the consumer's
      # exact check; on any divergence, refresh the toolchain to the current
      # stable (matching the fresh `dtolnay/rust-toolchain@stable` the consumer
      # CI installs) and re-format, so the PR opens already passing. A
      # still-residual diff after the refresh is surfaced as a loud ::error::,
      # never a non-zero exit (which would block PR creation and lose the
      # agent's work).
      needs_heal=false
      for root in "${ws_roots[@]}"; do
        ( cd "$root" && cargo fmt --all -- --check ) >/dev/null 2>&1 || needs_heal=true
      done
      if [ "$needs_heal" = "true" ]; then
        echo "::warning::Host rustfmt output diverges from 'cargo fmt --all -- --check' (likely a stale host stable rustfmt vs the consumer's edition-2024 let-chain formatting; #163). Refreshing the toolchain and re-formatting."
        rustup update stable || \
          echo "::warning::rustup update stable failed; re-formatting with the installed toolchain."
        for root in "${ws_roots[@]}"; do
          ( cd "$root" && cargo fmt --all ) || \
            echo "::warning::cargo fmt --all in ${root} exited non-zero after the toolchain refresh; leaving formatting for consumer CI."
        done
        for root in "${ws_roots[@]}"; do
          if ! fmt_check_out=$( cd "$root" && cargo fmt --all -- --check 2>&1 ); then
            echo "::error::Host rustfmt still leaves ${root} non-canonical after a toolchain refresh; the consumer's 'cargo fmt --all -- --check' will fail this PR (#163)."
            printf '%s\n' "$fmt_check_out"
          fi
        done
      fi
      # Collect every tracked file the cleanup changed (refreshed locks,
      # reformatted sources/manifests, clippy-fixed sources) and stage them.
      mapfile -t changed_files < <( git diff --name-only | sort -u )
      if [ "${#changed_files[@]}" -eq 0 ]; then
        echo "cargo cleanup produced no change; nothing to amend."
        exit 0
      fi
      echo "Files to stage:"
      printf '  %s\n' "${changed_files[@]}"
      git add -- "${changed_files[@]}"
      # Amend the agent's last commit so the cleanup travels with the agent's
      # change. gh-aw's signed-commit push (ADR 0004) re-attributes the
      # resulting commit to the App identity at PR-create time, so the cleanup
      # inherits agent-authored attribution.
      git commit --amend --no-edit
      # Regenerate the format-patch transport so the safe_outputs job
      # replays the amended history. Match gh-aw's generate_git_patch.cjs:
      # full mode, --stdout to one file.
      git format-patch --stdout "${base_sha}..HEAD" > "$AGENT_PATCH"
      echo "Rewrote ${AGENT_PATCH} ($(wc -c < "$AGENT_PATCH") bytes)"
      # Regenerate the bundle when bundle transport is in use (gh-aw's
      # default patch-format). Mirror generate_git_bundle.cjs:
      #   git bundle create <bundle> <base>..<branch>
      if [ -n "$AGENT_BUNDLE" ]; then
        git bundle create "$AGENT_BUNDLE" "${base_sha}..${AGENT_BRANCH}"
        echo "Rewrote ${AGENT_BUNDLE} ($(wc -c < "$AGENT_BUNDLE") bytes)"
      fi
---

## Host-side Rust cleanup post-step

This fragment carries the post-agent, pre-PR host cleanup that lets `sdd-execute`
open implementation pull requests a Rust consumer's CI accepts without manual
fixup. The agent edits Rust from inside gh-aw's network-restricted container,
which has no crates.io egress and no Rust toolchain, so it cannot run
`cargo fmt`, `cargo clippy`, or `cargo update` to self-verify. The safe-output
patch therefore carries rustfmt-dirty, clippy-dirty code and a stale
`Cargo.lock`, which a consumer's `fmt --check`, `clippy -D warnings`, or
`cargo fetch --locked` gate rejects (issues #153, #158, #160).

The `post-steps` run on the GitHub runner, outside the firewall sandbox, after
the agent and before `safe_outputs` materializes the PR. When the agent's patch
touches Rust (`*.rs` or `Cargo.toml`) they install the Rust toolchain, refresh
the lockfile when a manifest changed, run `cargo fmt --all` and
`cargo clippy --fix` (machine-applicable lints only), amend the agent's commit
with whatever changed, and re-emit the patch and bundle transport files. The
amend lands inside the agent's existing commit, so gh-aw's signed-commit push
re-attributes the cleanup to the App identity (ADR 0004).

### Fmt self-heal

After formatting, the step re-runs the consumer's exact gate
(`cargo fmt --all -- --check`). When the host's stable rustfmt diverges from
the consumer's — the observed case is an edition-2024 `let`-chain a newer
rustfmt rewrites — it refreshes the toolchain to the current stable and
re-formats, so the PR opens already passing rather than failing the consumer's
fmt-check (issue #163). The whole block is best-effort: a genuine compile error
or non-machine-applicable lint is left untouched (not masked, #158) and never
aborts the post-step, which would block PR creation and lose the agent's work.

### Out of scope

Dead-code suppression (#158 non-goal): `clippy --fix` never adds
`#[allow(dead_code)]` or gates a module. Test execution is the consumer CI's job
(#154). Non-Rust formatters are follow-ups.
