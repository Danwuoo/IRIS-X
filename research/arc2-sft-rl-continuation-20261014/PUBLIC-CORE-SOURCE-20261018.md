# Public core source checkpoint

This checkpoint publishes source and synthetic CPU regression tests for train-only diagnostics, compact FP32 computation, capacity comparison and efficient-fusion mechanisms. The official baseline convergence path uses `fp32-backbone-math-v1`: FP32 residence, disabled autocast/TF32, math SDPA, and matching non-reentrant checkpoint recomputation. Historical numerical policies remain separately identified.

Included capacity/fusion components provide local model, workflow, controller/worker, artifact-validation and scoring mechanisms. Private provider launchers, source/notebook configuration, CPU startup entrypoints and delivery capsules are excluded. This checkout is not the exact source capsule of a private execution and does not establish a deployable provider workflow.

Numerical admission thresholds, provenance/source-integrity checks, process closure, data separation and complete-denominator requirements remain enforced. Private datasets, protected evaluator bodies, raw execution outputs, credentials and model weights are not included. Existing public wrap-up documentation remains intact.

Synthetic CPU validation establishes mechanisms only. It does not establish official-model GPU feasibility, a new benchmark result, competition eligibility or a formal submission.

## Scope and validation

The release overlays 38 reviewed source/test paths and this note onto the prior public checkpoint. All source/test bytes are unchanged from their reviewed implementation; private delivery dependencies and operational history are not merged. Validation against this public subset completed on Linux with the existing local environments:

- Minimal-dependency public lane: `python tools/repository_check.py --public`, 2,379 tests, 1,877 passed and 502 explicit or optional skips; repository invariants and whitespace checks passed.
- Focused actual tiny-model CPU integration: 176 tests passed with zero skips across the eleven changed test modules, using PyTorch 2.8.0+cpu, Transformers 5.8.1 and PEFT 0.21.0.

These local results are not native Windows execution proof or full historical retained-evidence acceptance. The separate CI matrix must be read for its own exact commit.
