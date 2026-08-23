# Experiment 006 — Persistence and Recovery

## Identity

- Experiment ID: `experiment_006_persistence_and_recovery`
- Gate: `PS1-G9 — Storage and Persistence Gate`
- Named scope: `Fixture-Local SQLite Persistence v0`
- Runner: `mix vanta.persistence_experiment`
- Measured status: complete candidate run `20260715_114209` is
  `pass_acceptance_candidate`; predecessor `20260715_114052` remains
  `failed_no_acceptance` provenance. The
  [manifest closure](../00_manifest/Post_Stage_1_Persistence_v0_Closure.md)
  accepts the named passing scope as `accepted_by_closure`.

## Purpose

Measure whether the named SQLite adapter preserves artifact integrity,
state/journal atomicity, idempotency, restart recovery, audit completeness, and
minimum replay fidelity under deterministic failure injection.

This experiment does not simulate an operating-system kill. Injection points
stop the runtime at deterministic protocol boundaries and then close/reopen the
database to exercise the equivalent durable-state window.

## Result Contract

Each run writes:

`docs/04_experiments/results/persistence_and_recovery/<timestamp>/`

with at least:

- `run.json`;
- `summary.md`;
- `fixture_inventory.md`;
- `failure_injection_results.json`;
- `failure_injection_matrix.md`;
- `environment_manifest.json`; and
- `schema_hash_policy_versions.json`.

The runner may report only `pass_acceptance_candidate` or
`failed_no_acceptance`. Only a later manifest closure may report
`accepted_by_closure`.

## Fixture And Failure-Injection Matrix

| # | Case | Required outcome |
| ---: | --- | --- |
| 1 | Normal commit then restart | Accepted pointers, artifacts, and journal reload intact. |
| 2 | Crash before Evidence Packet persistence | No commit; episode is recoverable. |
| 3 | Prepared complete, before file effect | Restart aborts safely with unchanged target. |
| 4 | File effect complete, before DB commit | Restart restores backup and records `rolled_back`. |
| 5 | DB commit complete, before client response | Retry returns the prior logical result without another effect. |
| 6 | Crash before rollback starts | Restart completes rollback from durable intent. |
| 7 | Crash during rollback | Restart completes and verifies rollback. |
| 8 | Same idempotency key and request | Existing result returned; no duplicate logical commit. |
| 9 | Same key, different payload/hash | Conflict; no overwrite or effect. |
| 10 | Artifact content corruption | Integrity check detects the changed payload. |
| 11 | Missing artifact reference | Audit check reports incomplete. |
| 12 | Incompatible schema version | Open/integrity check rejects incompatibility. |
| 13 | Database busy/locked | Explicit busy/locked error; no partial commit. |
| 14 | Write failure/transaction rollback | State and journal pointers both remain unchanged. |
| 15 | Incomplete episode discovery | Restart lists the incomplete episode. |
| 16 | Clean workspace replay | All required fidelity comparisons pass. |
| 17 | Structured reversible edit restart/replay | Path, selector, hashes, diff, state, refs, and status match. |
| 18 | Rejected action | Rejected state never becomes accepted pointer. |
| 19 | Verifier decision other than `accept` | Logical commit is rejected. |
| 20 | Unsupported side effect and memory write | Executed/committed counts remain zero. |

## Hard Metrics

The run must use the exact hard gates in
[Storage and Persistence Gate](../00_manifest/Storage_and_Persistence_Gate.md).
All rate metrics require `1.0`; all violation/count metrics require `0`.

`persistence_write_success_rate` is successful durable writes divided by
writes expected to succeed. Expected injected busy, conflict, incompatibility,
and rollback failures are evaluated by their negative-case assertions and are
not relabeled as successful writes.

## Acceptance Rule

If any hard metric or required case fails, the run is
`failed_no_acceptance`. The result directory remains historical provenance,
the in-scope defect must be repaired, and the complete 20-case run must be
executed again. A partial or focused rerun cannot create closure.

## Claim Boundary

Even a passing closure is limited to the named fixture-local SQLite surface.
It does not validate H1-H5, the full architecture, production readiness,
distributed persistence, durable memory, full Context OS, external
`COMMITTABLE`, `IRREVERSIBLE`, `MEMORY_WRITE`, or broad agent safety.
