# Decision 0033: Execute the NVARC source continuation and direct teacher

Status: Accepted
Date: 2026-09-26

## Context

Decision 0032 is consumed. Its retained M2 export is verified, but its source
solve failed before TTT because the wheel lacked pinned source material.
Its four M3 replies were truncated and produced no accepted synthetic pairs.
Local repairs and deployment tests are recorded in the
[continuation plan](../plan/2026-09-26-nvarc-source-teacher-continuation.md).

After directing work onto `main`, the owner explicitly instructed:
「參考之前成功的案例，執行 kaggle 並繼續開發完成 nvarc」.
This is new execution authority for the reviewed continuation, not reuse of
any consumed run. The implementation remains on `main`.

## Decision

- Materialize only the small tokenizer/configuration files from the already
  pinned Qwen3.5-4B revision and verify the existing model-manifest hashes.
  Use them for local prompt/template preflight without model calls.
- Create one private Dataset, `danielwuu/irisx-nvarc-m2-sft-export-002`,
  containing the verified retained HF export and truth-free training lineage.
  Preserve the export digest
  `sha256:481d9f12d573b39b0703e47b5f8f6f518a7ccd7847824ffb3f0fb96b11f2c3e6`.
  Reuse existing model/wheel Datasets without new versions.
- Submit `danielwuu/nvarc-m2-source-cont-001` once, private and Internet
  disabled, with four distinct BF16 L4s and one L4 used, at most 1,800 seconds
  and USD 0. Reuse the exact visible task `00576224` and source configuration:
  zero SFT steps, one demonstration-only LoRA step, at most four 64-token
  generation calls and 128 DFS expansions per call. Bind a distinct
  continuation chain to the original training identity and immutable export.
  No optimizer-resume or repaired-original-run claim is permitted.
- Independently submit `danielwuu/nvarc-m3-teacher-small-004` once with the
  same private, offline, four-L4, 1,800-second and USD 0 limits. Use the pinned
  full-vocabulary Qwen3.5-4B and the same two public training parents.
  The distinct `qwen-direct-complete-v1` profile disables thinking and permits
  four dependent calls. Input/output caps are 4,096/512, 4,096/1,024,
  4,096/3,072 and 8,192/3,072: at most 28,160 reserved tokens. A rejected
  stage consumes its call and stops downstream stages without retry.
- Reserve each mutation in an atomic local ledger before issuing it. Each
  kernel identity permits one submission and one terminal output retrieval;
  rejection or failure consumes the submission. Record exact approved plan,
  notebook, wheel, Dataset and provider receipt bindings before and after
  submission. Do not mutate an executed identity or silently retry it.
- Continue local result verification, source-chain validation and sandboxed
  replay of complete teacher programs using the five fixed seeds. Retain
  program, pair and training-message artifacts with provenance. Structural
  pair acceptance does not establish semantic quality, upstream teacher
  parity, ARC accuracy or original-scale NVARC completion.
- The owner explicitly selected 「這次由你查到終態並繼續開發」 for this
  batch, superseding the prior wait-for-owner terminal-report preference.
  Perform bounded status checks, retrieve each terminal version once and
  continue local verification/development. No competition submission, heldout scoring, paid execution,
  public release or training on newly generated pairs follows from this batch.

The two inert drafts remain unchanged. Separate authorization bindings and
approved packages implement this decision; approved package hashes must be
retained before provider mutation. Ordinary local repairs, tests and analysis
remain authorized without additional decision records.
