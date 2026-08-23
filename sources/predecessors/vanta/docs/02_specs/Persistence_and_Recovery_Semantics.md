# Persistence and Recovery Semantics

## Authority And Scope

- Gate: `PS1-G9 — Storage and Persistence Gate`
- Spec version: `fixture-local-sqlite-persistence-v0`
- Storage schema version: `persistence-v0`
- Hash policy: `canonical-json-sha256-v1`

This specification defines the implementable persistence behavior for a
single-machine, fixture-local Document Ops runtime. It is downstream of
[Storage and Persistence Gate](../00_manifest/Storage_and_Persistence_Gate.md)
and upstream of schemas, experiments, evaluation, engineering, and code.

## 1. Persistence Adapter Contract

`Vanta.Persistence` is the runtime-facing contract. Concrete runtime modules
must not depend directly on SQLite. An adapter must support:

- initialize or open storage and verify storage/schema/hash-policy versions;
- create an episode idempotently;
- append an immutable typed artifact;
- save a Canonical State snapshot;
- record a prepared reversible effect;
- record a Verifier Output;
- atomically commit a logical step/episode;
- abort or reject an episode;
- record rollback and recovery status;
- load one episode, one artifact, or ordered episode artifacts;
- list recoverable episodes;
- verify artifact content integrity; and
- close storage.

The v0 adapters are `MemoryAdapter` and `SQLiteAdapter`. Adapter parity is
defined over artifact types, content hashes, lifecycle, accepted pointers,
idempotency outcomes, recoverable discovery, and integrity results, not over
backend-internal table layout.

## 2. Artifact Identity And Content Hash

Every persisted artifact has:

- stable `artifact_id`;
- `artifact_type`;
- artifact `schema_version`;
- `episode_id`;
- `content_hash` calculated from the payload under the named hash policy;
- monotonic `created_sequence` for deterministic ordering;
- provenance or reference metadata; and
- an inline payload or an explicit payload reference.

Artifacts are append-only. Updating a payload in place is corruption. Mutable
episode pointers and recovery-status rows may change only through adapter
operations that also preserve an immutable artifact trail where required.

## 3. Canonical State Snapshot Semantics

A persisted Canonical State snapshot validates against
`canonical_state.schema.json`. Its `state_hash` is SHA-256 over deterministic
canonical JSON of the semantic state after removing `state_hash` itself.
Runtime time, temporary paths, raw logs, connection metadata, and journal data
must not enter that hash input.

`accepted_state_artifact_id` is the sole persisted pointer to the current
accepted snapshot. A candidate or rejected state may be stored for audit but
must not become that pointer.

## 4. Append-Only Runtime Artifacts

Canonical State, Execution Step, Evidence Packet, Verifier Output, Episode
Journal, runtime manifest, and recovery metadata remain distinct types. A
database row set is not a raw tool-log archive. Artifacts order by
`created_sequence`, never by timestamp.

## 5. Episode Lifecycle

| Lifecycle | Meaning |
| --- | --- |
| `created` | Episode identity and runtime manifest exist; no action is running. |
| `running` | Execution has started and no unresolved prepared effect is known. |
| `prepared` | A reversible effect has durable target, pre-hash, and backup metadata. |
| `committed` | An accepted state pointer and journal pointer were atomically committed. |
| `aborted` | No accepted commit occurred and the action path stopped safely. |
| `rejected` | Policy, execution, evidence, verifier, idempotency, or integrity checks rejected the path. |
| `rollback_pending` | A durable rollback intent exists and completion is not yet proven. |
| `rolled_back` | The fixture target was restored and verified against the durable pre-hash. |
| `recovery_required` | Deterministic recovery cannot prove safe completion, abort, or rollback. |

This persistence lifecycle does not replace the Episode Journal commit and
rollback enums.

## 6. Transaction Boundary

One SQLite `BEGIN IMMEDIATE` transaction must contain:

- committed Execution Step, Evidence Packet, and Verifier Output artifacts;
- the accepted Canonical State snapshot;
- the committed Episode Journal artifact;
- `accepted_state_artifact_id` and `journal_artifact_id` pointer updates;
- lifecycle `committed`; and
- the unique logical-commit record and result.

Any failure rolls back the whole database transaction. A state pointer without
its journal pointer, or vice versa, is a hard atomicity violation.

## 7. Idempotency Semantics

Every logical commit has a unique string key and a deterministic request hash
covering episode, task, step/action payload, side-effect class, pre-state hash,
runtime/schema/hash-policy versions, and applicable structured-edit target
identity. Candidate state, Evidence Packet, and Verifier Output are produced
after an effect and remain independently content-hashed artifacts; they are
not required to recognize a safe pre-effect retry.

- Same key and same request hash returns the durable prior result and does not
  execute the fixture effect again.
- Same key and different request hash returns `idempotency_conflict` and does
  not write or execute anything.
- An incomplete key may be safely resumed only from durable recovery evidence;
  it may not be treated as committed.

## 8. Restart Recovery

On open/restart, adapters expose episodes in `running`, `prepared`,
`rollback_pending`, or `recovery_required`. Recovery verifies storage and hash
policy versions, artifact integrity, target identity, target hash, backup
integrity, logical-commit status, and accepted journal/state pointers.

Outcomes are limited to safe completion from a durable committed result,
`aborted`, `rolled_back`, or `recovery_required`.

## 9. Crash-Window Handling

Fixture-local filesystem effects follow a durable prepare protocol:

1. create a backup and durable metadata;
2. persist `prepared` with target identity and pre-effect hash;
3. execute the effect;
4. mark durable effect-applied evidence;
5. build Evidence Packet and Verifier Output;
6. commit database artifacts and pointers transactionally; and
7. return the client response.

Deterministic failure-injection points may stop after any numbered boundary.
They simulate process-loss windows; they are not reported as OS-level kill
tests. After restart:

- prepared/no effect and unchanged target becomes `aborted`;
- effect applied/no database commit is restored from backup and becomes
  `rolled_back` when the pre-hash verifies;
- database commit/no response returns the existing idempotent result;
- missing or corrupt recovery evidence becomes `recovery_required`.

## 10. Corruption Detection

Integrity verification recomputes every artifact payload hash and validates its
envelope plus its typed payload schema when a core schema exists. Missing
accepted pointers, missing journal references, changed payload bytes,
incompatible schema versions, and invalid recovery hashes are explicit errors.
No corrupt artifact may be used to report replay success.

## 11. Schema And Hash Policy Versioning

The database stores `persistence-v0`, current runtime schema version, and
`canonical-json-sha256-v1`. Opening a database with unsupported storage or hash
policy returns an incompatibility error before writes. Persisted artifacts
retain their own schema version.

## 12. Migration Policy

Persistence v0 performs only idempotent creation of its v0 tables and metadata.
There is no automatic destructive or lossy migration. A future storage schema
or hash policy requires:

1. a new accepted decision and schema impact review;
2. a versioned migration with backup and rollback instructions;
3. compatibility and failure-injection tests; and
4. a measured successor closure.

The existing `docs/03_schemas/*.schema.json` location remains schema authority;
this work does not package runtime schema assets.

## 13. Retention Boundary

The v0 database contains fixture-local runtime artifacts only. Measured compact
result JSON/Markdown is retained under the experiment result directory.
Scratch databases and copied workspaces are not durable program evidence and
need not be tracked. Historical failed result directories must remain intact.

## 14. Audit And Replay Requirements

Audit completeness requires resolvable accepted state/journal pointers, every
committed step's Evidence Packet and Verifier Output refs, a complete state hash
sequence, runtime/schema/hash policy versions, and recovery/idempotency records
where applicable.

Replay success requires exact comparison of episode/task identity,
runtime/schema version, ordered steps, action type, side-effect class, step and
commit status, rollback/recovery status, full state-hash sequence, evidence and
verifier refs, observation signatures, structured path/selector resolution,
before/after hashes, diff or contract result, and final accepted state hash.
Any missing required value fails replay.

## 15. Failure Behavior

- Schema-invalid inputs are rejected before persistence.
- Verifier decisions other than `accept` cannot update accepted state.
- Unsupported side effects cannot commit.
- Busy/locked databases return explicit errors after the configured timeout.
- Write errors and injected transaction failures roll back all transaction
  changes.
- Idempotency conflicts reject without overwrite.
- Incomplete episodes are discoverable after restart.
- Silent partial commit is forbidden.

### PS1-G10 Reuse Of Persistence v0

G10 reuses the existing generic artifact, recovery, idempotency, and logical-
commit tables; it does not migrate or broaden the Persistence v0 database
authority. Approval Records are typed persisted artifacts. A successful G10
logical commit must validate exactly one approved approval ref, exactly two
Evidence Packet refs, exactly two Verifier Output refs, the committed artifact
ref, and matching Episode Journal refs. Recovery distinguishes no-effect abort,
strict restore success, `recovery_required`, and already committed same-request
response recovery.

## 16. Non-goals

- PostgreSQL, distributed transactions, HA, replication, or sharding.
- Production deployment or production data.
- Durable memory, memory candidates, or `MEMORY_WRITE`.
- Full Context OS or raw tool-log archival.
- Executable external `COMMITTABLE` or `IRREVERSIBLE` actions.
- H1-H5, full-architecture, production-readiness, distributed-persistence, or
  broad agent-safety validation claims.
