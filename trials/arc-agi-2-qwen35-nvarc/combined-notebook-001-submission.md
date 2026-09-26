# Combined M2/M3 notebook 001: submission record

Status: version 1 accepted; runtime unqueried
Date: 2026-09-26
Authority: [Decision 0035](../../docs/decisions/0035-submit-nvarc-combined-two-gpu-notebook.md)

This record extends the [local draft review](combined-notebook-001.md).
The owner requested submission using previous successful Kaggle cases.
The new private notebook is `danielwuu/nvarc-m2-m3-combined-001`.
M2 and M3 each use one distinct L4 GPU within one 1,800-second notebook.
Provider allocation may contain four GPUs. Existing Datasets, exact materials,
workloads and generation limits are retained; no Dataset update is required.

The submission reuses the successful official competition mount, explicit
`NvidiaL4` CLI option, offline pinned dependency installation and removal of
incompatible optional `torchao`. The expired local OAuth credential was
refreshed and the owner account verified before reserving the kernel push;
no notebook status, logs or outputs were queried for that authentication check.

The sole provider request was reserved in
`.irisx/arc-agi-2/qwen35-nvarc/m2-m3/decision-0035-execution-ledger.json`.
Rejection or uncertainty consumes it. Stop at the receipt: no monitoring,
output retrieval, retry, scoring or heartbeat is authorized.

Local tests and a submission receipt do not establish successful GPU startup
or completed model work.

## Approved package and offline verification

The exact package is retained at
`.irisx/arc-agi-2/qwen35-nvarc/m2-m3/combined-approved-001/`.
It contains 15 closed-inventory members plus its stage summary. Model weights
are verified by reference to retained files and mounted from existing Datasets;
they are not embedded or uploaded again.

| Binding | SHA-256 |
| --- | --- |
| Canonical approved plan | `efa10338690105c3236a8bb62d235568d2335b08a674475ba156e6b9a4abc912` |
| Plan file | `cfae351ba376a1c354950ee6ae6205cf69e5d01263a3c6bbeea6c0ec502035f5` |
| Notebook file | `7abee8dec6b24cdb260cc57c006101e8c004acd3e59e221d8eaaf904f47852cb` |
| Kernel metadata | `9444c3865269bc1f45578731f2f12b87734c5346464e53db617170a2e352b0c0` |
| Runtime wheel | `cd9904717591f2d6e813834136cefb629624ac933364902ae4a3525fa055facb` |
| Stage summary | `11214ca76a54fdfc1071c7c038c8c56c40fb02db9d3ce5955ec576a3e6164d39` |
| Preflight JSON | `5a68886eaf9b83f03b685d13a32687796a8be1b9f316887678eae984c72ef16d` |
| Draft/approved comparison | `b79817383d06ad7b2c41fa48861138632daf47aefe809bd66361d4d3e62a17ba` |

Offline preflight verified the embedded bytes, exact approved template, closed
inventory, source bundle, retained export and cached tokenizer. Its stdlib
guard probe is deliberately truncated before shared setup; it confirms the
approved envelope is accepted and the inert draft rejected without loading
models, installing dependencies or making provider calls.

The focused authorization/process suite passed 19 tests and the affected
strict package suite passed five, including parent/worker guards loaded from
the actual runtime wheel. Evidence is retained in
`.irisx/nvarc-combined-activation-focused-001.txt` and
`.irisx/nvarc-combined-activation-strict-001.txt`.
Original draft bytes, standalone templates and prior submitted identities
remain unchanged. Actual CUDA UUID mapping and simultaneous GPU execution
remain pending; no local test claims to establish them.

Required `python tools/repository_check.py --all` passed: 240 tests, four
existing optional skips, repository invariants and whitespace checks.
The log is `.irisx/nvarc-combined-decision-0035-repository.txt`.

## Submission receipt

Kaggle accepted version 1 of
[`danielwuu/nvarc-m2-m3-combined-001`](https://www.kaggle.com/code/danielwuu/nvarc-m2-m3-combined-001)
at `2026-09-26T15:54:46.688412+00:00` (23:54 Taipei).
The source commit is `7926dc2ce4ce0e237291c28578ca41d5e97cf7d8`.
The CLI returned exit code 0 and `Kernel version 1 successfully pushed`.
The exact notebook title equals its slug; the accepted URL matches the plan.

The sole push and receipt are retained in the local atomic ledger and
`.irisx/arc-agi-2/qwen35-nvarc/m2-m3/decision-0035-push.txt`.
Receipt SHA-256 is
`3b9cc3a9246faea799394f16e3fe18b471d1a9bb13986dd2623c32f9e137f6fb`.
One push is consumed. There were zero Dataset mutations and zero status,
log, output or retrieval requests for this notebook. No heartbeat was resumed.

The task stopped at submission acceptance. Provider queue/running state,
two-worker readiness, actual GPU allocation and model outcomes are unobserved.
The receipt is not runtime success; no retry or retrieval follows automatically.
