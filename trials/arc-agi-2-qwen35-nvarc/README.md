# Qwen3.5-4B NVARC reproduction development

Status: **reviewed local P1 repairs implemented; CPU tiny Qwen3.5/PEFT verified;
4B pilot prepared but not approved or launched; acceptance still partial**.
The [second control review](control-review-4d23546.md) independently confirms
the earlier example repairs and identified TTT/DFS reservation binding,
unused-parameter DDP and TRM evaluation-entry blockers at `4d23546`. Its
subsequent disposition records the local fixes.
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

The continuation repaired the original three reviewed P1 boundaries and the
second review's reservation, DDP and TRM entry blockers, made DFS iterative,
and exercised a two-rank CPU Gloo DDP worker with pause, resume, and worker
failure. SDG stage accounting, a Docker launcher, a TRM invocation wrapper,
truth-free raw-tensor normalizer and strict optional ML profile were added.
The Docker daemon remains absent. A separate Python 3.12 environment now runs
tiny actual Qwen3.5/PEFT tests on CPU. The owner chose preparation of a real
4B pilot; its [exact proposed package](4b-pilot.md) is staged locally and
unapproved. No Kaggle kernel was launched or result retrieved for this identity.

The offline fixture E2E runs a **tiny random transition model for gradient and
resume checks**, then explicitly marked fixture predictions through candidate,
result and sealed-scoring paths. Its 2/3 pass@2 is synthetic test behavior,
not an ARC accuracy claim. The real 4B, TRM, and SDG teacher paths have not
been executed. The additional real PyTorch synthetic resume test skips under
default Python 3.14 but passes with the installed Python 3.12 and torch. Tiny
actual Qwen3.5/PEFT passes in the separate optional CPU environment; 4B GPU
compatibility remains unverified.
Source-level differences and remaining gaps are in
[`reproduction-matrix.md`](reproduction-matrix.md).

## Current evidence states

| State | Current value |
| --- | --- |
| implementation-verified | Partial: both reviews' local P1 and DFS defects repaired; CPU collective, unused-branch, TRM entry and tiny actual Qwen3.5/PEFT pass; sandbox, upstream TRM and 4B GPU gates remain |
| materials-ready | Partial: the existing private Kaggle Dataset v2 has pinned 4B base weights and offline wheels, now inventoried and digest-bound. The pilot uses synthetic data. Compact/ARC-SFT weights, full training data and TRM weights remain absent |
| runtime-verified | No for this new identity; the four-L4 success belongs only to the earlier trials |
| sft-trained | No |
| full-method-measured | No |

The [source-use](source-use.md), [runbook](runbook.md),
[4B pilot](4b-pilot.md), and [execution proposal](execution-proposal.md) bind
the next steps. A specific owner launch authorization is still required. The
present draft manifest is not an approval token.

No new real Qwen/TRM generations or training steps, SDG teacher calls, Codex proposer
calls, Kaggle mutation/retrieval, competition submission, or paid usage occurred
in this development task.
