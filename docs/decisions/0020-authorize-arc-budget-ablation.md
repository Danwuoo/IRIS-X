# Decision 0020: Authorize ARC output-budget and thinking ablation

Status: Accepted

Date: 2026-09-23

## Context

The owner directed: 「開發的模型和反思的模型都換成 gpt 6 sol xhigh，開始進行新實驗吧」
after reviewing the [ablation plan](../plan/2026-09-23-arc-reasoning-budget-ablation.md).
This opens the separate `arc-agi-2-budget-ablation` trial. Decision 0019 and
all prompt-pilot identities remain terminal, with no scored final holdout.

## Decision

Authorize one development task using `gpt-6-sol` with `xhigh` reasoning to
implement and continuously complete preparation, diagnostic execution,
retrieval, local scoring, conditional validation, and a final report.
Future active reflection configuration also becomes `gpt-6-sol / xhigh`,
through Codex CLI subscription usage with elapsed-time recording. Preserve
historical `gpt-5.6-sol` bindings and evidence; do not rewrite prior ledgers.
No GEPA proposal or reflection model call is part of this ablation workload.

The solver remains exactly
`Qwen/Qwen3.5-4B@851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`.
Keep B1's instruction, demonstrations, greedy decoding and strict final-grid
parser. Use the fixed 64-case optimization-train diagnostic cohort defined
in the plan, with existing 512-token/no-thinking results as the cached control.

- `budget-ablation-diagnostic-001`: one private kernel containing 192 jobs,
  64 each for no-thinking/1024, no-thinking/4096 and thinking/4096.
- `budget-ablation-validation-001`: at most one further private kernel with
  384 jobs for one frozen qualifying configuration, on the unchanged 256
  train plus 128 dev. Qualification requires at least four net additional
  correct diagnostic answers and retention of at least 16 of B1's 18 correct
  answers. Rank qualifying arms by correct count, then lower p95 elapsed,
  then lower token cap; an exact remaining tie favors thinking off.
- Cap all new Qwen generation calls, including failures, at 576. If no arm
  qualifies, stop at 192. Each job is bounded at 300 seconds with enforced
  termination, no retries, no warm-up generations and no extra samples.
  Thinking tokens and final tokens share the arm's single total budget.
- Reuse the successful runtime, exact large model Dataset and four-worker
  scheduler. Use small, immutable private runtime/outbound Dataset versions.
  Both kernels must mount `arc-prize-2026-arc-agi-2`, request `NvidiaL4`, have
  Internet disabled, and verify four distinct L4 identities and model-ready
  workers before dispatching work across all four cards.

Authorize necessary deliberate source/tokenizer/dependency acquisition,
existing Kaggle CLI authentication, private small Dataset staging/upload,
the above kernel launches, bounded low-frequency status/startup log reads,
one terminal output retrieval per launched kernel, and local checkpoint
packaging after a finalization-only failure. Reuse verified local and remote
artifacts first; do not download/upload large weights merely to reconstruct
a missing local cache. Tests and ordinary validation remain offline.
No paid GPU or metered external inference API is authorized; Codex development
uses the owner's subscription plan. Record durations rather than inventing
a dollar charge. GPU hours have no separate owner-set ceiling; generation
and per-job limits still apply, along with platform limits.

## Source compatibility and isolation

Before GPU submission, materialize and bind the official competition challenge
snapshot and audit visible content for all 512 selected train/dev/holdout cases.
Retain the exact discrepancy report, including `f3e62deb`; do not open holdout
answers. Every executed case must match the pinned solver view exactly.

If discrepancies are confined to the 128 unused holdout cases and all 384
train/dev cases match, the new train-only diagnostic and train/dev validation
may proceed. Mark the old holdout incompatible and unscored. This clarifies
the draft's all-512 preflight: audit coverage is 512, execution eligibility
requires parity for all 384 cases this experiment may run. A difference in
any of those 384 blocks submission; do not replace cases, change frozen source
bindings, or silently relax equality. Resolving an incompatible source would
require a separately reviewed comparison design.

Only visible solver inputs and execution configuration enter outbound
packages. Cohort strata, answers, scores, feedback and answer-derived metadata
stay evaluator-side. Keep the original split and all historical artifacts
unchanged, and give every changed configuration/package a distinct identity.

## Continuation, evidence and stop conditions

Maintain one atomic ledger before external mutation or retrieval, binding
configuration/cohort/source/model digests, Dataset/kernel versions, consumed
and reserved invocations, artifacts, timing and next action. Resume an
interrupted local controller from this ledger without duplicating operations.
Continue through terminal retrieval and scoring rather than stopping after
model-ready. Do not create a replacement kernel following runtime failure.
On missing credentials/quota/input, unverifiable evidence or incompatibility,
preserve the failure and report the concrete blocker without unlimited retries.

Deliver reproducible local score reports, paired comparisons, parse/truncation
and timing diagnostics, and the next research recommendation. The diagnostic
sample is deliberately selected using historical train outcomes, and dev is
previously used selection data; neither is an unseen public-evaluation score.

This decision does not authorize holdout inference/scoring, additional GEPA
search, NVARC training/adaptation, another solver, public evaluation sweeps,
competition submission, publication, promotion or P3/P4 work.
