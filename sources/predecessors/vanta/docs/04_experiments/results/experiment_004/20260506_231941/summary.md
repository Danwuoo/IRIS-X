# Experiment 004 Local Run

Status: completed
Fixture count: 3
Baseline: blind_retry_openclaw_agent_local/openai-codex/gpt-5.4-mini_matched_budget
Treatment: targeted_recovery_openclaw_agent_local/openai-codex/gpt-5.4-mini_matched_budget

## Blind Retry

- recovery_success_rate: 0.0
- targeted_recovery_success: 0.0
- failure_label_accuracy: 0.0
- repeated_failure_rate: 1.0
- rollback_recovery_success: 0.0
- audit_gap_closure_rate: 0.0
- compensation_policy_accuracy: 0.0


## Targeted Recovery

- recovery_success_rate: 1.0
- targeted_recovery_success: 1.0
- failure_label_accuracy: 1.0
- repeated_failure_rate: 0.0
- rollback_recovery_success: 1.0
- audit_gap_closure_rate: 1.0
- compensation_policy_accuracy: 1.0


## Compute Matching

- budget_matched: true
- matched_fixture_count: 3

Interpretation: this is the Phase 4 targeted-recovery ablation protocol
output. It must not be described as validation of H4 unless produced by a
measured OpenClaw run with the matched-budget controls preserved.
