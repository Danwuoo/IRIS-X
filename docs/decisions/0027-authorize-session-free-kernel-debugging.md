# Decision 0027: Authorize free kernel debugging of the compact 4B flow in this session

Status: Accepted

Date: 2026-09-24

## Context

The one Decision 0026 version, `nvarc-4b-compact-complete-001`, failed before
model loading at the Dataset v2 root inventory gate. Its push and retrieval
remain consumed. The owner now explicitly authorizes free Kaggle kernels for
program-error repairs during this session: 「授權這個 session 的程式錯誤性質修復都可以自由使用 kernel」.
This is a new direction for the compact flow, not a reopening of version 001
or any earlier trial identity.

## Decision

Permit successive **distinct**, private Kaggle kernel attempts, beginning with
`nvarc-4b-compact-complete-002`, only to diagnose and repair program errors in
the small complete synthetic Qwen3.5-4B flow. Each attempt gets a new run ID,
kernel slug, staged package, local launch ledger and retained terminal record.
Never overwrite or resubmit an accepted version's bytes or result. Necessary
own-kernel status, log and output retrieval may be used to inspect each attempt
and verify the final result. This authority lasts only for the current task
session and ends once the small complete flow is verified or the owner redirects
it; it is not a standing authorization for future sessions.

Every attempt retains the Decision 0026 scientific and data boundaries:
the same two synthetic tasks and four test inputs, pinned Qwen3.5-4B source,
read-only private Dataset v2 and official competition mount checked for
presence only. The notebook is private, Internet-disabled and truth-free.
Use at most one L4, 2,400 seconds session, 2,100 seconds worker,
900 seconds per task, two LoRA steps, 128 training tokens, four generation
calls, eight returned sequences, 64 DFS and 64 verification forwards, zero
teacher calls, and **USD 0 paid cost per attempt**. Do not run ARC scoring,
change the method or workload, mutate a Dataset, use external model APIs,
submit to the competition, publish, start full SFT/TRM/SDG, or use paid compute.

Fixes must be supported by local evidence before the next kernel. Keep
retrieved observations, failures and hashes private under `.irisx/`, report
each terminal state in the trial workspace, and independently verify any
truth-free result and compact model artifact. Once the complete flow passes,
stop further kernels. A scientific change or paid cost needs new owner
direction.
