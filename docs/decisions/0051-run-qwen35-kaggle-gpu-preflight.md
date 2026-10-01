# Decision 0051: Execute the Qwen3.5 port GPU preflight on Kaggle

Status: Accepted
Date: 2026-10-01

The owner requests execution using the previous Kaggle notebooks/submission
transport and explicitly chooses the existing verified Qwen3.5 port for GPU
resource/backend checks. This supersedes Decision 0050's local-only boundary
for this distinct preflight; it does not authorize original Qwen3/NeMo claims
or the complete 12,716-step SFT run.

Run `nvarc-q35-gpu-preflight-001` privately on four distinct BF16 NVIDIA L4s,
Internet disabled and USD 0 paid cost, reusing the existing compact base and
offline-wheel Datasets. Use eight whole, fixed published original-corpus
training records. Preserve the prior successful four-L4 competition source
mount (`arc-prize-2026-arc-agi-2`) as transport only; open no competition files.
The records cover all six sources; four records exercise each heavy
source's longest compact sequence, up to 11,196 tokens. Retain both parents,
exposure and binding to the verified original corpus. There is no clean/fresh
evaluation, hidden answer read, teacher call or generation.

Permit exactly two full-parameter FSDP optimizer steps with the source AdamW
betas/epsilon/weight decay/clip and 12,716-step warmup/decay schedule, global
assistant-token loss normalization, FP32 parameter/optimizer state with BF16
compute, and a controlled checkpoint interruption/resume between steps.
Microbatch/global batch size and unpacked independent sequences are resource
probe settings, explicitly different from original Megatron packed SFT.
No sequence is truncated. Packing/attention-state isolation parity remains
unverified and cannot be promoted by this preflight.

Allow one new private save-and-run submission, bounded status checks of this
exact version through terminal state, and one terminal output retrieval.
Maximum notebook wall time is 2,700 seconds, with a finalization reserve;
at most 24 status checks with backoff. Reserve mutations/retrieval locally
before provider calls and retain exact package/plan/wire/receipt bindings.
Previous kernels and consumed run identities remain unchanged and unqueried.
No Dataset mutation, automatic runtime retry, paid execution or publication.

Checkpoint model/optimizer bytes are confined to bounded ephemeral scratch.
Retain checkpoint inventories, restore checks, per-rank losses/gradients,
memory/throughput/timing, lineage references and small terminal diagnostics;
do not publish training samples, weights, optimizer bytes or evaluator data.
Verify returned evidence locally. Failure is retained without relabeling it
as completed training or promotion. Necessary local tests/preflight and
credential refresh for the sole exact submission are included.

The sole private version 1 and terminal retrieval are now consumed. Four BF16
L4s completed one source-optimizer step on 4,186 whole input tokens and passed
the checkpoint restore fingerprint gate. The second long-sequence step failed
during backward, with cuBLAS allocation and NCCL watchdog errors retained.
The [terminal record](../../trials/arc-agi-2-qwen35-nvarc/q35-gpu-preflight-001.md)
binds the exact approved plan and all returned diagnostic members. No further
kernel, output retrieval, full SFT or promotion is authorized by this decision.
