# Post-Stage-1 Lane A Larger Controlled Sample

Lane: Lane A larger controlled sample
Sample frame: PS1-LA-SAMPLE-002
Metric policy version: PS1-LA-METRIC-001
Threshold status: pass_acceptance_candidate
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
| `task_success_rate` | 0.6458 | 1.0000 |
| `invalid_action_rate` | 0.1207 | 0.2931 |
| `verifier_false_accept_rate` | 0.5294 | 0.0000 |
| `verifier_false_reject_rate` | 0.0571 | 0.0000 |
| `evidence_sufficiency_score` | 0.0000 | 1.0000 |
| `commit_integrity_score` | 0.0000 | 1.0000 |
| `replay_consistency` | 0.0000 | 1.0000 |
| `audit_completeness` | 0.0000 | 1.0000 |
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
- required_artifacts_valid: true
- arm_identity_compliant: true
- fixture_count_exact: true
- strata_complete: true


## Interpretation Boundaries

The run passes PS1-G2 as a pass_acceptance_candidate only. It still requires future manifest closure before accepted_by_closure may be used.

This report must not be described as H1-H5 validation, production readiness,
full Context OS validation, memory-write approval, irreversible-effect
approval, or a pure model-only OpenClaw baseline result.
