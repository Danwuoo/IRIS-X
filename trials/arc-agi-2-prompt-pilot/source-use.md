# Prompt-pilot source-use audit

This audit is for `arc-agi-2-prompt-pilot` and does not reactivate archived
code or Trial 002 execution authority.

## Runtime lineage adopted for baseline 001

- `src/irisx/kaggle_runner_trial002.py`: adopted the already exercised local
  Transformers 5.8.1 loader, native Qwen chat template with thinking disabled,
  one-sequence greedy generation, deterministic digit-row parser, and dual
  PyTorch / `nvidia-smi` four-L4 gate. The new runner extends only the parent
  scheduler from one job per worker to persistent dynamic workers.
- `src/irisx/arc_trial_002.py`: adopted closed-world ZIP, canonical JSON,
  material-manifest, checkpoint, and truth-free verifier patterns. New formats
  and identities are implemented in `arc_prompt_pilot.py`; no Trial 002
  constant, package, result, or executed byte is edited.
- `trials/arc-agi-2-baseline/kaggle-notebook.ipynb`: adopted the successful
  offline installation order and competition mount. Baseline 001 replaces
  `rglob` discovery with explicit base/runtime Dataset paths and exact wheel and
  outbound digests so the old wheel cannot be selected accidentally.

## DSPy and GEPA archive inspection

The cold archive records DSPy tree
`824de62cb23e2bf8b52adcb05a8804ef2c148e5d` as declared version 3.3.1 and GEPA
tree `eb66cc8bf0cdf9e7d3d25cf9f26ab0fd951bb833` as declared version 0.1.4; both
have unknown upstream commit provenance. Relevant files inspected from
`archive/pre-product-transition-2026-09-17` were:

- `sources/external/dspy/dspy/teleprompt/gepa/gepa.py`
- `sources/external/dspy/dspy/teleprompt/gepa/instruction_proposal.py`
- `sources/external/dspy/docs/docs/api/optimizers/GEPA/GEPA_Advanced.md`
- `sources/external/gepa/src/gepa/core/state.py`
- `sources/external/gepa/src/gepa/strategies/candidate_selector.py`
- `sources/external/gepa/src/gepa/strategies/acceptance.py`
- `sources/external/gepa/src/gepa/proposer/reflective_mutation/reflective_mutation.py`
- `sources/external/gepa/src/gepa/adapters/dspy_adapter/dspy_adapter.py`

They support the planned parent/frontier, minibatch acceptance, reflective
mutation, and adapter boundaries, but are not imported at runtime. Baseline 001
needs only a pure instruction adapter whose B1 messages and token IDs are
identical to B0. Before the first reflection task, development must choose and
pin an installable DSPy/GEPA release or commit and revalidate its actual API;
the archived unknown revisions are evidence, not a dependency pin.

## Deferred mechanisms

No DSPy optimizer, GEPA search, Codex proposer, SPEX comparison, holdout scorer,
TTT, or NVARC augmentation executes in baseline 001. The local B1 adapter
changes only the instruction parameter and proves render/token parity. This is
deliberate: startup verification for the fixed baseline must not be confounded
by new GPU-environment dependencies or a reflection call.
