# Decision 0013: Create unbounded-time four-invocation run-003

Date: 2026-09-22
Status: Accepted

## Context

The `run-002` smoke adapter applied the Trial 001 execution envelope's
600-second per-invocation limit. All four smoke invocations reached that limit,
so the session proved the transport, model-load, GPU, progress, and checkpoint
path but did not observe a naturally completed generation.

The owner clarified that the desired reference benchmark is four model
invocations allowed to finish without a runner-enforced time limit, with the
complete execution record returned in `result.zip`. Changing the executed
adapter or policy under `run-002` would invalidate its existing identity and
evidence, so the new bytes require a new run ID.

## Decision

Create `run-003` with `kaggle-notebook-v5.ipynb` and the v5 benchmark runner.
Preserve every `run-001` and `run-002` byte and identity unchanged.

The `run-003` benchmark policy is:

- execute exactly the first four frozen invocation keys in this order:
  baseline attempt 0, baseline attempt 1, candidate attempt 0, and candidate
  attempt 1 for the first evaluation test input;
- do not pass `max_time` to `model.generate` and do not enforce a cumulative
  runner wall-clock limit;
- retain the frozen 32,768 `max_new_tokens` bound, decoding parameters, seeds,
  model, prompts, and maximum recorded response bytes;
- acknowledge that Kaggle's provider-controlled session lifetime still exists
  and cannot be disabled by notebook code;
- atomically checkpoint before and after every invocation;
- if the provider interrupts a pending invocation, record the interruption and
  retry the same unfinished invocation on resume rather than counting it as a
  completed timeout; and
- after four terminal invocation records, atomically write
  `/kaggle/working/result.zip`.

`result.zip` is a closed-world, identity-bound benchmark package containing:

- one summary record for each invocation;
- each raw UTF-8 generation in a separate file;
- parsed grid or malformed/error status;
- raw-output digest, seed, input and generated token counts, EOS observation,
  truncation flag, error details, UTC start/end times, and elapsed time;
- GPU, CUDA, cuDNN, Python, Torch, Transformers, model class, dtype, parameter
  count, model-load timing, session/resume/interruption counts, and recorded
  wall time;
- canonical `progress.jsonl`, the final checkpoint state, and the exact run
  binding; and
- no evaluator truth, score, feedback, selection evidence, or Domain Package.

## Scope and authorization

The owner's 2026-09-22 instruction authorizes construction, packaging,
preflight, and execution of this exact four-invocation `run-003` completion
benchmark. It does not authorize the remaining 664 invocations, local scoring,
candidate promotion, a Domain Package, paid execution, network access,
credentials in the notebook, third-party ARC data, or a different accelerator
entitlement path.

The benchmark is reference evidence only. Even four valid grids cover one test
input and cannot satisfy Trial 001's accuracy measurement or five
percentage-point acceptance threshold.

## Consequences

The v5 result can distinguish slow-but-completing generation from the v4
600-second timeout failure mode and preserve enough raw evidence for later
runtime design. A platform interruption may require a resumed Kaggle session,
but completed invocations are not repeated and an unfinished invocation is not
misrepresented as complete.
