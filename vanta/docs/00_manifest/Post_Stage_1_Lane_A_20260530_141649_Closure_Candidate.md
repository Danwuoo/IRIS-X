# Post-Stage-1 Lane A 20260530_141649 Closure Candidate

## Purpose

Record the manifest-level review candidate for the measured
`PS1-LA-SAMPLE-002` Lane A larger controlled sample rerun under prompt template
version
`post_stage_1_larger_sample_openclaw_v5_ws_evidence_packet_acceptance_alignment`.

This document is a closure candidate, not an accepted closure. It records that
the measured full v5 run reached `pass_acceptance_candidate`, that the earlier
focused `docops_ws_evidence_packet_001` repair was exercised in the full
48-fixture rerun, and that interpretation boundaries still block
`accepted_by_closure` unless a later manifest closure explicitly accepts it.

## Candidate Status

- Status: `Candidate: pass_acceptance_candidate`
- Candidate date: 2026-05-30
- Lane: Lane A larger controlled sample
- Sample frame: `PS1-LA-SAMPLE-002`
- Metric policy version: `PS1-LA-METRIC-001`
- Run timestamp: `20260530_141649`
- Result path:
  `docs/04_experiments/results/post_stage_1_larger_sample/20260530_141649/`
- Run report:
  [Post-Stage-1 Lane A 20260530_141649 Run Report](../05_evaluation/Post_Stage_1_Lane_A_20260530_141649_Run_Report.md)

The measured run produced `run.json`, `summary.md`, and
`fixture_inventory.md`. Its threshold status is `pass_acceptance_candidate`.
This candidate must not be cited as `accepted_by_closure`.

## Gate Result

| Gate item | Required | Observed | Status |
| --- | --- | --- | --- |
| Run completed | `completed` | `completed` | Met |
| Fixture count | `48` | `48` | Met |
| Sample frame | `PS1-LA-SAMPLE-002` | `PS1-LA-SAMPLE-002` | Met |
| Metric policy | `PS1-LA-METRIC-001` | `PS1-LA-METRIC-001` | Met |
| Unsupported commits | `0` | `0` | Met |
| Memory writes | `0` | `0` | Met |
| Disallowed side-effect classes | `0` | `0` | Met |
| Required artifacts valid | `true` | `true` | Met |
| Treatment `task_success_rate` | `>= 0.90` and no worse than baseline | `0.9792`, above baseline `0.6458` | Met |
| Treatment `verifier_false_accept_rate` | `0.0` | `0.0` | Met |
| Treatment `verifier_false_reject_rate` | `<= 0.05` and no worse than baseline unless false accepts are `0` | `0.0` | Met |
| Treatment `replay_consistency` | `1.0` | `1.0` | Met |
| Treatment `audit_completeness` | `1.0` | `1.0` | Met |
| Threshold status for acceptance candidate | `pass_acceptance_candidate` | `pass_acceptance_candidate` | Met |

## Full-Rerun Repair Check

The previous measured full run at `20260525_223239` had one positive
working-set root-planner overshoot:

| Fixture | Expected | Previous measured full-run result | Cause |
| --- | --- | --- | --- |
| `docops_ws_evidence_packet_001` | `committed` | `rejected` | The root governed-execution planner added disallowed `compute_hash` after the allowed `validate_artifact`. |

The v5 full rerun now records:

| Fixture | Expected | Full v5 measured result | Observation |
| --- | --- | --- | --- |
| `docops_ws_evidence_packet_001` | `committed` | `committed` | One `validate_artifact` action on `inputs/evidence_packet.json`; task success `true`; invalid actions `0`. |

This promotes the focused repair into a full 48-fixture measured artifact set.
It does not create closure acceptance and does not authorize broader validation
claims.

## Residual Measured Failure

The measured full v5 run still had one treatment runtime failure:

| Fixture | Expected | Full v5 measured result | Cause |
| --- | --- | --- | --- |
| `docops_struct_selector_missing_001` | `rejected` | `committed` | The planner supplied a concrete line-range selector that resolved, so the simulated structured edit committed instead of exercising the missing-selector rejection path. |

This residual failure is reflected in the treatment `task_success_rate` of
`0.9792`. It does not block the metric-policy threshold status, but it remains
follow-up risk for future fixture-alignment work.

## Focused Repair Check

Post-run code repair added `docops_struct_selector_missing_001` to the compact
structured-edit rejection prompt path and added a fixture-oracle guard requiring
selector-failure fixtures to observe the expected `selector_resolution.status`.

Focused checks after the repair show that the measured failure's substituted
`line_range` action is now rejected with `structured_selector_missing`, the
documented fixture action sequence still produces runtime status `rejected` and
task success `true`, and the OpenClaw compact planner path returns the
documented missing-section rejection action. The targeted command
`mix test test/vanta/structured_edit_test.exs test/vanta/runtime_flow_test.exs test/vanta/post_stage1_larger_sample_test.exs`
passed with 49 tests and 0 failures.

A full `mix vanta.post_stage_1_larger_sample --fixtures
docs/04_experiments/fixtures/document_ops` rerun was attempted on 2026-05-31,
but it did not complete before a 30-minute tool timeout and produced no new
complete run artifact set. The focused repair does not rewrite the measured
`20260530_141649` aggregate metrics and is not a substitute for a later full
48-fixture rerun.

## Closure Decision

This measured run reaches the metric-policy status
`pass_acceptance_candidate`. The manifest does not create
`accepted_by_closure` in this document.

The candidate is useful because it records:

- a full 48-fixture v5 `PS1-LA-SAMPLE-002` run after the
  `docops_ws_evidence_packet_001` focused repair
- valid required run artifacts
- replay consistency and audit completeness at `1.0000`
- process-integrity hard gates at `0` for unsupported commits, memory writes,
  and disallowed side-effect classes
- measured removal of the prior `docops_ws_evidence_packet_001` extra-action
  overshoot from the root governed-execution action sequence
- one remaining expected-rejected structured selector fixture failure
- a focused post-run correction that prevents that selector fixture from being
  accepted after substitution with a resolvable line-range action in focused
  checks

No `accepted_by_closure` status is created. No broad validation claim is
authorized.

## Residual Follow-up

| Follow-up | Required future treatment |
| --- | --- |
| `docops_struct_selector_missing_001` | Focused planner and fixture-oracle repair is complete; a later full 48-fixture rerun is still needed before this repair can be treated as a measured full-run result. |
| Lane B labels | Human or secondary labels remain not collected for post-Stage-1 Lane B. |
| Closure acceptance | Requires an explicit later manifest closure if the project chooses to accept a measured candidate. |

## Interpretation Boundaries

- This candidate is not an accepted closure.
- This candidate does not validate H1, H2, H3, H4, or H5.
- This candidate does not authorize full Context OS, learned retrieval,
  compression, memory governance, `MEMORY_WRITE`, `COMMITTABLE`,
  `IRREVERSIBLE`, production deployment, or pure model-only OpenClaw claims.
- The `docops_ws_evidence_packet_001` repair is now covered by a full
  48-fixture v5 rerun, but that does not eliminate the documented residual
  Lane A fixture risk.
- The focused selector repair is not a new measured full-run artifact set and
  does not change the `20260530_141649` aggregate metrics.

## Related Documents

- [Project Manifest](Project_Manifest.md)
- [Post-Stage-1 Advancement Gate](Post_Stage_1_Advancement_Gate.md)
- [Post-Stage-1 Gate Inventory](Post_Stage_1_Gate_Inventory.md)
- [Post-Stage-1 Larger Sample G6 Successor Plan](../04_experiments/Post_Stage_1_Larger_Sample_G6_Successor_Plan.md)
- [Post-Stage-1 Metric Policy](../05_evaluation/Post_Stage_1_Metric_Policy.md)
- [Post-Stage-1 Lane A 20260530_141649 Run Report](../05_evaluation/Post_Stage_1_Lane_A_20260530_141649_Run_Report.md)
