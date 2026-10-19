# Math proof-agent STATUS (compatibility workstream: line-b)

Updated: 2026-10-19. Task state: [generated board](../../management/BOARD.md).
Research entry: [RESEARCH.md](RESEARCH.md).

## Scope

Owner selected proof-oriented tool-augmented mathematical reasoning, with IMO /
Putnam as capability probes, not prize targets. The research branch is
`feat/math-proof-agent-20261018`, based on shared `develop` commit
`9389f433a1fbe41d25f8ce1248fde07f7ce9250d`. Management ID remains `line-b`
for compatibility; this does not create another shared engineering branch.

The original six-case label fixture under `src/irisx/domains/line_b/` remains
unchanged and synthetic. New research lives in `research/math-proof-agent/`;
no production math solver is claimed. Research assistance/autonomous discovery
and contact with possible collaborators are deferred.

## Evidence

MATH-001 contains primary-source review, an answer/proof/cost evaluation design,
a TPU feasibility plan, and an executed 32-case exact-certificate audit. It is
an authored CPU verifier pilot, not an LLM/Lean/TPU or IMO/Putnam benchmark.
See the source-bound handoff for actual commands, outcomes and limitations.

MATH-002 adds one pinned TPU model adapter, restricted Lean worker, bounded
sampling/repair controller and task-owned monitor. Local safety/CPU numerical
controls and actual WSL Lean core/mathlib import-closure/isolation controls ran; these are engineering
evidence. The first private TPU push returned a batch-session-capacity error
despite CLI exit0. Exact task readback returned HTTP403; version remains unknown.
See [R002 results](../../../research/math-proof-agent/ROUND002-RESULTS.zh-TW.md).

## Blockers

No actual TPU target model or representative human-reviewed evaluation panel
has been qualified. Local Lean core and pinned mathlib Ring/NormNum controls passed;
full mathlib and Kaggle Lean/isolation remain unqualified. Upstream human-reviewed
source candidates exist; safe per-item acquisition/runtime admission and feasible
repair context remain open. A narrow Nat-witness binding now passed authored
Lean controls; no real source statement has been admitted to it. Exact tokenizer
checks confirm the 4096+4096 repair context conflict; a smaller common ceiling
is still only a candidate. The unresolved submission retains one attempt
and 1800 seconds of the 4-attempt/21600-second ceiling and blocks further push.
Shared WSF-R5 independent
acceptance remains unresolved; this research does not change existing reviews.
The inherited management/suite IDs are not renamed in this documentation task.

## Next

Read the MATH-002 handoff; reconcile the unknown submission read-only, without
disturbing other account work. Bind available upstream human-review evidence and actual
runtime qualification before freezing any scoring panel. Only then can a
fixed-model paired sampling/repair pilot answer the research question. No model
gain, zero gain or negative effect is inferred from a provider rejection.

## Boundaries

Keep main, develop, active ARC and historical research refs untouched. Use
separate worktrees and ignored `.irisx/line-b/<task>/` outputs. MATH-001's initial
stdlib-only scope remains historical. The owner's 2026-10-19 MATH-002 scope
permits bounded private Kaggle inference/verification and compatible public
dependencies/models, as recorded in its single plan. No training, paid API,
ARC resource operation, blocked transfer archive, public benchmark solution
acquisition or external contact is authorized. Do not publish PutnamBench
proofs or hidden evaluator data. This exception does not broaden other tasks.
