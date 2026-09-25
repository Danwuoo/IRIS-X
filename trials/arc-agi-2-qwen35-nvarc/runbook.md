# Development and future execution runbook

## M2/M3 local execution and external preflight (2026-09-25)

The [M2/M3 record](m2-m3.md) gives observed artifact identities and precise
open gates. Use the installed strict CPU environment from the repository root.
Every command below is local and makes a new ignored output directory.

```powershell
& .irisx/nvarc-ml-venv/Scripts/python.exe tools/nvarc_source.py verify
& .irisx/nvarc-ml-venv/Scripts/python.exe tools/nvarc_m2_m3.py freeze --data .irisx/arc-agi-2/qwen35-nvarc/m2-m3/arc-data-new
& .irisx/nvarc-ml-venv/Scripts/python.exe tools/nvarc_m2_m3.py tiny-sft --data .irisx/arc-agi-2/qwen35-nvarc/m2-m3/arc-data-new --output .irisx/arc-agi-2/qwen35-nvarc/m2-m3/tiny-sft-new
& .irisx/nvarc-ml-venv/Scripts/python.exe tools/nvarc_m2_m3.py tiny-solve --data .irisx/arc-agi-2/qwen35-nvarc/m2-m3/arc-data-new --sft .irisx/arc-agi-2/qwen35-nvarc/m2-m3/tiny-sft-new --output .irisx/arc-agi-2/qwen35-nvarc/m2-m3/tiny-solve-new
& .irisx/nvarc-ml-venv/Scripts/python.exe tools/nvarc_m2_m3.py tiny-trm --data .irisx/arc-agi-2/qwen35-nvarc/m2-m3/arc-data-new --output .irisx/arc-agi-2/qwen35-nvarc/m2-m3/tiny-trm-new
& .irisx/nvarc-ml-venv/Scripts/python.exe tools/nvarc_m2_m3.py tiny-joint --data .irisx/arc-agi-2/qwen35-nvarc/m2-m3/arc-data-new --sft .irisx/arc-agi-2/qwen35-nvarc/m2-m3/tiny-sft-new --qwen .irisx/arc-agi-2/qwen35-nvarc/m2-m3/tiny-solve-new --trm .irisx/arc-agi-2/qwen35-nvarc/m2-m3/tiny-trm-new --output .irisx/arc-agi-2/qwen35-nvarc/m2-m3/tiny-joint-new
& .irisx/nvarc-ml-venv/Scripts/python.exe tools/nvarc_m2_m3.py sdg-replay --data .irisx/arc-agi-2/qwen35-nvarc/m2-m3/arc-data-new --output .irisx/arc-agi-2/qwen35-nvarc/m2-m3/sdg-replay-new
& .irisx/nvarc-ml-venv/Scripts/python.exe tools/stage_nvarc_m2_fsdp.py --data .irisx/arc-agi-2/qwen35-nvarc/m2-m3/arc-data-new --output .irisx/arc-agi-2/qwen35-nvarc/m2-m3/fsdp-review-new
& .irisx/nvarc-ml-venv/Scripts/python.exe tools/stage_nvarc_m3_teacher.py --output .irisx/arc-agi-2/qwen35-nvarc/m2-m3/teacher-review-new
& .irisx/nvarc-ml-venv/Scripts/python.exe tools/preflight_nvarc_m2_m3.py .irisx/arc-agi-2/qwen35-nvarc/m2-m3/fsdp-review-new --report .irisx/arc-agi-2/qwen35-nvarc/m2-m3/fsdp-review-new/preflight.json
& .irisx/nvarc-ml-venv/Scripts/python.exe tools/preflight_nvarc_m2_m3.py .irisx/arc-agi-2/qwen35-nvarc/m2-m3/teacher-review-new --report .irisx/arc-agi-2/qwen35-nvarc/m2-m3/teacher-review-new/preflight.json
```

The FSDP stage requires the existing, independently verified compact 4B
material and creates hardlinks for one prospective private model Dataset. The
teacher stage uses the existing private full-vocabulary model/wheel Dataset;
it packages only pinned public training demos and source prompts. Both
`kernel-metadata.json` files are private, `NvidiaL4`, Internet-disabled and
both notebooks fail their `approved: false` gate before model/provider work.

Decision 0028 now supplies the exact bounded authorization. For any approved
package, create a local authorization JSON with
`approved: true`, `owner_decision`, `draft_plan_sha256`, `run_id` and final
`kernel_id`; FSDP also requires `model_dataset_id`. Restage to a **new** output
with `--authorization <file>` and inspect its updated summary/notebook before
the bounded Dataset/kernel commands. Never mutate an executed package or reuse
a failed identity. The staged FSDP worker invokes
`torch.distributed.run --nproc_per_node=4 -m irisx.arc_nvarc_fsdp` for one step.
The teacher worker invokes `irisx.arc_nvarc_sdg_teacher` for at most four
dependent calls. The terminal files and one retrieval per approved identity
must be retained; provider errors consume that identity. A successful 4B
feasibility step alone does not authorize the subsequent 8-step 4B SFT.
The FSDP package keeps compact files flat beside the CLI's singular
`dataset-metadata.json`. After approval, the bounded commands are:

```powershell
& .irisx/nvarc-ml-venv/Scripts/python.exe -m kaggle datasets create -p (Resolve-Path <approved-fsdp-package>/model-dataset).Path
& .irisx/nvarc-ml-venv/Scripts/python.exe -m kaggle kernels push -p <approved-fsdp-package>/kernel --accelerator NvidiaL4 --timeout 1800
& .irisx/nvarc-ml-venv/Scripts/python.exe -m kaggle kernels push -p <approved-teacher-package>/kernel --accelerator NvidiaL4 --timeout 1800
& .irisx/nvarc-ml-venv/Scripts/python.exe -m kaggle kernels output <exact-owner/slug/version> -p <new-local-output>
```

Dataset creation defaults to private. On Windows, pass an **absolute** Dataset
path: the installed CLI's resumable-upload cache cannot create its local temp
file for a relative path containing directory separators. This failure occurs
before a Dataset version request. Push the FSDP kernel only after its Dataset
version receipt. The teacher package attaches the existing private Dataset.
Preserve both returned kernel version IDs and use the final line at most once
for each terminal version. Decision 0028's teacher version 1 and its sole
retrieval are consumed; these commands are now lineage, not repeat authority.
The pre-submit FSDP transport revision mounts
`arc-prize-2026-arc-agi-2`, as did the prior successful four-L4 compact run;
its notebook still reads only the embedded frozen public training sequences.
The original no-competition-source teacher kernel received two T4s despite
requesting `NvidiaL4`. A metadata request does not prove actual hardware.
After an authorized teacher retrieval, keep the raw stage ledgers private and
run the local replay with the exact approved package seed:

```powershell
& .irisx/nvarc-ml-venv/Scripts/python.exe tools/nvarc_m2_m3.py sdg-teacher-replay --teacher-ledgers <retrieved>/m3-teacher-small-001/stage-ledgers --teacher-seed <approved-package>/seed.json --data <frozen-data> --output <new-local-output>
```

It extracts the two generated functions as text, executes them only in the
verified WSL namespace, and applies the pinned source pair filter and
augmentation. This ARC-seeded six-stage bridge does not claim HARC/BARC
cleaning parity; the separate saved-response test exercises all ten stages.

## Compact 4B small complete flow (2026-09-24 terminal)

The new [development plan](../../docs/plan/2026-09-24-qwen35-compact-complete-pilot.md)
and checked-in `configs/compact-complete-001.json` define the distinct
`nvarc-4b-compact-complete-001` identity. Decision 0026 authorized one
execution, which [failed before model loading](compact-complete-001.md). Its
one push and one terminal retrieval are consumed. The synthetic
visible source has two tasks, two test inputs each, rectangular grids, and no
test outputs. Its source digest is of those visible bytes only. The official
competition mount is checked for presence but no challenge file is read.
Decision 0027's separate [version 002](compact-complete-002.md) exposed a
serializer bug; [version 003](compact-complete-003.md) completed the bounded
flow and passed independent local verification. Session kernel debugging
authority has ended.

Local prepare, package and validation commands (no Kaggle mutation):

```powershell
$env:PYTHONPATH = 'src'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
python -m irisx.arc_nvarc_compact_pilot prepare --plan trials/arc-agi-2-qwen35-nvarc/configs/compact-complete-001.json --visible trials/arc-agi-2-qwen35-nvarc/configs/compact-complete-visible.json --model-manifest trials/arc-agi-2-qwen35-nvarc/configs/base-model-manifest.json --wheel-manifest trials/arc-agi-2-qwen35-nvarc/configs/base-wheel-manifest.json
python tools/stage_nvarc_compact_complete.py --output .irisx/arc-agi-2/qwen35-nvarc/compact-complete-review-003
& .irisx/nvarc-ml-venv/Scripts/python.exe -m unittest tests.test_arc_nvarc_compact_pilot tests.test_arc_nvarc_ml -v
```

The stage summary gives the exact plan, visible source, model/wheel manifest,
new IRIS-X wheel, notebook and metadata hashes. The draft notebook stops
before hardware/model work. An owner-approved authorization JSON must bind
the exact draft plan SHA-256, run ID, final kernel ID
`danielwuu/iris-x-4b-compact-complete-001`, and owner decision; pass its path
to `stage_nvarc_compact_complete.py --authorization` in a **new** output
directory to build the executable package. The prepared wheel/plan identity
then changes and must be reviewed before launch. Do not edit the draft kernel
metadata by hand.

The installed runtime also exposes `python -m irisx.arc_nvarc_compact_pilot
preflight --plan <approved-plan> --visible <visible-json> --model-manifest
<base-manifest> --wheel-manifest <wheel-manifest> --base <Dataset-v2-root>
--competition-source <official-challenge-file> --output <new-preflight-json>`.
It checks environment and full source inventory without loading model weights
or reading the challenge file. The notebook's `run` entry performs the same
gates in its first phases, so a separate preflight invocation is optional and
would reread the 9.34 GB inventory.

The authorized version 1 followed this planned CLI sequence: one private
`kaggle kernels push -p <approved-package>/kernel`, bounded terminal status
checks, one `kaggle kernels output` retrieval with local
`PYTHONIOENCODING=utf-8`, then
`python -m irisx.arc_nvarc_compact_pilot verify --output <retrieved-run-dir>`
against the retrieved `outbound.zip`, `result.zip`, and compact model inventory.
Before push, check
credential freshness through an own-kernel listing without printing tokens.
If the API rejects the request before creating a version, inspect own-kernel
status and retry the **same package bytes once at most** under the proposed
transport ceiling. HTTP 400 cause is unknown; changing a slug is not assumed
to fix it. Once a version is accepted, no model retry or second push is
proposed. Provider status, source and output requests stay inside the separately
approved bounds. This paragraph is an execution procedure, not approval.

The notebook reuses Dataset v2, the official competition mount, private
Internet-off `NvidiaL4` metadata, early `nvidia-smi` UUID/memory diagnostics,
and exact offline wheel hashes. It removes only optional incompatible `torchao`
before importing PEFT and records installed versions. The runner verifies the
entire 9.34 GB base inventory, converts its pinned source tokenizer rows into
a distinct 16-symbol compact model, saves/reloads and verifies its closed
material inventory, then uses one L4 for task-local adaptation and real grid
candidate generation. Source conversion runs before task reservation; if it
fails there is a phase failure record and **no** result ZIP. Once outbound and
checkpoint exist, the one-worker supervisor charges reservations before each
task, forcibly stops a timed-out worker, terminalizes pending tasks, and
packages a truth-free result. An outer 2,100-second timeout can finalize an
existing checkpoint but never resumes inference. The new compact artifact
remains in private kernel output and may be roughly 8–9 GB; output retrieval
must have disk capacity for it.

The plan ceilings are one kernel push, one terminal retrieval, USD 0 paid,
2,400 seconds session including 300 seconds finalization, 900 seconds per
task, two LoRA steps total with 128 token reservation, four generation calls,
eight sequences, 64 DFS forwards and 64 verification forwards. The pilot uses
rank 2 and a 64-token sequence limit; it does not test production rank 256 or
8,192 tokens. Missing/invalid candidates remain missing. A successful GPU
claim needs a verified result and at least one actual complete grid; otherwise
report a partial result. No ARC accuracy or full NVARC reproduction claim
follows from this synthetic flow.

All commands start at the repository root. The fixture and local pilot staging
commands run end to end. Neither starts a provider/model workload; generated
output stays under ignored `.irisx/`.

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
The strict ML profile now passes in a separate ignored
`.irisx/nvarc-ml-venv` with Python 3.12.10, torch 2.12.1+cpu,
Transformers 5.8.1, PEFT 0.21.0 and Safetensors 0.8.0. It runs tiny actual
Qwen3.5 conversion/gradient and PEFT/reset tests. Recreate it from the
recorded versions, then run
`.irisx/nvarc-ml-venv/Scripts/python.exe tools/nvarc_ml_profile.py` with
`PYTHONPATH=src`. This does not load 4B weights or prove GPU behavior. A
skipped generic unittest run is not an ML profile pass.

## Material and compatibility gates

1. Reuse the pinned Qwen3.5-4B base already present in the private Kaggle
   Dataset v2 for the proposed [4B compatibility pilot](4b-pilot.md). Small
   model/wheel manifests were retrieved and committed; the 9.34 GB base was
   **not** downloaded locally. The pilot checks every member SHA-256 at the
   exact mount before loading. Full conversion/training needs its own material
   and resource decision.
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
file. It targets the NVARC inference entry, which checks upstream source and
material hashes, loads the checkpoint, bounds test batches and calls the pinned
upstream evaluator without entering its training loop. A CPU fake-source
harness verifies that control flow and raw output. Its NVARC script directory
and TinyRecursiveModels import/config roots are distinct. These specs are
drafts; upstream dependencies, processed real data and checkpoint are absent,
and no upstream TRM command was run. The pinned README
names `hydra-core==1.3.2`, `adam_atan2_pytorch==0.2.4`,
`argdantic==1.3.3`, `coolname==2.2.0`, `numba==0.62.1` plus PyTorch and the
matching upstream source. The current Python 3.12 environment lacks
`argdantic`, `numba`, and `hydra`. `arc_nvarc_trm.py` now has a bounded
subprocess wrapper, ten-attempt output parser and a visible-input raw-tensor
normalizer. These paths have synthetic launch/parser tests. The inference
entry disables the upstream evaluator that reads labelled `test_puzzles.json`
and saves `inputs`, `puzzle_identifiers`, `q_halt_logits`, and `preds` tensors.
The pinned script's own launch remains training-only; actual upstream CUDA
compatibility of the new entry is unverified.
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

## Tiny GPU compatibility draft

The owner chose the real 4B route after this draft. Its single authorized
[4B pilot](4b-pilot.md) reached a terminal hardware-gate failure; no repeat
execution is authorized. The tiny-only GPU A package below remains unapproved.

`python tools/stage_nvarc_gpu_compat.py` produces an offline, reviewable
single-notebook package under `.irisx/arc-agi-2/qwen35-nvarc/gpu-a/`.
It embeds the current local IRIS-X wheel, checks both embedded SHA-256 digests,
and uses only Kaggle's installed PyTorch, Transformers, PEFT and Safetensors.
No Dataset, competition source, 4B weights or ARC records are mounted. The
notebook remains private with Internet disabled and writes one truth-free JSON
result. Its current `approved: false`, draft kernel ID and `UNBOUND` dependency
versions stop execution before wheel install or GPU work. Staging only writes
local ignored files; it does not call Kaggle.

If the owner selects this route, bind the exact Kaggle image and four installed
package versions, explicit run identity and retention, then review the rebuilt
notebook and hashes before one authorized push. The proposed ceiling is one
free private kernel, zero paid cost, at most 30 minutes session, one GPU device
used (up to four visible), two tiny training steps and 128 training tokens,
zero pretrained-model inference calls, one output retrieval, no retry. The
model's two layers exercise full attention and DeltaNet gradients, embedding
and head gradients, and PEFT success/failure reset. The local test covers the
draft guard and notebook composition; real architecture compatibility is the
point of the future GPU check.
