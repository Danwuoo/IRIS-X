# Post-Stage-1 Context OS Planning Draft Spec

## Purpose

Define the minimum routable Context OS planning contract allowed by `PS1-G7`
after the `20260601_113121` Lane A rerun accepted by manifest closure.

This document converts the measured Lane A working-set facts into a planning
surface for future Context OS specification and evaluation work. It is not a
runtime implementation spec for full Context OS.

## Status

Spec status: `Context OS planning draft`.

Gate policy version: `PS1-LC-CTX-GATE-001`.

Source Lane A run: `20260601_113121`.

Source Lane A closure status: `accepted_by_closure`.

Source sample frame: `PS1-LA-SAMPLE-002`.

Metric policy version: `PS1-LA-METRIC-001`.

Label policy version: `PS1-LB-LABEL-001`.

Lane B label status: `complete_reported` for the first active
`20260601_113121` packet.

Implementation status: `Not authorized`.

Schema status: no schema changes in this planning batch.

Claim level: planning artifact only. This document cites the Lane A
`accepted_by_closure` source run but does not create a Context OS closure, H3
validation, or full Context OS validation.

## Inputs

This planning draft depends on:

- [Context OS Expansion Gate](../00_manifest/Context_OS_Expansion_Gate.md)
- [Context OS and Working Set Compiler Note](Context_OS_and_Working_Set_Compiler_Note.md)
- [Post-Stage-1 Labeling Scope and Adjudication Policy](../05_evaluation/Post_Stage_1_Labeling_Scope_and_Adjudication_Policy.md)
- [Post-Stage-1 Lane A 20260601_113121 Run Report](../05_evaluation/Post_Stage_1_Lane_A_20260601_113121_Run_Report.md)
- [Post-Stage-1 Lane A 20260601_113121 Closure](../00_manifest/Post_Stage_1_Lane_A_20260601_113121_Closure.md)
- `docs/04_experiments/results/post_stage_1_larger_sample/20260601_113121/run.json`
- [Post-Stage-1 Lane B 20260601_113121 Blinded Label Packet](../05_evaluation/label_packets/post_stage_1_lane_b_20260601_113121/README.md)
- [Post-Stage-1 Lane B 20260601_113121 Label Report](../05_evaluation/Post_Stage_1_Lane_B_20260601_113121_Label_Report_Skeleton.md)
- [Coordinator-only post-freeze context unblind memo](../05_evaluation/label_packets/post_stage_1_lane_b_20260601_113121/coordinator_only_post_freeze_context_unblind_memo.md)

## Planning Boundary

| Area | Planning rule |
| --- | --- |
| Current implemented context capability | `Working Set Compiler v0` remains the current implemented scope. |
| Allowed planning output | Future Context OS spec, schema impact review, experiment plan, label/reporting path, and explicit non-goals. |
| Runtime behavior | No new runtime behavior is authorized by this document. |
| Schema behavior | No schema enum or contract changes are made by this document. |
| Memory | No memory store read, memory append, memory governance, learned memory, or `MEMORY_WRITE` action is authorized. |
| Retrieval and compression | No learned retrieval, learned ranking, or learned compression is authorized. |
| Side effects | `COMMITTABLE`, `IRREVERSIBLE`, and unaccepted external effects remain blocked. |
| Claims | No H3, full Context OS, production, or broad runtime validation claim is allowed. |

## Planning Contract

A future Context OS planning bundle must name these fields before any execution:

| Field | Required value |
| --- | --- |
| `gate_policy_version` | `PS1-LC-CTX-GATE-001` |
| `source_run_ref` | The measured run artifact used as input. For this draft: `20260601_113121`, accepted by Lane A manifest closure. |
| `metric_policy_version` | `PS1-LA-METRIC-001` unless explicitly superseded. |
| `label_policy_version` | `PS1-LB-LABEL-001` unless explicitly superseded. |
| `baseline_arm_label` | A `PS1-G5` compliant context baseline label. |
| `treatment_arm_label` | A `PS1-G5` compliant working-set or future Context OS treatment label. |
| `context_budget` | Prompt, response, and selected-context budget controls, with estimation method when exact tokens are unavailable. |
| `allowed_input_refs` | The reference families allowed for selection. |
| `blocked_input_refs` | Raw tool logs, full memory dumps, memory-write refs, and external side-effect refs. |
| `label_source` | Fixture oracle, automated structural, human, secondary review, or double-human adjudicated. |
| `artifact_paths` | Run, summary, fixture inventory, label packet, and report paths. |
| `interpretation_boundary` | Explicit statement that missing labels keep the artifact at planning draft or pilot level. |

## Allowed Input References

Planning may use only reference-backed inputs already allowed by the Stage 0 and
Phase 5 context boundary:

- active goal or task refs
- canonical state refs
- Evidence Packet refs
- constraint and policy refs
- recovery context refs
- fixture-provided memory refs when the fixture explicitly names them
- candidate-ref inventories used for evaluation packets

Planning must not use:

- raw tool logs as canonical context
- full memory dumps
- memory-store reads
- memory appends
- learned retrieval or ranking output
- compressed summaries treated as provenance-equivalent source artifacts
- external side-effect results not governed by an accepted side-effect gate

## Outputs

The minimum routable output set for this planning layer is:

| Output | Path in this batch | Status |
| --- | --- | --- |
| Context OS planning draft spec | `docs/02_specs/Post_Stage_1_Context_OS_Planning_Draft_Spec.md` | Draft |
| Schema impact review | `docs/03_schemas/Post_Stage_1_Context_OS_Schema_Impact_Review.md` | Draft, no schema changes |
| Context OS evaluation plan | `docs/04_experiments/Post_Stage_1_Context_OS_Evaluation_Plan.md` | Draft, not yet run |

These outputs are routing artifacts. They do not replace `working_set.schema.json`
or authorize runtime implementation.

## Lane A Evidence Used

The `20260601_113121` Lane A closure run supports these planning facts:

| Fact | Source value | Planning interpretation |
| --- | ---: | --- |
| Working-set fixture coverage | 6 long-context fixtures | The 48-fixture frame can produce a working-set stratum report. |
| Treatment working-set budget adherence | `1.0000` | Budget adherence can be structurally measured under the current run contract. |
| Treatment working-set provenance completeness | `1.0000` | Provenance completeness can be structurally measured under `Working Set Compiler v0`. |
| Treatment context omission error rate | `0.0000` | Fixture-oracle or structural omission scoring supports planning, not human-labeled Context OS evidence. |
| Treatment working-set relevance score | `0.9667` | Fixture-oracle or structural relevance scoring supports planning, not broad Context OS validation. |
| Treatment long-task stability | `1.0000` | The long-context stratum did not regress under the measured Lane A treatment. |
| Unsupported commits | `0` | Process-integrity floor held in the measured run. |
| Memory writes | `0` | The measured run stayed inside the no-memory-write boundary. |
| Disallowed side-effect classes | `0` | The measured run stayed inside accepted side-effect classes. |
| Required artifacts valid | `true` | `run.json`, `summary.md`, and `fixture_inventory.md` were produced and linked. |

## Lane B Label Evidence And Remaining Limits

The first active Lane B label report now provides packet-level human-labeled
context-quality evidence for the blinded working-set items:

| Item | Current status |
| --- | --- |
| Human-labeled omission evidence | Available for the named active packet: `context_omission_error_rate = 0.3684` (`14 / 38`) across blinded working-set items. |
| Human-labeled relevance evidence | Available for the named active packet: `working_set_relevance_score = 0.7742` (`24 / 31`) across blinded working-set items. |
| Post-freeze arm interpretation | Available only in the coordinator-only unblind memo. It maps blinded arms to the PS1-G5 compliant bounded raw-trace baseline and `Working Set Compiler v0` treatment after primary label freeze, and must not be copied into reviewer-visible packet records. |
| Broader context-quality claim | Limited to the named active packet; raw agreement counts are reported because the sample is small. |
| H3 interpretation | Still blocked. The source run is accepted only for the named Lane A threshold-governed sample, and Context OS implementation plus Context OS evaluation remain missing. |
| Full Context OS claim | Full Context OS implementation, learned retrieval, compression, and memory governance remain outside this gate. |

## Rejection Conditions

A future Context OS planning or evaluation artifact must be rejected or labeled
only as exploratory if it:

- omits `PS1-LC-CTX-GATE-001`
- treats the historical `20260530_141649` Lane A run or packet as the active
  accepted-run source
- treats the `20260601_113121` Lane A closure as H3 or full Context OS
  validation
- treats fixture-oracle working-set metrics as human-labeled evidence
- copies post-freeze arm identity mapping into reviewer-visible packet artifacts
- hides OpenClaw local harness identity
- introduces learned retrieval, learned ranking, learned compression, memory
  writes, or full memory dumps
- changes schema enums without an accepted schema batch
- reports full Context OS validation or H3 validation

## Open Questions

- Which Lane B label results, if any, justify a later Context OS implementation
  spec rather than continued `Working Set Compiler v0` evaluation?
- Should future context quality reports require a dedicated label-packet schema
  after the first Lane B packet is completed?
- Which failure classes should trigger working-set recompilation in a future
  spec, and which should stay with verifier rejection or targeted recovery?

## Related Documents

- [Project Manifest](../00_manifest/Project_Manifest.md)
- [Document Map](../00_manifest/Document_Map.md)
- [Traceability Matrix](../00_manifest/Traceability_Matrix.md)
- [Context OS Expansion Gate](../00_manifest/Context_OS_Expansion_Gate.md)
- [Context OS and Working Set Compiler Note](Context_OS_and_Working_Set_Compiler_Note.md)
- [Post-Stage-1 Lane A 20260601_113121 Run Report](../05_evaluation/Post_Stage_1_Lane_A_20260601_113121_Run_Report.md)
- [Post-Stage-1 Lane B 20260601_113121 Label Report](../05_evaluation/Post_Stage_1_Lane_B_20260601_113121_Label_Report_Skeleton.md)
- [Coordinator-only post-freeze context unblind memo](../05_evaluation/label_packets/post_stage_1_lane_b_20260601_113121/coordinator_only_post_freeze_context_unblind_memo.md)
- [Post-Stage-1 Context OS Schema Impact Review](../03_schemas/Post_Stage_1_Context_OS_Schema_Impact_Review.md)
- [Post-Stage-1 Context OS Evaluation Plan](../04_experiments/Post_Stage_1_Context_OS_Evaluation_Plan.md)
