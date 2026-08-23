# Post-Stage-1 Gate Inventory

## Purpose

This document is the tracking index for post-Stage-1 gate items. It records the
artifact status, proposed artifact path, routing dependencies, and downstream
unlocks for `PS1-G0` through `PS1-G10`.

This inventory is not an acceptance policy, experiment plan, validation report,
or replacement for [Post-Stage-1 Advancement Gate](Post_Stage_1_Advancement_Gate.md).
It does not accept gate artifacts and does not authorize larger samples, human
or secondary labels, runtime expansion, Context OS expansion, or side-effect
expansion.

## Scope

This inventory covers `PS1-G1` through `PS1-G10` as defined by
[Post-Stage-1 Advancement Gate](Post_Stage_1_Advancement_Gate.md). It retains
`PS1-G0` only as a met prerequisite so readers can see the full post-smoke
routing path.

This document does not redefine the gate items. The normative source remains
[Post-Stage-1 Advancement Gate](Post_Stage_1_Advancement_Gate.md) or a
successor manifest gate that explicitly supersedes it.

## Status Vocabulary

| Status | Meaning |
| --- | --- |
| `Open` | No required artifact exists yet. |
| `Drafting` | The required artifact is under development but has not been accepted by the gate. |
| `Ready for Review` | The artifact is formed, but routing, traceability, or export synchronization is incomplete. |
| `Accepted` | The required artifact exists and has been explicitly accepted by the manifest gate or successor gate. |
| `Superseded` | The item has been replaced by a later gate or document. |

## Gate Inventory Table

| Gate ID | Lane | Current status | Required artifact | Proposed artifact path | Upstream dependencies | Downstream unlocks | Must not claim |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `PS1-G0` | All lanes prerequisite | `Accepted` | Closure docs 001 through 005 and linked run reports | Existing closure docs and run reports | Stage 1 closure docs 001 through 005 | Post-Stage-1 planning can be routed through `PS1-G1` through `PS1-G8` | The five local smoke closures are not broad validation. |
| `PS1-G1` | Larger Controlled Samples | `Accepted` | [Post-Stage-1 Larger Sample Plan](../04_experiments/Post_Stage_1_Larger_Sample_Plan.md); G6-aware execution successor [Post-Stage-1 Larger Sample G6 Successor Plan](../04_experiments/Post_Stage_1_Larger_Sample_G6_Successor_Plan.md) | `docs/04_experiments/Post_Stage_1_Larger_Sample_Plan.md`; `docs/04_experiments/Post_Stage_1_Larger_Sample_G6_Successor_Plan.md` | `PS1-G0`; Document Ops benchmark; closure reports 001 through 005; `PS1-G6` local structured edit implementation | Larger controlled sample execution through `Vanta.PostStage1LargerSample`; input to `PS1-G2` | Acceptance claims require the accepted metric policy, measured results, and closure acceptance. |
| `PS1-G2` | Larger Controlled Samples | `Accepted` | [Post-Stage-1 Metric Policy](../05_evaluation/Post_Stage_1_Metric_Policy.md) | `docs/05_evaluation/Post_Stage_1_Metric_Policy.md` | `PS1-G1`; `PS1-G5`; metrics definition; closure reports 001 through 005 | Threshold-governed acceptance candidates for larger controlled samples | Passing thresholds is not broad validation and still requires measured run reports plus closure acceptance. |
| `PS1-G3` | Human or Secondary Labeling | `Accepted` | [Post-Stage-1 Labeling Scope and Adjudication Policy](../05_evaluation/Post_Stage_1_Labeling_Scope_and_Adjudication_Policy.md) | `docs/05_evaluation/Post_Stage_1_Labeling_Scope_and_Adjudication_Policy.md` | `PS1-G0`; Evidence Packet spec; Metrics Definition; labeling guides | Evidence sufficiency labeling can proceed under the fixed `PS1-LB-LABEL-001` scale; the first active `20260601_113121` packet now has frozen, validated, import-summarized, and reported primary evidence sufficiency labels | Evidence sufficiency labels for one active packet are not broad validation and do not validate H1-H5. |
| `PS1-G4` | Human or Secondary Labeling | `Accepted` | [Post-Stage-1 Labeling Scope and Adjudication Policy](../05_evaluation/Post_Stage_1_Labeling_Scope_and_Adjudication_Policy.md) | `docs/05_evaluation/Post_Stage_1_Labeling_Scope_and_Adjudication_Policy.md` | `PS1-G0`; `PS1-G3`; labeling guides | Broader subjective label claims can use the accepted review and adjudication policy after labels are collected; the first active `20260601_113121` packet now has frozen, validated, import-summarized, and reported primary labels at `docs/05_evaluation/label_packets/post_stage_1_lane_b_20260601_113121/` | Subjective metrics cannot support broad claims without policy-compliant packets, review, adjudication handling, and claim boundaries. |
| `PS1-G5` | Larger Controlled Samples | `Accepted` | [Baseline Identity Plan](../04_experiments/Baseline_Identity_Plan.md) | `docs/04_experiments/Baseline_Identity_Plan.md` | `PS1-G0`; OpenClaw local harness closure notes; Experiment 001 baseline records | Baseline arm naming for larger controlled samples; input to `PS1-G2` | OpenClaw harness results are not promoted to pure model-only baseline results. |
| `PS1-G6` | Broader Runtime Scope | `Accepted` | [Post-Stage-1 Runtime Scope Proposal](Post_Stage_1_Runtime_Scope_Proposal.md) | `docs/00_manifest/Post_Stage_1_Runtime_Scope_Proposal.md` | `PS1-G0`; Stage 1 scope boundaries; Execution IR, Evidence Packet, Commit/Abort/Replay specs | Local schema-backed implementation of `Document Ops Structured Edit Action Surface v0` | Local implementation and tests do not validate H1-H5 or authorize broader side-effect classes. |
| `PS1-G7` | Broader Runtime Scope | `Accepted; artifact-backed evaluation pilot complete; closure candidate prepared` | [Context OS Expansion Gate](Context_OS_Expansion_Gate.md); planning bundle [spec](../02_specs/Post_Stage_1_Context_OS_Planning_Draft_Spec.md), [schema impact review](../03_schemas/Post_Stage_1_Context_OS_Schema_Impact_Review.md), [evaluation plan](../04_experiments/Post_Stage_1_Context_OS_Evaluation_Plan.md), [pilot run report](../05_evaluation/Post_Stage_1_Context_OS_Evaluation_Pilot_Run_Report.md), and [evaluation-only closure candidate](Post_Stage_1_Context_OS_Evaluation_Pilot_Closure_Candidate.md) | Planning sources plus `docs/04_experiments/results/context_os_planning/20260719_224209/`, the pilot run report, and the manifest review candidate | `PS1-G0`; Phase 5 gate; Experiment 005 closure; Working Set Compiler note; `PS1-G1` through `PS1-G5` policies; `20260601_113121` accepted Lane A closure run; active frozen Lane B packet and coordinator-only post-freeze memo | Context OS specification/evaluation planning, deterministic artifact-backed evaluation tooling, and evaluation-only manifest review candidate preparation | Runtime implementation, schema changes, new closure authority or formal acceptance, full Context OS validation, learned retrieval, compression, memory governance, H3 validation, and production readiness are not authorized. |
| `PS1-G8` | Broader Runtime Scope | `Accepted; named planning pilot complete` | [Side-Effect Escalation Gate](Side_Effect_Escalation_Gate.md); first planning bundle [spec](../02_specs/Post_Stage_1_Side_Effect_Planning_Draft_Spec.md), [schema impact review](../03_schemas/Post_Stage_1_Side_Effect_Schema_Impact_Review.md), [evaluation plan](../04_experiments/Post_Stage_1_Side_Effect_Evaluation_Plan.md), and [measured planning report](../05_evaluation/Post_Stage_1_Side_Effect_Planning_Pilot_Run_Report.md) | Planning sources plus `docs/04_experiments/results/side_effect_planning/20260715_223158/` and `docs/05_evaluation/Post_Stage_1_Side_Effect_Planning_Pilot_Run_Report.md` | `PS1-G0`; Stage 1 side-effect allowances; Commit Abort Replay Semantics; Evidence Packet and Verifier Runtime | Planning validator, immutable fixtures, rerunnable runner, and complete named fixture-local Document Ops `COMMITTABLE` planning pilot | Runtime execution of `COMMITTABLE`, `IRREVERSIBLE`, or `MEMORY_WRITE` actions is not authorized; rollback must not be assumed; planning labels and fixture oracles are not runtime approvals; the pilot is not closure acceptance. |
| `PS1-G9` | Storage and Persistence Gate | `Accepted` | [Storage and Persistence Gate](Storage_and_Persistence_Gate.md), [Persistence and Recovery Semantics](../02_specs/Persistence_and_Recovery_Semantics.md), [schema impact review](../03_schemas/Post_Stage_1_Persistence_Schema_Impact_Review.md), [Experiment 006](../04_experiments/Experiment_006_Persistence_and_Recovery.md), [run report](../05_evaluation/Experiment_006_Persistence_and_Recovery_Run_Report.md), and [closure](Post_Stage_1_Persistence_v0_Closure.md) | `docs/00_manifest/Storage_and_Persistence_Gate.md`; `docs/02_specs/Persistence_and_Recovery_Semantics.md`; `docs/03_schemas/Post_Stage_1_Persistence_Schema_Impact_Review.md`; `docs/04_experiments/Experiment_006_Persistence_and_Recovery.md`; `docs/05_evaluation/Experiment_006_Persistence_and_Recovery_Run_Report.md`; `docs/00_manifest/Post_Stage_1_Persistence_v0_Closure.md` | `PS1-G0`; Stage 1 commit/replay contracts; `PS1-G6` fixture-local reversible edits; docs-local schema authority | `20260715_114209` is `accepted_by_closure`; named SQLite v0 is fixture-local persistence authority | Validation is limited to `Fixture-Local SQLite Persistence v0`; no production, distributed, durable-memory, external-side-effect, architecture, or H1-H5 claim. |
| `PS1-G10` | Fixture-local executable side effect | `Accepted; accepted_by_closure` | [Fixture-Local COMMITTABLE Execution Gate](Fixture_Local_Committable_Execution_Gate.md), [implementation spec](../02_specs/Fixture_Local_Committable_Document_Promotion_v0.md), [schema impact review](../03_schemas/Fixture_Local_Committable_Schema_Impact_Review.md), [Experiment 007](../04_experiments/Experiment_007_Fixture_Local_Committable_Execution.md), [run report](../05_evaluation/Experiment_007_Fixture_Local_Committable_Execution_Run_Report.md), and [closure](Post_Stage_1_Fixture_Local_Committable_v0_Closure.md) | G10 gate/spec/schema/protocol, 28 fixtures, run `20260716_020716`, report, implementation, tests, and closure | `PS1-G8`; accepted executable upstream decisions; `PS1-G9` closure | `validated for Fixture-Local COMMITTABLE Document Promotion v0`; one named action in marked ephemeral copied fixtures | No general planner authority, source/repository/user/external/production target, irreversible effect, memory write, distributed authority, production readiness, broad side-effect safety, or H1-H5 claim. |

## Dependency Order

- `PS1-G1`, `PS1-G2`, and `PS1-G5` are accepted and provide the Lane A sample,
  metric, and baseline identity policies.
- `PS1-LA-SAMPLE-002` is the G6-aware Lane A execution successor. It preserves
  the accepted 48-fixture sample size and 8-stratum shape while fixing
  structured-edit routing and runner artifacts for
  `Vanta.PostStage1LargerSample`.
- The first measured `PS1-LA-SAMPLE-002` run at
  `docs/04_experiments/results/post_stage_1_larger_sample/20260519_232854/`
  completed with threshold status `failed_no_acceptance`. It produced the
  required run artifacts, but the
  [run report](../05_evaluation/Post_Stage_1_Lane_A_20260519_232854_Run_Report.md)
  and
  [closure candidate](Post_Stage_1_Lane_A_20260519_232854_Closure_Candidate.md)
  record required-artifact, replay, and audit blockers. It is not
  `accepted_by_closure`.
- A repair-batch rerun at
  `docs/04_experiments/results/post_stage_1_larger_sample/20260522_012221/`
  also completed with threshold status `failed_no_acceptance`. It preserved
  process-integrity hard gates and fixed the repeated-step audit-ref collapse,
  but the
  [run report](../05_evaluation/Post_Stage_1_Lane_A_20260522_012221_Run_Report.md)
  and
  [closure candidate](Post_Stage_1_Lane_A_20260522_012221_Closure_Candidate.md)
  record remaining task-success, required-artifact, replay, and audit blockers.
  It is not `accepted_by_closure`.
- A compact fixture-alignment rerun at
  `docs/04_experiments/results/post_stage_1_larger_sample/20260523_223106/`
  completed with threshold status `pass_acceptance_candidate`. The
  [run report](../05_evaluation/Post_Stage_1_Lane_A_20260523_223106_Run_Report.md)
  and
  [closure candidate](Post_Stage_1_Lane_A_20260523_223106_Closure_Candidate.md)
  record valid required artifacts, replay consistency `1.0`, audit completeness
  `1.0`, and treatment task success `0.9583`. It is still not
  `accepted_by_closure` and does not validate H1-H5.
- A structured negative rejection alignment rerun at
  `docs/04_experiments/results/post_stage_1_larger_sample/20260525_223239/`
  completed with threshold status `pass_acceptance_candidate`. The
  [run report](../05_evaluation/Post_Stage_1_Lane_A_20260525_223239_Run_Report.md)
  and
  [closure candidate](Post_Stage_1_Lane_A_20260525_223239_Closure_Candidate.md)
  record valid required artifacts, replay consistency `1.0`, audit completeness
  `1.0`, treatment task success `0.9792`, one measured root-planner overshoot on
  `docops_ws_evidence_packet_001`, and a post-run focused repair that removes
  the extra disallowed `compute_hash` for future runs. It is still not
  `accepted_by_closure`; the focused repair is not a full 48-fixture v5 rerun
  and does not validate H1-H5.
- A full v5 rerun at
  `docs/04_experiments/results/post_stage_1_larger_sample/20260530_141649/`
  completed with threshold status `pass_acceptance_candidate`. The
  [run report](../05_evaluation/Post_Stage_1_Lane_A_20260530_141649_Run_Report.md)
  and
  [closure candidate](Post_Stage_1_Lane_A_20260530_141649_Closure_Candidate.md)
  record valid required artifacts, replay consistency `1.0`, audit completeness
  `1.0`, treatment task success `0.9792`, and full-run confirmation that the
  `docops_ws_evidence_packet_001` root planner no longer appends the extra
  disallowed `compute_hash`. One expected-rejected structured-selector fixture,
  `docops_struct_selector_missing_001`, still committed in the measured run.
  A later focused repair added a compact missing-selector rejection hint and a
  fixture-oracle selector-failure guard; targeted tests pass, but a 2026-05-31
  full rerun attempt timed out without producing a new complete artifact set.
  The run is not `accepted_by_closure` and does not validate H1-H5.
- A full selector-repair rerun at
  `docs/04_experiments/results/post_stage_1_larger_sample/20260601_113121/`
  completed with threshold status `pass_acceptance_candidate`. The
  [run report](../05_evaluation/Post_Stage_1_Lane_A_20260601_113121_Run_Report.md)
  and
  [closure](Post_Stage_1_Lane_A_20260601_113121_Closure.md)
  record valid required artifacts, replay consistency `1.0`, audit completeness
  `1.0`, commit integrity `1.0`, treatment task success `1.0000`, process
  integrity hard gates at `0`, and full-run confirmation that
  `docops_struct_selector_missing_001` now rejects the documented missing
  `section` selector. This run is accepted by manifest closure as
  `accepted_by_closure` for the named threshold-governed Lane A Document Ops
  sample. It does not validate H1-H5.
- `PS1-G3` and `PS1-G4` are accepted by
  [Post-Stage-1 Labeling Scope and Adjudication Policy](../05_evaluation/Post_Stage_1_Labeling_Scope_and_Adjudication_Policy.md).
  The first active Lane B primary label batch has been collected, frozen,
  validated, import-summarized, and reported for the `20260601_113121` packet.
- The active blinded Lane B packet for the `20260601_113121` Lane A closure run
  is prepared at
  `docs/05_evaluation/label_packets/post_stage_1_lane_b_20260601_113121/`,
  with a label report at
  `docs/05_evaluation/Post_Stage_1_Lane_B_20260601_113121_Label_Report_Skeleton.md`.
  It covers `evidence_sufficiency_score`, `context_omission_error_rate`, and
  `working_set_relevance_score` candidates. The first filled result file
  contains 40 real primary labels, records primary label freeze on 2026-06-05,
  validates with zero `needs_review` labels, zero adjudication triggers, and
  zero unhandled adjudication requirements, and has an import summary in the
  packet directory. This is Lane B labeled evaluation evidence for the named
  packet only; it does not validate H1-H5, authorize full Context OS, approve
  production readiness, or create runtime approval. Packet-local tooling remains
  evaluation tooling only and does not expand core schemas or runtime behavior.
- The earlier `20260530_141649` Lane B packet remains as a superseded
  historical packet only. It is not the current accepted-run Lane B source
  because the source run was not `accepted_by_closure` and its
  `docops_struct_selector_missing_001` item captured the pre-repair committed
  artifact.
- `PS1-G6` has a local schema-backed implementation of
  `Document Ops Structured Edit Action Surface v0`, including runtime code,
  schemas, fixtures, and tests. It remains fixture-local and does not create a
  measured validation claim.
- `PS1-G7` is accepted by
  [Context OS Expansion Gate](Context_OS_Expansion_Gate.md) for Context OS
  specification and evaluation planning only. It is separate from `PS1-G6`, and
  full Context OS implementation is not bundled with generic runtime scope
  expansion.
- The first `PS1-G7` planning bundle aligned to the `20260601_113121` Lane A
  closure run is routed through
  [Post-Stage-1 Context OS Planning Draft Spec](../02_specs/Post_Stage_1_Context_OS_Planning_Draft_Spec.md),
  [Post-Stage-1 Context OS Schema Impact Review](../03_schemas/Post_Stage_1_Context_OS_Schema_Impact_Review.md),
  and
  [Post-Stage-1 Context OS Evaluation Plan](../04_experiments/Post_Stage_1_Context_OS_Evaluation_Plan.md).
  Lane A working-set metrics support planning-level budget, provenance,
  omission, relevance, stability, and process-integrity statements. The first
  active Lane B packet now adds human-labeled omission and relevance evidence
  for the named packet, but the bundle remains planning-only and does not
  authorize implementation, schema changes, learned retrieval, memory writes,
  full Context OS validation, or H3 validation.
- The `20260719_224209` `PS1-G7` artifact-backed evaluation pilot validates the
  fixed controls, six fixture budgets, Lane A structural/oracle metrics, Lane B
  frozen human-label counts, post-freeze arm interpretation, reviewer-visible
  blinding, source hashes, and process floors without model or OpenClaw reruns.
  It is a completed evaluation-tooling result, not a full Context OS experiment
  or a new `accepted_by_closure` decision.
- The
  [PS1-G7 evaluation pilot closure candidate](Post_Stage_1_Context_OS_Evaluation_Pilot_Closure_Candidate.md)
  is prepared with status
  `Candidate: ready_for_evaluation_only_manifest_review`. It is a governance
  review artifact for the exact named pilot only. It records that the post-hoc
  `vanta-verifier` and `embedded_context_only` attestation does not block this
  narrow artifact-consistency candidate but does block stronger source-native
  execution-control, model-comparison, full Context OS, and H3 claims. It adds
  no downstream unlock, formal closure, or new acceptance authority.
- `PS1-G8` is accepted by
  [Side-Effect Escalation Gate](Side_Effect_Escalation_Gate.md) for
  side-effect specification and evaluation planning only. Runtime execution of
  `COMMITTABLE`, `IRREVERSIBLE`, or `MEMORY_WRITE` actions still requires later
  accepted specs, schemas, fixtures, runtime code, tests, and evaluation
  artifacts.
- The first `PS1-G8` side-effect planning bundle is routed through
  [Post-Stage-1 Side-Effect Planning Draft Spec](../02_specs/Post_Stage_1_Side_Effect_Planning_Draft_Spec.md),
  [Post-Stage-1 Side-Effect Schema Impact Review](../03_schemas/Post_Stage_1_Side_Effect_Schema_Impact_Review.md),
  and
  [Post-Stage-1 Side-Effect Evaluation Plan](../04_experiments/Post_Stage_1_Side_Effect_Evaluation_Plan.md).
  It defines a fixture-local Document Ops `COMMITTABLE` commit-proposal
  planning surface only. The `20260715_223158` measured pilot is complete with
  all 15 planning metrics at `1.0000` and all 16 process floors at `0`; see the
  [run report](../05_evaluation/Post_Stage_1_Side_Effect_Planning_Pilot_Run_Report.md).
  It does not authorize runtime execution, schema changes, approval collection,
  production readiness, or H5 validation.
- The 2026-07-16 upstream decisions close the action-shape, approval-schema,
  first-domain, successor-authorization, and supersession-evidence questions.
  The separately accepted `PS1-G10` gate now authorizes and implements the
  explicit `commit_fixture_document_candidate` path only in marked ephemeral
  copied fixtures. Run `20260716_020716` is a 28/28 passing acceptance
  candidate accepted by the named G10 closure; this inventory does not itself
  create or broaden the action-specific allowlist.
- `PS1-G9` is accepted as the storage/persistence successor gate. Its
  implementation, measured-run, and closure states remain separately tracked
  by [Storage and Persistence Gate](Storage_and_Persistence_Gate.md). Run
  `20260715_114209` passed every hard metric and required test command; the
  [closure](Post_Stage_1_Persistence_v0_Closure.md) now makes SQLite the named
  Fixture-Local Persistence v0 authority. This is not production or
  distributed persistence authority.

## Routing Rules

When a required post-Stage-1 artifact is added, update all relevant routing
surfaces in the same change:

- [Post-Stage-1 Advancement Gate](Post_Stage_1_Advancement_Gate.md)
- [Document Map](Document_Map.md)
- [Traceability Matrix](Traceability_Matrix.md)
- the relevant layer index or source document
- mirrored files in `chatgpt_docs/` when the changed source file is already
  mirrored there

Updating this inventory alone does not satisfy a gate. A gate item reaches
`Accepted` only when the required artifact exists and is explicitly accepted by
[Post-Stage-1 Advancement Gate](Post_Stage_1_Advancement_Gate.md) or a successor
manifest gate.
