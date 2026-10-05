# Two public evaluation notebooks — owner Editor

Date: 2026-10-05, Asia/Taipei.
Authority: [Decision 0060](../../docs/decisions/0060-save-two-public-evaluation-notebooks.md).
Status: local implementation complete; handoff checks and sole QUICK_SAVEs pending.

The owner requested two notebooks, local debugging before save, manual Editor
execution, and separate descriptive ZIP names. This implements the
[public evaluation design](../../docs/plan/2026-10-05-nvarc-public-eval-notebook.md).
No agent model/GPU execution, runtime query, retrieval or monitoring is included.

| Profile / immutable run | Training | Search plus verification | Session ceiling | Output ZIP |
| --- | --- | --- | --- | --- |
| `nvarc-public-base30-001` / BASE-30 | No TTT | 30 s/test | 3,600 s | `nvarc-public-base30-001.zip` |
| `nvarc-public-ttt128-30-001` / TTT128-30 | Complete original 128-step epoch per task | 30 s/test | 14,400 s | `nvarc-public-ttt128-30-001.zip` |

Both contain **120 tasks / 172 test inputs** and use four persistent, distinct
BF16 L4 workers with published Qwen3-4B SFT139. Internet is off; paid cost is
USD 0. The existing dependency/model/competition attachments are retained,
while runtime reads no competition files. No Dataset mutation is needed.

The public challenge SHA-256 is
`e7c62a4bd211867c6b538f66b8013b81f299663c82ca062f49a52bf439d6e4e8`;
model material digest is
`sha256:27de51ef22658a0cce3a9fc04fac8fc456165645e2665a82b215f72e20194b03`.
The public-demo-derived workload proof is
`12479915fd5bc81336c893315c67cd860932ddc51eb2f78d1b19b6ca0e1a5b52`:
15,360 original rows, at most 15,360 updates / 30,713,088 training input tokens.
Each TTT epoch has a 1,200-second deadline; incomplete epochs provide no
TTT-qualified candidates. Startup is bounded at 900 seconds; export reserves
300 seconds. Resource quota, factor, reservation and session reconciliation
facts are **unavailable**, represented as null; sufficiency is unverified.

## Implemented behavior

Four notebook cells contain instructions, compressed digest-bound source/input
bootstrap, parent orchestration/export and a separate download-only cell.
Models load once per worker. Every task gets fresh training state, full tensor
restore, discarded moments/gradients and exact same-run baseline controls.
Failed reset retires the worker without a reload or retry.

Each test uses the original DFS, four batches of four source views, 0.2 token
probability floor, at most 64 unique candidates and eight actual verifier views.
Search stops after 20 seconds; verification shares the final 30-second deadline.
Other ceilings are 4,096 generation / 128 verifier forwards and 5,242,880 physical
input tokens per test, 8,192 context tokens and 931 answer tokens. Public evidence
retains actual verifier NLLs and input/answer token digests; it does not retain
the historical full generation-logit stream or qualify the strict portable gate.

The complete submission skeleton exists before hardware/model preparation.
Each verified test is atomically checkpointed and merged by the parent. A test
deadline does not skip later tests. Normal deadlines retain partial output;
program/material/reset failures retain failed terminal status and diagnostics.
The run-named ZIP has closed member hashes, source/input/config, candidate pools,
coverage/timings, per-task training/reset evidence and bounded worker log tails.
It excludes weights, compiler caches and evaluator solutions.

Linux parent-death guards and process-group cleanup stop task-owned worker
processes when the notebook parent exits. A sudden provider kill can still
prevent final ZIP creation; per-test checkpoints remain the recovery evidence.
One candidate duplicates the second submission slot; no candidate uses `[[0]]`.
Fillers count as missing model coverage, even if they happen to match a solution.

`tools/score_nvarc_public_eval.py` is local-only and absent from both notebooks.
After owner outputs return it checks the saved package/returned source bindings,
then reads separate public solutions. It reports pass@1/pass@2 over all 172 tests,
task-average test fraction over all 120 tasks, all-tests task success, pool oracle
and coverage, with filler matches separate. No actual answer file or scoring was
used during implementation. Public exposure in SFT139 is unresolved; this is a
development comparison, not a fresh/hidden/official score or method promotion.

## Offline validation

Targeted checks use the exact pinned tokenizer and original loader/DFS/decoder,
a small learned CPU model, real 128-step optimizer updates and synthetic tasks.
They cover multi-test deadlines, eight actual verifier rows/NLLs, preserved
candidates after failure, full denominator/filler attribution, distinct ZIPs,
source/hash tampering, early hardware failure export, sequential task resets,
faulted TTT cleanup and failed-reset retirement. Four real local subprocesses
exercise one-time mailbox dispatch and cleanup. Actual SDK request serialization
is checked as QUICK_SAVE, with a fault before credentials proving reservation
precedes provider IO and cannot be retried. These establish local mechanics,
not Unsloth/L4 numerical parity or measured public speed.

A separate Linux/WSL probe killed a supervisor and observed its guarded worker
gone in 0.022 seconds, with zero GPU/provider calls. Retained evidence:
`.irisx/nvarc-public-eval-debug-20261005-001/linux-probe-001/verification.json`.
Repository handoff check outcome will be recorded before saving.

## Exact packages and save receipts

Each fixed package belongs at
`.irisx/nvarc-public-eval/runs/<run>/package-l4`, with its sole request,
reservation, ledger and receipt at sibling `editor-save`.
The implementation commit, package/request hashes and accepted URLs will be
recorded after offline validation and the two sequential sole saves.

The owner starts each notebook in Editor with Run All and returns its distinct
ZIP. Agent work stops at save receipts; there is no scheduled or continuous
monitor. The previous official 001 remains terminal failed without a score.
