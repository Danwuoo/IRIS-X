# Decision 0018: Authorize prompt-pilot result recovery

Status: Accepted

Date: 2026-09-22

## Context

`prompt-pilot-baseline-002` completed all 384 authorized generations (380
parser-valid grids and 4 parser-invalid outputs) but failed before producing
`result.zip`. The retained traceback proves a finalization-only defect: the
runner passed integer worker-rank keys into canonical JSON. The local fix now
converts those keys to strings and passes a result-ZIP regression test.

The owner explicitly confirmed authorization to retrieve the failed kernel's
retained output and package the completed checkpoint locally. Repeating the 384
generations would add no information and is not authorized.

## Decision

Authorize exactly one output retrieval from private Kaggle kernel
`danielwuu/iris-x-arc-agi-2-prompt-pilot-baseline-002`, version 1, into local
quarantine. Then:

- accept only identity-bound, truth-free artifacts retained by that failed
  kernel, including `checkpoint.json`, `progress.jsonl`, runtime failure and
  notebook preflight evidence;
- require the checkpoint to bind the exact baseline-002 run identity, contain
  the complete 384-job denominator, record exactly 384 generation invocations,
  and contain exactly 384 terminal records;
- reconstruct execution observations deterministically from the verified
  checkpoint and progress evidence, applying only the string-key serialization
  fix already covered by local tests;
- build and verify one local `result.zip` under the unchanged
  `prompt-pilot-baseline-002` package identity; and
- stop after retaining verification evidence. Do not score, reflect, publish,
  submit to the competition, upload another Dataset, update or launch a kernel,
  call an external model, or perform another output retrieval.

If Kaggle did not retain a complete checkpoint or any binding or count differs,
stop without fabricating missing evidence and without rerunning generations.

## Consequences

Successful recovery can change the trial state from
`compute-complete-result-packaging-failed` to `result-recovered-unscored`. It
cannot create a baseline measurement or authorize a GEPA proposal because local
scoring remains outside this decision.
