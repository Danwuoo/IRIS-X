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

For the installed CPU torch interpreter, run:

```powershell
$env:PYTHONPATH = 'src'
& 'C:/Users/wurre/AppData/Local/Programs/Python/Python312/python.exe' -m unittest tests.test_arc_nvarc tests.test_arc_nvarc_distributed -v
& 'C:/Users/wurre/AppData/Local/Programs/Python/Python312/python.exe' tools/nvarc_ml_profile.py
```

The first command executes synthetic SFT/resume and two-rank CPU Gloo DDP.
The strict ML profile returns `BLOCKED` until `transformers`, `peft`, and
`safetensors` are installed for Python 3.12. It records versions and then runs
tiny actual Qwen3.5 conversion/gradient and PEFT/reset tests. The current
interpreter has Python 3.12.10 and torch 2.12.1+cpu. Existing local wheel
caches did not contain the missing packages. Provision a separate optional
environment from a reviewed compatible wheelhouse, for example with
`python -m venv --system-site-packages .irisx/nvarc-ml-venv` and
`pip install --no-index --find-links <wheelhouse> transformers peft safetensors`;
record resolved versions before use. No real weights are needed for these
tiny tests. A skipped generic unittest run is not an ML profile pass.

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

   The freeze manifest now records exact per-source counts and rejects the
   known `arc2_evaluation6` source under `clean-research`. Source IDs and the
   excluded-parent list must be supplied from trusted lineage; this does not
   establish that an unknown upstream corpus is clean. The pinned NVARC SFT
   YAML concatenates six source datasets, but their actual counts and mixture
   are unavailable until those datasets are materialized and audited.
3. Run compact conversion with the pinned base revision and source manifest
   digest. The output is a distinct directory with `grid-vocab.json`, saved HF
   model, and `material-manifest.json`. The converter checks embedding/head
   rows and reload. It retains vision modules but passes only text IDs.
4. On a bounded pilot, check Qwen3.5 attention **and DeltaNet** gradients,
   PEFT LoRA target coverage, tied output head, one generation with EOS,
   throughput/peak VRAM and task reset. Stop on an unsupported module, OOM,
   nonfinite loss or missing full-grid completion. The present fixture does
   not pass this gate.

The Qwen candidate config now names `bounded-dfs` with cumulative NLL cutoff
`-log(0.2)`, at most 256 prefix expansions and four returned sequences per
view. An optional LRU retains full-prefix logits; model forwards still use
`use_cache=False`, preventing sibling hybrid-state leakage. A hybrid KV-cache
mode is explicitly rejected. A 1,000-token completion requires at least 1,001
expansions, so the 256 default cannot reach it. Full-prefix cache and reference
parity are CPU tested; 4B speed is unknown. `hf-beam` is a named
alternative, not source-method evidence. The parent still enforces one task
deadline across adaptation, all test inputs, generation and verification.
The result ledger counts generation calls, returned sequences and verification
calls separately. Phase F must measure DFS completion and cost before a larger
candidate run; Qwen3.5 hybrid cache reuse remains untested.

Real commands are deliberately gated. `convert-compact`, `train-sft`, and the
Kaggle runner require a new `authorization.json` with `approved: true`, exact
identity and nonempty owner decision/limits. The provided manifests remain
`approved: false`. A CLI flag alone cannot authorize them.

```powershell
$env:PYTHONPATH = 'src'
python -m irisx.arc_nvarc_cli snapshot-base-manifest --base <verified-base-dir> --output .irisx/arc-agi-2/qwen35-nvarc/base-model-manifest.json
python -m irisx.arc_nvarc_cli convert-compact --base <verified-base-dir> --base-manifest .irisx/arc-agi-2/qwen35-nvarc/base-model-manifest.json --output <new-compact-dir> --model-revision 851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a --model-manifest-digest <snapshot-output-digest> --authorization <approved-json>
python -m irisx.arc_nvarc_cli train-sft --compact-base <verified-compact-dir> --frozen-data <frozen-data-dir> --config trials/arc-agi-2-qwen35-nvarc/configs/sft-pilot.json --output <new-training-dir> --authorization <approved-json>
```

The local full-SFT backend is single-process and unpacked; its optimizer state
is separate from an exported inference model. `arc_nvarc_distributed.py` adds
DDP with disjoint rank samples, gradient collectives, rank-zero step checkpoints,
exact resume, and a cumulative session wall ledger. Its two-rank Gloo fixture
passes on Python 3.12. DDP copies the full model and optimizer to every rank;
GPU memory/throughput and sharding remain unverified before any full-corpus
proposal. Do not submit the original Qwen3 Megatron config unchanged.

TRM training has a separate two-stage path. First stage labelled JSON with
`stage_trm_training`, then use `trm_preprocess_spec` for the pinned upstream
`dataset/build_arc_dataset.py`; its output must contain `train/dataset.json`
before `trm_launch_spec(..., mode="train")` will produce a launch spec. The
evaluation spec requires a processed `test/dataset.json` and an exact checkpoint
file. Its NVARC script directory and TinyRecursiveModels import/config roots
are distinct. These specs are drafts; upstream dependencies, processed real
data and checkpoint are absent, and no TRM command was run. The pinned README
names `hydra-core==1.3.2`, `adam_atan2_pytorch==0.2.4`,
`argdantic==1.3.3`, `coolname==2.2.0`, `numba==0.62.1` plus PyTorch and the
matching upstream source. The current Python 3.12 environment lacks
`argdantic`, `numba`, and `hydra`. `arc_nvarc_trm.py` now has a bounded
subprocess wrapper, ten-attempt output parser and a visible-input raw-tensor
normalizer. These paths have synthetic launch/parser tests. The launch spec
disables the upstream evaluator that reads labelled `test_puzzles.json` and
saves `inputs`, `puzzle_identifiers`, `q_halt_logits`, and `preds` tensors.
The upstream script still mixes training/evaluation and derives optimizer
steps from `epochs`; pure inference launch semantics remain unverified.
Fixture predictions are tagged `trm-fixture` and rejected by model integration.

`arc_nvarc_sdg.py` saves stage identities and call reservations before provider
calls. Failed and pending calls are not retried automatically. Its Docker
program launcher pins a local image and bounds network, filesystem, CPU,
memory, process count, wall time and output size. Launcher flags and rejection
paths have fixtures; the Docker daemon was unavailable, so sandbox enforcement
has no integration evidence. A caller-supplied attestation claim is rejected.

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
