# Project Manifest

## Purpose

Vanta is a research and engineering program for an agent runtime centered on learned cognition, executable action, evidence, verification, context governance, memory discipline, failure attribution, and replay-safe execution.

This manifest defines the documentation system and prevents theory documents from directly controlling implementation without passing through specs, schemas, experiments, and evaluation.

## Documentation Layers

| Layer | Directory | Role |
| --- | --- | --- |
| L0 | `00_manifest` | Governance, scope, traceability, terminology, and document operations |
| L1 | `01_theory` | Source theory, research hypotheses, validation review, and alternative theories |
| L2 | `02_specs` | Implementable MVP specifications derived from the theory layer |
| L3 | `03_schemas` | Interoperable runtime, benchmark, and evaluation data contracts |
| L4 | `04_experiments` | Benchmark and ablation experiment design |
| L5 | `05_evaluation` | Metrics, labeling guides, and report templates |
| L6 | `06_engineering` | Architecture, module planning, timeline, and testing strategy |

## Governance Rules

- `Design_Theory.md` is the conceptual source of truth, not an implementation spec.
- `Validation_and_Refutation_Report.md` is an evidence and risk review, not proof of validation.
- Engineering work must be justified by specs, schemas, and tests, not by theory prose alone.
- Experimental claims must remain `TODO`, `Not yet run`, or `Open Questions` until measured.
- Cross-document open questions route through [Open Questions Index](Open_Questions_Index.md); the index classifies blockers but does not replace source documents, gates, decisions, specs, schemas, or evaluation reports.
- Changes to core concepts must update the traceability matrix and decision log.

## MVP Positioning

The MVP should focus on the minimal closed loop:

```text
state -> plan -> action -> evidence -> verify -> commit / abort
```

Targeted recovery, Context OS, long-term memory governance, and advanced execution governance should be staged after the minimal loop has measurable behavior.

After the five Stage 1 local smoke closures, advancement beyond local smoke is
controlled by [Post-Stage-1 Advancement Gate](Post_Stage_1_Advancement_Gate.md).
The closures are prerequisites for larger samples, human or secondary labeling,
and broader runtime scope. They are not validation by themselves.

Lane A planning has accepted `PS1-G1` and `PS1-G5`: the first larger controlled
Document Ops frame is 48 fixtures, and OpenClaw remains a local harness baseline
supplemented by separately named direct API arms when available. Lane A metric
thresholds are accepted by `PS1-G2`, so larger-sample runs can become
threshold-governed acceptance candidates after measured results and closure
acceptance.

Lane B labeling policy has accepted `PS1-G3` and `PS1-G4`: evidence
sufficiency labels use the `PS1-LB-LABEL-001` five-level scale, and subjective
or oracle-sensitive labels require the documented review and adjudication path.
The first active post-Stage-1 human label batch has been collected for the
`20260601_113121` Lane B packet.

The active blinded Lane B packet was prepared from the `20260601_113121` Lane A
closure run:
[Post-Stage-1 Lane B 20260601_113121 Blinded Label Packet](../05_evaluation/label_packets/post_stage_1_lane_b_20260601_113121/README.md),
with a companion
[label report](../05_evaluation/Post_Stage_1_Lane_B_20260601_113121_Label_Report_Skeleton.md).
It covers candidate artifacts for `evidence_sufficiency_score`,
`context_omission_error_rate`, and `working_set_relevance_score`. The reported
first primary label batch contains 40 real raw labels: 16
`evidence_sufficiency_score` labels and 24 `working_set_context` labels. The
primary labels were frozen on 2026-06-05 before fixture oracle metadata,
`task.json` oracle fields, arm identity mapping, Lane A item results, or
post-run repair notes were exposed. The filled result file validates with zero
`needs_review` labels, zero adjudication-required triggers, and zero unhandled
adjudication requirements, and an import summary is available in the packet
directory. The labels are reported in the companion label report. This is
`20260601_113121` active packet Lane B labeled evaluation
evidence only; it does not validate H1-H5, authorize full Context OS, approve
production readiness, create runtime approval, or expand core schemas.
Packet-local result and validator/import-summary tooling remain evaluation
tooling only and do not expand runtime behavior, core schemas, or approval
paths.
The primary-labeler-visible allowlist for this packet was frozen on
2026-06-03 in the packet-local coordinator freeze record; this allowlist freeze
is separate from the 2026-06-05 primary label freeze.

The earlier `20260530_141649` Lane B packet remains only as a superseded
historical packet for a non-accepted source run whose selector-missing item
captured the pre-repair committed artifact.

Lane C has implemented the `PS1-G6` local runtime batch:
[Post-Stage-1 Runtime Scope Proposal](Post_Stage_1_Runtime_Scope_Proposal.md)
names `Document Ops Structured Edit Action Surface v0`; the G6 batch adds
schema-backed fixture-local `READ_ONLY`, `SIMULATED`, and `REVERSIBLE`
structured edit actions, fixtures, and local tests. It does not approve full
Context OS, expand side-effect classes, collect measured experiment results, or
validate H1-H5.

Lane A has a G6-aware execution successor frame:
[Post-Stage-1 Larger Sample G6 Successor Plan](../04_experiments/Post_Stage_1_Larger_Sample_G6_Successor_Plan.md)
defines `PS1-LA-SAMPLE-002` as the 48-fixture, 8-stratum execution frame for
larger controlled sample runs after structured edit implementation. The local
runner `Vanta.PostStage1LargerSample` can produce `run.json`, `summary.md`, and
`fixture_inventory.md` under
`docs/04_experiments/results/post_stage_1_larger_sample/<timestamp>/` and can
only report `blocked_missing_metric`, `failed_no_acceptance`, or
`pass_acceptance_candidate` before manifest closure. The first measured
`PS1-LA-SAMPLE-002` run completed at
`docs/04_experiments/results/post_stage_1_larger_sample/20260519_232854/` with
threshold status `failed_no_acceptance`; the corresponding
[Post-Stage-1 Lane A 20260519_232854 Run Report](../05_evaluation/Post_Stage_1_Lane_A_20260519_232854_Run_Report.md)
and
[closure candidate](Post_Stage_1_Lane_A_20260519_232854_Closure_Candidate.md)
record required-artifact, replay, and audit blockers. It is not
`accepted_by_closure`. A repair-batch rerun completed at
`docs/04_experiments/results/post_stage_1_larger_sample/20260522_012221/` with
threshold status `failed_no_acceptance`; the corresponding
[Post-Stage-1 Lane A 20260522_012221 Run Report](../05_evaluation/Post_Stage_1_Lane_A_20260522_012221_Run_Report.md)
and
[closure candidate](Post_Stage_1_Lane_A_20260522_012221_Closure_Candidate.md)
record remaining task-success, required-artifact, replay, and audit blockers.
It is also not `accepted_by_closure`. A compact fixture-alignment rerun
completed at
`docs/04_experiments/results/post_stage_1_larger_sample/20260523_223106/`
with threshold status `pass_acceptance_candidate`; the corresponding
[Post-Stage-1 Lane A 20260523_223106 Run Report](../05_evaluation/Post_Stage_1_Lane_A_20260523_223106_Run_Report.md)
and
[closure candidate](Post_Stage_1_Lane_A_20260523_223106_Closure_Candidate.md)
record threshold-passing candidate status, residual expected-rejected fixture
follow-up, and the boundary that no `accepted_by_closure` or H1-H5 validation
claim is created.
A later rerun completed at
`docs/04_experiments/results/post_stage_1_larger_sample/20260525_223239/`
with threshold status `pass_acceptance_candidate`; the corresponding
[Post-Stage-1 Lane A 20260525_223239 Run Report](../05_evaluation/Post_Stage_1_Lane_A_20260525_223239_Run_Report.md)
and
[closure candidate](Post_Stage_1_Lane_A_20260525_223239_Closure_Candidate.md)
record a measured root-planner overshoot on `docops_ws_evidence_packet_001`
and a post-run focused repair that removes the extra disallowed `compute_hash`
for future runs. It is also not `accepted_by_closure`, and the focused repair is
not a substitute for a full 48-fixture v5 rerun.
A full v5 rerun completed at
`docs/04_experiments/results/post_stage_1_larger_sample/20260530_141649/`
with threshold status `pass_acceptance_candidate`; the corresponding
[Post-Stage-1 Lane A 20260530_141649 Run Report](../05_evaluation/Post_Stage_1_Lane_A_20260530_141649_Run_Report.md)
and
[closure candidate](Post_Stage_1_Lane_A_20260530_141649_Closure_Candidate.md)
record that the `docops_ws_evidence_packet_001` focused repair has been
exercised in a full 48-fixture measured run and that the prior extra
`compute_hash` overshoot no longer appears for that fixture. The run still has
one measured expected-rejected structured-selector failure on
`docops_struct_selector_missing_001`. A post-run focused repair now adds that
fixture to the compact structured-edit rejection prompt path and adds a
fixture-oracle selector-failure guard; targeted tests pass, but a full rerun
attempt on 2026-05-31 timed out without producing a new complete run artifact
set. The `20260530_141649` run is not `accepted_by_closure`, does not validate
H1-H5, and does not promote OpenClaw local harness arms to pure model-only
baselines.
A full selector-repair rerun completed at
`docs/04_experiments/results/post_stage_1_larger_sample/20260601_113121/`
with threshold status `pass_acceptance_candidate`; the corresponding
[Post-Stage-1 Lane A 20260601_113121 Run Report](../05_evaluation/Post_Stage_1_Lane_A_20260601_113121_Run_Report.md)
records treatment task success `1.0000`, replay consistency `1.0000`, audit
completeness `1.0000`, process-integrity hard gates at `0`, and measured
full-run coverage of the `docops_struct_selector_missing_001` repair. The
[Post-Stage-1 Lane A 20260601_113121 Closure](Post_Stage_1_Lane_A_20260601_113121_Closure.md)
accepts this measured run as `accepted_by_closure` for the named
threshold-governed Document Ops Lane A sample. It does not validate H1-H5,
authorize full Context OS, approve production readiness, authorize memory
writes or irreversible effects, or promote OpenClaw local harness arms to pure
model-only baselines.

Lane C has accepted `PS1-G7` for Context OS specification and evaluation
planning only:
[Context OS Expansion Gate](Context_OS_Expansion_Gate.md) defines the
conditions for moving beyond deterministic `Working Set Compiler v0`. It does
not implement full Context OS, change schemas, authorize learned retrieval or
compression, approve memory governance, or validate H3.

A first `PS1-G7` Context OS planning bundle has been aligned to the
`20260601_113121` Lane A closure run:
[Post-Stage-1 Context OS Planning Draft Spec](../02_specs/Post_Stage_1_Context_OS_Planning_Draft_Spec.md),
[Post-Stage-1 Context OS Schema Impact Review](../03_schemas/Post_Stage_1_Context_OS_Schema_Impact_Review.md),
and
[Post-Stage-1 Context OS Evaluation Plan](../04_experiments/Post_Stage_1_Context_OS_Evaluation_Plan.md).
The bundle records that Lane A working-set metrics support planning-level
budget, provenance, omission, relevance, stability, and process-integrity
statements for the measured run. The first active Lane B packet now adds
human-labeled context-quality evidence for the named `20260601_113121` packet:
combined `context_omission_error_rate = 0.3684` (`14 / 38`) and
`working_set_relevance_score = 0.7742` (`24 / 31`) across blinded working-set items, with
raw agreement counts reported because the sample is small. This updates the
planning evidence surface only; H3, learned retrieval, memory governance,
schema changes, runtime implementation, and full Context OS validation remain
blocked until later accepted specs, schemas, experiments, labels, and
implementation batches exist.

The first deterministic `PS1-G7` artifact-backed evaluation pilot is complete
at `docs/04_experiments/results/context_os_planning/20260719_224209/`, with
[run report](../05_evaluation/Post_Stage_1_Context_OS_Evaluation_Pilot_Run_Report.md).
It revalidates the accepted Lane A artifacts and active frozen Lane B packet
without rerunning a model or OpenClaw, reports exact per-fixture budgets and
arm-level Lane B raw counts, and preserves reviewer-visible blinding. The pilot
is evaluation tooling only: it creates no new closure decision, full Context
OS implementation, runtime action, schema authority, memory authority,
side-effect authority, H3 claim, or production-readiness claim.

The manifest-layer
[PS1-G7 evaluation pilot closure candidate](Post_Stage_1_Context_OS_Evaluation_Pilot_Closure_Candidate.md)
is now prepared with status
`Candidate: ready_for_evaluation_only_manifest_review`. It reviews only the
artifact consistency of the named `20260719_224209` pilot over the accepted
`20260601_113121` Lane A source and active frozen Lane B packet. It preserves
the residual limitation that `vanta-verifier` and `embedded_context_only` come
from a user-authorized post-hoc coordinator attestation rather than
source-run-native serialized metadata. The limitation does not block this
narrow candidate, but it blocks stronger source-native execution-control,
model-comparison, full Context OS, and H3 claims. No formal closure or new
`accepted_by_closure` status is created, and the G7 downstream unlock remains
unchanged.

Lane C has accepted `PS1-G8` for side-effect specification and evaluation
planning only:
[Side-Effect Escalation Gate](Side_Effect_Escalation_Gate.md) defines the
conditions for planning beyond Stage 1 side-effect allowances. It does not
authorize runtime execution of `COMMITTABLE`, `IRREVERSIBLE`, or
`MEMORY_WRITE` actions, change schemas, collect labels, run experiments,
approve production deployment, or validate H5.

The first `PS1-G8` side-effect planning bundle is now routed through
[Post-Stage-1 Side-Effect Planning Draft Spec](../02_specs/Post_Stage_1_Side_Effect_Planning_Draft_Spec.md),
[Post-Stage-1 Side-Effect Schema Impact Review](../03_schemas/Post_Stage_1_Side_Effect_Schema_Impact_Review.md),
and
[Post-Stage-1 Side-Effect Evaluation Plan](../04_experiments/Post_Stage_1_Side_Effect_Evaluation_Plan.md).
It defines a fixture-local Document Ops `COMMITTABLE` commit-proposal planning
surface only. The bundle does not add runtime actions, change schemas, execute
`COMMITTABLE`, `IRREVERSIBLE`, or `MEMORY_WRITE` effects, collect approvals,
run experiments, validate H5, approve production readiness, or create a runtime
approval path.

The formal `committable_docops_planning_pilot` completed at
`docs/04_experiments/results/side_effect_planning/20260715_223158/` with 10
fixtures. All 15 planning metrics passed at `1.0000`, including `8 / 8`
negative-fixture rejection-rule accuracy and `10 / 10` planning audit and
fixture-oracle conformance; all 16 process-integrity floors were `0`, including
actual `COMMITTABLE`, `IRREVERSIBLE`, and `MEMORY_WRITE` execution counts and
source-fixture mutation. The
[measured report](../05_evaluation/Post_Stage_1_Side_Effect_Planning_Pilot_Run_Report.md)
marks only this named planning pilot complete. It does not create closure
acceptance, validate H5 or executed side-effect safety, collect runtime
approval, authorize runtime effects, change schemas, or establish production
readiness.

On 2026-07-16, five upstream successor questions were resolved without
expanding runtime authority. Future approval records use standalone schema
authority plus typed Episode Journal refs; the future commit action is explicit
`commit_fixture_document_candidate`; the first domain is candidate promotion
inside explicitly marked ephemeral copied Document Ops fixtures; and only a
separately authored and accepted `Fixture-Local Document Commit Execution v0`
successor gate may authorize implementation and execution in that scope.
`fixture_commit_supersede` also has a fixed executable compensation-evidence
floor covering identity and hashes, append-only lineage, prior-artifact
retrieval, active-pointer transition, approval/verifier/evidence/journal refs,
idempotency and conflicts, restart, and replay. These are decisions and routing
constraints only: no gate, closure, schema, action, allowlist change, approval,
execution, or compensation evidence is created by this update.

Those decision-only constraints are historical upstream provenance. The later
separately accepted `PS1-G10` batch described below consumes them; it does not
retroactively change the authority of this decision-only update.

Lane C has accepted `PS1-G9` for the named `Fixture-Local SQLite Persistence
v0` implementation and measured evaluation path:
[Storage and Persistence Gate](Storage_and_Persistence_Gate.md) resolves the
storage backend, minimum replay fidelity, and Canonical State hash granularity.
The adapter abstraction, Memory/SQLite adapters, restart recovery,
idempotency, transactional state/journal pointer update, and deterministic
failure-injection runner are implemented. The complete Experiment 006 run at
`docs/04_experiments/results/persistence_and_recovery/20260715_114209/` is
`pass_acceptance_candidate` with 20/20 cases and every hard metric passing; the
earlier `20260715_114052` run remains `failed_no_acceptance` provenance.
The
[Post-Stage-1 Persistence v0 Closure](Post_Stage_1_Persistence_v0_Closure.md)
accepts the passing run as `accepted_by_closure` and records the exact claim
`validated for Fixture-Local SQLite Persistence v0`. This scope does not
validate H1-H5, the full architecture, production readiness, distributed
persistence, durable memory, full Context OS, external `COMMITTABLE`,
`IRREVERSIBLE`, or `MEMORY_WRITE` execution.

Lane D has accepted `PS1-G10` for the named `Fixture-Local COMMITTABLE Document
Promotion v0` implementation and measured evaluation path. The
[Fixture-Local COMMITTABLE Execution Gate](Fixture_Local_Committable_Execution_Gate.md)
adds one task-specific `commit_fixture_document_candidate` action, standalone
Approval Record, two-phase evidence/verifier contract, durable prepared intent,
SQLite logical commit, idempotency/conflict handling, restart recovery, strict
restore, audit, and replay only inside explicitly marked ephemeral copied
workspaces.

Experiment 007 run `20260716_020716` is `pass_acceptance_candidate`: 28/28
failure-injection fixtures and all 15 hard gates passed, and the source-fixture
tree hash remained unchanged. The
[run report](../05_evaluation/Experiment_007_Fixture_Local_Committable_Execution_Run_Report.md)
records the measured evidence. After the complete required command set passed,
the [G10 Closure](Post_Stage_1_Fixture_Local_Committable_v0_Closure.md)
accepted the named scope as `accepted_by_closure` and records only `validated
for Fixture-Local COMMITTABLE Document Promotion v0`. This scope does not
validate H1-H5, broad side-effect safety, production readiness,
source/repository/user/external targets, `IRREVERSIBLE`, `MEMORY_WRITE`,
durable memory, full Context OS, distributed transactions, or multi-process
authority.

The predecessor development diagnostic `20260716_015841` remains preserved as
`failed_no_acceptance` (27/28) provenance. Its missing-evidence and aggregate-
accounting failures were repaired in scope before the complete run was
repeated; it contributes no closure evidence.

## Source Documents

- [Design Theory](../01_theory/Design_Theory.md)
- [Validation and Refutation Report](../01_theory/Validation_and_Refutation_Report.md)
