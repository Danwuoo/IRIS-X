# ARC-AGI-2 output-budget and thinking ablation

Status: `diagnostic-kernel-running` (2026-09-23).

[Decision 0020](../../docs/decisions/0020-authorize-arc-budget-ablation.md)
authorizes the [development and execution plan](../../docs/plan/2026-09-23-arc-reasoning-budget-ablation.md).
Development is in a distinct worktree at commit `96667b2` using
`gpt-6-sol / xhigh`. No GEPA or reflection call is part of this run.

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
New local evidence and the atomic ledger are under `.irisx/arc-agi-2/budget-ablation/`
in this worktree. The original prompt-pilot evidence remains read-only.

## Verified preflight and launch

- Downloaded only official `arc-agi_training_challenges.json` from the 2026
  Kaggle competition. SHA-256 is
  `779eaba89790ebad9af02514a7efc0aefaf2cf8236f046a31bbf8b9ec48f20f5`.
  Full visible-content parity passed for 512 selected cases. The 384 train/dev
  test-index-0 execution views also match. The old `f3e62deb` gate failed
  because it compared one selected test input against its two-input holdout
  case; source content itself matches. The holdout remains unscored.
- Frozen diagnostic cohort: 18 B1-correct, 22 capped, 12 wrong-size, 12
  wrong-content train cases. Manifest digest:
  `sha256:6d37b1abf8e30cb5f70be0ed7e2c5d57a516595d57578d0f8f4727cee48cb66c`.
- Pinned-revision tokenizer and chat-template preflight passed for all 64
  prompts and thinking modes. A complete 30×30 digit-row fixture encodes to
  929 tokens. Reasoning-only and capped-final fixtures are rejected.
- Reused model Dataset `danielwuu/irisx-arc-agi-2-trial-002-smoke-001`
  version 2. Created a separate private, small, truth-free transport Dataset
  `danielwuu/irisx-arc-agi-2-budget-ablation-001` version 1. The CLI's first
  relative-path staging attempt failed locally before upload; the verified
  absolute-path create succeeded.
- Submitted exactly one diagnostic kernel version 1 under
  `danielwuu/iris-x-arc-agi-2-budget-ablation-diagnostic-001` with 192
  reserved jobs. Metadata mounts `arc-prize-2026-arc-agi-2`, requests
  `NvidiaL4`, is private and Internet-disabled. CLI reported `RUNNING`;
  worker readiness, dispatch and generations are not yet verified.

The diagnostic outbound digest is
`sha256:299472150cc55b6a2755a292db4952cfebf93e2a8343843af5d55463b4b8f485`.
The local repository check and 156 tests passed before launch. Runtime outcome,
single terminal retrieval, local scoring, and the conditional validation gate
will be recorded when evidence is available.
