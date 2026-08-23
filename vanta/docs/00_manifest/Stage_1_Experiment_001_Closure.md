# Stage 1 Experiment 001 Closure

## Purpose

Close the Stage 1 local smoke phase and Experiment 001 local smoke run without
claiming broad architectural proof.

## Closure Status

- Status: `Closed: local smoke completed`
- Closure date: 2026-05-03
- Closed scope: Stage 1 local Document Ops smoke phase and Experiment 001 local
  smoke comparison
- Result path: `docs/04_experiments/results/experiment_001/20260503_130927/`
- Fixture count: seven Document Ops fixtures
- Baseline: OpenClaw `openai-codex/gpt-5.4-mini` candidate canonical local LLM
  baseline, labeled as an OpenClaw local agent harness baseline
- Treatment: Stage 1 closed-loop runtime with Execution IR, Evidence Packet,
  deterministic Verifier v0, commit/abort handling, and Episode Journal

## Gate Result

The 2026-05-03 local run satisfied the Stage 1 local smoke gate:

| Gate item | Required | Observed | Status |
| --- | --- | --- | --- |
| Treatment `task_success_rate` | `1.0` | `1.0` | Met |
| Treatment `evidence_sufficiency_score` | `1.0` | `1.0` | Met |
| Treatment `replay_consistency` | `1.0` | `1.0` | Met |
| Unsupported treatment commits | `0` | `0` | Met |

## Metrics Summary

| Metric | Baseline | Treatment |
| --- | --- | --- |
| `task_success_rate` | `0.5714285714285714` | `1.0` |
| `invalid_action_rate` | `0.375` | `0.375` |
| `commit_integrity_score` | `0.5714285714285714` | `0.5714285714285714` |
| `evidence_sufficiency_score` | `0.0` | `1.0` |
| `replay_consistency` | `0.0` | `1.0` |

## Interpretation Boundaries

- This closes the Stage 1 local smoke phase only.
- This does not statistically support H1.
- This does not make the OpenClaw harness run a pure model-only baseline.
- This does not promote the result to a broader canonical benchmark.
- The OpenClaw call path includes the local agent harness and must remain
  labeled accordingly.

## Deferred Work

- Direct OpenAI Responses comparison with `gpt-5.4-mini`.
- Larger benchmark size beyond the current seven Document Ops fixtures.
- Human labeling budget and double-annotation rules.
- `verifier_false_accept_rate` and `verifier_false_reject_rate`, owned by
  Experiment 002 and verifier evaluation work.
- `audit_completeness`, owned by Experiment 003 and journal/replay evaluation
  work.
- Broader MVP thresholds beyond the Stage 1 local smoke gate.

## Related Documents

- [Stage 1 MVP Entry Gate](Stage_1_MVP_Entry_Gate.md)
- [Experiment 001: Minimal Loop](../04_experiments/Experiment_001_Minimal_Loop.md)
- [Experiment 001 Local Run Report](../05_evaluation/Experiment_001_Local_Run_Report.md)
- [Metrics Definition](../05_evaluation/Metrics_Definition.md)
