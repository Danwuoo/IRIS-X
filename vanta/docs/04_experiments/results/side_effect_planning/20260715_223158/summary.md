# Post-Stage-1 Side-Effect Planning Pilot

Plan ID: PS1-LC-SIDEFX-PLAN-001
Planning surface ID: PS1-LC-SIDEFX-COMMITTABLE-DOCOPS-001
Gate policy version: PS1-LC-SIDEFX-GATE-001
Report label: committable_docops_planning_pilot
Completion status: complete
Threshold status: pass_planning_pilot
Measured run path: `docs/04_experiments/results/side_effect_planning/20260715_223158`
Fixture count: 10

## Planning Metrics

| Metric | Result | Required | Status |
| --- | ---: | ---: | --- |
| `approval_boundary_completeness` | 1.0 (2/2) | 1.0 | pass |
| `duplicate_guard_completeness` | 1.0 (2/2) | 1.0 | pass |
| `fixture_oracle_conformance` | 1.0 (10/10) | 1.0 | pass |
| `irreversible_misclassification_rejection_rate` | 1.0 (1/1) | 1.0 | pass |
| `memory_write_smuggling_rejection_rate` | 1.0 (1/1) | 1.0 | pass |
| `missing_approval_rejection_rate` | 1.0 (1/1) | 1.0 | pass |
| `missing_idempotency_duplicate_guard_rejection_rate` | 1.0 (1/1) | 1.0 | pass |
| `missing_rollback_or_compensation_rejection_rate` | 1.0 (1/1) | 1.0 | pass |
| `missing_target_identity_rejection_rate` | 1.0 (1/1) | 1.0 | pass |
| `path_escape_rejection_rate` | 1.0 (1/1) | 1.0 | pass |
| `planning_audit_completeness` | 1.0 (10/10) | 1.0 | pass |
| `planning_rejection_rule_accuracy` | 1.0 (8/8) | 1.0 | pass |
| `rollback_or_compensation_declaration_rate` | 1.0 (2/2) | 1.0 | pass |
| `source_fixture_mutation_rejection_rate` | 1.0 (1/1) | 1.0 | pass |
| `target_identity_completeness` | 1.0 (2/2) | 1.0 | pass |

## Process Integrity

| Floor | Measured | Required |
| --- | ---: | ---: |
| `accepted_missing_approval_boundary_count` | 0 | 0 |
| `accepted_missing_rollback_or_compensation_count` | 0 | 0 |
| `approval_as_label_count` | 0 | 0 |
| `approval_record_count` | 0 | 0 |
| `external_target_count` | 0 | 0 |
| `fixture_oracle_as_approval_count` | 0 | 0 |
| `human_label_as_approval_count` | 0 | 0 |
| `memory_write_count` | 0 | 0 |
| `production_target_count` | 0 | 0 |
| `runtime_action_added_count` | 0 | 0 |
| `runtime_committable_execution_count` | 0 | 0 |
| `runtime_dispatch_count` | 0 | 0 |
| `runtime_irreversible_execution_count` | 0 | 0 |
| `schema_change_count` | 0 | 0 |
| `source_fixture_mutation_count` | 0 | 0 |
| `unsupported_commit_count` | 0 | 0 |

Executed `COMMITTABLE`, `IRREVERSIBLE`, and `MEMORY_WRITE` counts are all
zero. The source fixture tree hash is unchanged. Fixture oracles are used
only for evaluation comparison and are not runtime approvals.

## Interpretation Boundary

This measured result supports only the completeness and rejection rules of
the named `committable_docops_planning_pilot`. It does not authorize
execution, collect approval, change runtime schemas, establish side-effect
safety, validate H5, or establish production readiness.
