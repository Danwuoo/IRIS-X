# Decision 0012: Close ARC-AGI-2 Trial 001 as inconclusive

Date: 2026-09-22
Status: Accepted

## Context

Trial 001 was intended to measure whether the frozen candidate improves
ARC-AGI-2 public-evaluation pass@2 accuracy over the baseline by at least five
percentage points. That measurement was not completed.

The frozen non-checkpointing `run-001` session ran for approximately twelve
hours without returning a result package or recoverable partial state. The
separately identified checkpointing `run-002` smoke session then exercised two
baseline attempts and two candidate attempts. The owner-provided Kaggle log
reports four terminal invocation records, all with `timeout` status at the
600-second per-invocation limit, and 2,400.337651402 seconds of cumulative
model-invocation wall time. It also reports successful model-weight loading and
checkpoint creation. The checkpoint itself was not imported locally, so this
remains an explicitly owner-reported runtime observation.

Decision 0013 authorized `run-003` to let the same four generations finish
without a runner time limit. Its outbound and preflight were prepared, but no
`run-003/result.zip` was returned to local quarantine and verified. On
2026-09-22 the owner directed the project not to wait for that benchmark and to
close Trial 001 using the evidence already available.

## Decision

Close Trial 001 with disposition `inconclusive-no-promotion`.

- Preserve the `run-002` log observation as an owner-reported runtime and
  failure-mode benchmark, explicitly labeled as four timed-out invocations and
  not as four successful predictions.
- Record `run-003` as ended without locally accepted result evidence. A later
  output from that execution is outside this closed trial unless the owner
  explicitly reopens it under a new decision and evidence review.
- Do not compute accuracy, select the candidate, or construct a Domain Package.
- Do not interpret this disposition as evidence for or against the five-point
  acceptance threshold.
- Freeze the identities and bytes of `run-001`, executed `run-002`, and prepared
  `run-003`; never relabel one run's bytes as another run.
- End all remaining Trial 001 model execution authority, including the unused
  664 invocations and the previously authorized four-invocation benchmark.
- Any later experiment must state a new question and use a new trial and run
  identity.

The machine-readable closure record is
`trials/first-real-domain/closure.json`. It contains no evaluator truth,
prediction, score, or result digest. It binds the retained outbound SHA-256 for
all three run identities without claiming that any returned result was accepted.

## Closure evidence

The terminal conclusion is supported only by these bounded facts:

1. `run-001` returned no result package after the observed long-running attempt;
2. the owner-provided `run-002` log reports four 600-second timeouts and no
   successful prediction;
3. no `run-003/result.zip` was accepted through local quarantine verification
   before the owner ended the wait;
4. no complete baseline/candidate measurement or local accuracy evaluation
   exists; and
5. the owner explicitly selected terminal inconclusive closure rather than
   spending more execution time to manufacture a score.

Missing results are evidence of incompleteness, not evidence of model quality.
Accordingly, `promotion: false` means that promotion is unsupported; it is not
a measured rejection of the candidate.

## Relationship to Decision 0009

Decision 0009 assumed successful result return, import, and evaluation before
layout normalization. This accepted decision narrowly supplies the alternative
terminal gate anticipated for a trial that produced no usable result: an
explicit, machine-readable `inconclusive-no-promotion` closure with no accepted
result digests.

The read-only layout audit may report `normalization_ready: true` when the
Decision-0009 frozen identities remain valid and the closure record exactly
matches this decision. This does not allow unverified execution output to pass
as result evidence. Physical movement remains a separate, byte-preserving
repository operation; this decision does not delete or rewrite retained bytes.

## Consequences

Trial 001 now has a truthful terminal outcome without additional compute. It
provides implementation and runtime lessons but no ARC accuracy comparison,
promotion claim, or Domain Package. Work after this point must begin from a new
authorized product question rather than silently extending Trial 001.
