#!/usr/bin/env python3
"""Assert the slash-command vocabulary is consistent across the repo.

The pipeline's command vocabulary (`/spec`, `/triage`, `/approve`, `/revise`,
`/execute`) is documented in `shared/sdd-interaction.md` and referenced in
many workflow `.md` sources, doc pages, and ADRs. A new command added in one
place and forgotten in another becomes a silent inconsistency: the workflow
accepts the command, but the docs do not mention it, or vice-versa. This
script asserts three sets are mutually consistent at PR time:

- **W** — commands routed by `wrappers/*.yml`. The gh-aw `.md` sources do
  not themselves filter slash commands; the routing layer is the
  hand-written wrappers (`workflows/README.md` §"Why a wrapper, not the
  gh-aw command: trigger"). The scanner parses `firstWord === '/<name>'`
  literals — this is the idiom used in every wrapper that gates a slash
  command (`wrappers/sdd-spec.yml`, `wrappers/sdd-triage.yml`,
  `wrappers/sdd-execute-*.yml`).
- **T** — commands listed in the `shared/sdd-interaction.md` command table
  under "## Comment-command vocabulary". The table is the source of truth.
- **P** — commands mentioned in prose, across the workflow `.md` sources,
  `docs/sdd/index.md`, and `shared/sdd-interaction.md`. Prose mentions are
  matched with a bounded regex that anchors `/<name>` on a non-word
  preceding character so URL paths (`https://github.com/foo/bar`) do not
  pollute the set. Fenced code blocks are stripped first; the mermaid
  block in `docs/sdd/index.md` is included because the diagram labels
  (e.g. `comment /triage`) are user-facing prose.

Assertions:

- **W == T.** Every wrapper-routed command appears in the table, and every
  documented command has a wrapper that accepts it. A mismatch in either
  direction is a documentation drift bug.
- **P ⊆ T.** Every prose-mentioned command appears in the table. A prose
  mention of an undocumented command is the kind of drift this check exists
  to catch.

Documented exceptions live in `scripts/command-table-exceptions.yml`,
mirroring the pattern from `scripts/safe-output-allowlist-exceptions.yml`.

Exit 1 on any unresolved mismatch; exit 0 when the contract holds.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WRAPPERS_DIR = REPO_ROOT / "wrappers"
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
INTERACTION_FRAGMENT = REPO_ROOT / "shared" / "sdd-interaction.md"
DOCS_INDEX = REPO_ROOT / "docs" / "sdd" / "index.md"
EXCEPTIONS_FILE = REPO_ROOT / "scripts" / "command-table-exceptions.yml"

# `firstWord === '/<name>'` is the idiom every wrapper uses to gate a
# specific slash command (see wrappers/sdd-spec.yml line ~125 et al).
# A literal-string match on this pattern is intentional: the wrappers
# are hand-authored and small, and the literal form is the contract.
WRAPPER_ROUTE_RE = re.compile(r"firstWord\s*===\s*'(/[a-z][a-z-]*)'")

# Match a `/command` token at a word boundary, with a left-context guard
# so URL paths and code identifiers do not register. Accepted left
# contexts: start of line, whitespace, opening paren/bracket, single
# quote, backtick, comma, period, semicolon, or colon. Excluded: any
# alphanumeric, slash, or dash on the left (those produce things like
# `https://github.com/foo` or `path/to/file`).
PROSE_COMMAND_RE = re.compile(r"(?:^|(?<=[\s(\[\'\"`,.;:]))/([a-z][a-z-]+)\b", re.MULTILINE)

# Markdown table separator rows ("|---|---|---|") trip the prose scan
# only if a stray slash-prefixed token sneaks in; they are stripped for
# safety. Triple-backtick fenced blocks are stripped except for the
# mermaid block in docs/sdd/index.md, which carries user-facing labels.
CODE_FENCE_RE = re.compile(r"^```(?P<lang>\w*)\n(?P<body>.*?)^```", re.MULTILINE | re.DOTALL)

# The command-table block in `shared/sdd-interaction.md` is a markdown
# table with a header row `| Command | Where | Effect |`. Rows after
# the separator look like `| \`/spec\` | tracking issue | ... |`.
TABLE_ROW_RE = re.compile(r"^\|\s*`(/[a-z][a-z-]+)(?:\s+[^`]*)?`\s*\|", re.MULTILINE)


def load_exceptions() -> dict[str, list[str]]:
    if not EXCEPTIONS_FILE.exists():
        return {}
    with EXCEPTIONS_FILE.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    out: dict[str, list[str]] = {}
    for kind, entries in data.items():
        out[kind] = []
        for entry in entries or []:
            if not isinstance(entry, dict) or "name" not in entry:
                raise SystemExit(f"exceptions: malformed entry in {kind}: {entry!r}")
            if not entry.get("reason"):
                raise SystemExit(f"exceptions: missing 'reason' for {kind}/{entry['name']}")
            out[kind].append(entry["name"])
    return out


def collect_wrapper_routes() -> dict[str, list[str]]:
    """Return a map of `/command` -> list of wrapper files that route it.
    Reports a list (not a set) so a duplicate routing across wrappers
    is preserved for diagnostics (e.g. `/execute` routes from three
    sdd-execute-* wrappers — by design, one per model tier)."""
    routes: dict[str, list[str]] = {}
    for path in sorted(WRAPPERS_DIR.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        for m in WRAPPER_ROUTE_RE.finditer(text):
            cmd = m.group(1)
            routes.setdefault(cmd, []).append(path.name)
    return routes


def collect_table_commands() -> set[str]:
    """Parse the `## Comment-command vocabulary` table in the interaction
    fragment. Each row's first cell is the command in backticks."""
    text = INTERACTION_FRAGMENT.read_text(encoding="utf-8")
    # Anchor on the section heading so a future fragment edit that
    # moves the table or adds an unrelated table elsewhere does not
    # change the source-of-truth set silently.
    start = text.find("## Comment-command vocabulary")
    if start < 0:
        raise SystemExit(
            f"{INTERACTION_FRAGMENT}: missing '## Comment-command vocabulary' section"
        )
    end = text.find("\n## ", start + 1)
    section = text[start:end] if end > 0 else text[start:]
    commands = set(TABLE_ROW_RE.findall(section))
    if not commands:
        raise SystemExit(
            f"{INTERACTION_FRAGMENT}: no command rows found under "
            f"'## Comment-command vocabulary'"
        )
    return commands


def collect_prose_commands() -> dict[str, list[tuple[str, int]]]:
    """Scan workflow .md sources, the interaction fragment, and the docs
    page for `/command` mentions. Return a map of command -> list of
    (file, line_number) so a mismatch report can name the source."""
    sources: list[Path] = []
    sources.extend(sorted(WORKFLOWS_DIR.glob("*.md")))
    sources.append(INTERACTION_FRAGMENT)
    sources.append(DOCS_INDEX)

    found: dict[str, list[tuple[str, int]]] = {}
    for path in sources:
        if not path.exists():
            continue
        raw = path.read_text(encoding="utf-8")
        # To keep line numbers honest, scan the raw text and skip
        # matches that fall inside a non-mermaid fence rather than
        # stripping fences first (which would shift offsets).
        # Build a list of (start, end, lang) for every fenced block so a
        # raw-text scan can decide whether a `/command` hit is inside a
        # non-mermaid fence (and therefore code, not prose).
        fences: list[tuple[int, int, str]] = [
            (m.start(), m.end(), m.group("lang")) for m in CODE_FENCE_RE.finditer(raw)
        ]

        for m in PROSE_COMMAND_RE.finditer(raw):
            offset = m.start()
            in_fence = False
            for fs, fe, lang in fences:
                if fs <= offset < fe and lang != "mermaid":
                    in_fence = True
                    break
            if in_fence:
                continue
            cmd = "/" + m.group(1)
            line = raw.count("\n", 0, offset) + 1
            rel = str(path.relative_to(REPO_ROOT))
            found.setdefault(cmd, []).append((rel, line))
    return found


def main() -> int:
    exceptions = load_exceptions()
    routes = collect_wrapper_routes()
    W = set(routes)
    T = collect_table_commands()
    prose = collect_prose_commands()
    P = set(prose)

    failures: list[str] = []

    # W == T. Two directions, separate exception buckets so a deliberate
    # asymmetry (rare; the table and the wrappers should march together)
    # is documented in one direction only.
    wrapper_not_in_table = (W - T) - set(exceptions.get("wrapper-not-in-table", []))
    table_not_in_wrapper = (T - W) - set(exceptions.get("table-not-in-wrapper", []))

    for cmd in sorted(wrapper_not_in_table):
        wrappers = ", ".join(routes[cmd])
        failures.append(
            f"wrapper routes `{cmd}` ({wrappers}) but it is not in "
            f"shared/sdd-interaction.md command table"
        )
    for cmd in sorted(table_not_in_wrapper):
        failures.append(
            f"shared/sdd-interaction.md command table includes `{cmd}` "
            f"but no wrappers/*.yml routes it"
        )

    # P ⊆ T. Prose mentions of an undocumented command. Each mismatch
    # lists the first occurrence so the author can find it fast.
    prose_not_in_table = (P - T) - set(exceptions.get("prose-not-in-table", []))
    for cmd in sorted(prose_not_in_table):
        first_file, first_line = prose[cmd][0]
        failures.append(
            f"{first_file}:{first_line} mentions `{cmd}` "
            f"but it is not in the command table"
        )

    if failures:
        print("Command-table consistency: FAIL")
        for line in failures:
            print(f"  {line}")
        return 1

    print(f"Command-table consistency: OK ({len(T)} commands: {', '.join(sorted(T))})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
