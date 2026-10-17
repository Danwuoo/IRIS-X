# Capacity expansion: bounded comparison proposal

This is a proposal, not a changed model or launched experiment. The original
official 2B/4B pipeline remains first. Parameter expansion adds capacity, not
learned knowledge at initialization; additional data/optimization must make that
capacity useful within the same compute budget.

## Actual architecture counts

Counts exclude unmerged training adapters. Active parameters use conventional
per-token architecture accounting, not measured FLOPs or wall time.

| Design | Compact 2B total / active | Compact 4B total / active |
|---|---:|---:|
| Original | 1,409,475,584 / same | 3,633,593,856 / same |
| Four additional decoder blocks | 1,610,819,584 / same | 4,037,317,120 / same |
| Modest FFN-only widening | 1,585,636,352 / same | 4,058,267,136 / same |
| Two experts in every FFN, top-1 | 2,466,554,880 / 1,409,590,272 | 6,323,375,616 / 3,633,778,176 |
| Two experts in every FFN, top-2 | 2,466,554,880 / same | 6,323,375,616 / same |

Depth is 28→32 or 36→40. FFN intermediate widths are 6,144→7,168 and
9,728→11,264, with hidden/attention/KV geometry unchanged. MoE duplicates each
SwiGLU FFN and adds a bias-free H→2 router per replaced layer. One original FFN
contains 37,748,736 / 74,711,040 parameters respectively.

## First candidate: 2B identity depth expansion

Insert a copied block after original blocks 7, 14, 21 and 28. Zero only each
new attention output projection and MLP down projection, so the residual block
is mathematically identity. Preserve nonzero internal features and RMSNorm
scales. Initially some upstream gradients are zero until the output projection
moves; tests must show usable learning after that point.

[LLaMA-Pro's official converter](https://github.com/TencentARC/LLaMA-Pro/blob/main/scripts/block_expansion.py)
implements this pattern. Its [paper](https://aclanthology.org/2024.acl-long.352.pdf)
used substantial continued pretraining, including 80B tokens, not a short ARC
adaptation. Porting must preserve BF16 rather than blindly copying the script's
FP16 loader, update every layer/cache index and layer type, and preserve Qwen's
explicit head dimensions and rotary metadata. Initial logit/generation parity
requires actual dtype/backend tests, not only algebra.

Training four new 2B blocks fully while freezing old blocks plus the tiny full
embedding/head gives 201,409,536 trainables. Retaining the baseline rank-64
adaptation as well gives 271,139,840. These are different recipes and must be
identified; neither is an architecture-only causal experiment.

## Width and MoE tradeoffs

FFN-only widening is lower risk than full hidden-width growth: keep old weights,
add nonzero gate/up rows and zero corresponding down columns, then train those
new slices. This is an analytical SwiGLU adaptation, not an official NVARC
recipe. Replication-based [Net2Net](https://arxiv.org/abs/1511.05641) requires
consistent gate/up replication and down-column rescaling; symmetric clones may
remain redundant. Full hidden padding changes RMSNorm's denominator and can
disturb embedding/head, GQA and RoPE behavior. The
[official Qwen3 implementation](https://github.com/huggingface/transformers/blob/main/src/transformers/models/qwen3/modeling_qwen3.py)
also allows query projection width to differ from hidden width, as in this 4B.

MoE adds stored experts while conditionally activating a subset. It is not a
free dense-equivalent transformation:

- Normalized hard top-1 over one selected expert has weight exactly one, giving
  the router no task-loss gradient through that weight. Auxiliary balancing is
  not itself reward-directed routing.
- Unnormalized top-1 can train that probability, but scales the inherited FFN
  and does not initially preserve its function.
- Two-expert top-2 executes both experts, losing sparse-compute savings.
  Identical experts also initially provide no useful router task-gradient;
  exact symmetry can keep experts redundant.
- Token dropping, capacities, dispatch buffers and small per-expert batches
  matter. Active-parameter counts do not establish GPU throughput.

[Sparse Upcycling](https://arxiv.org/abs/2212.05055) reports meaningful gains
after additional T5/ViT training, with routing-dependent initial degradation.
Its [T5X code](https://github.com/google-research/t5x/tree/main/t5x/contrib/moe)
and [Flaxformer router](https://github.com/google/flaxformer/blob/main/flaxformer/architectures/moe/routing.py)
are runnable code, but not drop-in PyTorch compact-Qwen modules. A later
[matched-compute study](https://proceedings.mlr.press/v262/doubov24a.html)
reports benefits and inference overhead; its eight-expert/top-2 training does
not validate a two-expert/top-1 short ARC recipe.

If later justified, replacing only four FFNs limits the first MoE prototype:
2B total 1,560,486,912, top-1 active 1,409,491,968; 4B total 3,932,458,496,
top-1 active 3,633,614,336. This is a follow-up candidate, not an initial arm.

## Memory and decision protocol

Approximate static GiB with BF16 frozen weights and FP32 trainables/gradients/
Adam moments, before activations, KV, scratch and allocator overhead:

| Recipe | 2B | 4B |
|---|---:|---:|
| Existing rank-64 baseline | 3.67 | 8.74 |
| Baseline plus four fully trained blocks | 6.67 | 14.75 |
| Baseline plus appended FFN units | 6.29 | 15.07 |
| All-layer two-expert MoE with independent expert adapters | 6.29 | 15.02 |

The implementation's rollback snapshot adds four bytes per trainable parameter.
Full FP32 Adam training of the 4B all-layer MoE would consume about 94.23 GiB
for parameter states alone, so it is not viable on the observed 94.97 GiB GPU.
Depth grows KV cache; FFN-only width does not. All feasibility decisions require
actual 8k training/rollout measurements, not these static estimates.

Initial comparison: unchanged 2B, unchanged 4B and one 2B depth arm only.
Freeze the same training recipe, parent split, data order, verifier/reward,
generated-dev selection and decoding workload. Match exclusive measured GPU
hardware-seconds including load, dev and closure; report training-only seconds,
tokens, updates and memory separately. Do not compare only equal step counts.
Keep TTT off for this architecture screen. The ordinary four-arm continuation
and this future architecture screen are distinct experiments.

Admission requires starting-function parity, exact inherited/new tensor
inventory, finite useful updates, complete dev evaluation and checkpoint
roundtrip. A directional signal of two net extra solved dev parents is not
enough for a capability claim: confirm the leading expansion against its parent
with a second paired seed and a larger frozen panel, reporting parent-cluster
uncertainty and equal-time costs. If the gain disappears under equal time, do
not promote. Only then consider one FFN-width or limited-MoE follow-up. PUBLIC
answers remain evaluator-only and inherited-exposure qualifications remain.
