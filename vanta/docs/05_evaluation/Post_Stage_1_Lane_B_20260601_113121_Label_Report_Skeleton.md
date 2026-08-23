# Post-Stage-1 Lane B 20260601_113121 Label Report

## Experiment

- Source experiment ID: `post_stage_1_larger_sample`
- Source sample frame: `PS1-LA-SAMPLE-002`
- Source Lane A run timestamp: `20260601_113121`
- Source Lane A closure status: `accepted_by_closure`
- Lane B packet ID: `PS1-LB-PACKET-20260601-113121-BATCH-001`
- Label policy version: `PS1-LB-LABEL-001`
- Metric policy version: `PS1-LA-METRIC-001`
- Context gate policy version: `PS1-LC-CTX-GATE-001`
- Label collection status: `complete_reported`
- Report status: `reported_from_validated_primary_labels`
- Claim level after labels: `20260601_113121` active packet Lane B labeled
  evaluation evidence only
- Primary reviewer packet freeze: `frozen_for_primary_review_distribution`
  on 2026-06-03
- Primary label freeze: `frozen` at `2026-06-05T21:40:44+08:00`
- Fixture oracle metadata exposed before primary label freeze: `no`

For this packet, `complete_reported` means the primary labels were collected,
frozen, validated, import-summarized, and reported in this Lane B label report.
It is a packet-local evaluation status only and does not create a runtime
approval or broader validation claim.

## Source Artifacts

| Artifact | Path |
| --- | --- |
| Source run JSON | `docs/04_experiments/results/post_stage_1_larger_sample/20260601_113121/run.json` |
| Source run summary | `docs/04_experiments/results/post_stage_1_larger_sample/20260601_113121/summary.md` |
| Source fixture inventory | `docs/04_experiments/results/post_stage_1_larger_sample/20260601_113121/fixture_inventory.md` |
| Lane A run report | `docs/05_evaluation/Post_Stage_1_Lane_A_20260601_113121_Run_Report.md` |
| Lane A closure | `docs/00_manifest/Post_Stage_1_Lane_A_20260601_113121_Closure.md` |
| Label packet manifest | `docs/05_evaluation/label_packets/post_stage_1_lane_b_20260601_113121/packet_manifest.json` |
| Redacted task packets | `docs/05_evaluation/label_packets/post_stage_1_lane_b_20260601_113121/redacted_task_packets/` |
| Evidence sufficiency items | `docs/05_evaluation/label_packets/post_stage_1_lane_b_20260601_113121/evidence_sufficiency_items.jsonl` |
| Working-set context items | `docs/05_evaluation/label_packets/post_stage_1_lane_b_20260601_113121/working_set_context_items.jsonl` |
| Filled primary label results | `docs/05_evaluation/label_packets/post_stage_1_lane_b_20260601_113121/label_results_primary_filled.json` |
| Import summary | `docs/05_evaluation/label_packets/post_stage_1_lane_b_20260601_113121/label_results_import_summary.json` |
| Coordinator packet freeze record | `docs/05_evaluation/label_packets/post_stage_1_lane_b_20260601_113121/coordinator_primary_label_packet_freeze.json` |

## Supersession Boundary

This report supersedes
`Post_Stage_1_Lane_B_20260530_141649_Label_Report_Skeleton.md` as the active
Lane B reporting shell. The older skeleton remains a historical shell for the
non-accepted `20260530_141649` source run and its prepared packet only.

The older packet must not be used as the current Lane B source for accepted
post-Stage-1 routing because its source run was not `accepted_by_closure` and
its `docops_struct_selector_missing_001` item records the pre-repair committed
artifact. No labels had been collected for that older packet before this
rebuild.

## Labeling Contract

| Metric | Item count | Review mode | Label source | Status |
| --- | ---: | --- | --- | --- |
| `evidence_sufficiency_score` | 8 | `double_human_adjudicated` | `human` | `complete_reported` |
| `context_omission_error_rate` | 12 | `double_human_adjudicated` | `human` | `complete_reported` |
| `working_set_relevance_score` | 12 | `double_human_adjudicated` | `human` | `complete_reported` |

Reviewer identity policy: stable anonymized reviewer IDs are preserved in the
filled result file. The collected primary reviewer IDs are `reviewer_A` and
`reviewer_B`.

Blinding policy: primary labelers received only the packet item records,
referenced redacted task packets, fixture input artifacts, redacted
candidate-ref inventories, and blinded context arm names. Fixture oracle role
fields, original `input_artifacts.role` and `input_artifacts.description`
fields, arm identity mapping, expected labels, task success flags, aggregate
item metrics, and post-run repair notes were withheld until primary labels were
frozen.

The packet-local label result format is
`PS1-LB-LABEL-RESULT-LOCAL-001`. It is a local collection/import format for
this Lane B packet and does not extend core runtime schemas.

## Collection, Import, Validation, And Reporting Flow

Completed sequence:

1. Distributed only the frozen primary-labeler-visible packet files through the
   package prepared from the coordinator allowlist.
2. Collected raw primary labels with stable reviewer IDs and no fixture oracle
   exposure before freeze.
3. Froze primary labels at `2026-06-05T21:40:44+08:00`.
4. Validated the filled result file:
   `mix vanta.post_stage_1_lane_b_label_results --mode validate --results docs/05_evaluation/label_packets/post_stage_1_lane_b_20260601_113121/label_results_primary_filled.json`.
5. Validator reported zero `needs_review` labels, zero adjudication triggers,
   and zero unhandled adjudication triggers.
6. Produced import summary:
   `docs/05_evaluation/label_packets/post_stage_1_lane_b_20260601_113121/label_results_import_summary.json`.
7. Filled this report from the real raw labels, primary label freeze metadata,
   raw agreement counts, validation output, and import summary.

## Candidate Sample

Evidence sufficiency candidates:

| Item | Task | Stratum | Source item file |
| --- | --- | --- | --- |
| `lb20260601-es-001` | `docops_read_traceability_001` | `traceability_extraction` | `evidence_sufficiency_items.jsonl` |
| `lb20260601-es-002` | `docops_struct_contract_fail_001` | `terminology_consistency` | `evidence_sufficiency_items.jsonl` |
| `lb20260601-es-003` | `docops_simulate_patch_001` | `simulated_patch_and_diff` | `evidence_sufficiency_items.jsonl` |
| `lb20260601-es-004` | `docops_struct_apply_reversible_001` | `reversible_edit_and_commit` | `evidence_sufficiency_items.jsonl` |
| `lb20260601-es-005` | `docops_struct_selector_missing_001` | `invalid_action_and_path_guard` | `evidence_sufficiency_items.jsonl` |
| `lb20260601-es-006` | `docops_wrong_diff_001` | `evidence_and_verifier_challenge` | `evidence_sufficiency_items.jsonl` |
| `lb20260601-es-007` | `docops_rollback_failure_001` | `journal_replay_and_recovery` | `evidence_sufficiency_items.jsonl` |
| `lb20260601-es-008` | `docops_ws_evidence_packet_001` | `working_set_long_context` | `evidence_sufficiency_items.jsonl` |

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

| Metric | Raw labels | Adjudicated labels | Score | `needs_review` count | Status |
| --- | ---: | --- | ---: | ---: | --- |
| `evidence_sufficiency_score` | 16 | No adjudication required; exact matching primary labels retained | `0.9375` | 0 | `complete_reported` |
| `context_omission_error_rate` | 24 | No adjudication required; exact matching primary labels retained | `0.3684` (`14 / 38`) | 0 | `complete_reported` |
| `working_set_relevance_score` | 24 | No adjudication required; exact matching primary labels retained | `0.7742` (`24 / 31`) | 0 | `complete_reported` |

Evidence sufficiency raw labels:

| Item | Reviewer labels | Item normalized score |
| --- | --- | ---: |
| `lb20260601-es-001` | `4`, `4` | `1.0000` |
| `lb20260601-es-002` | `4`, `4` | `1.0000` |
| `lb20260601-es-003` | `4`, `4` | `1.0000` |
| `lb20260601-es-004` | `4`, `4` | `1.0000` |
| `lb20260601-es-005` | `3`, `3` | `0.7500` |
| `lb20260601-es-006` | `4`, `4` | `1.0000` |
| `lb20260601-es-007` | `3`, `3` | `0.7500` |
| `lb20260601-es-008` | `4`, `4` | `1.0000` |

Human-derived working-set labels by blinded arm:

| Blinded arm | Omission error rate | Working-set relevance score |
| --- | ---: | ---: |
| `context_arm_A` | `0.7368` (`14 / 19`) | `0.4545` (`5 / 11`) |
| `context_arm_B` | `0.0000` (`0 / 19`) | `0.9500` (`19 / 20`) |
| Combined | `0.3684` (`14 / 38`) | `0.7742` (`24 / 31`) |

The blinded arm names are reported without revealing the arm identity mapping.

## Adjudication

Adjudication status: `completed_no_records_required`.

Validator output:

- `needs_review_count`: 0
- `adjudication_required_count`: 0
- `unhandled_adjudication_required_count`: 0
- `adjudication_record_count`: 0

No reviewer marked `needs_review`; no evidence labels differed by two or more
levels; no evidence labels split across the `0-2` versus `3-4` acceptability
boundary; and reviewers did not disagree on harmful relevance,
task-critical refs, critical omission, or denominator fields.

Fixture oracle metadata exposure during adjudication: `not_exposed`; no
adjudication inspection was required after primary labels were frozen.

## Agreement

Inter-annotator agreement status: `small_sample_raw_counts`.

Raw agreement counts:

| Label surface | Exact agreement | Exact disagreement |
| --- | ---: | ---: |
| Evidence sufficiency raw label | 8 / 8 item pairs | 0 / 8 item pairs |
| Working-set omission fields | 12 / 12 item pairs | 0 / 12 item pairs |
| Working-set per-ref relevance labels | 12 / 12 item pairs | 0 / 12 item pairs |
| Working-set packet relevance quality | 12 / 12 item pairs | 0 / 12 item pairs |

This first active packet is too small for stable inter-annotator agreement
statistics, so the report gives raw agreement counts only.

## Import Summary

Validated import summary:

- Summary path:
  `docs/05_evaluation/label_packets/post_stage_1_lane_b_20260601_113121/label_results_import_summary.json`
- Result path:
  `docs/05_evaluation/label_packets/post_stage_1_lane_b_20260601_113121/label_results_primary_filled.json`
- Raw label counts:
  `evidence_sufficiency_score = 16`,
  `working_set_context = 24`
- Review coverage:
  `evidence_sufficiency_score = 8 / 8`,
  `context_omission_error_rate = 12 / 12`,
  `working_set_relevance_score = 12 / 12`
- Secondary review count: 0
- Adjudication required count: 0
- Unhandled adjudication required count: 0
- Fixture oracle exposed before freeze: `false`
- Reported metric score parity:
  `evidence_sufficiency_score = 0.9375`,
  `context_omission_error_rate = 0.3684 (14 / 38)`,
  `working_set_relevance_score = 0.7742 (24 / 31)`
- Parity check command:
  `mix vanta.post_stage_1_lane_b_label_results --mode report-parity --results docs/05_evaluation/label_packets/post_stage_1_lane_b_20260601_113121/label_results_primary_filled.json --import-summary docs/05_evaluation/label_packets/post_stage_1_lane_b_20260601_113121/label_results_import_summary.json --report docs/05_evaluation/Post_Stage_1_Lane_B_20260601_113121_Label_Report_Skeleton.md`

## Interpretation Boundaries

Allowed after this report:

- The `20260601_113121` Lane A closure run has a completed active Lane B label
  packet with 40 real raw primary labels, primary label freeze, validation,
  raw agreement counts, and import summary under `PS1-LB-LABEL-001`.
- The labels are Lane B labeled evaluation evidence for the named active packet
  and the named metrics only.

Disallowed:

- new `accepted_by_closure` status beyond the Lane A source closure
- H1-H5 validation
- full Context OS validation
- production readiness
- human-in-the-loop verifier or runtime approval claims
- replacing the measured Lane A aggregate metrics with label results
- model-only baseline claims for OpenClaw local harness results

## Findings

- The active packet has complete primary coverage: 16 evidence sufficiency raw
  labels and 24 working-set context raw labels.
- Both reviewers agreed exactly across all item pairs, so validator-triggered
  adjudication was not required.
- Evidence sufficiency labels produce a human-labeled score of `0.9375` for the
  sampled evidence items.
- Human-derived working-set context labels produce combined
  `context_omission_error_rate = 0.3684` and
  `working_set_relevance_score = 0.7742` across the blinded working-set items.

## Failures And Risks

- The sample remains small: 8 evidence sufficiency items and 12 working-set
  context items. Raw agreement counts are reported, but stable agreement
  statistics are not meaningful at this size.
- The report is limited to this active Lane B packet. It is not a broader
  runtime validation result and does not validate H1-H5.
- Human-derived working-set relevance must be read with omission results,
  because high relevance among included refs can still hide omitted critical
  refs.

## Next Steps

1. Use the validated import summary as the machine-readable import record for
   this packet.
2. Keep future Lane B packets separately named and policy-versioned if broader
   label coverage is needed.
3. Keep Context OS, side-effect, runtime approval, and H1-H5 claims routed
   through later accepted specs, schemas, experiments, and evaluation reports.
