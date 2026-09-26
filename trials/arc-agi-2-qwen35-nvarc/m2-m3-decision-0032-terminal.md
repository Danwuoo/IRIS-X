# Decision 0032 terminal evidence and local continuation

Both version-1 submissions and their single terminal retrievals are consumed.
This record introduces no external execution authority. Retrieved bytes remain
unchanged under `.irisx/arc-agi-2/qwen35-nvarc/m2-m3/`.

## M2: training/export complete, source solve failed

`fsdp-sft-retrieved-002/nvarc-m2-fsdp-sft-002/` contains eight full-parameter
optimizer steps, 2,578 training input tokens and 32 model forwards. The step-1
pause, four-rank restore traces, final step-8 manifest and export chain agree.
Four distinct L4s and separate scratch passed the notebook gates. Losses were
finite; each rank observed 522 nonzero gradient tensors.

The four HF shards independently match their material manifest. Export identity:
`sha256:481d9f12d573b39b0703e47b5f8f6f518a7ccd7847824ffb3f0fb96b11f2c3e6`.
Training identity:
`sha256:40804d408005b666cb377aab623bd6b0edcfbcdaa4743049d26e7e65500f5fc4`.
Final checkpoint manifest:
`sha256:e733fadbb2256ff869c91829b8430ec8e9c4a82c33a27e5afc97e9ef6bd40d06`.
Optimizer shard bytes existed only in that session's scratch. The HF export
is usable for a separately authorized inference/TTT continuation, not for
reconstructing the discarded optimizer state.

The installed-wheel source loader computed a repository-relative manifest
path absent from the Kaggle package. It raised `NVARC source manifest is
missing` in `qwen_cell("arc_loader.py")`, before the task-local update. There
is no `source-result.json` or `run-chain.json`. Hardware, scratch and SFT are
not the failed stages. The new `verify_training_export` entry checks this
partial milestone without weakening the original full-chain verifier.

## M3: four calls complete, no accepted SDG artifact

`teacher-retrieved-003/m3-teacher-small-003/` retains four raw responses and
their stage ledgers. Actual usage is 7,740 input plus 4,096 output tokens,
11,836 total, against a 20,480-token reservation. Every answer reached the
1,024-output-token ceiling. Neither program reply has a closed code block;
the output reply lacks the required complete `generate_puzzle_output` entry.
No new sandbox- and pair-filter-accepted SDG data exists.

The legacy adapter forwarded any nonempty reply to the next stage. Thus an
incomplete description was still used as downstream input. The next local
profile retains raw responses separately from validated stage content,
records EOS/length/other termination, and stops dependent calls on rejection.
The old replies and their original statuses are not rewritten.

## Next local work

The [continuation plan](../../docs/plan/2026-09-26-nvarc-source-teacher-continuation.md)
defines a source-only M2 continuation and a direct-response M3 profile.
Their draft identities are distinct and inert. They do not authorize another
Dataset upload, kernel, retrieval, teacher call, ARC score or method promotion.
