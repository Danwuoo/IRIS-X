# Decision 0029: One bounded repair of the NVARC M2 FSDP probe

Status: Accepted
Date: 2026-09-25

## Context

The owner explicitly said, 「執行 failed，授權修復重跑」 after the Decision 0028
FSDP version 1 ended in `KernelWorkerStatus.ERROR`. Its hardware gate verified
four distinct L4 GPUs, and all four ranks loaded the pinned compact Qwen3.5-4B.
No optimizer step or result was produced. Three ranks timed out at an NCCL
one-element all-reduce after 600 seconds; the log cannot establish which phase
held rank 0. The original notebook had no durable per-rank phase diagnostics.
The existing private model Dataset is ready and verified; it need not change.

## Decision

Authorize exactly one replacement private Kaggle kernel under the immutable
identity `nvarc-m2-fsdp-feasibility-002`, using the existing private compact
Dataset and pinned source sequences. Repair the runtime gradient/weight checks
to aggregate device predicates before host synchronization. Retain per-rank
phase and stack diagnostics so a second failure can be located. The kernel may
perform one unpacked BF16 full-parameter FSDP optimizer step across exactly
four distinct L4 GPUs, at most 128 input tokens per rank and 512 total, no
generations or teacher calls, at most 1,800 seconds, and USD 0 paid cost.
Authorize one kernel push, bounded status checks and one terminal output
retrieval. Keep the kernel private and Internet-disabled. Do not mutate the
model Dataset or re-use the `001` kernel identity.

If the replacement fails, preserve its terminal evidence. This decision does
not authorize a third attempt, ARC scoring, checkpoint promotion, paid compute,
publication or competition submission. The one-step result, if successful,
establishes only backend feasibility, not completion of 4B ARC-SFT.
