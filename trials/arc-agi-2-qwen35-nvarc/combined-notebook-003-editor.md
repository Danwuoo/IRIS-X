# Combined 003 owner-Editor notebook

Status: saved-without-running; Decision 0037's sole save is consumed.
Date: 2026-09-27

The owner requests notebook submission without running it and will execute it
from Editor and report. The original [inert candidate](combined-notebook-003-local-repair.md)
and its exact reviewed package remain preserved. The new approval envelope
uses that unexecuted candidate's run identity; scientific child fields match
the reviewed plan exactly. Background combined 002 remains unqueried.

- Run: `nvarc-m2-m3-combined-003`.
- Private kernel: `danielwuu/nvarc-m2-m3-combined-003`.
- Approval: [Decision 0037](../../docs/decisions/0037-save-nvarc-notebook-for-owner-editor.md).
- Candidate plan digest:
  `sha256:907dee6ecf5cfe043be5953ba90afb7524e5ee5ad5074b6d3d24e94170741cb8`.
- Editor plan digest:
  `sha256:13790f5930800a9614555cae183eecfe12b0443d9a8f4ba83f9d3976039410cf`.
- Generated local package:
  `.irisx/arc-agi-2/qwen35-nvarc/m2-m3/combined-editor-003/`.
- Save transport: SDK `SaveKernel` with `KernelExecutionType.QUICK_SAVE` (3),
  the exact [official `--no-run` mapping](https://github.com/Kaggle/kaggle-cli/blob/main/src/kaggle/api/kaggle_api_extended.py).
  The installed CLI 2.2.4 lacks this flag; its installed SDK supports the field.
  No ordinary push or session-create operation is permitted.

Two selected distinct L4 workers, existing Datasets, Internet disabled, USD 0,
and original time/token/step limits remain enforced. M2 retains score 0.2 and
adds persisted root/pruning diagnostics. M3 uses the reviewed paired-parent
JSON/permutation profile and unchanged EOS/sandbox gates. Actual GPU behavior
and teacher quality remain unverified for this package.

Offline preflight checks exact inventory, embedded payloads, model/tokenizer
references, wheel sources, approved and inert guards before setup, and 12
generated hardware fixtures. No model work occurs in these checks.

Kaggle accepted the sole `QUICK_SAVE` as version 1 at
2026-09-27T06:58:42.749827+00:00. The returned kernel ID is `136074222` and
the receipt URL is [combined 003](https://www.kaggle.com/code/danielwuu/nvarc-m2-m3-combined-003).
The exact wire request uses `kernelExecutionType: QUICK_SAVE`; the installed
SDK enum value is 3. One SDK `SaveKernel` POST was sent with retries disabled.
No session creation, notebook cell execution, status/log/output query,
retrieval or Dataset mutation occurred. Runtime is unobserved; the owner
controls manual Editor execution and reporting. No automatic retry follows.

Exact local SHA-256 bindings:

| Artifact | SHA-256 |
| --- | --- |
| `plan.json` | `d7aef8fc238e88d8666a3527e589f1248226375d5b9ba6ffc7cecc1fd20e7469` |
| `kernel/kaggle-notebook.ipynb` | `81877c7c88f2a549eefb1465281077ddeaa4b1521b1c88dcea14dfc37b8e5d73` |
| `kernel/kernel-metadata.json` | `5fc8504aab54a7fb13b41b448e1ab74798ccdb84f5614529d2fc2c2db758feb3` |
| Runtime wheel | `a9b6281723e2a79f2c5dcb44a849bc8eb160e4972081e1cb825fe51b74967fc5` |
| `stage-summary.json` | `6927c896d220f26353aa8a7aa32547b2eb42957056ec0d04ed1fcf4fd414c1d3` |
| `decision-0037-preflight.json` | `96b3533038e3496d1b9462adf2a47bf286b7acbd8fdb071764da74df328c9887` |
| `decision-0037-save-request.json` | `9261e29dce6f7a554574806f900f5b95c89aa11b1787d2acd56e85e5b70fa816` |
| `decision-0037-save-receipt.json` | `14880c27f3c798325e494893849e9a78eff1ab7a94a83e24cf2f405f34922aad` |
| `decision-0037-save-ledger.json` | `8dddecb4381e2e8c1ae47cd24056e509d890a47337d84c348be66555ed1cac88` |
| `decision-0037-save-log.txt` | `cd00dae3756940461dd5095f1bd9ba1aae20cad3f48fe50a630942a422df8498` |
| `decision-0037-save.py` | `c4aa37f944ff35835a45d8f4053e8c82d7430e7cd512021368b9d08a0f9892ee` |

The receipt, request, ledger and preflight are retained beside the package in
`.irisx/arc-agi-2/qwen35-nvarc/m2-m3/`. The complete file inventory is bound by
the stage summary. All 96 historical frozen files and all 16 files in the
reviewed inert candidate remained unchanged; local verification record digest
is `20a140710657d6423689c088d21e8e4e9e14ad242b8c747efd1e29bd028a8ea3`.

Validation: `python tools/repository_check.py --all` passed (256 tests, four
optional skips), 12 focused tests passed, both generated notebook authorization
paths were exercised before setup, and the installed wheel accepted the exact
owner-Editor plan while rejecting an agent-start mutation. Hardware fixture
preflight passed all 12 cases without real CUDA or model calls. The repository
log `.irisx/nvarc-editor-003-repository-check.txt` has SHA-256
`e450e63aabed685cb825ab1cd77c48d13d13e12253fee56ca6948a77585c8186`.
