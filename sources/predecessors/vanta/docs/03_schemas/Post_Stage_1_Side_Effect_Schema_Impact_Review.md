# Post-Stage-1 Side-Effect Schema Impact Review

## Purpose

Review whether the current schema layer is sufficient for the first `PS1-G8`
side-effect planning bundle.

This review covers the fixture-local Document Ops `COMMITTABLE` planning surface
defined by
[Post-Stage-1 Side-Effect Planning Draft Spec](../02_specs/Post_Stage_1_Side_Effect_Planning_Draft_Spec.md).
It is a planning document and does not change any JSON schema file.

## Status

Review status: `Side-effect planning draft`.

Planning surface ID: `PS1-LC-SIDEFX-COMMITTABLE-DOCOPS-001`.

Gate policy version: `PS1-LC-SIDEFX-GATE-001`.

Schema decision for this batch: no schema changes.

Implementation status: `Not authorized`.

Runtime execution status: `Not authorized`.

Run status: named planning pilot complete at
`docs/04_experiments/results/side_effect_planning/20260715_223158/`.

Upstream schema-placement decisions: `OQ-SCHEMA-013` and `OQ-SCHEMA-014`
resolved on 2026-07-16. They constrain a future schema batch; they do not change
JSON Schema files in this decision-only batch.

## Conclusion

The current schemas are sufficient to route this batch as planning evaluation
because no runtime action, schema-bound runtime fixture, approval record, or
executed `COMMITTABLE` step is produced. The planning fixtures and measured run
artifacts are explicitly pilot-local evaluation contracts.

The current schemas are not sufficient for executable `COMMITTABLE` Document Ops
runtime behavior. They already contain a `COMMITTABLE` side-effect enum in some
places, but they do not define a concrete committable action type, structured
payload, typed approval record, idempotency guard, duplicate-commit guard, or
typed rollback or compensation contract.

Therefore this batch must remain a no-change schema impact review with explicit
planning placeholders.

The later separately accepted `PS1-G10` schema batch applies the upstream shape:
use an explicit
`commit_fixture_document_candidate` action enum with a dedicated payload;
define approval records in standalone `approval_record.schema.json`; and add
typed `approval_record_refs` to the Episode Journal. Approval objects must not
be inlined in the Episode Journal, and committed promotion is not hidden in
structured-edit output. These are G10 changes; this historical G8 review remains
a no-change decision for its own planning batch.

The measured pilot uses a run-local proposal fixture format and machine-readable
result contract. Their successful validation does not make current runtime
schemas sufficient for executable `COMMITTABLE` behavior and does not add a
second schema authority.

## Current Schema Coverage

| Schema | Current coverage | Impact decision |
| --- | --- | --- |
| `execution_step.schema.json` | `side_effect_class` includes `COMMITTABLE`, and generic fields exist for preconditions, postconditions, verifier requirements, and rollback policy. | Sufficient to discuss the class conceptually, but not sufficient for an executable committable action because `action_type` lacks `commit_fixture_document_candidate` and no payload contract exists. |
| `planner_action_sequence.schema.json` | Restricts planner actions to the current Stage 1 and G6 action set. | Correctly blocks a new committable action. Do not add a planning placeholder to the runtime planner schema in this batch. |
| `benchmark_task.schema.json` | `side_effect_classes` includes `COMMITTABLE`, while `allowed_actions` remains limited to current action names. | Sufficient to show future task intent, but not sufficient for runnable fixtures because no allowed committable action exists. |
| `evidence_packet.schema.json` | Allows generic structured `observation`, `provenance`, and `runtime_context` objects. | Sufficient for planning prose only; not enough to enforce required pre-effect and post-effect committable evidence. |
| `verifier_output.schema.json` | Supports `accept`, `reject`, `abstain`, and `request_evidence`, with `side_effect_safety` and `policy_constraints` scopes. | Sufficient for planning the verifier boundary; not enough to enforce approval correctness or duplicate-guard completeness. |
| `episode_journal.schema.json` | Supports commit status, rollback status, and memory-write audit refs. | Sufficient for audit-boundary discussion; not enough to type approval refs, idempotency keys, compensation plans, or post-effect manifest refs. |
| `experiment_run.schema.json` | Captures core experiment run-level artifacts and metrics. | No change. The measured planning pilot uses an explicitly run-local contract rather than asserting compatibility with the core experiment schema. |
| `eval_result.schema.json` | Captures evaluation outputs and labels when reported. | No change. Planning fixture oracles are not labels or runtime approvals and do not expand this schema. |

## Planning Placeholders

These fields are required by the planning spec but are not current schema
properties:

| Placeholder | Current representation | Future schema need |
| --- | --- | --- |
| `commit_fixture_document_candidate` | Markdown placeholder only. | New action enum and payload contract before execution. |
| `target_identity` | Planning table field. | Structured object binding fixture workspace, source ref, candidate ref, target path, and hashes. |
| `approval_policy_ref` | Planning table field. | Versioned approval policy reference. |
| `approval_record_requirement` | Planning table field. | Standalone `approval_record.schema.json` plus typed Episode Journal `approval_record_refs`; no inline approval object. |
| `idempotency_key` | Planning table field. | Required duplicate guard field before commit. |
| `duplicate_guard` | Planning table field. | Structured rule for rejecting repeated or conflicting commits. |
| `pre_effect_evidence_requirements` | Planning table field. | Required evidence fields or action-specific evidence contract. |
| `post_effect_evidence_requirements` | Planning table field. | Required post-effect evidence fields after authorized execution. |
| `rollback_or_compensation_statement` | Planning table field. | Typed enum or policy ref distinguishing strict rollback from compensation. |
| `compensation_plan_ref` | Planning table field when compensation is used. | Typed compensation or reconciliation record. |

The future `fixture_commit_supersede` compensation contract must also type the
prior and superseding commit identities, shared target identity, prior,
current, candidate, and final hashes, append-only supersession lineage,
active-pointer transition, approval/evidence/verifier/journal refs,
idempotency key, request
hash, and duplicate/conflict outcome. This is an upstream impact decision, not
a current schema addition.

These placeholders must not be smuggled into runtime artifacts as untyped
side-channel fields.

## No-Change Decisions

| Area | Decision |
| --- | --- |
| Action enums | Do not add `commit_fixture_document_candidate` or any other `COMMITTABLE` action name. |
| Runtime side-effect enablement | Do not change runtime allowlists or task allowlists. |
| Approval schema | Do not add `approval_record.schema.json` in this batch. |
| Evidence schema | Do not add committable-specific required evidence fields yet. |
| Journal schema | Do not add approval, idempotency, or compensation fields yet. |
| Benchmark fixtures | Do not add runnable `COMMITTABLE` fixtures in this batch. |
| Memory writes | Do not add or enable memory-write fields beyond the existing audit boundary. |
| Irreversible effects | Do not add irreversible-effect schema behavior. |

## Future Schema Candidates

A later implementation-candidate batch may consider these schema changes only
after an accepted successor spec requires them.

| Candidate | Possible trigger | Current status |
| --- | --- | --- |
| `commit_fixture_document_candidate` action and payload contract | A later accepted `Fixture-Local Document Commit Execution v0` gate requires executable copied-fixture promotion. | Upstream shape decided; schema addition not authorized in this batch. |
| `approval_record.schema.json` and Episode Journal `approval_record_refs` | A later accepted successor gate requires machine-readable approval before commit. | Upstream placement decided; schema addition not authorized in this batch. |
| `side_effect_policy.schema.json` | Multiple side-effect classes need shared policy versioning and target-boundary validation. | Future question, not authorized. |
| `commit_idempotency.schema.json` | Duplicate prevention needs schema validation across fixtures or runs. | Future question, not authorized. |
| `compensation_record.schema.json` | Fixture-local supersession is evaluated beyond declaration completeness under the resolved evidence floor. | Required shape partially fixed by `OQ-MEAS-010`; schema addition not authorized in this batch. |
| `committable_eval_result` fields | A future run reports side-effect planning or execution metrics repeatedly enough to require typed aggregation. | Future question, not authorized. |

## Acceptance Criteria For A Later Schema Batch

A later schema batch may be drafted only when it names:

- the accepted side-effect implementation spec requiring the schema
- the exact runtime or evaluation artifact that cannot be represented today
- the action enum, payload contract, and side-effect class mapping
- approval policy fields and approval record validation rules
- pre-effect and post-effect evidence fields
- rollback, compensation, or reconciliation enum values
- Episode Journal audit and replay requirements
- migration impact on existing Stage 1, G6, Lane A, and Lane B artifacts
- validation tests for every new required field or enum
- explicit proof that no `IRREVERSIBLE` or `MEMORY_WRITE` behavior is bundled
  into the `COMMITTABLE` schema change

## Rejection Conditions

A schema proposal must be rejected or kept at planning level if it:

- treats the existing `COMMITTABLE` enum as runtime authorization
- adds an action enum without an accepted implementation spec and verifier
  contract
- adds approval fields without an approval policy
- uses human labels as runtime approvals
- treats compensation as strict rollback
- allows source fixture mutation, path escape, external targets, production
  targets, memory writes, or irreversible effects
- claims H5 validation, production readiness, or runtime approval

## Related Documents

- [Post-Stage-1 Side-Effect Planning Draft Spec](../02_specs/Post_Stage_1_Side_Effect_Planning_Draft_Spec.md)
- [Post-Stage-1 Side-Effect Evaluation Plan](../04_experiments/Post_Stage_1_Side_Effect_Evaluation_Plan.md)
- [Post-Stage-1 Side-Effect Planning Pilot Run Report](../05_evaluation/Post_Stage_1_Side_Effect_Planning_Pilot_Run_Report.md)
- [Side-Effect Escalation Gate](../00_manifest/Side_Effect_Escalation_Gate.md)
- [Execution IR and Episode Semantics](../02_specs/Execution_IR_and_Episode_Semantics.md)
- [Evidence Packet and Verifier Runtime](../02_specs/Evidence_Packet_and_Verifier_Runtime.md)
- [Commit Abort Replay Semantics](../02_specs/Commit_Abort_Replay_Semantics.md)
- [execution_step.schema.json](execution_step.schema.json)
- [planner_action_sequence.schema.json](planner_action_sequence.schema.json)
- [benchmark_task.schema.json](benchmark_task.schema.json)
- [evidence_packet.schema.json](evidence_packet.schema.json)
- [verifier_output.schema.json](verifier_output.schema.json)
- [episode_journal.schema.json](episode_journal.schema.json)
