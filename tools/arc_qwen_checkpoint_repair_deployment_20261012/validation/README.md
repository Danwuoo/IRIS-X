# Checkpoint-repair terminal validator

Offline, standard-library-only successor for code13 / inactive24 / active25 / transfer003 / run003. The collector API is unchanged:

`validate_outputs(download_root, *, manifest, finalization, launch_journal, launch_receipt, retrieval_receipt, finalized_notebook, allow_synthetic=False)`

The five inseparable runtime artifacts are `validate_transfer_outputs.py`, `budget_checks.py`, `generation_checks.py`, `selector_replay.py`, and `frozen-panel-plan.json`. Runtime source is read as bytes or AST constants, never imported. Validation makes no provider/network/model call, runs no shell, loads no tensor payload, and never parses target escrows or public gold. Archive CRC/SHA checks cover opaque archived bytes.

## Preserved contract

The predecessor five-file validator stays unchanged at its original path, including main SHA `416d7f93e1b123efd9aaef7948c7350dab524cfb33afa14ea8077e1cd076c98b`. The four helper/data files in this successor are byte-identical to that predecessor. Model/material/environment/hardware, fixed panels, native-cost accounting, decoder, generated-grid replay, selector, full-state reload, scorer, process closure, mandatory phases, inventory, generation-budget and timing-refresh checks remain.

The publication format is `irisx/qwen14b-transfer-checkpoint-repair-publication-contract-v1`. Numeric25 provider evidence and transfer003/run003/source003 are required. Numeric23 is historical evidence, whose provider COMPLETE and runtime TRANSFER_PARTIAL remain distinct. Its original source SHA `a7451ae7a341c36483737987d2edfaabd0e2e5cb8890234ec6b56f8565b26f03` is never relabeled.

The actual outer request must equal all15 submitted notebook config fields, with type-sensitive JSON equality. This includes execution42000 / outer42180 / provider42300 and the original dispatch epoch; global/program43200 remains unchanged. Evidence caps stay512MiB expanded /544MiB ZIP,12000 entries,16MiB ordinary members and64MiB only for the three historical large diagnostic paths. Checkpoint caps stay2GiB expanded /2GiB+2MiB ZIP /32MiB individual /1025 entries.

## Checkpoint repair checks

The source-bound schedule contracts are global0/64/256, task-local0/8/16, and explicitly tiny-fixture-only0/1/2. Strict types prevent Boolean or floating-point values from impersonating updates. The publication checkpoint descriptor binds all schedules to exact checkpoint-policy, protocol and shared checkpoint source bytes.

For every retained global checkpoint, the validator independently checks:

- The reached global checkpoint prefix, exact manifest/receipt/inference update, branch and source-bound schedule
- The complete trainer source map, rather than an arbitrary matching subset
- Exact unchanged trainer defaults/factory config, including split manifest and decoder commitment
- Ordered records reconstructed from native admission rows and solver dataset, native record/content digest, count and protocol/plan lineage
- Compact full manifest, resume JSON and standalone inference-index wrappers against declared asset SHA/length inventory
- Matching full-state/inference adapter identities, resume config/source identity, global/task scope, JSON update counters and scheduler counters
- Fresh full-state reload receipts, live parameter-binding continuity and unchanged physical accounting

The representative task checkpoint remains only the runtime's fixed selected representative at16; this does not expand persistence to other tasks/updates. Its exported demonstration-only records, exact source case, selected global checkpoint, metadata, reload and report projections are checked. Lower-level schedule/projection tests cover actual task checkpoints0/8/16 without altering the experiment.

## Evidence qualifications

The collector reports selected numeric output/header facts, never a whole-provider inventory. An HTTP200 Content-Length observation establishes only `HTTP200_CONTENT_LENGTH_VERIFIED`; equal size does not verify checkpoint archive bytes or hashes. An undeclared checkpoint remains UNKNOWN. Actual checkpoint bytes, if explicitly supplied and CRC/SHA checked, are reported separately.

Actual native CPU controls validate interfaces and full-state handling, not14B GPU fit, accuracy or throughput. Every synthetic provider/outer envelope is explicitly labeled and requires `allow_synthetic=True`. That option never promotes tiny execution to scientific or operational success. Genuine old pre-cap tiny evidence is rejected by this successor and remains checkable only with its preserved predecessor validator. Tensor payloads remain opaque even when archive bytes are verified; metadata consistency is not independent numerical attestation.

Source949bc253 is the earlier exact native baseline; source d485de95 is the final guard-repaired source. Each native control is checked only against its own immutable source snapshot. The source difference adds a negative inspection guard for omitted transfer schedule metadata. Prior native evidence is never presented as final-source execution.

## Tests

`python -B -m unittest discover -s portfolio63-checkpoint-repair-20261012/validation-tests -p 'test_*.py' -v`

Repeat with `python -B -O`. Set `TRANSFER_VALIDATION_RELEASE` to the exact release directory to test its manifest, notebook and policy descriptors. Source selection requires an immutable snapshot with an exactly matching mapping; it never rewrites source identity.

The suite includes unchanged historical archive/model/phase/public-bridge tests, unchanged budget/timing arithmetic tests, source-exact native checkpoint controls, explicit schedule/config/source/record/counter mutations, fully rehashed checkpoint metadata corruption, exact15-field outer-request mutations, and production-labeled synthetic complete/partial/failure envelopes. Fictional outer-only status controls are explicitly separate from full content acceptance. Retained full-content fixtures use actual final-source owned tiny main and before-load failure bytes; an additional before-model failure envelope is wholly authored fiction. Partial-status outer-envelope controls and checkpoint-prefix checks are synthetic; a new partial model run is not implied. Missing fixture-dependent checks are skipped explicitly, never counted as passed coverage.

Final verification: all270 tests passed normally and under Python `-O`, with zero skips, against exact release manifest `1db39d38fca5bb58c7f73035a2b555566f2a44c23c496488a0f55ba1f5da0331`. The sealed five-file descriptor is `VALIDATION-ARTIFACTS.json`; `VALIDATION-RECEIPT.json` binds the full test and actual-content receipts. Both isolated source-only packaging and an exact bundled release without raw source snapshots passed53 tests with15 explicit fixture omissions, normally and under `-O`. Those reduced runs do not replace the270-test retained-fixture validation.
