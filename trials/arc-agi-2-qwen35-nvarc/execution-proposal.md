# Proposed resource stages — no execution authorization

The next owner decision should authorize **only Phase F** after fixing exact
materials and a nonempty run identity. All numbers below are proposed maxima,
not measured Qwen3.5 throughput. Actual VRAM, step time and Kaggle queue time
are unknown. Paid cap remains **USD 0** for these drafts; any unavailable free
or owner-owned compute pauses the phase for a new budget decision. Existing
terminal trial ceilings do not transfer here.

| Phase | Materials/workload | Proposed hard ceilings and stop | Output |
| --- | --- | --- | --- |
| F: minimal compatibility | Pinned base Dataset v2, exact tokenizer/config, one clean synthetic/public-training task, candidate compact converter | Private L4×4; 4 LoRA steps total at rank 8, ≤4 generation invocations/4 sequences at ≤128 new tokens, bounded DFS ≤64 full-prefix forwards per invocation with cumulative NLL cutoff `-log(0.2)`, ≤600 s/task, ≤3,600 s session incl. 300 s finalization; 1 kernel and 1 retrieval only if separately approved; stop on four-GPU gate, DeltaNet/attention gradient mismatch, OOM, missing EOS, failed reload or DFS cap | Row mapping, loss/gradient, peak VRAM, step time, adapter reset and one truth-free partial result. No accuracy claim. |
| P: SFT pilot | Frozen clean labelled pilot, compact checkpoint, verified dependencies | 32 full-SFT optimizer steps, ≤131,072 training tokens, sequence ≤2,048, one H100 80GB or equivalent owner-owned compute, ≤2 h wall + 15 min finalization, checkpoint every 4 steps; 0 solver generations. Stop on OOM/nonfinite/zero gradient or data mismatch | Training state and distinct inference export; measured throughput/VRAM to resize full proposal. |
| S: full ARC SFT | Approved exposure-labelled full data manifest, proven distributed Qwen3.5 path | Source scale ceiling 12,716 steps, global batch ≤256, ≤3.26B training tokens, ≤32 H100 for ≤30 h, checkpoint ≤200 steps, 1 h finalization; no launch before a revised cost/resource approval and pilot proof | New immutable ARC-SFT checkpoint, validation loss and lineage, not a claim of source score. |
| E: fixed Q0–Q3 comparison | Same frozen, full-task train/selection-dev/locked-eval IDs and exact source parity; Q0 base, Q1 SFT/no TTT, Q2 +TTT, Q3 multi-view/rank | Draft ≤128 locked tasks, ≤256 test outputs, Q0/Q1/Q2 ≤256 generation calls each, Q3 ≤4,096 calls/16,384 sequences, ≤1,024 tokens/sequence, ≤1,200 s/task and ≤12 h/session per configuration incl. 900 s finalization; no retry | One truth-free result per config, one final sealed pass@2 comparison; dev and locked usage counted separately. |
| T: TRM branch/integration | Pinned TRM source, approved labelled data and independent trained checkpoint | Separate training proposal: ≤8 H100×24 h, ≤10,000 epochs, 256 augmentations/task; evaluation ≤4 L4×4 h, ≤10 attempts/test and bounded Qwen rescoring. Stop on artifact or version mismatch | TRM-only and joint Qwen-verified candidate results, never score-summed across branches. |
| D: SDG teacher | Approved teacher, prompts, source licenses, isolated Python executor and dataset lineage | **0 calls in this draft**. A later decision must bind model/provider/data/retention/call-token caps and sandbox. | Versioned generated material and filter trace, then a new data freeze. |

Phase F is a compatibility check, not a shortcut to Phase S or E. Pilot/full
SFT throughput and memory estimates must come from actual new measurements;
inference tokens/s from previous trials is not a training estimate. Phase E's
128/256 upper bounds are placeholders until an exact full-task workload and
its test-output count are frozen. Never trim multi-test cases to make the bound
fit; amend the proposal instead.

The machine-readable [`draft-phases.json`](configs/draft-phases.json) and
[`draft-kernel-metadata.json`](configs/draft-kernel-metadata.json) carry
`approved: false`, identity placeholders, resource ceilings, checkpoint and
retrieval conditions. A future owner-approved decision must name the provider,
specific model/data identities, cost limit, stop conditions, expected outputs
and retention before any external/provider work. Results remain private and
truth-free; public evaluation and competition submission need separate scope.

The local continuation adds a CPU DDP collective path, which synchronizes
gradients but leaves full model and optimizer copies on every rank. Phase S
must use separately measured GPU memory and, if necessary, an explicitly
validated sharding backend. Phase T has a local raw-tensor normalizer that
matches predictions to visible inputs and bypasses the pinned upstream
evaluator's label-bearing `test_puzzles.json`. It is parser-fixture verified;
the upstream script still derives steps from `epochs` and mixes training and
evaluation. Its pure inference launch behavior requires source-backed testing
and separate authorization before sealed tasks.

## Owner-selected next preparation: bounded real 4B pilot

The owner selected preparation of a **real Qwen3.5-4B pilot** rather than the
tiny-only GPU A kernel. The exact, unapproved
[4B pilot proposal](4b-pilot.md) now binds the existing private Dataset v2,
model and wheel manifests, synthetic-only training data, a one-L4 LoRA
workload, two steps/128 tokens, zero generation, one private kernel and one
terminal retrieval, 1,800 seconds and USD 0. Local staging and fail-closed
guards are implemented. This is a compatibility pilot; it does not authorize
full SFT or an ARC score. A specific launch decision remains open.

## Earlier narrow GPU acceptance choice after the second control review

At the second review, the repaired local control flow led to the two routes
below. The owner subsequently selected B preparation, implemented in the
bounded 4B pilot above. Neither route was a launch approval; the original
Phase F draft above is not an execution token.

| Choice | Proposed scope | Required binding before launch |
| --- | --- | --- |
| A: tiny random-model compatibility | One private Kaggle L4 kernel, Internet off, free tier only and USD 0; ≤30 min session, one GPU used, ≤2 training steps/128 tokens, zero model-generation calls, no ARC data or 4B weights; one terminal output retrieval, no retry. Exercise Qwen3.5 full-attention/DeltaNet/embedding/head gradients and PEFT reset. | [`draft-gpu-a.json`](configs/draft-gpu-a.json) is `approved: false`; the exact Kaggle image and installed torch/transformers/peft/safetensors versions, owner decision reference, final kernel ID and output retention must be bound. Local notebook staging is in `tools/stage_nvarc_gpu_compat.py`. |
| B: 4B compatibility | A separate private free-tier proposal would bind the exact base/model/tokenizer weights and hashes, mounting path, dependency wheels/image, GPU topology, training/inference call and token caps, wall ceiling and one retrieval. | Selected for preparation. The bounded [4B pilot](4b-pilot.md) now has local code and a staged draft notebook; no kernel has been launched. The broader Phase F placeholders remain insufficient. |

The [second control review](control-review-4d23546.md) now contains the repair
disposition. CPU evidence is not a real Qwen3.5, PEFT or TRM runtime claim.
The [Kaggle v170 GPU release](https://github.com/Kaggle/docker-python/releases/tag/v170-GPU-bdf9e0538555f90453619adefb49ba40cfa136db44a9c9be7a42ea715c0aa068)
supplies a target image digest and lists PEFT 0.19.1. The draft kernel metadata
does not pin that image; installed versions and image availability must be
verified before replacing the `UNBOUND` values. No version is guessed from
the release diff.
