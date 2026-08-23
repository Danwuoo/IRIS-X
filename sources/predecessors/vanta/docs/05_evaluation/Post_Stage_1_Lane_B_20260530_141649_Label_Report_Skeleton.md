# Post-Stage-1 Lane B 20260530_141649 Label Report Skeleton

## Experiment

- Source experiment ID: `post_stage_1_larger_sample`
- Source sample frame: `PS1-LA-SAMPLE-002`
- Source Lane A run timestamp: `20260530_141649`
- Lane B packet ID: `PS1-LB-PACKET-20260530-141649-BATCH-001`
- Label policy version: `PS1-LB-LABEL-001`
- Metric policy version: `PS1-LA-METRIC-001`
- Context gate policy version: `PS1-LC-CTX-GATE-001`
- Label collection status: `Not yet run`
- Report status: `Superseded historical skeleton; Not yet run`
- Claim level before labels: superseded prepared blinded label packet only

## Supersession Boundary

This skeleton remains in the repository only as the reporting shell for the
historical `20260530_141649` packet. It has been superseded as the active Lane B
reporting shell by
[Post-Stage-1 Lane B 20260601_113121 Label Report Skeleton](Post_Stage_1_Lane_B_20260601_113121_Label_Report_Skeleton.md).

The older source run was not `accepted_by_closure`, and its
`docops_struct_selector_missing_001` item records the pre-repair committed
artifact. Because no labels had been collected, current accepted-run Lane B
routing must use the `20260601_113121` packet instead.

## Source Artifacts

| Artifact | Path |
| --- | --- |
| Source run JSON | `docs/04_experiments/results/post_stage_1_larger_sample/20260530_141649/run.json` |
| Source run summary | `docs/04_experiments/results/post_stage_1_larger_sample/20260530_141649/summary.md` |
| Source fixture inventory | `docs/04_experiments/results/post_stage_1_larger_sample/20260530_141649/fixture_inventory.md` |
| Lane A run report | `docs/05_evaluation/Post_Stage_1_Lane_A_20260530_141649_Run_Report.md` |
| Label packet manifest | `docs/05_evaluation/label_packets/post_stage_1_lane_b_20260530_141649/packet_manifest.json` |
| Redacted task packets | `docs/05_evaluation/label_packets/post_stage_1_lane_b_20260530_141649/redacted_task_packets/` |
| Evidence sufficiency items | `docs/05_evaluation/label_packets/post_stage_1_lane_b_20260530_141649/evidence_sufficiency_items.jsonl` |
| Working-set context items | `docs/05_evaluation/label_packets/post_stage_1_lane_b_20260530_141649/working_set_context_items.jsonl` |
| Adjudication placeholders | `docs/05_evaluation/label_packets/post_stage_1_lane_b_20260530_141649/adjudication_placeholders.json` |

## Labeling Contract

| Metric | Item count | Review mode | Label source | Status |
| --- | ---: | --- | --- | --- |
| `evidence_sufficiency_score` | 8 | `double_human_adjudicated` | `human` | `Not yet run` |
| `context_omission_error_rate` | 12 | `double_human_adjudicated` | `human` | `Not yet run` |
| `working_set_relevance_score` | 12 | `double_human_adjudicated` | `human` | `Not yet run` |

Reviewer identity policy: anonymized reviewer IDs are allowed, but each raw
label must preserve a stable reviewer ID.

Fixture oracle metadata exposed before label freeze: `no`.

Blinding policy: primary labelers see only the packet item records, referenced
redacted task packets, fixture input artifacts, redacted candidate-ref
inventories, and blinded context arm names. Fixture oracle role fields, original
`input_artifacts.role` and `input_artifacts.description` fields, arm identity
mapping, expected labels, task success flags, aggregate item metrics, and
post-run repair notes remain withheld until labels are frozen.

## Candidate Sample

Evidence sufficiency candidates:

| Item | Task | Stratum | Source item file |
| --- | --- | --- | --- |
| `lb20260530-es-001` | `docops_read_traceability_001` | `traceability_extraction` | `evidence_sufficiency_items.jsonl` |
| `lb20260530-es-002` | `docops_struct_contract_fail_001` | `terminology_consistency` | `evidence_sufficiency_items.jsonl` |
| `lb20260530-es-003` | `docops_simulate_patch_001` | `simulated_patch_and_diff` | `evidence_sufficiency_items.jsonl` |
| `lb20260530-es-004` | `docops_struct_apply_reversible_001` | `reversible_edit_and_commit` | `evidence_sufficiency_items.jsonl` |
| `lb20260530-es-005` | `docops_struct_selector_missing_001` | `invalid_action_and_path_guard` | `evidence_sufficiency_items.jsonl` |
| `lb20260530-es-006` | `docops_wrong_diff_001` | `evidence_and_verifier_challenge` | `evidence_sufficiency_items.jsonl` |
| `lb20260530-es-007` | `docops_rollback_failure_001` | `journal_replay_and_recovery` | `evidence_sufficiency_items.jsonl` |
| `lb20260530-es-008` | `docops_ws_evidence_packet_001` | `working_set_long_context` | `evidence_sufficiency_items.jsonl` |

Working-set candidates:

| Task | Blinded arms | Source item file |
| --- | --- | --- |
| `docops_ws_evidence_packet_001` | `context_arm_A`, `context_arm_B` | `working_set_context_items.jsonl` |
| `docops_ws_irrelevant_context_001` | `context_arm_A`, `context_arm_B` | `working_set_context_items.jsonl` |
| `docops_ws_omission_trap_001` | `context_arm_A`, `context_arm_B` | `working_set_context_items.jsonl` |
| `docops_ws_recovery_context_001` | `context_arm_A`, `context_arm_B` | `working_set_context_items.jsonl` |
| `docops_ws_traceability_long_001` | `context_arm_A`, `context_arm_B` | `working_set_context_items.jsonl` |
| `docops_ps1_ws_structured_edit_context_001` | `context_arm_A`, `context_arm_B` | `working_set_context_items.jsonl` |

## Label Results

Human labels have not been collected.

| Metric | Raw labels | Adjudicated labels | Score | `needs_review` count | Status |
| --- | --- | --- | --- | --- | --- |
| `evidence_sufficiency_score` | `Not yet run` | `Not yet run` | `Not yet run` | `Not yet run` | `Not yet run` |
| `context_omission_error_rate` | `Not yet run` | `Not yet run` | `Not yet run` | `Not yet run` | `Not yet run` |
| `working_set_relevance_score` | `Not yet run` | `Not yet run` | `Not yet run` | `Not yet run` | `Not yet run` |

## Adjudication

Adjudication status: `Not yet run`.

Required adjudication triggers:

- any reviewer marks `needs_review`
- evidence sufficiency labels differ by two or more levels
- evidence sufficiency labels split across the `0-2` versus `3-4`
  acceptability boundary
- reviewers disagree on `task_critical`, `critical_omission`, `harmful`, or
  denominator fields for working-set metrics

Adjudication records must include original labels, adjudicated label,
adjudicator ID, rationale, artifact refs inspected, and whether fixture oracle
metadata was exposed.

## Agreement

Inter-annotator agreement: `Not yet run`.

If this first batch remains too small for stable agreement statistics, report
raw agreement counts and state that agreement statistics are not meaningful at
the sample size.

## Interpretation Boundaries

Allowed before labels are collected:

- The `20260530_141649` Lane A run has a prepared blinded Lane B label packet.
- The packet includes candidate artifact paths, review modes, blinding
  boundary, and adjudication placeholders for the three named metrics.
- The packet and this skeleton are historical and superseded by the
  `20260601_113121` Lane B packet for current accepted-run routing.

Disallowed before labels are collected:

- human-labeled broader evaluation evidence
- `accepted_by_closure`
- active accepted-run Lane B routing source
- H1-H5 validation
- full Context OS validation
- production readiness
- human-in-the-loop verifier or runtime approval claims
- replacing the measured Lane A aggregate metrics with post-run repair results

## Findings

`Not yet run`.

## Failures And Risks

`Not yet run`.

## Next Steps

1. Freeze the primary labeling packet and distribute only the blinded item
   files and referenced source artifacts to reviewers.
2. Collect two independent labels per item or record an allowed secondary
   review substitution.
3. Freeze primary labels before exposing fixture oracle fields or arm identity
   mappings.
4. Complete adjudication records for all required disagreements.
5. Fill this report with raw labels, adjudicated labels, agreement counts, and
   interpretation boundaries.
