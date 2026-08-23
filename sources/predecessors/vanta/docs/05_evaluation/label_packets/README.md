# Label Packets

## Purpose

This directory is the navigation entry for Lane B label packet artifacts.
Label packets are evaluation artifacts: they prepare or record blinded review
items, redacted task packets, local label results, import summaries, and
coordinator-only notes. They are not runtime approval records, schema expansion
records, H1-H5 validation, or full Context OS validation.

## Packets

| Packet | Status | Source run | Notes |
| --- | --- | --- | --- |
| `post_stage_1_lane_b_20260601_113121/` | Active reported packet | `docs/04_experiments/results/post_stage_1_larger_sample/20260601_113121/` | Built from the Lane A run accepted by closure for the named threshold-governed Document Ops Lane A sample. It has filled primary labels, validation, import summary, and the companion reported Lane B label report. |
| `post_stage_1_lane_b_20260530_141649/` | Superseded historical packet | `docs/04_experiments/results/post_stage_1_larger_sample/20260530_141649/` | Its source run was not `accepted_by_closure`, and its `docops_struct_selector_missing_001` item captures the pre-repair committed artifact. It remains provenance only. |

## Active Packet Boundary

The active packet source is the `20260601_113121` Lane A accepted closure run.
The packet supports Lane B labeled evaluation evidence for the named packet and
named metrics only. It does not create new closure acceptance, runtime
approval, schema enum changes, runtime behavior changes, production readiness,
H1-H5 validation, or full Context OS validation.

## Superseded Packet Boundary

The `20260530_141649` packet is retained as a superseded historical packet. It
must not be used as the active Lane B source because the source run was not
`accepted_by_closure` and the selector-missing item records the pre-repair
committed artifact. A future report may explicitly label that historical run
only if it states the reason and keeps the non-accepted source-run boundary.

## Artifact Types

| Artifact | Purpose |
| --- | --- |
| `packet_manifest.json` | Coordinator manifest for source linkage, review mode, blinding boundary, status, and packet artifact paths. |
| `evidence_sufficiency_items.jsonl` | Blinded evidence sufficiency label items. These are reviewer-visible packet records, not core runtime schemas. |
| `working_set_context_items.jsonl` | Blinded working-set omission and relevance label items. These are reviewer-visible packet records, not core runtime schemas. |
| `redacted_task_packets/` | Primary-labeler task packets with fixture oracle role and description fields removed where required by the packet blinding policy. |
| `adjudication_placeholders.json` | Packet-local adjudication scaffold and trigger rules. Empty or placeholder records are not completed adjudication evidence. |
| `label_results_template.json` | Packet-local import template for raw labels. It is not a core runtime schema and must not be treated as real labels. |
| `label_results_primary_filled.json` | Filled raw primary label results for packets that have collected labels. For the active packet, this records the 40 real primary labels and label freeze metadata. |
| `label_results_import_summary.json` | Machine-readable validation and import summary for a filled label result file. It supports report filling and parity checks only. |
| `coordinator_primary_label_packet_freeze.json` | Coordinator-only allowlist freeze for primary-labeler-visible files. It is not the primary label freeze unless the packet says so. |
| `coordinator_only_*` notes | Coordinator-only post-freeze interpretation or planning notes. They must remain outside primary-labeler-visible packet material before label freeze. |

## Retention

Active, historical, superseded, redacted, filled, import-summary, and
coordinator-only packet artifacts are retained for evaluation provenance.
Packet directories should not be moved or deleted during source-tree cleanup.
Use the artifact retention policy in
[Repository Structure](../../06_engineering/Repository_Structure.md) for
tracked/ignored boundaries and ChatGPT Project Knowledge export handling.

## Related Documents

- [Post-Stage-1 Labeling Scope and Adjudication Policy](../Post_Stage_1_Labeling_Scope_and_Adjudication_Policy.md)
- [Post-Stage-1 Lane B 20260601_113121 Label Report](../Post_Stage_1_Lane_B_20260601_113121_Label_Report_Skeleton.md)
- [Post-Stage-1 Lane B 20260601_113121 Blinded Label Packet](post_stage_1_lane_b_20260601_113121/README.md)
- [Post-Stage-1 Lane B 20260530_141649 Blinded Label Packet](post_stage_1_lane_b_20260530_141649/README.md)
