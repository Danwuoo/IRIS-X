# Component completion and reproduction gaps

`implemented` means source code exists. `fixture-verified` refers only to
synthetic CPU tests. None of these labels implies model readiness or ARC score.

| Component | Source method | Implementation | Verification and gap |
| --- | --- | --- | --- |
| SDG stages and provenance | Description → summary/mix → input/output programs → pairing/filtering | Saved-response replay with prompt/response digest and call counters; isolated-executor contract rejects unattested execution | Fixture-ready; teacher/backend, generated-program sandbox and real dataset lineage absent |
| Source data/splits | Published real + synthetic mix, 3.2M augmented samples | Streaming JSONL import, SQLite-backed parent and known-D4/color overlap, deterministic shards and file-backed training sequence view, clean and competition policies | CPU tested; no full dataset acquired, exact mixture/semantic overlap unverified |
| 16-token representation | Qwen3 selected 16 rows | Independent 16-symbol grammar; pinned Qwen3.5 tokenizer was read and all 16 exact single-row IDs verified; tied/untied HF checkpoint conversion | Grammar and tokenizer IDs checked; torch conversion/reload with 4B weights untested; row IDs differ from Qwen3 |
| ARC full SFT | Qwen3 NeMo Megatron 4×8 H100, 12,716 steps | Real local PyTorch full gradient, masks, limits, optimizer/scheduler/RNG/cursor checkpoint, inference export | Tiny transition model CPU tested; Qwen3.5 hybrid gradient, throughput/VRAM, multi-GPU full training untested; no original data |
| Per-task TTT | Qwen3 rsLoRA r256 alpha32, no 4-bit | Qwen3.5 target discovery, fresh adapter state/optimizer/RNG per full task, augmented leave-one-out demos | Data isolation tested; PEFT attachment and actual 4B gradients untested |
| Augmentation | D4, color permutation, demo shuffle | Reversible rectangular-grid D4/color and seeded demo order | CPU round-trip incl. zero/non-square; training mixture differs from source notebook |
| Candidate decoding | Source batch DFS and score threshold | Bounded HF beam search, EOS/full-grid gate, call/sequence accounting | Fixture multi-view tested; DFS batch behavior and generation quality untested; major method gap |
| Rerank/top two | 8 shared augmentations and `votes - mean NLL` | Eight-view model NLL, inverse-before-dedupe, deterministic ties, missing-candidate records | Fixture verified; real NLL numerics untested |
| Four-L4 runtime | Persistent independent workers/dynamic queue | Exact four-L4/source gate, one load per worker, parent timeout/crash terminalization, atomic task ledger | Four synthetic worker processes and forced crash/timeout/result tested; new identity not run on Kaggle; adapter call budget remains proposed |
| ZIP/result/evaluator | Truth-free result, multi-test pass@2 | Existing canonical transport, workload binding, sealed per-test scorer | Fixture E2E and boundary tests; no real result or holdout score |
| TRM | Independent TRM train/TTT, 10 attempts | Pinned training-data adapter, launch spec, candidate normalizer, Qwen verification integration | 30×30 encoding and fixture selection tested; no real TRM checkpoint or upstream run |
| Combined submission | 2B+TRM and separate 4B-only versions | Combined candidate pool with Qwen verification plus explicit branch-priority fallback | Interface tested; no calibrated/real joint run; cannot attribute or combine original scores |

The original Qwen submission notebook uses Unsloth and a custom batch DFS. The
current HF beam implementation is a concrete, bounded multi-candidate solver
but is **not exact DFS reproduction**. The original 4B ARC-SFT weights cannot
be loaded into Qwen3.5. This line requires fresh training and measured
compatibility before any capability claim.
