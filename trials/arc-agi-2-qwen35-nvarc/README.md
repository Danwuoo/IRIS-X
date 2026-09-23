# Qwen3.5-4B NVARC reproduction development

Status: **implementation-verified on synthetic CPU fixtures; development-authorized-no-execution**.
Owner direction and boundaries are in
[`docs/plan/2026-09-23-qwen35-nvarc-reproduction.md`](../../docs/plan/2026-09-23-qwen35-nvarc-reproduction.md).
This workspace is distinct from Trial 001, Trial 002, prompt pilot, and budget
ablation. None of their exhausted ceilings or frozen identities is reused.

## What was built

- Deterministic labelled-data import, parent and known-transform split checks,
  freeze manifests, reversible D4/color/demo augmentation, and saved-response
  SDG replay. Untrusted generated Python fails closed without an attested sandbox.
- A 16-symbol grid grammar with explicit role/end tokens; immutable Qwen3.5
  embedding/head conversion, reload and material digests. Original Qwen3 token
  IDs and weights are never assumed compatible.
- Unpacked full-SFT gradient/checkpoint/export path, task-local leave-one-out
  LoRA with adapter/optimizer/RNG reset, multi-view generation, complete-grid
  gating, inverse transforms, deduplication, Qwen likelihood verification and
  deterministic top two.
- Separate TRM training-data conversion and pinned launch specification,
  candidate normalization, and joint Qwen verification interface.
- Truth-free workload/result ZIPs, task-boundary call reservations, four-L4
  hardware/source gate, persistent worker dispatch, parent-enforced deadline,
  and evaluator-only full-task multi-test pass@1/pass@2.
- Static private Kaggle staging and a draft kernel notebook. No Dataset/kernel
  mutation was made.

The offline fixture E2E runs a **tiny random transition model for gradient and
resume checks**, then explicitly marked fixture predictions through candidate,
result and sealed-scoring paths. Its 2/3 pass@2 is synthetic test behavior,
not an ARC accuracy claim. The real 4B, TRM, and SDG teacher paths have not
been executed. Source-level differences and remaining gaps are in
[`reproduction-matrix.md`](reproduction-matrix.md).

## Current evidence states

| State | Current value |
| --- | --- |
| implementation-verified | Yes, for the offline modules and synthetic fixture cases listed in the runbook |
| materials-ready | No: this worktree has pinned small sources/configs, but no compact or ARC-SFT Qwen3.5 weights, frozen full training data, or TRM weights |
| runtime-verified | No for this new identity; the four-L4 success belongs only to the earlier trials |
| sft-trained | No |
| full-method-measured | No |

The [source-use](source-use.md), [runbook](runbook.md), and
[execution proposal](execution-proposal.md) bind the next steps. A new owner
authorization with exact materials, limits and retention is needed for each
real workload. The present draft manifests are not approval tokens.

No new real Qwen/TRM generations, SGD steps, SDG teacher calls, Codex proposer
calls, Kaggle mutation/retrieval, competition submission, or paid usage occurred
in this development task.
