# Qwen3.5-4B NVARC reproduction development

## M2–M3 local continuation (2026-09-25)

The [bounded M2–M3 record](m2-m3.md) covers public ARC train/dev freezing,
two-step full-parameter **tiny actual Qwen3.5** SFT with exact resume/export,
the new checkpoint's source TTT/DFS/ranking path, a real pinned TRM CPU
train/reload/TTT/inference and joint Qwen verification, plus ten-stage SDG
saved-response replay in a tested WSL namespace sandbox. Decision 0028
authorized one private 4B FSDP feasibility probe and one local Qwen3.5-4B
teacher smoke. The teacher kernel's sole version and retrieval are terminal:
Kaggle allocated two T4s, so its four-L4 gate stopped before any model call.
The compact Dataset is ready. The FSDP `001` kernel reached four L4s and loaded
the model, then timed out at a collective without an optimizer step. Decision
0029 authorizes one distinct bounded repair run, `002`, using the same Dataset.
Kaggle accepted `002` version 1; its first status was `RUNNING`, and monitoring
stopped at the owner's request pending their terminal notification. The owner
then reported its failure: all four ranks completed one 4B optimizer step, but
rank 0 could not serialize tuple fingerprints into the truth-free result.
Decision 0030 authorizes one new `003` run with the JSON-array repair; its
approved package passed local preflight. Kaggle accepted private `003` version
1; monitoring stopped after that receipt at the owner's request, with no
terminal result yet.
Full 4B ARC-SFT, a new 4B SFT checkpoint in TTT/search/rank, new teacher
output, and original-scale TRM remain open.

Status: **bounded synthetic 4B compact flow verified on one L4; full-method
acceptance remains partial**.
The [independent compact-flow analysis](control-review-e9048f8.md) accepts this
bounded engineering milestone after rehashing the model/result and rerunning
the repository and actual tiny-model tests. Candidate availability is 2/4,
not an accuracy result.
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

## Source integration checkpoint (2026-09-24)

**Local phases 1–3 accepted at `002f457`.** The
[independent repair review](control-review-002f457.md) passed the repository
and strict ML/source suites, rebuilt the actual source bundle offline, and
confirmed F1/F2 with independent dirty-source and no-network cache probes.
This accepts the documented source integration scope, not full-method execution.

The [independent source review](control-review-9198fd4.md) reran the repository
and strict ML/source profiles successfully at `9198fd4`, then reproduced two
source-tool defects. F1/F2 have since been repaired locally: readiness now
checks every Git index/worktree and executable addition, and materialization
reuses valid notebook cache or imports an exact local source bundle. The
[source integration record](source-integration.md) retains the offline rebuild
commands, regression evidence and remaining limits.

Owner-authorized local phases 1–3 now have a reconstructable pinned NVARC
source and public-notebook cache, a source-to-adapter map, upstream differential
tests and a shared fixture/tiny/4B stage configuration. The
[source integration record](source-integration.md) explains direct upstream use,
Qwen3.5 patches, test results and limits; the current
[reproduction matrix](reproduction-matrix.md) lists each component's artifact,
verification command and remaining gap. The source cache is ignored, and
`tools/nvarc_source.py verify` performs an offline identity check.

The source-profile fixture and tiny actual-Qwen3.5 CPU paths passed. The 4B
source profile, real ARC-SFT, SDG teacher, TRM model path and joint scoring have
not run. Kaggle, external execution and paid work remain outside this local
authorization. Historical pilot identities and their evidence remain frozen.

## Compact 4B vertical pilot (2026-09-24)

The distinct `nvarc-4b-compact-complete-001` flow was staged locally, then
authorized by Decision 0026. Its [one accepted private Kaggle version and one
terminal retrieval](compact-complete-001.md) are consumed. The version failed
before model loading because the Dataset v2 mount's root filenames did not
equal the pinned model and wheel inventory. It produced no compact artifact,
training steps, or generations.
Decision 0027 authorizes distinct free kernels in this session for program-error
repairs. [Version 002](compact-complete-002.md) passed that inventory gate and
saved compact weights, then failed because the grid tokenizer serializer used
a tuple where canonical JSON requires a list. Its large-file retrieval broke
mid-transfer, so no model artifact was verified locally. The serializer and
retrieval sharding repairs were applied in [version 003](compact-complete-003.md).
That version completed compact conversion and reload, two short task-local
LoRA steps, four generation calls, complete grids for two of four synthetic
tests, truth-free result packaging, and independent local material/result
verification. The other two tests are marked missing. Decision 0027's
session-specific kernel authority ends with this verified flow.
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
scoring. This checks the pipeline, not ARC quality. Pilot 003 separately
verified the real 4B compact artifact, bounded phase memory observations and
GPU result; full-method resource requirements remain unverified. The exact draft limits,
stage commands and executed boundary are in the [runbook](runbook.md) and
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
| materials-ready | Partial: Dataset v2 has pinned 4B base weights and offline wheels; compact pilot 003's distinct four-shard model is retained and locally verified. ARC-SFT weights, full training data and TRM weights remain absent |
| runtime-verified | Partial: compact pilot 003 verified one-L4 4B conversion/reload, two synthetic task-local LoRA steps, four generations, two tests with complete grids, truth-free result and local material verification; four-worker execution and ARC task quality remain untested |
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
16 tokens. These earlier compatibility pilots made no model generations.
The separate compact-complete-003 flow made four generations and two synthetic
adaptation steps using 20 tokens. Neither line performed ARC training or
scoring, SDG teacher calls, Codex proposer calls, competition submissions, or
paid usage.
