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
