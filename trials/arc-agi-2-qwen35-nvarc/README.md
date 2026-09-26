# Qwen3.5-4B NVARC reproduction development

## Current continuation (2026-09-26)

The owner has now authorized [one combined notebook submission](combined-notebook-001-submission.md)
under [Decision 0035](../../docs/decisions/0035-submit-nvarc-combined-two-gpu-notebook.md),
reusing the existing Datasets and unchanged M2/M3 workloads on two selected
L4 GPUs. Submission preparation is in progress; stop at the receipt without
monitoring or retrieval. The original inert draft remains preserved.

The owner's [combined two-GPU development plan](../../docs/plan/2026-09-26-nvarc-combined-two-gpu-notebook.md)
now has a distinct [inert notebook implementation and local verification record](combined-notebook-001.md).
It stages M2 and M3 as isolated workers with shared setup, separate budgets,
bounded readiness/supervision and independently checked partial outcomes.
Cached installed-wheel CPU and WSL probes use tiny real Qwen and saved
teacher-response replay; no new 4B work or teacher calls occurred. The draft
has zero external allowances and rejects live execution. Two-L4 resource fit,
GPU UUID mapping and Kaggle image acceptance remain pending. Decision 0034's
submitted versions remain unqueried and their identities stay frozen.

Decision 0032's two kernels and terminal retrievals are consumed. The
[terminal record](m2-m3-decision-0032-terminal.md) confirms M2's eight-step,
2,578-token SFT and verified HF export; source TTT failed on absent packaged
source before its update. M3 completed four teacher calls, but all replies
hit the output ceiling and no accepted SDG pairs exist. Full-method acceptance
and ARC quality remain unestablished.

The owner requested development directly on main after confirming the NVARC
worktree was already merged. The [local continuation plan](../../docs/plan/2026-09-26-nvarc-source-teacher-continuation.md)
adds a portable source bundle, an export-only M2 continuation, complete-stage
teacher validation and retained SDG data artifacts. New M2 `source-cont-001`
and M3 `teacher-small-004` were prepared as inert proposals. The owner's
subsequent Kaggle execution instruction is now recorded in
[Decision 0033](../../docs/decisions/0033-authorize-nvarc-source-and-direct-teacher.md),
which permits their bounded private execution and artifact verification.
The [execution record](m2-m3-decision-0033.md) retains the verified export
Dataset upload and both accepted version-1 receipts. The owner subsequently
paused monitoring and reported stopping both sessions.
[Decision 0034](../../docs/decisions/0034-restart-nvarc-without-monitoring.md)
authorizes one restart each as M2 `source-cont-002` and M3 `teacher-small-005`,
using the same workload and existing Datasets. The new
[execution record](m2-m3-decision-0034.md) retains their exact bindings.
Stop after submission receipts; monitoring and retrieval are not authorized.
The earlier dated sections below retain their historical observations
and are superseded by this section.

## M2–M3 local continuation (2026-09-25)

**Stages 4–5 remain incomplete.** Decision 0031's two private,
Internet-disabled version 1 kernels have now ended and their single terminal
outputs were retrieved. M2 stopped before model work because Kaggle supplied
20.94 GB free `/kaggle/working` space against the package's 60 GB checkpoint
gate. M3 passed its four-L4 gate but failed its first teacher stage with an
`AttributeError`: zero completed calls and zero responses. Neither identity
has a retry allowance. The
[independent review](control-review-0b7002a.md) accepted the four-L4 4B
optimizer-step milestone and found a WSL sandbox chroot escape plus a joint
verifier profile mismatch. Both are now repaired with actual namespace and
tiny-Qwen regressions. A two-rank tiny Qwen FSDP run also proves sharded
checkpoint resume, optimizer/RNG/cursor restoration, deterministic HF
export/reload and source TTT/search/rank from that export. The 4B SFT
checkpoint chain and real teacher batch have **not been obtained**. The
[bounded continuation plan](../../docs/plan/2026-09-25-nvarc-m2-m3-checkpoint-continuation.md),
[Decision 0031](../../docs/decisions/0031-authorize-nvarc-m2-m3-checkpoint-continuation.md)
and [M2/M3 record](m2-m3.md) bind the exact approved packages and limits.

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
terminal result at that handoff. After the owner reported completion, the
single terminal retrieval and independent verifier confirmed one real
full-parameter compact 4B step on four distinct L4s: 240 input tokens,
finite gradients and changed weights. The truth-free result SHA-256 is
`4624b1c4e4c4079d7daf6d0e958d74a0fd4fe5ebe1d1559a9a7faf28b5ef28ba`.
The Decision 0030 push and retrieval are consumed.
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

## Earlier evidence states (before Decision 0032 terminal retrieval)

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
