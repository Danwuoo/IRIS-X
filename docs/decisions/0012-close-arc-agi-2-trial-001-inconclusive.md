# Decision 0012: Close ARC-AGI-2 Trial 001 as inconclusive

Date: 2026-09-21
Status: Proposed

## Context

Trial 001 was intended to measure whether the frozen candidate improves
ARC-AGI-2 public-evaluation pass@2 accuracy over the baseline by at least five
percentage points. That measurement was not completed.

The frozen non-checkpointing `run-001` session ran for approximately twelve
hours without returning a result package or recoverable partial state. The
separately identified checkpointing `run-002` smoke session then exercised the
first two baseline attempts and first two candidate attempts. The owner-provided
Kaggle log reports four terminal invocation records, all with `timeout` status
at the 600-second per-invocation limit, and 2,400.337651402 seconds of cumulative
model-invocation wall time. It also reports successful model-weight loading and
checkpoint creation.

Those observations are useful as a runtime and failure-mode benchmark. They do
not contain a valid prediction, accuracy result, baseline/candidate comparison,
or evidence that can support promotion.

The owner initially directed that the four-invocation observation be retained
as a reference benchmark and that Trial 001 closure be prepared. The owner then
clarified that the desired benchmark must contain four naturally completed
generations without the runner's 600-second limit. Decision 0013 therefore
creates the separate `run-003` completion benchmark. This closure decision
remains proposed until the returned `run-003/result.zip` is imported and
verified locally.

## Proposed decision

After the closure evidence gate below passes, close Trial 001 with disposition
`inconclusive-no-promotion`.

- Preserve the four `run-002` records as a runtime and failure-mode benchmark,
  explicitly labeled as four timed-out invocations rather than four successful
  predictions.
- Do not compute accuracy, select the candidate, or construct a Domain Package
  from this benchmark.
- Do not interpret the outcome as evidence for or against the trial's five
  percentage-point acceptance threshold.
- Freeze the executed `run-002` outbound package, notebook, runner, runner core,
  run binding, checkpoint policy, and their recorded identities.
- Retain the frozen `run-001` identities and record that no result package was
  returned from that attempt.
- End further Trial 001 model execution. Any later experiment must state a new
  question and use a new trial and run identity.

## Closure evidence gate

This proposal may become accepted only after all of the following are true:

1. the returned `run-003/result.zip` is downloaded unchanged into local
   quarantine and its container SHA-256 is recorded;
2. offline verification binds the result to the exact verified `run-003`
   outbound package and confirms four contiguous invocation records;
3. local inspection records whether each invocation produced a valid grid,
   malformed generation, or runtime error, without using evaluator truth;
4. the `run-002` timeout observation and the verified `run-003` completion
   benchmark are summarized without being treated as accuracy evidence; and
5. this record is updated with the `run-003` result digest and changed to
   `Status: Accepted`.

Until then, Trial 001 is `closure-prepared-awaiting-checkpoint`, not closed.

## Relationship to Decision 0009

Decision 0009 assumed successful result return, import, and evaluation before
layout normalization. An accepted version of this decision will narrowly add
an alternative terminal closure for a trial that produced no usable result:
verified benchmark-result import plus an explicit `inconclusive-no-promotion`
closure. It will not weaken the frozen `run-001` identity checks or allow
unverified evidence to pass the existing result closure gate.

Physical layout normalization remains blocked while this decision is proposed.
After acceptance, the layout audit must be updated to recognize the explicit
inconclusive closure before any retained bytes move.

## Consequences

Trial 001 will have a truthful terminal outcome without spending more compute
to manufacture a score. The benchmark will preserve the observed 600-second
timeout behavior for later design work, while product promotion, candidate
selection, and Domain Package creation remain unsupported.
