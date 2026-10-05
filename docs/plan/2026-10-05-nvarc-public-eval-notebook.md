# NVARC public evaluation notebook development

Date: 2026-10-05, Asia/Taipei.
Status: implemented under Decision 0060; exact save receipts and local checks
are retained in the [public notebook record](../../trials/arc-agi-2-qwen35-nvarc/public-eval-notebooks-001.md).

## Objective and first release

Build a private Kaggle notebook for the standard ARC-AGI-2 public evaluation
input: **120 tasks and 172 test inputs**. Obtain a bounded, reproducible public
development measurement without spending another six hours by default.

The recommended first full-set profile is **BASE-30**: the existing published
Qwen3-4B SFT139 model, no task-local training, the original DFS/ranking machinery,
a shared 30-second search-and-verification allowance per test, and a 60-minute
session cap. It is a baseline, not a measurement of the complete TTT method.
Keep **TTT128-30** as a separate comparison using all 128 original task-local
training rows and the same inference allowance. Do not silently replace the
original epoch with a few training steps to make a run appear faster.

The original request covered planning and local development. The owner's later
implementation instruction is recorded in Decision 0060: implement two private
notebooks, debug locally, QUICK_SAVE each once, then stop for manual owner
execution. The consumed official 001 and prior Editor identities remain frozen;
monitoring remains stopped. Current exact artifacts are in the separate save record.

## Evidence behind the time budget

The completed private official-001 preview took 21,681.367 seconds
(6 h 1 min 21 s) for 240 tasks and 259 test inputs. Its 240 worker receipts show:

| Recorded quantity | Value | Interpretation |
| --- | ---: | --- |
| Summed training time across workers | 33,151.062 s | 41.83% of summed worker time; parallel time must not be added to notebook wall time |
| Median training time per task | 101.499 s | Not a maximum or a prediction for the harder public set |
| Longest training time per task | 628.239 s | The long-task tail matters |
| Summed worker time | 79,255.013 s | Includes load, preparation, controls, TTT, search, verification, reset and serialization |
| Old training input tokens | 35,347,968 | Full 128-row epochs on the old preview input |
| Public training input tokens | 30,713,088 | Offline derivation of all 15,360 rows, using the exact pinned tokenizer and original augmentation/cut |
| Public/old token ratio | 86.89% | Half the task count does not imply half the training cost |
| Four-worker training-only linear projection | 7,201.061 s, about 2 h | Illustrative transfer of old seconds/token; excludes all other phases and is not an upper bound |

Public per-task training tokens range from 57,920 to 955,392; median 215,808.
Sequence lengths, parallel balance and the new worker lifecycle can change
throughput. No public GPU timing has been measured. In particular, the
58.17% outside training cannot be described as inference time or model-loading
time alone.

The previous preview input has zero task-ID overlap with this public set. Its
existing predictions cannot be rescored as standard ARC-AGI-2 public evaluation.

Offline timing/token evidence is retained at
`.irisx/stage3-public-eval-20261005-001/notebook-workload-profile.json`, SHA-256
`12479915fd5bc81336c893315c67cd860932ddc51eb2f78d1b19b6ca0e1a5b52`.
The inventory used no model calls, GPU jobs, solution reads or provider requests.

## Source and notebook comparison

Use the cached public input from pinned NVARC commit
`846d0198efa752534594e321fc3289fc0a06c657`:
`external/TinyRecursiveModels/kaggle/combined/arc-agi_evaluation2_challenges.json`.
Its SHA-256 is
`e7c62a4bd211867c6b538f66b8013b81f299663c82ca062f49a52bf439d6e4e8`.
The IDs match the 120 evaluation cases at ARC-AGI-2 commit
`f3283f727488ad98fe575ea6a5ac981e4a188e49`; test entries contain input only.
The prepared local copy is
`.irisx/stage3-public-eval-20261005-001/public-challenges.json`.

Retain model `sorokin/qwen3_4b_grids15_sft139/transformers/bfloat16/1`,
existing offline dependencies and the pinned runtime family from official 001.
Model material digest:
`sha256:27de51ef22658a0cce3a9fc04fac8fc456165645e2665a82b215f72e20194b03`.
Tokenizer SHA-256:
`af6b9e855f9db3192bd9152607708ebd7700b40f9fc5f792a26af70150a96cd5`.
Fix `PYTHONHASHSEED=0` before creating the parent and every worker process.

The owner's [reference notebook](https://www.kaggle.com/code/koushikrudra/failed-in-aimo)
was pulled and inspected without executing it. Retained notebook SHA-256:
`d80acd6a7ca6411e2c734722115aa85d6772f96e81cf3dbe941f4b28f83b81e2`.
It has the same loader/decoder definitions and the same native trainer,
collator, DFS and scoring function ASTs as our submitted package. Its four
persistent workers load once each; our 240-task preview used a new process and
model for every task. Adopt its persistent lifecycle, while retaining stronger
state isolation and explicit failure reporting. The speedup is unmeasured.

Its non-competition preview queues only four tasks. Do not copy that filter
into a full public run or use its preview to estimate all 120 tasks. Its optional
second-model program-induction branch is outside this first release. Downloaded
source contains no execution outputs proving its official score or success.
The comparison is retained under
`.irisx/stage3-reference-comparison-20261005-001/`.

## Proposed profiles

All values below are engineering caps for later implementation, not measured
completion times or execution approval. A run selects exactly one immutable
profile and task set. It does not automatically run this entire table.

| Profile | Task set | TTT | Per-test search + verification | Session cap |
| --- | --- | --- | --- | --- |
| SMOKE | Four reference IDs, five tests | Select BASE or full 128 explicitly | 30 s | BASE: 30 min; TTT: 45 min |
| BASE-30, recommended first full run | All 120 / 172 | None | 30 s | 60 min |
| TTT128-30, later comparison | All 120 / 172 | Full original 128-row epoch per task | 30 s | 4 h |

SMOKE IDs are `0934a4d8`, `36a08778`, `981571dc`, `aa4ec2a5`.
They span 266,240–955,392 training tokens per task and include a two-test task;
they check the long-task and multi-test paths, but are not a random performance
sample. Smoke output is never presented as a full-set score.

For BASE-30, reserve 900 seconds for setup/loading, 300 seconds for export,
and 2,400 seconds for solving. The ideal balanced four-worker inference
allowance is `172 * 30 / 4 = 1,290 seconds`, about 21.5 minutes. This arithmetic
excludes initialization, controls, reset, scheduling and export, and does not
guarantee 60-minute complete coverage. Use measured phase timings to revise the
next immutable profile rather than extend a running profile automatically.

TTT128-30 reserves 900 seconds for startup and 300 for export. Its task training
cap is 1,200 seconds; an incomplete epoch is explicitly incomplete and cannot
produce a TTT-qualified prediction. The original epoch, learning rates,
LoRA topology, public-demo-only labels and optimizer schedule stay intact.
The 4-hour session cap bounds cost; it is not a claim every task will finish.

Keep original source DFS probability threshold `-log(0.2)`, 8192-token context,
931-token answer ceiling, up to four batches of four source views per test,
eight-view verification and `score_kgmon` ranking. Retain ceilings of 4096
generation forwards, 128 verification forwards, 5 MiB physical input tokens,
and 64 processed candidate sequences per test. The 30-second clock includes
verification; do not give each view or batch a new 30-second allowance.
Only complete EOS-terminated legal grids with completed verification enter the
ranked pool. Planned deadlines can reduce coverage, never relax candidate gates.
An in-flight CUDA call can overrun a software deadline; the parent watchdog and
export reserve must bound this and report its actual overshoot.

## Notebook cells and outputs

| Cell | Responsibility |
| --- | --- |
| 1. Experiment description | State public development set, selected profile, complete denominator and exposure qualification |
| 2. Frozen configuration | Run ID, profile, model/input/source digests, seeds, session and per-test budgets; no automatic competition-rerun branch |
| 3. Offline setup | Verify embedded source/input and existing model/dependency mounts; install cached wheels once |
| 4. Initial output | Atomically create complete submission skeleton, coverage ledger and run manifest before model loading |
| 5. Hardware and workers | Require four distinct BF16 L4s; one pinned model per persistent worker; record actual GPU/runtime identities |
| 6. Task dispatch | Queue all selected tasks, cost-order using public input only; report phase timing, test coverage and remaining budget |
| 7. Incremental results | Commit each verified test result, then merge through a single parent writer; preserve every multi-test slot |
| 8. Final export | Stop dispatch before export reserve, retain completed checkpoints, validate schema/bindings and package the profile's run-named ZIP |
| 9. Download summary | Show completed/partial/failed state, model coverage, timeouts and file links; direct returned ZIP to separate local evaluator |

Outputs include `submission.json`, `candidate-pools.json`, `coverage.json`,
`task-timings.json`, `progress.jsonl`, `terminal.json`, the exact input/config,
and a digest manifest inside `nvarc-public-base30-001.zip` or
`nvarc-public-ttt128-30-001.zip`. Include task errors and worker/reset
failure reasons. Model weights and evaluator answers are not packaged.

The initial skeleton has both attempt fields for every selected test. A single
model candidate may be duplicated in the second slot and is recorded as such;
zero candidates use legal `[[0]]` fillers. Fillers are format support, not model
coverage. The parent is the only root submission writer. Atomic replacement
prevents interleaved workers or interruption from corrupting the last checkpoint.

A normal search/session deadline produces a partial run with complete output
schema. Bad model/source material, invalid token bindings, reset failure and
other program errors stay failures with their causes retained. An export helper
may preserve previously committed output after a failure; it must not turn that
failure into a successful experiment. Sudden provider kill/OOM cannot guarantee
a final ZIP, so durable incremental files must be usable independently.

## Worker isolation and evidence

BASE does not construct a Trainer or optimizer. Verify initial weights and
that the baseline remains unchanged, clear each task/test cache, and keep
source cache controls. For TTT, snapshot every original saved/trainable tensor,
including embedding/head `modules_to_save`; construct a fresh Trainer,
optimizer, scheduler and training dataset per task. Reset to cloned baseline,
discard moments/gradients and verify full tensor restoration and baseline
control output before accepting another task. A failed reset retires that
worker; no unplanned model reload or retry is allowed.

Persistent workers change the old fresh-process isolation contract. Add a
two-task sequential differential check against fresh workers and a faulted-TTT
reset check. Real GPU parity remains pending until measured; fixtures only
validate orchestration. Existing cross-Torch strict DFS replay remains false.

Use a separate **public-eval** evidence format for routine timing/coverage,
candidate grids, view/token bindings and eight-view scores. Avoid retaining the
full generation-logit transcript and replaying hundreds of MB in every quick
export. This lighter result is not an accepted historical native evidence
artifact and cannot satisfy the old portable GPU gate. If full native evidence
is requested later, it needs its own explicit profile, storage and export
budget; do not weaken `nvarc_native_submission.py` to make lightweight evidence
pass its existing contract.

## Independent public scoring

The GPU notebook receives public training demonstrations and test inputs only.
No public solutions are embedded, mounted into solver inputs, loaded by its
cells, or used for scheduling, tuning, stopping or TTT. After the run-named ZIP returns,
a separate local evaluator reads the pinned public evaluation solutions.

Report test exact-match pass@1 and pass@2 over **172 tests**, plus task-average
test success over **120 tasks** (mean of each task's top-two test-match fraction)
and the number/fraction of tasks for which all
test outputs match. Missing, timed-out, failed and undispatched cases remain
in the denominator. Report model-only candidate coverage separately from raw
submission exact-match so a filler that coincidentally matches is not attributed
to the model. Any pool-oracle metric must identify retained pool size and is
separate from top-two performance. Validate input/profile/output digests and
the entire task/test set before scoring; reject cross-run joins and duplicate
IDs. Scores from different inference/TTT profiles are labeled separately.

Public-eval checkpoint exposure in SFT139 is unresolved. This is a public
development measurement, not a fresh/locked holdout, semi-private score,
official hidden score or method promotion.

## Development sequence and acceptance

1. Implement `tools/nvarc_public_eval.py`: bound input/profile validation,
   deadline/coverage state, complete incremental output and finite reservations.
   Reuse original-source loading, grid/schema checks and ranking helpers; do
   not edit frozen official packages.
2. Implement `tools/nvarc_public_eval_runtime.py`: persistent four-worker
   lifecycle, BASE path, isolated full-TTT path and phase timing. Bind every
   result to input, model, runtime and profile identity.
3. Implement `tools/stage_nvarc_public_eval.py`: reproducible `.ipynb` renderer
   and offline package/preflight. The proposed design JSON is not a runtime
   admission or callable launcher.
4. Implement `tools/score_nvarc_public_eval.py`: independent full-set reader and
   metrics. Existing ABC scorers provide patterns but remain bound to their
   old small development sets.
5. Validate meaningful failure cases: multi-test deadlines; checkpoint survives
   a later failure; all 120/172 denominator slots remain; candidate ranking and
   filler attribution; no solutions outbound; wrong hashes rejected; interrupted
   task cannot contaminate the next; invalid reset retires a worker. Then run
   repository handoff checks and retain offline preflight evidence.
6. Produce the runnable notebook, exact immutable package and budget review.
   Later runtime validation proceeds through the selected smoke or full profile
   only under the owner's execution direction. Measure real startup, TTT,
   inference, verification, reset and export times before claiming a speedup.

Design parameters are recorded in
[`public-eval-notebook-design-001.json`](../../trials/arc-agi-2-qwen35-nvarc/configs/public-eval-notebook-design-001.json).
The JSON remains the original inert design snapshot. The implementation groups
the nine responsibilities above into four notebook cells: profile instructions,
verified payload/bootstrap and full skeleton, parent execution/export, and an
independently runnable download cell. It reserves the final 10 seconds of each
30-second test for verification. Decision 0060 and the save record govern the
two resulting exact notebooks; real public GPU timing remains unmeasured.
