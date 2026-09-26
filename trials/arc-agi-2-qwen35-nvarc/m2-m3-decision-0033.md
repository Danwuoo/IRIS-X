# Decision 0033 execution continuation

Status: owner reported stopping both sessions after pausing scheduled queries.
The last provider observation at 2026-09-26 04:46 UTC was QUEUED for both.
No terminal state, suspected provider bug or amount of model work is verified.
The owner-requested distinct restarts are governed by
[Decision 0034](../../docs/decisions/0034-restart-nvarc-without-monitoring.md).

The owner authorized execution and selected agent monitoring through terminal
state and continued development. [Decision 0033](../../docs/decisions/0033-authorize-nvarc-source-and-direct-teacher.md)
governs the reviewed USD 0 batch. Implementation commit is `834cdff` on main;
exact package hashes are in the [continuation plan](../../docs/plan/2026-09-26-nvarc-source-teacher-continuation.md).

| Work | Observed state | Next action |
| --- | --- | --- |
| Private retained-export Dataset | CREATE completed at 04:38:41 UTC; version 1 ready, private, all ten flat root files match expected names and byte sizes | Runtime verifies the pinned material hashes before model loading |
| M2 `nvarc-m2-source-cont-001` | Accepted version 1 at 04:42:02 UTC; owner later reported stopping it | Preserve identity and receipt; no further monitoring or retrieval |
| M3 `nvarc-m3-teacher-small-004` | Accepted version 1 at 03:36:19 UTC; owner later reported stopping it | Preserve identity and receipt; no further monitoring or retrieval |

Provider receipts and inventory evidence:

| Evidence | SHA-256 |
| --- | --- |
| Private Dataset CREATE receipt, `danielwuu/irisx-nvarc-m2-sft-export-002` | `a1370798da18108c510e702303d5153dfa3126822de07514592645f0597b7179` |
| Remote version-1 inventory, 10 files / 7,807,376,811 bytes | `b2e5c92b885a4cafd59efa12c5c93a0d59251d179e785500e1c2783d1d0a0a13` |
| Remote metadata, Dataset ID 12200379 and `isPrivate: true` | `826105315b1e9c15595ec45f82a661fa4532c15fcc0bb941ef1f3e876620641a` |
| [M2 version-1 push](https://www.kaggle.com/code/danielwuu/nvarc-m2-source-cont-001) | `07f70d9c19e6d8d1dc6f965178b8c2ab48fcc584e105ca34531894fb9086646c` |
| [M3 version-1 push](https://www.kaggle.com/code/danielwuu/nvarc-m3-teacher-small-004) | `7505a81d1a212cadc75dac43a3e44d9b50c37c447b17f92825587ee539c3e00a` |

Both submission allowances and the Dataset CREATE allowance are consumed.
Neither terminal output retrieval has been used. The remote inventory check
verifies names and sizes, not a second download or remote content hash.
No new TTT completion, accepted teacher stage, generated pair or ranking claim
follows from submission or queuing.

Local validation passed 219 unit tests with four existing optional skips.
The actual installed-wheel tiny deployment check passed both tests, and
focused artifact-tampering checks passed. Exact tokenizer verification and
prompt-budget probes are retained separately; they made no model calls.

The same-thread `nvarc-kaggle` heartbeat is PAUSED at the owner's request.
Decision 0034 supersedes this batch's monitoring and retrieval workflow.
Its durable working state is under `.irisx/arc-agi-2/qwen35-nvarc/m2-m3/`:

- `decision-0033-handoff.md`: concrete continuation commands and bounds;
- `decision-0033-active-ledger.json`: active mutation/retrieval reservations;
- `decision-0033-execution-ledger.json`: the completed original Dataset command's journal;
- `decision-0033-after-m3-push.json`: immutable recovery snapshot for the accepted M3 push;
- per-command UTF-8 receipts and status logs.

The active ledger imports only the original Dataset command's completion
event. An older upload-process snapshot must never overwrite newer M3 events.
No second CREATE, repeated push or repeated output command is authorized.
