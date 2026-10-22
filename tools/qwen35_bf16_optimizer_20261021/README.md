# BF16 final-write optimizer bridge

CPU-validated prerequisite, not a full-model TPU-ready training claim.

Uses the existing Optax AdamW transform with explicit BF16 moment configuration,
then changes only final parameter application to stochastic BF16 rounding.
Native FP32 source islands remain FP32. No full FP32 master is created.
Per-leaf FP32 candidates and PRNG arrays are temporary, but compiler aliasing and
actual accelerator peak memory remain a mandatory pilot admission item.

Pinned CPU validation: JAX/jaxlib0.11.1, Flax0.12.10, Optax0.2.8, Orbax0.12.7.
The full TPU libtpu/container is not certified by this CPU lock.

## Required caller contract

1. Build AdamW with `mu_dtype=bfloat16`, and verify the actual persistent state
   tree, not only a config flag. FP32 source parameters may retain corresponding
   FP32 optimizer leaves; bulk matrices must not silently become FP32.
2. Instantiate `BF16StochasticOptimizer` instead of stock `nnx.Optimizer`.
3. `update` returns an `accepted` scalar. The native training host MUST consume
   it and stop on false. Invalid gradients/candidates do not mutate any params,
   moments or counter. Ignoring this return is not an acceptable integration.
4. Save `policy_binding(seed)` with resolved configuration and checkpoint.
   Before restore, call `validate_policy_binding(saved, seed)` and check the
   original data iterator, model tree shapes/paths, step and runtime topology.
   Static seed/policy are NOT automatically saved by stock NNX checkpointing.
5. PRNG uses global leaf shapes, canonical typed paths, seed and step. Do not
   generate independent local-shard arrays or silently reshape scanned leaves.
   The same global array is bitwise reproducible across 1/4 virtual CPU devices;
   real TPU placement, compiler behavior and memory are still unvalidated.
6. Do not change gradients, weight decay, loss masking or optimizer hyperparameters
   and attribute effects only to stochastic rounding. This module does not claim
   equivalence of finite training trajectories to FP32 or proof of learning gain.

## Evidence

Seven focused CPU tests execute real `nnx.grad`, JIT updates, actual Orbax save
and exact next-update replay. A separate fresh-process 4-device CPU check confirms
same-global-shape sharded/unsharded writeback equality. They do not load 35B weights
or prove TPU fit. Native MaxText integration patches are reviewed separately.

This is an implementation of a known numerical technique, not a new method.
References: https://arxiv.org/abs/2010.06192 ;
https://proceedings.mlr.press/v258/ozkara25b.html ;
https://github.com/amazon-science/adamw-sr .

## Explicit optional CPU acceptance lane

The repository's base CI installs NumPy only; it does not certify this optional
JAX/Flax optimizer. With the separately prepared pinned environment, run:

    JAX_PLATFORMS=cpu PYTHONHASHSEED=0 python -m unittest tools.qwen35_bf16_optimizer_20261021.test_optimizer -v

Missing or incompatible optional dependencies fail this explicit lane; they are
not silently skipped. The test module lives beside the adapter to keep ordinary
public-checkout discovery independent of this optional backend.
