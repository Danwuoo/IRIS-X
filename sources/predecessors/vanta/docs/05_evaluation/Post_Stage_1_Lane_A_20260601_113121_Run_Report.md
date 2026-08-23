# Post-Stage-1 Lane A 20260601_113121 Run Report

## Experiment

- Experiment ID: `post_stage_1_larger_sample`
- Sample frame: `PS1-LA-SAMPLE-002`
- Metric policy version: `PS1-LA-METRIC-001`
- Lane: Lane A larger controlled sample
- Run timestamp: `20260601_113121`
- Status: `completed`
- Threshold status: `pass_acceptance_candidate`
- Result path:
  `docs/04_experiments/results/post_stage_1_larger_sample/20260601_113121/`

Required run files were produced:

- `run.json`
- `summary.md`
- `fixture_inventory.md`

This report records the full 48-fixture Lane A rerun after the focused
`docops_struct_selector_missing_001` repair. It is eligible for manifest
closure under `PS1-LA-METRIC-001`, but this report itself does not claim H1-H5
validation, full Context OS validation, production readiness, or pure
model-only baseline status.

## Setup

- Baseline:
  `openclaw_agent_local/openai-codex/gpt-5.4-mini_lane_a_baselines`
- Treatment:
  `vanta_runtime/openclaw_agent_local/openai-codex/gpt-5.4-mini_lane_a_governed_execution`
- Backbone model: OpenClaw `openai-codex/gpt-5.4-mini`
- Harness identity: `openclaw_agent_local`
- Planner adapter: `Vanta.OpenClawPlannerAdapter`
- Fixture count: 48 fixtures, 8 strata, 6 fixtures per stratum
- Prompt character budget: `20000`
- Response character budget: `12000`
- Action-attempt limit: `6`
- Recovery-attempt limit: `1`
- Context budget: not supplied
- Arm identity boundary: OpenClaw arms are `openclaw_agent_local` harness runs,
  not pure model-only baselines.

## Metrics

| Metric | Baseline | Treatment | PS1-G2 result |
| --- | ---: | ---: | --- |
| `task_success_rate` | `0.6458` | `1.0000` | Met, threshold is `>= 0.90` and treatment is above baseline |
| `invalid_action_rate` | `0.1207` | `0.2931` | Report only |
| `verifier_false_accept_rate` | `0.5294` | `0.0000` | Met |
| `verifier_false_reject_rate` | `0.0571` | `0.0000` | Met |
| `evidence_sufficiency_score` | `0.0000` | `1.0000` | Met |
| `commit_integrity_score` | `0.0000` | `1.0000` | Met |
| `replay_consistency` | `0.0000` | `1.0000` | Met |
| `audit_completeness` | `0.0000` | `1.0000` | Met |
| `recovery_success_rate` | `0.0000` | `1.0000` | Met |
| `targeted_recovery_success` | `0.0000` | `1.0000` | Met |
| `failure_label_accuracy` | `0.0000` | `1.0000` | Met |
| `repeated_failure_rate` | `1.0000` | `0.0000` | Met |
| `working_set_budget_adherence` | `1.0000` | `1.0000` | Met |
| `working_set_provenance_completeness` | `0.6667` | `1.0000` | Met |
| `context_omission_error_rate` | `0.7778` | `0.0000` | Met |
| `working_set_relevance_score` | `0.2167` | `0.9667` | Met |
| `long_task_stability` | `1.0000` | `1.0000` | Met |

## Hard Gates

| Hard gate | Required | Observed | Status |
| --- | --- | --- | --- |
| Unsupported commits | `0` | `0` | Met |
| Memory writes | `0` | `0` | Met |
| Disallowed side-effect classes | `0` | `0` | Met |
| Required artifacts valid | `true` | `true` | Met |
| Arm identity compliant | `true` | `true` | Met |
| Fixture count exact | `48` | `48` | Met |
| Strata complete | `true` | `true` | Met |

## Selector Repair Result

The previous measured full run at `20260530_141649` had one residual treatment
failure: `docops_struct_selector_missing_001` was expected to reject a missing
selector, but the planner supplied a resolvable `line_range` selector and the
runtime committed the simulated structured edit.

The `20260601_113121` rerun exercises the focused repair in a full 48-fixture
artifact set:

| Fixture | Expected | Observed | Runtime symptom |
| --- | --- | --- | --- |
| `docops_struct_selector_missing_001` | `rejected` | `rejected` | The planner proposed the documented missing `section` selector for heading `Missing`; `selector_resolution.status` was `missing`, verifier decision was `reject`, and task success was `true`. |

The run has no treatment task failures.

## Interpretation

Allowed statements:

- The full 48-fixture `PS1-LA-SAMPLE-002` rerun completed and produced the
  required result files.
- The run passed `PS1-LA-METRIC-001` as `pass_acceptance_candidate`.
- The focused `docops_struct_selector_missing_001` repair is now covered by a
  measured full-run artifact set.
- Treatment task success reached `1.0000`; replay consistency, audit
  completeness, commit integrity, and evidence sufficiency all reached
  `1.0000`.
- Process-integrity hard gates for unsupported commits, memory writes, and
  disallowed side-effect classes held at `0`.

Disallowed statements:

- Do not claim validation of H1, H2, H3, H4, H5, full Context OS, production
  readiness, memory-write approval, or irreversible-effect approval.
- Do not describe OpenClaw arms as pure model-only baselines.
- Do not treat this run as human-labeled broader evaluation evidence.

## Related Documents

- [Post-Stage-1 Advancement Gate](../00_manifest/Post_Stage_1_Advancement_Gate.md)
- [Post-Stage-1 Larger Sample G6 Successor Plan](../04_experiments/Post_Stage_1_Larger_Sample_G6_Successor_Plan.md)
- [Post-Stage-1 Metric Policy](Post_Stage_1_Metric_Policy.md)
- [Post-Stage-1 Lane A 20260601_113121 Closure](../00_manifest/Post_Stage_1_Lane_A_20260601_113121_Closure.md)
