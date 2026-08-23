# Lane B Label Packet Reference

Active packet: `PS1-LB-PACKET-20260601-113121-BATCH-001`
Label policy: `PS1-LB-LABEL-001`
Primary label freeze: `2026-06-05T21:40:44+08:00`
Reviewer-visible true arm identity backfilled: `false`

The arm mapping is read only from the coordinator-only post-freeze memo for
evaluation interpretation. Reviewer-visible blinded artifacts remain
unchanged and use only `context_arm_A` and `context_arm_B`.

| Source artifact | SHA-256 / tree hash |
| --- | --- |
| `docs/05_evaluation/label_packets/post_stage_1_lane_b_20260601_113121/README.md` | `sha256:286bfaddc485526b079345b69996357f4b0b83947d5383e1ebbd2ca4d639b7b1` |
| `docs/05_evaluation/label_packets/post_stage_1_lane_b_20260601_113121/adjudication_placeholders.json` | `sha256:ae686b1e572ffc120c20dd1a9d4b70287d8a109711ffa9b2edacb68a257532ff` |
| `docs/05_evaluation/label_packets/post_stage_1_lane_b_20260601_113121/coordinator_only_post_freeze_context_unblind_memo.md` | `sha256:a9b693b43215b8609dc95fa02d8bb61428d108925dee6ea6a88f610bf7685d3f` |
| `docs/05_evaluation/label_packets/post_stage_1_lane_b_20260601_113121/coordinator_primary_label_packet_freeze.json` | `sha256:1fc2bca4b6639a1e297f50613feb04864e6564a162b51fb6cd86fe913c706b6f` |
| `docs/05_evaluation/label_packets/post_stage_1_lane_b_20260601_113121/evidence_sufficiency_items.jsonl` | `sha256:28a620ff5a121eb4cc8b28416b9b26d35177d28acf774a446ab6d1f04d55c992` |
| `docs/05_evaluation/label_packets/post_stage_1_lane_b_20260601_113121/label_results_import_summary.json` | `sha256:d1241acf94c1e2504a37ec11cb96c4d3d821e5bda4bc35d16a587f2c7eaeeb9d` |
| `docs/05_evaluation/label_packets/post_stage_1_lane_b_20260601_113121/label_results_primary_filled.json` | `sha256:3ab1744acc6d3565054421b8efc430674e0a79296446564f2efb0be4dfa216fc` |
| `docs/05_evaluation/label_packets/post_stage_1_lane_b_20260601_113121/label_results_template.json` | `sha256:f6643fb03b6ae7b7a35636d0d256e2318539740054078220d6d6e3244b1e4d4e` |
| `docs/05_evaluation/label_packets/post_stage_1_lane_b_20260601_113121/packet_manifest.json` | `sha256:73aed6614581eb72f886b45316a6cf52a6f7ce4e2f242f5d856349b4d4fc3879` |
| `docs/05_evaluation/label_packets/post_stage_1_lane_b_20260601_113121/redacted_task_packets/` | `sha256:28aafdd651a4caa22e54bd3a45e947754d6b1c65112a142d34a1e2db15bafaac` |
| `docs/05_evaluation/label_packets/post_stage_1_lane_b_20260601_113121/working_set_context_items.jsonl` | `sha256:2ee29b211da40ff0b74b1ea9a35c3475f39a8196c4e5bed428567c6e892ec614` |

Small-sample Lane B results:

- `context_arm_A`: omission 0.7368 (14/19); relevance 0.4545 (5/11)
- `context_arm_B`: omission 0.0000 (0/19); relevance 0.9500 (19/20)
- `Combined`: omission 0.3684 (14/38); relevance 0.7742 (24/31)

Relevance must be interpreted with omission. These labels remain
packet-level evaluation evidence and never become runtime approval.
