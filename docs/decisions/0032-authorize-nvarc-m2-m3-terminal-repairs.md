# Decision 0032: Authorize bounded NVARC M2 scratch and M3 teacher repairs

Status: Accepted
Date: 2026-09-25

## Context

Decision 0031's `nvarc-m2-fsdp-sft-001` and
`nvarc-m3-teacher-small-002` version 1 attempts and their single terminal
retrievals are consumed. The [terminal repair plan](../plan/2026-09-25-nvarc-m2-m3-terminal-repair.md)
and truth-free audit preserve the failures: M2 stopped at the working-disk
gate before model load; M3 failed on the first tokenizer call with zero
completed responses. Local scratch/checkpoint and tokenizer repairs have
passed their relevant CPU tests and offline package preflights. Neither
repair has run on Kaggle.

The owner explicitly answered 「批准 M2 與 M3（建議）」 to the integrated request
that specified both new identities and the limits below. This decision binds
M2 draft `m2-fsdp-sft-draft-002.json` SHA-256
`a94a7107fab2c5a210942977ae1841ee59cba1a4f701d67fe935937c74e7da03`
and M3 draft `m3-teacher-draft-003.json` SHA-256
`d758d1482f45f239cdc5580b24670c648eeaff8205ce2677ad04dd34baffcbea`.
The reviewed inert packages have plan SHA-256
`652d5d42c60938e97f79b7796dc5249def5cc047321c932d96afd04ec0d71303`
and `3c9206eb3388b50c741efda4d26a2b509ad157143a5c78f0583faafe478d3cfe`,
respectively. Their notebook SHA-256s are
`4dc03f89fa914da6e0575870b8b3458a487a69ac8c60b107a365bb0a83396e1d`
and `968c400da6ccb815c21eec430247193aecc57140578be8045c2f68ad87940d08`;
both use runtime wheel SHA-256
`d1c3d225be6a6b60ef879936b34273931192beeeb09e1ee92501da0c9e43bb6e`.
Approved-package hashes will differ because authorization is embedded and
must be recorded before submission.

## Decision

- Authorize exactly one private, Internet-disabled Kaggle four-L4 kernel
  submission as `danielwuu/nvarc-m2-fsdp-sft-002`, with maximum wall time
  2,700 seconds and USD 0 paid cost. Reuse the existing private compact-model
  and offline-wheel Datasets and the official competition source mount only
  for the established hardware transport; the embedded frozen public ARC
  training sequences are the training data. Require four distinct BF16 L4s,
  a separate scratch device with at least 55 GB free and working space with
  at least 11 GB free before model load. On eight frozen training parents,
  permit 128 train-only augmented episodes, eight unpacked full-parameter
  optimizer steps and at most 2,578 scheduled input tokens. Keep the eight
  disjoint dev parents, evaluation6 and holdout derivatives out of training.
  Save after step one, restart and restore optimizer/RNG/cursor, finish and
  export/reload the trained model. Permit one truth-free visible dev source
  solve through task-local TTT, DFS, inverse/dedupe and source ranking, with
  at most four generation calls of 64 new tokens each. Retain at most 12 GB
  in working output: HF export, manifests, trace, source result and run chain.
  Full optimizer DCP shards live only in session scratch and cannot be
  independently rebuilt from the retained export.
- Independently authorize exactly one private, Internet-disabled Kaggle
  four-L4 kernel submission as `danielwuu/nvarc-m3-teacher-small-003`, using
  one L4, maximum wall time 1,800 seconds and USD 0 paid cost. Reuse the
  existing private pinned Qwen3.5-4B full-vocabulary model and offline-wheel
  Dataset. On the same two frozen public ARC training parents, permit four
  source-prompt teacher calls, each at most 4,096 input plus 1,024 output
  tokens, with at most 20,480 total tokens reserved. Retain private raw
  responses, actual usage and stage ledgers. This local Qwen teacher differs
  from the upstream NeMo-Skills GPT-OSS-120B tutorial; no parity claim follows.
- Each identity permits one accepted kernel version and one terminal output
  retrieval. A provider rejection, hardware/disk-gate failure or notebook
  error consumes that identity. No retry, Dataset mutation, paid API,
  competition submission, heldout scoring, public release, original-scale
  H100 training or additional data acquisition is authorized. Preserve exact
  package, receipt, failure and measured step/call/token counts. Per the
  owner's standing instruction, stop monitoring after submission until the
  owner reports the terminal state.
