# Context OS Expansion Gate

## Purpose

Define the `PS1-G7` gate for expanding beyond deterministic
`Working Set Compiler v0` without approving full Context OS implementation,
memory governance, learned retrieval, or validation claims.

This gate decides when the program may begin Context OS specification and
evaluation planning. It does not change runtime code, update schemas, run
experiments, or authorize memory writes. Lane B labels, when present, remain
evaluation artifacts only and do not become Context OS runtime approvals.

## Status

Gate ID: `PS1-G7`

Gate policy ID: `PS1-LC-CTX-GATE-001`

Status: `Accepted as PS1-G7 gate-definition artifact` on 2026-05-11.

Original Lane A model run status: `20260601_113121` completed and
`accepted_by_closure` for the named Lane A scope.

Artifact-backed G7 evaluation pilot status: `complete` at
`docs/04_experiments/results/context_os_planning/20260719_224209/`.

Full Context OS experiment status: `Not yet run`.

Label status: `complete_reported` for the first active `20260601_113121`
Lane B packet.

Prepared label packet:
[Post-Stage-1 Lane B 20260601_113121 Blinded Label Packet](../05_evaluation/label_packets/post_stage_1_lane_b_20260601_113121/README.md)
covers candidate `context_omission_error_rate` and
`working_set_relevance_score` items from the `20260601_113121` Lane A closure
run.
The first primary label batch has been collected, frozen, validated, and
reported in
[Post-Stage-1 Lane B 20260601_113121 Label Report](../05_evaluation/Post_Stage_1_Lane_B_20260601_113121_Label_Report_Skeleton.md).
It provides packet-level human-labeled omission and relevance evidence for the
named active packet only, with no validator-triggered adjudication records
required.

Planning bundle draft:
[Post-Stage-1 Context OS Planning Draft Spec](../02_specs/Post_Stage_1_Context_OS_Planning_Draft_Spec.md),
[Post-Stage-1 Context OS Schema Impact Review](../03_schemas/Post_Stage_1_Context_OS_Schema_Impact_Review.md),
and
[Post-Stage-1 Context OS Evaluation Plan](../04_experiments/Post_Stage_1_Context_OS_Evaluation_Plan.md)
use the `20260601_113121` Lane A closure run as input. They are planning
artifacts only. They use the active Lane B labels as planning evidence, but
they do not change schemas, implement runtime behavior, authorize memory writes
or learned retrieval, or validate H3.

The deterministic `20260719_224209` evaluation pilot validates this planning
bundle against the frozen Lane A and Lane B artifacts without rerunning a model
or OpenClaw. It uses an explicitly non-native, evaluation-only coordinator
attestation for the OpenClaw agent and embedded-context-only control fields
that were absent from the source run serialization. The pilot adds no Context
OS runtime module, action, schema, memory authority, or side-effect authority,
and it is not a new `accepted_by_closure` decision.

The earlier `20260530_141649` packet is superseded historical material only; it
must not be treated as the active accepted-run source for this gate.

Accepted unlock: Context OS specification and evaluation planning only.

## Inputs

This gate depends on the existing Stage 0 and Stage 1 context boundary stack:

- [Stage 0 Boundary Lock](Stage_0_Boundary_Lock.md)
- [Phase 5 Working Set Compiler Gate](Phase_5_Working_Set_Compiler_Gate.md)
- [Stage 1 Experiment 005 Closure](Stage_1_Experiment_005_Closure.md)
- [Context OS and Working Set Compiler Note](../02_specs/Context_OS_and_Working_Set_Compiler_Note.md)
- `PS1-G1` [Post-Stage-1 Larger Sample Plan](../04_experiments/Post_Stage_1_Larger_Sample_Plan.md)
- `PS1-G2` [Post-Stage-1 Metric Policy](../05_evaluation/Post_Stage_1_Metric_Policy.md)
- `PS1-G3` and `PS1-G4` [Post-Stage-1 Labeling Scope and Adjudication Policy](../05_evaluation/Post_Stage_1_Labeling_Scope_and_Adjudication_Policy.md)
- `PS1-G5` [Baseline Identity Plan](../04_experiments/Baseline_Identity_Plan.md)

The Experiment 005 local smoke closure is useful boundary evidence for
`Working Set Compiler v0`. It is not broad validation of H3 and not evidence
for full Context OS implementation or validation claims.

## Expansion Layers

| Layer | Status after this gate | Allowed work | Still blocked |
| --- | --- | --- | --- |
| `Working Set Compiler v0` | Current implemented scope | Continue deterministic, reference-backed working-set runs under accepted metrics and labels. | Claims of full Context OS or H3 validation. |
| Context OS specification planning | Unlocked by this gate | Write a future Context OS spec, schema impact review, experiment plan, metric/reporting policy, and explicit non-goals. | Runtime code, schema changes, memory writes, learned retrieval, or validation claims. |
| Context OS implementation | Not unlocked | None in this batch. | Requires a later implementation batch after specs, schemas, experiments, and evaluation rules are accepted. |
| Memory and side-effect escalation | Not unlocked | None in this gate. | `MEMORY_WRITE`, `COMMITTABLE`, and `IRREVERSIBLE` effects remain blocked by `PS1-G8` or a successor gate. |

## Required Before Moving Beyond v0

Work may move beyond deterministic `Working Set Compiler v0` only after all
conditions below are documented for the target Context OS planning step:

| Requirement | Required condition |
| --- | --- |
| Larger controlled working-set evidence | A measured larger controlled sample reports the working-set metrics required by `PS1-G2`, including omission, relevance, provenance, budget adherence, and long-task stability. |
| Label evidence | Policy-compliant human or secondary labels exist for omission, relevance, and provenance when the claim depends on subjective or oracle-sensitive context quality. |
| Baseline identity | Context baselines and treatments follow `PS1-G5`, including harness identity and matched budget reporting. |
| Process integrity | Unsupported commits remain `0`. Memory writes remain `0`. Disallowed side-effect classes remain `0`. |
| Artifact linkage | Run records, context artifacts, label packets, and summaries link to machine-readable artifacts and policy versions. |
| Interpretation boundary | Reports state whether evidence is fixture-oracle, structural, human, or secondary review and must not present local smoke or pilot results as H3 validation. |

If any requirement is missing, the work may be labeled only as a Context OS
planning draft or exploratory pilot, not as advancement evidence.

## Required Before Implementation

Before any full Context OS implementation batch begins, the repository must
add and accept all of these artifacts or their explicitly named successors:

- a Context OS spec that defines allowed inputs, outputs, selection policy
  boundaries, interaction with verifier and recovery, and rejection conditions
- a schema impact review that states whether `working_set.schema.json` is still
  sufficient or which new schema contracts are needed
- an experiment plan that fixes sample frame, baselines, treatment arms, budget
  controls, and artifact locations before execution
- metric and reporting rules that preserve the `PS1-G2` hard gates and identify
  any new Context OS metrics before results are reported
- labeling packet and adjudication rules for any human or secondary context
  quality labels not already covered by `PS1-LB-LABEL-001`
- explicit non-goals for memory writes, learned retrieval or ranking,
  compression, external side effects, production deployment, and H3 validation
  claims

The implementation batch must update specs, schemas, fixtures, runtime code,
tests, and reports together. This gate does not authorize partial schema enum
updates or runtime behavior that lacks accepted evidence and verifier paths.

## Non-goals

- This gate does not implement full Context OS.
- This gate does not validate H3.
- This gate itself did not collect labels or run a larger sample.
- This gate does not authorize learned retrieval, learned ranking, or learned
  compression.
- This gate does not authorize long-term memory governance, memory append, or
  `MEMORY_WRITE` effects.
- This gate does not authorize `COMMITTABLE` external effects,
  `IRREVERSIBLE` effects, or production deployment.
- This gate does not convert human labels into runtime approvals.
- This gate does not treat raw tool logs, full memory dumps, or larger context
  windows as Context OS.

## Reporting Requirements

Any future Context OS planning or evaluation artifact must report:

- `Gate policy version: PS1-LC-CTX-GATE-001`
- satisfied and open gate IDs
- baseline and treatment arm labels
- model, harness, prompt budget, response budget, and context budget
- fixture count and long-context fixture family coverage
- metric policy version and label policy version
- label source for omission, relevance, and provenance metrics
- unsupported commit count, memory-write count, and disallowed side-effect count
- result path, label packet path, and machine-readable artifact path
- interpretation boundaries

Reports that do not satisfy this gate must use labels such as
`Context OS planning draft`, `context evaluation pilot`, or
`Working Set Compiler v0 result without Context OS claim`.

## Related Documents

- [Project Manifest](Project_Manifest.md)
- [Post-Stage-1 Advancement Gate](Post_Stage_1_Advancement_Gate.md)
- [Post-Stage-1 Gate Inventory](Post_Stage_1_Gate_Inventory.md)
- [Phase 5 Working Set Compiler Gate](Phase_5_Working_Set_Compiler_Gate.md)
- [Stage 1 Experiment 005 Closure](Stage_1_Experiment_005_Closure.md)
- [Context OS and Working Set Compiler Note](../02_specs/Context_OS_and_Working_Set_Compiler_Note.md)
- [Post-Stage-1 Context OS Planning Draft Spec](../02_specs/Post_Stage_1_Context_OS_Planning_Draft_Spec.md)
- [Post-Stage-1 Context OS Schema Impact Review](../03_schemas/Post_Stage_1_Context_OS_Schema_Impact_Review.md)
- [Post-Stage-1 Context OS Evaluation Plan](../04_experiments/Post_Stage_1_Context_OS_Evaluation_Plan.md)
- [PS1-G7 Artifact-Backed Evaluation Pilot Run Report](../05_evaluation/Post_Stage_1_Context_OS_Evaluation_Pilot_Run_Report.md)
- [Post-Stage-1 Larger Sample Plan](../04_experiments/Post_Stage_1_Larger_Sample_Plan.md)
- [Post-Stage-1 Metric Policy](../05_evaluation/Post_Stage_1_Metric_Policy.md)
- [Post-Stage-1 Labeling Scope and Adjudication Policy](../05_evaluation/Post_Stage_1_Labeling_Scope_and_Adjudication_Policy.md)
- [Post-Stage-1 Lane B 20260601_113121 Label Report](../05_evaluation/Post_Stage_1_Lane_B_20260601_113121_Label_Report_Skeleton.md)
- [Baseline Identity Plan](../04_experiments/Baseline_Identity_Plan.md)
