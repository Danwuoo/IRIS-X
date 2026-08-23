# Post-Stage-1 Lane B 20260530_141649 Blinded Label Packet

## Purpose

This packet is a historical blinded Lane B labeling batch prepared from the
`20260530_141649` Lane A full v5 rerun.

It has been superseded as the active Lane B labeling packet by
[Post-Stage-1 Lane B 20260601_113121 Blinded Label Packet](../post_stage_1_lane_b_20260601_113121/README.md),
which is rebuilt from the accepted `20260601_113121` Lane A closure run.

It prepares artifact packets for:

- `evidence_sufficiency_score`
- `context_omission_error_rate`
- `working_set_relevance_score`

It does not contain human labels, secondary-review labels, adjudicated labels,
or inter-annotator agreement results. Label collection status is
`Not yet run`.

## Supersession Boundary

This packet remains in the repository only as a historical artifact for the
non-accepted `20260530_141649` source run. It must not be treated as the current
Lane B label source for accepted post-Stage-1 routing because its source run was
not `accepted_by_closure` and its `docops_struct_selector_missing_001` item
records the pre-repair committed artifact.

The active packet for current Lane B routing is
`docs/05_evaluation/label_packets/post_stage_1_lane_b_20260601_113121/`.

## Packet Contents

| Artifact | Purpose |
| --- | --- |
| `packet_manifest.json` | Coordinator manifest, source run linkage, review mode, blinding boundary, and artifact paths. |
| `redacted_task_packets/` | Primary-labeler task packets with fixture oracle role and description fields removed from `input_artifacts`. |
| `evidence_sufficiency_items.jsonl` | Eight blinded evidence sufficiency label items sampled from the run artifact. |
| `working_set_context_items.jsonl` | Twelve blinded working-set omission and relevance items: six long-context tasks by two blinded context arms. |
| `adjudication_placeholders.json` | Empty adjudication record scaffold and trigger rules. |
| `../../Post_Stage_1_Lane_B_20260530_141649_Label_Report_Skeleton.md` | Report skeleton for recording labels after collection. |

## Source Run

- Source Lane A run:
  `docs/04_experiments/results/post_stage_1_larger_sample/20260530_141649/run.json`
- Source run report:
  `docs/05_evaluation/Post_Stage_1_Lane_A_20260530_141649_Run_Report.md`
- Label policy version: `PS1-LB-LABEL-001`
- Gate policy for context expansion planning: `PS1-LC-CTX-GATE-001`
- Source run threshold status: `pass_acceptance_candidate`
- Source run closure status: not `accepted_by_closure`
- Superseded by:
  `docs/05_evaluation/label_packets/post_stage_1_lane_b_20260601_113121/`

The source run remains a Lane A measured run. This Lane B packet is an
evaluation-labeling artifact only and does not change the measured Lane A
metrics.

## Review Modes

| Metric | Review mode | Label collection status |
| --- | --- | --- |
| `evidence_sufficiency_score` | `double_human_adjudicated` | `Not yet run` |
| `context_omission_error_rate` | `double_human_adjudicated` | `Not yet run` |
| `working_set_relevance_score` | `double_human_adjudicated` | `Not yet run` |

Double human annotation is the default for this first packet. A documented
secondary review may be used only if a later report records the substitution
and still satisfies `PS1-LB-LABEL-001`.

## Blinding Boundary

Primary labelers may see:

- the item JSONL records in this packet
- redacted task packets and fixture input artifacts referenced by item paths
- redacted candidate-ref inventories without fixture oracle role fields
- anonymized context arm names, `context_arm_A` and `context_arm_B`
- evidence packet, action, verifier output, and journal fields copied into the
  evidence item records

Primary labelers must not see before labels are frozen:

- fixture oracle fields such as `required_refs`, `relevant_refs`,
  `irrelevant_refs`, `omission_trap_refs`, `expected_runtime_status`,
  `expected_label_source`, expected failure labels, and original
  `input_artifacts.role` or `input_artifacts.description` fields
- aggregate Lane A metric results for the item under review
- context arm identity mapping from `context_arm_A` or `context_arm_B` to
  baseline or treatment
- task success flags from the source run
- post-run focused repair notes when labeling the measured artifact

Coordinator-only source artifacts, including the original fixture `task.json`
files, may be used after primary labels are frozen for scoring, secondary
review, or adjudication. Any exposure during adjudication must be recorded in
`adjudication_placeholders.json` or its filled successor.

## Candidate Sample

The evidence sufficiency batch uses one sampled treatment evidence unit from
each major Lane A stratum:

| Item | Task | Stratum |
| --- | --- | --- |
| `lb20260530-es-001` | `docops_read_traceability_001` | `traceability_extraction` |
| `lb20260530-es-002` | `docops_struct_contract_fail_001` | `terminology_consistency` |
| `lb20260530-es-003` | `docops_simulate_patch_001` | `simulated_patch_and_diff` |
| `lb20260530-es-004` | `docops_struct_apply_reversible_001` | `reversible_edit_and_commit` |
| `lb20260530-es-005` | `docops_struct_selector_missing_001` | `invalid_action_and_path_guard` |
| `lb20260530-es-006` | `docops_wrong_diff_001` | `evidence_and_verifier_challenge` |
| `lb20260530-es-007` | `docops_rollback_failure_001` | `journal_replay_and_recovery` |
| `lb20260530-es-008` | `docops_ws_evidence_packet_001` | `working_set_long_context` |

The working-set batch covers all six `working_set_long_context` tasks from the
run, each under two blinded context arms.

## Label Output Fields

Evidence sufficiency item labels must fill:

- raw `0-4` label or `needs_review`
- normalized score, after adjudication only
- reviewer ID or anonymized reviewer ID
- confidence
- rationale
- referenced artifact IDs

Working-set item labels must fill:

- omission severity
- omitted task-critical ref IDs
- task-critical candidate ref IDs
- per-ref relevance labels
- packet relevance quality
- reviewer ID or anonymized reviewer ID
- confidence
- rationale

All fields are currently `Not yet run`.

## Interpretation Boundary

This packet may support a future historical Lane B label report for the
`20260530_141649` run only if a later report explicitly chooses to label that
non-accepted source run and states why. Until then it may only be described as a
superseded prepared blinded label packet. It must not be described as the active
Lane B packet, human-labeled evidence, H1-H5 validation, full Context OS
validation, production readiness, a runtime approval path, or closure
acceptance for the `20260530_141649` Lane A run.
