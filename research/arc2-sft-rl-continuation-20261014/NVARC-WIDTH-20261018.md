# Function-preserving all-layer SwiGLU width screen

> Public-subset scope: this checkout includes only the width expansion, model
> integration, CPU component probe and model unit tests. The complete three-arm
> workflow, provider launchers, delivery capsule and operational integration
> tests remain private. Descriptions below cover that separately validated
> implementation; this public subset is not a ready-to-run Kaggle package.

## Status

New independent implementation: native FFN6144→8192 in every one of28 compact
Qwen3 layers, not a renamed LoRA-rank change. Hidden2048, residuals, GQA, RMSNorm,
RoPE, tokenizer, rank64/alpha16 rsLoRA, source admission and evaluator contracts
remain unchanged. Original sources and delivered artifacts are not edited.

The implementation passes53 focused CPU tests and four actual official-weight
component probes. An independent reviewer separately checked one actual layer,
meta-skeleton versus full-real PEFT initialization, finite gradients and exact
checkpoint reload. This is implementation evidence only. No official full-model
GPU forward, full-context feasibility, held-demo score, PUBLIC score, hidden score,
formal submission or capability improvement is established.

## Method and initialization

[Net2Net, Chen, Goodfellow and Shlens](https://arxiv.org/abs/1511.05641) provides
the primary function-preserving widening principle. This project's paired
antisymmetric SwiGLU/fresh-LoRA construction is an adaptation with its own proof,
not a reproduction of that paper's architecture or results.

Choose2048 distinct channels with CPU randperm seed20261018+layer index. For a
selected original channel(g,u,d), make(g,u+δ,d/2) and(g,u−δ,d/2), where each δ
coefficient equals that source up coefficient times an independent Rademacher
sign times2^-5. Since the gate is shared, the two contributions sum exactly to
the source contribution in real arithmetic. The fixed3.125% dyadic perturbation
was chosen before task scoring; it is not answer-derived tuning. The code asserts
exact FP32 paired up sums and down compensation.

Expansion occurs only after exact BF16-source→FP32 promotion. Re-quantizing the
new matrices to BF16 is forbidden. Larger GEMM reductions still round, so the
actual full/cached initial-logit gate remains1e-4 official/1e-5 tiny, with identical
greedy tokens. The separate sampled-versus-full0.05 official probability gate
also remains unchanged. The independent CPU consumer rejects forged gate limits,
measured gaps, token parity and full-context claims.

Only unused, checkpoint-unloaded, zero-B default adapters are accepted. Existing
gate/up A, old B rows, down-A old columns, down B and all non-FFN tensors are
preserved byte-for-byte. Extra gate/up B rows start at zero. Extra down-A columns
are seeded independently, use the original fan-in range, and are rounded BF16
then promoted FP32. No old optimizer/cache state or nonzero adapter is mapped.
Native expanded tensors stay frozen; exact named trainables are serialized and
reloaded only after deterministic source-derived architecture reconstruction.

Plain identical replication has redundant antisymmetric channel directions.
Here opposite gate-B row directions encounter different up features. Real
loss gradients and AdamW updates establish nonzero/nonidentical directions;
this is stronger than parameter counts, but does not prove useful task learning.

## Bounded comparison

- Untouched anchor:0 updates and a distinct immutable checkpoint.
- Dense baseline:64 updates.
- Width8192:64 updates.

The trained arms share every serialized example/order from16 admitted training
parents,4 rounds, fresh AdamW2e-5, weight decay0.01. All three use the same16-parent
held-demo panel, two transformed views and no TTT. All work is sequential, with
fixed deadlines. The anchor must retain exact initial trainable bytes.

A unique generated-exact dev winner must strictly beat the untouched anchor;
width must also beat the trained dense arm. Ties/incomplete work retain anchor.
Selection freezes before optional PUBLIC inference. All three PUBLIC arms retain
120 tasks/167 queries,334 views each,1002 total views. Missing work remains visible,
never drops the denominator, and cannot change selection. Original protected
scoring occurs after owned-process closure and immutable seals, outside the solver,
and reports paired diagnostics versus both anchor and trained baseline.

This is equal-step screening for two trained arms, not equal compute or general
expansion efficacy. Initial-weight contamination and prior PUBLIC exposure remain
explicit. All new score interpretations would remain development-qualified.

## Exact geometry and cost

| Quantity | Anchor/dense | Width8192 |
| --- | ---: | ---: |
| Native frozen parameters |1,409,475,584|1,761,797,120|
| Trainable parameters |69,795,840|80,805,888|
| Total resident parameters |1,479,271,424|1,842,603,008|
| Potentially active/token |1,479,205,888|1,842,537,472|
| FP32 resident parameter bytes |5,917,085,696|7,370,412,032|
| Analytic linear-forward ops/token |2,958,098,432|3,684,761,600|

Native growth is352,321,536; rank64 adapter growth11,010,048. All added channels
execute. Counts exclude unused original compact heads from the active convention,
but include their physical resident storage. FLOP proxies omit quadratic attention,
activation functions, backward/recomputation, optimizer and normalization.

Width adds0.323GB gradient storage and0.646GB Adam moments beyond7.37GB parameters;
a trainable rollback snapshot adds about0.323GB. Full FP32 math attention at8192
tokens may need multiple4.29GB attention-sized buffers. These are lower-bound
accounting components, not a measured peak. The40GiB free-device admission gate
remains conservative and unverified. Three trainable exports require881,590,272
payload bytes plus metadata; no native-model tensor export is needed.

## CPU observations

Environment:Torch2.8.0+cpu, Transformers5.8.1, PEFT0.21.0, safetensors0.8.0.
The four official probes stream only selected layer bytes from the retained
checkpoint, after exact whole-file/source admission. They allocate a full meta
skeleton to preserve PEFT target traversal, materialize one real layer, then
exercise native code. CPU initializer identity is not falsely claimed to be
bitwise identical to the distinct CUDA RNG stream.

| Original layer | FFN max output drift | Input-gradient max drift | Residual hidden max drift |
| --- | ---: | ---: | ---: |
|6|2.3842e-7|2.5466e-11|5.7220e-6|
|13|3.5763e-7|1.8190e-11|1.5259e-5|
|20|2.6822e-7|4.3656e-11|2.2888e-5|
|27|7.1526e-7|1.0186e-10|9.7656e-4|

Input-gradient relative L2 errors are2.49e-7–3.35e-7. Residual hidden relative L2
errors are2.61e-7–2.77e-7. Every one of2048 gate-B replica row pairs receives
distinct finite gradients and distinct updates in each actual AdamW2e-5 step;
all three A projections receive nonzero gradients on step2. Frozen native hashes
remain unchanged. Typical child peak RSS is0.93GB; no model/adaptor tensors are
exported by the official probe.

Counterfactual BF16 re-quantization then FP32 execution has FFN max drift up to
5.6922e-4, visibly worse than the admitted construction. It is not a fallback.

The first probe attempt mistakenly compared residual hidden-state drift to a
logit-unit1e-4 ceiling and failed layer27. That attempt is retained, not relabeled.
The corrected component test reports hidden drift descriptively, adds the input
Jacobian check, and never claims to execute or replace the full-model1e-4 logit
gate. Actual full-model gate failure would abort, not trigger threshold widening.

The independent layer13 probe also found noncollinear token-level gate tangent
features for every pair,15753 first-Adam coefficient differences>1e-7, all131072
new down-A coefficients with nonzero step2 gradients, finite states, and unchanged
frozen bytes. Separate full-real/meta-real initialization comparison found exact
selected-layer A equality across all seven target projections.

The53 focused tests use real tiny Qwen3/PEFT. They cover64 actual updates per trained
arm, zero-update anchor invariance,1002 synthetic PUBLIC views, raw reconstruction,
checkpoint roundtrip, actual original scorer CLI, full denominators, corrupted
source/metadata/predictions, failed numeric gates, poisoned optimizer outcomes,
original clocks, no implicit execution, and local source transport. These generated
synthetic grids and scorer fixtures are not actual PUBLIC or model-quality results.

The broad repository aggregate is separate from this focused evidence; inherited
unrelated failures are not modified or suppressed to make this work appear green.
