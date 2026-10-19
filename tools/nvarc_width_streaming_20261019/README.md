# Bounded streaming width reconstruction prototype

This is CPU engineering evidence, not an admitted full-2B loader, a replacement
for `WidthEngine`, or evidence of capability/training gain. It adds no remote
operation and does not alter the existing width release or its admission gates.

## What changed

The existing path constructs a BF16 dense model, initializes the original
rsLoRA adapters, promotes the model to FP32, and then widens each FFN. The
unchanged widening implementation simultaneously holds old and expanded MLP
weights and several selected-row arithmetic tensors. Neither those code facts
nor the prior exit137 establish the exact killed allocation or prove an OOM.

`bridge.py` provides a separate reconstruction mechanism:

1. Build a native Qwen3 skeleton on meta.
2. Give each native Parameter its own two-byte, zero-stride BF16 placeholder.
   Guard every native submodule and copied saved head against forward execution.
3. Run the actual installed PEFT initializer in the original module traversal,
   with the original shapes and isolated adapter RNG seed. This retains even
   discarded Linear-initialization draws and BF16 adapter rounding; it is not a
   hand-coded RNG simulation.
4. Open one source tensor at a time, verify actual shape/device/dtype/contiguity,
   check finite values, and assign directly into its final FP32 shape. Source
   handles and views are released before the next tensor. No full dense native
   model is retained alongside the destination.
5. Preserve the existing paired antisymmetric up rows, copied gate rows and
   split down columns. Keep one complete int8 sign draw per layer; do not assume
   chunked RNG calls reproduce the same stream. Map original LoRA slices exactly
   and append the original BF16-valued down-A columns using the same generator.
6. Reconstruct BF16-rounded then FP32-promoted rotary buffers, install the
   unchanged FP32/math and nonreentrant checkpoint policies, reject remaining
   placeholders/shared storage, and only then remove construction guards.

The source reader is not a provenance authority. The official probe first uses
unchanged `verify_model` to verify every pinned source file, then selects one
layer. The builder reports that it has not independently established official
source identity and returns no `WidthEngine` admission.

## Hard safety limits

The builder has no override for these limits:

- At most 4 layers, hidden width at most 2048, and rank at most min(64, hidden).
  These checks precede config copying and shape inventory construction.
- At most 100,000,000 native source parameters.
- At most 512 MiB final parameter storage and 768 MiB known live-tensor allowance.
- Positive integer geometry, divisible GQA, exact complete BF16 source inventory,
  actual per-read shape checks, finite source and non-overflowing paired results.
- CPU only; original compact vocabulary, untied heads and full-attention SwiGLU.

The analytic memory helper permits up to 64 layers for planning, not execution.
The full official 28-layer model is rejected before source reads or model/PEFT
construction. Malformed giant layer counts are rejected before Python object
expansion. The byte plan is not an operating-system RSS bound.

## Final v4 evidence, 2026-10-19

Two sequential fresh processes used the same pinned official layer-0 weights,
compact embedding/head and final norm: 14 source tensors, 50,403,584 source
parameters. The expanded subset has 65,935,616 resident parameters, including
2,949,120 trainables. It is not the complete official model.

The streamed construction and unchanged widening reference agree bitwise on:

- All 30 native/adapter/compact-head Parameter tensors, before and after updates.
- Both rotary buffers.
- Every one of 16 trainable gradients and every updated tensor for two real
  CE/AdamW steps. The second step has all seven LoRA-A gradient tensors nonzero.
- Two actual MLP executions per update, proving backward checkpoint recomputation.
- All 2,048 added gate-B pairs have distinct paired gradients on both steps.
- Full and cached logits, MLP outputs and MLP input gradients, initially and
  after training, and after fresh reconstruction plus raw trainable reload.

The unchanged dense-to-width reference has maximum absolute differences:

| Quantity | Maximum difference |
| --- | ---: |
| Full logits | 1.6689300537109375e-6 |
| Cached logits | 1.1920928955078125e-6 |
| MLP output | 6.332993507385254e-8 |
| MLP input gradient | 1.0913936421275139e-11 |

These nonzero rounding differences are not claimed to be bitwise dense/width
function identity. The bitwise comparisons above are between the *two expanded
reconstructions*. The two optimization steps use synthetic token labels and
establish gradient/update mechanics, not useful task-learning gain.

### Memory measurement and its important limitation

| v4 measured quantity | Reference harness | Streamed harness |
| --- | ---: | ---: |
| Peak RSS recorded at the end of construction | 924,053,504 bytes | 641,232,896 bytes |
| Whole-process peak including updates/reload | 924,053,504 bytes | 666,243,072 bytes |

The construction-stage peak difference is 282,820,608 bytes **in this bounded
harness only**. The reference harness constructs FP32 then BF16, unlike the
production `from_pretrained(dtype=BF16)` loader. Its construction-stage record
also includes dense full/cached/MLP input-gradient probes, while the streamed
stage does not. Therefore this is not a fair isolated production-loader memory
benchmark, not a production memory-reduction percentage, and not evidence that
the previous full-model exit137 is diagnosed or fixed.

For the official full geometry, arithmetic planning gives:

- Final FP32 parameters: 7,370,412,032 bytes.
- Known extra tensor allowance: 42,516,480 bytes, including one 25,165,824-byte
  BF16 source window, 4,194,304-byte sign tensor, and operation-specific scratch.
- Final parameters plus that allowance: 7,412,928,512 bytes.

This is **not measured**, excludes Python/PyTorch/allocator/kernel/activation
costs and training/checkpoint buffers, and grants no full-model execution. It
cannot establish safe admission on the current host. Existing full-engine
checks, optimizer rollback, formal checkpoint loading, full-context operation,
GPU behavior and task effectiveness still require separate evidence.

### Source binding

The authoritative final evidence binds `bridge.py` SHA-256
`4f94edb932be3f010cad7f97395a63a196b2aee39ddb312f6661d20b9e2ffc48`
and `cpu_probe.py` SHA-256
`33d1a24485af87b1247d837570745726e0342f9b1fdb7097713b2ccff061e501`.
Earlier v1/v2/v3 artifacts remain unchanged, not retroactively rebound.
No weights, raw checkpoint/probe files, task data or private outputs belong in Git.

## Verification

`tests/test_nvarc_width_streaming.py` has 13 tests. All pass under ordinary Python
and `python -O` in the CPU environment (Torch 2.8.0+cpu, Transformers 5.8.1,
PEFT 0.21.0, safetensors 0.8.0). An independent read-only review repeated both
suites and checked the final v4 code hashes, both receipts and probe tensors.

The suite covers exact native/adapter/buffer state, cached/full forward and
input/trainable gradients, nonzero-B train-mode checkpoint recomputation,
file-backed reconstruction/reload, global RNG preservation, chunk-size
invariance, stale source manifests, overflow, placeholder direct-submodule
execution, geometry/byte caps and preflight ordering. Its raw-trainable reload
is explicitly **not** formal `WidthEngine` checkpoint admission.

Run tiny tests with the existing CPU interpreter:

```sh
PYTHONHASHSEED=0 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 OMP_NUM_THREADS=1 \
  ../fusion-cpu-venv/bin/python -m unittest tests.test_nvarc_width_streaming -v
PYTHONHASHSEED=0 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 OMP_NUM_THREADS=1 \
  ../fusion-cpu-venv/bin/python -O -m unittest tests.test_nvarc_width_streaming -v
```

The optional `cpu_probe` command requires an already materialized, hash-verified
local official source directory and a fresh output directory. Run reference and
streamed modes sequentially, never as concurrent larger allocations. It has a
180-second watchdog and always restricts the reconstructed model to one layer.
