#!/usr/bin/env python3
"""Assert that gh-aw workflow safe-output allowlists match prose intent.

For every `.github/workflows/*.md` agentic-workflow source this script:

1. Parses the YAML frontmatter and extracts the `safe-outputs` block.
2. Builds the *declared* allowlist sets:
   - labels declared under `add-labels.allowed` / `remove-labels.allowed`
   - safe-output names declared as top-level keys under `safe-outputs:`
     (e.g. `add-comment`, `create-issue`, `push-to-pull-request-branch`,
     `update-issue`, `noop`, `hide-comment`, `close-issue`,
     `create-pull-request`, `create-pull-request-review-comment`)
3. Scans the prose body for *write events*: each event names a label
   the agent applies or removes. Patterns are drawn from the actual
   phrasings used across the suite — both the parenthetical
   ``(`add-labels`)`` / ``(`remove-labels`)`` tag and the English
   imperative forms ``Apply the `X` label`` / ``Remove the `X` label``
   / ``add `X``` / ``gains `X```. The label catalog at
   ``templates/.github/labels.yml`` bounds what counts as a label.
4. Compares the declared sets to the prose-derived sets and reports
   mismatches in both directions:
   - "allowed but unused": frontmatter declares a label or safe-output
     the prose never instructs the agent to use (dead allowlist entry).
   - "used but not allowed": prose instructs a write the frontmatter
     does not allow (gh-aw would reject it at runtime).

A YAML exceptions file at ``scripts/safe-output-allowlist-exceptions.yml``
documents intentional asymmetries with a one-line ``reason:`` per entry.

Exit 1 on any unresolved mismatch; exit 0 when the prose contract holds.

Source-of-truth note: issue #83 cites `.lock.yml` files. This script
reads the `.md` sources instead, which is equivalent and cleaner — the
lock files embed the same prose plus gh-aw transformations that make
parsing trickier. The prose contract is about what the agent author
wrote, which lives in the `.md`.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Iterable

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
LABELS_CATALOG = REPO_ROOT / "templates" / ".github" / "labels.yml"
EXCEPTIONS_FILE = REPO_ROOT / "scripts" / "safe-output-allowlist-exceptions.yml"

# The canonical set of gh-aw safe-output names this script knows about.
# Drawn from the frontmatter keys used across the suite and the gh-aw
# documentation. Any backticked occurrence of one of these in prose
# counts as a reference to that safe-output.
SAFE_OUTPUT_NAMES = frozenset(
    {
        "create-issue",
        "add-comment",
        "push-to-pull-request-branch",
        "update-issue",
        "add-labels",
        "remove-labels",
        "noop",
        "hide-comment",
        "close-issue",
        "create-pull-request",
        "create-pull-request-review-comment",
        "submit-pull-request-review",
        "merge-pull-request",
    }
)

# Structural keys under `safe-outputs:` that never appear as prose write
# instructions. Excluded from the safe-output name comparison.
NON_PROSE_SAFE_OUTPUT_KEYS = frozenset({"github-app"})

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)
BACKTICK_TOKEN_RE = re.compile(r"`([^`]+)`")


def load_label_catalog() -> set[str]:
    """Load the canonical label name set from templates/.github/labels.yml.
    The catalog is reference data, not a write filter: a prose write of a
    label not in the catalog is still a write (and the test still flags
    it against the workflow's allowlist). The catalog is used to widen
    the label shape regex, so an oddly-named label can be added to the
    catalog and the test picks it up without code changes."""
    with LABELS_CATALOG.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or []
    return {entry["name"] for entry in data if isinstance(entry, dict) and "name" in entry}


# A token looks like a label when it matches the convention used by
# templates/.github/labels.yml: a lowercase scope, a colon, a
# lowercase-and-dash payload (e.g. `sdd:ready`, `model:haiku`,
# `priority:must-have`); or it is the bare `needs-human` literal. Any
# token in the catalog is also accepted.
LABEL_SHAPE_RE = re.compile(r"^[a-z][a-z0-9]*:[a-z0-9][a-z0-9-]*$")


def looks_like_label(token: str, catalog: set[str]) -> bool:
    return token == "needs-human" or token in catalog or bool(LABEL_SHAPE_RE.match(token))


def load_exceptions() -> dict[str, dict[str, list[str]]]:
    if not EXCEPTIONS_FILE.exists():
        return {}
    with EXCEPTIONS_FILE.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    exceptions: dict[str, dict[str, list[str]]] = {}
    for workflow, blocks in data.items():
        wf: dict[str, list[str]] = {}
        for direction, entries in (blocks or {}).items():
            wf[direction] = []
            for entry in entries or []:
                if not isinstance(entry, dict) or "name" not in entry:
                    raise SystemExit(
                        f"exceptions: malformed entry in {workflow}/{direction}: {entry!r}"
                    )
                if not entry.get("reason"):
                    raise SystemExit(
                        f"exceptions: missing 'reason' for {workflow}/{direction}/{entry['name']}"
                    )
                wf[direction].append(entry["name"])
        exceptions[workflow] = wf
    return exceptions


CODE_FENCE_RE = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)


def strip_code_fences(body: str) -> str:
    """Remove fenced code blocks from the prose body. A fenced block is
    not natural-language instruction; scanning it for label tokens
    confuses the single-backtick token regex when the triple-backtick
    fence sits between paragraphs."""
    return CODE_FENCE_RE.sub("", body)


def parse_workflow(path: Path) -> tuple[dict, str] | None:
    text = path.read_text(encoding="utf-8")
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None
    frontmatter_raw, body = m.group(1), m.group(2)
    try:
        frontmatter = yaml.safe_load(frontmatter_raw) or {}
    except yaml.YAMLError as exc:
        raise SystemExit(f"{path}: invalid YAML frontmatter: {exc}")
    return frontmatter, strip_code_fences(body)


def declared_label_sets(frontmatter: dict) -> tuple[set[str], set[str]]:
    so = frontmatter.get("safe-outputs") or {}
    add_block = so.get("add-labels") or {}
    remove_block = so.get("remove-labels") or {}
    add = set(add_block.get("allowed") or []) if isinstance(add_block, dict) else set()
    remove = set(remove_block.get("allowed") or []) if isinstance(remove_block, dict) else set()
    return add, remove


def declared_safe_outputs(frontmatter: dict) -> set[str]:
    so = frontmatter.get("safe-outputs") or {}
    return {key for key in so.keys() if key not in NON_PROSE_SAFE_OUTPUT_KEYS}


# Clause-start anchor: the verb that follows must be the start of a
# sentence, list item, or coordinate sub-clause — i.e. directed at the
# agent. This rules out third-person prose like "templates apply
# `sdd:spec`" where the subject is something other than the agent.
# A comma is included because the suite phrases hand-offs as
# "When the gate finds X, apply `needs-human`": the comma introduces an
# imperative clause directed at the agent.
CLAUSE_START = r"(?:^|(?<=[.:;,\n])\s*(?:[-*]\s+)?|(?<=\(\s)|(?<=\n  )|(?<=\n))"

# Prose patterns that name the label the agent applies. Each pattern
# captures the label string in group 'label'. The label catalog still
# bounds what is accepted, so a stray capture is filtered downstream.
#
# Patterns cover the actual phrasings in this suite:
#   - "Apply the `X` label" / "apply the `X` label" (clause start)
#   - "Add the `X` label" / "add `X`" (clause start)
#   - "Then apply `X`" / "Then add `X`" (clause start after period)
#   - "gains `X`" — the verification-section phrasing
ADD_LABEL_PATTERNS = [
    re.compile(
        CLAUSE_START + r"(?:[Tt]hen\s+)?[Aa]pply(?:\s+the)?\s+`(?P<label>[^`\n]+)`",
        re.MULTILINE,
    ),
    re.compile(
        CLAUSE_START + r"(?:[Tt]hen\s+)?[Aa]dd(?:\s+(?:the|its))?\s+`(?P<label>[^`\n]+)`"
        r"(?=[^\n]{0,160}?(?:\s+label|\s+to\b|\(`add-labels`\)))",
        re.MULTILINE,
    ),
    # "gains `X`" / "moves to `X` and gains `X`" — verification phrasing
    re.compile(r"\bgains\s+`(?P<label>[^`\n]+)`", re.MULTILINE),
]
REMOVE_LABEL_PATTERNS = [
    re.compile(
        CLAUSE_START
        + r"(?:[Tt]hen\s+)?[Rr]emove(?:\s+(?:the|its))?\s+`(?P<label>[^`\n]+)`"
        r"(?=[^\n]{0,160}?(?:\s+label|\s+from\b|\(`remove-labels`\)))",
        re.MULTILINE,
    ),
]

# Parenthetical markers that appear right after the label being written:
#   "(`add-labels`)" / "(`remove-labels`)".
# The dropped `\`add-labels\`\\s+safe-output` form was too loose: meta
# prose like "the `add-labels` safe-output is allowlisted to `sdd:ready`"
# would pull in unrelated labels. The clause-start imperative patterns
# already catch the actual write phrasings without the meta-tag.
ADD_MARKER_RE = re.compile(r"\(`add-labels`\)")
REMOVE_MARKER_RE = re.compile(r"\(`remove-labels`\)")
MARKER_WINDOW_CHARS = 120


def _last_label_before(body: str, end: int, label_catalog: set[str]) -> str | None:
    start = max(0, end - MARKER_WINDOW_CHARS)
    window = body[start:end]
    last: str | None = None
    for m in BACKTICK_TOKEN_RE.finditer(window):
        tok = m.group(1).strip()
        if looks_like_label(tok, label_catalog):
            last = tok
    return last


def prose_write_sets(body: str, label_catalog: set[str]) -> tuple[set[str], set[str]]:
    added: set[str] = set()
    removed: set[str] = set()

    for pattern in ADD_LABEL_PATTERNS:
        for m in pattern.finditer(body):
            label = m.group("label").strip()
            if looks_like_label(label, label_catalog):
                added.add(label)

    for pattern in REMOVE_LABEL_PATTERNS:
        for m in pattern.finditer(body):
            label = m.group("label").strip()
            if looks_like_label(label, label_catalog):
                removed.add(label)

    # Parenthetical fallback: catch labels tagged with `(`add-labels`)`
    # or `(`remove-labels`)` that the imperative patterns missed (for
    # example "Then apply `needs-human` (`add-labels`)").
    for m in ADD_MARKER_RE.finditer(body):
        label = _last_label_before(body, m.start(), label_catalog)
        if label is not None:
            added.add(label)
    for m in REMOVE_MARKER_RE.finditer(body):
        label = _last_label_before(body, m.start(), label_catalog)
        if label is not None:
            removed.add(label)

    return added, removed


def prose_safe_output_refs(body: str) -> set[str]:
    refs: set[str] = set()
    for m in BACKTICK_TOKEN_RE.finditer(body):
        tok = m.group(1).strip()
        if tok in SAFE_OUTPUT_NAMES:
            refs.add(tok)
    return refs


def report_diff(
    workflow: str,
    kind: str,
    allowed: set[str],
    used: set[str],
    exceptions: dict[str, list[str]],
) -> list[str]:
    failures: list[str] = []
    allowed_but_unused = (allowed - used) - set(
        exceptions.get(f"{kind}-allowed-but-unused", [])
    )
    used_but_not_allowed = (used - allowed) - set(
        exceptions.get(f"{kind}-used-but-not-allowed", [])
    )
    for name in sorted(allowed_but_unused):
        failures.append(
            f"{workflow}: allowlist includes '{name}' but no prose instruction writes it ({kind})"
        )
    for name in sorted(used_but_not_allowed):
        failures.append(
            f"{workflow}: writes '{name}' but allowlist does not include it ({kind})"
        )
    return failures


def iter_workflow_sources() -> Iterable[Path]:
    for path in sorted(WORKFLOWS_DIR.glob("*.md")):
        yield path


def main() -> int:
    label_catalog = load_label_catalog()
    exceptions = load_exceptions()
    all_failures: list[str] = []

    for path in iter_workflow_sources():
        parsed = parse_workflow(path)
        if parsed is None:
            continue
        frontmatter, body = parsed
        if "safe-outputs" not in frontmatter:
            continue
        workflow = path.stem
        wf_exceptions = exceptions.get(workflow, {})

        declared_add, declared_remove = declared_label_sets(frontmatter)
        prose_add, prose_remove = prose_write_sets(body, label_catalog)
        all_failures.extend(
            report_diff(workflow, "add-labels", declared_add, prose_add, wf_exceptions)
        )
        all_failures.extend(
            report_diff(
                workflow, "remove-labels", declared_remove, prose_remove, wf_exceptions
            )
        )

        declared_so = declared_safe_outputs(frontmatter) & SAFE_OUTPUT_NAMES
        prose_so = prose_safe_output_refs(body)
        all_failures.extend(
            report_diff(workflow, "safe-outputs", declared_so, prose_so, wf_exceptions)
        )

    if all_failures:
        print("Safe-output allowlist contract: FAIL")
        for line in all_failures:
            print(f"  {line}")
        return 1

    print("Safe-output allowlist contract: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
