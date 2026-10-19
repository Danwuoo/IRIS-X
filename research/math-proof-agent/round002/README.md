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

Follow-up audit fixed nested statement metadata leakage and requires complete
scoring identity plus exact frozen panel membership, measured adapter identity,
verifier configuration and executing source bytes. The committed execution
manifest is trusted launcher input, never solver input. Its code SHA must match
the scoring identity. Scoring uses explicit canonical semantic hashes; the
existing smoke manifest contains raw-file hashes and cannot authorize scoring.
`execute_arm` additionally requires `panel`, `source_files` and
`execution_manifest` keyword arguments. No scoring manifest/runner is qualified.

An admitted `closed_exists_nat_v1` task can now bind a canonical natural-number
answer to the unchanged original existential theorem. The trusted Lean wrapper
chooses that exact witness and checks the model's restricted proof of its
remaining property, then audits the final theorem's transitive axioms. The
controller/evaluator/analyzer recheck statement, specification, answer and proof
hashes. Optional private answer keys only check consistency after selection;
disagreement blocks the joint conclusion. Unsupported tasks still stop before
generation. Authored controls qualify this narrow engineering path, not any real
source or scoring panel. Original-statement fidelity and provenance remain gates.

Context 8192 cannot accommodate a previous 4096-token candidate plus
instructions/feedback and another 4096 tokens. Exact pinned-tokenizer controls
in `context_controls.py` confirm this; 2048 is only a candidate common ceiling,
with very little slack in one authored case, not an adopted or universal policy.
A feasible common completion/context policy must be measured and preregistered
before freezing; `context_budget_exceeded` is retained without futile retries.
Timeouts outrank truncated-JSON parse failures. Missing/partial cost receipts
remain visible; reported model-cost sums are observed lower bounds. A pair with
either arm lacking generation is reported separately, never as a tie/gain/loss.

[Source feasibility notes](source-feasibility-notes.json) correct an earlier
overly strict source assessment: attributable upstream human review can satisfy
statement fidelity without requiring the owner to repeat that review. The
source/runtime/acquisition and joint-binding requirements still apply. No
benchmark is admitted by metadata review alone.
The [third source audit](source-feasibility-audit-03.json) records the unresolved
proof-field acquisition assurance, answer-slot semantics and runtime pin. It
also discloses an incidental methodology-paper example exposure to the audit
agent; no answer value is reproduced or sent to a solver, and no panel was changed.

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
