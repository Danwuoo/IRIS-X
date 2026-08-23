# Experiment 005 Local Run

Status: completed
Fixture count: 5
Baseline: raw_trace_bounded_openclaw_agent_local/openai-codex/gpt-5.4-mini_matched_budget
Treatment: working_set_compiler_v0_reference_backed_openclaw_agent_local/openai-codex/gpt-5.4-mini_matched_budget

## Baseline

- working_set_budget_adherence: 1.0
- working_set_provenance_completeness: 0.6
- context_omission_error_rate: 0.9333333333333332
- working_set_relevance_score: 0.1
- long_task_stability: 1.0
- task_success_rate: 1.0
- unsupported_commits: 0
- memory_writes: 0


## Treatment

- working_set_budget_adherence: 1.0
- working_set_provenance_completeness: 1.0
- context_omission_error_rate: 0.0
- working_set_relevance_score: 1.0
- long_task_stability: 1.0
- task_success_rate: 1.0
- unsupported_commits: 0
- memory_writes: 0


## Compute Matching

- budget_matched: true
- matched_fixture_count: 5

## Gate

- local_smoke_pass: true

Interpretation: this is a Phase 5 local smoke run for `Working Set Compiler
v0`. It is not validation of full Context OS or H3.
