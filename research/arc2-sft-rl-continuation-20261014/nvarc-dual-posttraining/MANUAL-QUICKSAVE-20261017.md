# Manual save-only continuation and RTX compatibility

## Current boundary

The manual-start preparation is local only and does not overwrite, cancel,
restart or save any existing notebook. No new Dataset, notebook version or GPU
execution follows from this change. Operational deployment identities and
provider receipts are retained privately.

The reviewed runtime source remains commit
`0705dbad30a9e4381027049c4c6f5999d9a5a94a`. Source/payload transport hashes are
retained privately. Historical source identities and consumed clocks are not
rewritten.

## Save semantics and later manual start

The official Kaggle SDK exposes `KernelExecutionType.QUICK_SAVE`, distinct from
`SAVE_AND_RUN_ALL`. Current official CLI source uses that field for `--no-run`:
https://github.com/Kaggle/kaggle-api/blob/main/src/kaggle/api/kaggle_api_extended.py
The installed older CLI does not expose the flag, so ordinary `kernels push`
must not be used for save-only work. Any later save needs an explicit serialized
QUICK_SAVE request, exact current identity/settings reconciliation and a positive
provider version receipt. An uncertain write is not permission to resend.

`tools/nvarc_posttrain_20261017/manual.py` creates a later notebook source draft
without starting a clock, installing dependencies, executing a model or making
provider calls. It accepts only an unexecuted, byte-exact reviewed loader. The
model and source pins remain unchanged. Its first actual code execution:

1. Creates a distinct manual session identity and disjoint output/runtime roots.
2. Preserves the historical request clock as predecessor evidence.
3. Sets the new deadline from the current Linux Python kernel's process birth,
   including its idle time, rather than granting another 12 hours on cell rerun.
4. Exclusively creates and fsyncs a start receipt before the loader executes.
   An existing receipt, source directory, output or runtime blocks reuse.

This is not a durable provider-wide replay registry. A completely fresh provider
workspace cannot remember prior files. Provider allocation/queue start also is
not independently known from the Python kernel birth; the provider's own limit
remains authoritative. Do not describe this as resetting or resuming an old run,
or as proving the remaining provider time.

Six focused tests pass in both ML and minimal interpreters, normally and under
`-O`. Independent checks also confirmed one winner among 32 simultaneous claims,
no symlink receipt overwrite, rejection of existing runtime and valid Linux
process-age calculation. The current-checkout complete Linux public lane passed
1,984 tests in 171.86 seconds, with 1,762 passing and 222 explicit skips. This
is not native Windows execution or strict retained-evidence/Stage 4 acceptance.
The 19-test package/manual focused group also passed. No runtime capsule bytes
were changed by these local tests.

## Can it run on RTX PRO 6000 Blackwell?

**Yes in supported architecture and implementation; exact dual-model GPU
execution and throughput are still unverified.** The implementation uses the
pinned `torch 2.8.0+cu128`, `transformers 5.8.1` and `peft 0.21.0` stack.
Architecture support is not proof of an actual device allocation or successful
compact-model execution; those require separate runtime admission.

PyTorch's official Blackwell/CUDA 12.8 support announcement:
https://pytorch.org/blog/pytorch-2-7/
Official PyTorch 2.8 CUDA 12.8 distribution instructions:
https://pytorch.org/get-started/previous-versions/
NVIDIA RTX PRO 6000 Blackwell product specifications:
https://www.nvidia.com/content/dam/en-zz/Solutions/data-center/rtx-pro-6000-blackwell-workstation-edition/workstation-blackwell-rtx-pro-6000-workstation-edition-nvidia-us-3519208-web.pdf

The engine uses BF16 frozen weights, FP32 rank-64 rsLoRA/compact heads,
non-reentrant gradient checkpointing and standard PyTorch SDPA. No custom
FlashAttention, MXFP4 or hardware partitioning is required. The actual official
2B checkpoint loaded and solved 12 fresh tiny procedural examples through this
compact engine on CPU. That is a content/codec smoke, not an ARC score,
post-training gain, full-context test, or GPU validation.

Approximate lower-bound resident model/training state, including BF16 base,
FP32 trainables/gradients/Adam moments and one rollback copy:

- 2B worker: 3.93 GiB.
- 4B worker: 9.23 GiB.
- Two of each: 26.3 GiB, **before** activations, KV caches, CUDA contexts,
  temporary operations and allocator overhead.

These estimates cannot authorize four-way operation. Runtime probes require
exactly one actual CUDA device and record its name, capacity and CUDA capability.
The frozen source does not explicitly require a particular SKU or pre-check
native BF16 support; unsupported hardware therefore may fail during real probes.

The controller measures individual peaks, admits waves only under
`baseline + sum(1.2 * peak + 2 GiB) <= 0.8 * total`, then compares identical work
at concurrency 1, 2 and 4 with two paired repeats. Parallel operation needs at
least 5% measured full-wall speedup; four-way also must beat two-way. This is
shared-process scheduling, not MIG. Failed/OOM benchmark candidates are rejected
and a completed safe serial reference can win. A later training/inference OOM
is a recorded closed-worker failure, not silently resumed or called successful.

The original complete-denominator evaluation and inherited-exposure
qualification remain unchanged. No billing or hardware-eligibility conclusion
is made here.
