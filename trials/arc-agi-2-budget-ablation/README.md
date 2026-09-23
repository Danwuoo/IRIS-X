# ARC-AGI-2 output-budget and thinking ablation

Status: `diagnostic-complete-no-validation` (2026-09-23).

[Decision 0020](../../docs/decisions/0020-authorize-arc-budget-ablation.md)
authorizes the [development and execution plan](../../docs/plan/2026-09-23-arc-reasoning-budget-ablation.md).
Development is in a distinct worktree at commit `96667b2` using
`gpt-6-sol / xhigh`. No GEPA or reflection call is part of this run.

- Development task: `gpt-6-sol / xhigh`; future reflection configuration uses
  the same model and effort, with zero proposer calls in this ablation.
- Solver: pinned Qwen3.5-4B, original B1 instruction and greedy decoding.
- Diagnostic: 64 train cases x three arms = 192 new generation calls, all
  completed in one kernel.
- Conditional validation: no arm qualified; the 384-job kernel was not
  prepared, uploaded, or launched.
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
  jobs. Metadata mounts `arc-prize-2026-arc-agi-2`, requests `NvidiaL4`, is
  private and Internet-disabled. One transient Kaggle API connection failure
  interrupted status polling; the same version 1 resumed from the ledger,
  without another upload, push or generation request.

The diagnostic outbound digest is
`sha256:299472150cc55b6a2755a292db4952cfebf93e2a8343843af5d55463b4b8f485`.
The runtime wheel digest is
`sha256:5b250ca40baa74f810d216ea53eaea671d3baeb069307530fcc8cf41a26e9484`.
The local repository check and 156 tests passed before launch.

## Runtime evidence and diagnostic result

The single kernel version 1 ended `COMPLETE`. Its one terminal retrieval
returned a verified truth-free `result.zip`, checkpoint and progress stream.
The result SHA-256 is
`65e2d694e7268815d1b7d594218dea2012c1a7694d108048c1cb543f878edeea`.
The checkpoint records exactly 192 distinct generation invocations, 192
terminal jobs, no retries, no timeouts and no warm-up. Four `NVIDIA L4` GPUs
had distinct UUIDs; four workers reported the pinned Qwen revision and model
manifest, each loaded once in 30.25–30.69 seconds. The first four jobs were
dispatched on ranks 0–3. Dynamic scheduling completed 40/50/53/49 jobs by
worker. The runner wall time was 4,732.345 seconds (78.87 minutes).

The historical B1 result was independently rescored and matched its retained
score JSON exactly: 18/256 train, 12/128 dev, holdout unscored. On the fixed,
outcome-selected 64 train cases, the paired diagnostic was:

| Arm | Exact /64 | Retained B1 correct /18 | New / lost | Valid grids | Cap hits | p50 / p95 generation seconds | p50 / p95 generated tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| B0 off / 512, cached | 18 | 18 | — | 60 | 22 | 6.8 / 31.5 | 111 / 512 |
| A1 off / 1,024 | 18 | 18 | 0 / 0 | 59 | 4 | 7.3 / 59.3 | 111 / 1,022 |
| A2 off / 4,096 | 18 | 18 | 0 / 0 | 59 | 4 | 6.7 / 210.5 | 111 / 3,634 |
| A3 on / 4,096 | 7 | 6 | 1 / 12 | 7 | 57 | 237.7 / 240.4 | 4,096 / 4,096 |

All 64 jobs per new arm supplied generation time and token counts; none had a
raw-completion storage truncation. A1 and A2 reduced the 22 cached 512-token
cap hits to four but did not add a correct answer. Their 18 correct answers
were the same 18 as B0. The four remaining capped jobs in each arm were
invalid under the complete-final rule; each arm had one additional EOS-ended
unparseable grid. A3 used all 4,096 shared reasoning/final tokens in 57/64
jobs without a `</think>` final separator, so those jobs were invalid. The
other seven had complete final grids and were correct: one new answer and six
retained B1 answers. Reasoning/final token counts are known only where the
separator appeared; missing values for the 57 capped jobs are not zeros.

By diagnostic stratum, B0/A1/A2 each scored 18/18 originally correct and
0/22 capped, 0/12 wrong-size, 0/12 wrong-content. A3 scored 6/18 originally
correct, 0/22 capped, 1/12 wrong-size and 0/12 wrong-content. This cohort was
chosen from known train outcomes and cannot estimate dev, public evaluation,
or competition accuracy. The A3 result tests greedy thinking with a combined
4,096-token cap; it does not establish the model's unconstrained reasoning
ceiling.

The qualification rule required at least four net additional correct answers
and retention of at least 16 of B1's 18. A1 and A2 had net zero; A3 had net
minus eleven and retained six. No arm qualified. The atomic ledger marks
validation `not-qualified`, with no version 2 Dataset or validation kernel.
Total new Qwen invocations: **192 of the 576 authorized ceiling**. No GEPA,
reflection, TTT, holdout inference/scoring, public evaluation, or competition
submission occurred. No paid inference API was used; Kaggle ran under the
private USD 0 paid-cost boundary.

The local score digest is
`sha256:94ba38faf24ccbe85294ba7991fc512b1216a6a9f3bc4050f3da929f558cc8f6`.
The paired analysis digest is
`sha256:dd74cce027439c0d6f73a70e8f9c652e1f9a1574ad48fdfd07d6a43032c54003`;
the gate record digest is
`sha256:42ed3b40e6f4fda95cf82b867a5efcb642e4c989106faf733de55360fed7ff0f`.
`analysis.json`, `diagnostic/qualification.json` and the single retrieved
output under `.irisx/arc-agi-2/budget-ablation/` retain the per-case pairs,
timing distribution, token counts and startup evidence. The observed source
audit is in `source/visible-audit.json`; its report digest is
`sha256:68d4dedbe8657e12bc8ff900b781d6b12978b4017b0a8138bcc973bd941f62d5`.

The private Dataset create CLI call took 21.89 seconds. Kernel push was
accepted at 01:06:18 UTC; runner preflight began 21.53 seconds later at
01:06:40. The session completed at 02:25:35, and low-frequency polling
observed terminal at 02:27:35, a 120-second detection lag. The single output
retrieval plus local score completed within 14 seconds of that observation.
These intervals distinguish transport and status-poll wait from the measured
4,732.345-second runner wall. No metered inference API charge is claimed.

## Decision and next research question

Neither larger no-thinking output budget improved exact match on this
diagnostic cohort, despite reducing caps, and the bounded thinking arm lost
correct answers because it usually never reached final. Retain B1 as the
comparison configuration; do not promote an ablation arm. The next distinct
experiment should test one bounded NVARC-derived task-local adaptation
protocol with a fixed checkpoint, source binding, contamination labels and
train/dev split. The earlier inference-only Trial 002 smoke does not evaluate
that adaptation method. It needs its own owner-approved design and budget;
this trial authorizes no further solver calls.
