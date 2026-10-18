# NVARC function-preserving FFN width comparison

> Public-subset scope: this checkout includes only the width expansion, model
> integration, CPU component probe and model unit tests. The complete three-arm
> workflow, provider launchers, delivery capsule and operational integration
> tests remain private. Descriptions below cover that separately validated
> implementation; this public subset is not a ready-to-run Kaggle package.

New local-only source namespace, separate from frozen capacity source003 and all
prior notebooks/checkpoints. No remote save, GPU Run or model-quality score is
claimed. The parent alone may publish the separately reviewed private Quick Save.

## Three explicit arms, two training schedules

1. `initial_anchor`: original compact2B SFT141, zero optimizer updates.
2. `baseline`: identical original architecture,64 continuation updates.
3. `width8192`: all28 FFNs expanded6144→8192,64 continuation updates.

All arms initialize the exact same official source and fresh rank64/alpha16
rsLoRA through the unchanged loader, then promote BF16 source values to FP32.
Both trained arms get the same serialized examples/order:16 admitted train
parents repeated4 times, fresh AdamW at2e-5, weight decay0.01. All three get the
same16-parent held-demo evaluation, two views, zero TTT. The unchanged anchor has
its own immutable checkpoint and retains exactly its initial trainable bytes.
Selection is frozen before all three optional PUBLIC120-task/167-query panels.
The anchor makes degradation relative to initialization directly visible.

This is equal optimizer steps for the two trained arms, not equal compute. A
unique strict dev pass@2 winner must beat the untouched anchor; width must also
beat trained baseline. Ties/partial work retain the anchor. PUBLIC never selects.
All evidence is exposure-qualified development evidence, not clean/hidden scores.

## Construction fixed before scoring

Primary principle: [Net2Net, Chen, Goodfellow and Shlens](https://arxiv.org/abs/1511.05641)
introduces function-preserving widening. The paired antisymmetric SwiGLU/fresh-LoRA
construction here is a project-specific adaptation and proof, not a reproduction
of that paper's architecture or results and not an established capability gain.

Seed20261018 plus layer index picks2048 distinct source channels by CPU randperm.
For each, duplicate the gate row g, replace the two up rows by u+δ and u−δ, and
split down column d equally. δ is per-element Rademacher sign times u times2^-5:

    d/2 SiLU(gx)((u+δ)x) + d/2 SiLU(gx)((u−δ)x) = d SiLU(gx)(ux).

The3.125% coefficient-relative perturbation is a fixed dyadic numerical rule,
not tuned on tasks. Source BF16 weights are promoted before transformation;
paired up sums are asserted exact in FP32. Larger GEMM reductions can still
round differently. Existing1e-4 official /1e-5 tiny full/cached initial-logit
limits and identical greedy-token admission are retained and independently
checked by the controller. The distinct unchanged sampled-versus-full0.05
limit also stays mandatory. No BF16 re-quantization, precision fallback, changed
production threshold or automatic retry exists.

Fresh zero-B adapters only: inherited gate/up A, old B rows, down-A old columns,
and down B are mapped exactly. Appended gate/up B rows are zero; new down-A
columns use independent CPU-seeded original-fan-in uniform initialization,
rounded to BF16 then exactly promoted. All non-FFN source/adapter bytes and global
process RNG are unchanged. Nonzero-B, used or checkpoint-loaded engines are
rejected. This is not a trained-adapter morphism or optimizer-state resume.

The +δ/−δ features differ. Opposite gate-B row perturbations, a redundant direction
under plain replication, now have nonzero measured loss gradients. Actual AdamW
updates separate every replicated row pair; subsequent A gradients wake. Native
weights stay frozen. This establishes usable directions, not efficacy or formal
universality; parameter counts alone are not the argument.

## Exact accounting and unmeasured resource envelope

Baseline/anchor native1,409,475,584; trainable69,795,840; resident1,479,271,424.
Width native1,761,797,120; trainable80,805,888; resident1,842,603,008.
Added native352,321,536; added rank64 adapter11,010,048.
FP32 resident bytes5,917,085,696 versus7,370,412,032.
Linear-forward operations/token2,958,098,432 versus3,684,761,600.
Every added channel executes. These are analytic counts, not measured GPU peaks
or complete training FLOPs; quadratic attention, backward/recompute, activation
functions, normalization and optimizer work are excluded.

The widest arm requires7.37GB parameter storage, another0.323GB gradient storage,
0.646GB Adam moments, and about0.323GB for a trainable rollback snapshot before
activation/cache/temporary buffers. FP32 math attention at8192 tokens can require
multiple4.29GB attention-sized buffers; exact peak is unknown. Arms run serially,
never concurrently. The unchanged conservative40GiB free-CUDA-memory gate remains
an unmeasured admission envelope, not proof that full-context execution fits.
Three trainable exports total881,590,272 tensor bytes, plus headers and evidence.
No full native model export is produced. Runtime disk reserve remains enforced.

## Closure and delivery

The controller independently validates architecture/counts, initial-function and
probability gates, all train examples, dev generations, exact-name checkpoints,
zero-update anchor invariance and frozen selection. Optional PUBLIC keeps all
1002 requested views, immutable seals, actual owned-process closure and separate
provider-terminal evidence. The unchanged protected scorer executes outside the
solver and reports paired differences versus both anchor and trained baseline.
Source003 wheel/input-isolation implementations are imported unchanged.

Private notebook metadata is Quick Save only, offline, no new resources. The
width-only target prefix and explicit historical exclusions prevent overwriting
old capacity/fusion sources. Creating/saving metadata is not execution. No run,
subsequent upload, paid resource or formal submission is authorized by the file.

## CPU evidence and limits

The53-test local suite exercises actual tiny Qwen3/PEFT initialization,64 updates
per trained arm,0 anchor updates, checkpoint reload, all1002 synthetic PUBLIC
views, unchanged isolated scorer, corruption/tamper/deadline rejection, and exact
private source capsule/manual-clock preparation. Synthetic tests are not scores.
The official component probe reads the existing checkpoint in place, allocates
only one real layer, follows full PEFT target traversal on a meta skeleton and
exports only scalar/hash receipts. Four real layers test forward/input-gradient
preservation and two AdamW updates; no official full-model CPU/GPU run occurs.

The detailed sanitized research report records numerical values and the retained
failed component assertion that initially confused hidden-state and logit units.
Production full-model/cached logit admission remains required and unverified.
