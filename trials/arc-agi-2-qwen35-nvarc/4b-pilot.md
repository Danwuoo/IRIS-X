# Qwen3.5-4B Kaggle compatibility pilot

Status: **terminal hardware-gate failure; Decision 0021 push and retrieval consumed**.
Owner selected a real 4B pilot preparation on 2026-09-23. This is one bounded
LoRA compatibility run, not full SFT, ARC evaluation, or a claim of NVARC
reproduction. It supersedes the tiny-only GPU A route for the next execution
choice. All older trial quotas and identities remain separate.
Implementation package: `1990872` on `main`, building on reservation repair
`9cd1839`, DDP repair `4267890` and TRM inference repair `f532885`.

## Exact materials and data

- Run identity: `nvarc-4b-compat-pilot-001`; approved metadata kernel ID
  `danielwuu/irisx-nvarc-4b-compat-pilot-001`. The one push produced Kaggle
  version 1 at the actual title-derived slug
  [`danielwuu/iris-x-qwen3-5-4b-bounded-lora-compatibility-pilot`](https://www.kaggle.com/code/danielwuu/iris-x-qwen3-5-4b-bounded-lora-compatibility-pilot).
  The local launch ledger records this slug mismatch; the approved plan and
  submitted bytes were not changed or pushed again.
- Reuse the existing **private** Kaggle Dataset
  `danielwuu/irisx-arc-agi-2-trial-002-smoke-001` version 2. Read-only CLI
  inventory on 2026-09-23 confirmed both BF16 weight shards, config, tokenizer,
  PEFT 0.21.0, Transformers 5.8.1, Safetensors 0.8.0, Tokenizers 0.22.2,
  Accelerate 1.10.1 and other offline wheels. The Kaggle metadata describes
  version 2 and private visibility; its file-list API did not expose a version
  number. The notebook verifies exact bytes at mount before loading.
- Model: `Qwen/Qwen3.5-4B@851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`.
  The retained Dataset [model manifest](configs/base-model-manifest.json)
  binds all 15 model files, 9,342,907,469 bytes total, with manifest digest
  `sha256:8f27407e1b0ee4dd7a5b4d62d39af9b356ba86b5701dd93eafba052febe9c72f`.
  Its two shards are 5,329,398,688 and 3,990,429,408 bytes, with SHA-256
  `26a93f066e1916adb13453dae5a0c707c0fbc71299ed98779571a907b8e74c61`
  and `cb544bd9bfae93dc59b0f22b292f5933573854a7f9b97835c67060d7d910e188`.
  The [wheel manifest](configs/base-wheel-manifest.json) binds the existing
  offline wheels with digest
  `sha256:d24d85f791788621166fa05d7db51c03f7c72c046af4923096b12863f7e7dfa1`.
  Only the small manifests/config were downloaded locally; no 9 GB duplicate.
- Input is one deterministic **synthetic** grid demonstration generated inside
  the runner. There is no ARC task, sealed answer, competition mount, external
  teacher, large labelled dataset, or model generation. The package tests
  architecture/PEFT behavior and memory only.
- Target Kaggle GPU image reference:
  [`v170-GPU-bdf9e0538555f90453619adefb49ba40cfa136db44a9c9be7a42ea715c0aa068`](https://github.com/Kaggle/docker-python/releases/tag/v170-GPU-bdf9e0538555f90453619adefb49ba40cfa136db44a9c9be7a42ea715c0aa068).
  The CLI kernel metadata selects `NvidiaL4`, not that Docker digest. Installed
  torch/image bytes were not pinned by that metadata. The runner checks Python,
  exact installed offline packages, GPU model and capacity before model work.
  The failure result omits installed versions and observed GPU properties, so
  the exact hardware mismatch and image bytes remain unknown.

## One-run ceiling and stop

The retained [machine-readable draft](configs/draft-4b-pilot.json) remains
`approved: false`; Decision 0021 permitted staging a separate bound approved
notebook. It authorized one private Kaggle kernel push and one terminal output
retrieval, no retry or resume, Internet off, and USD 0 paid cost. The kernel
may see one to four L4s but uses **one** with at least 22,000 MiB; no DDP or
sharding claim follows. Maximum 1,800 seconds from notebook start: setup at
most 180 seconds, worker at most 1,500 seconds, 300-second finalization
reserve. Exactly two reserved LoRA optimizer steps at most, 128 training
tokens, zero model generations, zero teacher calls, and no ARC scoring.
The runner creates an atomic ledger before material checks and reserves each
step/tokens before work. Pending reservations count as consumed on failure;
there is no automatic retry. It stops on missing/different material, dependency
or GPU mismatch, OOM, nonfinite loss, absent attention/DeltaNet/embedding/head
LoRA gradients, no adapter update/reset, or deadline. The result JSON and
ledger contain only counters, versions, timing, memory, loss and error class;
they are private and truth-free. Retain a local digest and result through owner
review; no publication or competition submission.

BF16 weights alone occupy about 8.68 GiB (9.32 GB decimal). Actual CUDA
workspace, LoRA state and activations are unknown, so **L4 fit is a pilot
question**, not a measured fact. Full-model AdamW SFT would require separate
memory/sharding proof; this run deliberately uses frozen-base LoRA r=2.

## Prepared and executed package

From the repository root, offline staging writes only under `.irisx/`:

```powershell
$env:PYTHONPATH = 'src'
python tools/stage_nvarc_4b_pilot.py
```

The draft metadata ID starts `DRAFT-DO-NOT-PUSH/`, and its first executable
cell refuses unapproved input before installing wheels or touching the GPU.
The approved package was staged separately with Decision 0021, then pushed
once with `--accelerator NvidiaL4 --timeout 1800`. The Kaggle kernel reached
`COMPLETE`; one terminal output retrieval was made. Both allowances are
consumed. The ignored local launch directory
`.irisx/arc-agi-2/qwen35-nvarc/4b-pilot-launch-001/` retains the exact
approved package, atomic launch ledger, six retrieved files and verification
report. Its verification SHA-256 is
`008227921a0ad2a53abce834534fad0438525cff5c8ccc33cbf09e437f40d6ea`.

## Terminal evidence

The application result is `failed` with `ValidationError: pilot requires one
usable L4 with 22000 MiB`. The guard checks CUDA availability, one to four
visible devices, the device-0 name containing `L4`, and device-0 total memory
of at least 22,000 MiB. The output does not identify which condition failed;
it does not record the observed GPU name or capacity. The runner reached this
guard after exact model-material verification and dependency/version checks,
but before loading the 4B model. The returned ledger and result agree on
**zero reserved/completed optimizer steps, zero training tokens and zero
generation calls**. The result is truth-free. Kaggle `COMPLETE` describes the
notebook's terminal state, not a successful pilot.

Local verification matched the retrieved plan, model manifest and wheel to
their approved prelaunch SHA-256 values. The canonical plan digest in the
result and ledger is
`sha256:4b194bcce885162519fc381bf1ca61119d713fe37e50ddb580ac6594e5fc7233`.
The result SHA-256 is
`0f84494a724d7191535752774d1256006706ce8d54dd985ce721c670c835e40a`;
the returned ledger SHA-256 is
`8eaba8f9809febcfed8e625d34c7514309c65ed1e85226d2121fa653c048bfec`.
The frozen identity cannot be retried or repaired under Decision 0021.
The [pilot 002 repair record](4b-pilot-002-draft.md) describes the official
competition mount and hardware diagnostic settings copied from earlier
successful notebooks. Its separate Decision 0022 push was rejected by the
provider; it does not alter pilot 001's terminal evidence.

## Verified versus open

- Latest local repair regression: boundary/TTT/DFS, two-rank CPU DDP with an
  unused visual branch, TRM inference-only harness and draft guards pass.
- Python 3.12 CPU tiny Qwen3.5 architecture, compact reload, masked loss,
  PEFT target attachment and reset pass with torch 2.12.1+cpu, Transformers
  5.8.1, PEFT 0.21.0 and Safetensors 0.8.0. Pinned 4B config ties embeddings;
  `ensure_weight_tying` was added to the LoRA adapter after this check.
- The one Kaggle push and retrieval are complete. The run passed exact material
  and dependency gates, then stopped at the hardware gate. **No 4B weights
  were loaded and no GPU training occurred.** Actual L4 availability and
  memory fit remain unverified; the output lacks hardware diagnostics.
