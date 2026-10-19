# Architecture / shared-pool fusion: evidence, not capability claims

This is a CPU integration checkpoint. It neither replaces a frozen experiment
nor authorizes a GPU run. The independent TPU port is a separate dense-only
migration screen; it must not be presented as reproducing the CUDA experiment.

## Acceptance layers

1. **Numerical and state stability:** explicit native-model admission; sampled
   behavior, forced cached replay, full teacher forcing and actual gradient-path
   probabilities; original 0.05 maximum log-probability gap gate; source-bound
   frozen tensors; exact checkpoint reconstruction; isolated optimizer histories;
   per-task reset; finite-gradient and post-update failure handling.
2. **Actual-model usability:** original tokenizer and real training-derived
   examples, official-weight architecture, real optimizer updates, complete
   requested work and checkpoint/recovery evidence, measured memory and wall time.
   Tiny fixtures prove contracts but not official-model feasibility.
3. **Capability:** generated exact answers on a predeclared parent-disjoint panel,
   full denominator, paired seeds, untouched anchor, target-CE and routed fusion
   controls. Loss decreases, valid output, device admission, one update and a
   successful mechanism test do not satisfy this layer. Parent separation in our
   continuation does not establish absence from the released model's prior SFT.

## Implemented bridge and verified boundaries

`tools/nvarc_efficient_fusion_20261018/architecture.py` admits exactly the reviewed
CompactEngine, CapacityEngine and WidthEngine classes and exact native
Qwen3ForCausalLM. Expanded engines and the shared-pool trainer require the
unchanged FP32-backbone policy. Admission delegates to each engine's existing
source-derived module/config/trainable/frozen-weight checks. It does not replace
any probability or gradient gate. Arbitrary subclasses are not accepted.

The generic training/workflow is tested with compact, capacity baseline,
depth-32, four-expert top-2 MoE and FFN-width-8192 constructions. The production
worker still constructs the dense compact engine, and its independent controller
still derives official dense expectations. The fixture-contract seam is NOT a
production mechanism for trusting artifact-supplied architectures. A future
expanded production recipe needs an independent constructor/contract derivation
on both producer and consumer sides.

Actual CPU fixtures cover all-wrong known-target CE, mixed-group upstream AF3
DDIS and all-correct canonical exact-positive CE, six committed updates per
architecture, fresh reconstructed checkpoints, post-learning probability replay,
frozen-base preservation and demo-only TTT reset. Outcomes are scripted only to
exercise branches; logits, gradients, losses, optimizers and checkpoints are real.
There is no ARC accuracy estimate in these tests.

Independent regression probes establish bitwise equality of interleaved arms
against independently uninterrupted arms, including complete AdamW state and
separate moment storage. Gradient mismatch/NaN rejects all optimizer attempts.
A post-step failure restores parameters but does not pretend to restore optimizer
or RNG: the engine remains poisoned and cannot be reused. An AF3-only MoE update
has a nonzero router gradient and changes router and expert-adapter tensors.

Four official 2B source-weight FFN components (layers 6, 13, 20, 27) additionally
passed function-preserving widening, input-gradient checks, real AdamW updates,
and frozen-source preservation. This is official component evidence, not a full
expanded-model run, GPU feasibility proof or capability result.

## Mechanisms retained, and deliberate deviations

- [Agent Factory 3](https://github.com/ycchen-tw/agent-factory-3): the pinned
  upstream DDIS loss is called, with our compact-model replay and explicit masks.
  The upstream multi-server framework is not reproduced.
- [RAFT](https://github.com/RLHFlow/RAFT): exact-positive samples can feed CE.
  Our all-correct canonical deduplication is an adaptation, not RAFT reproduction.
- [DAPO](https://dapo-sia.github.io/): bounded mixed-group collection and measured
  signal utilization are useful ideas. Our loss/reduction remains the explicitly
  audited AF3 objective, not DAPO's complete optimization recipe.
- [RLVE](https://github.com/Zhiyuan-Zeng/RLVE): verifiable train-only difficulty and
  coverage motivate curriculum design. No unimplemented automatic environment
  generator or original RLVE result is claimed.
- [Net2Net](https://arxiv.org/abs/1511.05641): function-preserving expansion is
  verified at initialization. Symmetry breaking, learned stability and useful
  increased capacity remain separate tests.
- [Sparse upcycling](https://arxiv.org/abs/2212.05055): replicated pretrained
  experts motivate the bounded MoE comparison. Routing, active cost and capacity
  are measured separately; additional total parameters alone imply no gain.

All-wrong target CE and all-correct canonical-positive CE share the same known
correct target in this grid domain. The distinct RL intervention occurs only in
mixed groups. A run collecting no mixed groups cannot establish an RL benefit.
Report unique supervised targets, duplicate rollouts, group categories, rollout
seconds versus optimizer seconds, gradient counts and tokens alongside accuracy.

## Smallest useful capability experiment (not launched)

Freeze parent selection and seeds before model output. Use the existing 96-parent
continuation-held panel, or explicitly label a smaller predeclared screen; never
replace failures or truncate the denominator after observing output. Exclude the
historically used diagnosis panels and known train/dev variants. Report inherited
checkpoint exposure separately; these are not clean hidden-competition results.

First compare unchanged dense anchor, target CE and routed fusion on identical
training parents and held queries, with two paired seeds if resources support it.
Keep TTT off by default. Use the same fixed decoding/view/ranking policy in all
arms. Report both equal optimizer-update results and actual supervised/rollout
 tokens and wall cost; equal steps must not be described as equal compute.
Only add one function-preserving capacity treatment after the dense workflow's
resource and stability admission. Do not combine width/depth/MoE and TTT in a
single unidentifiable intervention.

A positive screen requires a reproducible generated-exact paired advantage,
without missing work or extra data, and a disclosed uncertainty interval. A small
panel or one seed can reject obvious regressions but cannot establish a robust
capability gain. If rollout acquisition dominates cost or groups are uninformative,
record that negative efficiency result instead of spending most of the budget on
more redundant correct trajectories. A larger evidence-bearing comparison then
needs an explicit measured runtime budget, not an invented GPU throughput estimate.

## Completed CPU checkpoint

The combined focused regression ran 53 tests in 32.626 seconds: all passed,
zero skipped. The same 53-test suite also passed under Python optimization
(`-O`) in 33.497 seconds, with zero skips.

A complete official 2B model was loaded on CPU with the original rank64/alpha16
adapter initialization, then promoted to FP32. One 52-token, untruncated real
training-demonstration example produced a nonzero-gradient SFT update. Before
and after the update, cached/full/eval/train-gradient replay had measured maximum
log-probability gap 0.0 for the bounded sampled probe. Peak RSS was about 7.42 GiB.
A fresh engine reconstructed the original anchor, loaded the saved trained state,
and reproduced its generated tokens and probabilities bitwise. The attempted
load into a previously used engine was correctly rejected; the test was corrected
to create a fresh engine, rather than relaxing this production safeguard.

These are official full-model CPU mechanism and recovery observations for one
short example. They do not establish expanded-model full-size feasibility,
long-context throughput, generalization, or useful additional training. The
separate TPU port additionally has an actual official-model CPU reference for a
fixed 512-token eager-attention forward, bound to its own exact initialization,
model bytes and prospective train-only panel.

The broader ML-environment repository aggregate did **not** pass: 2,377 tests in
393.564 seconds, 2 failures, 13 errors and 48 skips. The 13 errors require absent
historical retained fixtures. One failure occurred when Gloo TCP device creation
was denied by the execution environment; the other was a child process propagating
SkipTest for unavailable native materials. No TPU-focused failure was observed.
These limits are not waived or converted into a claim of complete repository
acceptance. Historical retained acceptance remains separate from this checkpoint.
