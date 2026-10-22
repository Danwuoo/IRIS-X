# BF16 CPU numerical prerequisites, 2026-10-21

This is a bounded, offline numerical reference and test package. It is **not a
first training recipe, a deployed optimizer, a Qwen 35B experiment, or permission
to start a run**. Existing notebooks and provider state are untouched. No model
weights, actual gradients, external source acquisition, installs, or paid compute
are used. Numerical correctness, useful learning, full-model fit and backend
support remain separate questions.

## Implemented contract

- Persistent weight encodings in the BF16 experimental arms are NumPy `uint16`
  arrays, exactly two bytes per element. BF16-moment replay also stores mu/nu in
  `uint16`; no FP32 master weights exist in those arms. Small diagnostic FP32/FP64
  shadows are separate, not a proposed production state layout.
- Final updates are first formed in explicit FP32, then converted directly to
  BF16. Casting the candidate to BF16 before stochastic rounding destroys the
  information SR needs. Local FP32 update/reduction arithmetic is allowed and is
  **not** the same as full-FP32 persistent weights.
- RNE uses ties-to-even. SR uses all 16 discarded FP32 bits. If the magnitude's
  low bits are `r`, it rounds away from zero exactly when uniform integer
  `U in [0, 65535] < r`. For negative numbers, away from zero is the numeric lower,
  not upper, neighbor. For adjacent numeric values `a <= x <= b`, upper-round
  probability is `(x-a)/(b-a)` and variance is `(x-a)(b-x)`.
- Signed zero and all BF16 subnormals are preserved. The input must already have
  explicit native FP32 dtype. NaN/Inf and finite magnitudes above the largest
  finite BF16 value are rejected, not saturated/coerced. Rejecting the latter
  avoids claiming an unbiased finite bracket where none exists. This policy is
  stricter than IEEE conversions that may overflow to infinity.
- The reference enforces an element cap of 1,048,576. The measured tensor is just
  192 elements. A bounded 786,432-byte random-bit replay cache is used to compare
  arms with common randomness. It is **not** a whole-model random-tensor proposal
  or a measured memory bound for a future compiler/backend.

## Randomness, ordering and checkpoints

The scalar reference derives 16 bits with SHA-256 over a versioned domain prefix,
64-bit seed, 64-bit step, length-prefixed ASCII canonical leaf identity and 64-bit
**global C-order flat element index**. Numeric encoding is little endian. The
first two digest bytes are the random `uint16`.

- Repartitioning, chunk sizes, and iteration order do not change a coordinate's
  bits when that logical identity stays fixed. Replica copies must share it.
- Different leaf/step/seed changes the stream. A rank-local index reset is not
  valid resharding. Duplicate logical indices intentionally duplicate noise;
  shard coverage/uniqueness remains a caller obligation, not an inferred feature.
- SHA-256 sampling is a portable CPU reference, not Threefry, XLA, Pallas or a TPU
  hardware RNG implementation. There is no bitwise compatibility or native v5p
  execution claim. Backend subnormal/overflow behavior remains unmeasured.
- `RoundingStream` is single-owner and sequential, and requires a writable
  C-contiguous global destination (overlapping zero-stride views are rejected);
  validation precedes changes
  to either the BF16 buffer or cursor. Failed chunks leave both unchanged.
- Checkpoints are bounded strict JSON, not pickle. They include BF16 bytes,
  seed/step/leaf/global size/cursor, RNG algorithm/bit width/byte order/index
  scheme, implementation version, schema, overflow policy, and a candidate-input
  SHA-256 binding. Reload requires the caller to supply the expected identity
  and the digest of its regenerated exact candidates. The caller remains
  responsible for truthful candidate binding and external input availability.
- Missing/unknown fields, duplicate JSON keys, bad types/ranges, altered data,
  nonfinite state, changed input identity or unsupported contracts fail closed.
  Restore returns fresh objects only after all fields validate; no live state is
  partly overwritten. Write uses same-directory temp + fsync + atomic replace.
  A failure before replace preserves the prior file; an error after replace
  requires readback to learn which valid file exists, not blind retry.
- The SHA-256 envelope detects accidental corruption, not a malicious writer
  able to replace both payload and digest. This is not a distributed checkpoint,
  optimizer-moment checkpoint, crash-atomic multi-process update, or full model
  training resume contract.

## Experiments and fixed interpretation

The source fixes seeds 0..7, 256 steps, snapshots 1/16/64/256, three diagnostic
LR values (1e-6, 1e-5, 3e-5), and five histories before execution: constant
signed updates, alternating cancellation, one impulse per 32 steps, decay only,
and decaying oscillation. Initial tensor groups have scales 0, 2^-16, 2^-8,
0.25, 1 and 16, with deterministic mantissas and both signs. These are synthetic
stress distributions, not representative estimates of Qwen's actual leaves.

1. **Writeback-only replay** gives nearest and SR identical predetermined FP32
   updates; a small FP64 unrounded reference accumulates those exact updates.
   The decay-only history is precomputed from that shadow so writeback remains
   the only difference. A separate FP32 shadow diagnoses candidate-arithmetic
   loss. This isolates the quantizer; it does not model changing gradients.
2. **AdamW numerical replay** supplies the same exogenous synthetic FP32 gradient
   history to every arm. The BF16 arms compute moment candidates locally in
   FP32, RNE-write mu/nu to BF16, then compute bias correction, epsilon, decay
   and update locally in FP32. Nearest and SR differ only at weight writeback.
   An all-FP32 reference and a BF16-moment/FP32-weight shadow expose moment and
   final-write effects separately. This deliberately specified arithmetic
   variant is **not** stock native BF16 Adam, MaxText/Optax parity, BF16 raw-gradient
   validation, or a selected production algorithm.

Reported values include update-survival diagnostics, never-moved fraction,
signed accumulated bias, individual-path and ensemble-mean RMSE, displacement
projection, variance, groupwise statistics, final-write accumulated error,
FP32-addition error, moment error and candidate-update error. None is an automatic
learning admission threshold. In particular nonzero motion does not establish
learning, and exact cancellation has zero reference displacement, so its
projection ratio is reported as null rather than dividing by zero.

The statistical check fixes 12 cases, 8 x 4096 draws, and familywise alpha 1e-6
with a Hoeffding union-bound tolerance. This interpretation is conditional on
independent uniform PRNG draws; the hash implementation is empirically checked,
not proven statistically independent. Rare events with fewer than 20 expected
samples are explicitly marked low-power. Independent of that finite sampling,
all 65,536 possible random-bit values are enumerated per selected input, proving
the reference's discrete mapping, exact mean, support and variance for those
cases. All 65,280 finite BF16 representations are tested for exact identity.
There is no seed/horizon tuning based on results.

## Measured findings (fixed 30 cases)

The JSON receipt contains the complete measured results, not just this selection.
At LR=1e-6 in fixed constant-update replay, nearest never moves the groups whose
initial scales are 2^-8, 0.25, 1 and 16. At scale 2^-8, SR's ensemble displacement
projection is 1.00577 versus nearest's 0.0. However scale 16 still does not move
in this small SR window, and individual SR paths have substantially higher
variance. Eight seeds/256 steps do not establish rare-event long-horizon behavior.

Across the full tensor in that case, nearest's projection is 0.32672 and SR's
0.82163. Yet individual-path RMSE is 0.00020259 nearest versus 0.00057894 SR;
SR ensemble-mean RMSE is 0.00020694. SR is not uniformly better under every finite
sample/error metric. Alternating cancellation also demonstrates nonzero SR
random-walk error where the nearest path can return exactly to its starting value.

A particularly important boundary: decay-only LR=1e-6 loses the candidate update
in **FP32 addition itself**, before BF16 conversion. SR cannot restore bits that
never reached it. In the writeback experiment the FP64 intended displacement is
nonzero and error is reported; in the FP32 Adam reference the same tiny update
is also erased, so zero error against that reference is **not** success at
preserving the intended real-valued update. The two references must not be
collapsed into one favorable score.

Local unbiased final rounding does not make BF16 moments, nonlinear Adam, or a
changing-gradient training trajectory unbiased. These results support building
and testing a protected writeback mechanism; they do not certify stable learning,
held-out quality, a learning rate, hardware support, memory fit or throughput.

## Reproduce offline

From the repository root, with existing NumPy (no installation):

```sh
PYTHONHASHSEED=0 python -m unittest discover -s tests -p test_bf16_numeric_prerequisites_20261021.py -v
PYTHONHASHSEED=0 OPENBLAS_NUM_THREADS=1 python -m tools.bf16_numeric_prerequisites_20261021.experiments
```

An existing numerical receipt is never overwritten; choose a fresh `--output`
directory for another verification. Outputs default to the ignored
`.irisx/cpt-prerequisites-20261021/numerics/numerical-receipt.json` and bind source
hashes, initial tensor bytes, RNG cache bytes, environment and all fixed choices.
Receipts are local diagnostic evidence, not product acceptance or publication.
The full repository validator may fail on unrelated historical fixtures; report
its result separately from this focused suite.

## Prior research context, not newly verified backend evidence

References for the known numerical technique and backend caveats:

- [Revisiting BFloat16 Training](https://arxiv.org/abs/2010.06192)
- [AISTATS 2025 BF16 stochastic rounding](https://proceedings.mlr.press/v258/ozkara25b.html)
- [Pinned experimental TPU lowering](https://github.com/jax-ml/jax/blob/028d0db54dad1c545af05dc34564c826f7ef77eb/jax/_src/pallas/mosaic/lowering.py#L5144-L5168)
- [Pallas TPU PRNG caveats](https://docs.jax.dev/en/latest/pallas/tpu/prng.html)

No new remote verification was performed for this package. A future real-data
and backend comparison still needs pinned compatible software, actual gradients,
checkpointed full optimizer state, shard/replica integration, compiled/live
memory measurement and separately authorized model-level learning validation.
