# IRIS stopped-source checkpoint — 2026-10-27

IRIS development and new experiments stopped at the owner's direction on
October 27, 2026. This commit preserves reviewed source and synthetic tests;
it is not a runnable job package, training authorization, completed model,
quality improvement claim or permission to resume earlier research.

## Terminal state

- **PS GPU:** the corrected first-code-clock source was imported but no GPU
  run was submitted. The saved version initially lacked input/accelerator
  bindings; later draft binding work stopped, RTX activation was cancelled,
  and the editor session was verified OFF. No new model result exists.
- **TPU:** resource allocation occurred, but the guest ended
  `FAILED_BEFORE_NATIVE` with `ValueError`, no native child, no checkpoint
  commits and no uploaded outputs. This is a startup failure, not a failed
  training-method comparison. No new training attempt is authorized.
- **TPU closure:** node and queued resource both returned provider NOT_FOUND
  at 10:11:34 UTC. The exact temporary IAM binding was removed and read back
  at 10:12:01 UTC; unrelated bindings were preserved. No ongoing watchdog or
  paid resource from this job remains. Billing amount is not established here.
- **Evaluation:** no fresh DEV correctness result is claimed. Historical
  design-seen development and consumed evaluation qualifications still apply.
- **SB:** separate continuing work, outside this checkpoint and unchanged.

## Preserved implementation

`source/` contains byte-identical reviewed source and synthetic tests, stored
as inert `.py.txt` documents rather than active repository executables, for:

1. Fixed-pair matched positive-CE/DPO native experiment and training contracts.
2. First-actual-code 7,200-second whole-session publication wrapper.
3. Isolated evaluation/join code, without any real answers or predictions.
4. Public-support eight-update TPU optimization and portable adapter code.

`SOURCE-PROVENANCE.json` is the explicit allowlist with byte sizes and SHA-256
hashes. Existing source pins and historical immutable identities are retained,
not rewritten to claim a new scientific outcome. These source modules are a
preservation snapshot, not a self-contained execution distribution: frozen
external input/configuration documents and runtime/vendor material are absent.
Some synthetic tests require separately retained source fixtures or optional
libraries. Source preservation does not prove native numerical parity.

## Deliberate exclusions

No real target/pair/parity bodies, real task grids or predictions, notebooks, archives,
weights, checkpoints, credentials, account/provider configuration, raw logs,
live controllers or SB files are included. Handwritten toy fixtures remain in tests. Infrastructure-bound guest/owner
scripts and their private operational configuration remain local rather than
publishing cloud identifiers. Their final cleanup facts are summarized above.
Thread deletion is a separate user-interface operation and is not represented
as complete by this Git checkpoint.

## Validation

See `VALIDATION.json` for checks actually performed for this checkpoint.
A source/synthetic check is not GPU/TPU execution or a model-effectiveness test.
