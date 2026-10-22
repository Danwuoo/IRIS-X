# CPT preparation checkpoint, 2026-10-22

This is a public, source-only checkpoint of completed offline prerequisites.
It is not a model-quality result, a TPU readiness certificate, a formal training
launch, a resource provisioning instruction, or a claim that all preparation is
finished. No private corpus records, evaluator targets, model weights, runtime
artifacts, cloud bindings or credentials are included.

## Completed and included

- Corpus admission: strict pinned-artifact and registry validation, source and
  family ancestry checks, exclusion propagation, cross-split quarantine,
  transform-aware deduplication, bounded disk staging, restart validation and
  separate training, answer-free solver input, evaluator and audit outputs.
  Its tests use manufactured grids and provenance fixtures only. Hashes bind
  assertions; they do not independently establish a license or source lineage.
- BF16 numerical reference: finite-domain round-to-nearest and stochastic
  rounding, global-coordinate randomness, bounded atomic stream checkpoints,
  exhaustive BF16 identity and discrete-probability checks, and fixed synthetic
  writeback/AdamW replay. This reference is not a native TPU RNG.
- Token and loss-mask contract: sequence-length attention, shifted role masks,
  genuine EOS versus identical PAD token handling, explicit Unicode policy,
  no silent truncation, no multi-document packing and no unreviewed SFT split.
  The optional tokenizer probe requires separately available hash-pinned public
  tokenizer files; no tokenizer or model bytes are distributed here.
- Optional JAX/Flax optimizer bridge: Optax state layout is retained, native
  FP32 parameter islands are preserved, BF16 final writes use stochastic
  rounding, rejected updates leave state unchanged, and checkpoint restoration
  binds the seed and software policy. No persistent FP32 master is introduced.

## Validation of this public snapshot

Offline checks in a clean public-tree worktree:

- 59 focused tests passed for admission, NumPy numerics and token/mask contracts.
- 30 fixed synthetic numerical replay cases completed. All declared sampled
  probability tolerances passed and all exhaustive discrete means were exact.
- 7 optional CPU JAX tests passed, including real toy-model gradients, JIT
  updates, invalid-update rejection and Orbax next-update checkpoint replay.
  Versions: JAX/jaxlib 0.11.1, Flax 0.12.10, Optax 0.2.8, Orbax 0.12.7.

The base public CI installs NumPy, not the optional JAX stack. Its default test
discovery does not establish optimizer acceptance. Run that explicit lane in an
already prepared compatible environment:

```sh
JAX_PLATFORMS=cpu PYTHONHASHSEED=0 python -m unittest \
  tools.qwen35_bf16_optimizer_20261021.test_optimizer -v
```

Linux admission tests exercise real POSIX locks and filesystem behavior. The
Windows-portable lane reports those and directory-fsync checkpoint tests as
unverified instead of pretending to supply equivalent semantics.

## What remains unproven

No Qwen weights or real corpus are loaded by these acceptance tests. No TPU
forward, backward, optimizer update, full-model memory fit, throughput, training
quality improvement or ARC score is established by this checkpoint. A valid
stochastic write does not imply useful learning; FP32 candidate arithmetic can
already erase an update before the BF16 conversion.

Native model/conversion/parity integration, backend runtime locks, actual data
mixture and cloud execution bindings are outside this publication. Their absence
is not evidence that they passed or failed. No unfinished Compute adapter is
published. Existing historical runs and unrelated local work remain unchanged.

## Source and licensing boundary

These modules implement known numerical and data-validation techniques; they
are not claimed as new research. Bibliographic references remain in the package
READMEs. No upstream library implementation, dependency wheel, model artifact or
dataset body is vendored. Existing repository licensing is unchanged; publication
does not grant additional rights to third-party models, data or dependencies.

The original private worktree is not the publication source. An exact allowlist
was assembled on the already-public branch parent, without copying local history
or including arbitrary untracked files.
