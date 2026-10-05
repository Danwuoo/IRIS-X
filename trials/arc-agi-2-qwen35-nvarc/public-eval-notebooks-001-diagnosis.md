# Returned BASE-30 / TTT128-30 public development comparison

Date: 2026-10-05, Asia/Taipei.
Status: local archive, source, workload, reset and score verification complete.
Authority: the owner returned both run-named ZIPs in the main checkout and
requested analysis, reporting BASE about 24 minutes and TTT about 2 h 21 min.
The [save record](public-eval-notebooks-001.md) retains the consumed
[Decision 0060](../../docs/decisions/0060-save-two-public-evaluation-notebooks.md)
identities. This analysis made zero provider requests or real solver/GPU calls.

TTT increased model-only top-two exact matches from **5/172 to 10/172**,
an observed **2.91 percentage-point** gain, at about **5.88 times** the
owner-reported elapsed time. Both packages finished all 120 tasks without a
recorded worker/program exception. Their `partial` outcomes describe planned
test inference deadlines. All 120 TTT epochs completed their original 128
updates and verified reset. Candidate absence remains the largest score loss.

## Scores and paired outcomes

The primary denominator preserves every test in the exact shared saved input.
Solutions were read only by the local evaluator after receiving the outputs;
they were absent from the notebook payload and runtime evidence. Legal `[[0]]`
fillers receive no model coverage or model correctness credit.

| Quantity | BASE-30 | TTT128-30 |
| --- | ---: | ---: |
| Tasks / test inputs | 120 / 172 | 120 / 172 |
| pass@1, first ranked candidate | 5/172 (2.91%) | 8/172 (4.65%) |
| pass@2, either ranked submission slot | 5/172 (2.91%) | 10/172 (5.81%) |
| Retained pool oracle | 6/172 (3.49%) | 11/172 (6.40%) |
| Tests with a verified model candidate | 32/172 (18.60%) | 54/172 (31.40%) |
| Retained candidate sequences | 53 | 155 |
| Task-average top-two test fraction | 2.50% | 5.14% |
| Tasks with every test correct in top two | 3/120 | 4/120 |
| Raw submission test pass@2 | 5/172 | 10/172 |

Raw submission matches equal model-only matches; no filler happened to add a
correct answer. Pool oracle is descriptive coverage of the retained pool, not
an additional submitted attempt. Test-weighted pass@2 and task-average success
have different denominators and must not be presented as the same metric.

The paired top-two outcomes are four correct under both profiles, six TTT
gains, one TTT loss, and 161 wrong under both. Test indices below refer to the
zero-based saved variant input, including its extra tests described below.

| Change | Task / test | BASE candidate count | TTT candidate count |
| --- | --- | ---: | ---: |
| TTT gain | `3a25b0d8` / 1 | 0 | 3 |
| TTT gain | `78332cb0` / 1 | 2 | 4 |
| TTT gain | `b6f77b65` / 1 | 1 | 1 |
| TTT gain | `d35bdbdc` / 2 | 2 | 2 |
| TTT gain | `e8686506` / 0 | 3 | 7 |
| TTT gain | `eee78d87` / 0 | 1 | 3 |
| TTT loss | `38007db0` / 0 | 2 | 0 |

Coverage gained on 25 tests and was lost on three, for a net increase of 22.
The correct BASE answer for `e8686506` was already in its retained pool but
outside its first two positions; TTT brought a correct answer into its top two.
The other five gains lacked a correct BASE pool member. This is one paired
development observation, without repeated-run uncertainty estimates.

## Input provenance correction

The earlier plan called the combined 120/172 input standard ARC-AGI-2 public
evaluation. That designation was too broad. Both saved notebooks use the
**pinned NVARC/TinyRecursive public variant**, challenge SHA-256
`e7c62a4bd211867c6b538f66b8013b81f299663c82ca062f49a52bf439d6e4e8`,
at NVARC commit `846d0198efa752534594e321fc3289fc0a06c657`, path
`external/TinyRecursiveModels/kaggle/combined/arc-agi_evaluation2_challenges.json`.
The associated solution file has SHA-256
`84be4f4f39b79e82c36d565fc878830988b094917f052ee7069aef30b33ca8f1`.

All 120 task IDs match the repository's pinned ARC-AGI-2 source at commit
`f3283f727488ad98fe575ea6a5ac981e4a188e49`. Each of that source's 120 evaluation
files was verified against the retained Trial 001 provenance manifest. The
pinned upstream has **167 tests**, whereas the combined variant has 172.
There are five extra variant tests and two changed public demonstration sets:

| Task | Pinned upstream tests | Saved variant tests | Extra variant indices | Public demonstrations equal |
| --- | ---: | ---: | --- | --- |
| `4a21e3da` | 1 | 2 | 0 | Yes |
| `abc82100` | 1 | 2 | 0 | Yes |
| `b6f77b65` | 2 | 3 | 0 | Yes |
| `d8e07eb2` | 2 | 2 | None | No |
| `f560132c` | 1 | 2 | 0 | Yes |
| `faa9f03d` | 1 | 2 | 0 | No |

All 167 upstream test inputs map uniquely to the saved variant. Corresponding
solution grids agree exactly after this input-based join. The five extra
variant tests have only the pinned combined-source answer provenance; their
origin is not inferred here. They remain in the primary 172-test denominator.

For transparency, descriptive source-matched projections give:

| Projection | Tasks / tests | BASE pass@2 | TTT pass@2 |
| --- | ---: | ---: | ---: |
| Matching pinned upstream test inputs | 120 / 167 | 5/167 (2.99%) | 10/167 (5.99%) |
| Matching pinned upstream inputs and public demonstrations | 118 / 164 | 5/164 (3.05%) | 10/164 (6.10%) |

These are projections of the existing variant execution, not separate official
benchmark runs. The test set presented to the solver was different, including
the extra first tests. Frozen decisions, saved plans, payloads and receipts
remain unchanged. A future canonical-input experiment must use a new identity.

## Runtime acceptance and time cost

Each archive binds to its exact saved plan and all 17 packaged source/input/
configuration payloads. Closed ZIP inventory, path/symlink checks, CRCs, member
hashes, full task/test shape, task checkpoint/result equality and regenerated
submission/audit all pass. BASE has 656 data members plus its manifest; TTT has
1,256 plus its manifest. Both inventories report four distinct BF16 NVIDIA L4s,
Torch `2.8.0+cu128` and CUDA `12.8`. All four workers reported the exact pinned
model ready, at about 192–193 seconds on each parent timer. All 120 tasks were
dispatched and finished; no task was left undispatched and no worker failed.

The 120 baseline/reset observations per profile retain matching full saved/
trainable tensor fingerprints and baseline control output after restoration.
The common baseline fingerprint is
`sha256:4f83cfc93e909edb33bc0d647ffbdf7708d38bb460104a37cf8a6dbc7bf2654e`.
For TTT, the local audit reconstructs all **15,360** original public-demo-derived
source rows, prepared input IDs and supervised masks using the exact source
loader and pinned tokenizer. Actual training-row multisets match the 128 rows
for every task; all 15,360 forwards/backwards/updates completed, with one fresh
optimizer construction per task, the bound native Linux schedule, finite
training evidence, changed trained fingerprints and full baseline restoration.
Totals are **30,713,088 training input tokens / 13,462,144 supervised tokens**.
The retained runtime source guards optimizer state and cleanup; individual
Adam moment tensor bytes were not exported for an independent tensor replay.

For all 53 BASE and 155 TTT retained candidates, local reconstruction verifies
the actual eight-view query/answer token bindings: **424 / 1,240** rows.
Recorded scores remain runtime observations; this audit does not recompute GPU
logits or NLLs. The historical full generation-logit transcript is absent,
and **strict portable GPU numerical replay remains false**.

| Timing | BASE-30 | TTT128-30 |
| --- | ---: | ---: |
| Owner-reported approximate elapsed time | 24 min | 2 h 21 min |
| Recorded parent wall time | 1,290.418 s (21 min 30 s) | 7,896.522 s (2 h 11 min 37 s) |
| Sum of task worker durations | 4,260.132 s | 30,429.269 s |
| Sum of training durations | 0 | 25,298.197 s |
| Median / maximum task training time | 0 / 0 | 176.752 / 825.372 s |
| Sum of test search/verification durations | 3,379.160 s | 3,700.547 s |
| Sum of reset durations | 418.289 s | 422.399 s |
| Median reset time | 3.484 s | 3.513 s |
| Median / maximum test duration | 20.042 / 33.915 s | 20.062 / 31.771 s |

The recorded timer begins in the notebook bootstrap and is captured before
final archive creation; it is not a measurement of the owner's entire observed
Editor session. The difference from the approximate owner times is retained,
without attributing it to an unmeasured phase. Recorded wall-time ratio is
**6.119**, compared with **5.875** from owner times. Parallel worker durations
must not be added to parent elapsed time. Training accounts for **83.14% of
summed TTT task worker duration**, not 83.14% of measured parent elapsed time.

Training time tracks input tokens closely in these 120 tasks (Pearson
correlation 0.9937). The longest task, `981571dc`, trained for 825.372 seconds
on 955,392 input tokens; `d8e07eb2` took 767.052 seconds on 881,920. Both stayed
within the unchanged 1,200-second epoch ceiling. There is no truncated epoch
or evidence that the overall 3,600/14,400-second session ceiling stopped a task.

## Candidate and deadline bottlenecks

| Test termination reason | BASE-30 | TTT128-30 |
| --- | ---: | ---: |
| All source batches completed | 25 | 1 |
| Original-source DFS deadline | 137 | 152 |
| Shared inference deadline | 10 | 19 |
| Total | 172 | 172 |

Thus 147 BASE and 171 TTT tests encountered planned inference deadlines. Some
still retained verified candidates. No exception was downgraded to a normal
deadline. The 30-second per-test allowance is a cooperative software deadline:
an already-running forward and surrounding work can finish after it. Two BASE
tests and eleven TTT tests exceeded 30 seconds; observed maxima were 33.915 and
31.771 seconds. This is not a measured hard 30-second wall bound.

| Resource / score loss | BASE-30 | TTT128-30 |
| --- | ---: | ---: |
| Completed generation batches / maximum available | 351/688 | 207/688 |
| Tests with four completed batch calls | 41 | 1 |
| Generation forwards | 37,761 | 40,917 |
| Verification forwards | 106 | 315 |
| Generation physical input tokens | 3,257,820 | 2,045,460 |
| Verification physical input tokens | 727,840 | 2,075,160 |
| No retained candidate | 140 | 118 |
| Candidates retained, but no correct answer in pool | 26 | 43 |
| Correct answer in pool, but outside top two | 1 | 1 |

All reservations/completions and per-test forward ceilings reconcile. BASE
verification comprises two calls for each of its 53 candidates. TTT contains
310 such calls for 155 fully verified candidates plus five half-completed
candidate verifications abandoned at a deadline. No invalid candidate was
admitted. TTT retained more candidates but completed fewer view batches and
performed about three times as much verification. These observed costs share
the same inference budget; they do not establish which budget split is optimal.

The dominant failure is producing a correct complete candidate within the
search/verification budget. Perfect reranking of retained pools would recover
only one additional test in either profile. Increasing TTT steps has no support
from this comparison: the full epoch already completed and dominates cost.
For further locally planned work, first bind a canonical input and diagnose
candidate generation, source-view coverage and verification allocation. Any
changed runtime profile or GPU run requires separate owner direction; none was
prepared or submitted by this analysis. BASE remains the lower-cost development
control; this single result does not justify dropping that control.

## Retained evidence and validation limits

Owner originals remain in the checkout root, untouched and uncommitted. Exact
copies and the local procedure/results are retained at
`.irisx/public-eval-analysis-20261005-001/`. Their hashes bind this report to
ignored local evidence without committing solutions or raw generated archives.

| Artifact | SHA-256 |
| --- | --- |
| `inputs/nvarc-public-base30-001.zip` (3,810,917 bytes) | `9b267ad8ef37022e59ed571a226c6dc14748d893cfcf56ebdc150548cec1ad23` |
| `inputs/nvarc-public-ttt128-30-001.zip` (10,549,185 bytes) | `bbd0762e0dfc0a42f006ec0b2d98fda52877e2c22d23665d2f81c5bcdf2e5cd2` |
| `input-provenance.json` | `570d7acf6eed62a3e83bc58458b8aab4f6f0ba1fd069583a58a2c245c279d5f5` |
| `analyze.py` | `6f41fe9fceb1f1868b1fce4ecbe625067b4e1d0fb81b93b6a0eee2606e3bd860` |
| `analysis.json` | `c6f5f87a68cb01b0acd0c66d2dfec592d02bba316655751d934023f75753f399` |
| `base-score.json` | `ae85eeae17e26a22d3055c7f0df9f6dc702ec3eefc3458362df49f912c34ddb6` |
| `ttt-score.json` | `dd1dd3b7dbd8430ae256f79147c0a69158139c615cb63370fd38750a7cda649b` |
| `solutions-provenance.json` | `cea783273d46200365e02708e98a88ea258f7874f4486abdbe0c11bc47579d61` |
| `paired-tests.json` | `065681cd7a127606b545341cbfd644432a58eb708455663a9ed69d09e0689361` |
| `per-task.json` | `646f3101d3a83b33e77aedebcb1f9fcc054e5204dc17866c4e916991d1d115f3` |
| `per-test.json` | `2c8ddbd07e1cd521b6c6d11b162d6168b666ea6317d1ef61a6be956981b68f36` |

`PYTHONHASHSEED=0` was set before the offline source/token/mask audit. No
published model weights were loaded for the analysis. Paid cost and new solver
generations are zero. Synthetic CPU models used by offline tests are separate
from this returned-output audit and do not qualify GPU numerical parity.

The full repository handoff command ran **523 tests in 637.556 seconds, one
skip, two failures**. One is the repository layout check rejecting exactly the
two owner-supplied root ZIPs; these requested inputs were preserved. The other
is the unchanged synthetic combined-worker success test reporting `partial`
under its short readiness deadline. Its unchanged isolated rerun passed
(one test, 0.779 seconds); the precise transient cause is not established.
The original full-check failure log is retained as
`repository-check.log`, SHA-256
`26baa9f3de71dc4adb98b2bcfa1a10ca8913294b3ab8bf5b3ac2ba7b43c122e4`;
the isolated rerun is `combined-test-recheck.log`, SHA-256
`98dd07f735a73e893f439e5eace21daa4ba67e1f23b5d4d8ff765468949fb5f1`.
This is not a claim that the full repository check passed. All **13 focused
public-eval tests passed in 21.975 seconds**; their log is
`public-eval-tests.log`, SHA-256
`369a157c898195dee606bcdc3b26daa336a81af54a682d12d51226b3fa25d06a`.
After documentation changes, repository invariants report only the same two
owner root ZIP paths; other invariants and documentation links pass. The log is
`final-repository-invariants.log`, SHA-256
`a7cdf9467b049aa1c77ab6419a547364658640e67104dd4916545c4545f21a47`.
Diff whitespace checks pass. No implementation or checker policy was changed
to make this analysis pass, and neither owner original was moved or deleted.

Public SFT139 exposure remains unresolved. This verifies a public development
comparison and bounded runtime evidence, with the input qualification above;
it provides no fresh holdout, semi-private, hidden or official competition score,
no strict GPU numerical parity, no method promotion and no new execution
authority. Monitoring remains stopped.
