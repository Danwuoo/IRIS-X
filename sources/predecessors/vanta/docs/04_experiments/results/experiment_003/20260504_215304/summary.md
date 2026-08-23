# Experiment 003 Local Run

Status: completed
Fixture count: 7
Baseline: tool_trace_only_direct_execution
Treatment: stage1_episode_journal_replay_runtime

## Baseline

- commit_integrity_score: 0.0
- replay_consistency: 0.0
- audit_completeness: 0.0
- invalid_action_rate: 0.42857142857142855

## Treatment

- commit_integrity_score: 1.0
- replay_consistency: 1.0
- audit_completeness: 1.0
- invalid_action_rate: 0.42857142857142855

Interpretation: this is a seven-fixture local smoke run for journal audit
and replay pipeline stability. It must not be described as validation of H5.
