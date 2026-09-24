# Decision 0026: Authorize one compact 4B small complete flow

Status: Accepted

Date: 2026-09-24

## Context

Pilot 004 verified only two synthetic Qwen3.5-4B LoRA steps on the original
full-vocabulary model. It made no compact conversion or generation. The owner
requested a distinct small complete flow; local development, a tiny actual
Qwen3.5 CPU end-to-end test and a private Kaggle draft package are complete.
The owner then replied 「授權」 to the exact proposal in the development task.
Decisions 0021–0025 remain consumed and their identities and bytes are unchanged.

## Decision

Authorize `nvarc-4b-compact-complete-001` and exactly one private Kaggle
`SaveKernel` submission under kernel ID
`danielwuu/iris-x-4b-compact-complete-001`. The [draft plan](../../trials/arc-agi-2-qwen35-nvarc/configs/compact-complete-001.json)
SHA-256 is `c3b7891fbfe54ed852fe1263e620aea6679156c16ee374957d47d3e02734911f`.
The approved staged plan, visible source, original model manifest, offline
wheel manifest, current IRIS-X wheel, notebook and metadata SHA-256 values are:

| Material | SHA-256 |
| --- | --- |
| Approved plan | `0d3c7b78b5df18ccfc572f4bbad73efba8938330086e02dfffccb143344d0906` |
| Visible synthetic source | `4bbb0b7662938332192d400d0027bae8cc4ae917ddbaf1613446c79c180f8ba2` |
| Original model manifest | `0079d074151065b317da97aab60cea166498d08a1c2883c005dd12a1a6017667` |
| Offline wheel manifest | `f9106fe3d007d4b0963d12db6e7488a91b59e7824f8f0d192b4fcc45f8050887` |
| IRIS-X runtime wheel | `8b939a389f8301e4bea7fbd6bd4c54c5800e17cc70c8fbba9088928ea9a07ec0` |
| Notebook | `1e7a4db6cd44b2bc79968633a1bf9cdbf0a6b3b70b5f4bc8fed34b864a923a2a` |
| Kernel metadata | `b4e9fec8cbd6f32874dcb10b4b0d4b9e2a4eaef8860719380096e02cc13e6b89` |

Reuse only private Dataset `danielwuu/irisx-arc-agi-2-trial-002-smoke-001`
version 2, pinned Qwen/Qwen3.5-4B revision
`851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`, its exact model and wheel
inventories, and the existing official `arc-prize-2026-arc-agi-2` mount. The
mount is checked for challenge-file presence only; the ARC challenges and
evaluator truth are not read. The notebook remains private and Internet-off.
It may remove only optional `torchao` before installing the pinned wheels.

Require at least one L4 with 22,000 MiB; use device 0 only. The synthetic
visible workload has two tasks and four test inputs, including rectangular
grids. The sequence is original model inventory check, actual 16-row compact
conversion and save/reload, one task-local LoRA step per task, bounded DFS
generation and likelihood ranking, truth-free checkpoint/result ZIP, and
independent local verification. No fixture prediction may be substituted for
GPU model output. Missing or invalid outputs remain partial evidence.

The ceilings are USD 0 paid cost, 2,400 seconds total session with a
300-second finalization reserve, 2,100 seconds for the outer worker, 900
seconds per task, two LoRA steps and 128 training tokens in total, four
generation calls, eight returned sequences, 64 DFS forwards, 64 verification
forwards, zero teacher calls, one kernel push and one terminal retrieval.
Rank 2 and a 64-token sequence limit are pilot settings, not evidence for
rank 256 or 8,192-token viability. The one retrieval may include the newly
created compact model artifact, roughly 8–9 GB. Retain private truth-free
material locally through owner review; no publication, ARC scoring,
competition submission, Dataset mutation, full SFT, TRM, SDG or further run
is authorized.

Before mutation, atomically reserve the push with exact package hashes in a
local ledger. Check credential freshness without printing tokens. If and only
if Kaggle rejects the request before any kernel version exists, verify the
absence through an own-kernel listing and allow at most one retransmission of
the **same bytes and identity**. An accepted version consumes submission
authority whether runtime succeeds or fails. Monitor it to terminal, reserve
one output retrieval, download with UTF-8 CLI output, verify the result and
compact artifact locally, then stop. A model/runtime failure never authorizes
resubmission or resume. Record HTTP 400 without guessing its root cause.
