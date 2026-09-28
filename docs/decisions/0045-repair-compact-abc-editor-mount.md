# Decision 0045: Repair and save one distinct compact ABC Editor notebook

Status: Accepted
Date: 2026-09-28

The owner returned `結果.zip` from the manually run compact ABC 001 Editor
session and requested a repair and another QUICK_SAVE. The exact 001 result
SHA-256 is `72476b79f7a59f4fb81f6ca1a067177448b9720885ee55ee39c951440d526a12`.
Its digest-bound traceback shows a worker failure at the base model material
inventory gate, before any A/B/C model work. The gate required the local
`dataset-metadata.json` publishing sidecar even when absent from the mounted
Dataset. The result does not itself list the mounted model directory, so that
absence is a diagnosis, not a direct file inventory observation. Four distinct
BF16 L4 UUIDs were directly observed in the result.

The distinct replacement is `nvarc-compact-abc-editor-002`. Its exact plan is
`trials/arc-agi-2-qwen35-nvarc/configs/compact-abc-editor-002.json`, canonical
digest `sha256:20de08cb39cc4bfe7de02b15d1a350e1dbf4c040c94a5aaf26f4914a93fc5c4e`.
The repair makes the publishing sidecar optional while preserving the exact
manifest-file inventory and per-file digest checks. The official competition
source must be attached at
`/kaggle/input/competitions/arc-prize-2026-arc-agi-2`; the notebook checks
only its presence and reads no evaluator answers. The owner must select L4 x4;
the notebook verifies four distinct BF16 L4 UUIDs. The A/B/C workloads,
selected public parents, models, candidate and TTT ceilings, one active worker,
offline dependencies, USD 0 paid cost and 1,800-second session stay as in
Decision 0044 and the new plan.

One private, Internet-disabled `KernelExecutionType.QUICK_SAVE` is authorized
after exact offline preflight. The owner starts it in Kaggle Editor and returns
`結果.zip`. Reserve the sole send before the provider call; rejection or an
uncertain response consumes it. No agent execution, status/log/output query,
retrieval, Dataset mutation, monitoring, automatic retry, hidden-answer scoring
or promotion is authorized. The 001 package and receipt remain frozen. Status
is `trials/arc-agi-2-qwen35-nvarc/compact-abc-editor-002.md`.

The sole QUICK_SAVE was accepted as version 1 with provider kernel ID
`136279071`. Its request and receipt are retained on the status page. The
allowance is consumed. The agent did not start or query the saved notebook.
