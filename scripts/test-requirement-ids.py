#!/usr/bin/env python3
"""Assert that every `R<unit>.<seq>` requirement-ID citation resolves.

Workflow prose, ADRs, and shared fragments cite requirement IDs (e.g.
`R5.4`, `R6.2`) declared in the spec files under `docs/specs/*/`. A
spec edit that renumbers or deletes a requirement breaks every dangling
reference; without an automated check those breakages reach runtime,
where an agent cites a non-existent requirement or a triage step maps
a task to a deleted requirement.

This script:

1. Parses every `docs/specs/<N>-spec-<slug>/<N>-spec-<slug>.md` and
   extracts the set of *declared* IDs per spec. The declaration shape
   is the bullet-list form used uniformly across the suite:
   `- **R<unit>.<seq>**:` at start-of-line, optionally indented and
   optionally prefixed by `*` instead of `-`. A citation in prose
   (`(R5.4)`, `R5.4`, `R5.4 to R5.6`, table cells, etc.) is anything
   else.

2. Walks the *citing* sources — `.github/workflows/*.md` (skipping the
   gh-aw-generated `.lock.yml` files), `decisions/*.md`, `shared/*.md`,
   `docs/sdd/*.md`, and the other spec files (cross-spec citations are
   valid) — and pulls every `R\\d+\\.\\d+` token, tracking
   (file, line) for diagnostics. Non-markdown fenced code blocks
   (` ```text `, ` ```yaml `, ` ```bash `, etc.) are stripped before
   the scan — those blocks are example payloads, not contract prose,
   and the documented IDs inside them are intentionally generic.

3. Asserts every citation resolves to a declared ID in *some* spec.
   The issue's "multi-spec disambiguation is out of scope" rule means
   per-spec namespacing is not enforced: an `R5.4` cited from
   `decisions/0004-uses-distribution-model.md` resolves so long as
   *any* spec declares `R5.4`. This is the pragmatic rule — a typo
   (e.g. `R5.44`) or a deleted ID is still caught.

4. Optionally reports *dead requirements*: declared IDs cited only
   inside their own spec file (or not at all). Per the issue this is
   "optional ... worth implementing" and the first cut treats dead
   requirements as a *warning*, not a failure, because legitimate
   future-use or self-contained requirements exist on `main` (e.g.
   foundation requirements that no workflow source needs to cite by
   ID). The split is documented in the PR body.

Exit 1 on any unresolved citation; exit 0 when every cited ID resolves.
Warnings about dead requirements print to stdout and do not affect the
exit code.

The script is independent of `scripts/test-safe-output-allowlists.py`,
`scripts/test-command-table.py`, and
`scripts/test-lifecycle-state-machine.py` by design: these checks are
separable invariants and a shared parser would couple them.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SPECS_DIR = REPO_ROOT / "docs" / "specs"
EXCEPTIONS_FILE = REPO_ROOT / "scripts" / "requirement-id-exceptions.yml"

# Citing sources. The `.github/workflows/*.lock.yml` files are gh-aw
# compiled output and embed the same prose plus a `prompt:` block that
# would multiply-match every ID; the `.md` source is authoritative.
CITING_GLOBS: tuple[tuple[str, str], ...] = (
    (".github/workflows", "*.md"),
    ("decisions", "*.md"),
    ("shared", "*.md"),
    ("docs/sdd", "*.md"),
    # Spec files cite IDs across specs (e.g. a Unit 5 requirement in
    # spec 01 referencing a Unit 3 requirement in spec 01 itself). The
    # spec-internal citations are handled in the dead-requirement check
    # by filtering out same-file cites; the resolution check accepts
    # them as valid.
    ("docs/specs", "**/*.md"),
)

# The declared-ID shape across both spec files is uniform: a bullet
# item whose first token after the bullet marker is a bolded ID.
# Examples (all real):
#   `- **R1.1**: The repository shall be public ...`
#   `  - **R6.7**: When no eligible ...`
# An indented continuation line ("`  field (R5.6), proof artifacts`")
# never starts with `- **R...`, so the anchor is robust.
ID_DECLARATION_RE = re.compile(
    r"^\s*[-*]\s+\*\*(?P<id>R\d+\.\d+)\*\*\s*:",
    re.MULTILINE,
)

# Any R<unit>.<seq> token anywhere. Word boundaries on both sides keep
# `R10.4` and `RR1.1` separable, and reject substring matches inside
# version strings like `v1.1.0`.
ID_CITATION_RE = re.compile(r"\bR\d+\.\d+\b")

# Strip fenced code blocks except markdown-tagged ones. A ```text or
# ```yaml block is a sample payload (e.g. the task-body template in
# `sdd-triage.md` uses literal placeholder IDs like `R1.1`) and does
# not participate in the cross-reference contract. A ```markdown fence
# would be a quoted prose excerpt, which we still want to scan.
#
# The regex tolerates the full CommonMark fenced-code surface: up to 3
# leading spaces, either backtick or tilde fences (the two must match
# at open and close), and an info string after the fence that may carry
# metadata beyond the language token (e.g. ` ```python title="x" `).
# Without this generality a tilde fence containing a placeholder ID
# would be scanned as prose and false-positive the resolution check.
CODE_FENCE_RE = re.compile(
    r"^ {0,3}(?P<fence>`{3,}|~{3,})[ \t]*(?P<info>[^\n]*)\n"
    r"(?P<body>.*?)"
    r"^ {0,3}(?P=fence)[ \t]*$",
    re.MULTILINE | re.DOTALL,
)


def _fence_lang(info: str) -> str:
    """Extract the language token (first word) from a fence info string."""
    parts = info.strip().split(None, 1)
    return parts[0].lower() if parts else ""


def strip_non_markdown_fences(text: str) -> str:
    """Drop fenced code blocks except those tagged ```markdown.

    The sdd-triage task-body template uses ```text and contains
    placeholder requirement IDs (`R1.1, R1.2`) that are intentionally
    generic; they are not citations of the live spec's R1.1 and would
    false-positive a fragile assertion if a future spec edit deleted
    them. Same logic applies to ```yaml frontmatter examples elsewhere.
    """

    def repl(m: re.Match[str]) -> str:
        if _fence_lang(m.group("info")) == "markdown":
            return m.group("body")
        return ""

    return CODE_FENCE_RE.sub(repl, text)


def load_exceptions() -> dict[str, list[str]]:
    """Load documented exceptions. Schema (parallels #83/#84):

    dead-requirement:
      - name: R1.1
        reason: Foundation requirement satisfied by repo existence; no
          workflow prose has reason to cite it.

    The validator never errors on a dead-requirement entry; the
    warning is suppressed instead. There is no exception bucket for
    unresolved citations: a citation that does not resolve is a bug,
    not a documentation drift, and must be fixed.
    """
    if not EXCEPTIONS_FILE.exists():
        return {}
    with EXCEPTIONS_FILE.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    out: dict[str, list[str]] = {}
    for kind, entries in data.items():
        out[kind] = []
        for entry in entries or []:
            if not isinstance(entry, dict) or "name" not in entry:
                raise SystemExit(
                    f"exceptions: malformed entry in {kind}: {entry!r}"
                )
            if not entry.get("reason"):
                raise SystemExit(
                    f"exceptions: missing 'reason' for {kind}/{entry['name']}"
                )
            out[kind].append(entry["name"])
    return out


def find_spec_files() -> list[Path]:
    """Every `docs/specs/<N>-spec-<slug>/<N>-spec-<slug>.md` is the
    primary spec document for its directory. The directory name and
    the file name match by convention (see issue #86 issue text and
    the two existing specs). A directory without a same-named .md is
    treated as not-yet-authored and skipped quietly."""
    out: list[Path] = []
    for d in sorted(SPECS_DIR.iterdir()):
        if not d.is_dir():
            continue
        candidate = d / f"{d.name}.md"
        if candidate.exists():
            out.append(candidate)
    return out


def declared_ids(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    return {m.group("id") for m in ID_DECLARATION_RE.finditer(text)}


def iter_citing_files() -> list[Path]:
    seen: set[Path] = set()
    out: list[Path] = []
    for subdir, pattern in CITING_GLOBS:
        base = REPO_ROOT / subdir
        if not base.exists():
            continue
        for p in sorted(base.glob(pattern)):
            if not p.is_file():
                continue
            # Skip gh-aw-generated lock files. The glob already filters
            # to *.md, but a future glob change could pick them up;
            # belt-and-suspenders here.
            if p.name.endswith(".lock.yml"):
                continue
            if p in seen:
                continue
            seen.add(p)
            out.append(p)
    return out


def collect_citations(path: Path) -> list[tuple[str, int]]:
    """Return (id, line_number) for every cite in `path`, with
    non-markdown fenced blocks excluded.

    Implementation: find every R-token in the raw text, then drop any
    whose offset lies inside a non-markdown fence. This preserves the
    original line numbers (a substitution-then-rescan would shift them
    after a multi-line fence).
    """
    raw = path.read_text(encoding="utf-8")

    # Pre-compute fence spans so an in-fence test is O(1) per match
    # against a small list.
    fences: list[tuple[int, int, str]] = [
        (m.start(), m.end(), _fence_lang(m.group("info")))
        for m in CODE_FENCE_RE.finditer(raw)
    ]

    out: list[tuple[str, int]] = []
    for m in ID_CITATION_RE.finditer(raw):
        offset = m.start()
        in_fence = False
        for fs, fe, lang in fences:
            if fs <= offset < fe and lang != "markdown":
                in_fence = True
                break
        if in_fence:
            continue
        line = raw.count("\n", 0, offset) + 1
        out.append((m.group(0), line))
    return out


def main() -> int:
    spec_files = find_spec_files()
    if not spec_files:
        raise SystemExit(
            f"no spec files found under {SPECS_DIR.relative_to(REPO_ROOT)}"
        )

    # Per-spec declaration sets, keyed by the spec file's relative
    # path. The flat union is the resolution domain (per the issue:
    # "an ID is resolved if any spec declares it").
    per_spec: dict[Path, set[str]] = {p: declared_ids(p) for p in spec_files}
    all_declared: set[str] = set().union(*per_spec.values())

    # Every cite, indexed both ways for the two checks:
    #   citations[id] = [(file, line), ...]  -> resolution check
    #   cites_by_file[file] = set(ids)       -> dead-requirement check
    citations: dict[str, list[tuple[Path, int]]] = {}
    cites_by_file: dict[Path, set[str]] = {}

    for path in iter_citing_files():
        rel_path = path
        # The spec file's own declarations would match the citation
        # regex too. We skip declaration lines so a self-declared ID
        # does not count as a self-citation (which would mask a truly
        # dead requirement).
        if path in per_spec:
            # For spec files, only count citations that are NOT on a
            # declaration line. The simplest way: collect citations
            # normally, then drop any whose line is a declaration
            # line.
            raw = path.read_text(encoding="utf-8")
            declaration_lines = {
                raw.count("\n", 0, m.start()) + 1
                for m in ID_DECLARATION_RE.finditer(raw)
            }
            cites = [
                (cid, ln)
                for cid, ln in collect_citations(path)
                if ln not in declaration_lines
            ]
        else:
            cites = collect_citations(path)

        for cid, line in cites:
            citations.setdefault(cid, []).append((rel_path, line))
            cites_by_file.setdefault(rel_path, set()).add(cid)

    # --- Resolution check (hard failure) -------------------------------
    failures: list[str] = []
    for cid in sorted(citations):
        if cid not in all_declared:
            for file_path, line in citations[cid]:
                rel = file_path.relative_to(REPO_ROOT)
                failures.append(
                    f"unresolved requirement reference: {cid} in {rel}:{line}"
                )

    # --- Dead-requirement check (warning only) -------------------------
    exceptions = load_exceptions()
    dead_exceptions = set(exceptions.get("dead-requirement", []))

    warnings: list[str] = []
    for spec_path, ids in per_spec.items():
        spec_rel = spec_path.relative_to(REPO_ROOT)
        for rid in sorted(ids, key=_id_sort_key):
            if rid in dead_exceptions:
                continue
            # A requirement is "live" if some file other than its
            # declaring spec cites it. A citation from the same spec
            # file does not count (a spec referencing its own IDs is
            # internal cross-reference, not external use).
            cites = citations.get(rid, [])
            external = [c for c in cites if c[0] != spec_path]
            if not external:
                warnings.append(
                    f"dead requirement: {rid} declared in {spec_rel} "
                    f"but never cited outside its own spec"
                )

    # --- Report --------------------------------------------------------
    if failures:
        print("Requirement-ID cross-reference: FAIL")
        for line in failures:
            print(f"  {line}")
        if warnings:
            print()
            print(f"Warnings ({len(warnings)} dead requirement(s)):")
            for line in warnings:
                print(f"  {line}")
        return 1

    n_specs = len(per_spec)
    n_ids = len(all_declared)
    n_cites = sum(len(v) for v in citations.values())
    print(
        f"Requirement-ID cross-reference: OK "
        f"({n_specs} specs, {n_ids} declared IDs, {n_cites} citation(s))"
    )
    if warnings:
        print()
        print(f"Warnings ({len(warnings)} dead requirement(s) — non-fatal):")
        for line in warnings:
            print(f"  {line}")
    return 0


def _id_sort_key(rid: str) -> tuple[int, int]:
    """Sort R1.2 before R1.10 before R2.1 by parsing the numeric parts."""
    m = re.match(r"R(\d+)\.(\d+)", rid)
    if not m:
        return (0, 0)
    return (int(m.group(1)), int(m.group(2)))


if __name__ == "__main__":
    sys.exit(main())
