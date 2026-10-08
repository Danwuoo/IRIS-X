# E13 paired-search-budget diagnostic

Status: version 12 reached terminal ERROR at 02:53:05 UTC. The exact delivery
was retrieved once and independently verified as partial failure evidence.
No test has both arms committed; the search-budget question remains unanswered.
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

## Reapproved single admission

The owner explicitly approved package disclosure at 02:22:38 UTC. The expired
candidate001 and unsent journal remain intact. Candidate002 changes only the
source-commit binding and fresh resource observation; all 55 source-file hashes
and 78 non-plan payload hashes are identical. A fresh independent review passed
and recaptured the exact SDK wire. The initial read-only quota refresh returned
401; the official SDK renewed the existing login without a new grant or scope.

Exactly one SaveKernel was accepted as version 12 at 02:28:07 UTC. Its raw
receipt SHA-256 is
`9f979f0ca55518cf0df3a1ad5e0d01f5f8db4087cf5b6ba24c49000b40c60244`.
The pre-send 02:28:05 UTC quota observation remained 6139.2461 free charged
seconds, zero reservation and paid scaling disabled. Source is `23018f6`,
plan is `45a833b265f85fae7de4a431aca0ecad25be47f9f08b448cb2b9a667db571981`.
The bounded terminal monitor runs actively; no duplicate upload is permitted.

## Terminal failure and what is actually established

Worker 3's search240 cumulative event ledger reached 8,387,879 bytes of its
8 MiB allowance. Only 729 bytes remained; the actual next reservation would
need 1,160 bytes. The guard rejected call 3704 before model entry; 3703 calls
had completed. This was an instrumentation capacity failure, not a model,
forward-budget, time-budget or paid-quota rejection. The coordinator then
stopped the other three workers and exported the retained evidence successfully.

Independent data checks and trusted committed-source CPU replay establish:

- Four L4 workers retained 128 optimizer updates each, 512 observed updates,
  1,588,992 training input tokens and 789,888 supervised tokens.
- Only worker 3 completed its training/reset finalization proof (128 updates);
  no worker completed a qualified shared-state pair.
- Eight of twelve test executions started. Five committed: three short-arm
  tests and two long-arm tests. Three were interrupted; four never started.
- The five committed checkpoints contain ten retained attempts. Their source
  formatting, inverse transforms, eight-view verifier inputs, native ranking
  and sealed output projections pass independent CPU evidence replay.
- Zero matching test pairs, zero qualified tests and zero qualified workers.
  Gold stayed closed and correctness scoring was deliberately withheld.

The experiment cannot establish whether 240 seconds improves candidate oracle
coverage or top-two accuracy. Missing/unmatched runs must not become a negative
scientific result. CPU replay does not numerically re-run model logits or DFS.

The delivery is 4,653,835 bytes with SHA-256
`0acbfa23a453450a7a78c19b7da05a8d604b0858b1e63f0b5590f3f69be26d6a`.
The unchanged nested runtime archive hashes to
`49ec9dafa8e39edf42de426e195464db2a0c83cd8a06a70d48991bfeaee83c31`.
Coordinator host wall time was 1333.137782 seconds; this is not GPU billing.
At 02:55:40 UTC, free charged quota was 3324.7481 seconds, reservation zero,
paid scaling disabled. Account usage rose 2814.498 seconds since admission;
other account activity is not excluded, so this is not a job-specific bill.

A bounded offline capacity repair was started in a separate worktree, but the
owner then superseded it with a different new-notebook QuickSave request.
That unfinished repair is not integrated, validated, launched or promoted here.
The original package, journal, delivery, audit failures/corrections and incomplete
work are preserved. No replacement E13 GPU run is authorized or started.
