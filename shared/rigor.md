# Evidence standards for agent findings

Every spectacles agent imports this fragment. Before an agent reports a
finding, a problem, or a proposed change, it applies this checklist.

## Required before filing an issue, comment, or PR

1. **Reproduce the finding.** Confirm the problem exists in the current state
   of the default branch. Do not file findings that appear only in history or
   in a stale branch.
2. **Rule out false positives.** Check whether a suppression, a known
   exception, or an existing issue already accounts for the case. If so,
   update the existing item instead of filing a new one.
3. **Cite evidence.** Every finding includes at least one of: a file path and
   line number, a command and its output, or a direct quote from the
   codebase.
4. **Bound the scope.** State what is affected and what is not. Do not make
   broad claims without enumerated examples.
5. **One finding per issue.** Do not bundle unrelated findings. Each distinct
   problem gets its own issue so it can be triaged and closed independently.

## Confidence threshold

Do not report a finding when confidence is below 80%. An uncertain pattern is
raised as a note on an existing item, not as a standalone finding.

## Avoiding noise

- Ignore whitespace-only differences unless the file is generated.
- Do not report a TODO comment as a finding unless it blocks a merge.
- Do not report style that the repository linter already covers; it is caught
  automatically.
