# Preserve completed demonstration-only adaptation

This successor changes only PUBLIC task-local TTT transaction handling. It does
not change a previously submitted run or a frozen source capsule. It has no
measured effect on ARC accuracy or full-model CUDA performance yet.

## Why change the transaction boundary?

Previously, a recoverable error in any TTT step restored the task's original
selected checkpoint and reported zero retained TTT steps. A deadline, OOM, or
nonfinite update late in a multi-step adaptation could therefore discard all
earlier completed work. This is a finding from the implementation, not a claim
that a particular running experiment has encountered that path.

The new boundary is one optimizer step. Each task still starts from the exact
selected checkpoint and trains exclusively on its demonstration-derived
leave-one-out examples. A successful step becomes the starting point of the
next transaction. An aborted transaction restores only its own pre-step adapter,
verifies the exact restored digest, and ends adaptation without retrying.
Inference can then use earlier accepted adaptation instead of losing it.

## Deadline, failure and ownership contract

- The same per-task share and one-third TTT allocation remain. No deadline is
  extended and no extra training attempt is introduced after an abort.
- The existing pre-commit checks remain. A further check immediately after the
  step rejects an update whose optimizer execution crossed the deadline. Its
  parameter change is restored, but its physical work remains charged.
- Recoverable aborts are the existing deadline, CUDA OOM, nonfinite-value and
  invalid-example failures. Unknown runtime errors, failed restoration,
  mismatched restoration digests and cleanup errors remain fatal.
- A failure while encoding an example before any snapshot leaves the already
  committed adapter unchanged. A later failure restores that step's CPU copy.
- The failed exception scope is exited before restoration and cache cleanup.
  Gradient buffers are cleared and the optimizer and snapshot are discarded
  before inference. The failed optimizer is never reused.
- The next task again restores the exact selected checkpoint. No task-local
  adapter is exported for later tasks or checkpoint selection. Evaluator answers
  remain unavailable to adaptation, inference and candidate ranking.

## Retained state is not physical work

`ttt_phase_complete` records accepted steps, attempted examples, stop reason,
retained adapter digest, elapsed wall time, and the actual engine counter deltas
for optimizer attempts and completed finite steps. Rollback never decrements
those counters. For example, if a second finite optimizer step finishes late,
the receipt reports two physical completed steps but only one retained step.
If a partially mutating optimizer throws, its attempted update is still charged
even though it does not increment the completed-finite-step counter.

Task completion repeats the retained state and physical TTT counts. Existing
prediction schemas, fixed view ordering, batching, candidate selection, full
120-task/167-query denominator, prediction seals and scorer are unchanged.
SFT/control and AF3 optimizer semantics are not altered by this task-local fix.

## Verification scope

CPU fault-injection tests use an actual tiny Qwen model, real LoRA parameters,
autograd and AdamW. They cover partial optimizer OOM/nonfinite/invalid-value
failure, a pre-commit deadline, an exactly late completed commit, encoding
failure before a snapshot, traceback-owned tensor release, fatal failed or
incorrect restoration, fatal unknown errors, zero signal, and expired tasks.
A two-task integration exercises retained adapters with real batched transformed
views and checks the next task's reset and complete candidate-audit coverage.
These tests establish transaction behavior, not model effectiveness. The source
must have a new identity before any deployment, and GPU cost and valid ARC
scores must be reported separately.
