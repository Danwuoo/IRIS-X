# Post-Stage-1 Lane B 20260601_113121 Blinded Label Packet

## Purpose

This packet is the active blinded Lane B labeling batch prepared from the
`20260601_113121` Lane A rerun that is `accepted_by_closure` for the named
threshold-governed Document Ops Lane A sample.

It prepares artifact packets for:

- `evidence_sufficiency_score`
- `context_omission_error_rate`
- `working_set_relevance_score`

The prepared item files remain the frozen primary-labeler-visible packet. The
packet directory now also contains the first filled primary label result file
and import summary for this active packet. Label collection status is
`complete_reported`.

For this packet, `complete_reported` means the primary labels were collected,
frozen, validated, import-summarized, and reported in the companion Lane B
label report. It is a packet-local evaluation status only and does not create a
runtime approval or broader validation claim.

## Packet Contents

| Artifact | Purpose |
| --- | --- |
| `packet_manifest.json` | Coordinator manifest, source run linkage, review mode, blinding boundary, supersession note, and artifact paths. |
| `redacted_task_packets/` | Primary-labeler task packets with fixture oracle role and description fields removed from `input_artifacts`. |
| `evidence_sufficiency_items.jsonl` | Eight blinded evidence sufficiency label items sampled from the accepted run artifact. |
| `working_set_context_items.jsonl` | Twelve blinded working-set omission and relevance items: six long-context tasks by two blinded context arms. |
| `adjudication_placeholders.json` | Empty adjudication record scaffold and trigger rules. |
| `label_results_template.json` | Packet-local label result import template for `PS1-LB-LABEL-001`; not a core runtime schema. |
| `label_results_primary_filled.json` | Filled packet-local primary label result file with 40 real raw labels, primary label freeze, raw agreement counts, and no validator-triggered adjudication requirements. |
| `label_results_import_summary.json` | Machine-readable validation/import summary for the filled primary label result file. |
| `coordinator_primary_label_packet_freeze.json` | Coordinator-only freeze record for the primary-labeler-visible allowlist. This is not a reviewer-visible artifact and does not freeze primary labels. |
| `../../Post_Stage_1_Lane_B_20260601_113121_Label_Report_Skeleton.md` | Filled label report for this active packet. |

## Source Run

- Source Lane A run:
  `docs/04_experiments/results/post_stage_1_larger_sample/20260601_113121/run.json`
- Source run report:
  `docs/05_evaluation/Post_Stage_1_Lane_A_20260601_113121_Run_Report.md`
- Source closure:
  `docs/00_manifest/Post_Stage_1_Lane_A_20260601_113121_Closure.md`
- Label policy version: `PS1-LB-LABEL-001`
- Gate policy for context expansion planning: `PS1-LC-CTX-GATE-001`
- Source run threshold status: `pass_acceptance_candidate`
- Source run closure status: `accepted_by_closure`

The source run remains a Lane A measured run. This Lane B packet is an
evaluation-labeling artifact only and does not change the measured Lane A
metrics or create any new closure status.

## Supersession Boundary

This packet supersedes the prepared `20260530_141649` Lane B packet as the
active labeling packet because the older packet was extracted from a Lane A run
that was not `accepted_by_closure` and still contained the pre-repair
`docops_struct_selector_missing_001` committed artifact. No human labels,
secondary review, adjudication, or agreement reporting had been collected for
that older packet.

The older packet may remain in the repository only as a historical packet for
that non-accepted source run. It must not be used as the current Lane B label
source for accepted post-Stage-1 routing unless a future report explicitly
chooses to label that historical run and states why.

## Review Modes

| Metric | Review mode | Label collection status |
| --- | --- | --- |
| `evidence_sufficiency_score` | `double_human_adjudicated` | `complete_reported` |
| `context_omission_error_rate` | `double_human_adjudicated` | `complete_reported` |
| `working_set_relevance_score` | `double_human_adjudicated` | `complete_reported` |

Double human annotation is the default for this first active packet. A
documented secondary review may be used only if a later report records the
substitution and still satisfies `PS1-LB-LABEL-001`.

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
- post-run repair notes when labeling the measured artifact

The primary-labeler-visible packet was frozen for distribution in
`coordinator_primary_label_packet_freeze.json` on 2026-06-03. This freeze only
confirms the reviewer-visible allowlist. It does not freeze primary labels,
does not expose fixture oracle metadata, and is separate from the primary label
freeze recorded in `label_results_primary_filled.json` on 2026-06-05.

Coordinator-only source artifacts, including the original fixture `task.json`
files, may be used after primary labels are frozen for scoring, secondary
review, or adjudication. Any exposure during adjudication must be recorded in
`adjudication_placeholders.json` or its filled successor.

## Post-Freeze Unblind Guard

`mix vanta.post_stage_1_lane_b_packet --mode check` includes an executable
post-freeze unblind guard over reviewer-visible JSONL, redacted task packets,
`label_results_template.json`, and any packet-local result scaffold present.
The guard rejects coordinator-only arm mapping fields, source arm labels, and
post-freeze memo markers. It does not unblind, rewrite, or expand the frozen
item files.

## Candidate Sample

The evidence sufficiency batch uses one sampled treatment evidence unit from
each major Lane A stratum:

| Item | Task | Stratum |
| --- | --- | --- |
| `lb20260601-es-001` | `docops_read_traceability_001` | `traceability_extraction` |
| `lb20260601-es-002` | `docops_struct_contract_fail_001` | `terminology_consistency` |
| `lb20260601-es-003` | `docops_simulate_patch_001` | `simulated_patch_and_diff` |
| `lb20260601-es-004` | `docops_struct_apply_reversible_001` | `reversible_edit_and_commit` |
| `lb20260601-es-005` | `docops_struct_selector_missing_001` | `invalid_action_and_path_guard` |
| `lb20260601-es-006` | `docops_wrong_diff_001` | `evidence_and_verifier_challenge` |
| `lb20260601-es-007` | `docops_rollback_failure_001` | `journal_replay_and_recovery` |
| `lb20260601-es-008` | `docops_ws_evidence_packet_001` | `working_set_long_context` |

The working-set batch covers all six `working_set_long_context` tasks from the
accepted run, each under two blinded context arms.

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

The filled primary labels are recorded in `label_results_primary_filled.json`.
The item JSONL records remain the frozen reviewer-visible packet and are not
edited in place.

## Label Result Import Path

The packet-local result format is `PS1-LB-LABEL-RESULT-LOCAL-001`, with
`label_policy_version: PS1-LB-LABEL-001`. It is a collection and
validation aid for this Lane B packet only; it does not expand the core
runtime schemas in `docs/03_schemas/`.

Use `label_results_template.json` as the starting structure for imported
raw labels. Before any report claim, validate a filled results file with:

```text
mix vanta.post_stage_1_lane_b_label_results --mode validate --results <filled-results.json>
```

To produce a machine-readable import summary for filling the report after
real labels are collected, use:

```text
mix vanta.post_stage_1_lane_b_label_results --mode import-summary --results <filled-results.json> --out <summary.json>
```

These commands must not be used to treat templates, dry-run fixtures, or
generated test data as real human labels.

For the first active packet batch, the filled result file validates with:

- 16 `evidence_sufficiency_score` raw labels
- 24 `working_set_context` raw labels
- 0 `needs_review` labels
- 0 adjudication-required triggers
- 0 unhandled adjudication requirements

## Interpretation Boundary

This packet now supports the filled Lane B label report for the named
`20260601_113121` active packet. It may be described only as Lane B labeled
evaluation evidence for the named packet and metrics. It must not be described
as H1-H5 validation, full Context OS validation, production readiness, a runtime
approval path, or new closure acceptance beyond the Lane A `20260601_113121`
closure.
