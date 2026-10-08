# E13 paired-search-budget diagnostic

Status: implementation and independent review complete. Upload is blocked before
provider execution pending explicit permission to disclose the bounded package
to the existing private Kaggle notebook. No E13 upload or GPU run occurred.
Authority and frozen scope: Decision 0064.

The smallest same-footprint diagnostic tests whether additional search walltime
finds useful candidates after one shared native TTT128 training per task.
It does not compare independently retrained states to old E12 results.

## Fixed comparison

| Item | search120 | search240 |
| --- | --- | --- |
| Post-TTT state per task | Same exact inventory | Same exact inventory |
| Training updates, shared | 128 per task; 512 total | No retraining |
| Generation wall window | 120 seconds | 240 seconds |
| Verification reserve | 30 seconds | 30 seconds |
| Total test window | 150 seconds | 270 seconds |
| DFS probability floor | 0.2 | 0.2 |
| Maximum processed sequences per test | 64 | 64 |
| Generation/verification forwards per test | 4096 / 128 | 4096 / 128 |
| Physical inference input tokens per test | 5,242,880 | 5,242,880 |

Both use the same source augmentations, inverse transforms, eight-view NLL
scoring and kgmon ranking. Interleaved verification runs inside the generation
window, with the fixed reserve available afterward. Longer time does not remove
931-token, sequence, forward, input-token, probability or native 540-second
inner-DFS limits. Deadline-based search has hardware/ordering noise even with
RNG restoration. Fresh arm adapters/caches and order counterbalancing reduce,
but do not eliminate, these effects.

Arm order is frozen using only public task IDs and test counts:

- 195c6913 (two tests): search120, search240
- a25697e4 (two tests): search240, search120
- a47bf94d (one test): search120, search240
- aa4ec2a5 (one test): search240, search120

Each arm gets an independent telemetry collector. Do not add overlapping
collector elapsed times or equate host observations to allocated GPU cost.

## Interpretation fixed before results

Report all six tests in each arm, explicit missing slots and distinct task
clusters. Keep source/runtime evidence qualification separate from candidate
correctness. The evaluator alone may read gold; the implementation and launch
controllers receive only truth-free runtime outputs and safe aggregates.
Report oracle coverage among valid parsed candidate grids (and separately among
completed ranked candidates), actual top-two success, aggregate gains/losses,
source views started, cap/deadline terminations and endpoint cost observations.
Unparsed raw beams are not counted as independently established candidates.

- More cost without new correct candidates gives no reason to continue this
  search-expansion direction on this footprint.
- Oracle gains without top-two gains indicate a selection bottleneck.
- Another active cap or continuing truncation prevents interpreting a null
  result as the model's exhaustive capability limit.

This exposed six-test diagnostic cannot establish a general quality win,
statistical significance, official score, promotion or scoring readiness.
No 24-task/35-test expansion is included in this run.

## Preserved prelaunch validation

Source commit: `c269fecccd656fa7f11c05095f4fd894217f8f36`. Independent
review verifies all 55 source files, 78 non-plan payload entries, exact notebook
and a byte-identical fresh SDK wire recapture. All 268 historical tool files
remain unchanged. The new E13 suite passes 149 tests with two optional SDK
skips; the official-SDK transport suite passes all 20.

The full 1265-test aggregate is explicitly non-green: 35 historical error reports,
two failures and 47 skips. One additional unchanged historical process test
failed once, then passed a correctly configured isolated rerun; its cause is
unproven. The first aggregate matched all 36 historical failure labels. Both
receipts and the initial missing-PYTHONPATH rerun error are preserved.

The publication ledger remains prepared-not-sent, reservation 0, no claim,
no pre-send response or SaveKernel receipt. The 02:07:24 UTC authenticated
observation showed 6139.2461 free charged seconds, no reservation and paid
scaling off; it is historical evidence only. Resume requires explicit upload
permission and fresh quota/source checks. No independent GPU result, official
score, search-quality change or completion is claimed.
