# Qwen3.5-4B NVARC reproduction development

Status: **local continuation implemented; acceptance still partial; no execution authority**.
The [control review](control-review.md) found reproducible outbound, result,
model-material and DFS defects at `e7d74a6`. The
[continuation plan](../../docs/plan/2026-09-23-qwen35-nvarc-acceptance-continuation.md)
returns repairs and remaining implementation to the existing task on main.
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
  LoRA with adapter/optimizer/RNG reset, bounded score-pruned DFS with isolated
  prefix state, multi-view generation, complete-grid
  gating, inverse transforms, deduplication, Qwen likelihood verification and
  deterministic top two.
- Separate TRM training-data conversion and pinned launch specification,
  candidate normalization, and joint Qwen verification interface.
- Truth-free workload/result ZIPs, task-boundary call reservations, four-L4
  hardware/source gate, persistent worker dispatch, parent-enforced deadline,
  and evaluator-only full-task multi-test pass@1/pass@2.
- Static private Kaggle staging and a draft kernel notebook. No Dataset/kernel
  mutation was made.

The continuation repaired the three reviewed P1 boundaries, made DFS iterative,
and exercised a two-rank CPU Gloo DDP worker with pause, resume, and worker
failure. SDG stage accounting, a Docker launcher, a TRM invocation wrapper,
truth-free raw-tensor normalizer and strict optional ML profile were added.
The Docker daemon and the optional
Qwen3.5/PEFT packages are absent, so those integrations remain unverified.

The offline fixture E2E runs a **tiny random transition model for gradient and
resume checks**, then explicitly marked fixture predictions through candidate,
result and sealed-scoring paths. Its 2/3 pass@2 is synthetic test behavior,
not an ARC accuracy claim. The real 4B, TRM, and SDG teacher paths have not
been executed. The additional real PyTorch synthetic resume test skips under
default Python 3.14 but passed during control review with the installed Python
3.12 and torch. Qwen3.5/PEFT compatibility remains unverified.
Source-level differences and remaining gaps are in
[`reproduction-matrix.md`](reproduction-matrix.md).

## Current evidence states

| State | Current value |
| --- | --- |
| implementation-verified | Partial: reviewed P1 and DFS defects repaired; CPU collective and adapter fixtures pass; architecture, sandbox, upstream TRM and GPU gates remain |
| materials-ready | No: this worktree has pinned small sources/configs, but no compact or ARC-SFT Qwen3.5 weights, frozen full training data, or TRM weights |
| runtime-verified | No for this new identity; the four-L4 success belongs only to the earlier trials |
| sft-trained | No |
| full-method-measured | No |

The [source-use](source-use.md), [runbook](runbook.md), and
[execution proposal](execution-proposal.md) bind the next steps. A new owner
authorization with exact materials, limits and retention is needed for each
real workload. The present draft manifests are not approval tokens.

No new real Qwen/TRM generations or training steps, SDG teacher calls, Codex proposer
calls, Kaggle mutation/retrieval, competition submission, or paid usage occurred
in this development task.
