# Native multitask 010 owner-Editor export-repair save

Status: **private QUICK_SAVE accepted as version 1; save consumed; runtime unobserved**.

[Decision 0058](../../docs/decisions/0058-save-native-multitask-export-repair.md)
records the owner's instruction 「提交」 following the local 008 diagnosis and
immutable 009 review. Exactly one private, Internet-disabled, USD 0 QUICK_SAVE
derives `nvarc-original-qwen3-native-multitask-010` from review 009. Stop after
the receipt. The owner retains manual Editor operation and `結果.zip` return.
No agent run, runtime status/log/output query, retrieval, monitoring, Dataset
mutation, scoring, teacher call, competition submission or automatic retry.

Reviewed plan digest is
`sha256:02ac331440fdb44642225bc5f9977fb18f7af8c1ccab32ffb532f4a6292bb75d`;
notebook SHA-256 is
`8641f929504f77182992d362669af532fbde4f134a5154237c8473d781fa9b32`.
All non-plan payloads, the fixed eight scientific producers, model/source
materials, training/inference parameters and resource limits remain identical
to 009. Only identity and exact owner admission bindings change. Preserve the
inert review and all consumed identities and receipts.

| Resource/session fact | Observation |
| --- | --- |
| Reserved L4 quota hours | **Unavailable / 無法取得**; null |
| Quota observation time/timezone | **Unavailable / 無法取得**; null |
| Observed L4 factor | **Unavailable / 無法取得**; null |
| Quota reservation ID | **Unavailable / 無法取得**; null |
| Current Editor/GPU sessions closed | **Unavailable / 無法取得**; null |
| Current session reconciliation | **Unavailable / 無法取得**; null |
| Local resource admission | False; owner authorizes this save without asserting these facts |
| Resource sufficiency / strict GPU gate | Unverified |

The planned requirement remains 2.5 quota hours with the historical 2× planning
assumption. The pre-008 affirmative session report does not assert closure
after the subsequent owner Editor run. V4 admission is exact to 009-to-010 and
does not modify historical v1/v2/v3 admission behavior or frozen packages.

The fresh CPU export helper enforces startup `PYTHONHASHSEED=0`, no visible GPU
and all existing strict source/row/ranking gates. It performs no model load or
new model call. The recorded local cross-Torch numerical replay limitation
remains open, as retained in the
[008 diagnosis](native-multitask-008-editor-diagnosis.md).

## Exact saved package and receipt

Kaggle accepted the sole request at **2026-10-04 15:57:42 UTC**
(**2026-10-04 23:57:42 Asia/Taipei**):
[native multitask 010 notebook](https://www.kaggle.com/code/danielwuu/nvarc-original-qwen3-native-multitask-010).
One guarded SaveKernel POST used `QUICK_SAVE`. The agent started no session
and made zero runtime status/log/output or retrieval calls. Acceptance is a
save receipt, with execution outcome unobserved pending the owner's report.

| Binding | SHA-256 |
| --- | --- |
| Saved plan | `d0e0e2084929a411e4cfa9464cbfe8a20fc73b91466aa7e4f8f4f1a905d0ab81` |
| Saved notebook | `0d1e82b8310b70e1633a0f4728fc4d4dce3fea7a636c08088def22b2e7f2cb6e` |
| V4 admission | `895a1bd2a85c38201ff7f9825d02fdf4b3c68e9f3a6a40b10a3179afff48074e` |
| Decision 0058 | `b36f337b1cc941adaf02e81471289ec0ef032922832e0003fdf1ed0196956320` |
| Actual SDK wire request | `c4aea62cde23aa9e0ddda11f914ae327dabec7a10c514e4eb0a37b766222198c` |
| Save receipt | `aa904d4f76d6d5c1743568c3e0f5157adc65174637845e791725ffd94be4f5fd` |
| Terminal save ledger | `ba9f30e638a087ba6d6da0c0516dbb5e72cc83042a43c8690b3a825e52c7031a` |
| Exclusive save reservation | `12136c40df93953b2cda27bd5646e5e26a90ad975cf19d7db852d388f2cd890c` |

The package is retained at
`.irisx/nvarc-original/runs/nvarc-original-qwen3-native-multitask-010/package-l4`,
and receipt/request/ledger at the same run's `editor-save-final`. All 007/008/009
package and journal hashes were checked unchanged before and after this save.
The fixed export helper digest remains
`a092cb4d426dbef1672e4c2c2ee263cbdae1e7b00c32d820b39061c84f8668a5`.

The six focused admission/export regression tests passed with no skips; exact
offline derivation and SDK wire checks passed. `python tools/repository_check.py --all` ran 3 helper and 511 unit tests with no skips. The original full command failed on one historical v2 synthetic fixture because the new constructor read a session field that the old mocked fixture omits; the other 510 unit tests passed. Restoring the historical v2/v3 literal and restricting null-field reads to v4 fixes that local regression. All 17 transport/v4 tests then passed, including the failed fixture. Exact post-repair 008 and saved 010 package reconstruction also passed with unchanged digests. The original failed full-command log is retained and is not relabeled a pass; unaffected tests were not repeated. Redacted machine-readable evidence is
[`native-multitask-010-editor-save-evidence.json`](configs/native-multitask-010-editor-save-evidence.json).
No further provider action follows from this consumed save.

Final repository invariants passed after the targeted repair and exact package reconstruction.
