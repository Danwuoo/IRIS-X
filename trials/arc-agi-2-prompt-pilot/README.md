# ARC-AGI-2 prompt pilot

This is the current status page for trial `arc-agi-2-prompt-pilot`, authorized
by Decisions 0016–0019. It is separate from closed Trial 001 and completed
Trial 002.

## Goal

Measure whether instruction-only GEPA proposals can improve a fixed
Qwen3.5-4B selected-output exact-match baseline without changing the solver,
parser, demonstrations, decoding, or data isolation. Decision 0019 now runs
the bounded dependent search and final locked-holdout comparison. The failed
`prompt-pilot-baseline-001` and recovered `prompt-pilot-baseline-002` identities
remain frozen.

## Current state

- Status: `baseline-scored-search-initialized`. Baseline 002 reported all 384 terminal
  jobs (380 `valid`, 4 `invalid`) and then failed before writing `result.zip`.
  Decision 0018's single output retrieval recovered its complete checkpoint and
  progress evidence; local deterministic packaging now supplies a verified,
  truth-free result without another generation.
- Deterministic selected-output exact-match pass@1: optimization-train
  `18/256 = 0.0703125`; selection-dev `12/128 = 0.09375`; overall
  `30/384 = 0.078125`. All four invalid outputs are in the train denominator.
  The score report is bound to digest
  `6f189242d8fc1d9a744a7c79ed0acabec235e2f684466726537c1cd7972d761c`;
  holdout remains unopened.
- The Decision 0019 ledger is initialized with 0/10 proposer attempts and
  384/4,480 Qwen generations used. DSPy 3.3.1 and GEPA 0.1.4 are isolated
  controller dependencies; candidate runtime bytes do not import them.
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
- Recovery: Decision 0018's exact version 1 output retrieval and local result
  reconstruction are complete. The retrieval returned the canonical checkpoint,
  progress stream, original outbound, notebook preflight, and failure trace.
- Recovered checkpoint SHA-256:
  `609cdf460fd4edbc394d2179f04150320ae9a61615fab98389b24c33b383ae78`.
- Recovered progress SHA-256:
  `92e310e51b62b286c77267d65aef7842cc67f224f5767d2773fcf6e1c15e1571`.
- Recovered result SHA-256:
  `4764cd569f669f8736461ddf2b5d6ac3bf1c80ddf3f903d669f8d5a43aa054af`
  (1,167,002 bytes; manifest digest
  `45f39b7d1c9488e420f2f59b99c541c71c57d6fb9b403de72c7e1ebfca0db4d8`).
- The result contains only the exact run binding, complete checkpoint,
  predictions, reconstructed execution observations, and original progress
  stream. Independent verification and a second deterministic build produced
  identical bytes. `new_generation_invocations` is 0 and `scored` is false.
- The repair uses the unchanged 384 visible cases and split. Prior exact
  tokenizer parity therefore remains applicable, and a byte-exact local
  archive-to-extracted-to-archive reconstruction reproduced the repair
  outbound digest.

## Active boundary

Baseline 001 did not reach the gate; preserve that failure. Baseline 002 reached
the gate, completed all 384 jobs, and now has a locally recovered, verified,
scored result. Decisions 0017 and 0018 are consumed. Decision 0019 supersedes
their stop points for this trial only: continue through at most ten dependent
DSPy/GEPA plus Codex proposal attempts, distinct private candidate identities,
and one frozen final holdout comparison. Preserve one controller ledger, keep
dev details and all holdout truth out of reflection, and never exceed 4,480
Qwen generation invocations or submit to the competition.
