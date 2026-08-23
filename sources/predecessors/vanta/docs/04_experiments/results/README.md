# Experiment Results

## Purpose

This directory is the navigation entry for Vanta experiment result artifacts.
It records where result families live and how to read their status without
moving historical provenance directories.

Result directories are evidence and provenance records. They are not theory
documents, not implementation orders, and not validation claims unless a
separate evaluation report and manifest closure say so.

## Result Families

| Family | Purpose | Status | Measured | Planning-only |
| --- | --- | --- | --- | --- |
| `experiment_001/` | Stage 1 minimal closed-loop local smoke run artifacts. | Historical Stage 1 local smoke family. The closure document, not this index, identifies the accepted local smoke result. | Yes, for completed compact run artifacts. Historical attempts remain provenance. | No |
| `experiment_002/` | Stage 1 evidence/verifier hardening local smoke run artifacts. | Historical Stage 1 local smoke family with completed and partial historical attempts. The closure document identifies the accepted local smoke result. | Yes, for completed compact run artifacts; partial directories remain provenance. | No |
| `experiment_003/` | Stage 1 commit, journal, and replay local smoke run artifacts. | Historical Stage 1 local smoke family. | Yes, for the completed local smoke result. | No |
| `experiment_004/` | Stage 1 targeted recovery local smoke run artifacts. | Historical Stage 1 local smoke family. | Yes, for the completed local smoke result. | No |
| `experiment_005/` | Stage 1 Working Set Compiler v0 local smoke run artifacts. | Historical Stage 1 local smoke family. | Yes, for the completed local smoke result. | No |
| `post_stage_1_larger_sample/` | Lane A larger controlled Document Ops sample run artifacts for `PS1-LA-SAMPLE-002`. | Active Lane A result family. It contains failed, threshold-passing candidate, superseded, timeout or partial, and closure-accepted provenance. | Yes, for completed run directories with `run.json`, `summary.md`, and `fixture_inventory.md`; not every directory is accepted. | No |
| `context_os_planning/` | `PS1-G7` deterministic artifact-backed Context OS planning evaluation artifacts. | `20260719_224209` is the complete post-freeze evaluation pilot over the accepted Lane A run and active frozen Lane B packet; its [evaluation-only closure candidate](../../00_manifest/Post_Stage_1_Context_OS_Evaluation_Pilot_Closure_Candidate.md) is prepared for manifest review. | Evaluation evidence only; no model or OpenClaw measured run occurred in this pilot. | Yes |
| `side_effect_planning/` | PS1-G8 side-effect planning scaffolds and measured planning-pilot artifacts. | `20260701_201804` is the historical scaffold; `20260715_223158` is the complete 10-fixture `committable_docops_planning_pilot`. | Planning validation only: all 15 planning metrics passed and all 16 process floors were `0`; no side-effect runtime execution occurred. | Yes |
| `persistence_and_recovery/` | `PS1-G9` Experiment 006 SQLite persistence and deterministic failure-injection artifacts. | Active persistence result family. `20260715_114052` is retained `failed_no_acceptance`; `20260715_114209` is the complete 20-case `pass_acceptance_candidate` used by measured report and closure review. | Yes. Deterministic protocol-boundary injection is measured; no OS-level process-kill claim. | No |
| `fixture_local_committable_execution/` | `PS1-G10` Experiment 007 approval, promotion, recovery, rollback, audit, and strict replay artifacts. | `20260716_015841` preserves a 27/28 `failed_no_acceptance` development diagnostic; repaired complete run `20260716_020716` is the 28-case `pass_acceptance_candidate` accepted by the named manifest closure. | Yes for the closure run; the predecessor is explicitly development-diagnostic provenance. | No |

## Accepted Closure Boundary

`post_stage_1_larger_sample/20260601_113121/` is accepted by manifest closure
only as the named threshold-governed Document Ops Lane A sample. Its runner
threshold status is `pass_acceptance_candidate`; the manifest closure upgrades
that named result to `accepted_by_closure`.

That acceptance does not validate H1-H5, authorize full Context OS, approve
production readiness, authorize memory writes, authorize irreversible effects,
authorize runtime execution of side-effect planning surfaces, or promote
OpenClaw local harness arms to pure model-only baselines.

The `context_os_planning/20260719_224209/` result completes only the named
artifact-backed `PS1-G7` evaluation pilot. It validates frozen controls,
source/fixture/context traceability, Lane A structural/oracle metrics, Lane B
human-label counts and post-freeze interpretation, reviewer-visible blinding,
process floors, and deterministic output. It is not a full Context OS
experiment, H3 validation, runtime or schema authority, production readiness,
or a new closure decision.

The
[PS1-G7 evaluation-only closure candidate](../../00_manifest/Post_Stage_1_Context_OS_Evaluation_Pilot_Closure_Candidate.md)
records the separate manifest review of this result with status
`Candidate: ready_for_evaluation_only_manifest_review`. It does not upgrade the
pilot to formal closure, create new `accepted_by_closure`, or expand the G7
downstream unlocks.

The `side_effect_planning/20260715_223158/` result completes only the named
planning pilot. It is not closure acceptance, runtime approval, executable
`COMMITTABLE` authority, H5 validation, side-effect safety validation, or
production readiness.

The `persistence_and_recovery/20260715_114209/` runner result is
`pass_acceptance_candidate` for the named Fixture-Local SQLite Persistence v0
surface. Only
[Post-Stage-1 Persistence v0 Closure](../../00_manifest/Post_Stage_1_Persistence_v0_Closure.md)
upgrades that named scope to `accepted_by_closure` and records `validated for
Fixture-Local SQLite Persistence v0`; predecessor `20260715_114052` remains
failed provenance.

The `fixture_local_committable_execution/20260716_020716/` runner result is
`pass_acceptance_candidate` with 28/28 fixtures and all 15 G10 hard gates
passing. The
[G10 Closure](../../00_manifest/Post_Stage_1_Fixture_Local_Committable_v0_Closure.md)
accepts only the named copied-fixture promotion surface as
`accepted_by_closure`; the runner result itself remains unchanged.

The earlier `fixture_local_committable_execution/20260716_015841/` directory is
retained unchanged as `failed_no_acceptance` development-diagnostic provenance.
Its missing-evidence case committed incorrectly and its aggregate calculations
also failed; it is not acceptance evidence.

## Provenance Retention

Historical, failed, superseded, timeout, and partial run directories are
provenance. They should not be deleted, renamed, moved, or rewritten to make the
tree look cleaner. Later reports may supersede their interpretation, but the
original directories remain useful for audit, regression, and source-to-report
traceability.

When a run directory contains raw logs, wrapper output, ignored JSON, or
scratch artifacts, preserve already-tracked provenance in place and follow the
artifact retention policy in
[Repository Structure](../../06_engineering/Repository_Structure.md). New
summary or closure claims must be made through evaluation or manifest documents,
not by mutating historical run artifacts.

## Related Documents

- [Document Ops Benchmark](../Document_Ops_Benchmark.md)
- [Post-Stage-1 Larger Sample G6 Successor Plan](../Post_Stage_1_Larger_Sample_G6_Successor_Plan.md)
- [Post-Stage-1 Side-Effect Evaluation Plan](../Post_Stage_1_Side_Effect_Evaluation_Plan.md)
- [Post-Stage-1 Lane A 20260601_113121 Run Report](../../05_evaluation/Post_Stage_1_Lane_A_20260601_113121_Run_Report.md)
- [Post-Stage-1 Lane A 20260601_113121 Closure](../../00_manifest/Post_Stage_1_Lane_A_20260601_113121_Closure.md)
- [Post-Stage-1 Context OS Evaluation Plan](../Post_Stage_1_Context_OS_Evaluation_Plan.md)
- [PS1-G7 Artifact-Backed Evaluation Pilot Run Report](../../05_evaluation/Post_Stage_1_Context_OS_Evaluation_Pilot_Run_Report.md)
- [PS1-G7 Evaluation Pilot Closure Candidate](../../00_manifest/Post_Stage_1_Context_OS_Evaluation_Pilot_Closure_Candidate.md)
- [Experiment 006 Persistence and Recovery](../Experiment_006_Persistence_and_Recovery.md)
- [Experiment 006 Persistence and Recovery Run Report](../../05_evaluation/Experiment_006_Persistence_and_Recovery_Run_Report.md)
- [Post-Stage-1 Persistence v0 Closure](../../00_manifest/Post_Stage_1_Persistence_v0_Closure.md)
- [Experiment 007 Fixture-Local COMMITTABLE Execution](../Experiment_007_Fixture_Local_Committable_Execution.md)
- [Experiment 007 Run Report](../../05_evaluation/Experiment_007_Fixture_Local_Committable_Execution_Run_Report.md)
- [G10 Closure](../../00_manifest/Post_Stage_1_Fixture_Local_Committable_v0_Closure.md)
