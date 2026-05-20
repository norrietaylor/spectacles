---
name: Bug
about: Report defective behavior for the SDD pipeline to spec a fix and build it.
title: "bug: "
labels:
  - kind:bug
  - sdd:spec
---

## Summary

One or two sentences describing the defect.

## Expected behavior

What should happen.

## Actual behavior

What happens instead. Include error output or a `file:line` reference where
you can.

## Reproduction

The smallest set of steps that reliably reproduces the defect.

## Scope notes

Anything in or out of scope, constraints, or related work the agents should
know. Leave blank if there is nothing to add.

---

<!-- SDD command vocabulary. Do not edit this footer. -->

This issue is the tracking issue for the fix. It carries the `sdd:spec`
lifecycle label, so `sdd-spec` will draft a spec PR from it automatically.

Steer the pipeline with these comment commands. Each is gated to commenters
with write access to the repository.

| Command | Where | Effect |
|---|---|---|
| `/spec` | this tracking issue | re-run `sdd-spec` to draft or revise the spec |
| `/triage` | this tracking issue, after the spec PR is merged | start `sdd-triage` phase A (architecture) |
| `/approve` | this tracking issue | confirm the proposed plan so `sdd-triage` creates the Unit and task sub-issues |
| `/revise <note>` | a spec, architecture, or implementation PR, or this tracking issue | re-run the owning agent with the note as an added instruction |
| `/execute` | a task sub-issue | run `sdd-execute` for that task ahead of the schedule |

Merging the spec PR advances to the architecture phase; merging the
architecture PR advances to a plan-comment phase, where `sdd-triage` posts
the proposed plan as one comment on this tracking issue. When an agent needs
a human decision it applies the `needs-human` label and posts one comment;
clear the label once you have answered and the agent resumes.
