# IRIS-X: primary-source method assessment and conditional experiment plan

Research date: 2026-10-13 UTC. Read-only assessment of checkout `2901a97a1aa934d15e468e3e6d57bd96d95791e9`. No repository, Kaggle, model, or runtime changes were made. This report distinguishes published evidence, local source contracts, and proposed experiments. This research document does not itself grant execution authority; current owner scope and verified publication prerequisites remain separate.

## Executive conclusion

Keep the current 14B experiment intact while repairing runtime admission. Its scientific question is worthwhile: **does a small amount of exact-reward policy optimization improve task-held-out grid predictions beyond the SFT anchor and additional SFT costing comparable wall time?** It is an informative, deliberately small intervention-package pilot, not a strong test of whether RL can create broad new ARC capability. Four or fewer updates on 32 parents cannot support that larger conclusion. Repeated startup failures have not tested the method at all.

The most relevant external successes support four separable mechanisms: domain-specialized data/SFT, task-local adaptation, candidate-generation diversity, and selection under transformations or executable demonstrations. They do not support forecasting PUBLIC120 >=151/167 from this pilot. One RTX PRO 6000 can plausibly support the current LoRA mechanics; this does not establish four-L4 deployment, and a full BF16 Qwen3-14B replica cannot fit on one 24-GB L4 even before cache/workspace.

Priority order, conditional on authorized execution:
1. Restore exact runtime admission without changing the scientific variables.
2. Establish full-model unchanged-policy replay alignment and the distribution of mixed reward groups.
3. Complete the frozen A/B/C comparison and sealed scores if admitted.
4. Choose the next experiment from the measured failure class, rather than installing another framework or switching model because startup failed.

## 1. Local evidence and which protocol is current

Read first:
- `research/arc-next-line/RESEARCH-SUMMARY.zh-TW.md`, `architecture-memo.zh-TW.md`, and `model-hardware-memo.md`.
- `research/qwen-portfolio-20261012/{PLAN.md,experiment-guide.zh-TW.md,panel-plan.md,CHECKPOINTS.md}`.
- `tools/arc_qwen_rlvr004_20261013/source/design/{MEASURED-POLICY.json,COST-EVIDENCE.json,LEAD-EXPERIMENT-DECISIONS.json}`.
- `source/rl_session/{plan.py,runtime.py,actor.py}`, `source/reviewed/rl_math.py`, and the independent protocol review.
- Latest run007 transfer and earlier terminal/snapshot records under `docs/plan/`.

Important historical distinctions:
- The uncapped six-query direct-grid experiment reports candidate-pool oracle=top-2=1/6. For those exposed cases, reranking alone cannot fix the five missing correct candidates. This is a small, historical diagnostic, not a present 14B baseline.
- The portfolio plan's 2/6→5/6 program-LoRA observation concerns already inspected, same-family authored queries. Its retrospective 6/6 portfolio is motivation for prospective testing, not independent ARC generalization.
- The independent RL protocol review and `LEAD-EXPERIMENT-DECISIONS.json` describe an earlier **SFT64 / full 256-slot sweep** design. The later measured policy and executable `rl_session/plan.py` describe **SFT256 / four disjoint 64-slot batches**. Do not silently use the old review as the current runtime specification.
- `COST-EVIDENCE.json` contains timing, memory, packing and source hashes, explicitly excluding correctness. Its reference to v25 science summaries is not a substitute for those absent scoring artifacts. No v25 accuracy conclusion is drawn here.
- run007/v39 is recorded ERROR during CUDA-library admission. Neither its terminal status nor source reconstruction establishes a successful anchor, RL update, paired prediction, or PUBLIC120 result.

### Current experiment, as read from source

A: same-session BF16 Qwen3-14B plus FP32 rank-8 LoRA; 256 SFT updates; persisted/reloaded anchor. B: restore A; 32 fixed training parents, one identity-transform leave-last-demonstration-out query each, 8 samples/parent; four disjoint batches of 8 parents/64 slots; maximum one update per completed batch, maximum four updates; exact binary rewards; temperature=1/top-p=1 under native grid DFA; learning rate 1e-6. C: restore A; additional SFT, fresh optimizer at 2e-4, matched to B's whole synchronized model-phase wall time within the fixed tolerance, without idle padding. Primary evaluation has no TTT and two deterministic transforms. The frozen order is A/B/C dev16, freeze the selected arm, that arm’s PUBLIC predictions with the full 167-query denominator, A/B/C reused held32 predictions, model closure, then held and PUBLIC scoring.

The local loss is group-centered, equal-sequence-weighted DDIS-style policy gradient with detached ratios and strict clipping; it is **not a full reproduction of GRPO, PPO, or an external agent-factory system**. No critic, advantage standardization, entropy bonus or reference-KL is implied by the inspected math. Those distinctions belong in the report even if “RLVR” remains the convenient umbrella label.

## 2. What the strongest relevant primary evidence actually establishes

### NVARC: directly relevant contest system, expensive training and exposed public validation

The original paper describes Qwen3-4B specialization, per-puzzle BF16 LoRA adaptation, batched DFS, and scoring using shared augmentation views. Full SFT used 32 H100s for 27 hours (864 GPU-hours, arithmetic; not a dollar quote). Its 3.2M augmented samples include synthetic descendants of descriptions of all 120 public-evaluation tasks; the authors explicitly acknowledge this exposure. A public-set comparison to those weights is therefore not pristine generalization.

The paper's 27.64% and post-deadline 29.72% concern the competition public leaderboard; ARC Prize separately reports 24.03% private evaluation. TRM did not automatically improve the strongest branch: a 10-hour 4B run remained 27.22% with TRM, and the last 4B submission used Qwen alone. These observations support reproducing mechanisms and measuring complementarity, not copying a headline. [Original paper, §§2–4](https://github.com/1ytic/NVARC/blob/main/nvarc_2025.pdf), [organizer's private results](https://arcprize.org/blog/arc-prize-2025-results-analysis).

The official implementation explicitly uses a 16-token grid representation and a four-node SFT launch. That is a specialized direct-grid model, not an interchangeable program proposer retaining normal coding ability. IRIS-X's full-vocabulary program line and compact NVARC line should remain distinct controls. [Training README](https://raw.githubusercontent.com/1ytic/NVARC/main/ARChitects/README.md), [training launcher](https://raw.githubusercontent.com/1ytic/NVARC/main/ARChitects/run_sft_4b.sh).

### Small-model TTT: credible ablations, mostly ARC-AGI-1 evidence

Akyürek et al. identify task-specific adapters, in-context leave-one-out formatting, and transformations as important components. Their 8B pipeline reports 47.125% ARC-AGI-1 public pass@2 using their own fine-tuned base and 53% using BARC's base. The paper reports substantially lower semi-private ensemble performance (47.5%) than its public ensemble figure. Initial 8B fine-tuning used four A100s; TTT plus inference took about 12 hours per 100 tasks on an A100. The precise ensemble number is internally inconsistent between one table and text, so it is not needed here.

Inference: retain TTT as a serious controlled option, but first separate base/SFT/TTT/search contributions and match task-local reset behavior. Neither a public ARC-1 score nor “8B” implies affordability or success on ARC-2. [Paper, §§4 and appendices B–C](https://arxiv.org/html/2411.07279v2).

### SOAR: the most relevant program-training precedent

SOAR alternates program sampling/refinement with learning from search experience, including hindsight relabeling. On ARC-AGI-1 it reports Qwen2.5-Coder-7B improving from 14.25% search performance to 36.25%, and 14B from 19.87% to 42.75%. The 52% headline combines five model sizes; it is not the 7B result. Its search spends 6,000 synthesis attempts per task per iteration. The 7B/14B LoRA fine-tuning fits one H100, but that does not make the entire multi-model search/data-generation pipeline cheap.

Inference: if local oracle coverage is the bottleneck, train proposal/refinement behavior on verified, training-only traces and compare it to extra independent sampling. This is a better-grounded hypothesis than assuming a generic agent wrapper alone supplies reasoning. [SOAR, §§3–4 and Table 1](https://arxiv.org/html/2507.14172v2).

### Small Qwen + genetic search: direct ARC-2 proof of concept, weak causal estimate

The Qwen3.5-4B+GA paper reports 2/60 correct test outputs in the seed pool versus 6/60 after evolution; nine programs fit all demonstrations, of which only six generalized. It used the first 60 public tasks, with the first 20 already used during development. The random-seed control changed during development, and additional GA compute was not matched to additional LLM sampling. Treat the four added solves as proof that local program search can add missing candidates, not a clean estimate of architecture gain or unbiased generalization. [Paper, §§4–5](https://arxiv.org/html/2609.27242v1).

### TRM and other direct-grid architectures: small parameter count is not small total experiment

TRM's original paper reports 44.6% ARC-1 and 7.8% ARC-2 public evaluation with a 7M recursive network. ARC training took roughly three days on four H100s, with heavy augmentation and task/augmentation-specific embeddings. These costs and transductive task-adaptation details matter more than the neural core's parameter count. It is latent answer refinement, not a recursive team of language-model agents. [TRM, §5 and setup appendix](https://arxiv.org/html/2510.04871v1).

The ARChitects' 2025 technical report instead uses an 8B masked-diffusion backbone, 2D positional encoding, LoRA and recursive latent sampling, and explicitly includes ARC training and evaluation sets in its data mix. It is a genuine alternative inductive bias, but adopting it now would introduce model, representation, training and decoding changes simultaneously. [Authors' report](https://lambdalabsml.github.io/ARC2025_Solution_by_the_ARChitects/).

A newer LongT5 report describes a ~201M specialized model, 2.3M synthetic tasks, 64-H100 offline training and a custom 177-task evaluation. Its ablations separately report candidate coverage, filtered coverage, top-2 and time, a useful evaluation template. Its custom-set and Kaggle figures must not be conflated with IRIS-X's PUBLIC120 metric. [Authors' technical report, §§6 and 10](https://arxiv.org/html/2603.06590v1).

### Frontier REPL agents: mechanism evidence, no small-model feasibility guarantee

Arcgentica reports Opus 4.6 ARC-2 public performance rising from 79.03% at $3.81/task to 85.28% at $6.94/task. The system provides a stateful REPL and recursive delegation; this does not isolate delegation from execution feedback, prompt/interface changes or extra compute. It uses a frontier API model, not offline 14B on four L4s. This supports testing executable hypothesis/refinement mechanisms, with a same-model equal-budget control. [Authors' report](https://www.symbolica.ai/blog/arcgentica).

### RLVR: measure coverage and signal rather than assuming either magic or impossibility

Yue et al. find that, in their experiments, RL can improve low-k success while reducing high-k coverage. That is evidence to measure both selection efficiency and reachable candidate coverage, not a theorem that RL can never learn. [Primary study](https://arxiv.org/html/2504.13837v3).

ProRL reports broader gains under prolonged RL, but uses over 2,000 steps, diverse domains and about 16,000 H100 GPU-hours, including entropy-management interventions. It is not an ARC-2 success result or comparable to four LoRA updates. [ProRL, §3](https://arxiv.org/html/2505.24864v1).

TTRL learns from majority-vote pseudo-label rewards on unlabeled test problems. Such agreement is not an independent verifier of an ARC rule. It should not replace available exact training-demonstration rewards or be described as known-correct supervision. [TTRL](https://arxiv.org/abs/2504.16084).

## 3. Is the current RLVR hypothesis strong enough?

**Yes for a signal/mechanism pilot; no for a broad capability claim.** The following are distinct, useful questions:
- Can the exact full model sample both correct and incorrect training-query grids under the admitted grammar?
- Can those same original tokens be replayed with numerically consistent masked log-probabilities and real adapter gradients?
- Does the resulting low-dose policy update improve paired task-held-out top-2 beyond A, and beyond compute-comparable C?

The experiment controls the anchor and evaluates held-out task parents; it has a meaningful extra-SFT alternative and an honest no-update outcome. That makes it more than infrastructure. Its weaknesses are deliberate but must remain visible: 32 parents, at most four updates, sparse all-grid exact reward, grid-only restricted policy, different B/C learning rates, reused held32, and a dev selector with only 16 parents. A positive B result means this package helped under these settings, not that its objective alone caused the gain. A null result is also highly local.

For binary reward with eight independent samples and per-task correctness probability p, the probability of a mixed group is 1−p^8−(1−p)^8. Illustrative values: p=0.01 gives ~7.7%; p=0.05 gives ~33.7%; p=0.10 gives ~57.0%; p=0.50 gives ~99.2%. These are arithmetic illustrations, not estimates for this model; rollout correlations can reduce useful diversity. All-zero and all-one groups have zero centered advantage. Therefore count **mixed parents and contributing nonforced tokens**, not just 256 slots, training loss or claimed update count.

A withheld demonstration structurally hidden from the actor can still have been optimized during SFT through another record/augmentation. That is legal training exposure, not an independent generalization result. Track exact and ancestor exposure; do not select reward records retrospectively to improve reward variance. Keep original observed parent order and the current batch protocol frozen.

## 4. Conditional branches that distinguish method from runtime

These are proposals for the next authorized execution and later separately frozen experiments. They do not alter the current source contract.

| Observation | Valid conclusion | Next discriminating action |
|---|---|---|
| Loader/library/hash/child-process admission fails | No scientific test occurred | Repair and verify exact dependency selection in the same launcher/process topology. Preserve predictions absent/unknown. No model/framework change. |
| Model loads but unchanged-weight actor/replay gap fails | RL update cannot be trusted | Diagnose cache, mask support, precision, dropout/mode, position/prefix alignment on retained original tokens. Do not loosen tolerances based on observed passing values. |
| Memory or replay deadline fails before a complete audit | Infrastructure/cost infeasibility at this configuration | Retain actual attempted and eligible denominators. A later separately declared memory/backend variant must reproduce the same workload before interpreting quality. |
| Complete audit, all-zero groups | No usable positive reward under this policy/budget | Keep B=A for the declared no-update result. Next test proposal coverage: training-only verified program SFT, more representative real/synthetic data, or a separately budgeted candidate audit. Do not conclude all RL is ineffective. |
| Complete audit, all-one groups | Reward task saturated; no centered signal | A later protocol may predeclare harder training-only LOO/family mixtures. Do not replace parents mid-run. |
| Mixed groups, real gradients, but B=A quality | Low-dose intervention provided no measured transfer | Examine gains/losses, diversity, exposure and step magnitude. Compare C; distinguish too little signal from reduced coverage. More RL is justified only by a new budget and hypothesis. |
| B beats A but C also matches/beats B | No advantage over spending comparable time on SFT | Prefer the simpler supported intervention for this setting; B is not disproved universally. |
| B beats A and C on dev and reused held | Promising package-level gain | Replicate on predeclared unused task parents/families; retain same scoring and report uncertainty. Do not call reused held32 pristine confirmation. |
| Candidate oracle is low | Missing hypotheses dominate | Spend experiments on representation/data/proposal/refinement; a learned selector cannot select absent answers. |
| Oracle is high but actual top-2 low | Selection wastes available solutions | Compare fixed shared-view likelihood, vote/diversity rules, and fresh-fold demo validation on the same sealed candidate pool. Never feed oracle labels to selection. |
| Demo-perfect programs often fail withheld examples | Demonstration fit overaccepts | Test leave-one-demo-out validation using candidates generated without the withheld output, plus explicit complexity/robustness controls. With very few demos, disclose variance and imperfect identification. |

The runtime/gradient separation follows the current local source contract. Candidate, TTT and coverage branches are motivated by NVARC, Akyürek et al., SOAR, the Qwen+GA study, and the conflicting RLVR results cited above. These are **our proposed experiments**, not published guarantees.

### Minimum reporting for the first successful A/B/C run

Retain planned/dispatched/eligible/context-excluded/not-reached counts; all-zero/all-one/mixed group counts; actual committed updates; nonforced-token actor/replay gaps; clipping fraction and gradient norm; adapter identity before/after/reload; wall-time and peak memory; invalid/truncated outputs; task-paired gains and losses; pass@1/pass@2 with the original denominator. Separately state infrastructure completion, numerical validity and scientific result. A skipped or failed operation is not a zero-reward model error.

For a later method comparison, preregister one compact train-only development screen: direct grid, independent program sampling, and feedback-repair from the **same checkpoint**, with a common wall/token ceiling and actual cost curves. Candidate oracle is evaluator-only. Repair must outperform spending the same allowance on additional independent candidates, and programming syntax/runtime failure rates must remain in the denominator. This extends the repository's existing A/B/C architecture design and is directly motivated by SOAR and the Qwen+GA evidence.

## 5. One RTX PRO 6000 versus four L4s

Google specifies `g4-standard-48` as one 96-GB RTX PRO 6000 with 48 vCPUs and 180 instance-memory units. NVIDIA specifies each L4 as 24 GB, 300 GB/s memory bandwidth and PCIe Gen4 x16. These are specifications, not usable-memory or workload-throughput measurements. [Google G4](https://docs.cloud.google.com/compute/docs/accelerator-optimized-machines#g4-vms), [NVIDIA L4](https://www.nvidia.com/en-us/data-center/l4/).

Qwen's official model card lists 14.8B parameters. Simple weight-only estimates are ~29.6 GB/~27.6 GiB BF16, ~14.8 GB/~13.8 GiB at 8 bits, and ~7.4 GB/~6.9 GiB at 4 bits. Real quantized memory includes metadata and unquantized tensors. Conventional full Adam training at 16 bytes/parameter would require ~236.8 GB before activations; LoRA avoids most of that optimizer state. The official config implies BF16 KV cache of 160 KiB per token per sequence, approximately 0.625 GiB at 4096 tokens. [Model card](https://huggingface.co/Qwen/Qwen3-14B), [config](https://huggingface.co/Qwen/Qwen3-14B/raw/main/config.json). These are arithmetic capacity bounds, not benchmark results.

Consequences:
- The current single-GPU BF16-LoRA training approach is credible. The local cost artifact records successful historical SFT/calibration peaks around 34–44 billion bytes, while explicitly leaving stochastic RL replay/backward unmeasured. It is not proof of current run007 success.
- A full BF16 14B replica **cannot** reside on one L4. Four L4s do not form a transparent 96-GB allocation. Candidate deployment designs include two-GPU sharding with two replicas, one four-GPU shard, or a measured quantized replica per L4.
- vLLM documents Ada support for AWQ/GPTQ/Marlin, bitsandbytes, INT8 and FP8 routes. That is framework-level compatibility, not evidence for the exact pinned Qwen checkpoint, LoRA path, constrained decoder or TTT loop. Compare outputs/accuracy and end-to-end latency before adopting any. [vLLM quantization support](https://docs.vllm.ai/en/stable/features/quantization/).
- Rebuild/requalify target-specific kernels and wheel/runtime combinations. Do not move a Blackwell-only compiled cache and assume Ada portability. Keep numerical model artifacts separate from device-specific executables.
- Measure one task of each relevant prompt/output size, then the full declared topology and completion budget. Include loading, adaptation, decoding, reranking and export. Tokens/s or theoretical Tensor FLOPS alone is insufficient.
- The current 12-hour policy spends a large reserve on one selected PUBLIC pass. It is not a resource-matched reproduction of NVARC's data generation, SOAR's thousands of attempts, or ProRL's long training. Dollar cost is unknown without the actual authorized instance tariff, region and billing duration; no dollar forecast is fabricated.

## 6. Data exposure and score interpretation

Use a source/ancestor graph, not only exact-byte deduplication: D4 transforms, color permutations, same generator family, human descriptions, program solutions and synthetic descendants can all carry task information. Exclude disallowed public-evaluation descendants if the aim is an unexposed public measure; quarantine exposed external checkpoints/data rather than silently mixing them into a clean control.

Keep distinctions explicit: public-training LOO transfer; repeatedly used project development; fresh family/task holdout; public evaluation; organizer semi-private/private. The official ARC-AGI-2 repository warns against inspecting or repeatedly tuning on evaluation tasks and identifies 1000 training versus 120 public-evaluation tasks. [Official dataset guidance](https://github.com/arcprize/ARC-AGI-2/blob/main/readme.md).

IRIS-X PUBLIC120 micro pass@2 uses 167 queries. Some published results average per-task normalized scores instead. Even identical predictions can produce different aggregates when tasks have multiple queries. Preserve the unchanged project scorer and report denominator/aggregation beside every number. A target-free seal prevents current-run label-based selection; it does not erase earlier human/developer exposure or unknown model pretraining exposure.

## Bottom line

The immediate next success criterion is a valid, complete, interpretable measurement of the existing hypothesis. If it fails before model work, fix runtime. If it reaches a clean zero-signal audit, improve training-only proposal coverage before scaling RL. If it has real signal, use the paired A/B/C result to decide. Small models have credible ARC successes, but the strongest sources attribute them to substantial specialization, task adaptation and carefully budgeted search. None justifies promising PUBLIC90 from the current 14B pilot.
