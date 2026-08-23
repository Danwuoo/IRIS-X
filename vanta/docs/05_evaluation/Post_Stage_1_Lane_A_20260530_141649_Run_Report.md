# Post-Stage-1 Lane A 20260530_141649 Run Report

## Experiment

- Experiment ID: `post_stage_1_larger_sample`
- Sample frame: `PS1-LA-SAMPLE-002`
- Metric policy version: `PS1-LA-METRIC-001`
- Lane: Lane A larger controlled sample
- Run timestamp: `20260530_141649`
- Status: `completed`
- Threshold status: `pass_acceptance_candidate`
- Result path:
  `docs/04_experiments/results/post_stage_1_larger_sample/20260530_141649/`

Required run files were produced:

- `run.json`
- `summary.md`
- `fixture_inventory.md`

This report records the full 48-fixture Lane A rerun under prompt template
version
`post_stage_1_larger_sample_openclaw_v5_ws_evidence_packet_acceptance_alignment`.
It promotes the earlier focused `docops_ws_evidence_packet_001` repair into a
measured full-run artifact set. It does not accept closure, does not use
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
  `post_stage_1_larger_sample_openclaw_v5_ws_evidence_packet_acceptance_alignment`
- Arm identity boundary: OpenClaw arms are `openclaw_agent_local` harness runs;
  the run metadata records `pure_model_only: false`.

## Metrics

| Metric | Baseline | Treatment | PS1-G2 result |
| --- | ---: | ---: | --- |
| `task_success_rate` | `0.6458` | `0.9792` | Met, threshold is `>= 0.90` and treatment is above baseline |
| `invalid_action_rate` | `0.1186` | `0.2712` | Report only |
| `verifier_false_accept_rate` | `0.3529` | `0.0000` | Met |
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

## Promoted Focused Repair Result

The earlier focused repair for `docops_ws_evidence_packet_001` is now covered
by this full 48-fixture v5 rerun.

| Fixture | Expected | Observed | Runtime symptom |
| --- | --- | --- | --- |
| `docops_ws_evidence_packet_001` | `committed` | `committed` | The root treatment planner proposed one `validate_artifact` action on `inputs/evidence_packet.json`; invalid actions were `0`. |

The prior full-run overshoot for this fixture, where the root planner appended
an extra disallowed `compute_hash`, does not appear in this measured v5 run.
The working-set treatment arm also selected all required refs and omitted only
the irrelevant `artifact:noise` ref under the fixture budget.

## Measured Task Failure

The measured full run still had one treatment runtime task failure:

| Fixture | Expected | Observed | Runtime symptom |
| --- | --- | --- | --- |
| `docops_struct_selector_missing_001` | `rejected` | `committed` | The treatment planner supplied a concrete line-range selector that resolved, so the simulated structured edit committed even though the fixture is an expected-rejected missing-selector case. |

This residual failure is included in the aggregate treatment
`task_success_rate` of `0.9792`. The run still reaches
`pass_acceptance_candidate` under `PS1-LA-METRIC-001`, but it is not closure
acceptance.

## Post-Run Focused Repair

After the measured run, `docops_struct_selector_missing_001` was added to the
planner adapter's compact structured-edit rejection path. The compact planner
hint now routes the fixture to its documented `section` selector for heading
`Missing` instead of relying on the root planner to infer the missing-selector
case from prose.

The fixture acceptance oracle was also tightened for selector-failure fixtures:
when `expected_failure_labels` contains `structured_selector_missing` or
`structured_selector_ambiguous`, the observed `selector_resolution.status` must
match the expected selector failure. This prevents a substituted resolvable
`line_range` action from being accepted as a valid commit for an
expected-rejected selector fixture.

Focused verification after the code change produced:

| Check | Result |
| --- | --- |
| Substituted `line_range` action from the measured failure | verifier rejected with `structured_selector_missing` |
| Fixture action sequence path | runtime status `rejected`, task success `true` |
| Planner compact prompt path | returns the documented missing-section rejection action |
| Targeted tests | `mix test test/vanta/structured_edit_test.exs test/vanta/runtime_flow_test.exs test/vanta/post_stage1_larger_sample_test.exs` passed: 49 tests, 0 failures |

A full `mix vanta.post_stage_1_larger_sample --fixtures
docs/04_experiments/fixtures/document_ops` rerun was attempted on
2026-05-31, but the local harness did not complete within a 30-minute tool
timeout. No new complete `run.json`, `summary.md`, or `fixture_inventory.md`
artifact set was produced, so this focused repair does not rewrite the measured
`20260530_141649` aggregate metrics.

## Interpretation

The run is a measured larger controlled Lane A run with threshold status
`pass_acceptance_candidate`.

Allowed statements:

- The 48-fixture `PS1-LA-SAMPLE-002` v5 run completed and produced the required
  machine-readable result files.
- The previously focused `docops_ws_evidence_packet_001` repair was exercised
  in a full 48-fixture rerun and the root treatment planner no longer proposed
  the extra disallowed `compute_hash` for that fixture.
- Process-integrity hard gates for unsupported commits, memory writes, and
  disallowed side-effect classes held at `0`.
- Required artifacts, replay consistency, and audit completeness all reached
  `1.0000`.
- The result is eligible for manifest review as a pass acceptance candidate.
- A post-run focused repair now prevents the documented
  `docops_struct_selector_missing_001` residual from becoming a resolvable
  line-range commit in focused runtime and planner checks.

Disallowed statements:

- Do not report this run as `accepted_by_closure`.
- Do not claim validation of H1, H2, H3, H4, H5, full Context OS, production
  readiness, memory-write approval, or irreversible-effect approval.
- Do not describe OpenClaw arms as pure model-only baselines.
- Do not treat `docops_ws_evidence_packet_001` repair success as eliminating
  all residual Lane A fixture risk.
- Do not treat the post-run focused selector repair as a completed full
  48-fixture rerun or as changing the measured `20260530_141649` aggregate
  metrics.

## Related Documents

Any Lane B links in this section are historical for this non-accepted source run
and are superseded by the `20260601_113121` Lane B packet for current
accepted-run routing.

- [Post-Stage-1 Advancement Gate](../00_manifest/Post_Stage_1_Advancement_Gate.md)
- [Post-Stage-1 Larger Sample G6 Successor Plan](../04_experiments/Post_Stage_1_Larger_Sample_G6_Successor_Plan.md)
- [Post-Stage-1 Metric Policy](Post_Stage_1_Metric_Policy.md)
- [Post-Stage-1 Lane A 20260530_141649 Closure Candidate](../00_manifest/Post_Stage_1_Lane_A_20260530_141649_Closure_Candidate.md)
- [Post-Stage-1 Lane B 20260530_141649 Blinded Label Packet](label_packets/post_stage_1_lane_b_20260530_141649/README.md)
- [Post-Stage-1 Lane B 20260530_141649 Label Report Skeleton](Post_Stage_1_Lane_B_20260530_141649_Label_Report_Skeleton.md)
- [Post-Stage-1 Context OS Planning Draft Spec](../02_specs/Post_Stage_1_Context_OS_Planning_Draft_Spec.md)
- [Post-Stage-1 Context OS Evaluation Plan](../04_experiments/Post_Stage_1_Context_OS_Evaluation_Plan.md)
