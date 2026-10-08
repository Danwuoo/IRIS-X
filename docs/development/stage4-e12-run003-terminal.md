# E12 run003 / Kaggle v11 terminal result

The telemetry repair is runtime-verified. The sole private version 11 reached
Kaggle `COMPLETE`, and independent data checks plus trusted CPU source replay
verified all four worker pairs, 768 optimizer updates and 12 native test
executions. The isolated retained-candidate public-development diagnostic is
**1/6 top-1 and 1/6 top-2 in each arm**. This is separate from **0/6
output-qualified tests in each arm**; incomplete search does not imply zero
candidate correctness.

## Immutable execution identity

- Run: `stage4-e12-probe-prefix-20261008-003`
- Notebook: `danielwuu/stage4-e10-probe-20261006-001`, ID 137327571, version 11
- Submitted source: `1c040c7eb8c4e77bcce170dd36cbd5b933453489`
- Plan: `db8d4bf61f292c68fc45ba747be2908869bac089d98fbb4c00ad8b178a08f83f`
- Package manifest: `291155117fc68ef2634151c2091366c230b2de7d621cc725e4c5de6d64b58cef`
- Notebook SHA-256: `abb786330caef8cbe57774c36762fffbd127ccc43219de4e93d265f3adf6615c`
- One accepted `SAVE_AND_RUN_ALL`; no extra run or official competition submission
- Terminal observed at 2026-10-08 01:24:39 UTC, bracketed by exact source/version reads
- Delivery: 6,333,693 bytes, SHA-256 `faea1163e25990b655684e66cafd8d52b568478ecf140ea8debe194edf3aba89`
- Nested runtime: 380 members, SHA-256 `5bfe73afe5501b3e2a03b82c65e5f9175a5b23847096983bb0cfc70a77dbd647`

The failed v10 package, receipts and 646-update partial evidence remain unchanged.
Two unsent local packaging candidates were preserved before the final reviewed
candidate003. These were packaging iterations, not provider runs.

## What completed

All 768 reserved training forwards/backwards/optimizer updates completed and
cross-reconcile with trace/callback evidence: 256 short-arm and 512 long-arm
updates. Each task pair uses the same original 128-row preparation, full-horizon
sampler/scheduler, original warmup, baseline and RNG, with an independent fresh
optimizer. All eight arm resets/disposals, four final resets and 28 controls
pass. Four distinct BF16 NVIDIA L4s, per-worker and aggregate memory limits,
shutdown and finalization reserves are evidenced. No telemetry collision recurred.

The full trusted CPU verifier replayed all eight arm answer records, 12 source
view constructions, 25 candidate parsing/inverse-transform/eight-view records
and 12 native rankings. It imported no returned Python, Torch or model package
and made no model, GPU or provider call. Stored NLLs and training observations
were verified as evidence, not numerically recomputed; DFS/model numerical
parity is not claimed.

## Retained candidates versus qualification

| Arm | Native test executions | Retained attempts | Missing attempt slots | Top-1 exact match | Top-2 exact match | Qualified tests |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 64 updates | 6 | 6 | 6 | 1/6 | 1/6 | 0/6 |
| 128 updates | 6 | 9 | 3 | 1/6 | 1/6 | 0/6 |

Accuracy is an isolated evaluator-side diagnostic of the retained candidates on
the full six-test denominator. Gold remains outside the runtime, outbound
package and preserved result archive. These four selected, previously exposed
public-development task clusters and one technical repeat do not establish an
independent benchmark or a causal quality comparison.

Eleven tests stopped at `source_dfs_deadline` and one at `inference_deadline`;
none exceeded its 150-second total window. All tests committed, but none
completed the full native search. Fifteen attempts survive, with explicit null
missing slots. There is no official score, promotion, full E12-screen result,
BASE0 causal claim, or official-scoring-ready candidate.

## Time and free quota

Coordinator host wall time was 1,656.123758 seconds; the outer interval through
post-write receipt was 1,666.962872 seconds. These are host observations,
not GPU kernel duration or allocated-GPU cost.

The post-terminal authenticated quota observation at 01:25:07 UTC shows
6,139.2461 free charged-quota seconds (about 1.705 hours), zero reservation and
typed pay-to-scale disabled. Account usage increased by 3,458.162 seconds in the
same quota window. Other account activity is not excluded, so this is not a
job-specific bill or evidence of per-arm/total-cost reduction. Paid ceiling
remained USD 0. This quota observation grants no further run authority.

## Honest local validation and recovery record

The final affected suite passed 108 tests with two optional SDK skips; the
independent final telemetry plus genuine-SDK transport suite passed all 30.
The full repository aggregate remains non-green: 1,116 tests, one failed test,
35 error reports and 45 skips, with no new failure labels versus the retained
historical baseline. Missing historical fixtures/materials are not concealed.
A separate `/tmp` reserve error passed after using workspace temporary storage.

The exact delivery was downloaded once and matches the provider-log digest.
Its first local verification call rejected an absolute path still containing
`..`; normalized-path offline verification passed without a second download.
The original failure journal remains unchanged. The independent data validator
also preserved its original inherited mandatory-filename rejection and applied
one documented correction: `source-verification-prepare.json` is an optional
legacy allowlist member; the actual producer writes `source-verification.json`.
No runtime byte, scientific threshold or source-binding check was relaxed.

Committed evidence summaries are in `research/stage4-e12/run003/`. Full
immutable package, journal, raw delivery, independent audits, evaluator-safe
aggregate and surviving-history bundle are retained in the preservation archive.
No new experiment or official submission is authorized by this completion.
