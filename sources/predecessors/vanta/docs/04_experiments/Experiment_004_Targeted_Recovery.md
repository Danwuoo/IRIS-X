# Experiment 004: Targeted Recovery

## Research Question

Does OpenClaw-backed failure classification plus allowlisted targeted recovery
beat blind retry under matched local compute budgets?

## Hypothesis Tested

H4: Failure credit routing can improve recovery efficiency.

## Baseline

`blind_retry_openclaw_agent_local/<model>_matched_budget`

The baseline repeats the original failing action sequence without failure
labels, credit vectors, or recovery-policy hints. Its budget ledger is matched
to the treatment fixture by fixture.

## Treatment

`targeted_recovery_openclaw_agent_local/<model>_matched_budget`

The treatment runs the failed episode, asks the OpenClaw recovery adapter for a
Recovery Decision, and applies only allowlisted fixture-local recovery policies.

## Matched Compute Rule

Each fixture must use the same:

- OpenClaw model-call count.
- Prompt character ceiling.
- Response character ceiling.
- Recovery action-attempt limit.

Exact token usage is not available from the current OpenClaw harness contract.
The run records estimated token counts from character counts and must label
those counts as estimates.

## Phase 4 Fixture Set

Experiment 004 uses only fixtures with `expected_recovery_policy` metadata:

- `docops_rollback_failure_001`
- `docops_audit_gap_001`
- `docops_compensable_action_001`

These are controlled Document Ops fixtures. No irreversible external action is
executed.

## Metrics

- `recovery_success_rate`
- `targeted_recovery_success`
- `failure_label_accuracy`
- `repeated_failure_rate`
- `recovery_compute_cost`
- `rollback_recovery_success`
- `audit_gap_closure_rate`
- `compensation_policy_accuracy`

## Status

Protocol, mock-run support, and one measured OpenClaw local harness run are
implemented. The measured run at
`docs/04_experiments/results/experiment_004/20260506_231941/` closes Phase 4 as
`Closed: local smoke completed` for the controlled three-fixture Document Ops
recovery set.

Implemented entrypoint:

```powershell
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$out = "docs/04_experiments/results/experiment_004/$timestamp"
mix vanta.experiment004 --out $out
```

Mock tests and fixture execution must not be described as validation of H4.
The measured run must also remain local-smoke scoped; it is not broad validation
of H4.

## Related Documents

- [Ablation Plan](Ablation_Plan.md)
- [Document Ops Benchmark](Document_Ops_Benchmark.md)
- [Stage 1 Experiment 004 Closure](../00_manifest/Stage_1_Experiment_004_Closure.md)
- [Experiment 004 Local Run Report](../05_evaluation/Experiment_004_Local_Run_Report.md)
- [Failure Labeling Guide](../05_evaluation/Failure_Labeling_Guide.md)
- [Metrics Definition](../05_evaluation/Metrics_Definition.md)
