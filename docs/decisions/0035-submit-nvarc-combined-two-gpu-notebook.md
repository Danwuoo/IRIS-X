# Decision 0035: Submit the combined two-GPU NVARC notebook

Status: Accepted
Date: 2026-09-26

## Context

The owner requested combining M2 and M3 in one notebook using two GPUs,
approved a plan under `docs/plan/`, and assigned implementation to
`gpt-6-sol / xhigh`. The local implementation and offline verification were
committed as `6d8acf096e0de5ded5b74cd8905522adaf36b13d`.
The owner then instructed: 「參考之前成功案例提交 kaggle notebook」.
This decision authorizes that submission. It preserves Decision 0034's
submit-only preference and does not query its two existing sessions.

## Decision

- Submit exactly one new private Kaggle notebook version under
  `danielwuu/nvarc-m2-m3-combined-001`, with that same title, Internet disabled
  and USD 0 paid cost. Reserve the sole request in an atomic local ledger;
  rejection or uncertainty consumes it and does not authorize another request.
- Bind the approved plan to Decision 0035 and the unchanged original inert
  draft digest `sha256:2052311757ab3922473e0476801dde4df551e0a037795b64025fa5f17c54e0ef`.
  Preserve the draft, old submitted packages and identities. Activation may
  change authorization/transport fields and guards, not scientific limits.
- Reuse the existing `danielwuu/irisx-arc-agi-2-trial-002-smoke-001` model/wheel
  Dataset and `danielwuu/irisx-nvarc-m2-sft-export-002` export Dataset version 1.
  Mount `arc-prize-2026-arc-agi-2` as in successful L4 submissions. Do not
  acquire models, update Datasets, expose evaluator truth or score ARC tasks.
- Request `NvidiaL4` using the successful CLI transport. Select exactly two
  distinct BF16-capable L4 GPU UUIDs, one per branch. The provider allocation
  may contain four GPUs; this decision does not claim an exactly-two-L4
  provider offering. Verify each worker's sole visible device before model work.
- Retain the shared offline dependency setup, including removal of optional
  incompatible `torchao`, pinned wheels, exact mount resolution, branch-local
  failures, bounded logging and process cleanup. Bound the whole notebook to
  1,800 seconds, including at most 300 seconds setup and 30 seconds reserved
  for terminal cleanup. Pass the same 1,800-second bound to Kaggle.
- M2 uses the retained SFT export
  `sha256:481d9f12d573b39b0703e47b5f8f6f518a7ccd7847824ffb3f0fb96b11f2c3e6`,
  training lineage
  `sha256:40804d408005b666cb377aab623bd6b0edcfbcdaa4743049d26e7e65500f5fc4`
  and source bundle
  `sha256:625b010706dabfce5df58c036f5921af4e782da133bd27038bc442abdc79e1a4`.
  Retain visible task `00576224`, zero new SFT, one demonstration-only LoRA
  step, at most four generation calls, 64 new tokens and 128 DFS expansions
  per call, and the existing source configuration and ranking limits.
- M3 uses full-vocabulary `Qwen/Qwen3.5-4B` at revision
  `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`, base manifest
  `sha256:8f27407e1b0ee4dd7a5b4d62d39af9b356ba86b5701dd93eafba052febe9c72f`,
  public parents `833966f4` and `6150a2bd`, and the unchanged direct prompts.
  Four dependent greedy calls with thinking disabled retain input/output
  caps 4,096/512, 4,096/1,024, 4,096/3,072 and 8,192/3,072, at most 28,160
  reserved tokens, with no stage retry or training on generated pairs.
- Exact approved plan, notebook, metadata, runtime wheel and preflight hashes
  must be retained before the provider request. Use the successful UTF-8
  logged CLI transport. Existing local credentials may be refreshed for this
  submission without printing secret values; this is not kernel monitoring.
- Stop after saving the submission receipt. Do not query status, logs or
  outputs, retrieve results, resume the heartbeat, retry a branch/kernel,
  publish, submit to the competition, evaluate holdout or claim promotion.
  Output retrieval authority remains zero pending new owner direction.

The implementation remains under the existing NVARC trial. Local offline
validation does not establish successful GPU execution of the combined flow.

## Exact submission record

The immutable package bindings and transport outcome are retained in
`trials/arc-agi-2-qwen35-nvarc/combined-notebook-001-submission.md` and the
ignored local atomic execution ledger. Neither a receipt nor local preflight
is evidence of notebook startup or completed model work.
