# Local capacity-initialization controls

This independent CPU-only prototype does not modify the running dual-model
notebook or its frozen source. It adds untrained capacity, not knowledge.
There is no new benchmark result, GPU experiment or expanded-weight release.

## What is implemented

`tools/nvarc_capacity_20261017/prototype.py` contains three distinct controls:

1. **Depth:** copy selected full decoder blocks and zero only the new attention
   output and FFN down projections. Update every attention cache index, common
   configuration and layer type. Old model tensors remain intact.
2. **FFN width:** append independent SwiGLU units with nonzero gate/up matrices
   and zero output columns. Keeping the new tensors separate permits real
   freezing of old units even under AdamW weight decay. A separate export
   transform folds the two FFNs into native Qwen3 matrices; numerical parity
   must be checked before saving and the training scope reconfigured afterward.
   This does not widen attention or hidden states.
3. **MoE mechanism:** two tiny identical experts, explicit normalized top-1,
   unnormalized top-1 or soft top-2 routing. This is a bounded CPU diagnostic,
   not an efficient GPU dispatcher, production MoE or extra training arm.

All old optimizers and KV caches must be discarded after a transform. The
current helpers accept only a fresh finite CPU compact Qwen3 in evaluation
mode, at most one transform per live model, and no more than 512 million added
parameters or the original parameter count, whichever is smaller. Training
scope selection is bound to the exact live model/receipt and rejects pending
gradients before changing flags. They are not resume converters or adapters
for arbitrary architectures.

## Synthetic evidence

The tiny double-precision Qwen3 tests demonstrate initial depth and width
output parity, cache-index correctness, native checkpoint reload, preserved
original tensors, useful gradients in zero-output projections, and subsequent
gradient flow into the newly added internal features after an optimizer step.
Frozen inherited weights remain unchanged with AdamW weight decay enabled.

The MoE controls distinguish three effects:

- Normalized hard top-1 preserves the inherited FFN output but gives its router
  zero task-loss gradient through the normalized selected probability. Only
  the selected expert receives that example's task gradient.
- Unnormalized top-1 at a uniform two-expert router halves the inherited FFN
  output. It has a router task gradient, but is not function preserving.
- Identical soft top-2 experts preserve output yet initially have zero router
  task gradient and identical expert gradients. Explicitly making the experts
  distinct unlocks the router signal, while evaluating both loses top-1's
  sparse-compute advantage.

These tests do not establish task learning, routing quality or hardware speed.

## Official 2B admission performed locally

`admit_depth.py` verifies the existing official SFT141 file hashes, full compact
tokenizer roundtrip and original configuration, then inserts four copied
identity blocks after original zero-indexed layers 6, 13, 20 and 27. It reads
only that already-downloaded model and a tiny self-contained synthetic prompt.

On the measured CPU with BF16 weights and SDPA:

- Original parameters: 1,409,475,584; expanded: 1,610,819,584.
- Full short-prompt logits and six fresh-cache decoding steps were bit-identical
  before and after insertion; maximum absolute difference was zero.
- Cache layers changed from 28 to 32 and greedy token sequences matched.
- Four new blocks plus compact embedding/head give 201,409,536 planned
  trainables. Their dtype was not promoted and no optimizer was allocated.
- The complete verification and short admission took 13.27 seconds with a
  measured peak process RSS of 3.35 GiB in this CPU environment.

No official-model update, 8k-context measurement, GPU admission, throughput
comparison, task evaluation or expanded checkpoint export occurred. The time
and RSS above cannot be used as GPU training estimates. Inherited benchmark
exposure of the official checkpoint is unchanged by expansion.

## Next decision-bearing experiment, not launched

Keep the ordinary official 2B/4B continuation first. If its train-derived
results justify an architecture comparison, screen one 2B depth arm against
the unchanged model with the same parent split, data order, reward, decoding
and exclusive measured hardware time. Count new-block full training and LoRA
training as different recipes, not an architecture-only causal contrast.

Require useful finite updates, exact pre-public selection, native checkpoint
roundtrip and complete dev evaluation before any public inference. A small
directional dev gain needs a larger frozen panel and a second paired seed.
Do not promote expansion if its advantage disappears under equal time.
The width and limited-MoE alternatives remain later candidates, not an
unbounded additional experiment grid. See `CAPACITY-COMPARISON.md` for primary
method sources, full parameter accounting and memory caveats.
