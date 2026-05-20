#!/usr/bin/env python3
"""Assert the `sdd:*` lifecycle label state-machine invariants.

The `sdd:*` lifecycle labels (`sdd:spec` → `sdd:triage` → `sdd:ready`
→ `sdd:in-progress` → `sdd:review` → `sdd:done`) are a state machine
documented in prose in `shared/sdd-interaction.md` and steered through
the `add-labels` / `remove-labels` safe-outputs of the five `sdd-*`
agentic workflows. The invariant "exactly one `sdd:*` lifecycle label
on the tracking issue at a time" is stated in prose but not enforced.
A workflow that writes a new state without removing the old one — or
removes the old without adding the new — silently breaks the contract.

This script statically analyzes the workflow sources and the label
catalogue, derives the realized state-transition graph, and asserts
five invariants:

1. **Classification completeness.** Every `sdd:*` label in
   `templates/.github/labels.yml` is declared in `lifecycle-states.yml`
   as either a lifecycle state or a marker. An undeclared `sdd:*`
   label is an unknown state and fails fast.
2. **Reachability and terminality.** Every state in `lifecycle:` is
   reachable from `sdd:spec` along the `transitions:` graph, and
   `sdd:done` is the only state without outgoing transitions.
3. **Pairing.** For each lifecycle label written via `add-labels` in
   a workflow's prose, the same Markdown subsection (heading-bounded)
   also writes a `remove-labels` of the previous lifecycle state. A
   marker label is exempt — markers are orthogonal and need no pairing.
4. **Single writer.** Each lifecycle label X has exactly one writer
   workflow. The set of workflows whose frontmatter
   `safe-outputs.add-labels.allowed` lists X must match the writer
   named in `lifecycle-states.yml`, modulo the `sdd-execute-*` alias
   collapsing.
5. **Writer match.** The actual writer set agrees with the declared
   `writers:` map. Two distinct writers for the same lifecycle label
   is a hard failure with a diagnostic naming both.

The prose-parsing approach mirrors the technique #83 introduced for
the safe-output allowlist test, deliberately duplicated rather than
shared via import: these checks are independent invariants and a
shared parser would couple them.

Exit 1 on any unresolved violation; exit 0 when every invariant holds.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
LABELS_CATALOG = REPO_ROOT / "templates" / ".github" / "labels.yml"
CONFIG_FILE = REPO_ROOT / "scripts" / "lifecycle-states.yml"

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)

# A heading line at level `### ` starts a numbered step subsection in
# the `## Procedure` blocks of every `sdd-*` workflow source (e.g.
# `### 8. Advance the lifecycle on a merged spec pull request`). The
# pairing rule is structural: a transition is paired when both an add
# and a remove of the relevant lifecycle labels appear within one such
# subsection. A `## ` heading also closes a subsection (the prose may
# leave Procedure for Boundaries/Verification without a `### `).
SUBSECTION_HEADING_RE = re.compile(r"^(##+)\s", re.MULTILINE)

# Imperative phrasings the agents use to write a label, paired with the
# safe-output that effects the write. These mirror the patterns #83's
# allowlist test picks up. The label is captured in group 'label'.
#
# Two equally-valid forms appear in this suite, sometimes in the same
# step:
#   - English imperative: "Remove the `sdd:X` label" / "Add the
#     `sdd:Y` label". The trailing parenthetical `(`remove-labels`)`
#     or `(`add-labels`)` is optional decoration; the imperative
#     itself, with the trailing word "label", is the contract.
#   - Compact form: "remove its `sdd:X` label (`remove-labels`)" and
#     "add `sdd:Y` (`add-labels`)" appear in the sdd-execute step 2
#     prose, where the `(...)` safe-output tag is the disambiguator.
#
# A loose generic "add `sdd:X`" without either anchor would be too
# permissive — the prose body contains plenty of meta references like
# "the `add-labels` safe-output is allowlisted to `sdd:ready`" that are
# not write instructions. Either the word "label" follows, or the
# parenthetical safe-output tag does.
ADD_LABEL_PATTERNS = [
    re.compile(
        r"[Aa]dd(?:\s+(?:the|its))?\s+`(?P<label>sdd:[a-z][a-z0-9-]*|needs-human)`"
        r"(?=[^\n]{0,80}?(?:\s+label\b|\(`add-labels`\)))",
        re.MULTILINE,
    ),
    re.compile(
        r"[Aa]pply(?:\s+(?:the|its))?\s+`(?P<label>sdd:[a-z][a-z0-9-]*|needs-human)`"
        r"(?=[^\n]{0,80}?(?:\s+label\b|\(`add-labels`\)))",
        re.MULTILINE,
    ),
    # "moves to `sdd:X`" / "gains `sdd:X`" — verification-section phrasings.
    re.compile(
        r"\b(?:gains|moves\s+to)\s+`(?P<label>sdd:[a-z][a-z0-9-]*|needs-human)`",
        re.MULTILINE,
    ),
]
REMOVE_LABEL_PATTERNS = [
    re.compile(
        r"[Rr]emove(?:\s+(?:the|its))?\s+`(?P<label>sdd:[a-z][a-z0-9-]*|needs-human)`"
        r"(?=[^\n]{0,80}?(?:\s+label\b|\(`remove-labels`\)))",
        re.MULTILINE,
    ),
]

# A fenced code block is documentation, not a write instruction. The
# state-diagram fence in `shared/sdd-interaction.md` lists every state
# in order; without stripping fences the validator would see a
# pseudo-add of every lifecycle label.
CODE_FENCE_RE = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)


def strip_code_fences(text: str) -> str:
    return CODE_FENCE_RE.sub("", text)


def load_config() -> dict:
    with CONFIG_FILE.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_label_catalog() -> set[str]:
    with LABELS_CATALOG.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or []
    return {entry["name"] for entry in data if isinstance(entry, dict) and "name" in entry}


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
    return frontmatter, body


def declared_add_allowed(frontmatter: dict) -> set[str]:
    so = frontmatter.get("safe-outputs") or {}
    block = so.get("add-labels") or {}
    if not isinstance(block, dict):
        return set()
    return set(block.get("allowed") or [])


def split_step_subsections(body: str) -> list[tuple[str, str]]:
    """Split a workflow body into the `### N. ...` step subsections.

    The pairing rule applies to **procedural** subsections only — the
    numbered steps under `## Procedure` (`### 1. ...`, `### 2. ...`,
    etc.) where the agent is being told to write a label. Level-2
    sections (`## Verification`, `## Boundaries`) are descriptive
    prose: phrases like "the tracking issue moves to `sdd:done` and
    gains `needs-human`" assert observable outcomes, not write
    instructions. Including them would false-positive on every
    workflow's verification block.

    A subsection runs from one `### ` heading up to the next heading
    of any level. The heading line itself is the first line of the
    slice so a diagnostic can name the step.
    """
    sections: list[tuple[str, str]] = []
    stripped = strip_code_fences(body)
    # Index all headings to find subsection terminators.
    headings = [
        (m.start(), len(m.group(1))) for m in SUBSECTION_HEADING_RE.finditer(stripped)
    ]
    for i, (start, level) in enumerate(headings):
        if level != 3:  # only `### ` level subsections
            continue
        end = headings[i + 1][0] if i + 1 < len(headings) else len(stripped)
        chunk = stripped[start:end]
        first_line = chunk.split("\n", 1)[0].strip()
        sections.append((first_line, chunk))
    return sections


def extract_writes(section_text: str) -> tuple[set[str], set[str]]:
    added: set[str] = set()
    removed: set[str] = set()
    for pat in ADD_LABEL_PATTERNS:
        for m in pat.finditer(section_text):
            added.add(m.group("label"))
    for pat in REMOVE_LABEL_PATTERNS:
        for m in pat.finditer(section_text):
            removed.add(m.group("label"))
    return added, removed


def collapse_writer(stem: str, aliases: dict[str, list[str]]) -> str:
    """Map a workflow stem to its logical writer name.

    `sdd-execute-haiku` / `sdd-execute-sonnet` / `sdd-execute-opus` are
    three compiled variants of one source; they share frontmatter and
    prose verbatim (the only difference is the engine model and the
    `model:*` tier). For writer-set purposes they are one writer.
    """
    for canonical, members in aliases.items():
        if stem in members:
            return canonical
    return stem


def main() -> int:
    config = load_config()
    lifecycle: list[str] = config.get("lifecycle") or []
    markers: set[str] = set(config.get("markers") or [])
    transitions: dict[str, list[str]] = config.get("transitions") or {}
    writers_decl: dict[str, str] = config.get("writers") or {}
    writer_aliases: dict[str, list[str]] = config.get("writer_aliases") or {}

    lifecycle_set = set(lifecycle)
    catalog = load_label_catalog()

    failures: list[str] = []

    # Invariant 1: classification completeness. Every `sdd:*` in the
    # label catalogue is declared either as a lifecycle state or a
    # marker. An unknown label fails with a name-and-fix diagnostic.
    catalog_sdd = {name for name in catalog if name.startswith("sdd:")}
    declared = lifecycle_set | (markers & catalog_sdd)
    for name in sorted(catalog_sdd - declared):
        failures.append(
            f"unknown lifecycle state: {name} "
            f"(in templates/.github/labels.yml but neither lifecycle nor marker in "
            f"scripts/lifecycle-states.yml)"
        )

    # Invariant 2a: reachability. Walk the transition graph from
    # `sdd:spec` and check every lifecycle state is reached. An
    # unreachable state is a dead lifecycle entry.
    if "sdd:spec" not in lifecycle_set:
        failures.append("lifecycle is missing the entry state `sdd:spec`")
        reachable: set[str] = set()
    else:
        reachable = {"sdd:spec"}
        frontier = ["sdd:spec"]
        while frontier:
            cur = frontier.pop()
            for nxt in transitions.get(cur, []):
                if nxt not in reachable:
                    reachable.add(nxt)
                    frontier.append(nxt)
    for name in sorted(lifecycle_set - reachable):
        failures.append(
            f"lifecycle state {name} is not reachable from `sdd:spec` "
            f"via the declared transitions"
        )

    # Invariant 2b: terminal state. `sdd:done` is the only state
    # allowed to have no outgoing edges. Any other state with no
    # outgoing edges is a dead-end that traps the pipeline.
    for state in sorted(lifecycle_set):
        if state == "sdd:done":
            continue
        if not transitions.get(state):
            failures.append(
                f"lifecycle state {state} has no outgoing transitions "
                f"(only `sdd:done` may be terminal)"
            )
    extra_terminal = [
        s
        for s in transitions.get("sdd:done", [])
        if s  # any outgoing edge from `sdd:done` is unexpected
    ]
    if extra_terminal:
        failures.append(
            f"`sdd:done` declares outgoing transitions {extra_terminal!r}; "
            f"it must be terminal"
        )

    # Walk every workflow source. For each lifecycle label written via
    # add-labels in a subsection, demand the matching remove-labels in
    # the same subsection (invariant 3). Collect the set of writer
    # workflows per lifecycle label for invariants 4 and 5.
    writers_actual: dict[str, set[str]] = {state: set() for state in lifecycle}

    for path in sorted(WORKFLOWS_DIR.glob("sdd-*.md")):
        parsed = parse_workflow(path)
        if parsed is None:
            continue
        frontmatter, body = parsed
        stem = path.stem

        # Invariant 5 data: frontmatter declares who is allowed to add
        # each label. The validator reads frontmatter as ground truth
        # for "this workflow is permitted to add X". Frontmatter and
        # prose agreement is #83's job; here we only need the
        # frontmatter side for the writer set.
        allowed = declared_add_allowed(frontmatter)
        for label in allowed:
            if label in writers_actual:
                writers_actual[label].add(collapse_writer(stem, writer_aliases))

        # Invariant 3: pairing within a subsection. For each ### step,
        # examine the prose writes. A subsection that adds a lifecycle
        # label X but does not remove a predecessor lifecycle state is
        # a hand-off without a release. The marker exemption: a
        # subsection may add `needs-human` (a marker) without removing
        # anything — that is the documented hand-off pattern.
        for heading, section in split_step_subsections(body):
            added, removed = extract_writes(section)
            lifecycle_added = added & lifecycle_set
            if not lifecycle_added:
                continue
            lifecycle_removed = removed & lifecycle_set
            if lifecycle_removed:
                continue
            # A subsection that adds a lifecycle label and removes
            # none is a pairing violation. Diagnose with the file,
            # heading, and the orphaned label so the author finds it.
            for label in sorted(lifecycle_added):
                failures.append(
                    f"{path.relative_to(REPO_ROOT)} '{heading}': "
                    f"adds `{label}` without a paired `remove-labels` of a "
                    f"predecessor lifecycle state"
                )

    # Invariant 4 + 5: single writer, and the writer matches the
    # declaration. Two writers is a hard failure with both names. A
    # mismatch with the declaration is a softer "expected X, found Y".
    for label in lifecycle:
        if label == "sdd:spec":
            # `sdd:spec` is applied by the `feature`/`bug` issue
            # template, not by an agent's `add-labels` safe-output.
            # It has no agent writer and the validator skips it.
            continue
        actual = writers_actual.get(label, set())
        expected = writers_decl.get(label)
        if not actual:
            failures.append(
                f"`{label}` has no writer: no sdd-*.md workflow declares it in "
                f"safe-outputs.add-labels.allowed"
            )
            continue
        if len(actual) > 1:
            failures.append(
                f"`{label}` has two writers: {', '.join(sorted(actual))} "
                f"(expected exactly one)"
            )
            continue
        only = next(iter(actual))
        if expected and only != expected:
            failures.append(
                f"`{label}` writer mismatch: declared {expected!r} in "
                f"scripts/lifecycle-states.yml, actual writer is {only!r}"
            )

    if failures:
        print("Lifecycle state-machine invariants: FAIL")
        for line in failures:
            print(f"  {line}")
        return 1

    print(
        f"Lifecycle state-machine invariants: OK "
        f"({len(lifecycle)} states, {sum(len(v) for v in transitions.values())} transitions)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
