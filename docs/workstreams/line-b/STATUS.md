# Math proof-agent STATUS (compatibility workstream: line-b)

Updated: 2026-10-18. Task state: [generated board](../../management/BOARD.md).
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

## Blockers

No target model, Lean installation, actual TPU capability or representative
model-evaluation panel has been executed/qualified. Shared WSF-R5 independent
acceptance remains unresolved; this research does not change existing reviews.
The inherited management/suite IDs are not renamed in this documentation task.

## Next

Read the research direction and MATH-001 report. Next bounded implementation is
one Lean verifier and one TPU model adapter, then a fixed-model paired independent-
sampling versus verifier-guided-repair pilot. Pin data/compute conditions before
viewing outcomes. Do not treat the certificate audit as agent improvement.

## Boundaries

Keep main, develop, active ARC and historical research refs untouched. Use
separate worktrees and ignored `.irisx/line-b/<task>/` outputs. Initial execution
is stdlib CPU only: no training, Kaggle/provider run, model/evaluator/transfer
acquisition or external contact. Future model experiments need explicit pinned
resource/data scope. Do not publish PutnamBench proofs or hidden evaluator data.
