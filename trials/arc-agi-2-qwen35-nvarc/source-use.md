# Pinned source use and method provenance

Read-only inspection on 2026-09-23. NVARC was cloned at commit
`846d0198efa752534594e321fc3289fc0a06c657`; no upstream file was
vendored into the runtime. Its root lacks a license at this commit. The
TinyRecursiveModels submodule is pinned to
`e7b68717f0a6c4cbb4ce6fbef787b14f42083bd9`.

| Source binding | Inspected mechanism | IRIS-X use and difference |
| --- | --- | --- |
| NVARC `SDG/README.md`, `scripts/build_datasets.py` SHA-256 `1996ed8010afa28135f3d3fad5d89ae113ca845a0f235ab7392e4167cb23f5e8` | Ten-stage summary/mix/input/output program/pair/filter/data route; 8 dihedral transforms, colors and message examples | `arc_nvarc_data.py` implements deterministic import, groups, augmentation and saved-response replay. Teacher generation and isolated Python execution are not run. |
| NVARC `ARChitects/cut_tokenizer.ipynb` SHA-256 `1b108add2834da40da103cbb961964bb7e0796e4e7d7a5ec82f29edee080a3f7` | 16 tokens selected from a Qwen3 corpus, including `arc2_evaluation6`; direct embedding row slicing | `arc_nvarc_representation.py` independently defines the published 16-symbol grid grammar and maps pinned Qwen3.5 rows. It avoids evaluation-derived vocabulary selection and does not reuse Qwen3 row IDs. This is a method rewrite, not an identical tokenizer. |
| NVARC `ARChitects/run_sft.py` SHA-256 `457afaa486d2bcd65727797115bca10285f49c17b4df4250a95b6a3691a03175`; `run_sft_4b.sh` SHA-256 `4fb428cfef81514102f614a31e719e0072365b9fbf26ecc9d289c11c5c3eb60c` | NeMo RL/Megatron full SFT; four nodes of eight H100, 12,716 steps, global batch 256, 256k-token packing | Local PyTorch full-SFT entrance is unpacked and single-process; optimizer/RNG/cursor resume and export exist. Qwen3.5 hybrid gradients, memory and numerical behavior remain untested. Original data mix and scale are not reproduced. |
| Public Qwen submission notebook `sorokin/arc2-qwen3-unsloth-flash-lora-batch4-queue`, pulled by Kaggle CLI, SHA-256 `506b85db66f9949022e87935ccb06a73fd78cb690883bd600bfb5c7d36c2b3af` | Qwen3 ARC-SFT checkpoint; per-task r=256/alpha=32 rsLoRA, 16 augmentation views, batch DFS, 8 common augmentation likelihood checks, `votes - mean NLL` selection | `arc_nvarc_training.py` uses task-local leave-one-out adaptation; `arc_nvarc_candidates.py` uses 16 views and eight verification views. HF beam generation replaces batch DFS; no equivalence claim. LoRA targets are discovered from Qwen3.5 attention and DeltaNet modules, not copied from Qwen3. |
| NVARC paper `nvarc_2025.pdf` in pinned Git commit | 4B-only public 27.64% in competition, 29.72% in a later variant; 2B+TRM was a different ensemble; joint TRM attempts were rescored by Qwen; synthetic-data exposure is acknowledged | Scores and methods remain version-separated. `integrate_with_qwen_verifier` models joint rescoring; current branch-priority fallback is an explicit alternative and is unmeasured. No historic score is used as an acceptance threshold. |
| NVARC `TRM/README.md`, `eval-arc-k-10.py` SHA-256 `62ec1e2f179cd80c58a7f0067ab51c76e2e7eb213959566b015c107c5d98b36f`; pinned TinyRecursiveModels `dataset/build_arc_dataset.py`, `evaluators/arc.py` | Separate TRM model, 30×30 PAD/EOS/color encoding, augmentation and 10-attempt candidate branch; NVARC trained with 8 H100 and tuned TTT | `arc_nvarc_trm.py` implements labelled training staging, encoding, bounded upstream command spec and candidate/joint selection interface. Real TRM weights/dependencies/evaluation remain absent. |
| Qwen `Qwen/Qwen3.5-4B@851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`; `config.json` SHA-256 `ddc63e1c717afa86c865bb5e01313d89d72bb53b97ad4a8a03ba8510c0621670`; tokenizer SHA-256 `5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42`; weight index SHA-256 `cf3f798ee02ba45f9622aa8892a47369ab667d0afbf154ee7c2212de42e6302d` | `Qwen3_5ForConditionalGeneration`, tied embeddings, 32 layers alternating linear attention/periodic full attention, language embedding key `model.language_model.embed_tokens.weight`. Exact tokenizer IDs are `15..24` (digits), `198` newline, `846` user, `74455` assistant, `248044` pad, `248045` begin, `248046` end. | Text-only input path retains the vision module in the serialized HF model; no image inputs. Conversion requires the exact tokenizer bytes/IDs and uses HF model APIs, not Qwen3 tensor keys. Base BF16 material is ~9.34 GB and was not downloaded to this worktree. |
| Official `arcprize/ARC-AGI-2@f3283f727488ad98fe575ea6a5ac981e4a188e49` and `arc-prize-2026-arc-agi-2` Kaggle mount | Full visible task source and multi-test scoring | Current tests use synthetic tasks. New real outbound drafting requires exact challenge digest and full-task parity; no sealed answer file was opened. Earlier 512-case parity audit remains historical evidence, not new authorization. |
| Existing `arc_budget_ablation.py`, `kaggle_runner_budget_ablation.py`, `arc_trial_002.py`, `transport.py` in this repository | Source audit, four-L4 hardware gate, persistent workers, deadlines, canonical ZIPs, multi-test score | Trial-specific runtime reuses their tested primitives and patterns without modifying historical runners or identities. Its four-L4 path has not itself executed. |

The paper's synthetic corpus and public evaluation exposure make external
"clean" claims unsafe without lineage review. `clean-research` excludes known
parent/visible transforms; its manifest says `unproven`. The
`competition-reproduction` policy is explicitly contamination-possible.
Published datasets were not downloaded, imported, or regenerated here.

The handoff's ignored evidence locations under worktrees `e34a` and `918a`
were absent when checked from this task. The committed budget-ablation control
review and Trial 002 source-use were read instead. No old result ZIP, ledger,
sealed truth or output was retrieved, copied or mutated.
