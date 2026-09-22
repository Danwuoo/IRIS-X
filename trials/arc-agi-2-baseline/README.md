# ARC-AGI-2 Trial 002 — completable baseline

This is the single current status page for logical trial
`arc-agi-2-trial-002`. Decision 0014 opened the question; Decision 0015 records
the failed first attempt and authorizes one repaired replacement. Trial 001
remains closed and unchanged.

## Goal

Determine whether exact Qwen3.5-4B can complete four fixed public-training
task/test pairs on Kaggle L4 x4, return identity-bound valid grids, and expose
actionable runtime cost and failure evidence. This is not a public-evaluation
score or an 85% milestone measurement.

## Current state

- Status: `runtime-verified`; the one authorized replacement completed, its
  exact output passed local quarantine, and all external execution and
  retrieval authority for this smoke is consumed. Four valid grids were
  returned, but local exact-match scoring was 0/4, so this is not a successful
  quality baseline or `baseline-measured` evidence.
- Trial ID: `arc-agi-2-trial-002`.
- Failed identity retained: `trial-002-smoke-001`. Kaggle kernel version 1
  ended `ERROR`; its server metadata omitted competition sources and its log
  reports two visible GPUs. It did not reach model generation.
- Authorized replacement: `trial-002-smoke-002`.
- Selected model:
  `Qwen/Qwen3.5-4B@851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`.
- Competition: `arc-prize-2026-arc-agi-2`; runtime input is challenge-only
  `arc-agi_training_challenges.json`.
- Fixed answer-blind task/test pairs: `2dd70a9a/0`, `992798f6/0`,
  `305b1341/0`, and `d968ffd4/0`.
- Workload: exactly four inference-only generation invocations, one task per
  GPU, `num_return_sequences=1`, no TTT, LoRA, retry, or warm-up generation.
- Primary local metric: selected-output exact-match pass@1 mean over four
  outputs. The retained pass@2 score envelope contains one generated attempt
  per job, so its result is equivalent to pass@1 for this smoke. Valid
  generation and completion rates are reported separately.
- Runtime gate: exactly four NVIDIA L4 GPUs with at least 22,000 MiB each,
  verified before model loading by both notebook and runner.
- Budget: 3,600 seconds for the whole session, a bounded finalization allowance,
  and USD 0 external paid cost.
- Transport: a new immutable version of the existing private Dataset and one
  private kernel through Kaggle CLI; notebook Internet disabled; no competition
  submission.
- Submission receipt: Kaggle normalized the title to platform ref
  `danielwuu/iris-x-arc-agi-2-trial-002-repair-smoke-002`, kernel ID
  `135334870`, version 1. Static server metadata records the intended private,
  Internet-disabled `NvidiaL4` request plus the exact competition and Dataset
  sources. Returned evidence independently confirms the runtime allocation and
  model work described below.
- Verified outbound SHA-256:
  `c5abe026303920cc79376e0bc111abbbcd9c616e23ea243f11cbf6488a848c01`.
- Technical preflight SHA-256:
  `c67153b81a13d5087c4ee7c0cb920324ff67ff6709a093a45bf6e5d991337967`.
- Verified result ZIP SHA-256:
  `91b21a5fdae10d5adda5dc59e22626a92d1935f15e06ca5a35cf2eeac0b53097`.
- Local score JSON SHA-256:
  `5712fc5c020026b489d7792c7c89260190b78ada5cc683ad9399cbcc8b36d712`.

## Verified outcome

The returned observation reports four NVIDIA L4 devices, each with 22,563 MiB
visible to PyTorch; the independent `nvidia-smi` rows report 23,034 MiB each.
The mounted challenge digest matches the bound competition input, competition
solutions were not opened, notebook Internet was disabled, and external paid
cost was USD 0. The session completed in 175.427 seconds with exactly four
completed generation invocations and four `valid` terminal jobs.

| Task/test | GPU | Invocation | Generated tokens | Generation seconds | Peak MiB | Exact match |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `2dd70a9a/0` | 0 | 1 | 192 | 12.823 | 9,225 | no |
| `305b1341/0` | 2 | 2 | 420 | 27.157 | 9,498 | no |
| `992798f6/0` | 1 | 3 | 272 | 17.644 | 9,293 | no |
| `d968ffd4/0` | 3 | 4 | 88 | 6.579 | 8,944 | no |

Valid-generation and completion rates are both 4/4. Local test-output exact
match is 0/4 (`0.0`), and no task is all-correct. TTFT and GPU busy time remain
explicitly `unknown`; the result does not invent those measurements.

## Completion states

- `implementation-ready`: offline code and failure-path tests pass.
- `package-ready`: exact challenge/model/source/wheel/outbound bytes plus
  Dataset and kernel staging pass static preflight.
- `submitted-awaiting-result`: the exact kernel version is accepted and its
  static server metadata receipt is retained; this does not claim model start.
- `runtime-verified`: the authorized kernel finishes, output passes local
  quarantine, all four invocation/job records are terminal, and hardware
  evidence proves exactly four L4 GPUs.
- `baseline-measured`: not achievable from this four-output training smoke; it
  requires a separately authorized comparable workload.

## Next action

Preserve the verified local evidence and make no further Kaggle status, log,
output, retry, or submission request under this authorization. Any follow-on
quality experiment needs a new question, identity, execution authorization,
and technical preflight. The 0/4 result is useful falsifying evidence for this
exact single-generation configuration; it is not permission to tune it.

The detailed procedure is
[`docs/development/arc-agi-2-trial-002-kaggle-smoke.md`](../../docs/development/arc-agi-2-trial-002-kaggle-smoke.md).
The source and compatibility audit is [`source-use.md`](source-use.md).

## Fixed boundary

Do not run Trial 001, alter either Trial 002 identity's retained evidence,
execute another kernel, perform a fifth generation call, use competition
solutions or evaluator truth in the runtime, publish data or code, submit to
the competition, call an external model API, or start TTT, LoRA, SFT, RL,
prompt search, a second solver, or a public sweep under this authorization.
