# Independent review template

This template is not review evidence. An independent reviewer must read the
actual branch, source diff and reports and record what they reran versus only
inspected. Implementing developer/subagent self-review cannot fill this role.

The referenced machine-readable review uses this shape:

```json
{
  "format": "irisx.review.v1",
  "target_commit": "<actual full 40-character implementation SHA>",
  "reviewer_role": "independent",
  "source": "<actual independent reviewer report or review provenance>",
  "outcome": "verified_with_limits",
  "limitations": ["Actual scoped residual limitation"]
}
```

Allowed human outcomes are verified, verified_with_limits, changes_requested
and blocked. Only verified or verified_with_limits may support a verified task.
Record actual independently sourced review provenance in source. Register the
actual JSON report as an evidence document and refer to its catalog
ID in review_refs. The target must match the task's implementation_commit; use a
separate tested_commit in the prose report when necessary. A limited acceptance
must keep limitations visible in the board. Structural validation does not
establish reviewer independence or the correctness of their conclusions.

Record scope, reviewer/source, full target SHA, remote source/CI inspection,
independent environment, commands/results, negative-test inspection, metadata
and frozen-source checks, unavailable tests and limits. The research review
checks the source-faithful relationship between the main question, original
methods, results/limits, current comparison and conditional next steps; keyword
presence is insufficient. Do not provide a review's own containing commit SHA.

Retain an old review as historical when the code/tests/dependencies/CI change.
Request a new review for the affected task and downstream dependency scope.
None of these outcomes authorizes merging a PR or external execution.
