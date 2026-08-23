# Fixture-Local COMMITTABLE Schema Impact Review

## Review Identity

- Gate: `PS1-G10 — Fixture-Local COMMITTABLE Execution Gate`
- Review date: 2026-07-16
- Spec: `fixture-local-committable-document-promotion-v0`
- Decision: accepted additive action, approval, evidence, journal, and
  persisted-artifact schema batch

## Upstream Decisions Applied

This review implements accepted `OQ-SCHEMA-013` and `OQ-SCHEMA-014` exactly:
Approval Record is standalone schema authority with typed journal refs, and the
commit action is an explicit enum with a dedicated payload rather than an
extension of structured-edit output.

## Schema Changes

| Schema | Accepted impact |
| --- | --- |
| `approval_record.schema.json` | New standalone approval artifact with decision, approver, action/target/candidate/policy/time scope. |
| `execution_step.schema.json` | Add only `commit_fixture_document_candidate` plus its dedicated closed payload. |
| `planner_action_sequence.schema.json` | Represent the explicit action for caller-supplied governed sequences; general model-planner enumeration remains code-restricted. |
| `benchmark_task.schema.json` | Allow the named action in fixture tasks. |
| `evidence_packet.schema.json` | Add typed evidence phase, target identity, Approval Record refs, and artifact refs used by G10 pre/post packets. |
| `episode_journal.schema.json` | Add typed `approval_record_refs` and committed `artifact_refs`; G10 runtime validation requires both for committed actions. |
| `persisted_artifact.schema.json` | Add `approval_record` artifact type; generic SQLite table shape is unchanged. |
| `canonical_state.schema.json` | No shape change. |
| `verifier_output.schema.json` | No shape change; two schema-valid outputs reference pre/post evidence separately. |
| `persistence_manifest.schema.json` | No shape or lifecycle change. |
| `recovery_record.schema.json` | No shape change; existing target and backup objects carry the typed G10 prepared intent. |

## Compatibility And Authority

Existing Stage 1/G6 payloads remain schema-valid. New evidence/journal fields
are optional for historical non-G10 artifacts, while the G10 runtime commit
validator makes them mandatory for the named action. This avoids rewriting
historical measured artifacts while keeping the executable boundary fail-closed.

SQLite `persistence-v0` tables are already generic over artifact type and JSON
payload, so no database migration or duplicate schema authority is introduced.
Schemas remain documentation-local under `docs/03_schemas/*.schema.json`.

The general `Vanta.action_types/0` model-planner list and general Stage 1
side-effect list do not gain broad `COMMITTABLE` authority. Code exposes a
separate action-specific G10 authorization check.

## Validation Requirements

- every new valid record validates independently;
- missing approval scope, expiry, target identity, or candidate hash fails;
- action payload rejects extra fields, path smuggling, memory fields, and
  unsupported rollback statements;
- G10 committed journal refs exactly match persisted approval/evidence/verifier
  payload IDs and its committed artifact ref;
- existing fixtures and schemas remain valid; and
- no `IRREVERSIBLE` or `MEMORY_WRITE` action is added.

## Non-Goals

- no external or production action schema;
- no supersession/compensation schema in v0;
- no memory schema, irreversible action, distributed transaction, packaged
  runtime schema asset, or H1-H5 validation claim.
