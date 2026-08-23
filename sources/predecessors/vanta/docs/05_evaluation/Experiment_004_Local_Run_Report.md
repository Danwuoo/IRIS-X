# Experiment 004 Local Run Report

## Experiment

- Experiment ID: `experiment_004_targeted_recovery`
- Date: 2026-05-06
- Runtime version: local `vanta` workspace, Mix project version `0.1.0`
- Evaluator: fixture oracle plus recovery assertions
- Dataset or benchmark: three controlled Document Ops recovery fixtures
- Status: `Completed OpenClaw local harness run`
- Result path:
  `docs/04_experiments/results/experiment_004/20260506_231941/`

## Setup

- Baseline:
  `blind_retry_openclaw_agent_local/openai-codex/gpt-5.4-mini_matched_budget`
- Treatment:
  `targeted_recovery_openclaw_agent_local/openai-codex/gpt-5.4-mini_matched_budget`
- Backbone model: OpenClaw `openai-codex/gpt-5.4-mini`
- Tool interface: OpenClaw local harness through WSL
- Fixture set:
  `docops_rollback_failure_001`, `docops_audit_gap_001`, and
  `docops_compensable_action_001`
- Side-effect scope: fixture-local recovery artifacts only; no irreversible
  external action is executed

The baseline repeats the original failing action sequence without failure
labels, credit vectors, or recovery-policy hints. The treatment asks the
OpenClaw recovery adapter for a schema-valid Recovery Decision and applies only
allowlisted fixture-local recovery policies.

## Metrics

| Metric | Blind Retry | Targeted Recovery | Notes |
| --- | --- | --- | --- |
| `recovery_success_rate` | `0.0` | `1.0` | All three targeted recovery attempts satisfied fixture recovery assertions. |
| `targeted_recovery_success` | `0.0` | `1.0` | Treatment policy matched each expected recovery policy and succeeded. |
| `failure_label_accuracy` | `0.0` | `1.0` | Treatment labels included fixture oracle labels; oracle labels were not treatment input. |
| `repeated_failure_rate` | `1.0` | `0.0` | Blind retry left the original failures unresolved. |
| `rollback_recovery_success` | `0.0` | `1.0` | Rollback reconstruction succeeded on the rollback-failure fixture. |
| `audit_gap_closure_rate` | `0.0` | `1.0` | Audit refs were repaired on the audit-gap fixture. |
| `compensation_policy_accuracy` | `0.0` | `1.0` | Compensation treatment was selected and completed for the compensable fixture. |

Compute matching was preserved fixture by fixture:

| Compute field | Blind Retry Mean | Targeted Recovery Mean |
| --- | --- | --- |
| `model_call_count` | `1.0` | `1.0` |
| `prompt_chars` | `7228.0` | `7228.0` |
| `response_chars` | `319.3333333333333` | `319.3333333333333` |
| `estimated_input_tokens` | `1807.3333333333333` | `1807.3333333333333` |
| `estimated_output_tokens` | `80.0` | `80.0` |
| `action_attempts` | `1.0` | `1.0` |

Token counts are estimates derived from character counts because the current
OpenClaw harness contract does not expose exact token usage.

## Run Command

Command recorded for Experiment 004 runs:

```powershell
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$out = "docs/04_experiments/results/experiment_004/$timestamp"
mix vanta.experiment004 --out $out
```

Observed result path:

```text
docs/04_experiments/results/experiment_004/20260506_231941/
```

`run.json` and `summary.md` were produced. The result status is `completed`.

## Findings

- The run status is `completed`.
- The treatment selected `reconstruct_rollback_from_diff` for
  `docops_rollback_failure_001`, `repair_audit_refs` for
  `docops_audit_gap_001`, and `produce_compensation_record` for
  `docops_compensable_action_001`.
- All three targeted recovery attempts wrote fixture-local recovery artifacts
  and satisfied their fixture-specific recovery assertions.
- Blind retry used the matched local budget but did not recover any of the
  three controlled failures.
- The run provides a measured local smoke result for the Phase 4 recovery
  protocol. It is not broad validation of H4.

## Failures And Risks

- The fixture count is three, so this is a smoke-scale controlled ablation, not
  a statistically powered recovery benchmark.
- OpenClaw results include local harness effects and must not be described as
  pure model-only recovery results.
- Fixture oracle labels and expected recovery policies are deterministic scoring
  references, not substitutes for human labels in broader evaluation.
- Exact token accounting remains unavailable; the compute ledger uses
  character-derived estimates.

## Next Steps

- Keep Phase 4 claims scoped to the three-fixture local smoke result until
  larger Document Ops recovery samples exist.
- Add ambiguous or multi-cause recovery fixtures before treating failure-label
  accuracy as a robust credit-routing measure.
- Add human or secondary labels before using recovery labels as broader
  empirical support for H4.
