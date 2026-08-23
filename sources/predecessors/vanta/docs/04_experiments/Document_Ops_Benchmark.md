# Document Ops Benchmark

## Purpose

Define a candidate controlled benchmark domain for evaluating Vanta without irreversible external side effects.

## Scope

Document operations tasks should require multi-step reasoning, source tracking, action execution, evidence collection, verification, and audit.

## Candidate Task Families

- Translate a source document while preserving structure.
- Refactor a document tree without deleting originals.
- Extract traceability links across multiple documents.
- Apply structured edits and verify no source content was lost.
- Detect inconsistent terminology across specifications.

## Required Logs

- Benchmark task record.
- Execution steps.
- Evidence packets.
- Verifier outputs.
- Episode journal.
- Human labels, where needed.

## Success Criteria

- Task output satisfies the task-specific acceptance criteria.
- No source document is modified unless explicitly required.
- Evidence is sufficient to audit important transformations.
- Replay metadata is complete enough for postmortem review.

## Failure Criteria

- Source content is omitted or distorted.
- Unsupported validation claims are introduced.
- Required provenance is missing.
- The runtime commits an invalid or unsafe action.

## Stage 1 Fixture Sets

Document Ops fixtures are prepared under
`docs/04_experiments/fixtures/document_ops/` and mirrored under
`test/fixtures/document_ops/`.

### Initial Seven-Fixture Smoke Set

The initial local smoke set contains:

- `docops_read_traceability_001`
- `docops_detect_terms_001`
- `docops_simulate_patch_001`
- `docops_reversible_edit_001`
- `docops_action_not_allowed_001`
- `docops_path_escape_001`
- `docops_wrong_diff_001`

These fixtures include positive and negative Stage 1 acceptance cases. They are
the historical seven-fixture local smoke set used by Experiments 001, 002, and
003. They supported the minimal loop, verifier hardening, and journal/replay
local smoke closures.

The initial seven-fixture smoke set is not a broad benchmark. It provides a small
controlled Document Ops spine for local smoke evidence and regression checks
only.

### Expanded Document Ops Fixture Set

The expanded fixture set begins after the Experiment 001, 002, and 003 local
smoke closures. Its first purpose is not to increase sample size in isolation,
but to add failure and recovery-relevant shapes needed before Phase 4 Targeted
Recovery:

- Multi-step commit cases.
- Rollback failure cases.
- Audit gap cases.
- Compensable action cases.

Expanded fixtures may change current fixture counts, review item counts, and
invalid action rates. Tests and runners should compute those values from fixture
directories and acceptance metadata rather than treating the initial seven-item
smoke set as a fixed constant.

Current expanded fixtures:

- `docops_multistep_commit_001`: three-step read/simulate/diff commit path for
  journal, evidence, verifier, and replay coverage without source mutation.
- `docops_rollback_failure_001`: reversible patch with missing backup metadata
  that forces rollback failure and targeted reconstruction from diff.
- `docops_audit_gap_001`: supplied journal and artifacts where evidence and
  verifier refs are missing and must be repaired from supplied artifacts.
- `docops_compensable_action_001`: fixture-local compensable receipt that
  requires compensation treatment rather than strict rollback.

### Phase 5 Working Set Fixture Set

The Phase 5 fixture set is selected by the presence of
`expected/working_set_acceptance.json`. It is designed to test bounded raw trace
against `WorkingSet` artifacts under fixed OpenClaw local smoke controls:

- `docops_ws_traceability_long_001`: multi-document traceability refs.
- `docops_ws_evidence_packet_001`: task requires Evidence Packet refs.
- `docops_ws_irrelevant_context_001`: distracting irrelevant refs.
- `docops_ws_omission_trap_001`: required context appears after raw-trace
  budget pressure.
- `docops_ws_recovery_context_001`: recovery context must be included.

### Post-Stage-1 Larger Controlled Sample Frame

[Post-Stage-1 Larger Sample Plan](Post_Stage_1_Larger_Sample_Plan.md) defines
the accepted `PS1-G1` sample frame for the first Lane A larger controlled
Document Ops sample.

[Post-Stage-1 Larger Sample G6 Successor Plan](Post_Stage_1_Larger_Sample_G6_Successor_Plan.md)
defines the G6-aware execution frame `PS1-LA-SAMPLE-002` for the Lane A runner.
It preserves the 48-fixture frame and explicitly routes structured-edit
fixtures into the behavioral strata below.

The execution sample contains 48 fixtures across eight strata:

- traceability extraction
- terminology consistency
- simulated patch and diff
- reversible edit and commit
- invalid action and path guard
- evidence and verifier challenge
- journal, replay, and recovery
- working-set long context

This frame supports fixture construction, controlled data-collection planning,
and future threshold-governed acceptance candidates under the accepted `PS1-G2`
metric policy. It is not a completed run, broad benchmark coverage, or MVP
acceptance claim by itself.

The repository now contains the 48 mirrored docs/test fixtures required by the
G6-aware execution frame. The dedicated runner is `Vanta.PostStage1LargerSample`
and writes Lane A results under
`docs/04_experiments/results/post_stage_1_larger_sample/<timestamp>/`.

### Results and Label Packet Navigation

Lane A result artifacts are preserved under:

```text
docs/04_experiments/results/post_stage_1_larger_sample/<timestamp>/
```

The `accepted_by_closure` Lane A closure run for the named threshold-governed
Document Ops larger controlled sample is:

```text
docs/04_experiments/results/post_stage_1_larger_sample/20260601_113121/
```

Earlier Lane A result directories remain historical provenance records,
including failed runs, threshold-passing candidates that were not accepted by
closure, and timed-out or superseded attempts.

Lane B label packets are evaluation artifacts under:

```text
docs/05_evaluation/label_packets/
```

The active reported packet is
`post_stage_1_lane_b_20260601_113121/`. The
`post_stage_1_lane_b_20260530_141649/` packet remains superseded historical
provenance because its source run was not `accepted_by_closure`.

## Status

Fixture set prepared with deterministic acceptance recipes and exercised by:

- Experiment 001 minimal loop local smoke closure on 2026-05-03.
- Experiment 002 verifier hardening local smoke closure on 2026-05-04.
- Experiment 003 journal/replay local smoke closure on 2026-05-04.
- Experiment 004 targeted recovery local smoke closure on 2026-05-06.
- Experiment 005 working-set compiler local smoke closure on 2026-05-07.

The current status is local smoke support for Stage 1 plus measured Phase 4
targeted recovery smoke coverage on three controlled recovery fixtures and
measured Phase 5 working-set smoke coverage on five controlled long-context
fixtures.

The post-Stage-1 larger-sample frame is implemented as a 48-fixture controlled
sample with a dedicated runner. The `20260601_113121` Lane A larger controlled
sample is `accepted_by_closure` for the named threshold-governed Document Ops
Lane A sample after full-run coverage of the
`docops_struct_selector_missing_001` repair.

This acceptance is limited to that named threshold-governed Document Ops Lane A
sample. It does not validate H1-H5, authorize full Context OS, authorize memory
writes or irreversible effects, approve production readiness, or promote local
harness results to pure model-only baselines.

## Related Documents

- [Benchmark Task Format](Benchmark_Task_Format.md)
- [Metrics Definition](../05_evaluation/Metrics_Definition.md)
- [Stage 1 Experiment 001 Closure](../00_manifest/Stage_1_Experiment_001_Closure.md)
- [Stage 1 Experiment 002 Closure](../00_manifest/Stage_1_Experiment_002_Closure.md)
- [Stage 1 Experiment 003 Closure](../00_manifest/Stage_1_Experiment_003_Closure.md)
- [Stage 1 Experiment 004 Closure](../00_manifest/Stage_1_Experiment_004_Closure.md)
- [Experiment 004 Targeted Recovery](Experiment_004_Targeted_Recovery.md)
- [Experiment 005 Working Set Compiler](Experiment_005_Working_Set_Compiler.md)
- [Stage 1 Experiment 005 Closure](../00_manifest/Stage_1_Experiment_005_Closure.md)
- [Post-Stage-1 Larger Sample Plan](Post_Stage_1_Larger_Sample_Plan.md)
- [Post-Stage-1 Larger Sample G6 Successor Plan](Post_Stage_1_Larger_Sample_G6_Successor_Plan.md)
- [Post-Stage-1 Lane A 20260601_113121 Run Report](../05_evaluation/Post_Stage_1_Lane_A_20260601_113121_Run_Report.md)
- [Post-Stage-1 Lane A 20260601_113121 Closure](../00_manifest/Post_Stage_1_Lane_A_20260601_113121_Closure.md)
- [Post-Stage-1 Lane B 20260601_113121 Blinded Label Packet](../05_evaluation/label_packets/post_stage_1_lane_b_20260601_113121/README.md)
- [Baseline Identity Plan](Baseline_Identity_Plan.md)
- [Post-Stage-1 Metric Policy](../05_evaluation/Post_Stage_1_Metric_Policy.md)
