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

- Status: `submitted-awaiting-result`; the replacement outbound, Dataset v2,
  kernel staging, and offline preflight are identity-bound and verified, and
  Kaggle accepted kernel version 1. Runtime state is updated only from the one
  scheduled retrieval and verified returned evidence.
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
  outputs. Valid generation and completion rates are reported separately.
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
  sources. This does not claim runtime GPU allocation or model start.
- Verified outbound SHA-256:
  `c5abe026303920cc79376e0bc111abbbcd9c616e23ea243f11cbf6488a848c01`.
- Technical preflight SHA-256:
  `c67153b81a13d5087c4ee7c0cb920324ff67ff6709a093a45bf6e5d991337967`.

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

Do not poll or stream logs. Make the one scheduled status/output retrieval only
after the bounded execution window. If it remains queued at that check, report
the queue state without starting a polling loop or resubmitting.

The detailed procedure is
[`docs/development/arc-agi-2-trial-002-kaggle-smoke.md`](../../docs/development/arc-agi-2-trial-002-kaggle-smoke.md).
The source and compatibility audit is [`source-use.md`](source-use.md).

## Fixed boundary

Do not run Trial 001, alter either Trial 002 identity's retained evidence,
execute another kernel, perform a fifth generation call, use competition
solutions or evaluator truth in the runtime, publish data or code, submit to
the competition, call an external model API, or start TTT, LoRA, SFT, RL,
prompt search, a second solver, or a public sweep under this authorization.
