#!/usr/bin/env python3
"""Assert a staging repo's terminal state against a scenario's expectations.

The `e2e-dispatch` workflow seeds a synthetic tracking issue on the staging
repo, drives it through the SDD lifecycle, and polls until the issue reaches a
terminal `sdd:*` label (or `needs-human`, or a timeout). This script reads the
resulting state through the GitHub API and checks it against the scenario's
`expectations.yml` assertion contract:

  - `terminal_label`  the tracking issue carries this `sdd:*` label (null = no
                      terminal lifecycle label is required, e.g. needs-human).
  - `require_label`   the tracking issue carries this label (e.g. needs-human).
  - `forbid_labels`   none of these labels are present on the tracking issue.
  - `artifacts`       each glob matches at least one file on the default branch.
  - `prs.opened_min`  at least N pull requests were opened since `--since`.
  - `prs.all_merged`  every such pull request is merged.

All GitHub reads go through the `gh` CLI (`gh api`), matching the rest of the
repo's scripts — no PyGithub, no raw HTTP. Every failed check is collected and
printed; the script exits 1 if any check fails, 0 when all hold. Assertion
failures are reported, never raised.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml


def gh_api(path: str, *, paginate: bool = False) -> object:
    """Call `gh api <path>` and return the parsed JSON."""
    cmd = ["gh", "api", path]
    if paginate:
        # --slurp wraps the paginated pages into a single JSON array so a
        # single json.loads sees every page.
        cmd += ["--paginate", "--slurp"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"gh api {path} failed: {proc.stderr.strip()}")
    return json.loads(proc.stdout)


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Translate a path glob (supporting `**`) to an anchored regex.

    `**` matches any number of path segments (including zero); `*` matches
    within a single segment; `?` matches one non-slash character.
    """
    out = []
    i = 0
    while i < len(pattern):
        c = pattern[i]
        if c == "*":
            if pattern[i : i + 2] == "**":
                # `**/` collapses to "zero or more leading segments"; a bare
                # `**` matches the rest of the path across segments.
                if pattern[i : i + 3] == "**/":
                    out.append("(?:.*/)?")
                    i += 3
                    continue
                out.append(".*")
                i += 2
                continue
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(c))
        i += 1
    return re.compile("^" + "".join(out) + "$")


def check_labels(issue: dict, expect: dict, fail) -> None:
    labels = {lbl["name"] for lbl in issue.get("labels", [])}

    terminal = expect.get("terminal_label", "__unset__")
    if terminal not in ("__unset__", None):
        if terminal not in labels:
            fail(f"terminal_label: expected {terminal!r}; issue labels are {sorted(labels)}")

    require = expect.get("require_label")
    if require and require not in labels:
        fail(f"require_label: expected {require!r}; issue labels are {sorted(labels)}")

    for forbidden in expect.get("forbid_labels") or []:
        if forbidden in labels:
            fail(f"forbid_labels: {forbidden!r} is present on the tracking issue")


def check_artifacts(repo: str, expect: dict, fail) -> None:
    globs = expect.get("artifacts") or []
    if not globs:
        return
    meta = gh_api(f"repos/{repo}")
    branch = meta["default_branch"]
    tree = gh_api(f"repos/{repo}/git/trees/{branch}?recursive=1")
    if tree.get("truncated"):
        fail("artifacts: default-branch tree was truncated; cannot assert reliably")
    paths = [e["path"] for e in tree.get("tree", []) if e.get("type") == "blob"]
    for pattern in globs:
        rx = glob_to_regex(pattern)
        if not any(rx.match(p) for p in paths):
            fail(f"artifacts: no file on {branch} matches {pattern!r}")


def check_prs(repo: str, expect: dict, since: str | None, fail) -> None:
    pr_expect = expect.get("prs") or {}
    if not pr_expect:
        return
    pulls = gh_api(f"repos/{repo}/pulls?state=all&per_page=100", paginate=True)
    # --slurp yields a list of pages (each a list); flatten. Without pagination
    # gh returns a single list.
    if pulls and isinstance(pulls[0], list):
        pulls = [pr for page in pulls for pr in page]
    if since:
        pulls = [pr for pr in pulls if pr["created_at"] >= since]

    opened_min = pr_expect.get("opened_min")
    if opened_min is not None and len(pulls) < opened_min:
        fail(f"prs.opened_min: expected >= {opened_min}; found {len(pulls)} since {since}")

    if pr_expect.get("all_merged"):
        unmerged = [pr["number"] for pr in pulls if not pr.get("merged_at")]
        if unmerged:
            fail(f"prs.all_merged: PRs not merged: {unmerged}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", required=True, help="staging repo as owner/name")
    ap.add_argument("--issue", required=True, type=int, help="tracking issue number")
    ap.add_argument("--expect", required=True, type=Path, help="path to expectations.yml")
    ap.add_argument(
        "--since",
        default=None,
        help="ISO 8601 timestamp; only PRs created at or after this are considered",
    )
    args = ap.parse_args()

    expect = yaml.safe_load(args.expect.read_text())
    if not isinstance(expect, dict):
        print(f"e2e-assert: {args.expect} is not a mapping", file=sys.stderr)
        return 1

    failures: list[str] = []
    fail = failures.append

    try:
        issue = gh_api(f"repos/{args.repo}/issues/{args.issue}")
        check_labels(issue, expect, fail)
        check_artifacts(args.repo, expect, fail)
        check_prs(args.repo, expect, args.since, fail)
    except RuntimeError as exc:
        print(f"e2e-assert: {exc}", file=sys.stderr)
        return 1

    if failures:
        print(f"e2e-assert: {len(failures)} assertion(s) failed for {args.repo}#{args.issue}:")
        for f in failures:
            print(f"  - {f}")
        return 1

    print(f"e2e-assert: all assertions passed for {args.repo}#{args.issue}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
