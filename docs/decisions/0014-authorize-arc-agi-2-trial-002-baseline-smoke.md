# Decision 0014: Authorize the ARC-AGI-2 Trial 002 completable baseline smoke

Date: 2026-09-22
Status: Accepted

## Context

Trial 001 is closed as `inconclusive-no-promotion`. Its Qwen3.8-27B runs,
packages, and evidence remain frozen. The owner has opened a new question:
whether a small, NVARC-derived ARC solver can finish a bounded four-task run,
return valid predictions, and expose enough cost and failure evidence to guide
the next experiment. Public-evaluation accuracy of at least 85% is a long-term
milestone and private-test accuracy of at least 85% is the final target; this
smoke does not claim either result.

The selected model is the official post-trained
`Qwen/Qwen3.5-4B@851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`. Official
model-card results support prioritizing it over the older same-size Qwen3
reference on several general reasoning and instruction benchmarks, but do not
prove an ARC improvement. NVARC's published ARChitects path uses Qwen3-specific
16-token embeddings and a large SFT recipe whose listed material includes
`arc2_evaluation6`. Those adapter bytes are not architecture-compatible with
Qwen3.5 and are not reused.

## Decision

Create logical trial `arc-agi-2-trial-002` and one smoke run
`trial-002-smoke-001` with these boundaries:

- use official ARC-AGI-2 bytes at
  `f3283f727488ad98fe575ea6a5ac981e4a188e49`;
- select exactly four public-training tasks before solving, using only task ID
  and input shapes under the fixed seed recorded in the run binding;
- use all selected test inputs, with local test-output exact-match pass@2 as
  the primary score denominator;
- keep evaluator truth, answer-derived metadata, scores, and feedback out of
  the notebook input, checkpoint, and returned result;
- integrate the NVARC ARChitects mechanism through compact grid formatting,
  spatial and color augmentation, per-task LoRA adaptation from demonstrations,
  transformed candidate generation, inversion, and frequency/score ranking;
- retain the Qwen3.5 native tokenizer and vocabulary, use no old Qwen3 adapter,
  and make no claim that the unperformed NVARC large-scale SFT was reproduced;
- use four persistent workers, one per verified L4 GPU, with model loading once
  per worker, a 300-second adaptation-plus-inference deadline per task, and a
  3,600-second whole-session limit including load and finalization;
- stop model work at least 180 seconds before the session limit, preserve
  truth-free atomic checkpoints, and distinguish valid grids, malformed output,
  timeout, OOM, crash, and unexecuted jobs;
- never count a fallback grid as a valid model output;
- use private Kaggle Dataset and kernel transport through the installed CLI,
  with notebook Internet disabled, existing CLI authentication, no credential
  capture or logging, and external paid cost capped at USD 0; and
- do not call an external model API, publish an artifact, submit to the
  competition, run a second comparison job, start large-scale SFT, perform RL
  or prompt optimization, or execute a public-evaluation sweep.

The owner authorizes one final, preflight-passing Kaggle L4 x4 smoke. A failed
or queued job still consumes that one-run authorization. The job is not polled
or live-streamed. After submission, retrieval occurs once after the execution
budget plus finalization allowance, or through one bounded app-native wake-up.

Open-source programs, checkpoints, and traceable third-party or synthetic ARC
data may be researched. Any checkpoint exposed to public-evaluation answers
must label public results contaminated and retain a clean original-weight
control. This smoke uses the official Qwen3.5 weights without project ARC
answer adaptation before per-task training demonstrations; unknown general
pretraining exposure remains `unknown`, not `clean`.

## Evidence and completion states

Implementation readiness, package readiness, runtime verification, and a
measured baseline are distinct. This smoke is runtime-verified only if the
downloaded result passes local quarantine, covers every fixed job with a
terminal record, and contains at least one valid non-fallback model grid.
Training-split accuracy cannot estimate public-evaluation or private-test
generalization and cannot trigger promotion or a Domain Package.

## Preserved boundaries

This decision does not reopen Trial 001. Do not reopen Trial 001, change any
Trial 001 identity, rewrite
the P1 public contracts, authorize paid compute, or authorize a competition
submission. A later run requires a new identity and owner scope.


