# Decision 0034: Restart the two NVARC kernels without monitoring

Status: Accepted
Date: 2026-09-26

## Context

Decision 0033 submitted M2 `nvarc-m2-source-cont-001` and M3
`nvarc-m3-teacher-small-004` version 1. Both were last observed QUEUED.
The owner then paused scheduled queries and reported stopping both sessions:
「可能遇到 bug，我停掉兩個 session，你幫我重啟，完成後不監看」.
The suspected bug and provider terminal states have not been verified.

## Decision

- Preserve both previous version-1 identities, packages and receipts. Record
  their cancellation as owner-reported, not verified model failure or zero work.
- Submit exactly one new private, Internet-disabled, USD 0 Kaggle version each
  for `danielwuu/nvarc-m2-source-cont-002` and
  `danielwuu/nvarc-m3-teacher-small-005`. Each requests NvidiaL4, verifies four
  distinct BF16 L4s, uses one L4 and retains the 1,800-second bound.
- Reuse the existing private export Dataset version 1 and existing model/wheel
  Dataset. No Dataset creation, new version, tokenizer acquisition or model
  download is authorized or needed.
- M2 retains the exact SFT export, lineage, source bundle, visible task
  `00576224` and source configuration: zero SFT, one demonstration-only LoRA
  step, at most four 64-token generation calls and 128 DFS expansions per call.
- M3 retains the pinned Qwen3.5-4B model, public training parents, prompts and
  `qwen-direct-complete-v1` profile. Four dependent calls retain input/output
  caps 4,096/512, 4,096/1,024, 4,096/3,072 and 8,192/3,072, with at most 28,160
  reserved tokens, thinking disabled and no stage retry.
- Local code changes may bind these two distinct identities and decisions;
  they do not alter the algorithm or repair an unconfirmed provider bug.
  Validate exact packages offline and reserve each submission in an atomic
  ledger before the provider request. Rejection or uncertainty consumes the
  request; there is no silent retry or identity reuse.
- Stop after retaining the submission receipts. Do not query status, logs or
  outputs after submission, retrieve results, score, or resume the heartbeat.
  Both new plans have zero currently authorized output retrievals. Await
  further owner direction for result handling. This instruction supersedes
  Decision 0033's continuous monitoring and retrieval workflow.

No paid execution, holdout evaluation, training on generated pairs, public
release, competition submission or parity claim is authorized.
