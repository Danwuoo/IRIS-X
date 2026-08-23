# Post-Stage-1 Lane A 20260601_113121 Closure

## Purpose

Accept the measured `PS1-LA-SAMPLE-002` Lane A larger controlled Document Ops
run at `20260601_113121` as the first threshold-governed Lane A closure.

This closure accepts a named larger controlled sample result under
`PS1-LA-METRIC-001`. It does not validate H1 through H5, approve full Context
OS, approve production deployment, authorize memory writes, authorize
irreversible effects, or promote OpenClaw local harness arms to pure model-only
baselines.

## Closure Status

- Status: `accepted_by_closure`
- Closure date: 2026-06-01
- Lane: Lane A larger controlled sample
- Sample frame: `PS1-LA-SAMPLE-002`
- Metric policy version: `PS1-LA-METRIC-001`
- Run timestamp: `20260601_113121`
- Result path:
  `docs/04_experiments/results/post_stage_1_larger_sample/20260601_113121/`
- Run report:
  [Post-Stage-1 Lane A 20260601_113121 Run Report](../05_evaluation/Post_Stage_1_Lane_A_20260601_113121_Run_Report.md)

The measured run produced `run.json`, `summary.md`, and
`fixture_inventory.md`. Its runner threshold status is
`pass_acceptance_candidate`; this manifest closure accepts that candidate as
`accepted_by_closure`.

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
| Treatment `task_success_rate` | `>= 0.90` and no worse than baseline | `1.0000`, above baseline `0.6458` | Met |
| Treatment `verifier_false_accept_rate` | `0.0` | `0.0` | Met |
| Treatment `verifier_false_reject_rate` | `<= 0.05` and no worse than baseline unless false accepts are `0` | `0.0` | Met |
| Treatment `evidence_sufficiency_score` | `>= 0.95` | `1.0000` | Met |
| Treatment `commit_integrity_score` | `1.0` | `1.0` | Met |
| Treatment `replay_consistency` | `1.0` | `1.0` | Met |
| Treatment `audit_completeness` | `1.0` | `1.0` | Met |
| Conditional recovery thresholds | Pass when recovery fixtures are included | All recovery metrics met | Met |
| Conditional working-set thresholds | Pass when long-context fixtures are included | All working-set metrics met | Met |
| Closure decision | Manifest closure required | `accepted_by_closure` | Met |

## Selector Repair Closure Check

The previous full v5 measured run at `20260530_141649` had one residual
expected-rejected structured selector failure:

| Fixture | Expected | Previous measured result | Cause |
| --- | --- | --- | --- |
| `docops_struct_selector_missing_001` | `rejected` | `committed` | The planner supplied a concrete line-range selector that resolved. |

The `20260601_113121` rerun records the repaired behavior:

| Fixture | Expected | Accepted measured result | Observation |
| --- | --- | --- | --- |
| `docops_struct_selector_missing_001` | `rejected` | `rejected` | The planner used the documented missing `section` selector; `selector_resolution.status` was `missing`; verifier decision was `reject`; task success was `true`. |

This closes the previously documented Lane A residual fixture risk for the
accepted sample frame.

## Accepted Claim

The accepted claim is narrow:

- `PS1-LA-SAMPLE-002` has one threshold-governed larger controlled Document Ops
  Lane A result accepted by manifest closure.
- The accepted run is `20260601_113121`.
- The acceptance is harness-labeled:
  `openclaw_agent_local/openai-codex/gpt-5.4-mini`.
- The accepted comparison is between the documented OpenClaw local harness
  baseline arm and the governed Vanta runtime treatment arm.

## Non-Claims

This closure does not claim:

- validation of H1, H2, H3, H4, or H5
- full Context OS validation
- learned retrieval, learned ranking, or learned compression approval
- memory governance or `MEMORY_WRITE` approval
- `COMMITTABLE` or `IRREVERSIBLE` runtime execution approval
- production readiness
- pure model-only OpenClaw baseline status
- human-labeled broader evaluation evidence

## Follow-up

| Follow-up | Status |
| --- | --- |
| Lane B labels | 2026-06-01 closure-time status: no Lane B labels were accepted by this closure. Post-closure routing now uses the companion Lane B report, whose first primary batch is `complete_reported`; no broader label claim is created by this closure. |
| Context OS planning | Existing `PS1-G7` planning artifacts may cite the accepted Lane A run as a threshold-governed Document Ops closure, but not as H3 or full Context OS validation. |
| Side-effect escalation | `PS1-G8` remains planning-only; no runtime side-effect class expansion is authorized. |

## Related Documents

- [Project Manifest](Project_Manifest.md)
- [Post-Stage-1 Advancement Gate](Post_Stage_1_Advancement_Gate.md)
- [Post-Stage-1 Gate Inventory](Post_Stage_1_Gate_Inventory.md)
- [Post-Stage-1 Larger Sample G6 Successor Plan](../04_experiments/Post_Stage_1_Larger_Sample_G6_Successor_Plan.md)
- [Post-Stage-1 Metric Policy](../05_evaluation/Post_Stage_1_Metric_Policy.md)
- [Post-Stage-1 Lane A 20260601_113121 Run Report](../05_evaluation/Post_Stage_1_Lane_A_20260601_113121_Run_Report.md)
