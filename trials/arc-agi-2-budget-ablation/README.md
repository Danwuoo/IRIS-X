# ARC-AGI-2 output-budget and thinking ablation

Status: `diagnostic-complete-no-validation` (2026-09-23).

[Decision 0020](../../docs/decisions/0020-authorize-arc-budget-ablation.md)
authorizes the [development and execution plan](../../docs/plan/2026-09-23-arc-reasoning-budget-ablation.md).
The control task verified development head `e8868c6` in the `918a` worktree.
The [control review](control-review.md) records independently recomputed
scores, source parity, paired raw-output comparisons and research conclusions.
Development code remains on `codex/arc-budget-ablation`, pending integration.

- Development task: `gpt-6-sol / xhigh`; future reflection configuration uses
  the same model and effort, with zero proposer calls in this ablation.
- Solver: pinned Qwen3.5-4B, original B1 instruction and greedy decoding.
- Diagnostic: 64 train cases x three arms = 192 completed generation calls.
  A1/A2 each scored 18/64, identical to cached B0; A3 scored 7/64.
- Conditional validation: no arm qualified; no 384-job kernel was launched.
- Total ceiling: 576 calls, 300 seconds per job, no retry or warm-up.
- Runtime: official competition mounted, private, Internet disabled, four
  verified L4 workers and dynamic dispatch; reuse the successful model Dataset.
- Full visible-source audit covers 512 cases. All 384 executable train/dev
  cases match. All 512 full visible cases also match. The old holdout error
  compared a selected-test projection to a full multi-test case; it was not
  actual source-content drift. Holdout remains unscored.

The one kernel and one terminal retrieval completed. Result SHA-256:
`65e2d694e7268815d1b7d594218dea2012c1a7694d108048c1cb543f878edeea`.
The four-L4 session took 78.87 minutes with no generation retry or timeout.
Decision 0020's workflow is terminal; the unused generation ceiling does not
authorize additional experiments or a validation run that failed its gate.

Prior evidence remains read-only in
`C:/Users/wurre/.codex/worktrees/e34a/IRIS-X/.irisx/arc-agi-2/prompt-pilot/`.
New generated evidence belongs under the development worktree's
`.irisx/arc-agi-2/budget-ablation/`. Keep its identities and ledger separate
from the completed prompt pilot. Record actual task identity, preflight,
launches and results here as they become verified.
