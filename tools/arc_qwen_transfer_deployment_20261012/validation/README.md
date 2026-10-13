# True-ARC transfer terminal validator

This is a separate, offline, standard-library-only successor validator. It does not import the neural runtime, load model weights, invoke a shell/provider, install software, extract ZIP members to disk, open evaluator assets, or rescore gold. Exact archive integrity hashes/CRC include all archived bytes; target escrows are never parsed. Original historical material and validators were not edited.

## Interfaces

- `validate_outputs(download_root, *, manifest, finalization, launch_journal, launch_receipt, retrieval_receipt, finalized_notebook, allow_synthetic=False)` validates the exact code11 / notebook21 / transfer001 collector envelope and both original owned-process closures. Manifest and notebook are exact local files; the retrieval receipt is an object.
- `validate_content(output_root, expected_source, *, source_root, allow_synthetic=False, verify_checkpoint_bytes=False)` performs source-aware content subchecks for directly retained evidence. This never sets `provider_envelope_verified=True`. `source_root` is the exact frozen source directory or source ZIP; `expected_source` is the exact inner identity mapping (or its JSON file).
- `validate_public`, `validate_ttt`, `validate_model_identity`, `validate_public_rows`, and the other named checks are available for qualified direct/manual evidence. They do not grant provider admission.

The three Python files and `frozen-panel-plan.json` are inseparable validation runtime files. The collector must hash-gate all four. Helper imports use explicit sibling file paths and work when loaded by `importlib.util.spec_from_file_location` from another directory.

## Meaning of results

`valid=True` establishes internal evidence integrity at the stated level. `status` retains TRANSFER_COMPLETE / TRANSFER_PARTIAL / TRANSFER_NOT_ADMITTED / TRANSFER_FAILED. Provider COMPLETE by itself never implies science or operational success. `science_complete`, `operational_success`, `goal_met`, synthetic origin, provider-envelope verification, and checkpoint-byte verification are separate Booleans.

Only a real, complete, source/model-bound full120-task/167-query measurement from the unchanged original scorer with at least151 correct top-two answers may establish the numerical public goal. The source-bound detail report is matched to the public summary; truth-free per-query scorer rows are independently aggregated and matched to the sealed native-output pool. A goal flag also requires clean real operational/science completion. Provider ERROR or CANCEL_ACKNOWLEDGED forces reported operational and goal flags false while preserving verified runtime/measurement fields separately.

The CPU public evaluator emits a clean bounded-subprocess receipt, not an owned-tree proof; validation requires that actual receipt and its exact request/seal/output bindings. This is explicitly qualified as source-bound subprocess evidence. Independent outer/model PID-and-birth closures are verified separately.

Production source identity requires the finalized runtime release and its exact independent runtime-approval receipt. `dispatch_ready` is intentionally not required: the frozen notebook is an epoch-unpatched template, while operator/provider authorization gates are separately enforced. Global/program43200, inner execution42000, outer42180, provider42300, and the JIT maximum60-second age all use the same original dispatch epoch.

Checkpoint state metadata, adapter hashes, source/records/config bindings and full-state fresh-reload receipts are checked without default checkpoint downloads. The result explicitly states that missing actual checkpoint archive bytes were not verified. If the collector explicitly supplied the archive, every inventory member, CRC and hash is checked. No checkpoint payload is unpickled or executed.

## Tests and limits

Run `python -B -m unittest discover -s validation-tests -p 'test_*.py' -v` from this package's parent directory; also run with `-O`.

The actual retained owned tiny main fixture has full48 main parents, real tiny Qwen/PEFT updates, checkpoint/reload/closure evidence and explicit128/512 calibration only. It predates later source changes and is validated against its exact frozen source, never relabeled as the final source or as production4096/GPU evidence. The actual targeted tiny TTT case validates48 updates, complete leave-one-out and query refits, and reset/selector lineage; it is not a completed16-parent TTT experiment.

The public fixture is explicit synthetic120/167 data and test-authored native receipts, with an actual stopped fixture owner and original CPU scorer subprocess. Its167/167 is a parser/bridge fixture, never scientific production evidence. The full collector fixture combines unchanged actual tiny content with explicitly fictional provider/outer envelopes, all marked synthetic. The production API rejects those envelopes. These fixtures never read real public answers or execute a production model.

Metadata-only unit fixtures used to challenge exact weight names/hashes, environment, driver and memory receipts are synthetic test data. No actual14B execution, memory fit, accuracy or efficacy claim is made by this package or its tests. Receipt verification depends on exact reviewed execution/source and provider provenance; it is not cryptographic remote attestation or a provider billing/VM termination guarantee.
