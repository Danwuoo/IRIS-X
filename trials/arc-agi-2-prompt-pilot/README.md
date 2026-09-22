# ARC-AGI-2 prompt pilot

This is the current status page for trial `arc-agi-2-prompt-pilot`, authorized
by Decisions 0016 and 0017. It is separate from closed Trial 001 and completed
Trial 002.

## Goal

Measure whether instruction-only GEPA proposals can later improve a fixed
Qwen3.5-4B selected-output exact-match baseline without changing the solver,
parser, demonstrations, decoding, or data isolation. The current task covers
the baseline transport and its one owner-authorized repair. The failed
`prompt-pilot-baseline-001` remains frozen; the distinct
`prompt-pilot-baseline-002` replacement reached its startup stopping condition.

## Current state

- Status: `compute-complete-result-packaging-failed`. At
  2026-09-22T13:05:09Z, baseline 002 reported all 384 terminal jobs (380
  `valid`, 4 `invalid`) and then failed before writing `result.zip`.
- Startup remains verified. At 2026-09-22T12:48:57Z, baseline 002 reported
  four exact-model `model_ready` events on four distinct L4 UUIDs and dispatched
  one initial job to every rank. No output was retrieved or scored.
- Baseline 001 status: `startup-failed-before-model-load`. Its authorized
  version 1 was
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
- Repair: Decision 0017 authorized one new `prompt-pilot-baseline-002` launch.
  Its notebook accepts only the exact owner-qualified current Dataset and
  competition paths or their explicit legacy alternatives, requires exactly
  one match, and reconstructs an extracted outbound only from a closed member
  list. It never searches across `/kaggle/input`. The runtime resolved the exact
  current Dataset and competition paths, reconstructed the outbound, passed its
  digest and four-L4 hardware gates, and entered scheduling.
- Repair run identity digest:
  `15f6d00a764b3849664bdfafa80183f051bf2701c6bd64f01caf9b53168b4051`.
- Repair truth-free outbound SHA-256:
  `da38bb7b165f8ddc66f9709faec3222e9b2129b685d1794da1aa960a05c92a8b`.
- Repair runtime wheel SHA-256:
  `2c54d4cddc82cf791f6ae9b55cd502169aab5bfe576248ba0272d8fbf5b23882`.
- Repair private runtime Dataset:
  `danielwuu/irisx-arc-agi-2-prompt-pilot-baseline-001`, version 2, observed
  `ready` with only the new wheel and extracted baseline-002 outbound members.
- Repair submitted kernel:
  `danielwuu/iris-x-arc-agi-2-prompt-pilot-baseline-002`, version 1,
  [Kaggle URL](https://www.kaggle.com/code/danielwuu/iris-x-arc-agi-2-prompt-pilot-baseline-002).
- Repair submitted notebook SHA-256:
  `b3cb5b523b26e0907bcb611de86e5f8ba66a30e524b2cb7d618b4949f797eae4`.
- Runtime evidence: ranks 0–3 reported model revision
  `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a` and model-manifest digest
  `de2a3d00931355f6b190f7fe67205569af6a41a69d6b458d0f894445c7a13ade`
  on four distinct L4 UUIDs. The scheduler then dispatched job keys
  `66ac4c3b:0`, `5614dbcf:0`, `9968a131:0`, and `e7dd8335:0` to ranks 0–3.
- Terminal failure: `build_result_package` rejected
  `observations.model_ready` because the runner passed its internal integer rank
  keys directly to canonical JSON, which requires string object keys. This was
  a finalization serialization bug, not ZIP compression and not model/runtime
  failure. The retained traceback is
  `ValidationError: $.model_ready: JSON object keys must be strings`.
- The local runner now converts rank keys to strings and has a focused
  regression test. Those repaired source bytes have not been uploaded or
  executed, and no new Dataset/kernel identity has been created.
- The repair uses the unchanged 384 visible cases and split. Prior exact
  tokenizer parity therefore remains applicable, and a byte-exact local
  archive-to-extracted-to-archive reconstruction reproduced the repair
  outbound digest.

## Stop boundary

Baseline 001 did not reach the gate; preserve that failure. Baseline 002 reached
the gate and completed all 384 jobs, but no result package was written. Decision
0017's Dataset update, kernel push, and bounded monitoring authority are
consumed. Do not retrieve output, package or score the retained checkpoint,
resubmit the kernel, or launch a third identity without a new explicit owner
instruction. Prefer recovering and packaging the completed baseline-002
checkpoint, if Kaggle retained it, over repeating 384 generations.
