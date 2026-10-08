# IRIS-X uncapped owner run: complete engineering result, unchanged exposed-development accuracy

Date: 2026-10-08. Analysis is local and read-only with respect to original evidence and repository. No returned Python or notebook code was executed. No new GPU/model calls, provider queries, official submission, source/package changes, or hidden/locked-confirmation truth reads occurred.

## Bottom line

The owner-returned run completed all of the promised workload: four original native TTT128 epochs, six searches, all 24 batches / 96 generation views, all returned candidates and all eight-view verification work. Independent CPU verification passes every worker and reproduces input transformations, event accounting, retained score readbacks and the original ranking.

Descriptive exact-match accuracy on the same previously exposed four-task/six-test public-development footprint is **top-1 1/6; top-2 1/6; full retained-pool oracle 1/6**. The run produces 41 distinct retained candidates and 12 actual guess slots. The full retained pool contains no correct answer for the other five tests, so changing only the final ranking cannot fix those five cases using these candidates. This is a proposal/representation/adaptation bottleneck for this run, not evidence that a particular replacement architecture will succeed.

Removing program resource ceilings solved the earlier evidence/runtime interruption and provided a complete observation. It did not, in this small unpaired observation, provide evidence of improved exact-match quality. Do not turn the shared 1/6 outcome into a causal claim that more search never helps or TTT128 is equivalent to TTT64.

## Provenance and preservation

- Owner-returned Library item: libfile_f73c25e003cc819191a7227ff142cb5f, backing file file_0000000005f88230bd969f8d3fbee3cf, Library version 0.
- Original filename: stage4-uncapped-20261008-001.zip.
- Exact original size: 9,745,665 bytes. SHA-256: `3452843d477778b1f17ae42666c987fa3ad54072c54da72b08de872b17b8190a`.
- ZIP safety: regular safe relative members; no duplicate members, traversal, encryption, or symlinks. The trusted streaming verifier verifies 262 data members, 116,680,259 data bytes, plus the 36,833-byte embedded manifest. Total expanded bytes: 116,717,092. Ten excluded entries are documented compiler/bytecode cache directories, not missing output/training evidence.
- Exact saved plan: `1e8d68e6c981e9511e9712bacc64c55ae96f42e985f1b2232230ea114d782b47`; returned plan and screen bytes match the pre-run package. All 87 payload bindings verify, and every file in the original saved runtime package is byte-identical in the returned material.
- Runtime source commit: `491a0831fca82829f66d5c66d0182d4680b86b4e`. Transport commit: `9c9e60f`. Analysis validator checkout: `7ac9cca0795e8d8f98f1e2cdb7bcb546fbe30b67`.
- Saved private notebook: [danielwuu/stage4-uncapped-ttt128-20261008-3baff209a1](https://www.kaggle.com/code/danielwuu/stage4-uncapped-ttt128-20261008-3baff209a1), numeric ID 137591923, saved version 1. Prior retained receipt establishes QUICK_SAVE at 03:58:30 UTC and exact executable-source/private/Internet-OFF readback at 03:58:37. This analysis did not query current provider status. The owner-run artifact is bound to that saved runtime through exact bytes; it is not a fresh provider-side attestation of the Editor session or runtime/version state.
- Saved notebook SHA-256: `e2e3dbf5599a4edbe8018d871328ae368427724b6805efc813b6460622e6adad`; package manifest SHA-256: `bda7f8fde5d1b8b274bf36d9185b879f29899fc7702069d5831f7bc9c5edc989`.

The original ZIP remains under `original/`. Derived data are under `extracted/`; analysis receipts and scripts are siblings. These files are separate from the immutable repository and prior E12/E13 evidence.

## What actually ran

The retained hardware evidence reports four distinct NVIDIA L4 GPUs, each 23,659,151,360 bytes (23,034 MiB), with BF16 supported; Torch 2.8.0+cu128 and CUDA 12.8. Runtime source enforces Python 3.11.13; worker banners report Unsloth 2025.9.7, Transformers 4.55.4 and Triton 3.4.0. Four workers map to distinct GPU UUIDs and each reports one native model instance.

The model is pinned `sorokin/qwen3_4b_grids15_sft139/transformers/bfloat16/1` (instance version 627758), with material digest `sha256:27de51ef22658a0cce3a9fc04fac8fc456165645e2665a82b215f72e20194b03`. The original rank-256 rsLoRA, alpha 32, zero dropout, module targets, BF16 parameters, native full 128-row epoch and native 128-step scheduler are preserved. Ten model-file hash checks are recorded by the runtime; model weight files themselves are not included in the returned archive, so they cannot be rehashed locally from this output.

The coordinator reports `complete`, no errors and 1,677.447450161 host seconds (27 min 57.45 s). Worker durations overlap and sum to 4,529.19 seconds; they must not be added to infer elapsed runtime. Search timestamps span 06:09:38.444 to 06:27:42.244 UTC. Four-device wall-time multiplication is 1.86383 nominal device-hours, not a measured Kaggle quota charge or billing statement. The terminal reports USD 0; paid scaling OFF and quota review are owner declarations in the start record, not independently re-observed account state.

All worker exit codes and coordinator return code are zero. Owned process-group cleanup verifies within the artifact. This does not establish that the broader Kaggle Editor session has been stopped.

## Training: complete and observable

| Task | Updates | Input tokens | Supervised tokens | Training host s | Peak CUDA allocated GiB |
|---|---:|---:|---:|---:|---:|
| 195c6913 | 128 | 442,624 | 220,160 | 381.106 | 14.358 |
| aa4ec2a5 | 128 | 408,320 | 203,008 | 328.853 | 13.856 |
| a47bf94d | 128 | 373,632 | 185,664 | 305.282 | 13.502 |
| a25697e4 | 128 | 364,416 | 181,056 | 313.868 | 13.710 |
| Total | 512 | 1,588,992 | 789,888 | 1,329.109 summed | Not additive |

Every worker has 128 completed forwards, backwards and optimizer updates, one optimizer construction, one unchanged native sampler iteration, full callback/scheduler trace, and no training-phase generation or teacher calls. All 506 finite Adam states reach step 128, including the schedule's zero-learning-rate update. All 506 trainable tensor records change during training and return exactly to their original baseline. The 528,564,224 trainable-element layout and all trained/inference/reset transitions verify. Inference uses the same unchanged post-TTT tensor inventory per task.

All four first-16 versus last-16 mean training losses fall: 0.05930→0.001674, 0.01390→0.004000, 0.02328→0.001176, 0.03274→0.000359. This establishes successful optimization on augmented demonstrations. It does not establish rule discovery or generalization to unseen test outputs. There is no no-TTT control in this run, so TTT's incremental contribution is unmeasured.

Seven synthetic cache/reset control forwards per worker pass (28 total). Cache/deep/sibling comparisons pass and reset prefill vectors are bitwise equal. Per-worker process peak host RSS is about 5.95 GiB; these are not whole-system peaks. CUDA allocated peaks are not reserved-memory or total-device consumption measurements.

## Search and verification: full declared coverage

| Task/test | Search host s | Generation forwards | Raw occurrences | Unique candidates | Views with returned sequences / 16 |
|---|---:|---:|---:|---:|---:|
| 195c6913 / 0 | 530.065 | 5,857 | 6 | 6 | 5 |
| 195c6913 / 1 | 477.499 | 4,715 | 12 | 10 | 10 |
| aa4ec2a5 / 0 | 278.840 | 3,146 | 17 | 3 | 16 |
| a47bf94d / 0 | 421.142 | 4,508 | 9 | 8 | 9 |
| a25697e4 / 0 | 512.470 | 5,522 | 14 | 8 | 13 |
| a25697e4 / 1 | 425.621 | 4,794 | 8 | 6 | 7 |

All six tests terminate with `all_source_batches_completed`. Each completes exactly four four-view source batches, with no unfinished or undispatched view, no raw unprocessed candidate, no invalid candidate, no missing guess slot and no artificial duplicate filler. All 96 generation views were dispatched and completed; 60 views return sequences and 36 return none. An empty completed view is not a skipped view or a timeout.

Aggregate work:
- 28,542 completed/reserved generation forwards, with 494,120 physical generation input tokens.
- 82 completed/reserved verification forwards, with 1,585,888 physical verification input tokens.
- 66 raw sequence occurrences, 41 unique candidates and 25 repeated occurrences.
- Exactly eight verifier rows per unique candidate: 328 rows, in two four-row model calls per new candidate. Duplicate occurrences reuse the same completed score readbacks.
- 86,218 complete chain-bound inference events, 100,109,230 bytes (95.472 MiB). Every worker's inference ledger exceeds the historical 8 MiB ceiling, and the largest is 37,243,215 bytes. These complete streams directly demonstrate that the old E13 ledger interruption is absent.

The aggregate exclusive worker host scopes are generation 2,275.670 s, training 1,329.066 s, load 397.568 s, verification 362.119 s, controls 20.613 s, preparation 6.300 s and parse/dedup/ranking below one second. These are overlapping workers' host scopes, not GPU kernel timings. Missing export/reset scopes are null, not measured zero. Generation is the largest observed compute phase; changing a negligible-time ranker alone does not solve the dominant execution cost or the missing-correct-candidate issue.

## What “uncapped” establishes and what it does not

All resource-policy fields for timers, model-forward counts, physical input tokens, processed candidates, event/ledger bytes and observer rows are null. The source adapter replaces only the original dual wall-clock condition (540 seconds and end-time) and verifies that restoring it reproduces the original inference AST. No source files are rewritten.

Scientific constraints remain: cumulative probability floor p=.2, original traversal/ranking, sixteen generation views, four-view batches, interleaved eight-view verification, 8,192-token context, 931 answer tokens, legal 30×30 grid grammar and two displayed guesses. The actual source prunes cumulative NLL at −log(.2). Removal of elapsed-time ceilings does not remove probability pruning, grammar limits, finite model context, memory/disk/provider limits, or the original algorithm's representation choices.

The retained events establish completion of the declared source batches and verification protocol. They do not independently regenerate native logits, establish numerical parity across Torch/GPU versions, or prove exhaustive enumeration of every valid ARC answer. `native_logit_replay` and `search_exhaustiveness_claim` remain false. Full-event hashes bind the retained transcript to its seal, not to cryptographically attested GPU hardware.

## Isolated descriptive correctness

The current owner request to analyze the returned completed run is interpreted with the existing public-development protocol as authorizing descriptive evaluation of this exact already-exposed footprint. Only the four predeclared public upstream files were opened. Their hashes, challenge/train/test order and partition membership were checked before scoring. None belongs to the locked confirmation partition. Gold grids were never written into reports or runtime material.

- Four tasks, six actual tests; every test remains in the denominator.
- Top-1: 1/6 (16.67%). Top-2: 1/6 (16.67%). Retained-pool oracle: 1/6.
- Twelve real guess slots; 41 ranked unique candidates; six output-qualified tests.
- Task-macro top-2: 25%; one task has all its tests correct. This is a different metric from 1/6 test-micro and must not be substituted for it.
- Native completion/evidence qualification is independent of exact correctness. All six are now complete/qualified even though only one is correct.
- Eight synthetic score tests and an independent tuple-based canonical-grid crosscheck reproduce all six test metrics.

Upstream source commit is `f3283f727488ad98fe575ea6a5ac981e4a188e49`; partition manifest SHA-256 `85ee338fbf02c0b48d969cfc44f9b2ab355c2958f35bff1c32cfd23bef12fe39`; evaluator binding SHA-256 `6b6f3d971244cc81b68f76d4c62a0474fb24ec5496485be2e2f32ab2fae9cd83`. Per-test correctness and source-answer diagnostics are quarantined under `evaluator-only/` and must not enter solver features, runtime packages or configuration selection. This report contains aggregate correctness and truth-free per-test resource metrics only.

## Comparison with prior observations

E12 version 11 TTT64 and TTT128 each scored retained top-1/top-2/oracle 1/6, but both had zero qualified test cases because their native completion gates were not satisfied. TTT64 retained eight unique candidates / six guesses; TTT128 retained ten unique candidates / nine guesses. This uncapped run retains 41 unique candidates / twelve guesses and six complete cases, still top-1/top-2/oracle 1/6.

E13 version 12 failed its 8 MiB event ceiling after 512 training updates and five committed tests, with zero completed matched search-arm pairs. It cannot answer its intended 120-versus-240-second comparison. The new run is a different, single-search-per-test experiment. It does not repair E13 into a valid paired comparison.

These observations share selected, previously examined public tasks and unresolved checkpoint-training exposure. They are not a fresh held-out benchmark, a broad ARC-AGI-2 performance estimate, the full 24-task/35-test development panel, a causal compute ablation, an official Kaggle score or evidence of promotion readiness.

## Consequences for the next research line

1. Preserve this as a fully observed engineering baseline. Further plumbing/debugging is no longer the primary explanation for this run's five misses.
2. Target candidate generation and task representation before optimizing only final selection. An oracle over all 41 current candidates already saturates at 1/6.
3. Treat low demonstration loss as fit, not generalization. Evaluate any changed adaptation objective through demonstration-only pseudo-test/cross-validation, without using the six exposed answer labels to select configurations.
4. Distinguish more diverse proposals from more time on the same p=.2 search tree. This run completes its declared tree traversals; merely increasing a timer has no remaining stop to remove. Changing pruning, representations, training or proposal families would be a new method and needs a distinct experimental identity.
5. Predeclare a larger development comparison and use the locked confirmation boundary appropriately before asserting improvement. Separate proposal oracle, top-two selection, completion coverage, wall/compute costs and exposure caveats.
6. This evidence motivates testing an explicit object/relation or program-hypothesis proposal branch alongside a frozen neural baseline, but does not validate that branch or authorize an external run. A hybrid replacement should earn promotion by improving correct-candidate coverage first, then selection and resource efficiency.

## Reproduction and receipts

- `verify_return.py`, `independent-verification.json`, `independent-verification.log`: trusted archive, plan, training/control and full source-transformed inference replay. Parser/ranker definitions load only from the original pre-run package; an audit hook forbids executing code whose filename is under returned `extracted/`, spawning processes or opening network connections. The initial local environment lacked tokenizers; that failed attempt is separately preserved. The final replay used the existing trusted tokenizers 0.21.4 interpreter.
- `summarize_runtime.py`, `runtime-statistics.json`: data-only timing/count/resource summaries.
- `score_public_dev.py`, `prediction-bindings.json`, `public-dev-aggregate.json`: predictions frozen before evaluator truth reads, aggregate-only output.
- `crosscheck_score.py`, `scoring-crosscheck.json`, `scoring-crosscheck.log`: separate canonical-grid scoring implementation and eight synthetic cases.
- `archive-inventory.json`: pre-extraction safe-member inventory and original ZIP binding.

Original evidence and repo status are rechecked at handoff. No new official score exists; official score remains null.
