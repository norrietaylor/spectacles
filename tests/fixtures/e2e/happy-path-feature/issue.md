## Summary

Add a `--version` flag to the sample CLI that prints the package version and exits 0.

## Problem

The CLI has no way to report its own version, so operators cannot confirm which build is deployed.

## Desired outcome

Running the CLI with `--version` prints the version string on stdout and exits 0; no other flag behavior changes.

## Scope notes

Single flag. No config, no new dependencies.
