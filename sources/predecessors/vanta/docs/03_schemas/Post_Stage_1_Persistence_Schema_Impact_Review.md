# Post-Stage-1 Persistence Schema Impact Review

## Review Identity

- Gate: `PS1-G9 — Storage and Persistence Gate`
- Review date: 2026-07-15
- Storage schema version: `persistence-v0`
- Hash policy: `canonical-json-sha256-v1`
- Decision: add three persistence-specific schemas; do not expand existing core
  runtime enums or create duplicate core schema authority.

## Upstream Authority

- [Storage and Persistence Gate](../00_manifest/Storage_and_Persistence_Gate.md)
- [Persistence and Recovery Semantics](../02_specs/Persistence_and_Recovery_Semantics.md)
- [Commit Abort Replay Semantics](../02_specs/Commit_Abort_Replay_Semantics.md)
- existing `docs/03_schemas/*.schema.json` contracts

## Impact Decision

The existing core schemas remain authoritative for their payloads. Persistence
needs envelope, lifecycle/pointer, and recovery contracts that do not belong in
Canonical State, Evidence Packet, Verifier Output, or Episode Journal.

| Schema | Change | Authority |
| --- | --- | --- |
| `persistence_manifest.schema.json` | New | Episode lifecycle, accepted pointers, and version metadata. |
| `persisted_artifact.schema.json` | New | Immutable artifact envelope shared by both adapters. |
| `recovery_record.schema.json` | New | Prepared-effect and crash-window recovery metadata. |
| `canonical_state.schema.json` | No shape change | Payload remains core authority; hashing semantics are locked in the persistence spec and versioned hash policy. |
| `episode_journal.schema.json` | No enum change | Existing commit/rollback semantics remain; persistence lifecycle is separate. |
| `execution_step.schema.json` | No change | No new action or side-effect class is introduced. |
| `evidence_packet.schema.json` | No change | Persisted payload continues to validate against the existing schema. |
| `verifier_output.schema.json` | No change | Persisted payload continues to validate against the existing schema. |

## Lifecycle Impact Review

The required lifecycle values `created`, `running`, `prepared`, `committed`,
`aborted`, `rejected`, `rollback_pending`, `rolled_back`, and
`recovery_required` are storage/recovery states. Directly adding them to the
Episode Journal's `commit_status` would conflate persistence recovery with the
runtime commit decision. Therefore `persistence_manifest.schema.json` owns the
new lifecycle enum, while the Episode Journal retains its current enum.

## Hash Impact Review

`OQ-SCHEMA-004` is resolved without a Canonical State shape change. The existing
`state_hash` field stores a `sha256:` digest. Policy
`canonical-json-sha256-v1` specifies deterministic key ordering and exclusion
of `state_hash` itself plus non-canonical runtime metadata. A future policy must
be versioned in the persistence manifest; silent rehashing is forbidden.

## Artifact Type Authority

The artifact envelope enumerates distinct runtime types. It does not replace
their payload schemas. Typed validation routing is:

| Artifact type | Payload authority |
| --- | --- |
| `canonical_state` | `canonical_state.schema.json` |
| `execution_step` | `execution_step.schema.json` |
| `evidence_packet` | `evidence_packet.schema.json` |
| `verifier_output` | `verifier_output.schema.json` |
| `episode_journal` | `episode_journal.schema.json` |
| `runtime_manifest`, `episode_metadata`, `prepared_effect`, `recovery_record` | persistence spec plus the new envelope/recovery schemas |

## Packaging Boundary

Schemas remain documentation-local under `docs/03_schemas/*.schema.json` and
are loaded through `Vanta.Schema`. This review does not perform or authorize a
runtime schema asset packaging migration.

## Non-goals

- No `COMMITTABLE`, `IRREVERSIBLE`, or `MEMORY_WRITE` enum change.
- No durable-memory schema.
- No distributed storage contract.
- No production migration contract.
- No H1-H5 or architecture validation claim.

