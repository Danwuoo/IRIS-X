# Overnight source integration

Authority is [Decision 0053](../../docs/decisions/0053-nvarc-overnight-development-goal.md).
The development Goal ends on substantial completion or the one-shot 07:00
Taipei timer on 2026-10-02. Previous run identities and results remain frozen.

## Packing and accumulation evidence

`arc_nvarc_packing` adapts NeMo-RL v0.3.0's MFFD placement under its retained
Apache-2.0 license. The exact primary reference is commit
`b1c86a816c5e2b4ca41ece193624a38dc62e6fdf`,
[algorithms.py](https://github.com/NVIDIA/NeMo-RL/blob/b1c86a816c5e2b4ca41ece193624a38dc62e6fdf/nemo_rl/data/packing/algorithms.py).
Its SHA-256 is `4b946e5913b50ae96891138b508352a1ce75a4e1bfe14aea14a31179ced64011`.
The original NVARC run's precise NeMo version remains unknown.

Logical packs round whole sequences to 64, cap each bin at 256,000 tokens,
retain dual-parent/exposure lineage, reset positions, and mask padding. Execution
uses a fresh hybrid attention/DeltaNet state for every segment. It establishes
isolation and loss semantics, not fused FlashAttention/NeMo throughput parity.
503 input sets match the separately loaded pinned placement implementation.
Real tiny Qwen3.5 independent-sequence logits, token-mean loss and all gradients
match; altering a prior sample cannot affect a later one. An unsafe flat
concatenation differs, so this check exercises the recurrent boundary.

FSDP CPU offload replaces reduced gradients; ordinary backward accumulation
does not suffice. This implementation adds reduced FP32 CPU shards and copies
the result into the last FSDP gradient views, with a globally supervised-token
mean. Each rank performs an equal number of collectives; zero-loss dummy slots
on shorter ranks do not count as training tokens. It does not retain full GPU
gradients with `no_sync`. The constraint is documented in the primary
[PyTorch FSDP reference](https://docs.pytorch.org/docs/2.10/fsdp.html).

Two real CPU FSDP workers, unequal rank sample counts and two optimizer steps
match an independent all-sample oracle, including AdamW moments. The reusable
SFT path also verifies uninterrupted versus process-restarted execution with
bitwise-equal model/optimizer tensors, scheduler, RNG and source cursor. Its
checkpoint consolidation and export/reload verify every tensor's exact bytes.
An initial Windows full-state CPU-offload gather crashed natively; the proof
uses the same sharded DCP path as the runtime, followed by independent local
consolidation. Failed diagnostics remain retained, and are not counted as passes.

The lazy original-corpus stream follows the complete source concatenation and
seed-24 shuffle, memory maps Arrow lineage, preserves whole long sequences and
keeps validation separate. The fixture retains a 17,000-token sample and both
exposed parents without filtering or truncation.

| Check | Outcome | Local log SHA-256 |
|---|---|---|
| Stream, packing, differential isolation | 6 passed / 11.757 s | `63aac0a0851aefad7cd8c6f1081c17735229edcc2c71c469126902c0edbbd045` |
| Independent distributed accumulation | 1 passed / 38.344 s | `113ab2ec960ac652d589aa3611f6795f9350f8e151026ec57275f65fb8eee65d` |
| Resume, cursor, RNG, exact export | 1 passed / 101.087 s | `c5f56c448aa6cfb573e87918705e1222dd07deb35aedbbdab6402399ac3dd4d8` |
| Required repository validation | 314 passed / 317.310 s | `72b482e2899d3a67732f2dd2e2ae3ff3c7443dcf0c60840eb41ab7ec480b8c41` |

Logs and the exact reference live under the isolated local
`.irisx/nvarc-original/materials/nemo-packing-reference-20261002/` namespace.

## Four-L4 runtime

The distinct `nvarc-overnight-sft-001` package is being prepared. It repeats
eight frozen whole published records for two accumulated steps: all six source
families and the 11,196-token maximum are represented. Global batch is eight
for this integration probe. It is not the source global-256 epoch, 12,716-step
training, original Qwen3 checkpoint, or an ARC quality evaluation.

No new runtime outcome is asserted before an exact submission receipt and
digest-bound terminal result. The next runtime must also retain its HF export;
optimizer checkpoints remain explicitly ephemeral Kaggle scratch.
