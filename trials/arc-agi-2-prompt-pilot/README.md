# ARC-AGI-2 prompt pilot

This is the current status page for trial `arc-agi-2-prompt-pilot`, authorized
by Decision 0016. It is separate from closed Trial 001 and completed Trial 002.

## Goal

Measure whether instruction-only GEPA proposals can later improve a fixed
Qwen3.5-4B selected-output exact-match baseline without changing the solver,
parser, demonstrations, decoding, or data isolation. The current task covers
only baseline run `prompt-pilot-baseline-001`.

## Current state

- Status: `startup-failed-before-model-load`. The one authorized version 1 was
  accepted, briefly reported `RUNNING`, then ended `ERROR` before the hardware
  gate or runner started. Its kernel launch is consumed and no resubmission is
  authorized.
- Split: 256 optimization-train, 128 selection-dev, 128 locked-holdout from
  pinned official public training; only the first 384 groups run now.
- Runtime: private Kaggle `NvidiaL4` x4, Internet disabled, USD 0 paid cost.
- Solver: `Qwen/Qwen3.5-4B@851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`.
- Baseline: greedy pass@1, thinking disabled, 512 tokens, one generation per
  test-index-0 job, no retry or warm-up.
- Run identity digest:
  `861110e3df3d8f691cd73fe69ef9d08063821593e0bb89f5f398241d445ef74e`.
- Split digest:
  `6176d88ce9a66dcc45584aa09c110898c0f782b1f97e42e1f268c3ef1f25bd2b`.
- Truth-free outbound SHA-256:
  `d6ea290d12e65d0950ae793ccc0af347c91ed89478c9de5700923df9119b8a33`.
- Exact runtime wheel SHA-256:
  `ecc2b429d58be79c7b41d7fee7a4ed122e059a0210c3f18892d05fe3d2cd28c5`.
- The retained Trial 002 result verifier regression reaccepted result digest
  `91b21a5fdae10d5adda5dc59e22626a92d1935f15e06ca5a35cf2eeac0b53097`.
- Private runtime Dataset:
  `danielwuu/irisx-arc-agi-2-prompt-pilot-baseline-001`, version 1, observed
  `ready` with the new wheel and extracted outbound members.
- Submitted kernel:
  `danielwuu/iris-x-arc-agi-2-prompt-pilot-baseline-001`, version 1,
  [Kaggle URL](https://www.kaggle.com/code/danielwuu/iris-x-arc-agi-2-prompt-pilot-baseline-001).
- Submitted notebook SHA-256:
  `feda2df3200292e2ab7e3d29f3f19af8f59766ec544f102d2519c6bd18270639`.
- Failure: at Papermill runtime time 23.284540225 seconds, the notebook raised
  `RuntimeError: exact bound outbound is neither an archive nor the expected
  extracted directory`. This occurred before the hardware inventory, runner,
  model load, or scheduler. There were zero `model_ready` events and zero Qwen
  generation invocations; the 384-job baseline is **not running**.
- Server-source metadata retrieval returned HTTP 403 both while the kernel was
  running and after it failed. Therefore the locally submitted metadata remains
  intended configuration, not server-confirmed metadata evidence. The CLI did
  confirm the actual normalized kernel ref, version 1, `RUNNING`, then `ERROR`.

## Stop boundary

The required four identity-bound `model_ready` events and scheduler dispatch
were not reached. Preserve the failure and stop external monitoring. Do not
retrieve or score results, invoke Codex reflection, repair this consumed run
identity, or launch another kernel under Decision 0016. A repair needs a new
owner-authorized identity and must bind Kaggle's actual Dataset mount topology.
