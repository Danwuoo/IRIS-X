# Benchmark Task Format

## Purpose

Define the minimum fields for benchmark tasks before they are serialized into `benchmark_task.schema.json`.

## Required Fields

- `task_id`
- `task_type`
- `prompt`
- `initial_state`
- `allowed_actions`
- `success_criteria`
- `failure_criteria`
- `side_effect_classes`
- `required_logs`

## Labeling Fields

- Human task success label.
- Human failure class label.
- Verifier accept/reject label.
- Evidence sufficiency score.
- Audit completeness label.
- Failure labels and expected recovery policy for recovery fixtures.
- Recovery assertions for targeted recovery experiments.
- Required, relevant, irrelevant, and omission-trap refs for working-set
  fixtures.

## Open Questions

- Should task difficulty be ordinal, categorical, or computed post hoc?
- What minimum metadata is required for reproducibility?
- Which tasks require multiple independent human labels?

## Related Schema

- [`benchmark_task.schema.json`](../03_schemas/benchmark_task.schema.json)
