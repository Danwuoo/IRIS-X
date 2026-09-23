# Qwen3.5-4B NVARC reproduction development

Status: **reviewed local P1 repairs implemented; pilot 004 verified a bounded
synthetic Qwen3.5-4B LoRA path on one L4; full-method acceptance remains partial**.
The [2026-09-24 independent review](control-review-811bd4b.md) verifies the
retained pilot evidence and local ML tests, and records the remaining shipped
configuration mismatch, numerical-check gap and full-method integration gates.
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

## Compact 4B vertical pilot development (2026-09-24)

The distinct `nvarc-4b-compact-complete-001` flow is now staged **locally as an
unapproved draft**; it has not launched a Kaggle kernel or retrieved output.
The checked-in candidate `method` now passes the same binding/outbound verifier
used by the runner, while unknown fields still fail closed. Task-local LoRA
checks finite loss, every trainable gradient and updated adapter tensors at
each step; failures reset the adapter and leave a bounded failure observation.
Compact conversion selects only the 16 pinned source rows before resize and
releases the source model before reload. Bounded DFS now prevents empty or
newline-only completions from consuming the candidate sequence ceiling and
shares calls across multiple tests.

The strict CPU ML environment ran a tiny **real Qwen3.5** two-task/four-test
flow through conversion, reload, PEFT adaptation, model DFS generation,
likelihood verification, checkpoint/result ZIP and separate sealed synthetic
scoring. This checks the pipeline, not ARC quality. The 4B compact artifact,
its VRAM/RAM cost and GPU result remain **unverified**. The exact draft limits,
stage commands and owner review gate are in the [runbook](runbook.md) and
[development plan](../../docs/plan/2026-09-24-qwen35-compact-complete-pilot.md).

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
- Static private Kaggle staging and a draft kernel notebook. Preparation itself
  made no Dataset/kernel mutation; Decision 0021 later authorized one push.

The continuation repaired the original three reviewed P1 boundaries and the
second review's reservation, DDP and TRM entry blockers, made DFS iterative,
and exercised a two-rank CPU Gloo DDP worker with pause, resume, and worker
failure. SDG stage accounting, a Docker launcher, a TRM invocation wrapper,
truth-free raw-tensor normalizer and strict optional ML profile were added.
The Docker daemon remains absent. A separate Python 3.12 environment now runs
tiny actual Qwen3.5/PEFT tests on CPU. Decision 0021's bounded
[4B pilot](4b-pilot.md) was pushed once and retrieved once. Kaggle marked the
kernel `COMPLETE`, while the application failed its L4 hardware gate before
loading model weights or training. Both external allowances are consumed.

The offline fixture E2E runs a **tiny random transition model for gradient and
resume checks**, then explicitly marked fixture predictions through candidate,
result and sealed-scoring paths. Its 2/3 pass@2 is synthetic test behavior,
not an ARC accuracy claim. Full ARC 4B training, TRM, and SDG teacher paths
have not been executed. The additional real PyTorch synthetic resume test skips under
default Python 3.14 but passes with the installed Python 3.12 and torch. Tiny
actual Qwen3.5/PEFT passes in the separate optional CPU environment; pilot 004
separately verifies bounded 4B LoRA gradients and reset on one L4.
Source-level differences and remaining gaps are in
[`reproduction-matrix.md`](reproduction-matrix.md).

## Current evidence states

| State | Current value |
| --- | --- |
| implementation-verified | Partial: both reviews' local P1 and DFS defects repaired; CPU collective, unused-branch, TRM entry, tiny actual Qwen3.5/PEFT and bounded 4B GPU LoRA pilot pass; sandbox, upstream TRM and full-method GPU gates remain |
| materials-ready | Partial: the existing private Kaggle Dataset v2 has pinned 4B base weights and offline wheels, now inventoried and digest-bound. The pilot uses synthetic data. Compact/ARC-SFT weights, full training data and TRM weights remain absent |
| runtime-verified | Partial: pilot 004 verified one L4 Qwen3.5-4B load, two synthetic LoRA steps, four expected gradient groups, adapter reset and 9,419 MiB peak allocation; four GPUs were visible but no four-worker or ARC task execution was tested |
| sft-trained | No |
| full-method-measured | No |

The [source-use](source-use.md), [runbook](runbook.md),
[4B pilot](4b-pilot.md), and [execution proposal](execution-proposal.md) retain
the preparation and terminal evidence. Decision 0021's one launch and
retrieval are consumed; a new external attempt requires new owner direction.
The retained draft manifest is not an approval token.
The [pilot 002 package](4b-pilot-002-draft.md) corrected the missing official
competition mount and added early hardware diagnostics locally. Decision 0022's
single push was rejected by Kaggle HTTP 400 before a version receipt. Its
authority is consumed; pilot 001 stays frozen.
The owner then authorized retry of that pre-version rejection. Decision 0023's
separate [pilot 003 attempt](4b-pilot-003.md) with a shorter title/slug was
accepted. It verified the official mount and four L4s, then failed on the
preinstalled `torchao 0.10.0`/PEFT 0.21.0 incompatibility before model load.
That execution and its retrieval attempt are consumed.
The [pilot 004 draft](4b-pilot-004-draft.md) contains a bounded offline
dependency repair. Decision 0024 authorizes one separate Kaggle push and
terminal retrieval. Its first request received HTTP 401 from an expired local
OAuth token before version creation. Decision 0025 authorizes one exact-package
transport retry after refreshing that credential. That retry was accepted as
version 1, completed two synthetic 4B LoRA steps and was retrieved and
verified once. Both decisions are consumed.

Pilot 001 made one private Kaggle kernel push and one terminal retrieval.
Pilot 002's one push request was rejected before a version receipt, with no
retrieval. Pilot 003 made one accepted push and one partial terminal retrieval
attempt. Pilot 004 made one HTTP 401 request and one accepted retry, followed
by one full terminal retrieval. It completed two synthetic 4B LoRA steps with
16 tokens. No pilot made model generations, ARC training or scoring, SDG
teacher calls, Codex proposer calls, competition submissions, or paid usage.
