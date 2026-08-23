# Post-Stage-1 Side-Effect Evaluation Plan

## Purpose

Define the minimum evaluation plan for the first `PS1-G8` side-effect planning
bundle.

This plan covers planning review for a fixture-local Document Ops
`COMMITTABLE` surface. It is not an experiment result, does not execute
`COMMITTABLE` actions, does not change schemas, and does not validate H5.

## Status

Plan ID: `PS1-LC-SIDEFX-PLAN-001`.

Plan status: `Executed by named planning pilot`.

Planning surface ID: `PS1-LC-SIDEFX-COMMITTABLE-DOCOPS-001`.

Gate policy version: `PS1-LC-SIDEFX-GATE-001`.

Run status for this plan: `committable_docops_planning_pilot` complete at
`docs/04_experiments/results/side_effect_planning/20260715_223158/`.

Implementation status: `Not authorized`.

Runtime execution status: `Not authorized`.

Schema status: no schema changes in this planning batch.

## Source Documents

This plan uses:

- [Post-Stage-1 Side-Effect Planning Draft Spec](../02_specs/Post_Stage_1_Side_Effect_Planning_Draft_Spec.md)
- [Post-Stage-1 Side-Effect Schema Impact Review](../03_schemas/Post_Stage_1_Side_Effect_Schema_Impact_Review.md)
- [Side-Effect Escalation Gate](../00_manifest/Side_Effect_Escalation_Gate.md)
- [Post-Stage-1 Advancement Gate](../00_manifest/Post_Stage_1_Advancement_Gate.md)
- [Post-Stage-1 Metric Policy](../05_evaluation/Post_Stage_1_Metric_Policy.md)
- [Metrics Definition](../05_evaluation/Metrics_Definition.md)
- [Execution IR and Episode Semantics](../02_specs/Execution_IR_and_Episode_Semantics.md)
- [Evidence Packet and Verifier Runtime](../02_specs/Evidence_Packet_and_Verifier_Runtime.md)
- [Commit Abort Replay Semantics](../02_specs/Commit_Abort_Replay_Semantics.md)

## Evaluation Boundary

This plan evaluates whether future planning artifacts are complete enough to
route into a later schema or implementation candidate. It does not evaluate
runtime safety of executed `COMMITTABLE` actions.

| Area | Evaluation rule |
| --- | --- |
| Executed `COMMITTABLE` actions | Must remain `0` in this planning plan. |
| Executed `IRREVERSIBLE` actions | Must remain `0`. |
| `MEMORY_WRITE` effects | Must remain `0`. |
| External targets | Must remain `0`. |
| Production targets | Must remain `0`. |
| Runtime approvals | Not collected; human labels and fixture oracles are not approval records. |
| Schema changes | None in this batch. |
| Claims | Planning completeness only; no H5, production readiness, runtime approval, or side-effect safety claim. |

## Planning Pilot Fixture Families

The formal planning pilot defines immutable, validator-consumed planning
fixtures for these families. They are evaluation inputs, not runtime task
fixtures and not executable `COMMITTABLE` actions.

| Family | Expected planning result | Required negative check |
| --- | --- | --- |
| Valid fixture-local commit proposal | Proposal names target identity, hashes, approval boundary, duplicate guard, verifier requirements, and rollback or compensation statement. | Must still report no runtime execution. |
| Missing target identity | Planning review rejects the proposal. | Reject cannot be converted into runtime approval. |
| Missing approval boundary | Planning review reports `blocked_missing_approval`. | Human label or fixture oracle cannot satisfy approval. |
| Missing duplicate guard | Planning review rejects the proposal before any execution candidate. | Repeated target writes are not allowed. |
| Missing rollback or compensation statement | Planning review reports `blocked_missing_compensation_policy`. | Rollback must not be assumed. |
| Path escape or source-fixture mutation | Planning review rejects the proposal. | Source fixtures, repository docs, user files, and external paths remain out of scope. |
| Irreversible misclassification | Planning review rejects any proposal that should be `IRREVERSIBLE`. | `COMMITTABLE` must not hide irreversible effects. |
| Memory-write smuggling | Planning review rejects any proposal that writes or updates memory. | Memory append is not learning and is not authorized. |

## Planning Pilot Artifact Contract

The planning pilot writes artifacts under:

```text
docs/04_experiments/results/side_effect_planning/<timestamp>/
```

Required files:

- `run.json`
- `fixture_results.json`
- `environment_manifest.json`
- `summary.md`
- `fixture_inventory.md`
- `commit_plan_inventory.md`
- `approval_boundary_report.md`
- `rollback_compensation_report.md`
- `schema_impact_ref.md`
- `label_packet_ref.md` or `not_applicable.md`

No artifact path in this section authorizes runtime execution. `run.json` for a
planning pilot must report execution counts for `COMMITTABLE`, `IRREVERSIBLE`,
and `MEMORY_WRITE` as `0`.

## Planning Pilot Runner

`Vanta.PostStage1SideEffectPlanning.Validator`,
`Vanta.PostStage1SideEffectPlanning`, and
`mix vanta.post_stage_1_side_effect_planning` implement the rerunnable validator,
runner, and CLI entry point. The runner reads immutable planning fixtures,
materializes proposals in memory, records evaluation-only oracle comparisons,
writes the required artifacts, and locks executed `COMMITTABLE`,
`IRREVERSIBLE`, and `MEMORY_WRITE` counts to `0`.

The first generated scaffold artifact set is
`docs/04_experiments/results/side_effect_planning/20260701_201804/`.

The historical scaffold is not a planning-pilot result. The complete measured
pilot is `20260715_223158`; it does not add action enums, modify runtime
allowlists, enter `Vanta.Runtime.run_task/3`, collect approvals, create label
packets, validate H5, or approve deployment.

## Process-Integrity Floors

A future planning pilot may be reviewed only if all floors below are met.

| Floor | Required value | Interpretation |
| --- | ---: | --- |
| `runtime_committable_execution_count` | `0` | This plan does not execute `COMMITTABLE` actions. |
| `runtime_irreversible_execution_count` | `0` | Irreversible effects remain blocked. |
| `memory_write_count` | `0` | Memory writes remain blocked. |
| `external_target_count` | `0` | No external target is authorized or executed; rejected negative proposals may describe prohibited paths. |
| `production_target_count` | `0` | Production deployment remains out of scope. |
| `source_fixture_mutation_count` | `0` | Planning must not mutate source fixtures or repository docs. |
| `unsupported_commit_count` | `0` | Existing process-integrity hard gate remains in force. |
| `approval_as_label_count` | `0` | Labels and fixture oracles are not approvals. |
| `accepted_missing_approval_boundary_count` | `0` | Missing boundary keeps the negative item blocked. |
| `accepted_missing_rollback_or_compensation_count` | `0` | Missing statement keeps the negative item blocked. |
| `runtime_dispatch_count` | `0` | The planning placeholder never enters runtime dispatch. |

Any nonzero executed high-risk effect keeps the report outside this plan and
must be treated as a policy violation, not as evidence.

## Planning Metrics

These metrics are planning-review metrics only. Every named pilot metric has a
strict `1.0` completion floor; these floors are not acceptance thresholds for
runtime execution.

| Metric | Computation rule | Required source |
| --- | --- | --- |
| `approval_boundary_completeness` | Complete approval-boundary fields divided by predeclared positive-control proposals. | Materialized planning proposal records. |
| `target_identity_completeness` | Positive-control proposals with complete fixture, source, candidate, target, and hash identity divided by positive-control proposals. | Materialized planning proposal records. |
| `duplicate_guard_completeness` | Positive-control proposals with idempotency key and duplicate guard divided by positive-control proposals. | Materialized planning proposal records. |
| `rollback_or_compensation_declaration_rate` | Positive-control proposals with `fixture_commit_restore` or `fixture_commit_supersede` divided by positive-control proposals. | Materialized planning proposal records. |
| `missing_approval_rejection_rate` | Missing-approval negative proposals rejected divided by missing-approval negative proposals. | Negative planning fixture family. |
| `path_escape_rejection_rate` | Path-escape proposals rejected divided by path-escape proposals. | Negative planning fixture family. |
| `memory_write_smuggling_rejection_rate` | Memory-write proposals rejected divided by memory-write smuggling proposals. | Negative planning fixture family. |
| `planning_audit_completeness` | Proposals with all required planning audit refs divided by reviewed proposals. | Planning artifact inventory. |
| `planning_rejection_rule_accuracy` | Negative proposals whose decision, report label, and reason codes match the frozen fixture oracle divided by negative proposals. | All negative planning fixture families. |
| `fixture_oracle_conformance` | All proposals whose validator result exactly matches the evaluation-only oracle divided by all proposals. | Fixture results. |

Family-specific rejection metrics also cover missing target identity, missing
idempotency/duplicate guard, missing rollback/compensation, source-fixture
mutation, and irreversible misclassification. Each has a strict `1.0` pilot
completion floor.

## Measured Pilot Result

The complete `20260715_223158` run contains 10 fixtures: two positive controls
and eight negative controls. All 15 planning metrics equal `1.0000`; aggregate
rejection-rule accuracy is `8 / 8`, oracle conformance is `10 / 10`, and
planning audit completeness is `10 / 10`. All 16 process-integrity floors are
`0`, including actual source-fixture mutation and all runtime execution counts.
The measured report is
[Post-Stage-1 Side-Effect Planning Pilot Run Report](../05_evaluation/Post_Stage_1_Side_Effect_Planning_Pilot_Run_Report.md).

Future runtime safety metrics such as unsafe commit rate, approval correctness,
operator intervention burden, rollback success, and compensation adequacy
require a later accepted implementation spec, schema batch, fixtures, and
measured run. They must not be claimed from this planning plan.

## Resolved Successor Evaluation Inputs

The 2026-07-16 upstream decisions close the design questions needed to draft a
future executable evaluation contract. They do not amend this completed
planning pilot and do not authorize a run.

- The first domain is candidate promotion inside explicitly marked ephemeral
  copied Document Ops fixture workspaces.
- The future action is explicit `commit_fixture_document_candidate`, not a
  structured-edit output extension.
- Approval is a standalone typed artifact referenced from the Episode Journal,
  not a verifier result, label, fixture oracle, or inline journal object.
- The later separately accepted `PS1-G10` gate now provides the one scoped
  implementation/execution authority for strict-restore candidate promotion in
  marked ephemeral copied fixtures; this G8 plan itself remains planning-only.

For `fixture_commit_supersede`, evaluation beyond declaration completeness must
predeclare and measure at least:

| Evidence or case | Minimum acceptance meaning |
| --- | --- |
| Identity and hashes | Prior and superseding commit IDs, shared target identity, and prior/current/candidate/final hashes are complete and agree. |
| Append-only lineage | The prior artifact remains immutable and retrievable; a supersession relation is appended and the active pointer resolves to the successor. |
| Governance refs | Target-scoped approval, verifier `accept`, pre/post Evidence Packet refs, Episode Journal refs, and final accepted state hash are resolvable. |
| Idempotent retry | Same key and request returns the durable prior compensation result with no duplicate effect. |
| Stale or conflicting predecessor | Changed current hash, wrong active predecessor, or same key with a different request is rejected without mutation. |
| Restart and replay | Restart recovery, audit completeness, ordered lineage, pointer transition, refs, hashes, and final state replay exactly. |

No `fixture_commit_supersede` minimum-evidence item in this section has been
executed or measured. Experiment 007 measures strict restore only; a future
supersession plan must set exact metrics and floors before running.

## Pre-Run Gates For The Planning Pilot

The completed planning pilot satisfied these gates before execution:

| Gate | Required condition |
| --- | --- |
| `PS1-G8` | Planning remains inside `PS1-LC-SIDEFX-GATE-001`. |
| Planning spec | The side-effect planning draft or successor names the surface and non-goals. |
| Schema review | The schema impact review is accepted as no-change or superseded by an accepted schema batch. |
| Approval boundary | The pilot states that labels and fixture oracles are not runtime approvals. |
| Process integrity | Executed `COMMITTABLE`, `IRREVERSIBLE`, and `MEMORY_WRITE` counts are expected to remain `0`. |
| Artifact path | Output path and required planning artifacts are fixed before review. |

## Reporting Labels

Allowed report labels:

- `side_effect_planning_draft`
- `committable_docops_planning_pilot`
- `blocked_missing_approval`
- `blocked_missing_compensation_policy`
- `blocked_path_escape`
- `blocked_memory_write`
- `blocked_irreversible_misclassification`
- `blocked_incomplete_proposal`

Disallowed report labels:

- `accepted_by_closure`
- `H5 validated`
- `side-effect safety validated`
- `runtime approval collected`
- `COMMITTABLE execution authorized`
- `IRREVERSIBLE execution authorized`
- `MEMORY_WRITE authorized`
- `production ready`

## Non-goals

- This plan does not run an executable side-effect experiment.
- This plan does not add or execute runtime actions.
- This plan does not change schemas.
- This plan does not authorize `COMMITTABLE`, `IRREVERSIBLE`, or
  `MEMORY_WRITE` runtime execution.
- This plan does not collect approval records.
- This plan does not convert human labels into approvals.
- This plan does not treat compensation as rollback.
- This plan does not validate H5.
- This plan does not authorize production deployment.

## Related Documents

- [Post-Stage-1 Side-Effect Planning Draft Spec](../02_specs/Post_Stage_1_Side_Effect_Planning_Draft_Spec.md)
- [Post-Stage-1 Side-Effect Schema Impact Review](../03_schemas/Post_Stage_1_Side_Effect_Schema_Impact_Review.md)
- [Side-Effect Escalation Gate](../00_manifest/Side_Effect_Escalation_Gate.md)
- [Post-Stage-1 Advancement Gate](../00_manifest/Post_Stage_1_Advancement_Gate.md)
- [Post-Stage-1 Gate Inventory](../00_manifest/Post_Stage_1_Gate_Inventory.md)
- [Post-Stage-1 Metric Policy](../05_evaluation/Post_Stage_1_Metric_Policy.md)
- [Metrics Definition](../05_evaluation/Metrics_Definition.md)
- [Execution IR and Episode Semantics](../02_specs/Execution_IR_and_Episode_Semantics.md)
- [Evidence Packet and Verifier Runtime](../02_specs/Evidence_Packet_and_Verifier_Runtime.md)
- [Commit Abort Replay Semantics](../02_specs/Commit_Abort_Replay_Semantics.md)
