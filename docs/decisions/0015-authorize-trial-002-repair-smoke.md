# Decision 0015: Authorize the Trial 002 repair smoke

Status: Accepted

Date: 2026-09-22

## Context

Decision 0014 authorized `trial-002-smoke-001`, but the submitted Kaggle
kernel did not reach model execution. The retained version-1 server metadata
has an empty `competition_sources` list, and the returned runtime failure
reports exactly two visible GPUs where the runner required four. The exact
failed log is retained locally with SHA-256
`1c446702785642ff6e7e62f01d0dc3b3360dbef23e90be392640057cda1bf4d3`.
This is failure evidence, not permission to rewrite or reuse the failed run
identity.

The owner has directed a fresh repair that mounts the actual Kaggle competition
`arc-prize-2026-arc-agi-2`, verifies the resulting L4 x4 runtime before model
work, and measures exactly four Qwen3.5-4B inference invocations. This durable
change to the external-execution boundary requires a new run identity.

## Decision

Authorize one replacement private Kaggle smoke under
`trial-002-smoke-002`, subject to all of these bindings:

- the kernel metadata names `arc-prize-2026-arc-agi-2` in
  `competition_sources`, uses `NvidiaL4`, keeps Internet disabled, and names
  the existing private transport Dataset;
- the notebook opens only the competition file
  `arc-agi_training_challenges.json`; competition solution files, evaluator
  truth, scores, and answer-derived metadata stay outside the measured
  runtime;
- the exact challenge file is bound by SHA-256
  `779eaba89790ebad9af02514a7efc0aefaf2cf8236f046a31bbf8b9ec48f20f5`;
- both notebook and runner must observe exactly four NVIDIA L4 devices with at
  least 22,000 MiB each, including an `nvidia-smi` inventory, before model
  loading or generation;
- the fixed tasks are `2dd70a9a`, `992798f6`, `305b1341`, and `d968ffd4`,
  using test index 0 only: one distinct task/test job per GPU;
- the global generation quota is exactly four calls to
  `Qwen/Qwen3.5-4B@851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`'s
  `generate`, with `num_return_sequences=1`, no retry, no warm-up generation,
  no multi-view generation, and no fifth invocation on resume;
- the repair performs inference only. It performs no TTT, LoRA, SFT, RL,
  adapter training, prompt search, or second-solver work;
- each invocation records its ordinal, task/test identity, raw completion,
  parse outcome, terminal state, timing, tokens, and GPU memory in a truth-free
  checkpoint/result;
- the already uploaded model and wheel bytes may be reused. The existing
  private Dataset may receive a new immutable version containing the new
  runtime/outbound bytes; no 9 GB model re-download is required;
- the owner authorizes one kernel push and one later bounded status/output
  retrieval. Do not poll, stream logs, automatically retry, or resubmit; and
- Kaggle Internet remains disabled, paid external cost remains USD 0, and
  public publication and competition submission remain prohibited.

The operator must save the submitted server metadata and verify that the
accepted settings include the competition source and requested machine shape.
That static receipt does not prove runtime success. `runtime-verified` requires
returned output to pass local quarantine and all identity, hardware,
invocation-count, and evidence checks.

## Consequences

`trial-002-smoke-001` remains an immutable failed attempt. Its kernel metadata,
source, output, log, and absence of a competition mount remain retained
lineage. No byte from the repair is assigned that identity.

Decision 0015 supersedes Decision 0014 only for the authorized execution
shape, run identity, workload cardinality, and removal of task-local
adaptation. Decision 0014 continues to establish the separate Trial 002
question, model/source lineage, privacy boundary, zero-paid-cost limit, and
non-submission rule. Trial 001 remains closed.

Failure of `trial-002-smoke-002`, a queued state at the one scheduled check, or
an invalid returned package does not authorize another submission.
