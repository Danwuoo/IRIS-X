# Decision 0052: Repair and upload the second Qwen3.5 GPU preflight

Status: Accepted
Date: 2026-10-01

The owner explicitly directs continued repair and uploading the second version
after Decision 0051's partial GPU result. Continue the previously requested
save-and-run workflow under distinct immutable identity
`nvarc-q35-gpu-preflight-002`, preserving 001's package, receipt and failure.
One private submission, bounded monitoring to terminal and one terminal
diagnostic retrieval are authorized; no Dataset mutation or automatic further
kernel follows. USD 0, four distinct BF16 L4s, Internet disabled, existing
compact base/wheel Datasets and the prior official competition mount remain.
Open no competition files, evaluator truth or hidden scoring material.

Keep the exact eight whole original-corpus records, all six sources, 47,078
input tokens, maximum sequence length 11,196, original lineage/exposure,
two full-parameter steps, source optimizer/loss/schedule and controlled
checkpoint restart. No truncation, packing, generation, teacher invocation,
scoring, full SFT or original Qwen3/NeMo equivalence claim is authorized.

Repair backend resource handling with supported FSDP CPU parameter/gradient
offload and FP32 CPU AdamW state, explicit non-foreach optimizer execution,
non-reentrant per-layer activation checkpointing, no backward prefetch, and
separate CPU Gloo control/checkpoint synchronization from NCCL model
collectives. Preserve BF16 GPU compute and FP32 parameter/optimizer precision.
Record rank memory/device residency and exact phase failure before exit.
Keep monitoring/watchdog enabled; CPU control timeout 600 seconds, NCCL
collective timeout 180 seconds and heartbeat 120 seconds are bound. These are
engineering port choices, not the original Megatron training backend.

Maximum notebook wall time remains 2,700 seconds with a 120-second finalization
reserve. At most 24 backed-off status requests of this new identity and one
terminal retrieval are permitted. Reserve them atomically before provider
calls, refresh credentials before the sole mutation and keep retries disabled.
Retain the exact plan/wheel/notebook/request/receipt and returned digests.
Checkpoint bytes and sample tokens stay in ephemeral scratch; retain only
bounded diagnostics and checkpoint inventories. Local offline verification
must precede submission, and failure must remain a failure without promotion.

## Consumed outcome

The sole private `SAVE_AND_RUN_ALL` was accepted as version 1. Nine backed-off
status requests observed `COMPLETE`; one terminal output listing and one
bounded archive download are consumed. Offline closed-inventory verification
passed all 29 data-member digests, exact saved plan/runtime bindings and four
distinct BF16 L4 worker envelopes. Both full-parameter steps and controlled
checkpoint resume completed over 47,078 input tokens (maximum 11,196), with
CPU FP32 state and 32 activation-checkpointed layers. Retained archive SHA-256
is `d06408cf34aca7d4247ed2c18bcd84b45ad6a9c370fd63aad89a62c458bb80b5`.

This resource probe is terminal. Checkpoint bytes remained ephemeral; no full
SFT, original Qwen3/NeMo parity, packing, teacher, generation, scoring or further
execution is implied. Exact receipt, metrics and evidence bindings are in
[the terminal record](../../trials/arc-agi-2-qwen35-nvarc/q35-gpu-preflight-002.md).
