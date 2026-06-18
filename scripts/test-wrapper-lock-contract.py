#!/usr/bin/env python3
"""Assert every wrapper -> reusable-lock call honors the lock's `workflow_call` contract.

Each `wrappers/*.yml` is a hand-authored caller workflow. Where a job
delegates to a gh-aw-compiled reusable workflow with

    uses: norrietaylor/spectacles/.github/workflows/<name>.lock.yml@<ref>

GitHub Actions binds the caller's `with:` block against the lock's
`on.workflow_call.inputs` and the caller's `secrets:` block against
`on.workflow_call.secrets`. That binding is strict at *startup*:

  * A `with:`/`secrets:` key the lock does not declare is an "unexpected
    input/secret" error — the run never starts. This is the class of
    `startup_failure` issue #284 fixed: a wrapper passed a secret the
    lock had dropped, and every dispatch died before the agent booted.
  * A lock input/secret marked `required: true` that the caller omits is
    a "missing required input/secret" startup_failure of the same shape.

Neither failure is caught by the existing `compile` gate (the lock is
internally valid) nor by `actionlint` (it does not resolve cross-repo
reusable-workflow contracts). It only manifests at dispatch time, far
from the PR that introduced it. This gate makes it a red PR check.

For every wrapper job that `uses:` a local `*.lock.yml`, the script:

  1. collects the job's `with:` input keys and `secrets:` keys;
  2. parses the called lock's `on.workflow_call.inputs` and
     `on.workflow_call.secrets` (names, and which are `required`);
  3. fails if the wrapper passes an input/secret the lock does not
     declare (the #284 startup_failure class), or if a lock input/secret
     marked required is not passed by the wrapper.

Exit 1 on any contract violation; exit 0 when every wrapper -> lock call
binds cleanly. Only locks resolvable in this repository
(`.github/workflows/<name>.lock.yml`) are checked; a `uses:` pointing at
some other owner/repo is out of scope and skipped with a note.

A note on `required`: gh-aw serializes `required: false` as the *string*
`"false"` in some emitted `workflow_call` blocks, not the YAML boolean.
A bare `bool("false")` is `True`, which would invert the check and demand
every optional input be passed. This script coerces `required` with
explicit truthy handling (`_is_required`) so both the boolean and the
string form resolve correctly.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WRAPPERS_DIR = REPO_ROOT / "wrappers"
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

# Matches a reusable-workflow reference into this repo's compiled locks:
#   norrietaylor/spectacles/.github/workflows/<name>.lock.yml@<ref>
# Captures <name> so the called lock file can be resolved on disk. A
# `uses:` that points at any other owner/repo, or at a non-lock workflow,
# does not match and is left out of scope.
LOCK_USES_RE = re.compile(
    r"^norrietaylor/spectacles/\.github/workflows/"
    r"(?P<name>[A-Za-z0-9._-]+)\.lock\.yml@"
)


def _is_required(value) -> bool:
    """Coerce a `workflow_call` `required:` value to a bool.

    gh-aw emits `required: false` as the YAML boolean in most locks but
    as the *string* `"false"` in some. `bool("false")` is `True`, so a
    naive cast would treat every optional input as required and demand
    the wrapper pass it. Handle the string form explicitly: only an
    actual truthy boolean, or a string spelling a truthy value, counts
    as required. A missing key defaults to GitHub's own default of
    not-required.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1"}
    if value is None:
        return False
    return bool(value)


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise SystemExit(f"{path}: top-level YAML is not a mapping")
    return data


def workflow_on(data: dict) -> dict:
    """Return the `on:` mapping, tolerating YAML's `on` -> `True` coercion.

    Unquoted `on:` is the YAML 1.1 boolean `True`, so `yaml.safe_load`
    keys the trigger block under the Python bool `True`, not the string
    `"on"`. Check both so the lock's `workflow_call` block is found
    regardless of how the key deserialized.
    """
    for key in ("on", True):
        block = data.get(key)
        if isinstance(block, dict):
            return block
    return {}


def lock_contract(lock_path: Path) -> tuple[set[str], set[str], set[str], set[str]]:
    """Parse a lock's `on.workflow_call` declared inputs and secrets.

    Returns (declared_inputs, required_inputs, declared_secrets,
    required_secrets). A `secrets:` entry may be `null` (a bare name) or
    a mapping carrying `required:`; both forms are handled.
    """
    data = load_yaml(lock_path)
    wc = workflow_on(data).get("workflow_call")
    if not isinstance(wc, dict):
        raise SystemExit(
            f"{lock_path}: no `on.workflow_call` block — not a reusable workflow"
        )

    declared_inputs: set[str] = set()
    required_inputs: set[str] = set()
    inputs = wc.get("inputs") or {}
    if isinstance(inputs, dict):
        for name, spec in inputs.items():
            declared_inputs.add(name)
            if isinstance(spec, dict) and _is_required(spec.get("required")):
                required_inputs.add(name)

    declared_secrets: set[str] = set()
    required_secrets: set[str] = set()
    secrets = wc.get("secrets") or {}
    if isinstance(secrets, dict):
        for name, spec in secrets.items():
            declared_secrets.add(name)
            if isinstance(spec, dict) and _is_required(spec.get("required")):
                required_secrets.add(name)

    return declared_inputs, required_inputs, declared_secrets, required_secrets


def lock_calls(wrapper_data: dict):
    """Yield (job_name, lock_name, with_keys, secret_keys) per lock-calling job.

    A wrapper job that delegates to a reusable workflow carries a
    `uses:` string matching LOCK_USES_RE and may carry `with:` /
    `secrets:` mappings. A job without such a `uses:` (a deterministic
    `steps:` job) is skipped — it has no lock contract to validate.
    """
    jobs = wrapper_data.get("jobs") or {}
    if not isinstance(jobs, dict):
        return
    for job_name, job in jobs.items():
        if not isinstance(job, dict):
            continue
        uses = job.get("uses")
        if not isinstance(uses, str):
            continue
        m = LOCK_USES_RE.match(uses.strip())
        if not m:
            continue
        lock_name = m.group("name")
        with_block = job.get("with") or {}
        secrets_block = job.get("secrets") or {}
        # `secrets: inherit` is the string "inherit", not a mapping. The
        # wrappers map secrets explicitly (inherit does not cross owners),
        # so a string here passes no individually named secret; treat it
        # as an empty key set rather than a contract to validate.
        with_keys = set(with_block) if isinstance(with_block, dict) else set()
        secret_keys = (
            set(secrets_block) if isinstance(secrets_block, dict) else set()
        )
        job_perms = job.get("permissions")
        yield job_name, lock_name, with_keys, secret_keys, job_perms


# Repository GITHUB_TOKEN permission scopes are ordered: a reusable callee's
# jobs may not request a permission beyond what the CALLER job grants, or GitHub
# rejects the run at load (`startup_failure`, before any `if:` gate). `write`
# subsumes `read`. This is the class of issues #295 (sdd-triage) and #298
# (sdd-spike-reentry, sdd-derive) — distinct from the #284 input/secret class.
_PERM_RANK = {"none": 0, "read": 1, "write": 2}


def _perm_level(value) -> int:
    if value is None:
        return 0
    return _PERM_RANK.get(str(value).strip().lower(), 0)


def lock_permission_ceiling(lock_path: Path) -> dict:
    """Max permission level each scope reaches across all of a lock's jobs.

    A caller job must grant at least this for every scope, since its
    `permissions` cap every nested job in the called reusable workflow.
    """
    data = load_yaml(lock_path)
    jobs = data.get("jobs") or {}
    ceiling: dict = {}
    if isinstance(jobs, dict):
        for job in jobs.values():
            if not isinstance(job, dict):
                continue
            perms = job.get("permissions")
            if isinstance(perms, dict):
                for scope, level in perms.items():
                    if _perm_level(level) > _perm_level(ceiling.get(scope)):
                        ceiling[scope] = level
    return ceiling


def main() -> int:
    if not WRAPPERS_DIR.is_dir():
        raise SystemExit(f"wrappers directory not found: {WRAPPERS_DIR}")

    failures: list[str] = []
    checked_calls = 0

    for wrapper_path in sorted(WRAPPERS_DIR.glob("*.yml")):
        wrapper_data = load_yaml(wrapper_path)
        rel = wrapper_path.relative_to(REPO_ROOT)
        # A job without its own `permissions:` inherits the workflow-level
        # block; fall back to it when checking the caller's grant.
        workflow_perms = wrapper_data.get("permissions")
        for job_name, lock_name, with_keys, secret_keys, job_perms in lock_calls(
            wrapper_data
        ):
            lock_path = WORKFLOWS_DIR / f"{lock_name}.lock.yml"
            if not lock_path.is_file():
                # Out of scope: the lock is not resolvable in this repo
                # (a cross-repo reusable workflow). The contract lives in
                # whatever repo owns it; this gate cannot see it.
                print(
                    f"note: {rel} job '{job_name}' calls {lock_name}.lock.yml "
                    f"which is not present in this repo — skipping"
                )
                continue

            (
                declared_inputs,
                required_inputs,
                declared_secrets,
                required_secrets,
            ) = lock_contract(lock_path)
            checked_calls += 1

            # #284 startup_failure class: an input/secret the lock does
            # not declare. GitHub rejects the run at startup.
            for key in sorted(with_keys - declared_inputs):
                failures.append(
                    f"{rel} job '{job_name}' passes input `{key}` not declared by "
                    f"{lock_name}.lock.yml `on.workflow_call.inputs` "
                    f"(startup_failure, #284 class)"
                )
            for key in sorted(secret_keys - declared_secrets):
                failures.append(
                    f"{rel} job '{job_name}' passes secret `{key}` not declared by "
                    f"{lock_name}.lock.yml `on.workflow_call.secrets` "
                    f"(startup_failure, #284 class)"
                )

            # Missing-required class: a lock input/secret marked required
            # that the wrapper does not pass. Also a startup_failure.
            for key in sorted(required_inputs - with_keys):
                failures.append(
                    f"{rel} job '{job_name}' omits required input `{key}` declared by "
                    f"{lock_name}.lock.yml `on.workflow_call.inputs`"
                )
            for key in sorted(required_secrets - secret_keys):
                failures.append(
                    f"{rel} job '{job_name}' omits required secret `{key}` declared by "
                    f"{lock_name}.lock.yml `on.workflow_call.secrets`"
                )

            # Caller>=callee permission class (#295, #298): the caller job's
            # `permissions` cap every nested job in the called reusable
            # workflow. Granting a scope below what any nested job requests
            # fails the whole workflow at load (startup_failure, before `if:`).
            effective = job_perms if isinstance(job_perms, dict) else workflow_perms
            effective = effective if isinstance(effective, dict) else {}
            for scope, need in sorted(lock_permission_ceiling(lock_path).items()):
                if _perm_level(need) > _perm_level(effective.get(scope)):
                    failures.append(
                        f"{rel} job '{job_name}' grants `{scope}: "
                        f"{effective.get(scope, 'unset')}` but {lock_name}.lock.yml's "
                        f"nested jobs request `{scope}: {need}` — a reusable callee "
                        f"may not exceed the caller (startup_failure, #298 class)"
                    )

    if failures:
        print("Wrapper -> lock contract: FAIL")
        for line in failures:
            print(f"  {line}")
        return 1

    print(f"Wrapper -> lock contract: OK ({checked_calls} wrapper->lock calls checked)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
