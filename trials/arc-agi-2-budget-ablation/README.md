# ARC-AGI-2 output-budget and thinking ablation

Status: `authorized-awaiting-implementation` (2026-09-23).

[Decision 0020](../../docs/decisions/0020-authorize-arc-budget-ablation.md)
authorizes the [development and execution plan](../../docs/plan/2026-09-23-arc-reasoning-budget-ablation.md).
No new kernel or generation is claimed by this initial status.

- Development task: `gpt-6-sol / xhigh`; future reflection configuration uses
  the same model and effort, with zero proposer calls in this ablation.
- Solver: pinned Qwen3.5-4B, original B1 instruction and greedy decoding.
- Diagnostic: 64 train cases x three arms = 192 new generation calls.
- Conditional validation: one qualifying arm x 384 train/dev cases.
- Total ceiling: 576 calls, 300 seconds per job, no retry or warm-up.
- Runtime: official competition mounted, private, Internet disabled, four
  verified L4 workers and dynamic dispatch; reuse the successful model Dataset.
- Full visible-source audit covers 512 cases. All 384 executable train/dev
  cases must match; discrepancies only in unused holdout are retained and
  do not turn the old holdout into an authorized workload.

Prior evidence remains read-only in
`C:/Users/wurre/.codex/worktrees/e34a/IRIS-X/.irisx/arc-agi-2/prompt-pilot/`.
New generated evidence belongs under the development worktree's
`.irisx/arc-agi-2/budget-ablation/`. Keep its identities and ledger separate
from the completed prompt pilot. Record actual task identity, preflight,
launches and results here as they become verified.
