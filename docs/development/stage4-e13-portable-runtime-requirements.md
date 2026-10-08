# E13 portable runtime: requirements only

No GCP resources, software, login grants, transfers or runs have been created.
This is a migration checklist for the same four-task/six-test experiment after
its instrumentation repair. It does not authorize a new model or broader panel.

## Information needed from the owner

- Exact existing machine or approved project, region/zone and environment route;
  whether it is already running, and who pays for it.
- GPU count/model/VRAM, host RAM, available disk, Linux/Python/CUDA driver details,
  accessible working directory and transfer mechanism.
- Explicit allowed duration and total cost ceiling, including idle time, disk and
  any transfers; a stop/shutdown policy and any data-location restrictions.
- Permission to transfer this specific truth-free code/material package and model
  to that destination, and to perform any necessary setup. New credentials or
  security-sensitive permissions require their separate supported approval flow.

## Existing reference contract

- Exactly four visible NVIDIA L4 devices, one resident model and worker per GPU.
  A different GPU layout needs an explicitly reviewed hardware/runtime profile.
  Both search budgets still run on identical hardware within a paired experiment.
- Pinned Qwen3-4B grid SFT139 BF16 material:
  `sorokin/qwen3_4b_grids15_sft139/transformers/bfloat16/1`, material digest
  `27de51ef22658a0cce3a9fc04fac8fc456165645e2665a82b215f72e20194b03`.
- Original source/dependency provenance from notebook
  `sorokin/pip-install-unsloth-flash-patch/2`, script version 272622465;
  Torch 2.8.0+cu128 and the original pinned native training stack. Preserve the
  selected-byte readproof and offline installation order; do not substitute a
  fresh dependency resolver or newer packages.
- Current guards permit at most 16 GiB worker host RSS and 64 GiB summed worker
  RSS; the host also needs coordinator, operating-system and filesystem headroom.
  These are process limits, not a claim that a 64 GiB VM is sufficient.
- Provide space for pinned model/dependency material, temporary compilation caches
  and separately bounded evidence. Inventory actual bytes before provisioning;
  no model weights, secrets or evaluator truth belong in the result archive.

## Required engineering changes before a GCP launch

- Replace Kaggle-only input mounts and working-path discovery with exact local
  paths and immutable digest checks. Do not weaken material provenance gates.
- Replace Kaggle quota/admission transport with an approved environment-specific
  cost/time admission receipt. A Kaggle authorization cannot admit a GCP run.
- Verify driver compatibility, the ptxas executable path, four distinct GPU UUIDs,
  offline source imports, memory headroom and child-process ownership/cleanup.
- Keep native execution offline and gold isolated. Retain one TTT128 state per
  task, restored RNG, counterbalanced arms, 120/240-second windows plus 30-second
  reserves, all scientific caps, and the repaired bounded instrumentation.
- Repeat CPU packaging/negative tests, independent exact-package review, a checked
  stop/finalization path and bounded result export before any authorized GPU work.

An existing GCP machine could avoid the remaining Kaggle quota bottleneck, but
its availability, cost, compatibility and transfer permission are unverified.
No installation, setup, new cloud resources or execution follows from this note.
