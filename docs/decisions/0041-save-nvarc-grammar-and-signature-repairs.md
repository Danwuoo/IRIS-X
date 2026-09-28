# Decision 0041: Save grammar-completion and teacher-signature repairs

Status: Accepted
Date: 2026-09-28

The owner supplied combined 006's Editor result and directs continued repair
and QUICK_SAVE if needed. Its digest-bound diagnosis shows M2's 0.02 token
floor terminating all paths at depth two and M3's one-argument program entry
contract failing at the final teacher stage. This authorizes exactly one new
private, unexecuted `nvarc-m2-m3-combined-007` save. All predecessor identities
and observations remain frozen. The exact plan is
`trials/arc-agi-2-qwen35-nvarc/configs/m2-m3-combined-editor-007.json`, digest
`sha256:3b32c1ce64662c5e108d8dfd494fa51d67b31a4da084d8d3434fb41727e9d77d`.

- M2 keeps the same SFT export, public task, source views, one TTT step and
  512-training-token ceiling. Four generation calls may each return at most
  two 64-token sequences, with no more than 128 explicit forward expansions
  each and eight total verifications. Replace the failed probability-floor DFS
  with a distinct public-grammar completion profile: the 6×6 shape forces
  row separators and EOS; the public input palette limits colors and reserves
  cells so every color occurs; among legal colors, the raw model logits choose
  the best token, with a second path starting at the next-best legal root.
  Record the selected probabilities and forced-symbol counts. This is a
  model-guided constrained candidate, not an autonomous model completion.
  No hidden truth, ARC exact-match claim or promotion enters the package.
- M3 keeps the same pinned model, public parents, four dependent EOS calls,
  per-stage token caps, 28,160 total reserved tokens, 44 isolated program
  invocation ceiling, source pair filter and zero retries. Its new distinct
  prompt gives the exact public-rule-checked 3×3 index order and a complete
  one-argument output-function example. The model must still return its own
  raw reply, pass the existing syntax and signature gate, and pass every
  sandboxed semantic challenge; no response is silently repaired.
- The parent retains two distinct BF16 L4 workers, existing Datasets and
  competition source, Internet off, USD 0 and the 1,800-second session.
  Ordinary completion or Python failure should leave a truth-free,
  digest-bound `/kaggle/working/結果.zip`; hard termination can prevent it.

After exact offline package and guard verification, reserve and submit one
`KernelExecutionType.QUICK_SAVE` request. Stop at its receipt. A rejection or
uncertain response consumes the allowance. No agent execution, status/log/
output query, retrieval, monitoring, Dataset mutation, paid run, competition
submission or automatic retry is authorized.

Status: `trials/arc-agi-2-qwen35-nvarc/combined-notebook-007-editor.md`.
