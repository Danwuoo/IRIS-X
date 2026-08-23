# Stage 1 Experiment 003 Closure

## Purpose

Close the Phase 3 local smoke work for Experiment 003 without claiming broad
validation of H5.

## Closure Status

- Status: `Closed: local smoke completed`
- Closure date: 2026-05-04
- Closed scope: Phase 3 journal audit and replay local smoke for Experiment 003
- Result path: `docs/04_experiments/results/experiment_003/20260504_215304/`
- Fixture count: seven Document Ops fixtures
- Baseline: `tool_trace_only_direct_execution`
- Treatment: `stage1_episode_journal_replay_runtime`

## Gate Result

The `20260504_215304` run is the Phase 3 local smoke closure. It records that
the current Episode Journal and ReplayRunner pipeline produced audit-complete,
replay-consistent treatment results on the seven local Document Ops fixtures.

| Gate item | Required | Observed | Status |
| --- | --- | --- | --- |
| Treatment `commit_integrity_score` | `1.0` | `1.0` | Met |
| Treatment `replay_consistency` | `1.0` | `1.0` | Met |
| Treatment `audit_completeness` | `1.0` | `1.0` | Met |
| Unsupported treatment commits | `0` | `0` | Met |

## Metrics Summary

| Metric | Baseline | Treatment |
| --- | --- | --- |
| `commit_integrity_score` | `0.0` | `1.0` |
| `replay_consistency` | `0.0` | `1.0` |
| `audit_completeness` | `0.0` | `1.0` |
| `invalid_action_rate` | `0.42857142857142855` | `0.42857142857142855` |

## Interpretation Boundaries

- This closes the Phase 3 local smoke journal and replay step only.
- This is not broad validation of H5.
- The valid reportable claim is limited to: the current Episode Journal and
  ReplayRunner pipeline produced audit-complete, replay-consistent treatment
  results on the seven local Document Ops fixtures.
- The baseline records tool traces and final outputs without Episode Journal,
  Evidence Packet, Verifier Output, or ReplayRunner artifacts; its audit and
  replay metrics are therefore zero by experiment definition.
- Human or secondary audit labels, larger Document Ops samples, and statistical
  support remain deferred.

## Deferred Work

- Expand the Document Ops fixture set beyond the current seven fixtures.
- Add multi-step, compensable, rollback-failure, and audit-gap cases.
- Add human or secondary audit labels before treating audit completeness as a
  broader reviewability measure.
- Revisit commit integrity thresholds when multi-step and compensable action
  fixtures are added.
- Phase 4 Targeted Recovery is tracked separately by
  [Stage 1 Experiment 004 Closure](Stage_1_Experiment_004_Closure.md).

## Related Documents

- [Experiment 003: Commit Journal](../04_experiments/Experiment_003_Commit_Journal.md)
- [Experiment 003 Local Run Report](../05_evaluation/Experiment_003_Local_Run_Report.md)
- [Metrics Definition](../05_evaluation/Metrics_Definition.md)
