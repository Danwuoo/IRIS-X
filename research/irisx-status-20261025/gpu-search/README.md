# GPU: episodic adaptation, search and selection

Local research proposal, not a GPU execution result. TPU optimization experiments remain separate.

Start with actual device/runtime checks, unchanged-policy cached/full parity, one update, full reset/restore and measured memory. Then use a metadata-fixed eight-parent discovery order and choose only a feasible 2/4/8-parent prefix from timing and VRAM, never reward. The larger 32-parent, three-seed study is a later target, not the first-run workload.

[`rerank_candidates.py`](../../../tools/postsft_gpu_selector_20261025/rerank_candidates.py) is a model-free, gold-free selector for one frozen candidate pool. It compares first-valid, duplicate-frequency and mean-logprob selection, retains draw/duplicate/invalid counts, and makes no semantic correctness claim. Logprobs and inverse-transform provenance must be certified upstream. Query answers and oracle feedback belong only in an isolated evaluator after predictions and selections are sealed.

Whole model-phase wall time includes preparation, adaptation, generation, Python/hash, failures, save/reload and verification. Matching caps alone does not establish equal realized compute. Seeds are nested within parents; extra seeds are not extra independent tasks.

The available 32-parent panel is training/discovery data, not a clean holdout. Independent parent/family isolation remains a gate before any generalization or formal-training decision.

The legacy historical evidence and the unique decision table remain in `research/arc2-sft-rl-continuation-20261014/`; this component does not rewrite old A/B/C or promote old RL failures as successful updates.

Run the synthetic-only selector tests from the repository root with `python tools/postsft_gpu_selector_20261025/test_rerank.py`. No model, GPU, network, query gold or provider call is used.
