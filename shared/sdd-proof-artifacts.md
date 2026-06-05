# Proof artifacts

Every `sdd-*` agent that defines, decomposes, or verifies work imports this
fragment so the proof-artifact contract is stated once. A proof artifact is a
concrete, re-runnable demonstration that a demoable unit behaves as specified.
It is not a description of a test: it is the test, the command, the URL, the
browser action, or the file assertion that an agent or a reviewer can execute
and observe.

## The five proof-artifact types

Each demoable unit declares its proof artifacts as one or more of these five
types. Each artifact names what is run and what observable result confirms the
unit.

1. **Test.** An automated test (unit, integration, or end-to-end) that fails
   before the unit lands and passes after. The artifact records the test
   command and the expected pass.
2. **CLI.** A command-line invocation whose output, exit code, or generated
   file confirms the behavior. The artifact records the exact command and the
   observable result.
3. **URL.** An HTTP request to an endpoint whose response status, headers, or
   body confirms the behavior. The artifact records the request and the
   expected response.
4. **Browser.** A scripted browser interaction (navigate, click, assert) that
   confirms a user-visible behavior. The artifact records the steps and the
   expected on-screen result.
5. **File.** An assertion about a committed file: that it exists, that it
   contains a required string, or that it conforms to a schema. The artifact
   records the path and the assertion.

## The empty PR rule

A proof artifact must demonstrate behavior that exists only after its demoable
unit lands. The test is the empty-PR test:

> A proof that would pass against an empty PR is a health check, not a proof,
> and must be dropped.

A test that passes whether or not the unit's code is present, a CLI command
that succeeds on the base branch unchanged, a URL that already returns the
expected response, a file assertion satisfied by a file that already exists:
each is a health check, not a proof. It confirms the environment, not the
unit. An agent drops it and replaces it with an artifact that fails before the
unit and passes after.

A `kind:spike` task is exempt from this empty-PR/proof rule because its sole
deliverable is the `docs/spikes/<date>-<slug>.md` write, whose existence is
itself the File-type proof artifact (see `sdd-spike.md`).

## How many per unit

Each demoable unit carries **1 to 3 proof artifacts**. One is enough when a
single artifact unambiguously demonstrates the unit; three is the ceiling so a
unit is not buried under redundant checks. Each artifact must demonstrate
behavior that exists only after that unit lands; an artifact that overlaps
another, or that restates a health check, is dropped rather than kept to reach
a count.

## Verification

- An `sdd-*` agent that emits proof artifacts cites one of the five types for
  each artifact and states the observable result.
- No emitted artifact would pass against an empty PR.
- Each demoable unit carries between one and three artifacts.
