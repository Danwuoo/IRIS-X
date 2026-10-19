# MATH-002 implementation and evidence

This is a bounded inference-only research implementation. The canonical scope
and acceptance gates are in the [single plan](../../../docs/plan/2026-10-19-math-proof-agent-round02.md).
`protocol.json` and `panel-proposal.json` deliberately remain unfrozen until
actual model/Lean qualification, source legality and human statement review.
No empty panel, authored control or mocked model may become an efficacy score.

The implementation has one Qwen3 JAX adapter (`model_adapter.py`), one restricted
Lean worker (`lean_worker.py`), a bounded `controller.py`, and evaluator-only
exact answer comparison plus `analyze.py`. Each generated candidate and tool
event is atomically saved. Incomplete planned items remain in denominators.
Model weights are never updated. Formal statements are separately fingerprinted
and immutable. The conservative tactic grammar is a known capability constraint.

`controls.py` uses scripted outputs solely for controller/budget negatives;
`test_model_adapter.py` uses tiny random weights solely for numerical conversion
checks. Neither is target-model research. The [Lean guide](lean/README.md)
documents actual local runtime setup, failed first attempt, and successful
controls. Local WSL isolation does not establish Kaggle isolation.

`package_run.py` reads committed Git blobs, embeds exact bytes in one notebook,
and binds source/model/protocol/panel hashes. Kaggle does not upload adjacent
modules automatically. `remote_bootstrap.py` prepares public dependencies and
weights in task-owned `/tmp`; `/kaggle/working/m002/results` contains only
reports/logs. The parent finalizer emits hashes even on a caught child failure.
An interrupted parent or platform failure can still lose outputs; never claim
such a snapshot was saved without retrieval.

`kaggle_run.py` is the single task-owned entrypoint. Default operation is a
read-only observation, with local state under `.irisx/line-b/MATH-002/`:

```powershell
.irisx/line-b/MATH-002/venv/Scripts/python.exe research/math-proof-agent/round002/kaggle_run.py observe
.irisx/line-b/MATH-002/venv/Scripts/python.exe research/math-proof-agent/round002/kaggle_run.py observe --watch-seconds 600
.irisx/line-b/MATH-002/venv/Scripts/python.exe research/math-proof-agent/round002/kaggle_run.py reconcile
.irisx/line-b/MATH-002/venv/Scripts/python.exe research/math-proof-agent/round002/kaggle_run.py retrieve
```

`reconcile` only reads back a previously uncertain submission. `submit` is an
explicit operation for the current research task after checks; monitors never
invoke it. All reserved submissions count even when failed or unknown. A failed
run needs a recorded diagnosis before another submit. Locks are not automatically
deleted if stale: first verify the recorded process is no longer alive.

Installed CLI 2.2.4 status/logs/output use latest even when given `/version`.
The read-only `sdk_readback.py` obtains the actual current version and source
fingerprint around these operations; exact-version source must match too.
Receipts and non-public generated proofs stay ignored. A successful remote
process is not mathematical success; only the fixed verifier's final theorem
and axiom policy can qualify a proof.

There is no automatic resume of interrupted candidate generation. Preserve the
unknown event, reconcile complete snapshots and all identities, and charge any
future run against the original task budget before explicit continuation.
