# Schemas Index

## Purpose

Provide the L3 navigation entry for Vanta data contracts. This index lists the
current JSON schema files and separates schema contracts from schema impact
review documents.

## Scope

Schema files in this directory are the `*.schema.json` contracts consumed by
runtime, benchmark, experiment, and evaluation artifacts. Markdown files in this
directory are review or planning documents unless they explicitly say otherwise.

The accepted 2026-07-06 schema packaging decision keeps these schema files
documentation-local under `docs/03_schemas/*.schema.json` for the current
Post-Stage-1 runtime. `Vanta.Schema` loads validation contracts from this
docs-local path. Packaged runtime assets require a later accepted migration gate
with loader, package, and test changes.

Post-Stage-1 Context OS and G8 Side-Effect schema impact reviews remain
historical no-change planning decisions. The separately accepted G10 review
adds one standalone approval contract and the explicitly scoped fixture-commit
shape; it does not add memory writes, irreversible effects, external targets,
or full Context OS behavior.

## Complete Schema List

| Schema file | Category | Purpose |
| --- | --- | --- |
| `canonical_state.schema.json` | Runtime schema | Accepted task-relevant state snapshot. It is not an execution trace or raw tool log. |
| `execution_step.schema.json` | Runtime schema | Action-level Execution IR step, including action identity, dependencies, side-effect class, and commit or rollback boundary metadata. |
| `planner_action_sequence.schema.json` | Runtime schema | Bounded planner output sequence consumed before execution and verification. It is planner output, not verifier output. |
| `evidence_packet.schema.json` | Runtime schema | Structured evidence for verifier, audit, recovery, and regression handling. It is not an explanation field. |
| `verifier_output.schema.json` | Runtime schema | Verifier decision and diagnostics. Verifier Runtime is not limited to final-answer judging. |
| `episode_journal.schema.json` | Runtime schema | Audit and replay journal for runtime episodes. It is not durable memory. |
| `approval_record.schema.json` | Runtime schema | Standalone approval decision and exact action/target/candidate/policy/time scope for G10; it is not verifier output or evidence. |
| `persistence_manifest.schema.json` | Persistence schema | Fixture-local episode lifecycle, accepted state/journal pointers, and storage/runtime/hash-policy versions. |
| `persisted_artifact.schema.json` | Persistence schema | Immutable typed artifact envelope; it does not replace core payload schemas. |
| `recovery_record.schema.json` | Persistence schema | Prepared-effect, crash-window, rollback, and recovery metadata. |
| `benchmark_task.schema.json` | Benchmark schema | Document Ops task fixture contract, including inputs, allowed actions, expected artifacts, and runtime artifact requirements. |
| `fixture_acceptance.schema.json` | Benchmark schema | Deterministic expected outcome and action recipe for controlled fixtures. |
| `experiment_run.schema.json` | Benchmark and evaluation schema | Compact measured run record for local and post-Stage-1 experiment outputs. A valid run record does not by itself create closure acceptance. |
| `eval_result.schema.json` | Evaluation schema | Evaluation result contract for metric and failure-attribution outputs. |
| `recovery_decision.schema.json` | Working-set and recovery schema | Failure classification and targeted recovery proposal for recovery experiments. |
| `working_set.schema.json` | Working-set and recovery schema | Budget-aware, provenance-backed working-set artifact with selected references and known omissions. |

## Category Navigation

### Runtime Schemas

- `canonical_state.schema.json`
- `execution_step.schema.json`
- `planner_action_sequence.schema.json`
- `evidence_packet.schema.json`
- `verifier_output.schema.json`
- `episode_journal.schema.json`
- `approval_record.schema.json`
- `persistence_manifest.schema.json`
- `persisted_artifact.schema.json`
- `recovery_record.schema.json`

Runtime schemas support the Stage 1 spine:

```text
state -> plan -> action -> evidence -> verify -> commit / abort
```

### Benchmark Schemas

- `benchmark_task.schema.json`
- `fixture_acceptance.schema.json`
- `experiment_run.schema.json`

Benchmark schemas describe fixture tasks, deterministic acceptance metadata, and
measured run artifacts. They do not replace experiment protocols or closure
documents.

### Evaluation Schemas

- `eval_result.schema.json`
- `experiment_run.schema.json`

Evaluation schemas support metrics, reporting, and run-level measurement records.
Human label packet templates under `docs/05_evaluation/label_packets/` are
packet-local evaluation tooling, not core runtime schemas.

### Working-Set and Recovery Schemas

- `working_set.schema.json`
- `recovery_decision.schema.json`

Working-set and recovery schemas support bounded context compilation, provenance,
known-omission reporting, failure classification, and targeted recovery. They do
not authorize learned retrieval, memory governance, memory writes, or full
Context OS behavior.

### Persistence Schemas

- `persistence_manifest.schema.json`
- `persisted_artifact.schema.json`
- `recovery_record.schema.json`

These schemas implement the `PS1-G9` storage envelope, lifecycle, pointer, and
recovery contracts. Core runtime payloads continue to validate against their
existing schemas. Persistence schemas do not authorize production or
distributed storage, durable memory, or external side effects.

## Review Documents In This Directory

| Review document | Status |
| --- | --- |
| `Post_Stage_1_Context_OS_Schema_Impact_Review.md` | Context OS planning review. No schema changes in the planning batch. |
| `Post_Stage_1_Side_Effect_Schema_Impact_Review.md` | Side-effect planning review. No schema changes and no executable `COMMITTABLE`, `IRREVERSIBLE`, or `MEMORY_WRITE` expansion in the planning batch. |
| `Post_Stage_1_Persistence_Schema_Impact_Review.md` | `PS1-G9` impact review. Adds three persistence schemas while preserving existing core enum and payload authority. |
| `Fixture_Local_Committable_Schema_Impact_Review.md` | `PS1-G10` impact review. Adds Approval Record authority, one explicit action payload, typed approval/artifact refs, and two-phase evidence fields only for the named copied-fixture path. |

These reviews should be routed from manifest, spec, experiment, and evaluation
documents when schema impact is discussed. The no-change reviews do not prove a
schema change; G9 and G10 authorize only the changes their reviews enumerate.
