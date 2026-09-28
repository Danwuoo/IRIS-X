# Decision 0039: Save repaired M2/M3 notebook for owner Editor

Status: Accepted
Date: 2026-09-28

The owner reviewed combined 004 and directs repair and rerun of **both** M2
and M3, with a QUICK_SAVE submission and no agent run. This authorizes one
private QUICK_SAVE of the distinct `nvarc-m2-m3-combined-005` notebook. The
owner starts it in Editor and supplies `/kaggle/working/結果.zip`. All earlier
identities, packages, observations, and consumed allowances remain frozen.

The exact canonical plan is
`trials/arc-agi-2-qwen35-nvarc/configs/m2-m3-combined-editor-005.json`, digest
`sha256:24d2f2a1a31c49f968c8076c73b4c09cfec8bad5f8979b218c40c391c84aedf5`.
The saved wheel, notebook and embedded payloads are checked against this plan.

- M2 keeps the verified eight-step SFT export, same visible task, source views,
  model, and task-local adaptation. Its public training examples all map 2×2
  inputs to 6×6 outputs; the test input is 2×2. A distinct search profile uses
  that *public shape witness* to require complete 6×6 grids and a 0.02
  probability floor per unmasked token rather than the prior cumulative
  threshold. It retains one TTT step / at most 512 training tokens, four
  generation calls, two sequences and 64 tokens per call, 128 DFS expansions
  per call, at most eight verifications / 64 verifier forwards, and no SFT
  resume. Candidate availability does not establish ARC correctness.
- M3 keeps the pinned full-vocabulary Qwen3.5-4B, public parent demos and
  four dependent calls with unchanged stage caps and 28,160 total reserved
  tokens. The new prompt gives checks of the five single operations against
  **every public demo** and explicitly asks the teacher to verify its rule.
  One isolated JSON fence is accepted for summary or mix; prose and extra
  blocks still fail. The prior semantic demonstration, exact ordered mix,
  EOS, generated-program, source-filter and namespace-isolated 44-invocation
  gates remain. A rejected stage stops dependent work without retry.
- The notebook uses two distinct L4 workers, BF16, existing Datasets and
  competition source, pinned offline dependencies, Internet off, USD 0,
  1,800 seconds, and the existing setup/readiness/terminal reserves. It
  produces a digest-inventoried, truth-free `結果.zip` on ordinary completion
  or Python failure. Hard termination may prevent ZIP finalization.

Complete offline verification and reserve the sole save before exactly one
`SaveKernel` request with `KernelExecutionType.QUICK_SAVE`. Stop at its receipt.
No agent session start, status/log/output query, retrieval, monitoring,
Dataset mutation, paid cost, scoring, publication, competition submission,
or automatic retry is authorized. A rejected or uncertain save consumes this
allowance.

Status and receipt: `trials/arc-agi-2-qwen35-nvarc/combined-notebook-005-editor.md`.
