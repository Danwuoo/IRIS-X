# ARC-AGI-2 prompt pilot

This is the current status page for trial `arc-agi-2-prompt-pilot`, authorized
by Decisions 0016–0019. It is separate from closed Trial 001 and completed
Trial 002.

## Goal

Measure whether instruction-only GEPA proposals can improve a fixed
Qwen3.5-4B selected-output exact-match baseline without changing the solver,
parser, demonstrations, decoding, or data isolation. Decision 0019 ran the
bounded dependent search and attempted the final locked-holdout comparison.
The failed `prompt-pilot-baseline-001` and recovered
`prompt-pilot-baseline-002` identities remain frozen.

## Current state

- Status: `search-complete-final-holdout-unscored`. The controller consumed
  exactly 10/10 proposal attempts. Nine distinct legal proposals were each run
  once; G2 failed in the proposer and used no GPU. No proposed instruction beat
  B1 on frozen selection-dev, so B1 was selected as `G*` with `12/128 = 0.09375`.
- Candidate exact-match results were:

  | Candidate | Optimization-train | Selection-dev |
  | --- | ---: | ---: |
  | B1 | 18/256 | 12/128 |
  | G1 | 7/256 | 5/128 |
  | G2 | proposer failed | not run |
  | G3 | 14/256 | 9/128 |
  | G4 | 11/256 | 8/128 |
  | G5 | 9/256 | 7/128 |
  | G6 | 10/256 | 6/128 |
  | G7 | 11/256 | 10/128 |
  | G8 | 10/256 | 10/128 |
  | G9 | 7/256 | 8/128 |
  | G10 | 8/256 | 8/128 |

- The B1-only 128-case final holdout was opened exactly once as private Dataset
  version 14 and kernel version 10. Four distinct L4 GPUs passed the hardware
  gate, but runtime validation stopped before model load or generation because
  the official competition mount's visible task `f3e62deb` differed from the
  Decision 0019 pinned upstream commit. The terminal error was
  `ValidationError: runtime competition case differs: f3e62deb`.
- The single authorized terminal output retrieval is consumed. It returned
  `runtime-failure.json`, preflight, progress, the original outbound, and the
  kernel log, but no checkpoint or `result.zip`; therefore no local recovery or
  holdout score is possible and no retry is authorized. Failure evidence digest:
  `deaa2fbb8a780b31fd57642443f174971e21d8dde70af3cd980fcd70d31d5b4a`.
- Final holdout run identity digest:
  `5904b7e1f261be30d8faac90064800cbe850c083770884e1a6cf189b6e9f2f72`;
  truth-free outbound digest:
  `dcfbba24656030205650c94409707a42e6571a74939c0fe307c4bfdecce1dfc8`;
  final runtime wheel digest:
  `8091171cc787372595e7af32dd0cd2b2c24758f6dca78e684d81dd4b1d6672fd`.
- The ledger conservatively reserves 3,968/4,480 generation invocations: 384
  baseline, nine candidate workloads of 384, and the 128-case final holdout.
  Runtime evidence shows the holdout failed before model load, so actual completed
  Qwen calls remain 3,840. No retry, hidden warmup, fifth proposal phase, public
  evaluation, or competition submission occurred.
- Baseline 002 reported all 384 terminal jobs (380 `valid`, 4 `invalid`) and
  then failed before writing `result.zip`. Decision 0018's single output
  retrieval recovered its complete checkpoint and progress evidence; local
  deterministic packaging supplied a verified, truth-free result without
  another generation.
- Deterministic selected-output exact-match pass@1: optimization-train
  `18/256 = 0.0703125`; selection-dev `12/128 = 0.09375`; overall
  `30/384 = 0.078125`. All four invalid outputs are in the train denominator.
  The score report is bound to digest
  `6f189242d8fc1d9a744a7c79ed0acabec235e2f684466726537c1cd7972d761c`.
- DSPy 3.3.1 and GEPA 0.1.4 remained isolated controller dependencies;
  candidate runtime bytes did not import them. The frozen search result digest
  is `058214e6cc736b56f7743d578b0576f34c06b62a8fbd84efe7890439350073d5`.
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
the gate, completed all 384 jobs, and has a locally recovered, verified, scored
result. The Decision 0019 search completed without improving on B1. Its one
final holdout launch failed closed before model load because the pinned public
source and current competition mount differed, and its one output retrieval
contained no recoverable predictions. Decisions 0017–0019 are consumed. Do not
retry the holdout, create another candidate or Dataset/kernel identity, open a
different split, or reinterpret the missing holdout score as zero. Preserve the
controller ledger and all terminal evidence; further external work requires new
explicit owner authority and a new governing decision.
