# NVARC verification schedule (E10 local implementation)

This is local, offline engineering under the controller dispatch of 2026-10-06.
The E10 quality and mechanism hypothesis remains pending real execution.
Official 56840442 still has Notebook Threw Exception, null score and unknown
cause. The solver lineage is published **Qwen3-4B SFT139**, not the historical
Qwen3.5 compact pilot. No real weights, GPU screen or evaluator answers are used
by the new tests.

## Baseline and control

The actual public path is `NativeEngine` → `run_one_task` → `solve_test` in
`tools/nvarc_native_multitask.py`. `LightModel` admits generation until the
test's absolute +20-second cutoff and verification until the same start's
+30-second deadline. A forward already admitted may return late. The source
DFS, full-task augmentation stream, inverse transforms, formatter, 931-token
answer ceiling and `score_kgmon` stay unchanged.

`solve_test(..., verification_schedule='interleaved')` is the default. It
verifies a new parsed grid immediately in two batches of four views, reuses
the complete score for subsequent duplicates, then continues generation.
The 64 cap counts processed returned sequences, including invalid and duplicate
occurrences; it is not a unique-grid or raw-return count. Stable ranking uses
the source `len(votes) - mean(eight-view NLL)` getter. Beam scores are retained
without introducing a beam-score priority. Ties keep first grid occurrence.

The default producer is compared directly with main
`90ea1bcd40d9e8c88fb7e849e55257704e9b3c16` in a finite fake-model test:
results, events, calls and votes agree. Existing source/tiny CPU regression
also runs. The telemetry terminal is now serialized **after** its forward/token
deltas are finalized; otherwise a serialized event and its later checkpoint
would contain different telemetry. Without telemetry this changes no output.

## Deferred opt-in

`verification_schedule='deferred'` queues only parsed, inverse-transformed
grids. The queue is bounded by an integer processed cap of at most 64.
Unique identities follow first processed occurrence: batch order, the original
returned-row order (not sorted row ID), then beam order. Every valid occurrence
is retained separately, with its original view, tokens and beam score.
No probability, diversity, view-quota or dispatch policy is added.

After generation stops or completes, the queue drains immediately; it never
waits deliberately for 20 seconds. Admission uses the supplied absolute
verification deadline. It neither resets that deadline nor gives individual
items fresh time. Both arms use the same parent hard cap; no new per-candidate
watchdog exists. `EvidenceModel` honors an explicitly supplied verification
deadline just as `LightModel` already does, while callers without it retain
the old single-deadline contract. Application clocks cannot preempt in-flight
CUDA calls or blocking IO. A complete eight-view return after deadline remains
observed complete, and the next forward is refused.

Only eight finite scores qualify a grid. Four-view partial, unfinished and
pending grids never enter the ranked pool. For every fully verified grid,
**all** its occurrences vote, inserted in original sequence order. This
preserves multiplicity and stable ties even if duplicates occur in later
batches. Score reuse cannot change weighting. Existing exporters separately
audit model slots, duplicate-first fillers and constant fallbacks, retaining
every actual task/test denominator.

## Evidence and replay

The opt-in adds the optional result field `verification_schedule`, now with
format `irisx/nvarc-verification-schedule-v2`, and a closed coarse declaration event.
Its queue records first sequence index, grid digest, state, completed views
and actual call IDs, plus absolute deadlines and separate generation/verification
termination and phase-switch observations. E00 telemetry remains v1 with
optional deferred counters `queued` and `pending`. Its existing sequences retain
source-view multiplicity, returned-token digest, duplicate and vote flags.
Existing host scopes measure exclusive generation, verification, parse/dedup
and ranking; nested/inclusive intervals must not be summed. No new per-token
IO, device synchronization or GPU-kernel timing is added. Observation overhead
on real hardware is unmeasured.

Native strict replay requires `task_specs[task_id].verification_schedule`
to declare deferred and separately supplied caller admissions. An old or
undeclared plan rejects deferred candidate evidence.
It still replays exact DFS logits/clocks, source tokens and inverse transforms.
It independently reconstructs FIFO from processed source returns, verifies
actual eight-view token/NLL bindings in queue order, filters the fully verified
grids, recreates every occurrence vote and calls the original selector.
Changed FIFO, missing votes, partial promotion, token bindings, undeclared
schedule or nested truth are rejected even after event rehashing. Deadline
qualification uses the caller admission described below, not agreement among
producer reports.
Optional telemetry counters/provenance/forward-token deltas are recounted
against the transcript, not trusted as qualification evidence.

## E10 controller repair: caller-admitted budget

The controller's review of `4a2e6f2` found that v1 compared the declaration and
terminal deadlines without binding them to an admitted allocation. Together
changing both verification deadlines by +30 seconds, copying the terminal to
the checkpoint and rebuilding its hash chain was accepted. Its unchanged
submission demonstrates a qualification gap, not actual excess model work.
The old PASS/handoff and controller reproduction remain unchanged. The local
repair independently reproduced that acceptance before changing code; evidence
is under `.irisx/stage4-e10-repair-001/`.

`admit_test_allocation` belongs to the calling coordinator. The closed
`irisx/nvarc-test-allocation-v1` object binds the exact run/plan/task identity,
actual test index, admitted host-epoch start, effective common task/session
deadline, nominal generation 20 seconds, total 30 seconds and verification
reserve 10 seconds. The caller retains its admission separately from worker
events and checkpoints. It must not reconstruct trusted admissions from those
worker reports. Epoch timestamps and this separation do not attest a physical
clock, authentic GPU runtime or tamper-proof operating system.

Both producer and independent replay derive:

```text
test deadline = min(admitted start + 30, admitted common session deadline)
generation cutoff = max(admitted start, test deadline - 10)
```

An unclipped allocation yields start+20/start+30. A session ending 25 seconds
after entry yields start+15/start+25, preserving the existing tail reserve;
with five seconds left, generation admits no call. There is no fresh allowance
per queue item or at phase switch. Later actual tests get independently admitted
starts and the same common session deadline. The legacy interleaved call path
and old single-deadline native fixtures require no allocation and retain their
existing contract.

Deferred `solve_test` requires the caller allocation and refuses adapter
deadlines that differ from its derivation. Schedule v2 declaration, proof and
optional telemetry bind its digest. `build_native_submission(...,
test_allocations=...)` receives the caller-owned task/test map as a **separate
argument**; it never takes that authority from producer evidence. It checks
declarations even in killed/uncommitted prefixes, then checks committed results
and telemetry against the derived deadlines. Missing admissions or v1 deferred
envelopes fail closed. Simultaneously changing declaration, terminal, checkpoint,
telemetry and allocation digest cannot extend the unchanged caller admission.
Changing the trusted caller argument would cross this trust boundary; validating
the coordinator's real clock/admission receipt is future runtime work.

The native exporter accepts that same separate Python argument and binds its
digest into the generation identity and audit. Recovery requires the original
admissions and repeats strict replay; changed admissions cannot recover a prior
generation. No worker-file auto-discovery is added. The current legacy exporter
CLI supplies no admissions, so a new deferred native package through it fails
closed. A real package still needs a reviewed coordinator-to-export admission
transport and immutable caller receipt. Nothing here authorizes such a run.

The public caller creates admissions at actual per-test dispatch and retains
them in its lightweight record. Public record validation is still a consistency
check with `evidence_qualified=false`, never the independent native timing gate.
No GPU synchronization, per-token IO, hardkill, ranking or workload change is
part of this repair. A forward admitted before the derived deadline may return
after it; complete eight-view scores remain complete, and the next entry is
refused. Repair tests include coordinated budget mutations, missing admissions,
fixed/clipped/later-test allocations, actual tiny CPU NLLs with a synthetic
late host return, and E01 generation recovery with caller-admission binding.

Public lightweight records check full-pool and occurrence closure and remain
explicitly short of native qualification. Their task binding already includes
the entire plan digest. The old fixed public run IDs refuse deferred plans.
The only new public envelope here is a distinctly named, unapproved
`stage4-e10-inert-cpu-*` fixture, accepted only with `allow_fixture=True`.
A future real screen needs a separately reviewed, exactly bound runtime package;
this local fixture is not a save or execution envelope.

E01 source/reset/transcript gates, generation transaction/recovery, primary
exception handling and bounded cleanup are untouched. Later test exceptions
and reset failures preserve earlier committed verified tests while marking
the task failed/retired. Uncommitted candidates in a test that raises an
unexpected exception do not gain export qualification. This follows E01's
existing commit boundary. A recoverable verification budget stop retains the
current test's earlier complete candidates and excludes its partial/pending
queue. Recovery revalidates the selected committed generation and grants no
promotion.

## Verification and pending work

`tests/test_nvarc_verification_schedule.py` uses finite fake models/clocks for
default parity, cross-view/batch duplicates, invalid/duplicate cap, FIFO,
early finish, exact 20-second admission, shared 30-second partial stop and
in-flight overrun. Synthetic source-view gain is only a mechanism illustration,
not ARC correctness or GPU throughput. Existing tiny CPU fixtures additionally
exercise real source generation, strict NLL/DFS replay and rehashed negatives,
and matched full 128-row TTT epochs with equal ledgers, trained fingerprints,
candidate scores, occurrence provenance, ranking, reset and E01 recovery.

The new [inert screen draft](../../research/stage4-e10/inert-screen-plan.json)
keeps the research acceptance thresholds and 24-task × 2-arm × 2-repeat screen.
The first six tasks include calibration without extra runs. Task manifest,
actual test/token counts, exact runtime bytes, common parent caps, quota,
source/license/rules and real execution authorization remain pending freeze.
No task list or fresh holdout is created here; evaluator labels and
answer-derived strata never enter the solver or outbound. One final public
development confirmation requires separate final-configuration approval.
