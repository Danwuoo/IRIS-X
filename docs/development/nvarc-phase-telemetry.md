# NVARC host telemetry

E00 extends the existing public worker and native `solve_test`; the shared
[offline evaluator](arc-offline-evaluation.md) is unchanged except for a paired
task-cluster bootstrap helper. Telemetry contains visible-input and model-output
provenance, never evaluator truth or answer-derived routing labels.

`PhaseTelemetry` lives in `tools/nvarc_public_eval.py`, already transported with
the public runtime. `run_one_task` creates one in-memory collector per task.
Native callers can attach a collector to `adapter.telemetry`; leaving it null
preserves the existing native output schema. No saved package is rewritten.
The legacy public stager still includes its frozen native payloads; those old
payloads cannot acquire the new lifecycle instrumentation by importing a new
public wrapper. A future separately authorized package must bind the current
native producer explicitly. Empty telemetry tests/absent phases stay unknown.

## Timing contract

The clock is monotonic **host wall time**, including existing device readbacks,
finite checks, evidence writes and synchronizations where inside the scope.
GPU kernel time is null. No CUDA synchronization or per-token telemetry IO is
added. The coarse scopes are generation, verification, parse/dedup, ranking,
training, reset, load, export, control and preparation.

The parse/dedup inclusive scope encloses one `solve_test`: formatter/view
preparation, prefix/token processing, inverse/dedup, vote bookkeeping and
existing event callback costs. Generation, verification and ranking are nested
scopes. Their time is subtracted from parse/dedup's **exclusive** time. Therefore
the exclusive phases plus unscoped time partition a collector's elapsed time;
inclusive scopes and detailed intervals overlap and must not be summed.
Parallel worker/task sums cannot be added to the parent's elapsed time.

Training covers the same complete Trainer epoch, `EpochBudget.complete`,
existing final synchronize, trained inventory and its write. The original
training ledger, full-gradient guard and optimizer synchronization remain
unchanged. Reset covers optimizer cleanup, tensor restore, inference reset
control and reset evidence writes. Preparation before training and task-final
export are not silently relabeled as training or reset. Worker model load has
its own `workers/<rank>/load-telemetry.json`. Parent material setup/load and
final export have `parent-telemetry.json`; the completed archive duration is
available only in that sidecar, written **after** the archive. It is not claimed
to be embedded in the ZIP it measures.

Missing scopes are null. An entered zero-duration fake scope is observed zero.
Whole BASE training still has independently validated no-TTT zero in the
existing evaluator; an absent timing scope alone does not establish zero.

Detailed profiling requires `run_one_task(..., detailed_profiling=True)` or
the worker's explicit `--detailed-profiling` flag. It measures positions CPU
copy, model callable host entry, finite-logits guard, verifier readback and
training ledger callback IO. The default per-forward detail context does not
read a clock. Full-gradient scan and optimizer synchronize individual costs
remain null/unobserved: `EpochBudget` is byte-preserved because legacy package
reconstruction binds it. Their cost remains inside training; no residual is
presented as an observed guard measurement. Real GPU overhead is unmeasured.

## Candidate and forward contract

Per-test counters have separate denominators:

| Counter | Meaning |
| --- | --- |
| raw_returned | All beams in completed generation batch results, before the processing cap |
| processed | Sequences examined, including duplicates and invalid parses; original cap 64 |
| invalid | Processed sequences that the original formatter cannot parse |
| duplicate | Parsed occurrences whose canonical grid appeared earlier |
| parsed_unique | Distinct grids parsed, including ones never fully verified |
| verification_started | Unique candidates whose eight-view verification starts |
| partial_verified | Candidates with some returned verifier scores, fewer than eight |
| full_verified | Candidates passing the original eight finite-score gate |
| ranked | Unique final `score_kgmon` grids |
| votes_ranked | Original sequence occurrences inserted into the ranking vote mapping |

Each processed occurrence retains sequence index, source view, source-token
digest/length, candidate digest, duplicate flag and whether it contributed a
vote. Invalid occurrences have no candidate digest. Duplicate votes reuse
scores while preserving their original multiplicity and source provenance.
Partial verification records completed views and call IDs, and does not enter
the ranked pool. An earlier fully verified candidate survives a later 4/8 stop.
Counters observe the existing interleaved loop; they do not create a queue.

Forward reservations/completions and reserved/completed physical input tokens
are deltas of actual adapter counters per test. Training uses the existing
ledger's reservations/completions and input/supervised tokens. Returned answer
token counts are per sequence, not another estimate of GPU work. Old adapters
without completed-token observations report null. Exceptions retain incomplete
reservations and close host scopes; no completion is inferred.

Generation and verification deadlines remain absolute cooperative epoch-clock
limits. A reserved model entry may return after its limit. Coarse post-return
observations identify that late host return without preemption or another
forward. A parent task watchdog is a distinct monotonic wall deadline; retired
worker receipts include PID, observed return code and watchdog classification.
A fake-clock test demonstrates admission behavior; the bounded CPU subprocess
test additionally demonstrates actual OS termination. Neither qualifies GPU
timing or unknown official hidden failures.

## Offline checks and deferred output work

`tests/test_nvarc_phase_telemetry.py` tests counts, unchanged votes/ranking/model
calls, nesting, partial verification, deadline admission/overrun, incomplete
forward, multi-test continuation, undispatched denominators, recursive truth
injection, weighted task-cluster resampling and a real finite CPU watchdog.
The public tiny CPU test compares default versus detailed observations of the
same frozen native budget through all 128 steps, the exact ledger, trained fingerprints and restoration;
detail mode adds only measurements. Existing source, schedule, native-export
and submission regressions remain required.
Historical native multitask constructors 001–010 now read their reviewed
producer bytes from immutable `cd3d932` Git objects, so current adapter edits
cannot change the old notebook hash. New inert fixture identities still bind
current producers; this does not authorize staging or saving another real run.

The [E00 controller note](../../research/stage4-e00/CONTROLLER_SCOPE.md) records
the adoption and [E01 gap matrix](../../research/stage4-e00/E01_GAPS.md). E00
only tests the existing single-file checkpoint replacement boundary. It does
not introduce a multi-file exporter transaction, atomic root copy or fallback
policy. Output validity, notebook exit, evidence qualification and promotion
remain distinct. Official submission 56840442 still has an exception, null
scores and an unknown root cause.
