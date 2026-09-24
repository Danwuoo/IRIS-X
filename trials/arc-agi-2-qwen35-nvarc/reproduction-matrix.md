# Component completion and reproduction gaps

`implemented` means source code exists. `fixture-verified` refers only to
synthetic CPU tests. None of these labels implies model readiness or ARC score.

| Component | Source method | Implementation | Verification and gap |
| --- | --- | --- | --- |
| SDG stages and provenance | Description → summary/mix → input/output programs → pairing/filtering | Saved/fake teacher stage ledger and call reservations; Docker command bounds generated code; caller claims rejected | Stage fixtures pass; Docker daemon is absent, so container isolation and real teacher calls remain unverified |
| Source data/splits | Six concatenated SFT sources in `sft_mg.yaml` (ARC2 training, MiniARC, ConceptARC, REARC, NVARC training/full); published real + synthetic mix, 3.2M augmented samples | Streaming JSONL import, SQLite-backed parent and known-D4/color overlap, deterministic shards with per-source counts and file-backed training sequence view; clean policy rejects the known `arc2_evaluation6` source | CPU tested; no full dataset acquired, exact counts/ratios or semantic overlap unverified. Source IDs and excluded parents still require a trusted manifest |
| 16-token representation | Qwen3 selected 16 rows | Independent 16-symbol grammar; pinned Qwen3.5 tokenizer was read and all 16 exact single-row IDs verified; tied/untied HF checkpoint conversion, special-token and generation-config checks on reload/export | Compact pilot 003 verified pinned 4B source material, conversion, four-shard save/reload and local material digest; row IDs differ from Qwen3 |
| ARC full SFT | Qwen3 NeMo Megatron 4×8 H100, 12,716 steps | Local PyTorch full gradient, masks, limits, optimizer/scheduler/RNG/cursor checkpoint, inference export; separate bounded DDP worker and wall ledger | Python 3.12 torch single-process resume and two-rank CPU Gloo collective tested; only a separate two-step synthetic 4B LoRA pilot has GPU gradient/memory proof; full SFT throughput, VRAM and GPU sharding untested; no original data |
| Per-task TTT | Qwen3 rsLoRA r256 alpha32, no 4-bit | Qwen3.5 target discovery, fresh adapter state/optimizer/RNG per full task, augmented leave-one-out demos; reset on task success/failure and discarded optimizer | Compact pilot 003 completed one task-local 4B LoRA step on each of two synthetic tasks, with 20 total training tokens; full ARC task-local TTT and r256 remain untested |
| Augmentation | D4, color permutation, demo shuffle | Reversible rectangular-grid D4/color and seeded demo order | CPU round-trip incl. zero/non-square; training mixture differs from source notebook |
| Candidate decoding | Source batch DFS, cumulative NLL threshold `-log(0.2)`, sorted nonterminal siblings, EOS completion | Iterative bounded DFS with distinct expansion/sequence/token/deadline stops, safe full-prefix logit cache and named `hf-beam` alternative | Compact pilot 003 made four actual 4B generation calls and produced complete grids for two of four synthetic tests; source batch KV reuse, high-token and ARC quality remain untested |
| Rerank/top two | 8 shared augmentations and `votes - mean NLL` | Eight-view model NLL, inverse-before-dedupe, deterministic ties, missing-candidate records | Compact pilot 003 completed four actual 4B likelihood verification calls and returned two attempts for each of two tests; two other tests were marked missing; full ARC rerank quality remains untested |
| Four-L4 runtime | Persistent independent workers/dynamic queue | Exact four-L4/source gate, one load per worker, parent timeout/crash terminalization, atomic task ledger | Four synthetic worker processes and forced crash/timeout/result tested; this four-worker runtime has not run on Kaggle; adapter call budget remains proposed |
| ZIP/result/evaluator | Truth-free result, multi-test pass@2 | Existing canonical transport, workload binding, sealed per-test scorer | Compact pilot 003 produced an independently verified truth-free 4B result ZIP; no ARC scoring or holdout score |
| TRM | Independent TRM train/TTT, 10 attempts | Pinned labelled stage, source-hashed preprocess/train/eval specs, bounded invocation wrapper, ten-attempt parser and visible-input raw-tensor normalizer with fixture provenance | 30×30 encoding and launch/parser fixtures pass; upstream dependencies, checkpoint and pure inference launch semantics unverified |
| Combined submission | 2B+TRM and separate 4B-only versions | Combined candidate pool with Qwen verification plus explicit branch-priority fallback | Interface tested; no calibrated/real joint run; cannot attribute or combine original scores |

The original Qwen submission notebook uses Unsloth and a custom batch DFS. The
bounded DFS reproduces its score-pruned traversal semantics, but its safe cache
retains only complete-prefix logits to keep hybrid state isolated. It does not reproduce batch KV reuse,
runtime or the notebook's 540-second internal clock. The original 4B ARC-SFT weights cannot
be loaded into Qwen3.5. This line requires fresh training and measured
compatibility before any capability claim.

## Continuation evidence at 2026-09-23

| Component | Implemented and locally verified | Remaining gate |
| --- | --- | --- |
| Workload/result/material | Independent schema, complete terminal checkpoint, exact counters, closed model inventory and pinned base inventory checks; rehashed adversarial fixtures pass | Large real model material absent |
| DFS | Iterative >1,000-token path, distinct stop reasons and cost counters; safe full-prefix logit LRU parity with reference; canonical duplicate grids share one verification while retaining each vote | Source notebook's batched KV behavior and GPU performance unverified; hybrid KV is rejected |
| Single-process SFT | Python 3.12 torch synthetic gradient/resume passes; optional tiny Qwen3.5 compact reload and PEFT pass in a separate environment; pilot 004 completes two synthetic 4B LoRA gradients on one L4 | Full SFT memory and GPU sharding untested |
| Distributed SFT | Two-rank CPU Gloo DDP update with unused trainable visual branch, disjoint samples, exact pause/resume and forced worker failure pass; text weights update and unused visual weights stay fixed | DDP does not shard memory; actual Qwen3.5 text gradient groups, GPU and large-model path untested |
| 4B compatibility pilot | Private, offline, one-L4 LoRA package with existing Dataset v2 model/wheel digests and two-step atomic ledger; pilots 001–003 preserve separate failed identities; Decisions 0024–0025 are consumed | Pilot 004 verifies exact material, official mount, four visible L4s, offline `torchao` removal, 4B load, two synthetic PEFT steps using 16 tokens, gradient groups, adapter reset and 9,419 MiB peak allocation; zero generations; no ARC task or full-method measurement |
| 4B compact complete pilot | Private synthetic one-L4 source conversion, task-local LoRA, bounded DFS, likelihood ranking and truth-free result | Distinct pilot 003 verifies four-shard 4B save/reload, two task-local steps, four generations, two of four tests with complete grids, and independent model/result digests; no ARC accuracy or full-method measurement |
| SDG | Saved/fake stage provider, stable stage identity, failed/duplicate call accounting and fail-closed caller claims pass | Docker launcher flags tested; daemon absent, no real sandbox integration or teacher call |
| TRM | Pinned source hash binding, inference-only checkpoint/test entry and CPU fake-source call-order harness, bounded invocation fixture, ten-attempt parser and truth-free raw-tensor normalization pass | `argdantic`, `numba`, `hydra` and model checkpoint missing; actual upstream CUDA inference remains unverified |

The table above supersedes earlier implementation-status cells for this
continuation. The reviewed historical version remains described above.
