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

The distinct integration packages repeat
eight frozen whole published records for two accumulated steps: all six source
families and the 11,196-token maximum are represented. Global batch is eight
for this integration probe. It is not the source global-256 epoch, 12,716-step
training, original Qwen3 checkpoint, or an ARC quality evaluation.

No new runtime outcome is asserted before an exact submission receipt and
digest-bound terminal result. The next runtime must also retain its HF export;
optimizer checkpoints remain explicitly ephemeral Kaggle scratch.

`nvarc-overnight-sft-001`'s one SaveKernel received HTTP 400 without a version
receipt. A single recent-own-kernel listing found 57 kernels and no matching
001 entry. Its failed push, exact request and package are retained; no runtime
work or provider error cause is inferred. The original uncompressed notebook
was 1,346,529 bytes, compared with 972,714 bytes for the previous accepted
preflight. The replacement compresses and bounds payload expansion while
retaining the same exact raw data and model workload.

`nvarc-overnight-sft-002`'s compressed 642,849-byte notebook passed offline
verification and its single private SAVE_AND_RUN_ALL was accepted as version 1,
kernel ID `136684509`, at `2026-10-01T17:02:28.456561` UTC.
[Kaggle notebook](https://www.kaggle.com/code/danielwuu/nvarc-overnight-sft-002).
Compression acceptance does not prove the earlier provider error's cause.
Plan digest is `sha256:96ac918d32ce722959f13b4ca2330dd85fed06596ca9c8760d604749df8afd26`;
runtime identity is `sha256:eb7abf3529a8888e831bd6b0f0f943c3427dc202f8584944ab4613c38bef99d3`.
The ledger and exact package live under
`.irisx/nvarc-original/runs/nvarc-overnight-sft-002/`.
The terminal provider status is COMPLETE. Its sole terminal retrieval retained
the exact closed diagnostic archive and is transferring the four HF shards.
The runtime completed two global-batch-eight accumulated steps, 94,156 input
and 48,670 supervised tokens, sixteen whole forwards and an exact process
restart at step one. Its FP32 saved/consolidated fingerprints agree within the
bound tolerance, and all 724 exported tensors reloaded identically onsite.
Material digest is `sha256:2f367df415813dbb82b96192750f334f2a91e84c9d6812daa92e7a2a5bd04ca7`.
The complete notebook took 2,454.945 seconds; actual rank optimizer steps took
128.101–140.096 seconds. An independent local tensor reader will verify the
transferred files before claiming the local weight recovery complete.

The distinct `nvarc-overnight-sft-003` is accepted as private version 1,
kernel ID `136689146`, with a 10,800-second finite limit. It freezes the actual
first 512 seed-24 shuffle records: all six sources, dual-parent exposure retained,
zero filtered/truncated records, 1,770,662 input and 764,883 supervised tokens.
The two global-batch-256 steps use 64 reduced CPU-shard microsteps per rank.
Plan digest is `sha256:c5196971143abe73774581b17e5f7ac11b239d686520cf32e4a7f5d3bdb35dbb`;
identity is `sha256:95bb2b4ddf8151cf4cb7005276c4872b25e650596eda4df72986cb44f9773884`.
[Kaggle notebook](https://www.kaggle.com/code/danielwuu/nvarc-overnight-sft-003).
This is the source epoch's exact prefix, not a completed original-scale epoch.
Its runtime outcome is pending.

## Complete TTT memory path

An opt-in nonreentrant activation-checkpoint setting now covers the full
source 128-view rank-256 epoch. A real hybrid tiny model returns bitwise-equal
losses, adapter weights and learning-rate schedules with/without checkpointing;
both reset to the exact initial adapter. The one differential test passed in
21.915 seconds (log SHA-256
`52828308cde6d52452f3643c84c110b658368e5587fc1f832d63f0160aa7fd80`).
The complete trained tiny export independently reconciles all 128 optimizer
events, sixteen source DFS calls, public-demo verifier probes kept outside the
candidate pool, exact adapter reset and rejection of an altered forward ledger.
That test passed in 13.996 seconds (log SHA-256
`4ea22f61ae50bb17e22353e9d8c411a8a3e24cb03c6411ba8ad7197665f635da`).

`nvarc-overnight-ttt-001` was accepted as private version 1, kernel ID
`136689709`. It uses the immutable 002 export via a kernel output mount; every
mounted weight must pass exact material verification before a model loads.
The local download need not gate this independent onsite material check, and
the plan explicitly says local export bytes were not yet verified at staging.
It binds one repeatedly exposed public tuning parent, all 128 source views,
rank 256/alpha 32, source cosine scheduling, sixteen source DFS calls and up to
34 eight-view verifications. Two public-demo verifier probes can exercise
ranking even if the decoder produces no candidates, and are never model
answers. It adds no palette/shape grammar or probability-floor repair.
Plan digest is `sha256:6a9dd999b59520b07003878c9305ca5f2cda04d55d909a2a90cc2d4f9b952500`.
[Kaggle notebook](https://www.kaggle.com/code/danielwuu/nvarc-overnight-ttt-001).
Its sole terminal retrieval verified failure at `exact-export-mount` after
8.110 seconds, before dependency/model work. Four distinct L4s were present;
the template omitted the owner-qualified `/kaggle/input/notebooks/` root.
Archive SHA-256 is `ee4590328b46169854f639913c5ddcdb3ebe628a999b250f90bd37f7a27d6ce9`.
The failed package and retrieval are frozen.

The distinct `nvarc-overnight-ttt-002` adds that exact notebook root and a
bounded mount inventory diagnostic, keeping the same scientific workload and
material bytes. It was accepted as private version 1, kernel ID `136690164`.
Plan digest is `sha256:9fcf49abeeece59eac5bb503240bc01d23dac3d64ba7e0860f02017f222fbc69`.
[Kaggle notebook](https://www.kaggle.com/code/danielwuu/nvarc-overnight-ttt-002).
Its 4B memory/performance and terminal outcome remain pending.

## SDG/TRM and milestone validation

The strict ML profile passed 45 tests in 329.491 seconds. It includes actual
WSL user/mount/PID/network namespace isolation, all ten saved-response SDG
stages, source preprocessing and real tiny TRM train/reload/TTT/joint Qwen
ranking. Log SHA-256 is
`dc67fc69d434b65b7c28e5279352678b30ca01027923a197c3314171fa6d1e21`.
These are engineering checks, not original teacher yield or full-size TRM proof.

Published SDG artifact version 1 has a closed provider inventory of 192
Parquet members and 47,514,077,184 uncompressed bytes. Its original-namespace
download is pending full archive SHA/CRC/member verification; no generated
program is executed during acquisition. The source-linked public TRM Dataset
`cpmpml/arc-prize-trm-031` version 1 contains seven 2,159,719,349-byte
checkpoints. Only the source's `step_220708` is being downloaded, with its exact
2,159,719,349-byte provider bound. Exact v18 notebook source
was requested once with version label 18 and returned HTTP 404; retained v21
source is not silently substituted for v18 parity.

Required repository validation passed 314 tests in 267.771 seconds for this
milestone. Log SHA-256 is
`bf5441a7801db8633f43d0191855b1f9a0f78184bcafe2542e74bb07e2e5fe06`.
