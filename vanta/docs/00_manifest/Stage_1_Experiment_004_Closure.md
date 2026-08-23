# Stage 1 Experiment 004 Closure

## Purpose

Close the Phase 4 local smoke work for Experiment 004 without claiming broad
validation of H4.

## Closure Status

- Status: `Closed: local smoke completed`
- Closure date: 2026-05-06
- Closed scope: Phase 4 targeted recovery local smoke for Experiment 004
- Result path: `docs/04_experiments/results/experiment_004/20260506_231941/`
- Fixture count: three controlled Document Ops recovery fixtures
- Baseline:
  `blind_retry_openclaw_agent_local/openai-codex/gpt-5.4-mini_matched_budget`
- Treatment:
  `targeted_recovery_openclaw_agent_local/openai-codex/gpt-5.4-mini_matched_budget`

## Gate Result

The `20260506_231941` run is the Phase 4 local smoke closure. It records that
the current OpenClaw recovery adapter plus allowlisted fixture-local recovery
policies recovered all three controlled Document Ops recovery fixtures under
matched local compute, while the blind-retry baseline recovered none.

| Gate item | Required | Observed | Status |
| --- | --- | --- | --- |
| Compute matching preserved | `true` | `true` | Met |
| Targeted `recovery_success_rate` | `1.0` | `1.0` | Met |
| Targeted `targeted_recovery_success` | `1.0` | `1.0` | Met |
| Targeted `failure_label_accuracy` | `1.0` | `1.0` | Met |
| Targeted `repeated_failure_rate` | `0.0` | `0.0` | Met |

## Metrics Summary

| Metric | Blind Retry | Targeted Recovery |
| --- | --- | --- |
| `recovery_success_rate` | `0.0` | `1.0` |
| `targeted_recovery_success` | `0.0` | `1.0` |
| `failure_label_accuracy` | `0.0` | `1.0` |
| `repeated_failure_rate` | `1.0` | `0.0` |
| `rollback_recovery_success` | `0.0` | `1.0` |
| `audit_gap_closure_rate` | `0.0` | `1.0` |
| `compensation_policy_accuracy` | `0.0` | `1.0` |

## Interpretation Boundaries

- This closes the Phase 4 local smoke targeted-recovery step only.
- This is not broad validation of H4.
- The valid reportable claim is limited to: the current OpenClaw recovery
  adapter and allowlisted fixture-local recovery policies selected the expected
  recovery policy and repaired all three controlled Document Ops recovery
  fixtures under matched local compute.
- The OpenClaw call path includes the local harness and must not be described as
  a pure model-only recovery result.
- Fixture oracle labels and expected recovery policies are scoring references;
  treatment must use the OpenClaw Recovery Decision.
- Larger samples, ambiguous failure classes, human labels, and statistical
  support remain deferred.

## Deferred Work

- Expand Document Ops recovery fixtures beyond rollback failure, audit gap, and
  compensable-action cases.
- Add ambiguous or multi-label failures to test whether recovery classification
  remains useful when fixture oracles are less direct.
- Add human or secondary labels before treating `failure_label_accuracy` as a
  broader credit-routing measure.
- Add a direct Responses recovery arm if a pure model-only comparison is needed.
- Keep Context OS / Working Set Compiler work deferred to Phase 5.

## Related Documents

- [Experiment 004: Targeted Recovery](../04_experiments/Experiment_004_Targeted_Recovery.md)
- [Experiment 004 Local Run Report](../05_evaluation/Experiment_004_Local_Run_Report.md)
- [Metrics Definition](../05_evaluation/Metrics_Definition.md)
