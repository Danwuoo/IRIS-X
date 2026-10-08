# Decision 0064: Run one paired 120/240-second search diagnostic

Status: Accepted
Date: 2026-10-08 (UTC)

At 2026-10-08 01:52:44 UTC, the owner replied “先跑那個實驗” to the
explicit choice between a new technical direction and the proposed paired
120/240-second search experiment. The message is
`Sentinel_4b0cec11ab188191abe81f31076ec619`.

Authorize one distinct private Kaggle attempt,
`stage4-e13-search-budget-20261008-001`, expected version 12 of notebook
`danielwuu/stage4-e10-probe-20261006-001` (numeric ID 137327571), following the
verified terminal version 11. Preserve all consumed E12 and earlier packages,
run identities, source modules, and evidence unchanged. This is a small
four-task/six-test diagnostic on the same exposed public-development footprint,
not an expanded decision panel or independent benchmark.

## Frozen scientific comparison

- Train each task once for the original full 128 updates: 512 total updates.
- Both search arms retain that exact trained tensor state and restore identical
  post-training Python, NumPy, Torch CPU and CUDA RNG states before inference.
- Compare generation wall windows of 120 and 240 seconds, each followed by a
  fixed 30-second verification reserve, yielding total windows of 150 and 270.
  Interleaved verification consumes time inside the generation window, as before.
- Preserve the Qwen3-4B SFT139 model, native tokenizer, TTT schedule, public
  inputs, source views, p=0.2 DFS pruning, ranking, and all non-time search caps.
- Use fresh per-arm answer adapters, caches, counters and inference telemetry.
  Counterbalance arm order by sorted public task IDs within one-test and
  two-test strata; do not change order after seeing results.
- Record started views, deadlines, termination causes, returned candidates,
  retained top two attempts, evidence qualification and observed cost.
  Candidate correctness/oracle/top-two comparison is evaluator-side only;
  gold and answer-derived metadata never enter runtime or source configuration.

The prior v11 arms retrained separately and did not export trained weights.
They are background evidence, not paired controls for this new run. This
experiment does not establish exhaustive search: token, sequence, forward,
input-token, probability and native inner-clock limits remain.

## Resources and one-run transport

Keep exactly four NVIDIA L4 GPUs, private visibility, Internet disabled,
existing pinned model/dependency sources, paid ceiling USD 0, pay-to-scale off,
and maximum internal/provider-requested duration 3600 seconds. Decision 0062's
explicit conservative-reservation waiver continues: refresh and verify actual
positive free quota, zero conflicting reservation and paid scaling disabled
before the sole SaveKernel. Positive quota is not a completion guarantee.
Do not expand the footprint or paid-resource scope to improve feasibility.

Independently review the final committed source, immutable package, exact
notebook and genuine SDK-intercepted wire before admission. Reserve one send
atomically and retain the original receipt; uncertain admission freezes the
identity without blind retry. Actively wait for exact source/version-bracketed
terminal status, retrieve the exact bounded output once, independently verify
it and report the scientific result, then commit and push audited preservation
to the existing private recovery branch. Main remains unchanged.

No official competition submission, hidden evaluation, paid scaling, GCP
execution, new model or broad replacement methodology is authorized here.
A failed diagnostic does not automatically authorize another GPU attempt.
