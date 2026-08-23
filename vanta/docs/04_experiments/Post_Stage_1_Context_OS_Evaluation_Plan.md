# Post-Stage-1 Context OS Evaluation Plan

## Purpose

Define the minimum evaluation plan for Context OS planning under `PS1-G7`,
using the `20260601_113121` Lane A closure run as the measured input.

This plan now has one deterministic artifact-backed evaluation pilot result.
The pilot is not a new model run or a full Context OS experiment. It does not
change schemas, add runtime authority, or validate H3.

## Status

Plan ID: `PS1-LC-CTX-PLAN-001`.

Plan status: `artifact-backed G7 evaluation pilot complete`.

Gate policy version: `PS1-LC-CTX-GATE-001`.

Source Lane A run: `20260601_113121`.

Source threshold status: `pass_acceptance_candidate`.

Closure status: `accepted_by_closure` for the named Lane A Document Ops sample.

Lane B label status: `complete_reported` for the first active
`20260601_113121` packet.

Original model run status: `20260601_113121` completed and
`accepted_by_closure` for the named Lane A scope; it was not rerun by this
pilot.

Artifact-backed G7 evaluation pilot status: `complete` at
`docs/04_experiments/results/context_os_planning/20260719_224209/`.

Full Context OS experiment status: `Not yet run`.

Implementation status: evaluation-only tooling is implemented; full Context
OS implementation remains `Not authorized`.

The pilot used `artifact_backed_post_freeze_evaluation`, loaded the accepted
Lane A artifacts and active frozen Lane B packet, reconstructed only the
existing bounded raw-trace and unchanged `Working Set Compiler v0` context
selection artifacts, and issued zero model calls and zero OpenClaw measured
runs. The post-hoc coordinator control attestation records `vanta-verifier` and
`embedded_context_only` only for this evaluation interpretation; those fields
were not source-run-native metadata and create no runtime authority.

## Source Evidence

This plan uses:

- [Post-Stage-1 Lane A 20260601_113121 Run Report](../05_evaluation/Post_Stage_1_Lane_A_20260601_113121_Run_Report.md)
- [Post-Stage-1 Lane A 20260601_113121 Closure](../00_manifest/Post_Stage_1_Lane_A_20260601_113121_Closure.md)
- `docs/04_experiments/results/post_stage_1_larger_sample/20260601_113121/run.json`
- `docs/04_experiments/results/post_stage_1_larger_sample/20260601_113121/summary.md`
- `docs/04_experiments/results/post_stage_1_larger_sample/20260601_113121/fixture_inventory.md`
- [Post-Stage-1 Lane B 20260601_113121 Blinded Label Packet](../05_evaluation/label_packets/post_stage_1_lane_b_20260601_113121/README.md)
- [Post-Stage-1 Lane B 20260601_113121 Label Report](../05_evaluation/Post_Stage_1_Lane_B_20260601_113121_Label_Report_Skeleton.md)
- [Coordinator-only post-freeze context unblind memo](../05_evaluation/label_packets/post_stage_1_lane_b_20260601_113121/coordinator_only_post_freeze_context_unblind_memo.md)
- [Evaluation-only coordinator control attestation](context_os_planning_control_attestation.json)
- [PS1-G7 Artifact-Backed Evaluation Pilot Run Report](../05_evaluation/Post_Stage_1_Context_OS_Evaluation_Pilot_Run_Report.md)

## Evidence Already Supported By Lane A

| Evidence item | Baseline | Treatment | Interpretation |
| --- | ---: | ---: | --- |
| `working_set_budget_adherence` | `1.0000` | `1.0000` | Structural budget checks can be routed through existing run artifacts. |
| `working_set_provenance_completeness` | `0.6667` | `1.0000` | Treatment provenance completeness is supported structurally. |
| `context_omission_error_rate` | `0.7778` | `0.0000` | Fixture-oracle or structural omission scoring supports planning, not human-labeled claims. |
| `working_set_relevance_score` | `0.2167` | `0.9667` | Fixture-oracle or structural relevance scoring supports planning, not broad Context OS validation. |
| `long_task_stability` | `1.0000` | `1.0000` | Long-context tasks remained stable under the measured treatment. |
| Unsupported commits | `0` | `0` | Process-integrity floor held. |
| Memory writes | `0` | `0` | No memory-write expansion occurred. |
| Disallowed side-effect classes | `0` | `0` | No side-effect expansion occurred. |

The treatment working-set stratum covered six long-context fixtures:

- `docops_ws_evidence_packet_001`
- `docops_ws_irrelevant_context_001`
- `docops_ws_omission_trap_001`
- `docops_ws_recovery_context_001`
- `docops_ws_traceability_long_001`
- `docops_ps1_ws_structured_edit_context_001`

## Lane B Label Evidence And Remaining Gaps

The first active Lane B label report now provides packet-level human-labeled
context-quality evidence for the blinded working-set items:

| Evidence item | Current status |
| --- | --- |
| Human-labeled context omission results | Available for the named active packet: `context_omission_error_rate = 0.3684` (`14 / 38`) across blinded working-set items. |
| Human-labeled working-set relevance results | Available for the named active packet: `working_set_relevance_score = 0.7742` (`24 / 31`) across blinded working-set items. |
| Post-freeze arm interpretation | Available only in the coordinator-only unblind memo. It maps the blinded arms to the bounded raw-trace context baseline and `Working Set Compiler v0` treatment after primary label freeze, and must not be copied into reviewer-visible packet records. |
| Broader context-quality interpretation | Limited to the named active packet; raw agreement counts are reported because the sample is small. |
| Context OS expansion evidence beyond v0 | A later accepted spec, schema decision, fixed arms, and measured run. |
| H3 validation | Not available from this planning batch. |

## Planned Arms

This plan preserves the existing `PS1-G5` baseline identity boundary.

| Arm role | Label | Status |
| --- | --- | --- |
| Context baseline | `raw_trace_bounded_openclaw_agent_local/<model>_matched_budget` | Existing Lane A arm family. |
| Current treatment | `working_set_compiler_v0_reference_backed_openclaw_agent_local/<model>_matched_budget` | Existing `Working Set Compiler v0` arm family. |
| Future Context OS candidate | To be named by a later accepted spec. | Placeholder only; not executable in this plan. |

No arm may be labeled `context_os` unless a later accepted spec defines the
capability and the report states the implementation boundary. OpenClaw local
harness arms must not be reported as pure model-only baselines.

## Fixed Controls For The Artifact-Backed Pilot

The completed pilot validates these exact frozen controls:

- model: `openai-codex/gpt-5.4-mini`
- harness: `openclaw_agent_local`
- context planner adapter: `Vanta.OpenClawContextPlannerAdapter`
- OpenClaw agent: `vanta-verifier`, from the evaluation-only post-hoc
  coordinator attestation rather than source-run-native metadata
- prompt / response budgets: `20000` / `12000` characters
- response format: `json_only`
- action / recovery attempt limits: `6` / `1`
- tool policy: `embedded_context_only`, checked against the attested adapter
  source hash and required no-tool/embedded-context fragments
- exact baseline arm:
  `raw_trace_bounded_openclaw_agent_local/openai-codex/gpt-5.4-mini_matched_budget`
- exact treatment arm:
  `working_set_compiler_v0_reference_backed_openclaw_agent_local/openai-codex/gpt-5.4-mini_matched_budget`

The source run's global context budget is `null`, with the explicit pilot
semantics `uses_frozen_per_fixture_budgets`. The complete frozen map is:

| Fixture | Context budget (characters) |
| --- | ---: |
| `docops_ws_evidence_packet_001` | 260 |
| `docops_ws_irrelevant_context_001` | 240 |
| `docops_ws_omission_trap_001` | 250 |
| `docops_ws_recovery_context_001` | 270 |
| `docops_ws_traceability_long_001` | 280 |
| `docops_ps1_ws_structured_edit_context_001` | 320 |

## Fixed Controls For A Future Full Context OS Run

Any future Context OS evaluation run using this plan must fix before execution:

- model identity
- harness identity
- planner, verifier, recovery, and context-planner adapter identities
- prompt character budget
- response character budget
- selected-context budget or an explicit `null` value with rationale
- action-attempt limit
- recovery-attempt limit
- allowed action set
- baseline and treatment arm labels
- compute matching rule
- label policy version and label source
- artifact output path

## Required Metrics

Future reports must include at minimum:

| Metric | Required source |
| --- | --- |
| `working_set_budget_adherence` | Automated structural check. |
| `working_set_provenance_completeness` | Automated structural check, with secondary review if source resolution is disputed. |
| `context_omission_error_rate` | Fixture oracle for Lane A; human, secondary review, or double-human adjudicated for broader Lane B claims. |
| `working_set_relevance_score` | Fixture oracle for Lane A; human, secondary review, or double-human adjudicated for broader Lane B claims. |
| `long_task_stability` | Automated structural and task-outcome checks. |
| unsupported commit count | Must remain `0`. |
| memory-write count | Must remain `0`. |
| disallowed side-effect count | Must remain `0`. |

If human or secondary labels are missing, the report must label subjective
context-quality metrics as fixture-oracle, automated structural, or
`Not yet run`, as applicable.

## Artifact Contract

The completed artifact-backed pilot writes artifacts under this contract; a
future authorized run must use an independently timestamped directory under
the same result family:

```text
docs/04_experiments/results/context_os_planning/<timestamp>/
```

Required files:

- `run.json`
- `summary.md`
- `fixture_inventory.md`
- `context_artifact_inventory.md`
- `label_packet_ref.md` or a link to the applicable Lane B packet

The pilot contract is evaluation-local and does not add a core schema. The
exact machine-readable runtime schema remains the current schema set unless a
later schema batch is accepted.

## Pre-Run Gates For A Future Full Context OS Experiment

A future Context OS evaluation run must not start until:

| Gate | Required condition |
| --- | --- |
| `PS1-G7` | Context OS planning remains inside `PS1-LC-CTX-GATE-001`. |
| Schema review | The schema impact review is accepted as no-change or superseded by an accepted schema batch. |
| Label boundary | Any human or secondary context-quality claim has a packet and review path under `PS1-LB-LABEL-001`. |
| Baseline identity | Arm labels satisfy `PS1-G5`. |
| Process integrity | Unsupported commits, memory writes, and disallowed side-effect classes are expected to remain `0`. |
| Implementation boundary | Any future candidate arm has an accepted implementation spec before execution. |

## Reporting Labels

Allowed report labels after the first active Lane B packet:

- `Context OS planning draft`
- `context evaluation pilot`
- `Working Set Compiler v0 result without Context OS claim`
- `Lane B packet-level context-quality evidence`

Disallowed report labels in this plan:

- Context OS `accepted_by_closure`
- `H3 validated`
- `full Context OS validated`
- `learned retrieval validated`
- `memory governance validated`
- `production ready`
- reviewer-visible packet records containing post-freeze arm identity mapping

## Non-goals

- The completed pilot is a post-freeze artifact evaluation, not a new model or
  OpenClaw measured experiment.
- This plan itself did not collect Lane B labels.
- This plan does not change schemas.
- This plan does not implement full Context OS.
- This plan does not authorize learned retrieval, learned ranking, or
  compression.
- This plan does not authorize memory writes or memory governance.
- This plan does not authorize `COMMITTABLE` or `IRREVERSIBLE` side effects.
- This plan does not validate H3.

## Related Documents

- [Post-Stage-1 Context OS Planning Draft Spec](../02_specs/Post_Stage_1_Context_OS_Planning_Draft_Spec.md)
- [Post-Stage-1 Context OS Schema Impact Review](../03_schemas/Post_Stage_1_Context_OS_Schema_Impact_Review.md)
- [Context OS Expansion Gate](../00_manifest/Context_OS_Expansion_Gate.md)
- [Context OS and Working Set Compiler Note](../02_specs/Context_OS_and_Working_Set_Compiler_Note.md)
- [Post-Stage-1 Lane A 20260601_113121 Run Report](../05_evaluation/Post_Stage_1_Lane_A_20260601_113121_Run_Report.md)
- [Post-Stage-1 Labeling Scope and Adjudication Policy](../05_evaluation/Post_Stage_1_Labeling_Scope_and_Adjudication_Policy.md)
- [Post-Stage-1 Lane B 20260601_113121 Label Report](../05_evaluation/Post_Stage_1_Lane_B_20260601_113121_Label_Report_Skeleton.md)
- [Coordinator-only post-freeze context unblind memo](../05_evaluation/label_packets/post_stage_1_lane_b_20260601_113121/coordinator_only_post_freeze_context_unblind_memo.md)
- [Evaluation-only coordinator control attestation](context_os_planning_control_attestation.json)
- [PS1-G7 Artifact-Backed Evaluation Pilot Run Report](../05_evaluation/Post_Stage_1_Context_OS_Evaluation_Pilot_Run_Report.md)
