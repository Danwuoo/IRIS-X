# Decision 0011: Create checkpointing ARC-AGI-2 run-002

Date: 2026-09-21
Status: Accepted

## Context

The frozen `run-001` v3 adapter executes 668 model invocations, retains progress
only in memory, and writes `result-package.zip` only after both configurations
finish. A Kaggle session ran for approximately twelve hours without completing,
and no partial result can be recovered after its kernel or session disappears.

Decision 0009 prohibits changing the frozen `run-001` outbound, notebook,
runner, or manifest identities. Different execution bytes therefore require a
new bundle ID.

## Decision

Create `run-002` with `kaggle-notebook-v4.ipynb` and the checkpointing v4
runner. Preserve every `run-001` byte and identity unchanged.

The `run-002` checkpoint protocol is:

- write an atomic `checkpoint-package.zip` before and after every model
  invocation;
- write canonical `progress.jsonl`, flush it after every event, and mirror the
  same events to notebook output;
- bind every checkpoint to the bundle, trial manifest, model provenance,
  repository revision, notebook, runner, runner core, configurations, execution
  envelope, and checkpoint policy;
- accept only a contiguous prefix of the frozen invocation order;
- on resume, treat an invocation that was pending at interruption as a timeout
  charged at its full reserved duration, then continue with the next invocation;
- carry one cumulative wall-clock budget across sessions and reserve 1,800
  seconds for checkpoint and final result packaging;
- allow resume either from `/kaggle/working/checkpoint-package.zip` or from a
  manually attached private Dataset at
  `/kaggle/input/datasets/danielwuu/run-002-checkpoint/checkpoint-package.zip`;
  and
- create `result-package.zip` only after all 668 required invocation records
  are present.

Final `run-002` observations use execution-observation format `2.0` and record
session count, resume count, interrupted attempts, complete invocation count,
cumulative wall time, and invariant hardware/software identity. Local result
verification recomputes these completeness and identity conditions.

## Preserved boundaries

- Checkpoints contain solver-facing predictions and execution observations only;
  evaluator truth, scores, feedback, and selection evidence remain local.
- Internet, provider calls, credentials, and external paid execution remain
  prohibited.
- The model, workload, two-attempt policy, baseline, candidate, seeds,
  acceptance threshold, and local evaluation process do not change.
- `run-001` remains available only through its exact frozen package and digest.
- This decision authorizes repository implementation, offline package building,
  verification, and preflight for `run-002`. It does not authorize a real
  model/solver run. Real execution still requires a separate explicit owner
  instruction for the final verified `run-002` identities.

## Consequences

An interrupted session loses at most the in-flight invocation, which is
recorded as a charged timeout rather than silently rerun with extra budget. A
completed checkpoint can rebuild the final result package without repeating
earlier invocations. The manually transported checkpoint Dataset is private,
immutable per version, and subject to the same retention controls as notebook
output.
