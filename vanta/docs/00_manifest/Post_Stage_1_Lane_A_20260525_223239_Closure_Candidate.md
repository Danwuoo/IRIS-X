# Post-Stage-1 Lane A 20260525_223239 Closure Candidate

## Purpose

Record the manifest-level review candidate for the measured
`PS1-LA-SAMPLE-002` Lane A larger controlled sample rerun after structured
negative rejection alignment, and record the post-run focused repair for the
`docops_ws_evidence_packet_001` planner overshoot.

This document is a closure candidate, not an accepted closure. It records that
the measured run reached `pass_acceptance_candidate` and preserves the
interpretation boundaries that block `accepted_by_closure` unless a later
manifest closure explicitly accepts it.

## Candidate Status

- Status: `Candidate: pass_acceptance_candidate`
- Candidate date: 2026-05-26
- Lane: Lane A larger controlled sample
- Sample frame: `PS1-LA-SAMPLE-002`
- Metric policy version: `PS1-LA-METRIC-001`
- Run timestamp: `20260525_223239`
- Result path:
  `docs/04_experiments/results/post_stage_1_larger_sample/20260525_223239/`
- Run report:
  [Post-Stage-1 Lane A 20260525_223239 Run Report](../05_evaluation/Post_Stage_1_Lane_A_20260525_223239_Run_Report.md)

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
| Treatment `task_success_rate` | `>= 0.90` and no worse than baseline | `0.9792`, above baseline `0.6250` | Met |
| Treatment `verifier_false_accept_rate` | `0.0` | `0.0` | Met |
| Treatment `verifier_false_reject_rate` | `<= 0.05` and no worse than baseline unless false accepts are `0` | `0.0` | Met |
| Treatment `replay_consistency` | `1.0` | `1.0` | Met |
| Treatment `audit_completeness` | `1.0` | `1.0` | Met |
| Threshold status for acceptance candidate | `pass_acceptance_candidate` | `pass_acceptance_candidate` | Met |

## Focused Repair Check

The measured full run still had one treatment runtime failure:

| Fixture | Expected | Measured full-run result | Cause |
| --- | --- | --- | --- |
| `docops_ws_evidence_packet_001` | `committed` | `rejected` | The root governed-execution planner added disallowed `compute_hash` after the allowed `validate_artifact`. |

Post-run code repair added this fixture to the compact positive-fixture
acceptance path and increments future Lane A prompt-template reporting to
`post_stage_1_larger_sample_openclaw_v5_ws_evidence_packet_acceptance_alignment`.

Focused rerun after the repair produced one `validate_artifact` action, runtime
status `committed`, task success `true`, and `0` invalid actions. This confirms
the targeted repair, but it does not rewrite the measured `20260525_223239`
aggregate metrics and is not a substitute for a full 48-fixture v5 rerun.

## Closure Decision

This measured run reaches the metric-policy status
`pass_acceptance_candidate`. The manifest does not create
`accepted_by_closure` in this document.

The candidate is useful because it records:

- a second measured threshold-passing `PS1-LA-SAMPLE-002` run
- valid required run artifacts
- replay consistency and audit completeness at `1.0000`
- process-integrity hard gates at `0` for unsupported commits, memory writes,
  and disallowed side-effect classes
- a focused post-run correction for the one positive working-set fixture where
  the root planner proposed an extra disallowed action

No `accepted_by_closure` status is created. No broad validation claim is
authorized.

## Residual Follow-up

| Follow-up | Required future treatment |
| --- | --- |
| Full v5 Lane A rerun | Needed only if the project wants a 48-fixture measured artifact set whose root governed-execution action sequence no longer contains the `docops_ws_evidence_packet_001` overshoot. |
| Lane B labels | Human or secondary labels remain not collected for post-Stage-1 Lane B. |
| Closure acceptance | Requires an explicit later manifest closure if the project chooses to accept a measured candidate. |

## Interpretation Boundaries

- This candidate is not an accepted closure.
- This candidate does not validate H1, H2, H3, H4, or H5.
- This candidate does not authorize full Context OS, learned retrieval,
  compression, memory governance, `MEMORY_WRITE`, `COMMITTABLE`,
  `IRREVERSIBLE`, production deployment, or pure model-only OpenClaw claims.
- The focused repair confirms a targeted planner behavior only; it does not
  create a new full-run measured result.

## Related Documents

- [Project Manifest](Project_Manifest.md)
- [Post-Stage-1 Advancement Gate](Post_Stage_1_Advancement_Gate.md)
- [Post-Stage-1 Gate Inventory](Post_Stage_1_Gate_Inventory.md)
- [Post-Stage-1 Larger Sample G6 Successor Plan](../04_experiments/Post_Stage_1_Larger_Sample_G6_Successor_Plan.md)
- [Post-Stage-1 Metric Policy](../05_evaluation/Post_Stage_1_Metric_Policy.md)
- [Post-Stage-1 Lane A 20260525_223239 Run Report](../05_evaluation/Post_Stage_1_Lane_A_20260525_223239_Run_Report.md)
