# Side-Effect Escalation Gate

## Purpose

Define the `PS1-G8` gate for side-effect classes beyond the Stage 1 runtime
allowances.

This gate allows side-effect specification, schema impact review, evaluation
planning, and implementation planning. It does not authorize runtime execution
of `COMMITTABLE`, `IRREVERSIBLE`, or `MEMORY_WRITE` actions.

## Status

Gate ID: `PS1-G8`

Gate policy ID: `PS1-LC-SIDEFX-GATE-001`

Status: `Accepted as PS1-G8 gate-definition artifact` on 2026-05-11.

Run status: named planning pilot complete at
`docs/04_experiments/results/side_effect_planning/20260715_223158/`.

Label status: `Not applicable`; fixture oracles were used as evaluation
comparators only and are not runtime approvals.

Accepted unlock: side-effect specification, schema impact review, evaluation
planning, and implementation planning only.

First planning bundle:
[Post-Stage-1 Side-Effect Planning Draft Spec](../02_specs/Post_Stage_1_Side_Effect_Planning_Draft_Spec.md),
[Post-Stage-1 Side-Effect Schema Impact Review](../03_schemas/Post_Stage_1_Side_Effect_Schema_Impact_Review.md),
and
[Post-Stage-1 Side-Effect Evaluation Plan](../04_experiments/Post_Stage_1_Side_Effect_Evaluation_Plan.md).
This bundle defines a fixture-local Document Ops `COMMITTABLE` planning surface
only. It does not authorize runtime execution, schema changes, approval
collection, experiments, production readiness, or H5 validation.

The named `committable_docops_planning_pilot` is complete for 10 planning
fixtures. All 15 planning metric floors passed, all 16 process-integrity floors
were `0`, and the source fixture tree remained unchanged. This measures only
planning completeness and rejection rules; it does not expand the accepted
unlock or create executable side-effect authority.

Upstream successor decisions recorded on 2026-07-16 select copied-workspace
Document Ops candidate promotion as the first domain, explicit action
`commit_fixture_document_candidate`, standalone approval-record schema
authority plus typed Episode Journal refs, and a minimum executable
`fixture_commit_supersede` evidence floor. The separately accepted `PS1-G10`
gate now authorizes actual execution only in explicitly marked ephemeral copied
fixtures. This does not modify the G8 gate's planning-only unlock, authorize
supersession, or make G8 evidence an executable approval.

## Inputs

This gate depends on the existing side-effect boundary stack:

- [Stage 1 MVP Entry Gate](Stage_1_MVP_Entry_Gate.md)
- [Post-Stage-1 Advancement Gate](Post_Stage_1_Advancement_Gate.md)
- [Post-Stage-1 Gate Inventory](Post_Stage_1_Gate_Inventory.md)
- [Execution IR and Episode Semantics](../02_specs/Execution_IR_and_Episode_Semantics.md)
- [Evidence Packet and Verifier Runtime](../02_specs/Evidence_Packet_and_Verifier_Runtime.md)
- [Commit Abort Replay Semantics](../02_specs/Commit_Abort_Replay_Semantics.md)
- [Post-Stage-1 Side-Effect Planning Draft Spec](../02_specs/Post_Stage_1_Side_Effect_Planning_Draft_Spec.md)
- [Post-Stage-1 Side-Effect Schema Impact Review](../03_schemas/Post_Stage_1_Side_Effect_Schema_Impact_Review.md)
- [Post-Stage-1 Side-Effect Evaluation Plan](../04_experiments/Post_Stage_1_Side_Effect_Evaluation_Plan.md)
- [Post-Stage-1 Metric Policy](../05_evaluation/Post_Stage_1_Metric_Policy.md)
- [Post-Stage-1 Labeling Scope and Adjudication Policy](../05_evaluation/Post_Stage_1_Labeling_Scope_and_Adjudication_Policy.md)
- [Post-Stage-1 Side-Effect Planning Pilot Run Report](../05_evaluation/Post_Stage_1_Side_Effect_Planning_Pilot_Run_Report.md)

The Stage 1 and post-Stage-1 local smoke closures are useful evidence for
fixture-local governance. They are not evidence that high-risk external effects
are safe, accepted, or validated.

## Escalation Layers

| Layer | Status after this gate | Allowed work | Still blocked |
| --- | --- | --- | --- |
| Stage 1 side-effect scope | Current implemented scope | Continue `READ_ONLY`, `SIMULATED`, and `REVERSIBLE` fixture-local Document Ops work under accepted specs and metrics. | Claims that this covers external or irreversible effects. |
| Fixture-local `COMPENSABLE` | Existing recovery fixture scope | Continue Phase 4-style compensation records for controlled local fixtures. | General external compensation semantics. |
| `COMMITTABLE` planning | Unlocked by this gate | Write specs, schema impact reviews, verifier contracts, approval policy, experiment plans, and implementation plans. | Runtime execution or schema-required new fields without a later implementation batch. |
| `IRREVERSIBLE` planning | Restricted planning only | Write successor gate and evaluation plans for high-risk irreversible effects. | Runtime execution, production deployment, or treating compensation as rollback. |
| `MEMORY_WRITE` planning | Unlocked by this gate | Write memory-write specs, provenance policy, deletion or retraction policy, verifier contracts, and evaluation plans. | Durable memory writes, learning claims, or memory governance implementation. |

## Side-Effect Policy Matrix

| Side-effect class | Required before implementation | Verifier and approval requirement | Rollback, compensation, and journal requirement |
| --- | --- | --- | --- |
| `COMMITTABLE` | Target identity, effect boundary, pre-effect evidence, post-effect evidence, idempotency or duplicate guard, and accepted action spec. | Verifier decision must be `accept`; approval record must identify approver type, scope, timestamp, and policy version. | Journal must link execution step, Evidence Packet, verifier output, approval record, commit status, and either rollback availability or compensation declaration. |
| `IRREVERSIBLE` | Successor gate, risk record, explicit non-goal review, target identity, and irreversible-effect acceptance criteria. | Execution remains blocked by this gate; any future successor must require explicit escalation and approval before action. | Journal policy must record `rollback_unavailable`, compensation or reconciliation plan, operator notification path, and post-action audit requirements. |
| `MEMORY_WRITE` | Memory candidate, source provenance, retention and scope policy, staleness check, conflict check, deletion or retraction path, and accepted memory-write spec. | Verifier decision must be `accept`; write approval must identify whether the write is automatic, operator-approved, or evaluation-only. | Episode Journal records the memory-write effect as audit data only; memory append is not learning unless a separate training process and evaluation document define it. |

Missing target identity, missing approval record, unverifiable provenance,
ambiguous rollback or compensation status, or absent verifier `accept` must
block commit and report `blocked_missing_approval`,
`blocked_missing_compensation_policy`, or the closest successor report label.

## Required Before Implementation

Before any implementation batch may execute `COMMITTABLE`, `IRREVERSIBLE`, or
`MEMORY_WRITE` actions, the repository must add and accept all of these
artifacts or explicitly named successors:

- a side-effect action spec that defines allowed domains, action types, target
  identity, preconditions, postconditions, and rejection conditions
- a schema impact review that states whether existing side-effect enums are
  sufficient or which new required fields are needed
- an Evidence Packet and verifier contract for each side-effect class
- an approval policy that defines automatic, operator, and escalation paths
- a rollback, compensation, reconciliation, or deletion policy as applicable
- an Episode Journal and replay contract for audit and postmortem review
- an experiment plan with fixed baselines, fixtures or sandbox targets,
  artifact locations, and process-integrity floors
- metric and labeling rules for unsafe actions, approval correctness,
  compensation adequacy, memory-write correctness, audit completeness, and
  operator intervention burden when those metrics are claimed

The implementation batch must update specs, schemas, runtime code, fixtures,
tests, and reports together. This gate does not authorize partial schema changes
or runtime behavior without accepted evidence and verifier paths.

## Reporting Requirements

Any future side-effect planning, implementation, or evaluation artifact must
report:

- `Gate policy version: PS1-LC-SIDEFX-GATE-001`
- satisfied and open gate IDs
- side-effect classes present in the run or proposal
- approval policy version and approval record location
- verifier policy version and Evidence Packet requirements
- rollback, compensation, reconciliation, deletion, or retraction policy
- unsupported commit count, memory-write count, and irreversible-effect count
- result path, label packet path, and machine-readable artifact path when
  results or labels are reported
- interpretation boundaries and whether the artifact is planning, exploratory,
  implementation candidate, or accepted by a later closure

Reports that do not satisfy this gate must use labels such as
`side_effect_planning_draft`, `side_effect_policy_accepted`,
`implementation_candidate_only`, `blocked_missing_approval`, or
`blocked_missing_compensation_policy`.

## Non-goals

- This gate does not execute `COMMITTABLE`, `IRREVERSIBLE`, or `MEMORY_WRITE`
  actions.
- This gate does not authorize production deployment.
- This gate does not validate H5.
- This gate does not collect labels or run a larger sample.
- This gate does not treat rollback as available for all effects.
- This gate does not treat compensation or reconciliation as strict rollback.
- This gate does not make memory append equivalent to learning.
- This gate does not convert human labels into runtime approval decisions.
- This gate does not replace external policy engines or operator approval in
  high-risk settings.

## Related Documents

- [Project Manifest](Project_Manifest.md)
- [Post-Stage-1 Advancement Gate](Post_Stage_1_Advancement_Gate.md)
- [Post-Stage-1 Gate Inventory](Post_Stage_1_Gate_Inventory.md)
- [Stage 1 MVP Entry Gate](Stage_1_MVP_Entry_Gate.md)
- [Execution IR and Episode Semantics](../02_specs/Execution_IR_and_Episode_Semantics.md)
- [Evidence Packet and Verifier Runtime](../02_specs/Evidence_Packet_and_Verifier_Runtime.md)
- [Commit Abort Replay Semantics](../02_specs/Commit_Abort_Replay_Semantics.md)
- [Post-Stage-1 Metric Policy](../05_evaluation/Post_Stage_1_Metric_Policy.md)
- [Post-Stage-1 Labeling Scope and Adjudication Policy](../05_evaluation/Post_Stage_1_Labeling_Scope_and_Adjudication_Policy.md)
