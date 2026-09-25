# NVARC M2/M3 terminal repair — bounded new identities

Status: local repairs and inert packages complete; [Decision 0032](../decisions/0032-authorize-nvarc-m2-m3-terminal-repairs.md)
now authorizes exactly one new bounded private kernel and one terminal
retrieval for each distinct M2 `002` and M3 `003` identity. Decision 0031's M2 SFT `001` and M3 teacher `002`
version 1 identities, pushes and single retrievals are consumed. The
independent truth-free audit is retained locally as
`.irisx/arc-agi-2/qwen35-nvarc/m2-m3/decision-0031-terminal-audit.json`
(SHA-256 `2ffb584f165230927137024d41ab0491a18e7defcf840383a03860fab52769d3`).

## Observed failures

- M2 `nvarc-m2-fsdp-sft-001` ended `KernelWorkerStatus.ERROR`. Four distinct
  BF16 L4s were present, but `/kaggle/working` reported **20,939,517,952
  free bytes**, below the approved notebook's 60,000,000,000-byte checkpoint
  gate. It stopped before model load, optimizer update or SFT checkpoint.
  [Kaggle's Notebook documentation](https://www.kaggle.com/docs/notebooks)
  states that `/kaggle/working` has 20 GB of saved output and that additional
  scratch space outside it is not retained. The actual scratch capacity of a
  future four-L4 allocation is unmeasured.
- M3 `nvarc-m3-teacher-small-002` reached `KernelWorkerStatus.COMPLETE` as a
  notebook, but its first stage failed after one ledger reservation with
  `AttributeError`. It completed **zero model calls and zero responses**;
  provider-reserved tokens remained zero. Local Transformers 5.8.1 returns a
  `BatchEncoding` by default from `apply_chat_template(...,
  return_tensors="pt")`, while the adapter had read `.shape` as if it were a
  tensor. A real Qwen3.5 tokenizer regression reproduces that mismatch.

## Local repairs

`BoundedLocalHFTeacher` now asks the pinned tokenizer for
`return_dict=False`, validates the resulting two-dimensional token tensor,
and retains the existing per-call and total token ceilings. The teacher entry
writes its result and raises on an incomplete four-call batch, so a failed
first stage cannot appear as a successful kernel. The strict tokenizer test
passes on the same Transformers 5.8.1 release.

The FSDP worker can now restore a step-1 full model/optimizer/RNG/scheduler
checkpoint from session-only scratch, verify the restored weight fingerprint,
retain its manifest and a resume trace, then remove that first shard set
before the final checkpoint is written. A two-rank real Qwen3.5 CPU test
executed continuous and interrupted/resumed training, removed the old shard
set after reload, exported matching HF weights, and checked tampering. The
`nvarc_m2_fsdp_sft_notebook_002` adapter proposes `/kaggle/temp` for the
full optimizer checkpoint and retains only the trained HF export (about 7.81
GB), first/final checkpoint manifests, traces, counters, source result and
run chain under `/kaggle/working`. The actual DCP shards would be lost when
the session ends, so an offline verifier can check the saved manifests and
export, but **cannot independently reconstruct the optimizer state after
retrieval**. This is an explicit evidence limit, not a claim of retained
optimizer checkpoint bytes.

## Reviewable new packages

| Bound | M2 scratch repair | M3 tokenizer repair |
| --- | --- | --- |
| Identity | `nvarc-m2-fsdp-sft-002` | `nvarc-m3-teacher-small-003` |
| Inert package | `.irisx/arc-agi-2/qwen35-nvarc/m2-m3/fsdp-sft-storage-review-003/` | `.irisx/arc-agi-2/qwen35-nvarc/m2-m3/teacher-repair-review-004/` |
| Draft SHA-256 | `a94a7107fab2c5a210942977ae1841ee59cba1a4f701d67fe935937c74e7da03` | `d758d1482f45f239cdc5580b24670c648eeaff8205ce2677ad04dd34baffcbea` |
| Embedded plan SHA-256 | `652d5d42c60938e97f79b7796dc5249def5cc047321c932d96afd04ec0d71303` | `3c9206eb3388b50c741efda4d26a2b509ad157143a5c78f0583faafe478d3cfe` |
| Notebook SHA-256 | `4dc03f89fa914da6e0575870b8b3458a487a69ac8c60b107a365bb0a83396e1d` | `968c400da6ccb815c21eec430247193aecc57140578be8045c2f68ad87940d08` |
| Shared wheel SHA-256 | `d1c3d225be6a6b60ef879936b34273931192beeeb09e1ee92501da0c9e43bb6e` | same |
| Exact work | Same eight ARC train parents, 128 augmented train episodes, 8 full-parameter steps, 2,578 input tokens, step-1 resume, final export/reload and one visible dev source solve with at most four 64-token generations | Same two public ARC train parents, four pinned source-prompt calls, each at most 4,096 input plus 1,024 output tokens; 20,480 reserved ceiling |
| Provider limits | One private Internet-disabled Kaggle four-L4 kernel, at most 2,700 seconds; `/kaggle/working` at least 11 GB free, separate scratch at least 55 GB free, retained output at most 12 GB | One private Internet-disabled Kaggle four-L4 kernel, one L4 used, at most 1,800 seconds |
| Retention | HF trained model, source result, manifests, traces and run chain; no DCP shard bytes after session | Private raw responses, usage and stage ledgers |
| Common limits | One accepted version and one terminal retrieval per identity, no retry or Dataset mutation, USD paid 0 | same |

Both package preflights passed with `approved: false`, an unpushable kernel
ID, zero external calls and a notebook guard that stops before model work.
The Kaggle scratch gate and full 4B save/export path are **unexecuted** in
this repair. The source solve may return no complete grid. M3 is still a
different local Qwen teacher from the upstream tutorial and has generated no
new accepted SDG pairs. Neither package allows heldout scoring, competition
submission, public release, paid API, original-scale H100 training or a
change to the frozen ARC parent split.

AGENTS.md and `docs/development/data-and-execution-policy.md` require new
owner direction for these new external identities and resource bounds. The
owner supplied it for the exact draft SHA-256s above through Decision 0032;
Decision 0031 cannot be reused to launch either repair. Submission receipts
and terminal outcomes must be appended without rewriting these frozen drafts.
