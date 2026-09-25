# Decision 0031: Authorize bounded NVARC M2 checkpoint and M3 teacher continuation

Status: Accepted
Date: 2026-09-25

## Context

The owner replied 「授權」 to the integrated request after reviewing the
locally staged packages in
[`2026-09-25-nvarc-m2-m3-checkpoint-continuation.md`](../plan/2026-09-25-nvarc-m2-m3-checkpoint-continuation.md).
That request named both the M2 full-parameter SFT and M3 teacher packages,
their separate identities, provider, data, execution and retrieval bounds.
The earlier Decision 0028–0030 probes are consumed. In particular, the
verified four-L4 `nvarc-m2-fsdp-feasibility-003` result completed one update
but saved no SFT checkpoint, and `nvarc-m3-teacher-small-001` made no teacher
calls after a two-T4 hardware-gate failure.

The inert M2 draft `m2-fsdp-sft-draft-001.json` has SHA-256
`8e69cdf03d9f4e3146349f3abe8bb8fa6e6cc4ce2a2a0010245b705579397e1f`.
Its reviewed `fsdp-sft-review-004` package binds plan SHA-256
`4f16baf031c7ffb63a002ab61ce6cae3713f4296899173216ac1baf33410f6af`,
runtime wheel SHA-256
`523285fadb96ada0a9483cb63a63655a1584b5d524592eecdf6e3c016ac051ce`,
and notebook SHA-256
`46d392ad48e4c351acb8bbfd29fbb3dd8af2e184603fb10a1d116c57a722b1e3`.
The inert M3 draft `m3-teacher-draft-002.json` has SHA-256
`1b9f03dca16dfeadc3e3d2520d5989a2f1734eefbbbe1c159c05a91317ec49f6`.
Its reviewed `teacher-review-004` package binds plan SHA-256
`e2cdbd1275bd41c645e262a93eaf6bef17be09d8845aba105e8194c0f4cf837d`,
the same runtime wheel, and notebook SHA-256
`0dcb0b7ddd99f6d45c2e4f20d51aff0bf06bdb256863c024cbc551ac0f057e33`.
Both local preflights passed without external calls.

## Decision

- Authorize one private, Internet-disabled Kaggle `NvidiaL4` kernel under
  `danielwuu/nvarc-m2-fsdp-sft-001`, with exactly four distinct BF16 L4s,
  at most 2,700 seconds, USD 0 paid cost, one accepted kernel version and one
  terminal output retrieval. Reuse the existing private compact-model and
  offline-wheel Datasets; the official competition mount is present only to
  reproduce the successful four-L4 transport. Train only on the frozen public
  ARC training set: eight train parents, 128 train-only augmented sequences,
  eight disjoint dev parents, no evaluation6 or holdout derivatives. Permit
  eight unpacked full-parameter FSDP optimizer steps, at most 2,578 scheduled
  input tokens and sequence length 128. Save after step one, restart and
  resume, save final model/optimizer/RNG/cursor, export/reload the trained
  checkpoint, then run source-profile task-local TTT, DFS, inverse/dedupe and
  ranking on one visible dev task. Bound that solve to at most four generation
  calls of 64 new tokens each and 128 DFS expansions per call. Retain the
  truth-free checkpoint transport, export, run chain, source result and
  diagnostics.
- Separately authorize one private, Internet-disabled Kaggle `NvidiaL4`
  kernel under `danielwuu/nvarc-m3-teacher-small-002`, with a four-L4
  hardware gate and one L4 used, at most 1,800 seconds, USD 0 paid cost, one
  accepted kernel version and one terminal output retrieval. Reuse the
  existing private full-vocabulary pinned Qwen3.5-4B Dataset and the same
  official competition mount. On the two frozen public ARC training parents,
  permit at most four dependent NVARC source-prompt calls, each capped at
  4,096 input and 1,024 output tokens, reserving at most 20,480 tokens in
  total. Retain private raw responses, actual usage and all stage ledgers.
- Private transport and use of the pinned NVARC prompts for this bounded
  teacher run is approved. The local Qwen3.5-4B teacher differs from the
  upstream NeMo-Skills GPT-OSS-120B tutorial; neither original teacher parity
  nor original-scale SDG/TRM performance may be claimed. After retrieval,
  replay saved responses only in the tested isolation sandbox and keep
  generated pairs separate from dev and evaluator truth.
- The two attempts are independent. A provider rejection, hardware-gate
  failure or notebook error consumes that identity. No automatic retry,
  replacement identity, Dataset mutation or second retrieval is authorized.
  Preserve the exact submitted bytes, receipts, failures and token/step counts.
  No paid API, Codex subscription as teacher, heldout scoring, competition
  submission, public release, original-scale H100 training or new large data
  acquisition is authorized.
