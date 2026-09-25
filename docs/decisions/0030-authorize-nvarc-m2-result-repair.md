# Decision 0030: One result-packaging repair of the NVARC M2 FSDP probe

Status: Accepted
Date: 2026-09-25

## Context

The owner explicitly said, 「執行 failed，授權修復重跑」 after the Decision 0029
replacement version 1 ended `KernelWorkerStatus.ERROR`. Its retained per-rank
diagnostics show four distinct L4s and all four ranks completing forward,
backward, nonzero finite gradient checks, clipping, an AdamW optimizer step,
finite updated-weight checks, and fingerprint all-reduce. Rank 0 then failed
while writing the truth-free result: the canonical JSON serializer rejects
Python tuples in `weight_fingerprint_before` and `weight_fingerprint_after`.
The other ranks waited at the final barrier and timed out. There is no result
artifact or exported SFT checkpoint from that attempt. The private model
Dataset and frozen public ARC training sequences remain unchanged.

## Decision

Authorize exactly one new private Kaggle kernel under immutable identity
`nvarc-m2-fsdp-feasibility-003`, with the sole repair converting the two
numerical fingerprint tuples to canonical JSON arrays and testing that output
shape. Reuse the existing private compact model Dataset. Keep the four distinct
L4 gate, Internet-disabled transport, unpacked BF16 full-parameter FSDP,
one optimizer step, at most 128 input tokens per rank/512 total, zero
generations and teacher calls, at most 1,800 seconds, and USD 0 paid cost.
Authorize one kernel push, a single terminal status check when the owner calls,
and one terminal output retrieval. Preserve the `001` and `002` identities
and evidence. Do not automatically retry after `003` or infer a completed
4B ARC-SFT checkpoint from this one-step feasibility observation.
