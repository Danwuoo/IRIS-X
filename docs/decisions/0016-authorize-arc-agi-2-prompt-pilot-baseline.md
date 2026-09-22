# Decision 0016: Authorize the ARC-AGI-2 prompt-pilot baseline launch

Status: Accepted

Date: 2026-09-22

## Context

The owner directed a new development task to implement and start the first
baseline notebook for the DSPy / GEPA prompt pilot, then stop development and
external monitoring as soon as the new run itself proves that four distinct L4
workers loaded the pinned model and entered the scheduler. Trial 002 is closed;
its successful runner and private transport are lineage and reusable bytes, not
an execution identity or authorization token.

The full research route permits at most ten later, dependent GEPA proposal
attempts. This decision covers only the initial B1 baseline and does not authorize Codex reflection,
result retrieval, scoring, a candidate notebook, a
holdout run, or another kernel submission.

## Decision

Create trial `arc-agi-2-prompt-pilot` and authorize exactly one private Kaggle
kernel launch under run `prompt-pilot-baseline-001` with these bindings:

- solver model `Qwen/Qwen3.5-4B` revision
  `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`;
- official source `arcprize/ARC-AGI-2` commit
  `f3283f727488ad98fe575ea6a5ac981e4a188e49` and Kaggle competition
  `arc-prize-2026-arc-agi-2`, challenge digest
  `779eaba89790ebad9af02514a7efc0aefaf2cf8236f046a31bbf8b9ec48f20f5`;
- a deterministic answer-blind split of 256 optimization-train, 128
  selection-dev, and 128 locked-holdout public-training tasks, excluding the
  four Trial 002 smoke tasks and visible-content color-renamed duplicates;
- exactly the 384 train/dev test-index-0 baseline jobs in this kernel, greedy
  single generation, thinking disabled, 512 new-token limit, 300-second job
  deadline, no warm-up generation, retry, TTT, LoRA, or second solver;
- exactly four NVIDIA L4 GPUs with at least 22,000 MiB each. Four persistent
  workers bind physical GPU ranks 0–3, load one model each, first receive one
  job each, then receive jobs dynamically as they become idle;
- the successful private base Dataset
  `danielwuu/irisx-arc-agi-2-trial-002-smoke-001` version 2 supplies the
  already-uploaded model and offline dependencies. A distinct small private
  Dataset supplies only the new identity-bound wheel and outbound package;
- kernel metadata must preserve `NvidiaL4`, private visibility, Internet
  disabled, the official competition source, and both exact private Dataset
  refs. Evaluator truth, scores, feedback, secrets, and competition solutions
  remain local; no competition submission or public publication is allowed;
- external paid cost is USD 0. Existing Kaggle CLI credentials may be used but
  never printed or retained in artifacts; and
- startup confirmation may read server metadata, status, and runtime logs at a
  reasonable interval. Submission acceptance, RUNNING state, model-load-start,
  or memory allocation is insufficient. Success requires four distinct
  `model_ready` events bound to the exact model revision and four GPU UUIDs,
  followed by scheduler dispatch evidence from this run.

Once that success evidence is retained, stop development and all external
monitoring immediately. Leave the notebook running normally; do not cancel it,
wait for 384 jobs, download output, score, reflect, schedule a follow-up, or
submit another kernel. If startup fails, retain the traceback and consumed
identity without automatic resubmission. If live evidence cannot be obtained,
report `model-load-unverified` rather than claiming success.

## Consequences

Trial 001 and Trial 002 bytes, identities, and terminal states remain unchanged.
The new run can reach `startup-verified` in this task, but cannot reach
`baseline-measured` because result retrieval and local scoring are outside this
authorization. Any continuation requires a later explicit owner instruction
and must resume from the retained identity and checkpoint evidence rather than
silently repeating consumed generations.
