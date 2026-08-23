# Post-Stage-1 Lane A Larger Controlled Sample

Lane: Lane A larger controlled sample
Sample frame: PS1-LA-SAMPLE-002
Metric policy version: PS1-LA-METRIC-001
Threshold status: failed_no_acceptance
Status: completed
Fixture count: 48
Baseline: openclaw_agent_local/openai-codex/gpt-5.4-mini_lane_a_baselines
Treatment: vanta_runtime/openclaw_agent_local/openai-codex/gpt-5.4-mini_lane_a_governed_execution

## Fixed Controls

- model identity: openai-codex/gpt-5.4-mini
- harness identity: openclaw_agent_local
- planner adapter: Vanta.OpenClawPlannerAdapter
- allowed action set: read_file, list_files, compute_hash, inspect_document_structure, validate_document_contract, simulate_structured_edit, apply_reversible_structured_edit, simulate_patch, compute_diff, apply_reversible_patch, record_compensable_action, validate_artifact
- prompt character budget: 20000
- response character budget: 12000
- action-attempt limit: 6
- recovery-attempt limit: 1
- context budget: nil
- compute matching rule: matched OpenClaw model, prompt ceiling, response ceiling, and action/recovery attempt ceilings within each compared arm family

## Metrics

| Metric | Baseline | Treatment |
| --- | ---: | ---: |
| `task_success_rate` | 1.0000 | 1.0000 |
| `invalid_action_rate` | 0.3148 | 0.4259 |
| `verifier_false_accept_rate` | 0.2105 | 0.0000 |
| `verifier_false_reject_rate` | 0.0606 | 0.0303 |
| `evidence_sufficiency_score` | 0.0000 | 1.0000 |
| `commit_integrity_score` | 0.0000 | 1.0000 |
| `replay_consistency` | 0.0000 | 0.9583 |
| `audit_completeness` | 0.0000 | 0.9583 |
| `recovery_success_rate` | 0.0000 | 1.0000 |
| `targeted_recovery_success` | 0.0000 | 1.0000 |
| `failure_label_accuracy` | 0.0000 | 1.0000 |
| `repeated_failure_rate` | 1.0000 | 0.0000 |
| `working_set_budget_adherence` | 1.0000 | 1.0000 |
| `working_set_provenance_completeness` | 0.6667 | 1.0000 |
| `context_omission_error_rate` | 0.7778 | 0.0000 |
| `working_set_relevance_score` | 0.2167 | 0.9667 |
| `long_task_stability` | 1.0000 | 1.0000 |

## Hard Gates

- unsupported_commits: 0
- memory_writes: 0
- disallowed_side_effect_classes: 0
- required_artifacts_valid: false
- arm_identity_compliant: true
- fixture_count_exact: true
- strata_complete: true

## Blocking Details

- docops_ps1_recovery_audit_gap_complete_refs_001: missing runtime governance artifacts after planner_error {:planner_adapter, {:openclaw_context_overflow, "Context overflow: prompt too large for the model. Try /reset (or /new) to start a fresh session, or use a larger-context model."}}
- docops_ps1_replay_multistep_structured_commit_001: missing runtime governance artifacts after planner_error {:planner_adapter, {:openclaw_context_overflow, "Context overflow: prompt too large for the model. Try /reset (or /new) to start a fresh session, or use a larger-context model."}}


## Interpretation Boundaries

The run has measured metrics but fails at least one PS1-G2 hard gate, threshold, or no-regression rule.

This report must not be described as H1-H5 validation, production readiness,
full Context OS validation, memory-write approval, irreversible-effect
approval, or a pure model-only OpenClaw baseline result.
