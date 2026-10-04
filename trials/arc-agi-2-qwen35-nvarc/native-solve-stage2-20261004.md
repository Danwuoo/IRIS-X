# Native solver engineering, stage 2 (2026-10-04)

Baseline: clean local `main` at `a1f68d2981c820e0256cf551c47a8b31894df1a1`.
Delivery commit: resolve with `git log -1 --format=%H -- trials/arc-agi-2-qwen35-nvarc/native-solve-stage2-20261004.md`.
The delegated scope is local implementation, CPU verification and inert packaging.
No Kaggle save/push/run/status/log/output/retrieval, Dataset mutation, GPU run,
teacher call, scoring, publication, competition submission, git push, new chat,
automation or new execution admission occurred.

## Executable path and evidence boundary

`nvarc_native_multitask.py` connects task-local native TTT to every real test
index. A fresh process loads the published original checkpoint and creates a
fresh rank-256 adapter, Trainer, optimizer and scheduler for each task. The
task shares one complete epoch across its tests. Native preparation compares
actual tokenizer/collator rows against task-derived references; reference texts
contain only public demonstrations. There is no full SFT prerequisite.

The source cells, formatter, 16-symbol representation, sixteen generation
views, four-view batches, EOS limit 931, cumulative `-log(0.2)` DFS threshold,
inverse, deduplication, eight verification views and `score_kgmon` remain exact.
All tests are augmented jointly before selecting a real index, preserving the
original RNG stream. The new sequential schedule finishes a test's four batches
before the next test; upstream interleaves the first/last batch pairs across
tests. Finite engineering deadlines and this ordering are explicit differences,
not a full original method or historical-clock parity claim.

Fsynced event chains bind run/plan/producer/challenge/task/test and reserve model
entries before calls. Actual verifier token log probabilities and generation
last logits/clocks are retained. Each test checkpoint commits before the next
test. OOM, timeout, interrupts, worker failures, planned limits, empty output and
undispatched items retain the full denominator. The parent's finalizer can
export earlier committed tests after an interrupt or worker failure. An abrupt
parent/provider kill can prevent ZIP finalization; neither reset nor a terminal
ZIP is inferred in that case.

`nvarc_native_submission.py` is the strict bridge into `arc_kaggle_submission`.
It checks exact producer bytes, source input/inverse bindings, native hardware
and published-material envelopes, complete task TTT, and event order. It replays
the original DFS without a model against retained logits/clocks, recounts
EOS-inclusive verifier NLLs, and recomputes duplicate votes and rank order.
Changed bindings, stale runs, duplicate tasks/tests, unknown/evaluator fields,
altered source generation, inverse or ranking fail closed. Hashes identify
retained bytes; they are not an execution attestation. The generic records
exporter remains a generic exporter; its grids do not establish native evidence.

Every challenge test has two attempt slots. A single ranked candidate can be
native-complete but still lacks a second model attempt; the second slot is
explicit duplicate filler. Zero candidates use the existing constant `[[0]]`
filler. Partial candidates require independently committed and verified tests.
Parent/child failures remain failures in the audit.

## Materials and fixed inert GPU plan

The published original `sorokin/qwen3_4b_grids15_sft139/transformers/bfloat16/1`
uses instance `627758`, ten retained files and material digest
`sha256:27de51ef22658a0cce3a9fc04fac8fc456165645e2665a82b215f72e20194b03`.
The native008 prerequisite archive remains
`2a8acbc25e5f4b673e3982c550914728ddf8db350191cc4b9cf823db8014dfec`.
The exact model/tokenizer, BF16 adapter topology (506 saved tensors,
528,564,224 trainable elements), rank 256/rslora/alpha 32, optimizer recipe,
Trainer implementations and sixteen pinned distributions come from that
verified native preparation, not Qwen3.5 or the compact eight-step pilot.
Pinned runtime includes Python 3.11.13, Torch 2.8.0+cu128, Transformers 4.55.4,
PEFT 0.17.1, Unsloth 2025.9.7 and Unsloth Zoo 2025.9.9.

Final package: `.irisx/native-solve-stage2-20261004-001/proposal-006`.
Run: `nvarc-original-qwen3-native-multitask-006`.
Plan digest: `sha256:6addcdc7c292cfb3a562b47e629690f2ff6f8fbd3c85c3f82ea843d9eadc7557`.
`approved=false`; admission, quota observation and closed-session assertions
are absent/unknown. Earlier local proposals 001–005 are frozen unapproved
drafts. No existing native-solve or native008 identity was rewritten.

| Work | Bound |
| --- | --- |
| Public parents/tests | `44f52bb0`: 2 tests; `833966f4`: 1 test |
| Source | Retained training2 challenges SHA-256 `779eaba89790ebad9af02514a7efc0aefaf2cf8236f046a31bbf8b9ec48f20f5`; no solutions opened |
| Exposure | Published source/tuning inputs, prior training exposure unresolved; no fresh/hidden/locked evaluation claim |
| Normal TTT | 128 rows/steps per task; 15,360 + 5,632 input tokens, 1,536 + 2,048 supervised tokens; maxima 120/52 tokens |
| Generation/verification | 12 DFS batch invocations total; 16 views/test, 64 processed sequences/test, 8 views per unique candidate |
| Additional isolation work | First-task fault after exactly two updates; fresh second-task baseline-only control after that failure |
| Hardware/processes | Four distinct BF16 L4s required; four fresh child invocations sequentially on physical GPU 0; other GPUs idle |
| Training/session ceilings | 258 outer forwards/updates; 259 reserved Trainer microsteps; 21,232 input tokens |
| Inference ceilings | Per test: 4,096 generation + 128 verifier forwards, 5 Mi physical input tokens; session outer forward ceiling 12,958 |
| Cache/reset controls | Raw native cache, 7 calls/168 input tokens per invocation, 28 calls/672 tokens total; no deepcopy/crop repair |
| Clock/disk | 3,600-second parent; 1,000-second child; 800-second task, 450-second inference, 300-second inference reserve, 60-second reset reserve; 240-second finalization reserve; minimum 4 GiB working disk |
| Cost/admission | USD 0; future explicit reconciled owner-Editor admission and at least 2.5 reserved quota hours at the retained 2× L4 quota factor; current quota/sessions unobserved |
| ZIP | Closed `結果.zip`, maximum 96 MiB; exact plan/payload/source scripts, hardware/material checks, receipts, preparation/token bytes, training/event ledgers, per-test checkpoints, reset/result diagnostics, native evidence, audit and submission |

All three tests must retain nonempty completed source rankings for the GPU gate.
Empty output or budget stop is evidence of an unmet gate, never permission to
change DFS thresholds. Normal task baselines, post-reset controls, and the
second-task baseline after the injected failure must agree. The intentional
fault remains a failed child/parent observation even if its isolation gate
passes. Four concurrent GPU workers are not implemented or claimed.

## Validation and retained limits

The focused suite exercises real learned tiny CPU generation through the exact
DFS/inverse/dedup/ranking/export route and separately labeled injected candidates.
Tiny Qwen3/PEFT tests exercise actual eight-view NLLs and optimizer/gradient/
scheduler/adapter restoration after success and failure. The fault must retain
a changed pre-reset fingerprint; uncleared state cannot produce a completed
worker outcome. Raw mutable HF cache
fails the branch control; no cache deepcopy masks that failure. Tiny transition
model cache behavior is deliberately cache-independent and gives no native
attention/backend conclusion.

Final counts, commands, SHA-256 bindings and repository-check skips are retained
in [`configs/native-solve-stage2-20261004-evidence.json`](configs/native-solve-stage2-20261004-evidence.json).
The final focused run passed 87 tests with zero skips.
Local real CPU replay is `cpu-replay-005`; a separate process independently
replays its exported evidence. The final inert notebook rejects before GPU/model
work and its closed failure ZIP passes the independent verifier. All 175 retained
delivery/history files checked, including 64 historical bindings, remain exact.

Native GPU cache, trained generation/nonempty rankings, target process isolation,
resource sufficiency and producer/export qualification remain **unverified**.
Exact DFS numerical replay between pinned Linux Torch 2.8 and the current
Windows Torch 2.12.1 CPU profile also remains unverified; a mismatch rejects
evidence without relaxing the scientific threshold. The local tests establish
engineering behavior, not official score, SOTA, full NVARC reproduction or
method promotion. ARC correctness was not scored.

Re-run from the delivered commit using the existing ML environment:

```powershell
$env:PYTHONHASHSEED='0'
$env:IRIS_NATIVE_CODE_ONLY_DIR="$PWD/.irisx/native-solve-stage1-20261004-001/code-only"
.irisx/nvarc-ml-venv/Scripts/python.exe -m unittest tests.test_nvarc_native_solve tests.test_arc_kaggle_submission tests.test_nvarc_native_multitask tests.nvarc_native_solve_strict tests.nvarc_native_multitask_strict -v
.irisx/nvarc-ml-venv/Scripts/python.exe tools/stage_nvarc_native_multitask.py preflight --package .irisx/native-solve-stage2-20261004-001/proposal-006
.irisx/nvarc-ml-venv/Scripts/python.exe .irisx/native-solve-stage2-20261004-001/independent_cpu005.py
.irisx/nvarc-ml-venv/Scripts/python.exe tools/repository_check.py --all
```

The next concrete acceptance is controller review of this exact package/evidence,
then a separately admitted new immutable owner-Editor package. The owner can run
it and return its ZIP for `verify_nvarc_native_multitask.py --archive ... --package
... --output ...`. The current inert package cannot be edited into an execution
approval, and this handoff grants no save/run or retrieval authority. No subsequent
development chat or schedule was created.
