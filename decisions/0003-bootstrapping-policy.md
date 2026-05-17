# ADR 0003: Bootstrapping policy

- Status: Accepted
- Date: 2026-05-16

## Context

spectacles is itself a spec-driven development pipeline. That raises a
question about its own construction: are the nine demoable units built
through the pipeline, or conventionally?

The pipeline does not exist until its units are built, so the early units
have no choice. But once `sdd-spec`, `sdd-triage`, and `sdd-execute` exist,
the suite could in principle build its own remaining units. Doing so carries
a recursion hazard: an unproven `sdd-execute` would be writing the very
`sdd-validate` and `sdd-review` agents meant to catch its mistakes, with no
validator or reviewer yet in place to catch them.

## Decision

1. **All nine units are built conventionally.** Each unit is authored by hand
   or by a subagent and delivered as an ordinary pull request. No unit is
   built through spectacles' own pipeline.
2. **The first pipeline run targets a fixture, not spectacles.** The first
   real end-to-end pipeline run is the Unit 9 acceptance test: a throwaway
   feature on a fixture repository. It is never a spectacles unit, so there is
   no self-modification during the bootstrap.
3. **Self-hosting is a later, separate decision.** Running spectacles' own
   future features through the pipeline is decided deliberately, and only
   after the pipeline has one clean fixture run behind it.

## Reasoning

- `sdd-execute` is load-bearing; an unproven pipeline must not build it.
- A pipeline that builds its own validator and reviewer has no safety net
  watching that build. Conventional construction keeps a human in the loop
  for every unit.
- Separating self-hosting from dogfooding lets the pipeline be proven on a
  disposable target before it is ever pointed at itself.

## Verification

- Each of the nine unit pull requests is authored conventionally and reviewed
  before merge.
- The Unit 9 acceptance test runs the pipeline end to end on a fixture
  repository, not on spectacles.

## Consequences

- This decision supersedes the spec's Success Metric "Dogfood end-to-end in
  the suite's own repo". Under this policy the first end-to-end pipeline run
  is the Unit 9 fixture-repo acceptance test, not a run on spectacles itself.
- No pipeline run happens until the GitHub App is provisioned and Distillery
  and Serena are reachable. That operator infrastructure is a hard
  prerequisite, separate from and parallel to the unit builds.
- Self-hosting spectacles on its own repository is explicitly not a goal of
  the initial build. ADR 0002 records the same point from the import angle.
