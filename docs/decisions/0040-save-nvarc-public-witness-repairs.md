# Decision 0040: Save public-witness repairs for M2 and M3

Status: Accepted
Date: 2026-09-28

After reviewing combined 005's owner-Editor result, the owner directs further
repair and one QUICK_SAVE. This authorizes exactly one private, unexecuted
`nvarc-m2-m3-combined-006` save. The owner remains responsible for any Editor
run and supplying `結果.zip`. All predecessor identities, observations and
consumed allowances remain frozen. The exact plan is
`trials/arc-agi-2-qwen35-nvarc/configs/m2-m3-combined-editor-006.json`, digest
`sha256:2479810ca715523c62263d1de9256146081edbfe3b2a3ce79af053c76d625637`.

- M2 keeps the same compact SFT export, task, source views, one TTT step,
  512-training-token ceiling, four generation calls, two sequences / 64 tokens
  / 128 DFS expansions per call, and at most eight verifications. The 6×6
  public output-shape witness and 0.02 unmasked per-token floor remain. A new
  public-demo palette witness requires every train output to retain its input
  colors, masks generation to the **transformed test input** colors in each
  source view, and accepts a completed candidate only when it uses all those
  colors. The inverse-mapped result verifier checks the original test palette.
  This repairs combined 005's concrete candidate inconsistency; it does not
  supply hidden truth, claim exact-match accuracy or promote the method.
- M3 keeps the same pinned full-vocabulary Qwen3.5-4B and two public parents,
  at most four dependent EOS-complete calls, the unchanged stage token caps
  and 28,160 total reserved-token ceiling. After a summary passes every public
  demo, the trusted rule interpreter derives the exact ordered 3×3 mix JSON
  and includes it in the mix prompt. The model still returns the mix response;
  its schema and exact composition must pass the existing semantic gate before
  either program stage. The isolated 44-invocation program suite, source pair
  filter and zero-retry policy remain unchanged.
- The parent keeps two distinct BF16 L4 workers, existing pinned private
  Datasets and competition source, offline dependencies, Internet off, USD 0,
  1,800 seconds and the previous setup/readiness/terminal reserves. On ordinary
  completion or Python failure, the notebook writes a truth-free digest-bound
  `/kaggle/working/結果.zip`; hard session termination may prevent finalization.

Complete offline staging, source/wheel and draft/approved guard checks before
reserving the sole SaveKernel request. Send it once with
`KernelExecutionType.QUICK_SAVE`, then stop at its receipt. A rejected or
uncertain request consumes the allowance. No agent execution, status/log/output
query, retrieval, monitoring, Dataset mutation, paid cost, competition
submission or automatic retry is authorized.

Status: `trials/arc-agi-2-qwen35-nvarc/combined-notebook-006-editor.md`.
