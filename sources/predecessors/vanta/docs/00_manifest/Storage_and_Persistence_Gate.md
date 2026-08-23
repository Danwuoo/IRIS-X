# Storage and Persistence Gate

## Authority

- Gate ID: `PS1-G9`
- Formal name: `Storage and Persistence Gate`
- Accepted gate/spec date: 2026-07-15
- Named implementation scope: `Fixture-Local SQLite Persistence v0`

This manifest gate authorizes the first fixture-local persistence surface for
the Vanta runtime. Gate/spec acceptance authorizes implementation and measured
evaluation only. It is not implementation completion, a measured result, or
`accepted_by_closure` by itself.

## Current Status

| State | Result |
| --- | --- |
| gate/spec accepted | 2026-07-15 |
| implementation completed | completed for the named v0 adapter/runtime surface |
| measured run completed | `20260715_114209`, 20/20 cases, every hard metric passed |
| `accepted_by_closure` | accepted by [Post-Stage-1 Persistence v0 Closure](Post_Stage_1_Persistence_v0_Closure.md) |
| validated within named scope | `validated for Fixture-Local SQLite Persistence v0` only |

The predecessor `20260715_114052` remains `failed_no_acceptance` provenance.

## Purpose

Authorize a single-machine, restartable, auditable, and replayable persistence
surface for the existing Document Ops runtime spine:

```text
state -> plan -> action -> evidence -> verify -> commit / abort
```

The accepted backend is SQLite behind a persistence adapter contract. The
first adapters are an in-memory adapter for fast tests and compatibility and a
SQLite adapter for persistence, restart, recovery, and measured failure
injection.

## Authorized Persistent Surface

`PS1-G9` may persist these distinct artifact classes without collapsing them
into an undifferentiated log:

- Episode metadata.
- Canonical State snapshots.
- Execution Steps.
- Evidence Packets.
- Verifier Outputs.
- Episode Journal.
- Runtime manifest.
- runtime, schema, storage-schema, and hash-policy versions.
- rollback and recovery metadata.
- logical-commit idempotency metadata.

The Episode Journal records references and state-hash sequences; it is not
Canonical State and is not durable memory. Raw tool logs are not part of this
surface.

## Locked Decisions

### `OQ-IMPL-001`: storage backend

Use SQLite for the named single-machine fixture-local persistence authority,
accessed through `Vanta.Persistence`. `Vanta.Persistence.MemoryAdapter` remains
available for fast tests and compatibility. `Vanta.Persistence.SQLiteAdapter`
uses the minimal `exqlite` driver directly so transaction, busy, rollback, and
corruption behavior remain explicit; no Ecto repository, PostgreSQL, HA, or
distributed transaction is introduced.

### `OQ-IMPL-003`: minimum replay fidelity

Replay success requires equality or verifiable correspondence for every item
below. Missing required source artifacts, missing references, incompatible
versions, or unverifiable values are replay failures:

- episode and task identity;
- runtime and schema version;
- step count and order;
- action type and side-effect class;
- step, commit, rollback, and recovery status;
- the full Canonical State hash sequence;
- Evidence Packet and Verifier Output references;
- observation signatures;
- structured-edit path and selector resolution;
- before and after hashes;
- diff or contract result; and
- final accepted Canonical State hash.

### `OQ-SCHEMA-004`: Canonical State hash granularity

Canonical State uses deterministic canonical JSON plus the existing project
SHA-256 algorithm under hash policy `canonical-json-sha256-v1`. The hash covers
only semantic Canonical State content, excludes the `state_hash` field itself,
orders object keys deterministically, and excludes runtime timestamps,
temporary paths, raw tool logs, and other non-canonical metadata. A different
policy requires a new version. The Episode Journal stores the resulting hash
sequence but is not included in Canonical State.

## Episode Lifecycle Authority

Persistence lifecycle is defined by
[Persistence and Recovery Semantics](../02_specs/Persistence_and_Recovery_Semantics.md)
and `persistence_manifest.schema.json`:

`created`, `running`, `prepared`, `committed`, `aborted`, `rejected`,
`rollback_pending`, `rolled_back`, and `recovery_required`.

This is a persistence lifecycle. It does not silently expand the existing
`episode_journal.schema.json` commit-status or rollback-status enums. The
separation and impact are recorded in
[Post-Stage-1 Persistence Schema Impact Review](../03_schemas/Post_Stage_1_Persistence_Schema_Impact_Review.md).

## Transaction And Recovery Gate

For every accepted logical commit, the new Canonical State snapshot, accepted
state pointer, Episode Journal artifact/reference, and committed logical-key
record must be written in one SQLite transaction.

SQLite and the fixture filesystem are not one transaction. A fixture-local
`REVERSIBLE` effect must therefore use this protocol:

1. persist `prepared`;
2. persist target identity, pre-effect hash, and backup metadata;
3. execute the fixture-local effect;
4. build post-effect evidence;
5. run the verifier;
6. transactionally persist runtime artifacts, the new state snapshot, accepted
   state pointer, journal reference, and committed status; and
7. after a crash window, discover the episode as recoverable and use durable
   evidence to complete, abort, roll back, or mark `recovery_required`.

No crash window may default to committed. Every logical commit has one unique
idempotency key. Same key plus same request returns the durable result or safely
continues; same key plus a different request hash is a conflict and cannot
overwrite the prior result.

## Migration Phases

| Phase | Authority | Required evidence |
| --- | --- | --- |
| A — Shadow mode | Existing in-memory runtime remains authority while SQLite receives the same artifacts. | Memory/SQLite artifact parity; no persistence-authority claim. |
| B — Restart/replay candidate | SQLite reloads episodes and drives deterministic recovery/replay checks. | Restart, crash-window, idempotency, corruption, version, busy, and rollback tests. |
| C — Persistence authority | The named SQLite mode may become accepted authority only through measured closure. | All hard metrics and required test commands pass; evaluation report and manifest closure exist. |

## Acceptance Criteria

`PS1-G9` may become `accepted_by_closure` only when one complete measured run
meets all of these hard gates:

| Metric | Required |
| --- | ---: |
| `persistence_artifact_schema_validity` | `1.0` |
| `persistence_write_success_rate` | `1.0` |
| `restart_recovery_success` | `1.0` |
| `replay_consistency` | `1.0` |
| `audit_completeness` | `1.0` |
| `state_journal_atomicity_violations` | `0` |
| `duplicate_logical_commits` | `0` |
| `silent_partial_commits` | `0` |
| `committed_effects_without_journal_refs` | `0` |
| `artifact_integrity_detection_rate` | `1.0` |
| `unsupported_commits` | `0` |
| `memory_writes` | `0` |
| `irreversible_effects` | `0` |

A failed hard gate requires `failed_no_acceptance`; the failed run remains
provenance. Thresholds may not be lowered to create closure.

## Status Model

These states must remain distinct:

| State | Meaning |
| --- | --- |
| gate/spec accepted | This document and the normative persistence spec authorize scoped implementation and measurement. |
| implementation completed | Adapter, SQLite, runtime, recovery, runner, and tests exist. This alone is not validation. |
| measured run completed | A complete run produced immutable result artifacts. This alone is not closure. |
| `accepted_by_closure` | A manifest closure reviewed a complete hard-gate pass. |
| validated within named scope | Only the named `Fixture-Local SQLite Persistence v0` surface is supported by the accepted measured evidence. |

## Explicit Exclusions And Claim Boundary

This gate does not authorize or validate:

- durable memory or memory candidates;
- `MEMORY_WRITE`;
- full Context OS;
- raw tool log archives;
- external account or production data;
- executable external `COMMITTABLE`;
- `IRREVERSIBLE`;
- distributed transactions, HA, or distributed persistence;
- production readiness;
- H1-H5;
- the full architecture; or
- broad agent safety claims.

## Required Artifacts

- [Persistence and Recovery Semantics](../02_specs/Persistence_and_Recovery_Semantics.md)
- [Post-Stage-1 Persistence Schema Impact Review](../03_schemas/Post_Stage_1_Persistence_Schema_Impact_Review.md)
- `persistence_manifest.schema.json`
- `persisted_artifact.schema.json`
- `recovery_record.schema.json`
- [Experiment 006 Persistence and Recovery](../04_experiments/Experiment_006_Persistence_and_Recovery.md)
- measured result directory under
  `docs/04_experiments/results/persistence_and_recovery/<timestamp>/`
- [Experiment 006 Persistence and Recovery Run Report](../05_evaluation/Experiment_006_Persistence_and_Recovery_Run_Report.md)
- [Post-Stage-1 Persistence v0 Closure](Post_Stage_1_Persistence_v0_Closure.md)
