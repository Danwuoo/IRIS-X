# Generation-budget successor terminal validator

Offline, standard-library-only validation for code12 / inactive22 / active23 / transfer002 / run002. The API is unchanged:

`validate_outputs(download_root, *, manifest, finalization, launch_journal, launch_receipt, retrieval_receipt, finalized_notebook, allow_synthetic=False)`

The five inseparable runtime artifacts are `validate_transfer_outputs.py`, `budget_checks.py`, `generation_checks.py`, `selector_replay.py`, and `frozen-panel-plan.json`. Hash-gate every entry in `VALIDATION-ARTIFACTS.json`. Runtime modules are inspected as exact bytes/AST constants, never imported. Validation makes no provider/network/model call, runs no shell, loads no tensor payload, and never parses target escrows or public gold. Archive CRC/SHA checks still cover opaque archived bytes.

## Preserved guarantees

All historical model/material/environment/hardware, fixed-panel, native-cost, decoder, generated-grid, selector, training/checkpoint/reload, sealed prediction/scorer, owner-incarnation closure, mandatory-phase, archive inventory, and same-origin clock checks remain. The exact historical validator SHA `7b88b2fb219eb2f95eff6440d36afce290dc3fb9d1a565cce952386e06eac56e` and its three helper/data artifacts remain unchanged at their historical paths. The independently established v21 outer-config correction is carried forward: the exact emitted request must include all15 config keys, including execution42000 / outer42180 / provider42300, with global43200 and the original dispatch epoch.

Production source must declare512MiB aggregate expanded evidence. ZIP container cap is544MiB; ordinary members remain16MiB and only the three historical diagnostic paths may reach64MiB. Member count remains12000. Separate checkpoint limits remain2GiB expanded /2GiB+2MiB archive /32MiB each /1025 entries. Actual retained pre-cap-change tiny evidence may use its exact256MiB source only with the explicit synthetic option; it is never relabeled as final512MiB-source execution.

## New budget and forecast replay

Generation receipts/markers bind exact hard180 / normal work175 windows, internal cleanup, original branch/owner deadline, policy SHA, physical event, and nested native/wrapper clocks. Likelihood retains hard120 / normal work115. Historical calibration/update markers retain hard120 with branch-bound work, without an invented115-second soft limit. Their known event namespace, owner bound, ordering and recorded native start/deadline are checked when present. Legacy likelihood receipts have no independent wrapper-start timestamp; this limitation is stated in results rather than presented as attestation.

All224 fixed main slots bind native receipts, allowlisted timing-only sidecars, per-call evidence boundaries and the exact closed physical-ledger prefix at freeze. Later ledger appends are allowed without changing that prefix. The refreshed PUBLIC estimate is independently recomputed from every actual main timing, explicit base/trained/per-method coverage, synchronized calibration contexts through4096, maximum measured overhead and fixed full3072+1023 generation length with1.5 safety. No correctness, validity, EOS or short-output discount selects timing samples. Unsupported coverage must preserve the original conservative calibration estimate. The immutable selected estimate and its receipt SHA precede PUBLIC admission and remain linked from the phase. TTT retains calibration-based cost admission.

## Provenance and checkpoint scope

The collector supplies selected numeric23 downloaded/header byte facts, not a whole-provider inventory. Results state `inventory_scope=selected_outputs_only` and `whole_provider_inventory_verified=False`. A declared checkpoint header may establish only `HTTP200_CONTENT_LENGTH_VERIFIED`; equal size never establishes archive/hash verification. No declaration remains `UNKNOWN`, not absence. Actual checkpoint bytes, if explicitly supplied and fully CRC/SHA checked, are reported separately. Provider status COMPLETE alone establishes neither operational nor scientific success; ERROR/CANCEL status suppresses operational/goal flags while preserving qualified measurements.

Production rejects every synthetic envelope and tiny request. `valid=True` reports consistency at the stated evidence level, not scientific effectiveness or remote/billing attestation.

## Verification and fixtures

Full retained-fixture suite, normal and optimized:

`TRANSFER_VALIDATION_RELEASE=portfolio63-transfer-repair-20261012/release-candidate-002 python -B -m unittest discover -s portfolio63-transfer-repair-20261012/validation/tests -p 'test_*.py' -v`

Repeat with `python -B -O`. The final full suite includes128 tests.67 unchanged historical archive/model/phase/public-bridge interfaces are reused against successor functions. Historical public fixtures are explicit synthetic original-scorer outputs and never production accuracy evidence.

The genuine owned tiny main uses source `e02c3485ac271fa738d0bc8728ad4e7f07be3f43e698d5387c6bfbea1a07e245`, archive `63f5a4bedb746901cc3fe8ced80728555f65f4f18e744f0dbdd619a2881d30bc`, and224 real timing sidecars. It deliberately calibrates128/512 with tiny updates/output cap, so PUBLIC refresh correctly falls back. It demonstrates CPU interface/closure behavior, not14B GPU fit, throughput or accuracy. Final source `177c9a02047156f8881838c256515e4e1fcf430b2860f8960f48cd363a86c2f5` differs only in the subsequently tested aggregate-cap constant. Final-source API tests use an entirely authored before-load failure with explicit synthetic provenance and exact final manifest/source ZIP/notebook, avoiding any relabeling of the genuine tiny run.

A portable source-only bundle may omit raw owner archives, source fixtures and historical sibling fixtures. The same test command then explicitly skips unavailable fixture-dependent checks. `receipts/portable-source-only-tests.txt` records that limited run. It does not replace the full128-test receipt. No raw owner outputs or synthetic task grids are required to compile the five runtime files or run the standalone metadata/arithmetic tests.
