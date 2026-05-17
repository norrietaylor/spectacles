#!/usr/bin/env bash
# leak-scan.sh — fail when a denylisted private term appears in the tree.
#
# The denylist comes from the LEAK_DENYLIST environment variable, supplied as
# a repository or organization secret, one term per line. Terms and matching
# lines are never printed: only file paths are reported, so the public CI log
# cannot itself leak a term. A line beginning with '#' is treated as a comment.
set -euo pipefail

if [ -z "${LEAK_DENYLIST:-}" ]; then
  echo "leak-scan: LEAK_DENYLIST is empty or unset; nothing to scan against."
  echo "leak-scan: set the LEAK_DENYLIST secret to enable the scan."
  exit 0
fi

found=0
while IFS= read -r term; do
  [ -z "$term" ] && continue
  case "$term" in
    \#*) continue ;;
  esac
  if matches=$(git grep --fixed-strings --ignore-case --files-with-matches \
      -- "$term" 2>/dev/null); then
    found=1
    echo "leak-scan: a denylisted term appears in:"
    printf '%s\n' "$matches" | sed 's/^/  /'
  fi
done <<< "$LEAK_DENYLIST"

if [ "$found" -ne 0 ]; then
  echo "leak-scan: FAIL. A denylisted private term is present in the tree."
  echo "leak-scan: terms and matching lines are intentionally not printed."
  exit 1
fi

echo "leak-scan: clean."
