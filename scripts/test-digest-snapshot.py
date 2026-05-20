#!/usr/bin/env python3
"""Assert every container reference in a `.lock.yml` matches the snapshot.

Every `.github/workflows/*.lock.yml` embeds a `gh-aw-manifest` JSON comment
header that lists the containers gh-aw will pull at run time. A typical
entry looks like:

    {
      "image": "ghcr.io/github/serena-mcp-server:latest",
      "digest": "sha256:bf3433...",
      "pinned_image": "ghcr.io/github/serena-mcp-server:latest@sha256:bf3433..."
    }

Some entries carry no `digest` field (e.g. the firewall stack and
`github-mcp-server` on current main). The compile step pulls and pins
those at run time, but a moved tag would shift the digest silently — the
.lock.yml diff at compile time is large and a digest change looks like
noise. This check exists so a digest drift becomes a small, reviewable
diff against a checked-in snapshot.

This script:

1. Walks every `.github/workflows/*.lock.yml`, locates the
   `# gh-aw-manifest: {...}` header line, parses the JSON, and collects
   the observed `(image, digest)` set. Containers without a `digest`
   field appear in the set with `digest: None` so the snapshot still
   records their presence — a future digest pinning is a real change
   that should land via a reviewable snapshot edit.

2. Loads the snapshot at `scripts/digest-snapshot.yml`. Schema:

       containers:
         - image: ghcr.io/github/serena-mcp-server:latest
           digest: sha256:bf3433...
         - image: ghcr.io/github/gh-aw-firewall/agent:0.25.46
           digest: null

3. Asserts three contracts:

   - **Drift**: an observed `image` whose digest differs from the snapshot
     digest. Reported as `digest drift: <image>: <snapshot> -> <observed>`.
     A `null` snapshot digest becoming a real digest counts as drift —
     that is the "the registry just pinned this tag" event the check
     exists to surface.
   - **Unsnapshotted**: an observed `image` not present in the snapshot.
     Reported as `unsnapshotted container: <image> (digest: <observed>)`.
   - **Stale**: a snapshot entry no longer observed in any lock file.
     Reported as a warning (not failure) — a lock file may legitimately
     drop a container, and the next snapshot edit can prune the stale
     entry without blocking the PR that drops it.

4. With `--write`, regenerates the snapshot from the observed set.
   This is the one-shot bootstrap mode and the way a maintainer commits
   a reviewed digest change: bump the version in the workflow source,
   `gh aw compile`, then `python scripts/test-digest-snapshot.py --write`
   and inspect the snapshot diff before committing.

Exit 1 on drift or unsnapshotted entries; exit 0 otherwise. Stale-entry
warnings print to stdout and do not affect the exit code.

The script is independent of `scripts/test-safe-output-allowlists.py`,
`scripts/test-command-table.py`, `scripts/test-lifecycle-state-machine.py`,
and `scripts/test-requirement-ids.py` by design: these checks are
separable invariants and a shared parser would couple them.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
LOCK_GLOB = ".github/workflows/*.lock.yml"
SNAPSHOT_FILE = REPO_ROOT / "scripts" / "digest-snapshot.yml"

MANIFEST_PREFIX = "# gh-aw-manifest: "


def extract_manifest(lock_path: Path) -> dict[str, Any]:
    """Find the `# gh-aw-manifest: {...}` comment line and parse its JSON.

    The header sits near the top of every compiled lock file (line 2 on
    current main) and is the only `# gh-aw-manifest:` line in the file.
    We scan from the top and stop on the first match; if no header is
    present the file is treated as malformed and the script exits 1.
    """
    with lock_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.startswith(MANIFEST_PREFIX):
                payload = line[len(MANIFEST_PREFIX) :].rstrip("\n")
                try:
                    return json.loads(payload)
                except json.JSONDecodeError as exc:
                    raise SystemExit(
                        f"{lock_path.relative_to(REPO_ROOT)}: "
                        f"malformed gh-aw-manifest JSON: {exc}"
                    ) from exc
    raise SystemExit(
        f"{lock_path.relative_to(REPO_ROOT)}: no gh-aw-manifest header found"
    )


def collect_observed() -> dict[str, str | None]:
    """Union the containers from every lock file.

    Returns `{image: digest_or_None}`. A conflict (two lock files
    disagreeing about a digest for the same image) is itself a bug — the
    compile step should pin every reference to the same digest — and we
    surface it as a hard error rather than silently picking one.
    """
    observed: dict[str, str | None] = {}
    sources: dict[str, Path] = {}
    lock_paths = sorted(REPO_ROOT.glob(LOCK_GLOB))
    if not lock_paths:
        # A false-green on zero matches would mask a glob drift (e.g. a
        # workflow rename, a moved directory) without any visible signal.
        raise SystemExit(
            f"no lock files found matching {LOCK_GLOB} — check the glob and repo layout"
        )
    for lock_path in lock_paths:
        manifest = extract_manifest(lock_path)
        if not isinstance(manifest, dict):
            raise SystemExit(
                f"{lock_path.relative_to(REPO_ROOT)}: "
                f"gh-aw-manifest must decode to an object, got {type(manifest).__name__}"
            )
        containers = manifest.get("containers") or []
        if not isinstance(containers, list):
            raise SystemExit(
                f"{lock_path.relative_to(REPO_ROOT)}: "
                f"'containers' must be a list, got {type(containers).__name__}"
            )
        for entry in containers:
            if not isinstance(entry, dict):
                raise SystemExit(
                    f"{lock_path.relative_to(REPO_ROOT)}: "
                    f"container entry must be an object: {entry!r}"
                )
            image = entry.get("image")
            if not image:
                raise SystemExit(
                    f"{lock_path.relative_to(REPO_ROOT)}: "
                    f"container entry missing 'image': {entry!r}"
                )
            digest = entry.get("digest")
            if image in observed:
                if observed[image] != digest:
                    prev = sources[image].relative_to(REPO_ROOT)
                    curr = lock_path.relative_to(REPO_ROOT)
                    raise SystemExit(
                        f"inconsistent digest for {image}: "
                        f"{observed[image]} (in {prev}) vs "
                        f"{digest} (in {curr})"
                    )
            else:
                observed[image] = digest
                sources[image] = lock_path
    return observed


def load_snapshot() -> dict[str, str | None]:
    if not SNAPSHOT_FILE.exists():
        return {}
    with SNAPSHOT_FILE.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise SystemExit(
            f"snapshot: root must be a mapping, got {type(data).__name__}"
        )
    containers = data.get("containers") or []
    if not isinstance(containers, list):
        raise SystemExit(
            f"snapshot: 'containers' must be a list, got {type(containers).__name__}"
        )
    out: dict[str, str | None] = {}
    for entry in containers:
        if not isinstance(entry, dict) or "image" not in entry:
            raise SystemExit(
                f"snapshot: malformed container entry: {entry!r}"
            )
        out[entry["image"]] = entry.get("digest")
    return out


def write_snapshot(observed: dict[str, str | None]) -> None:
    """Serialize with deterministic ordering so diffs are minimal."""
    entries = [
        {"image": image, "digest": observed[image]}
        for image in sorted(observed)
    ]
    body = (
        "# Snapshot of container references and pinned digests from every\n"
        "# .github/workflows/*.lock.yml `gh-aw-manifest` header.\n"
        "#\n"
        "# Regenerate with: python scripts/test-digest-snapshot.py --write\n"
        "# A digest change here is the reviewable signal for a moved tag.\n"
        "containers:\n"
    )
    for entry in entries:
        digest = entry["digest"]
        rendered_digest = digest if digest is not None else "null"
        body += f"  - image: {entry['image']}\n"
        body += f"    digest: {rendered_digest}\n"
    SNAPSHOT_FILE.write_text(body, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--write",
        action="store_true",
        help="Regenerate the snapshot from the current observed set.",
    )
    args = parser.parse_args()

    observed = collect_observed()

    if args.write:
        write_snapshot(observed)
        print(
            f"Digest snapshot: wrote {len(observed)} container(s) to "
            f"{SNAPSHOT_FILE.relative_to(REPO_ROOT)}"
        )
        return 0

    snapshot = load_snapshot()

    drift: list[str] = []
    unsnapshotted: list[str] = []
    stale: list[str] = []

    for image, digest in sorted(observed.items()):
        if image not in snapshot:
            unsnapshotted.append(
                f"unsnapshotted container: {image} "
                f"(digest: {digest if digest is not None else 'null'})"
            )
            continue
        if snapshot[image] != digest:
            snap = snapshot[image] if snapshot[image] is not None else "null"
            obs = digest if digest is not None else "null"
            drift.append(f"digest drift: {image}: {snap} -> {obs}")

    for image in sorted(snapshot):
        if image not in observed:
            stale.append(f"stale snapshot entry: {image}")

    failures = drift + unsnapshotted
    if failures:
        print("Digest snapshot: FAIL")
        for line in failures:
            print(f"  {line}")
        print()
        print(
            "Review the drift above; if intentional, regenerate the snapshot "
            "with `python scripts/test-digest-snapshot.py --write` and commit "
            "the result."
        )
        if stale:
            print()
            print(f"Warnings ({len(stale)} stale snapshot entry/entries):")
            for line in stale:
                print(f"  {line}")
        return 1

    print(
        f"Digest snapshot: OK "
        f"({len(observed)} container(s) across "
        f"{len(list(REPO_ROOT.glob(LOCK_GLOB)))} lock file(s))"
    )
    if stale:
        print()
        print(
            f"Warnings ({len(stale)} stale snapshot entry/entries — non-fatal):"
        )
        for line in stale:
            print(f"  {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
