# Decision 0033 execution continuation

Status at 2026-09-26 03:52 UTC: in progress, not a completion claim.

The owner authorized execution and selected agent monitoring through terminal
state and continued development. [Decision 0033](../../docs/decisions/0033-authorize-nvarc-source-and-direct-teacher.md)
governs the reviewed USD 0 batch. Implementation commit is `834cdff` on main;
exact package hashes are in the [continuation plan](../../docs/plan/2026-09-26-nvarc-source-teacher-continuation.md).

| Work | Observed state | Next action |
| --- | --- | --- |
| Private retained-export Dataset | One CREATE in flight since 03:35:56 UTC; no completion receipt yet | Preserve the running transfer, verify ready state and flat file inventory |
| M2 `nvarc-m2-source-cont-001` | Approved offline package passed; kernel not yet submitted | One push after Dataset readiness, then terminal check/retrieval and independent source-chain verification |
| M3 `nvarc-m3-teacher-small-004` | Kaggle accepted version 1 at 03:36:19 UTC; latest status QUEUED | Terminal check, one retrieval, verify all stage ledgers and sandbox complete programs |

M3 receipt URL:
https://www.kaggle.com/code/danielwuu/nvarc-m3-teacher-small-004
Its receipt SHA-256 is
`7505a81d1a212cadc75dac43a3e44d9b50c37c447b17f92825587ee539c3e00a`.
No new TTT completion, accepted teacher stage, generated pair or ranking claim
follows from submission or queuing.

Local validation passed 219 unit tests with four existing optional skips.
The actual installed-wheel tiny deployment check passed both tests, and
focused artifact-tampering checks passed. Exact tokenizer verification and
prompt-budget probes are retained separately; they made no model calls.

The same-thread `nvarc-kaggle` heartbeat is active every five minutes, with
instructions to finish this batch and its local verification, then stop.
Its durable working state is under `.irisx/arc-agi-2/qwen35-nvarc/m2-m3/`:

- `decision-0033-handoff.md`: concrete continuation commands and bounds;
- `decision-0033-active-ledger.json`: active mutation/retrieval reservations;
- `decision-0033-execution-ledger.json`: the original in-flight Dataset command's journal;
- `decision-0033-after-m3-push.json`: immutable recovery snapshot for the accepted M3 push;
- per-command UTF-8 receipts and status logs.

The active ledger imports only the original Dataset command's completion
event. An older upload-process snapshot must never overwrite newer M3 events.
No second CREATE, repeated push or repeated output command is authorized.
