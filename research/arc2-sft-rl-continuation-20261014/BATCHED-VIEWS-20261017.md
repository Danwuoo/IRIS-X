# Bounded batched transformed-view inference

This is an opt-in successor protocol, not a change to the running v50 source.
It targets the serial forward-call cost of 8/16-view inference while preserving
complete PUBLIC120 coverage and selecting only two final grids per query.
No CUDA throughput improvement or score improvement has yet been established.

## Execution contract

- `candidate_batch_size` accepts only the integers 1, 2, 4, or 8. Its default is
  1, which preserves the existing serial path. Sampling and AF3 replay are not
  batched by this option and their original implementations remain unchanged.
- A batch contains fixed transformed views of one query under the same
  task-specific adapter. Variable-length prompts are left-padded with explicit
  attention masks and per-row position IDs; there is no cross-example packing.
- Generation is full-vocabulary greedy decoding. Each row has its own EOS and
  completed-grid stop condition. Padding and finished-row filler are excluded
  from returned trajectories, log probabilities, and candidate votes.
- The fixed query deadline and, where enabled, likelihood-reranking reserve
  remain in force. Each group receives a proportional share of the remaining
  generation interval. Checks before a forward, after synchronization, and after
  decoding reject late results while still charging executed token work.
- An OOM permits at most one singleton attempt for each member, inside the same
  original group deadline, and demotes remaining groups in that query to
  singletons. The failed graph/cache references are released before retry.
  Other failures do not trigger retries; malformed batches cannot contribute
  partial votes.
- Successful results are committed in the original fixed view order, then
  inverse-transformed, deduplicated, and ranked. Every planned view retains its
  receipt, including first failures and fallback attempts. Attempt records
  distinguish actual invocation from an expired attempt that did no work and
  include token work, forward calls, padded prompt cost, and wall time.
- Batched two-view inference also requires the full private candidate audit at
  prediction sealing. Missing predictions remain in the full 120-task,
  167-query denominator. No evaluator answer is used for candidate selection.

## Numerical distinction from serial inference

Batching is not asserted to be bitwise equivalent to singleton decoding. An
independent tiny-Qwen probe used five seeds, eight unequal prompt lengths, and
twelve generated tokens. FP32 matched singleton greedy tokens in all 40 rows,
with maximum sampled-token log-probability difference about 4.77e-7. With a
BF16 base and FP32 LoRA, 2 of 40 rows diverged in their greedy tokens; among
matching rows the maximum log-probability difference was about 0.0020013.
Reversing batch row order preserved tokens in both tested dtypes. Inputs,
adapter bytes, and RNG state remained unchanged.

These small CPU observations do not establish 14B CUDA equivalence. BF16
rounding can alter a near-tied argmax, so a future batched run needs its own
source/protocol identity and cannot be described as an identical faster replay
of a serial run. The BF16 regression instead checks replay of each batch's own
tokens, finite values, and bounded numerical differences.

## Verification scope

Focused tests exercise real tiny-Qwen cached decoding, unequal lengths,
explicit masks/positions, staggered stops, replay, immutable adapter/input/RNG
state, finite-value rejection, and charging of late work. Integration tests
cover 2/8/16 views, OOM demotion, malformed output, deadline and rerank reserves,
fixed candidate ordering, full-denominator receipts, and sealing requirements.
CPU tests and fewer forward calls are not GPU throughput or ARC score evidence.
The first deployment must report actual hardware, batch/OOM costs, selected
top-two predictions, and a valid unchanged-scorer result separately.

The focused goal suite passed 190 tests in both normal and optimized Python:
188 passed and 2 skipped for unavailable CUDA and Landlock. The actual pinned
Qwen tokenizer, RE-ARC source, and dependency wheels were present. Independent
review passed 114 of 115 subset tests with one optional tokenizer skip and an
additional multi-task/multi-query scorer-interface probe. These results do not
replace platform CI or strict historical retained-evidence acceptance.
