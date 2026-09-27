# Decision 0038: Save paired NVARC tasks with a downloadable analysis ZIP

Status: Accepted
Date: 2026-09-27

The owner instructs: 「參考之前的案例，兩個任務掛到同一個 notebook，最後產出結果.zip
供我下載讓你分析。提交 quick save 就好，不需要 run」. This authorizes one private
QUICK_SAVE of the distinct `nvarc-m2-m3-combined-004`. The owner starts it in
Editor and supplies the resulting ZIP. No further confirmation is required.

The new owner-Editor envelope combines the reviewed local proposals from
`5fc5ed6`. Preserve both inert proposals and all previous identities/packages.
The exact plan is `trials/arc-agi-2-qwen35-nvarc/configs/m2-m3-combined-editor-004.json`,
canonical digest `sha256:7abcb83ec8824db7822349a5e735efb532caa1a56ba52a4c619ba1afe049550b`.
Its parent guard is separate from every consumed execution envelope.

- M2 uses the retained digest-bound eight-step SFT inference export and the same
  visible task, source views, compact vocabulary, seeds and LoRA settings. One
  task-local adaptation is shared and frozen across thresholds 0.2, 0.1 and
  0.02. Limits are one TTT step, 512 training tokens, twelve generation calls,
  two sequences per call, 64 new tokens, 128 DFS expansions per call, 1,536 DFS
  forwards and at most 24 verification calls / 192 verifier forwards. No SFT
  resume, ARC exact-match scoring or promotion is authorized.
- M3 uses the unchanged pinned full-vocabulary Qwen3.5-4B material and two public
  training parents. The restricted `qwen-rule-contract-v3` profile checks every
  public demo, exact ordered composition, EOS and complete Python. At most four
  dependent calls reserve at most 28,160 tokens with unchanged per-stage caps;
  the first rejected stage stops its dependent pipeline without retry.
  Complete replies may undergo at most 44 isolated program invocations for a
  3x3 composition and five seed pairs. The pinned SDG source filter and cached
  NumPy are carried separately from the frozen Qwen source bundle. Generated
  Python never runs on the trusted host. Missing namespace/dependency support
  yields a retained rejection, not a relaxed sandbox or accepted pair.
- Retain two distinct BF16 L4 workers, existing private Datasets and official
  competition source, offline pinned dependency setup, Internet disabled,
  USD 0, the 1,800-second session, 300-second setup/readiness and 30-second
  terminal reserve. Ten terminal seconds are reserved for ZIP finalization.
- The notebook writes `/kaggle/working/結果.zip` on normal completion or ordinary
  Python failure. It contains raw replies, candidate/semantic results, usage,
  hardware, lineage, partial failures and a closed digest inventory; it omits
  model weights, optimizer shards, dependencies and evaluator truth. Evidence
  is capped at 64 MiB. Provider termination can prevent finalization.
- Complete offline verification first. Reserve the sole save before exactly
  one `SaveKernel` request with `KernelExecutionType.QUICK_SAVE`. A credential
  refresh may precede it without exposing credentials. A rejected or uncertain
  request consumes this save; there is no automatic retry or run fallback.
  Stop at its retained receipt. Agent execution, status/log/output requests,
  retrieval, Dataset mutation, acquisitions, monitoring, publication and
  competition submission are not authorized.

Status and the exact saved package bindings are retained in
`trials/arc-agi-2-qwen35-nvarc/combined-notebook-004-editor.md`.
