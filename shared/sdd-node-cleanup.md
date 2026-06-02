---
# Host-side Node/TypeScript cleanup, post-agent, pre-PR. The agent edits TS/JS
# from inside the firewalled container (no npm-registry egress, no Node
# toolchain) so it cannot run `prettier --write`/`eslint --fix` or refresh the
# lockfile to self-verify; the safe-output patch carries prettier-dirty,
# eslint-dirty code and a stale lockfile. Any consumer CI that runs
# `prettier --check`, `eslint`, or an install with a frozen lockfile
# (`npm ci`, `pnpm install --frozen-lockfile`, `yarn install --frozen-lockfile`)
# rejects the PR — the Node analog of the Rust failure mode #160 fixed. These
# post-steps run on the host runner (outside the firewall sandbox, per gh-aw's
# post-steps contract), detect a Node edit (*.ts/*.tsx/*.js/*.jsx/*.mjs/*.cjs
# or package.json) in the agent's patch, install Node on the host, then in a
# single refresh: detect the consumer's package manager from the lockfile
# present (npm/pnpm/yarn), refresh that lockfile (when package.json changed),
# run the consumer's own prettier and eslint fixers (only when the consumer
# declares them — never a hardcoded default), amend the agent's last commit
# with whatever changed, and re-emit the patch + bundle transport files that
# the safe_outputs job replays. The toolchain step is gated on the patch
# actually touching Node — no install on doc-only or non-Node task runs. The
# amend lands inside the agent's existing commit, so gh-aw's signed-commit push
# (ADR 0004) re-attributes the cleanup to the App identity at PR-create time.
# Tool/registry egress stays on the host runner only: the agent container's
# firewall is never widened (consistent with #152/#153 and the Rust analog).
# Best-effort + self-heal posture mirrors shared/sdd-rust-cleanup.md (#163):
# a fixer that exits non-zero never aborts the post-step (that would block PR
# creation and lose the agent's work); a residual diff after the consumer's own
# check is surfaced loudly rather than masked.
#
# This fragment is the Node analog of shared/sdd-rust-cleanup.md. It is imported
# by the three sdd-execute tier sources (haiku, sonnet, opus) via the pinned-ref
# form `norrietaylor/spectacles/shared/sdd-node-cleanup.md@<ref>` (ADR 0002).
# Editing it requires `gh aw compile` to propagate into the inlined locks; the
# lint workflow's drift gate enforces that.
post-steps:
  - name: Detect Node edits in the agent's patch
    id: node_detect
    shell: bash
    run: |
      set -euo pipefail
      tmpdir=/tmp/gh-aw
      # Scan every aw-*.patch (a run may emit a create_pull_request and a
      # push_to_pull_request_branch in the same job; pick the patch that
      # touches Node). The trailing-boundary on the regex avoids substring
      # matches like `package.json.bak`; a source edit gates the fixers even
      # when no manifest changed. The refresh step recomputes which roots had a
      # package.json change per-root from the diff, so this step only needs to
      # decide whether the patch touches Node at all.
      shopt -s nullglob
      matched_patch=""
      matched_count=0
      node_glob='\.(ts|tsx|js|jsx|mjs|cjs)|package\.json'
      for f in "${tmpdir}/aw-"*.patch; do
        if grep -qE "^diff --git .*(${node_glob})([[:space:]]|$)" "$f"; then
          matched_patch="$f"
          matched_count=$((matched_count + 1))
        fi
      done
      shopt -u nullglob
      if [ "$matched_count" -eq 0 ]; then
        echo "No agent patch touches Node; node cleanup is a no-op."
        echo "changed=false" >> "$GITHUB_OUTPUT"
        exit 0
      fi
      if [ "$matched_count" -gt 1 ]; then
        echo "::error::Multiple aw-*.patch files touch Node; refusing to guess which to clean up."
        exit 1
      fi
      patch_file="$matched_patch"
      # The patch filename's branch token is sanitized (slashes → dashes) by
      # gh-aw's getPatchPath, so it does not round-trip to a git ref. Read the
      # current HEAD instead: by post-step time the agent has already committed
      # and switched to its sdd/<task-id>-<slug> branch, so HEAD names the real
      # ref the patch came from.
      branch=$(git rev-parse --abbrev-ref HEAD)
      if [ "$branch" = "HEAD" ]; then
        echo "Detached HEAD at post-step time; skipping node cleanup."
        echo "changed=false" >> "$GITHUB_OUTPUT"
        exit 0
      fi
      # The bundle file mirrors the patch filename — derive the same sanitized
      # stem rather than the live branch name.
      bundle_stem=$(basename "$patch_file" .patch)
      bundle_file="${tmpdir}/${bundle_stem}.bundle"
      [ -f "$bundle_file" ] || bundle_file=""
      echo "Agent patch ${patch_file} touches Node; will run node cleanup."
      {
        echo "changed=true"
        echo "patch_file=${patch_file}"
        echo "bundle_file=${bundle_file}"
        echo "branch=${branch}"
      } >> "$GITHUB_OUTPUT"
  - name: Install Node toolchain (host)
    if: steps.node_detect.outputs.changed == 'true'
    uses: actions/setup-node@48b55a011bda9f5d6aeb4c2d9c7362e8dae4041e # v6.4.0
    with:
      node-version: "22"
  - name: Refresh the lockfile, format, and lint-fix the agent patch
    if: steps.node_detect.outputs.changed == 'true'
    shell: bash
    env:
      AGENT_BRANCH: ${{ steps.node_detect.outputs.branch }}
      AGENT_PATCH: ${{ steps.node_detect.outputs.patch_file }}
      AGENT_BUNDLE: ${{ steps.node_detect.outputs.bundle_file }}
    run: |
      set -euo pipefail
      # Pick the base ref the patch was generated against. Mirror the precedence
      # gh-aw's generate_git_patch.cjs uses: GITHUB_BASE_REF on PR events;
      # otherwise the repository's default branch (gh-aw exports DEFAULT_BRANCH
      # at the agent job's env block). Hardcoding "main" would break repos whose
      # default branch is master/trunk/etc.
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
      # Enumerate the files the agent touched (fixer-relevant extensions plus
      # any package.json). These are the only files the fixers may rewrite —
      # the cleanup is scoped to the patch, never to the whole project tree.
      mapfile -t touched_files < <(
        git diff --name-only "${base_sha}..HEAD" \
          | grep -E '\.(ts|tsx|js|jsx|mjs|cjs)$|(^|/)package\.json$' \
          | sort -u
      )
      if [ "${#touched_files[@]}" -eq 0 ]; then
        echo "No Node paths in the diff after recheck; skipping node cleanup."
        exit 0
      fi
      # Resolve each touched file to its package-manager root: the nearest
      # ancestor directory that holds a lockfile (where install, the pinned
      # prettier/eslint, and their shared config live). A workspace member's
      # touched file (e.g. apps/web/src/x.ts) must resolve to the repo-root
      # lockfile, not apps/web/package.json — otherwise detect_pm finds no
      # lockfile and the cleanup silently skips the monorepo case it exists to
      # cover. Fall back to the nearest enclosing package.json only when no
      # lockfile exists anywhere up the tree (a lockfile-less project gets the
      # fixers but no lockfile refresh).
      find_project_root() {
        local dir="$1" fallback=""
        while :; do
          if [ -f "${dir}/pnpm-lock.yaml" ] || [ -f "${dir}/yarn.lock" ] || \
             [ -f "${dir}/package-lock.json" ] || [ -f "${dir}/npm-shrinkwrap.json" ]; then
            printf '%s\n' "$dir"
            return 0
          fi
          [ -n "$fallback" ] || { [ -f "${dir}/package.json" ] && fallback="$dir"; }
          [ "$dir" = "." ] && break
          dir="$(dirname "$dir")"
          [ "$dir" = "/" ] && dir="."
        done
        [ -n "$fallback" ] && printf '%s\n' "$fallback"
      }
      declare -A seen_roots=()
      project_roots=()
      for f in "${touched_files[@]}"; do
        root="$(find_project_root "$(dirname "$f")")" || true
        [ -n "$root" ] || continue
        if [ -z "${seen_roots[$root]:-}" ]; then
          seen_roots[$root]=1
          project_roots+=("$root")
        fi
      done
      if [ "${#project_roots[@]}" -eq 0 ]; then
        echo "No resolvable Node project (no enclosing lockfile or package.json) from the touched files; skipping cleanup."
        exit 0
      fi
      echo "Node project roots to clean up:"
      printf '  %s\n' "${project_roots[@]}"
      # Record which roots actually had a package.json change in this patch, so
      # the lockfile-refresh decision is per-root, not global: a monorepo where
      # only one workspace's manifest changed must not force the lock-mutating
      # path on every other root.
      declare -A manifest_changed_roots=()
      for f in "${touched_files[@]}"; do
        case "$f" in
          package.json|*/package.json)
            r="$(find_project_root "$(dirname "$f")")" || true
            [ -n "$r" ] && manifest_changed_roots["$r"]=1
            ;;
        esac
      done
      # Detect the consumer's package manager from the lockfile present, never a
      # hardcoded default. Each manager has a distinct lockfile name; gate the
      # lockfile refresh and the fixer invocation on which one exists. A project
      # with no lockfile gets no lockfile refresh (nothing to refresh).
      detect_pm() {
        local root="$1"
        if [ -f "${root}/pnpm-lock.yaml" ]; then echo pnpm; return; fi
        if [ -f "${root}/yarn.lock" ]; then echo yarn; return; fi
        if [ -f "${root}/package-lock.json" ]; then echo npm; return; fi
        if [ -f "${root}/npm-shrinkwrap.json" ]; then echo npm; return; fi
        echo ""
      }
      # Run a binary the consumer declares, through its package manager's runner
      # so the consumer's pinned version is used. The package manager is passed
      # explicitly (not read from an outer-scope variable) so this is correct
      # for every project root, including the post-loop self-verify below.
      run_tool() {
        local pm="$1" r="$2"; shift 2
        case "$pm" in
          pnpm) ( cd "$r" && pnpm exec "$@" ) ;;
          yarn) ( cd "$r" && yarn exec "$@" ) ;;
          npm)  ( cd "$r" && npm exec --no -- "$@" ) ;;
          *)    ( cd "$r" && "./node_modules/.bin/$1" "${@:2}" ) ;;
        esac
      }
      # Run a binary the consumer declares in its own toolchain. Prefer the
      # package manager's runner so the consumer's pinned version is used
      # (`pnpm exec` / `yarn exec` / `npm exec`); each is a no-op cost only when
      # the consumer actually declares the tool. `has_tool` checks the project's
      # node_modules and package.json so a consumer that does not use
      # prettier/eslint pays nothing and the fixer is skipped (no hardcoded
      # default formatter).
      has_tool() {
        local root="$1" tool="$2"
        [ -x "${root}/node_modules/.bin/${tool}" ] && return 0
        # Fall back to a package.json devDependency/dependency declaration so a
        # not-yet-installed tool still counts (the install step below populates
        # node_modules first).
        node -e '
          const fs=require("fs");
          const p=process.argv[1], t=process.argv[2];
          try {
            const j=JSON.parse(fs.readFileSync(`${p}/package.json`,"utf8"));
            const d={...(j.dependencies||{}),...(j.devDependencies||{})};
            process.exit(d[t]?0:1);
          } catch(e){ process.exit(1); }
        ' "$root" "$tool"
      }
      # rel_touched prints the touched files that live under $root, made
      # relative to $root, NUL-terminated — the exact set of files the fixers
      # are allowed to rewrite for this root, so the cleanup never sweeps
      # unrelated tracked files into the amend.
      rel_touched() {
        local root="$1" prefix f
        prefix="${root#./}"
        [ "$prefix" = "." ] && prefix=""
        [ -n "$prefix" ] && prefix="${prefix%/}/"
        for f in "${touched_files[@]}"; do
          case "$f" in
            "${prefix}"*) printf '%s\0' "${f#"$prefix"}" ;;
          esac
        done
      }
      for root in "${project_roots[@]}"; do
        pm="$(detect_pm "$root")"
        root_manifest_changed=false
        [ -n "${manifest_changed_roots[$root]:-}" ] && root_manifest_changed=true
        echo "Project ${root}: package manager = ${pm:-<none>}, manifest changed = ${root_manifest_changed}"
        # Install dependencies first so the consumer's pinned prettier/eslint
        # (and their plugins/configs) resolve. Best-effort: a failed install
        # must not abort the post-step. When this root's package.json changed,
        # refresh the lockfile (a stale lockfile breaks the consumer's frozen
        # install). When it did not, install against the existing lockfile and,
        # on a frozen-install failure, only warn — never fall back to a
        # lock-mutating install that would rewrite a lockfile this patch did not
        # touch.
        case "$pm" in
          pnpm)
            corepack enable >/dev/null 2>&1 || true
            if [ "$root_manifest_changed" = "true" ]; then
              ( cd "$root" && pnpm install --no-frozen-lockfile ) || \
                echo "::warning::pnpm install in ${root} exited non-zero; leaving the lockfile for consumer CI."
            else
              ( cd "$root" && pnpm install --frozen-lockfile ) || \
                echo "::warning::pnpm install --frozen-lockfile in ${root} exited non-zero; leaving deps and the lockfile for consumer CI."
            fi
            ;;
          yarn)
            corepack enable >/dev/null 2>&1 || true
            if [ "$root_manifest_changed" = "true" ]; then
              ( cd "$root" && yarn install ) || \
                echo "::warning::yarn install in ${root} exited non-zero; leaving the lockfile for consumer CI."
            else
              # The lockfile-preserving install flag differs by Yarn major:
              # Yarn Classic (1.x) uses --frozen-lockfile; Yarn Berry (2+) uses
              # --immutable (--frozen-lockfile is only an alias there). Pick by
              # the consumer's own yarn version so a 1.x repo is not failed by a
              # flag it does not understand.
              yarn_major="$( cd "$root" && yarn --version 2>/dev/null | cut -d. -f1 )"
              if [ "${yarn_major:-1}" -ge 2 ] 2>/dev/null; then
                yarn_frozen_flag="--immutable"
              else
                yarn_frozen_flag="--frozen-lockfile"
              fi
              ( cd "$root" && yarn install "$yarn_frozen_flag" ) || \
                echo "::warning::yarn install ${yarn_frozen_flag} in ${root} exited non-zero; leaving deps and the lockfile for consumer CI."
            fi
            ;;
          npm)
            if [ "$root_manifest_changed" = "true" ]; then
              ( cd "$root" && npm install --package-lock-only --no-audit --no-fund ) || \
                echo "::warning::npm install --package-lock-only in ${root} exited non-zero; leaving the lockfile for consumer CI."
              ( cd "$root" && npm install --no-audit --no-fund ) || \
                echo "::warning::npm install in ${root} exited non-zero; leaving deps for consumer CI."
            else
              ( cd "$root" && npm ci --no-audit --no-fund ) || \
                echo "::warning::npm ci in ${root} exited non-zero; leaving deps and the lockfile for consumer CI."
            fi
            ;;
          *)
            echo "Project ${root} has no recognized lockfile; skipping dependency install and lockfile refresh."
            ;;
        esac
        # Build this root's relative touched-file list once; the fixers run only
        # against these files, never the whole tree. Skip the fixers entirely
        # when the root has no touched files (it was reached only via a child
        # root's resolution).
        mapfile -d '' -t root_files < <( rel_touched "$root" )
        if [ "${#root_files[@]}" -eq 0 ]; then
          echo "Project ${root}: no touched files under this root; skipping fixers."
          continue
        fi
        # Format with the consumer's prettier (only when the consumer declares
        # it), scoped to the touched files. Best-effort: a parse error or config
        # problem makes prettier exit non-zero but it leaves the source
        # untouched (no false "fixed"), so the dirty code still surfaces for
        # consumer CI rather than being masked.
        if has_tool "$root" prettier; then
          echo "Project ${root}: running prettier --write on ${#root_files[@]} file(s)"
          run_tool "$pm" "$root" prettier --write -- "${root_files[@]}" || \
            echo "::warning::prettier --write in ${root} exited non-zero (likely a parse/config error); leaving formatting for consumer CI."
        else
          echo "Project ${root}: no prettier declared; skipping formatter."
        fi
        # Apply the consumer's eslint auto-fixes (only when the consumer
        # declares it), scoped to the touched files. `--fix` rewrites only
        # fixable rules; unfixable lint errors are left for consumer CI (not
        # masked). Best-effort guard: eslint exits non-zero when unfixable
        # problems remain, which must not abort the post-step. `--no-error-on-
        # unmatched-pattern` keeps eslint from failing when none of the touched
        # files match its configured patterns.
        if has_tool "$root" eslint; then
          echo "Project ${root}: running eslint --fix on ${#root_files[@]} file(s)"
          run_tool "$pm" "$root" eslint --fix --no-error-on-unmatched-pattern -- "${root_files[@]}" || \
            echo "::warning::eslint --fix in ${root} exited non-zero (unfixable lint or config error); leaving those for consumer CI."
        else
          echo "Project ${root}: no eslint declared; skipping linter."
        fi
      done
      # Self-verify against the consumer's own prettier check (scoped to the
      # touched files) and surface a residual diff. Mirrors the Rust fmt
      # self-heal (#163): a still-non-canonical file is surfaced as a loud
      # ::error::, never a non-zero exit (which would block PR creation and lose
      # the agent's work). node_modules is never committed: it is de-staged
      # below.
      for root in "${project_roots[@]}"; do
        if has_tool "$root" prettier; then
          mapfile -d '' -t root_files < <( rel_touched "$root" )
          [ "${#root_files[@]}" -eq 0 ] && continue
          pm="$(detect_pm "$root")"
          if ! check_out=$( run_tool "$pm" "$root" prettier --check -- "${root_files[@]}" 2>&1 ); then
            echo "::error::prettier --check still reports non-canonical files in ${root}; the consumer's prettier gate will fail this PR."
            printf '%s\n' "$check_out"
          fi
        fi
      done
      # Collect the tracked files the cleanup changed and stage them. The
      # dependency install above writes node_modules and may create it as an
      # untracked dir; only ever stage files git already tracks (refreshed
      # lockfiles, reformatted/lint-fixed sources) plus a newly created lockfile
      # if package.json changed — never node_modules.
      git rm -r --cached --quiet --ignore-unmatch -- '**/node_modules' node_modules >/dev/null 2>&1 || true
      mapfile -t changed_files < <( git diff --name-only -- . ':(exclude)**/node_modules' ':(exclude)node_modules' | sort -u )
      # Stage a newly created lockfile (untracked) for each project that gained
      # one, so a first-time lockfile is captured.
      for root in "${project_roots[@]}"; do
        for lf in package-lock.json pnpm-lock.yaml yarn.lock npm-shrinkwrap.json; do
          p="${root%/}/${lf}"; p="${p#./}"
          if [ -f "$p" ] && ! git ls-files --error-unmatch -- "$p" >/dev/null 2>&1; then
            changed_files+=("$p")
          fi
        done
      done
      # Dedup the staging set.
      mapfile -t changed_files < <( printf '%s\n' "${changed_files[@]}" | sort -u )
      if [ "${#changed_files[@]}" -eq 0 ]; then
        echo "node cleanup produced no change; nothing to amend."
        exit 0
      fi
      echo "Files to stage:"
      printf '  %s\n' "${changed_files[@]}"
      git add -- "${changed_files[@]}"
      # Amend the agent's last commit so the cleanup travels with the agent's
      # change. gh-aw's signed-commit push (ADR 0004) re-attributes the
      # resulting commit to the App identity at PR-create time.
      git commit --amend --no-edit
      # Regenerate the format-patch transport so the safe_outputs job replays
      # the amended history. Match gh-aw's generate_git_patch.cjs: full mode,
      # --stdout to one file.
      git format-patch --stdout "${base_sha}..HEAD" > "$AGENT_PATCH"
      echo "Rewrote ${AGENT_PATCH} ($(wc -c < "$AGENT_PATCH") bytes)"
      # Regenerate the bundle when bundle transport is in use (gh-aw's default
      # patch-format). Mirror generate_git_bundle.cjs.
      if [ -n "$AGENT_BUNDLE" ]; then
        git bundle create "$AGENT_BUNDLE" "${base_sha}..${AGENT_BRANCH}"
        echo "Rewrote ${AGENT_BUNDLE} ($(wc -c < "$AGENT_BUNDLE") bytes)"
      fi
---

## Host-side Node/TypeScript cleanup post-step

This fragment is the Node analog of `shared/sdd-rust-cleanup.md`. It carries the
post-agent, pre-PR host cleanup that lets `sdd-execute` open implementation pull
requests a Node/TypeScript consumer's CI accepts without manual fixup. The agent
edits TS/JS from inside gh-aw's network-restricted container, which has no
npm-registry egress and no Node toolchain, so it cannot run `prettier --write`,
`eslint --fix`, or refresh the lockfile to self-verify. The safe-output patch
therefore carries prettier-dirty, eslint-dirty code and a stale lockfile, which
a consumer's `prettier --check`, `eslint`, or frozen-lockfile install
(`npm ci`, `pnpm install --frozen-lockfile`, `yarn install --frozen-lockfile`)
gate rejects — the Node analog of the Rust failure mode #160 fixed.

The `post-steps` run on the GitHub runner, outside the firewall sandbox, after
the agent and before `safe_outputs` materializes the PR. When the agent's patch
touches Node (`*.ts`/`*.tsx`/`*.js`/`*.jsx`/`*.mjs`/`*.cjs` or `package.json`)
they install Node on the host, resolve each touched file to its package-manager
root, detect the consumer's package manager from the lockfile there, refresh the
lockfile for the roots whose `package.json` changed, run the consumer's own
prettier and eslint fixers over the touched files, amend the agent's commit with
whatever changed, and re-emit the patch and bundle transport files. The amend
lands inside the agent's existing commit, so gh-aw's signed-commit push
re-attributes the cleanup to the App identity (ADR 0004).

### Consumer-driven tool and package-manager choice

Nothing is hardcoded. Each touched file resolves to its package-manager root —
the nearest ancestor directory holding a lockfile — so a workspace member's edit
(e.g. `apps/web/src/x.ts`) resolves to the repo-root lockfile and shared tooling
rather than to `apps/web/package.json`; the package manager is detected from that
lockfile (`pnpm-lock.yaml` → pnpm, `yarn.lock` → yarn, `package-lock.json` /
`npm-shrinkwrap.json` → npm). A project with no lockfile anywhere up the tree
falls back to the nearest `package.json` and gets the fixers but no lockfile
refresh. The fixers run only when the consumer declares them in its own
`package.json` (or has them installed in `node_modules/.bin`) and are invoked
through the consumer's package-manager runner so its pinned version is used. A
consumer that uses neither prettier nor eslint pays nothing beyond the detection
checks.

### Scoped to the patch

The lockfile-refresh decision is per-root: only a root whose own `package.json`
changed in this patch takes the lock-refreshing install; every other root
installs against its existing lockfile (frozen) and, on failure, only warns —
it never falls back to a lock-mutating install that would rewrite a lockfile the
patch did not touch. The fixers and the `prettier --check` self-verify run only
against the files the patch touched under each root, never the whole project
tree, so the cleanup never sweeps unrelated tracked files into the amended
commit.

### Self-heal

After the fixers run, the step re-runs the consumer's own `prettier --check`. A
still-non-canonical file is surfaced as a loud `::error::`, never a non-zero
exit. The whole block is best-effort: a parse error, unfixable eslint rule, or
failed install is left untouched (not masked) and never aborts the post-step,
which would block PR creation and lose the agent's work.

### No registry egress on the agent

All npm-registry traffic is on the host runner only, outside the agent's
firewall sandbox; the agent container's network is never widened (consistent
with #152/#153 and `shared/sdd-rust-cleanup.md`). `node_modules` is never
staged or committed.

### Out of scope

Test execution (`npm test`) and type-checking (`tsc`) are the consumer CI's job
(mirrors #154). Stacks beyond Node/Rust are separate follow-ups.
