# Local run007 publisher and one-shot handoff

The new owner instruction and Decision 0073 govern this distinct local recovery.
The original run005 snapshot and consumed run006 publication/source remain
preserved, including run006 epoch 1791901490 and deadline 1791944690.
This directory contains
locally adapted official-auth configuration/common/collector and a locally
reconstructed transport successor. config.py and operator_common.py retain
the exact reviewed run006 bytes; this adapter never relabels old receipts.

Use local WSL/POSIX with the real account HOME. The only permitted credential
stores are the owner's official Windows store
`/mnt/c/Users/wurre/.kaggle/credentials.json`, protected by the live Windows
ACL/reparse check, or the real POSIX home's official `.kaggle/credentials.json`.
No cloud credential path or task-local credential kind is accepted. The official
SDK loads/saves this exact local store; token values never enter events or Git.
Existing OAuth refresh is durably journaled. New authorization, if needed, must
use the official flow and the owner, never an old chat login code.

The reviewed config binds absolute repository/candidate/scratch/state/evidence
paths, the complete publication manifest and actual remote predecessor. Version
allocation follows the fresh observation; no operator argument can skip source,
privacy, material, history or owned-process gates. The seven non-code Dataset
versions, locked model, Docker, NvidiaRtxPro6000, offline settings and ARC3
metadata association remain fixed.

The finite publisher sequence is:

1. Validate the final contract locally, commit/push the reviewed source and
   obtain a current predecessor bracket. Every write requires the independently
   reviewed remote Git commit and exact local operator blobs at that revision.
2. Reserve/upload one private code successor. If a write is uncertain, reconcile
   numeric provider state and exact bytes before any resend.
3. Wait only for Dataset processing, then verify its numeric full archive and
   closed file set. Run `local_accept_numeric_mount_run007.py` with that actual receipt
   and independently pinned final manifest/inventory. It uses the unchanged
   owned guard and source-only helper; it cannot attest installation or GPU work.
4. Save the inactive notebook via QUICK_SAVE with GPU/TPU/Internet off, then
   verify saved source, all settings and private identities. Bare provider Dataset
   names do not alone attest mounted versions; numeric bytes and runtime hashes
   remain separate safeguards.
5. Independently audit the persisted real code/inactive/mount receipts and bind
   the audit to this exact final candidate. The review is not synthetic success.
6. Call `activate` once. The transport samples a real pre-dispatch epoch only
   after readiness, produces four hash-bound JIT documents and durably journals
   intent before official SaveKernel RUN. Queue/setup time consumes the same
   43,200-second deadline. The accepted save immediately performs the one
   source/settings/status bracket and records its real state, including QUEUED.
7. Deliver that receipt and stop. Do not call `verify-run` after the successful
   internal readback. It exists for an uncertain send before confirmation only.
   The durable `active-readback` claim prevents a second successful readback.

Current execution review actions exclude polling, collection and watching.
`execution_gate(..., monitor=True)` rejects collector actions before Provider
creation. No watcher or automatic next RUN is created. The collector retains
optional diagnostic paths and original validators for a later explicit owner
continuation; it does not authorize one now.

Run focused no-provider tests from the root:

```sh
python3 -B -m unittest discover -s tools/arc_qwen_rlvr004_20261013/publication_run007/tests -v
python3 -O -B -m unittest discover -s tools/arc_qwen_rlvr004_20261013/publication_run007/tests -v
```

Use the existing offline flags, `PYTHONHASHSEED=0` and an ignored POSIX
workspace-backed TMPDIR. Keep raw archives/state/logs outside Git. Passing CPU
checks and accepting a RUN do not prove model inference, valid predictions,
full PUBLIC120 scoring or scientific improvement.
