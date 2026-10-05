# Two public evaluation notebooks — owner Editor

Date: 2026-10-05, Asia/Taipei.
Authority: [Decision 0060](../../docs/decisions/0060-save-two-public-evaluation-notebooks.md).
Status: both sole private QUICK_SAVEs accepted as version 1 and consumed;
owner Editor execution and returned ZIPs are pending. Runtime is unqueried.

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
`python tools/repository_check.py --all` passed: **522 discovered tests,
one optional skip, 1,169.309 seconds**, repository invariants and diff checks
passed. The packaging-only fresh-process fix was followed by the final 13-test
targeted regression below and a fresh repository invariant check. Its code
changes no embedded runtime/source/input bytes.
Retained logs: `.irisx/nvarc-public-eval-debug-20261005-001/repository-check.log`
and sibling `targeted-final.log`, `sdk-save-tests.log`.

## Exact packages and save receipts

Each fixed package belongs at
`.irisx/nvarc-public-eval/runs/<run>/package-l4`, with its sole request,
reservation, ledger and receipt at sibling `editor-save`.

Implementation commit: `0c19b4ba0e7c70faebb82042ac96f3d0279b6fb9`.
Offline preflight fix: `56904063494d5c6d4897f3f0f3efc0e08a75854b`.
The fresh-process preflight found a Python dictionary-order difference before
credential/provider IO. The fix reconstructs every payload from trusted local
source while retaining the saved literal ordering; both notebooks and package
hashes remain unchanged. No save reservation or provider call occurred during
those failed offline checks.

Targeted final regression: **13 tests, no skips, PASS in 44.806 seconds**.
This includes fresh interpreters with hash seeds 13 and 71. Actual SDK wire tests
also passed in the separate credential/runtime environment without provider IO.

### nvarc-public-base30-001

- Plan digest: `sha256:0c05e77adcbb40abd223345122ec84a10e7e67e86b0ecf2d4e041c109871ef58`.
- Notebook SHA-256: `4bd74f119e202a6fcd09ed1a73ea40531c95845a2b2a3623998d9687852123e4` (179915 bytes).
- Metadata SHA-256: `00679d1a70dcde3130fd34f0ce7999b4b4723ce71a44ed8c8efdac7076e73265`.
- Stage summary SHA-256: `7c184ccd28d5ba54dde3be292c1ca2377076464b90cca77daa29813820ab180b`.
- SDK request SHA-256: `4aea2a78e3eb704bc720878932e1a689bac7f970589b7041689f17a89012488a`.
- Offline request: `QUICK_SAVE`, private, Internet off, `NvidiaL4`, 3600 seconds.
- Accepted version 1, kernel ID `137147166`: [nvarc-public-base30-001](https://www.kaggle.com/code/danielwuu/nvarc-public-base30-001).
- Reserved UTC: `2026-10-05T07:54:14.875218+00:00`; accepted receipt UTC: `2026-10-05T07:54:18.227356+00:00`.
- Reservation SHA-256: `2585ef17584822b8f9f62d13ea128fc59447be21d03604a71a9a45d2ba820a05`.
- Receipt SHA-256: `18d2c360907dd56f3b02d1e86cbafa5d32b7eb1a4f3527a3bbd8817d972d24ea`.
- Final ledger SHA-256: `c153751d0890dead04d3816b876f3a6035c9999a32361e98070d6debbbc1c08e`.
- Counts: one save reserved / one exact POST sent; zero status queries,
  zero retrievals. The identity is consumed without retry.

### nvarc-public-ttt128-30-001

- Plan digest: `sha256:a3001cd4f8d1ddba1cc2e2515bcb4c24c1ee4887e41d40c62fcd7cf85d9668fe`.
- Notebook SHA-256: `0973b904892e06876a0ef8921353fec866af6d9c1ee14a2331ef6f384df99def` (179952 bytes).
- Metadata SHA-256: `a4507188fd86acecb6351c1c713c52d2e6bc16956984d10be291c2b94cc915ec`.
- Stage summary SHA-256: `73e96af750a0951e85b4e25cf835449244350c0949376a65cf583c60477e31f3`.
- SDK request SHA-256: `7ad5cccbccb56853247ef00336ff37e6e47ee63a52d19ba7a098992849816b0d`.
- Offline request: `QUICK_SAVE`, private, Internet off, `NvidiaL4`, 14400 seconds.
- Accepted version 1, kernel ID `137147194`: [nvarc-public-ttt128-30-001](https://www.kaggle.com/code/danielwuu/nvarc-public-ttt128-30-001).
- Reserved UTC: `2026-10-05T07:54:32.724279+00:00`; accepted receipt UTC: `2026-10-05T07:54:36.332255+00:00`.
- Reservation SHA-256: `96a56c26c3e0b3b68b64a46194e02ee8e4eb34f4a61b460ac3a924f46b696c6b`.
- Receipt SHA-256: `abf4d78ae84b703a7e56257e9de0eb26fcf2dc93854cb6195bb8fff3f8123d48`.
- Final ledger SHA-256: `3bfeb642d387a7bfb03d9e1019a2bfd81571ce9b9c6efea3236e32737957093b`.
- Counts: one save reserved / one exact POST sent; zero status queries,
  zero retrievals. The identity is consumed without retry.

No agent session was started and no provider runtime, log or output query was
made. Both requests explicitly used `QUICK_SAVE`; no formal competition
submission or Dataset mutation occurred. All external operations stopped at
the receipts. GPU runtime/parity and correctness remain unobserved/unscored.

The owner starts each notebook in Editor with Run All and returns its distinct
ZIP. Agent work stops at save receipts; there is no scheduled or continuous
monitor. The previous official 001 remains terminal failed without a score.
