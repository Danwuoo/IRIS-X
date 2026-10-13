# Persistent Qwen branch checkpoints

Implementation: `worktree/tools/arc_qwen_portfolio_20261012/checkpoints.py`
Tests: `tests/test_checkpoints.py`

## Changes

- The old `Trainer.save_checkpoint` uses `state.pt`, omits scaler and some complete logical restart fields, and cannot persist a clean untrained base. Its adapter exporter does not establish a fresh-backend reload. The new module does not reinterpret old reports as saved weights; v18 exported no adapters.
- New immutable update directories contain only bounded JSON and safetensors shards. Publication uses a same-filesystem atomic directory rename after file and directory fsync. Existing updates are never overwritten or silently pruned.
- Each safetensors file is at most 32 MiB, retaining the existing 64 MiB process file limit. The whole checkpoint store is capped at 2 GiB. Production admission reserves space for the remaining store budget plus at least 4 GiB free disk. Actual tensor/file bytes and every file hash are recorded.
- Inference assets have their own complete manifest and may be copied alone. Their tokenizer and base model are exact external references. The resume tree references the same physical adapter shards rather than duplicating adapter bytes. The installed PEFT version does not support sharded adapter loading directly; `load_inference_adapter` is the explicit validated loader.
- Resume state retains optimizer, scheduler, optional scaler, all cleared-gradient semantics, sampler/cursor/counters, Python/NumPy/Torch/CUDA RNG, task/caller/global snapshots, and model training mode. Identity binds live model/tokenizer/runtime, source, full configuration, records, branch, decoder, and expanded realized PEFT target inventory.
- Branch mismatch, changed model/config/tokenizer/source, wrong manifests, unexpected files, corruption, symlinks/hardlinks, unsafe paths, nonfinite or wrong-dtype/shape tensors, and incomplete update boundaries are rejected. Restore preserves live parameter objects and cannot restore physical accounting. Unexpected restore errors roll logical state back.

## API

- `save_branch_checkpoint(trainer, root, branch_id=..., update=..., records=..., provenance=...)`
- `load_branch_checkpoint(trainer, receipt['path'], branch_id=..., records=..., expected_manifest_sha256=...)`
- `load_inference_adapter(trainer, receipt['inference_path'], branch_id=..., records=..., expected_inference_manifest_sha256=...)`
- `inspect_checkpoint(path, expected_manifest_sha256=...)`
- `verify_disk_reload(..., clean_snapshot=..., evaluate=...)` compares actual generated token IDs and exact NLL before and after a clean reset and disk reload. The callback must make real metered native calls.

The experiment uses one explicitly shared frozen-base checkpoint plus independent grid/program update-8 and update-16 states. Load-time branch identity remains strict. The module also supports two separately branch-bound base states within the same hard cap. The pinned model has 32,112,640 LoRA elements (128,450,560 FP32 bytes). Two base states plus four states with two Adam moments require at most 1,798,307,840 raw tensor bytes before metadata; the shared-base experiment needs less.

## Validation scope

The actual CPU fixture uses native Qwen3, four layers, hidden size 8, all 151936 input/output rows, BF16 frozen base and FP32 rank-8/alpha-16 LoRA. Its 28 expanded targets cross PEFT's 20-target minimization threshold. The suite persists update 0/8/16, checks actual generation/NLL parity, destroys the first model/trainer before reconstructing a fresh backend, loads a standalone inference-only directory, and verifies complete-state equality of resumed update 17 against uninterrupted update 17. Physical work remains charged. Test checkpoint paths are temporary and cleaned; the receipt is evidence, not pretrained adapter weights.

Read `checkpoints-tests.log` and `checkpoint-cpu-receipt.json` for the latest executed status and source hash. No pretrained 14B weights, GPU execution, provider actions, Git operations, or downloads were performed for this implementation. Full-size GPU fresh-constructor parity remains a manual runtime gate.
