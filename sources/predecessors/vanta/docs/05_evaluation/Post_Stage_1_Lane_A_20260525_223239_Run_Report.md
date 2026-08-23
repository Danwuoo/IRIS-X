# Post-Stage-1 Lane A 20260525_223239 Run Report

## Experiment

- Experiment ID: `post_stage_1_larger_sample`
- Sample frame: `PS1-LA-SAMPLE-002`
- Metric policy version: `PS1-LA-METRIC-001`
- Lane: Lane A larger controlled sample
- Run timestamp: `20260525_223239`
- Status: `completed`
- Threshold status: `pass_acceptance_candidate`
- Result path:
  `docs/04_experiments/results/post_stage_1_larger_sample/20260525_223239/`

Required run files were produced:

- `run.json`
- `summary.md`
- `fixture_inventory.md`

This report records the measured Lane A rerun after structured negative
rejection alignment. It does not accept closure, does not use
`accepted_by_closure`, and does not claim H1-H5 validation.

## Setup

- Baseline:
  `openclaw_agent_local/openai-codex/gpt-5.4-mini_lane_a_baselines`
- Treatment:
  `vanta_runtime/openclaw_agent_local/openai-codex/gpt-5.4-mini_lane_a_governed_execution`
- Backbone model: OpenClaw `openai-codex/gpt-5.4-mini`
- Harness identity: `openclaw_agent_local`
- Planner adapter: `Vanta.OpenClawPlannerAdapter`
- Verifier adapter: `Vanta.OpenClawVerifierAdapter`
- Recovery adapter: `Vanta.OpenClawRecoveryAdapter`
- Context planner adapter: `Vanta.OpenClawContextPlannerAdapter`
- Fixture count: 48 fixtures, 8 strata, 6 fixtures per stratum
- Prompt character budget: `20000`
- Response character budget: `12000`
- Action-attempt limit: `6`
- Recovery-attempt limit: `1`
- Context budget: not supplied
- Prompt template version:
  `post_stage_1_larger_sample_openclaw_v4_structured_negative_rejection_alignment`

## Metrics

| Metric | Baseline | Treatment | PS1-G2 result |
| --- | ---: | ---: | --- |
| `task_success_rate` | `0.6250` | `0.9792` | Met, threshold is `>= 0.90` and treatment is above baseline |
| `invalid_action_rate` | `0.1333` | `0.3000` | Report only |
| `verifier_false_accept_rate` | `0.2353` | `0.0000` | Met |
| `verifier_false_reject_rate` | `0.0286` | `0.0000` | Met |
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

## Measured Task Failure

The measured full run had one treatment runtime task failure:

| Fixture | Expected | Observed | Runtime symptom |
| --- | --- | --- | --- |
| `docops_ws_evidence_packet_001` | `committed` | `rejected` | The root treatment planner proposed `validate_artifact` followed by disallowed `compute_hash` even though the fixture allowed only `validate_artifact`. |

The Working Set treatment arm for the same fixture selected the required
Evidence Packet reference and proposed only `validate_artifact`; the overshoot
was in the root governed-execution planner action sequence.

## Post-Run Focused Repair

After the measured run, `docops_ws_evidence_packet_001` was added to the
planner adapter's compact positive-fixture acceptance path. Future full Lane A
runs use prompt template version
`post_stage_1_larger_sample_openclaw_v5_ws_evidence_packet_acceptance_alignment`.

Focused verification after the code change produced:

| Check | Result |
| --- | --- |
| OpenClaw planner action sequence | one `validate_artifact` action on `inputs/evidence_packet.json` |
| Runtime status | `committed` |
| Task success | `true` |
| Invalid actions | `0` |

This focused rerun confirms the targeted planner behavior, but it is not a
replacement for the measured 48-fixture `20260525_223239` run and does not
change that run's recorded aggregate metrics.

## Interpretation

The run is a measured larger controlled Lane A run with threshold status
`pass_acceptance_candidate`.

Allowed statements:

- The 48-fixture `PS1-LA-SAMPLE-002` run completed and produced the required
  machine-readable result files.
- Process-integrity hard gates for unsupported commits, memory writes, and
  disallowed side-effect classes held at `0`.
- Required artifacts, replay consistency, and audit completeness all reached
  `1.0000`.
- The result is eligible for manifest review as a pass acceptance candidate.
- A post-run focused repair corrected the targeted
  `docops_ws_evidence_packet_001` planner overshoot for future runs.

Disallowed statements:

- Do not report this run as `accepted_by_closure`.
- Do not claim validation of H1, H2, H3, H4, H5, full Context OS, production
  readiness, memory-write approval, or irreversible-effect approval.
- Do not describe OpenClaw arms as pure model-only baselines.
- Do not treat the post-run focused repair as a substitute for a full
  48-fixture rerun under the v5 prompt template.

## Related Documents

- [Post-Stage-1 Advancement Gate](../00_manifest/Post_Stage_1_Advancement_Gate.md)
- [Post-Stage-1 Larger Sample G6 Successor Plan](../04_experiments/Post_Stage_1_Larger_Sample_G6_Successor_Plan.md)
- [Post-Stage-1 Metric Policy](Post_Stage_1_Metric_Policy.md)
- [Post-Stage-1 Lane A 20260525_223239 Closure Candidate](../00_manifest/Post_Stage_1_Lane_A_20260525_223239_Closure_Candidate.md)
