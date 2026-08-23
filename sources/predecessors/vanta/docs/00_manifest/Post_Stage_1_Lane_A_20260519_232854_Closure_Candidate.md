# Post-Stage-1 Lane A 20260519_232854 Closure Candidate

## Purpose

Record the manifest-level review candidate for the first measured
`PS1-LA-SAMPLE-002` Lane A larger controlled sample run.

This document is a closure candidate, not an accepted closure. It records why
the measured run is not accepted and routes the next fix batch.

## Candidate Status

- Status: `Not accepted: failed_no_acceptance`
- Candidate date: 2026-05-20
- Lane: Lane A larger controlled sample
- Sample frame: `PS1-LA-SAMPLE-002`
- Metric policy version: `PS1-LA-METRIC-001`
- Run timestamp: `20260519_232854`
- Result path:
  `docs/04_experiments/results/post_stage_1_larger_sample/20260519_232854/`
- Run report:
  [Post-Stage-1 Lane A 20260519_232854 Run Report](../05_evaluation/Post_Stage_1_Lane_A_20260519_232854_Run_Report.md)

The run produced `run.json`, `summary.md`, and `fixture_inventory.md`, but its
threshold status is `failed_no_acceptance`. This candidate must not be cited as
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
| Required artifacts valid | `true` | `false` | Failed |
| Treatment `task_success_rate` | `>= 0.90` and no worse than baseline | `1.0`, equal to baseline | Met |
| Treatment `replay_consistency` | `1.0` | `0.9375` | Failed |
| Treatment `audit_completeness` | `1.0` | `0.9167` | Failed |
| Threshold status for acceptance candidate | `pass_acceptance_candidate` | `failed_no_acceptance` | Failed |

## Closure Decision

The manifest does not accept this measured run as a threshold-governed larger
sample acceptance result.

The run remains useful as a measured failure record because it shows:

- the 48-fixture G6-aware sample frame can execute to artifact generation
- unsupported commits, memory writes, and disallowed side-effect classes stayed
  at `0`
- planner and audit/replay blockers still prevent PS1-G2 acceptance

No `accepted_by_closure` status is created. No broad validation claim is
authorized.

## Blocking Fix Batches

| Batch | Blocking point | Required outcome before rerun |
| --- | --- | --- |
| `PS1-LA-FIX-001` | `docops_ps1_reversible_append_section_001` produced a planner action that failed schema validation. | Schema-valid action sequence and runtime governance artifacts for the fixture. |
| `PS1-LA-FIX-002` | `docops_ps1_recovery_audit_gap_complete_refs_001` and `docops_ps1_replay_multistep_structured_commit_001` returned OpenClaw context-overflow text instead of JSON action output. | Planner prompt budget enforcement or prompt reduction that keeps both fixtures JSON-only and schema-valid. |
| `PS1-LA-FIX-003` | `docops_detect_terms_001` committed but missed `evidence_audit` and `verifier_audit`. | Fixture-level and aggregate `audit_completeness` can reach `1.0`. |
| `PS1-LA-FIX-004` | Failed Lane A runs previously aborted before artifacts existed. | Preserve runner regression coverage so failed measured runs continue to emit `run.json`, `summary.md`, and `fixture_inventory.md`. |

## Interpretation Boundaries

- This candidate is not an accepted closure.
- This candidate does not validate H1, H2, H3, H4, or H5.
- This candidate does not authorize full Context OS, learned retrieval,
  compression, memory governance, `MEMORY_WRITE`, `COMMITTABLE`,
  `IRREVERSIBLE`, production deployment, or pure model-only OpenClaw claims.
- Human or secondary labels remain not collected for post-Stage-1 Lane B.

## Related Documents

- [Project Manifest](Project_Manifest.md)
- [Post-Stage-1 Advancement Gate](Post_Stage_1_Advancement_Gate.md)
- [Post-Stage-1 Gate Inventory](Post_Stage_1_Gate_Inventory.md)
- [Post-Stage-1 Larger Sample G6 Successor Plan](../04_experiments/Post_Stage_1_Larger_Sample_G6_Successor_Plan.md)
- [Post-Stage-1 Metric Policy](../05_evaluation/Post_Stage_1_Metric_Policy.md)
- [Post-Stage-1 Lane A 20260519_232854 Run Report](../05_evaluation/Post_Stage_1_Lane_A_20260519_232854_Run_Report.md)
