# Stage 1 Experiment 005 Closure

## Purpose

Close the Phase 5 local smoke work for Experiment 005 without claiming broad
validation of H3 or full Context OS.

## Closure Status

- Status: `Closed: local smoke completed`
- Closure date: 2026-05-07
- Closed scope: Phase 5 `Working Set Compiler v0` local smoke
- Result path: `docs/04_experiments/results/experiment_005/20260507_105950/`
- Fixture count: five controlled Document Ops long-context fixtures
- Baseline:
  `raw_trace_bounded_openclaw_agent_local/openai-codex/gpt-5.4-mini_matched_budget`
- Treatment:
  `working_set_compiler_v0_reference_backed_openclaw_agent_local/openai-codex/gpt-5.4-mini_matched_budget`

## Gate Result

The `20260507_105950` run is the Phase 5 local smoke closure. It records that
the current reference-backed `Working Set Compiler v0` produced schema-valid,
budget-adherent, provenance-complete working sets on the five controlled
Document Ops long-context fixtures. The bounded raw-trace baseline omitted
fixture-required refs under the same configured prompt and response ceilings.

| Gate item | Required | Observed | Status |
| --- | --- | --- | --- |
| OpenClaw configured and run completed | `completed` | `completed` | Met |
| Fixture count | `5` | `5` | Met |
| Treatment schema-valid `WorkingSet` artifacts | `true` | `true` | Met |
| Treatment `working_set_budget_adherence` | `1.0` | `1.0` | Met |
| Treatment `working_set_provenance_completeness` | `1.0` | `1.0` | Met |
| Treatment omission lower than baseline | `true` | `0.0 < 0.9333333333333332` | Met |
| Treatment relevance higher than baseline | `true` | `1.0 > 0.1` | Met |
| Treatment stability at least baseline | `true` | `1.0 >= 1.0` | Met |
| Unsupported commits | `0` | `0` | Met |
| Memory writes | `0` | `0` | Met |

## Metrics Summary

| Metric | Raw Trace Baseline | Working Set Treatment |
| --- | --- | --- |
| `working_set_budget_adherence` | `1.0` | `1.0` |
| `working_set_provenance_completeness` | `0.6` | `1.0` |
| `context_omission_error_rate` | `0.9333333333333332` | `0.0` |
| `working_set_relevance_score` | `0.1` | `1.0` |
| `long_task_stability` | `1.0` | `1.0` |
| `task_success_rate` | `1.0` | `1.0` |
| `unsupported_commits` | `0` | `0` |
| `memory_writes` | `0` | `0` |

## Interpretation Boundaries

- This closes the Phase 5 local smoke `Working Set Compiler v0` step only.
- This is not broad validation of H3.
- This is not validation or implementation of full Context OS.
- The valid reportable claim is limited to: the current deterministic,
  reference-backed compiler produced schema-valid, budget-adherent,
  provenance-complete working sets that reduced fixture-required context
  omission compared with bounded raw trace on five controlled Document Ops
  fixtures.
- The OpenClaw call path includes the local harness and `vanta-verifier` agent,
  so it must not be described as pure model-only context planning.
- Fixture required/relevant/irrelevant refs are deterministic scoring metadata;
  broader evaluation still needs larger samples and human or secondary labels.

## Deferred Work

- Expand Document Ops long-context fixtures beyond the five controlled smoke
  cases.
- Add human or secondary labels for omission and relevance.
- Compare against additional context strategies after the v0 compiler is stable.
- Keep full Context OS, long-term memory governance, learned retrieval,
  compression, and memory writes out of scope until separately specified.

## Related Documents

- [Phase 5 Working Set Compiler Gate](Phase_5_Working_Set_Compiler_Gate.md)
- [Experiment 005 Working Set Compiler](../04_experiments/Experiment_005_Working_Set_Compiler.md)
- [Experiment 005 Local Run Report](../05_evaluation/Experiment_005_Local_Run_Report.md)
- [Metrics Definition](../05_evaluation/Metrics_Definition.md)
