# Development and future execution runbook

All commands start at the repository root. The only command below that is
currently executable end to end is the synthetic fixture command. It has no
model/provider/Kaggle access and writes only to ignored `.irisx/`.

```powershell
$env:PYTHONPATH = 'src'
python -m irisx.arc_nvarc_cli fixture-e2e --output .irisx/arc-agi-2/qwen35-nvarc/offline-e2e-review
python tools/repository_check.py --all
```

Use a new empty output directory when repeating the fixture command. It
produces `outbound.zip`, `result.zip`, `frozen-data/manifest.json`, a tiny
training checkpoint, and a separate `sealed-fixture-score.json`. The score is
never in outbound/result. No model weights are read.

## Material and compatibility gates

1. Acquire the pinned Qwen3.5-4B base and verify its full upstream manifest.
   This worktree only retained small `config.json`, tokenizer config, template,
   and weight index. The 9.34 GB base was **not** downloaded here. Obtain an
   exact new owner decision and bounded resources before materializing the
   real conversion/training path.
2. Freeze a labelled training dataset with explicit source, parent, split,
   known-transform group and exposure policy. Importing a released NVARC
   dataset is not rerunning SDG. Do not put labelled `test` outputs in solver
   workload, inference Dataset or result ZIP. Document any `arc2_evaluation6`
   exposure separately; `clean-research` still says `unproven`.
   The disk-backed path streams JSONL into deterministic shards and checks
   parent/known-transform overlap without loading the full corpus:

   ```powershell
   python -m irisx.arc_nvarc_cli freeze-data --input <labelled-records.jsonl> --split sft-train --policy clean-research --excluded-parents <excluded-parent-ids.json> --output <new-frozen-dir> --shard-size 8192
   ```
3. Run compact conversion with the pinned base revision and source manifest
   digest. The output is a distinct directory with `grid-vocab.json`, saved HF
   model, and `material-manifest.json`. The converter checks embedding/head
   rows and reload. It retains vision modules but passes only text IDs.
4. On a bounded pilot, check Qwen3.5 attention **and DeltaNet** gradients,
   PEFT LoRA target coverage, tied output head, one generation with EOS,
   throughput/peak VRAM and task reset. Stop on an unsupported module, OOM,
   nonfinite loss or missing full-grid completion. The present fixture does
   not pass this gate.

Real commands are deliberately gated. `convert-compact`, `train-sft`, and the
Kaggle runner require a new `authorization.json` with `approved: true`, exact
identity and nonempty owner decision/limits. The provided manifests remain
`approved: false`. A CLI flag alone cannot authorize them.

```powershell
$env:PYTHONPATH = 'src'
python -m irisx.arc_nvarc_cli convert-compact --base <verified-base-dir> --output <new-compact-dir> --model-revision 851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a --model-manifest-digest <sha256:...> --authorization <approved-json>
python -m irisx.arc_nvarc_cli train-sft --compact-base <verified-compact-dir> --frozen-data <frozen-data-dir> --config trials/arc-agi-2-qwen35-nvarc/configs/sft-pilot.json --output <new-training-dir> --authorization <approved-json>
```

The local full-SFT backend is single-process and unpacked; its optimizer state
is separate from an exported inference model. Before a 12,716-step/full-corpus
run, a Qwen3.5-compatible distributed training implementation and a measured
single-step memory/throughput report are required. Do not submit the original
Qwen3 Megatron config against Qwen3.5 unchanged.

## Static Kaggle packaging

`draft-outbound` selects complete task IDs from an exact challenge snapshot,
including every test input. It strips all test outputs, binds the source/model/
tokenizer/data/runtime digests and run limits, and uses existing canonical ZIP
transport. Build a wheel locally and stage the two exact files:

```powershell
python -c "import sys; sys.path.insert(0,'tools'); import irisx_build_backend as b; print(b.build_wheel('.irisx/arc-agi-2/qwen35-nvarc/wheels'))"
python -m irisx.arc_nvarc_cli draft-outbound --challenges <verified-official-challenge.json> --task-ids <selected-task-ids.json> --binding-fields <approved-binding-fields.json> --output .irisx/arc-agi-2/qwen35-nvarc/outbound.zip
python -m irisx.arc_nvarc_cli stage-runtime --outbound .irisx/arc-agi-2/qwen35-nvarc/outbound.zip --wheel .irisx/arc-agi-2/qwen35-nvarc/wheels/irisx-0.2.0-py3-none-any.whl --output .irisx/arc-agi-2/qwen35-nvarc/staging
```

The draft notebook/metadata describe a **private**, Internet-disabled
`NvidiaL4` kernel with official `arc-prize-2026-arc-agi-2`, owner-qualified
runtime and new ARC-SFT model Datasets. Existing base Dataset
`danielwuu/irisx-arc-agi-2-trial-002-smoke-001` version 2 may be reused for
the original model but does not contain the new trained artifact. Notebook
mounts resolve only listed exact current/legacy paths. The runner checks four
different L4 UUIDs, exact challenge digest and full-task visible parity before
loading the model. Four persistent workers dynamically receive whole tasks;
TTT and every test/candidate share a parent-enforced task deadline. Pending
task reservations count at their maximum on interruption. A resume never
silently repeats the task; the parent writes terminal records for timeout,
crash, OOM, missing candidates and not-executed work.

No Kaggle Dataset/kernel push, result retrieval, or real run is authorized by
this runbook or draft files. After a separately approved run, verify the
result ZIP against its outbound and score only in an evaluator enclave with
full-task sealed truth. The scorer denominator is every specified test output;
report pass@1, pass@2, task-all-correct, invalid/missing and timing separately.
