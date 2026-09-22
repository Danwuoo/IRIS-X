# Trial 002 source-use and model audit

Audit date: 2026-09-22

## Selected model

| Candidate | Immutable identity | Evidence and fit | Decision |
| --- | --- | --- | --- |
| Qwen3.5-4B | `Qwen/Qwen3.5-4B@851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a` | Apache-2.0; 4B language model plus vision encoder; 9.34 GB BF16 material; 32-layer hybrid DeltaNet/full-attention architecture. The official card reports MMLU-Pro 79.1, IFEval 89.8, and LiveCodeBench v6 55.8. These general results support candidate priority, not ARC superiority. Transformers 5.8.1 recognizes the exact config. | Selected for four inference-only invocations in the repair smoke. |
| Qwen3-4B-Instruct-2507 | `Qwen/Qwen3-4B-Instruct-2507@cdbee75f17c01a7cc42f958dc650907174af0554` | Apache-2.0; 4.0B dense Qwen3 architecture, closer to NVARC's source checkpoint. The official card reports MMLU-Pro 69.6, IFEval 83.4, and LiveCodeBench v6 35.1 under its documented evaluation. | Compatibility reference only; not executed. |

The benchmark protocols and dates differ, so the table is evidence for
prioritization rather than a controlled model comparison. Neither model has
verified ARC-AGI-2 capability from these numbers.

The exact Qwen3.5 files were acquired with `hf download --revision` and all 14
Hub files passed `hf cache verify`. The project does not label general
pretraining exposure `clean`; it records only that the retained official bytes
received no project ARC-answer adaptation before task-local TTT.

## NVARC mechanism mapping

Upstream repository: `https://github.com/1ytic/NVARC.git`

Pinned revision: `846d0198efa752534594e321fc3289fc0a06c657`

The repository has no root license file at the pinned revision. IRIS-X does not
redistribute its files or copy its Qwen3 checkpoint. It reimplements the
published mechanisms in the project runner and binds the inspected source
digests locally.

| NVARC component | Trial 002 use | Adaptation or gap |
| --- | --- | --- |
| compact digit-row grid representation and Qwen chat formatting | Mechanism reimplemented | Qwen3.5 native tokenizer is retained; the 16-token vocabulary is not used. |
| transpose, rotations, color permutations, and shuffled demonstration augmentation | Deferred | The repair smoke uses one identity view and one invocation per task so the global generation count is auditable. |
| per-puzzle LoRA TTT with adapter reset | Deferred | No adapter or gradient work occurs in `trial-002-smoke-002`; TTT would be a separate experiment. |
| transformed candidate generation, inverse transforms, aggregation, and ranking | Deferred | Standard Transformers generation returns exactly one raw completion per task; parsing is deterministic and does not rank multiple candidates. |
| four-GPU queue with one persistent model per GPU | Mechanism reimplemented | Four fixed answer-blind task/test pairs, one per worker/GPU, with a parent-enforced global invocation quota and terminal records. |
| Qwen3 4B 16-embedding SFT checkpoint | Not reused | Architecture and tokenizer incompatible. Reproduction would require separately budgeted SFT and exposure review. |
| `arc2_evaluation6` listed in SFT/validation preparation | Exposure warning | No NVARC checkpoint is used. Any later NVARC checkpoint public score must be marked potentially contaminated until lineage proves otherwise. |

Inspected local digests include:

- `ARChitects/README.md`: `sha256:df4f4016bcf044f31b1274bbcaa72ee82d798d6bb0782083853d30e77814f7c8`;
- `ARChitects/run_sft.py`: `sha256:457afaa486d2bcd65727797115bca10285f49c17b4df4250a95b6a3691a03175`;
- `ARChitects/run_sft_4b.sh`: `sha256:4fb428cfef81514102f614a31e719e0072365b9fbf26ecc9d289c11c5c3eb60c`;
- `ARChitects/cut_tokenizer.ipynb`: `sha256:1b108add2834da40da103cbb961964bb7e0796e4e7d7a5ec82f29edee080a3f7`;
- public NVARC Kaggle notebook pulled by the CLI:
  `sha256:506b85db66f9949022e87935ccb06a73fd78cb690883bd600bfb5c7d36c2b3af`.

## Existing IRIS-X source use

The cold-archive registry is read-only. Its exact upstream revisions are mostly
`Unknown`, so the local Git-tree identities below are the only reproducible
bindings used here.

| Source | Binding | This iteration | Later connection |
| --- | --- | --- | --- |
| SPEX | tree `ec80163591ff791945e5221c76219af4f8986e60` | Reference only: per-job outcomes, comparison boundary, and resource ledger. | Paired fixed-workload comparisons. |
| VANTA | tree `4e095233520418705168f40a556177477839b052` | Mechanism reference: supervisor terminal states, verification, recovery, and no implicit rollback of consumed budget. | Isolated program solvers. |
| NeMo Agent Toolkit | tree `e02a7c4a0c7c49a3408e1ca757d75a3e0f198466` | Reference only: stage, timing, token, and memory observation fields. | Broader cost diagnostics if justified. |
| Prime Verifiers | tree `cbe80a474790e5aa98642c754e34ded4a759bbf4` | Interface reference: one test output as a job/rollout metric unit. | Reward and training integration. |
| DSPy | tree `824de62cb23e2bf8b52adcb05a8804ef2c148e5d` | Reference only: versioned prompt/program configuration and retained generations. | Prompt optimization after a working baseline. |
| GEPA | tree `eb66cc8bf0cdf9e7d3d25cf9f26ab0fd951bb833` | Reference only: reflective trace use and Pareto trade-offs. | Improvement experiments, not this smoke. |
| AFlow, RouteLLM, FrugalGPT, Agent Lightning, Prime Agent | archive tree identities in `corpus/sources.yaml` | Deferred: workflow search, routing, and RL would add a second research question. | Reconsider only after runtime feasibility. |
| IRIS and EIDOS | archive trees `7956c794…` and `c5afb209…` | Reference only: failure taxonomy and source/evidence separation. | No legacy architecture restoration. |

No archived source tree is imported into the active runtime, and no legacy
root is recreated.

