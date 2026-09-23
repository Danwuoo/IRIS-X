# Proposed Qwen3.5-4B Kaggle compatibility pilot

Status: **materials inventoried; local package staged; not approved or launched**.
Owner selected a real 4B pilot preparation on 2026-09-23. This is one bounded
LoRA compatibility run, not full SFT, ARC evaluation, or a claim of NVARC
reproduction. It supersedes the tiny-only GPU A route for the next execution
choice. All older trial quotas and identities remain separate.
Implementation package: `1990872` on `main`, building on reservation repair
`9cd1839`, DDP repair `4267890` and TRM inference repair `f532885`.

## Exact materials and data

- Run identity: `nvarc-4b-compat-pilot-001`; proposed new private kernel
  `danielwuu/irisx-nvarc-4b-compat-pilot-001`. No prior execution uses it.
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
  torch/image bytes cannot be asserted before launch; the runner records torch
  and fails before model work if Python, exact installed offline packages, GPU
  model or capacity differ. This is an explicit remaining environment gate.

## One-run ceiling and stop

The proposed [machine-readable plan](configs/draft-4b-pilot.json) is
`approved: false`. One private Kaggle kernel push, at most one terminal output
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

## Prepared handoff

From the repository root, offline staging writes only under `.irisx/`:

```powershell
$env:PYTHONPATH = 'src'
python tools/stage_nvarc_4b_pilot.py
```

`stage-summary.json` records the draft plan, wheel, model/wheel manifests,
notebook and metadata SHA-256 values. The draft metadata ID starts
`DRAFT-DO-NOT-PUSH/`, and its first executable cell refuses unapproved input
before installing wheels or touching the GPU. The wheel includes the
`arc_nvarc_4b_pilot` runner. An owner-approved authorization file must bind
`approved: true`, `run_id`, the printed `draft_plan_sha256`, final `kernel_id`,
and a nonempty `owner_decision`. Then stage a **new** directory with
`--authorization <reviewed-json>` and review its new hashes. That command
builds the final notebook locally; it does not push. The deliberate launch
command, after authorization and preflight, is one
`kaggle kernels push -p <approved-stage>/kernel --accelerator NvidiaL4 --timeout 1800`.
Retrieve only the terminal output once, verify run ID, plan digest, ledger,
truth-free result and SHA-256, then stop. Failure consumes the identity and
does not authorize repair submission.

## Verified versus open

- Latest local repair regression: boundary/TTT/DFS, two-rank CPU DDP with an
  unused visual branch, TRM inference-only harness and draft guards pass.
- Python 3.12 CPU tiny Qwen3.5 architecture, compact reload, masked loss,
  PEFT target attachment and reset pass with torch 2.12.1+cpu, Transformers
  5.8.1, PEFT 0.21.0 and Safetensors 0.8.0. Pinned 4B config ties embeddings;
  `ensure_weight_tying` was added to the LoRA adapter after this check.
- **No 4B weights were loaded, no GPU training occurred, no Kaggle kernel was
  pushed, and no output was retrieved for this new identity.** Image/runtime
  version and L4 memory fit will be known only after the authorized pilot.
