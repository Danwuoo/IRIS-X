# Post-Stage-1 Larger Sample Plan

## Purpose

Define the first larger controlled Document Ops sample after the five Stage 1
local smoke closures.

This document is the required artifact for `PS1-G1`. It defines the sample
frame, fixture count, fixture strata, inclusion rules, exclusion rules, and
minimum run controls for Lane A larger controlled samples.

It does not define MVP acceptance thresholds, validate any hypothesis, authorize
broader runtime scope, or approve production use.

## Status

Plan ID: `PS1-LA-SAMPLE-001`.

Status: `Accepted as PS1-G1 sample-frame artifact` on 2026-05-10.

Run status: `Not yet run`.

This plan may support fixture construction and controlled data collection after
the required run controls are fixed. Acceptance claims are governed by
[Post-Stage-1 Metric Policy](../05_evaluation/Post_Stage_1_Metric_Policy.md),
the accepted `PS1-G2` artifact, and still require measured results plus closure
acceptance.

Baseline arm identity is governed separately by
[Baseline Identity Plan](Baseline_Identity_Plan.md), the required artifact for
`PS1-G5`.

## Scope

The first larger controlled sample remains inside the Document Ops domain.

Allowed side-effect classes:

- `READ_ONLY`
- `SIMULATED`
- `REVERSIBLE`
- fixture-local `COMPENSABLE` only for recovery fixtures

Disallowed scope:

- non-Document-Ops domains
- `COMMITTABLE` external effects
- `IRREVERSIBLE` effects
- `MEMORY_WRITE` effects
- production deployment
- full Context OS beyond `Working Set Compiler v0`
- learned retrieval, learned ranking, or learned compression

## Sample Frame

The first larger controlled sample contains 48 Document Ops fixtures.

Each fixture must be represented as a `benchmark_task.schema.json` compatible
task record and must include deterministic acceptance metadata under the
fixture's `expected/` directory.

Fixture roots remain:

```text
docs/04_experiments/fixtures/document_ops/
test/fixtures/document_ops/
```

New fixtures should use a `docops_ps1_` task ID prefix unless a successor plan
defines a different naming convention.

## Strata

| Stratum | Fixture count | Primary coverage | Required fixture shape |
| --- | ---: | --- | --- |
| Traceability extraction | 6 | Minimal loop, source tracking, evidence refs | Read multiple source artifacts and emit traceability output without mutation. |
| Terminology consistency | 6 | Minimal loop, invalid action pressure, evidence sufficiency | Detect inconsistent terms across documents with explicit source refs. |
| Simulated patch and diff | 6 | Execution IR, simulated side effects, verifier postconditions | Produce a proposed patch or diff without mutating source artifacts. |
| Reversible edit and commit | 6 | Commit / abort, rollback metadata, journal integrity | Apply fixture-local reversible edits with complete backup metadata. |
| Invalid action and path guard | 6 | Safety rejection, verifier false-accept pressure | Include unsupported actions, path escape attempts, or disallowed source mutation. |
| Evidence and verifier challenge | 6 | Evidence Packet quality, verifier false accept / false reject analysis | Include missing evidence, wrong diff, stale provenance, or acceptance-oracle traps. |
| Journal, replay, and recovery | 6 | Replay consistency, audit completeness, targeted recovery | Include multi-step commit, rollback failure, audit gap, and compensable-action variants. |
| Working-set long context | 6 | `Working Set Compiler v0`, bounded raw trace comparison | Include required refs, irrelevant refs, omission traps, and recovery-context refs. |

Total: 48 fixtures.

## Inclusion Rules

Every fixture in this sample must satisfy all of these rules:

- The task is fixture-local and reproducible without external network effects.
- The task has deterministic success and failure criteria.
- The task record validates against `benchmark_task.schema.json`.
- Source artifacts, expected artifacts, and acceptance metadata are committed.
- Required logs include the runtime artifacts needed for the target stratum.
- Human or secondary labels are optional only when the metric is structural or
  fixture-oracle based.
- Any subjective or oracle-sensitive label must follow
  [Post-Stage-1 Labeling Scope and Adjudication Policy](../05_evaluation/Post_Stage_1_Labeling_Scope_and_Adjudication_Policy.md).
- The fixture exists under both `docs/04_experiments/fixtures/document_ops/`
  and `test/fixtures/document_ops/`.

## Exclusion Rules

Exclude a fixture from this sample when any of these conditions apply:

- It requires an irreversible, external, or production side effect.
- It requires a memory write or treats memory append as learning.
- It depends on full Context OS, learned retrieval, learned ranking, or learned
  compression.
- It cannot be evaluated without hidden manual judgment.
- Its oracle metadata is incomplete or ambiguous.
- It requires a tool interface not already covered by Stage 1 specs or a
  separately accepted scope gate.
- It changes source documents outside the fixture workspace.

## Fixed Controls Before Execution

Before a run is executed under this plan, the run record must fix:

- model identity
- harness identity
- planner adapter identity
- tool interface and allowed action set
- prompt template version
- prompt character budget
- response character budget
- action-attempt limit
- recovery-attempt limit when recovery fixtures are included
- context budget when working-set fixtures are included
- compute-matching rule for every compared arm
- fixture list and fixture hash inventory
- result directory

OpenClaw local harness runs must remain labeled as OpenClaw harness results.
Direct Responses API results must be emitted as separately named arms according
to [Baseline Identity Plan](Baseline_Identity_Plan.md).

## Artifact Contract

Minimum required artifacts for a larger controlled run:

| Artifact | Required location | Contract |
| --- | --- | --- |
| Fixture task records | `docs/04_experiments/fixtures/document_ops/<task_id>/task.json` and mirrored test fixture path | Validate against `benchmark_task.schema.json`. |
| Fixture expected artifacts | fixture-local `expected/` directory | Include deterministic acceptance metadata for the relevant stratum. |
| Run record | `docs/04_experiments/results/post_stage_1_larger_sample/<timestamp>/run.json` | Validate against `experiment_run.schema.json` for each comparison arm pair. |
| Run summary | `docs/04_experiments/results/post_stage_1_larger_sample/<timestamp>/summary.md` | Report lane, gate status, arms, fixture counts, metrics, and interpretation boundaries. |
| Fixture inventory | `docs/04_experiments/results/post_stage_1_larger_sample/<timestamp>/fixture_inventory.md` | List fixture IDs, strata, hashes, and included arms. |
| Closure candidate | future manifest closure document only after run and metric policy exist | Must not be written before measured results exist. |

If a future multi-arm aggregate schema is added, this plan must be revised or
superseded before the aggregate record is treated as normative.

## Minimum Metrics To Report

The run summary must report the Lane A metric set required by
[Post-Stage-1 Advancement Gate](../00_manifest/Post_Stage_1_Advancement_Gate.md):

- `task_success_rate`
- `invalid_action_rate`
- `verifier_false_accept_rate`
- `verifier_false_reject_rate`
- `evidence_sufficiency_score`
- `commit_integrity_score`
- `replay_consistency`
- `audit_completeness`
- recovery metrics when recovery fixtures are included
- working-set metrics when long-context fixtures are included

Metric thresholds are governed by
[Post-Stage-1 Metric Policy](../05_evaluation/Post_Stage_1_Metric_Policy.md).
This plan can support controlled data collection, exploratory scaled local
runs, or threshold-governed acceptance candidates when the measured run satisfies
the accepted policy.

## Execution Readiness Checklist

- [x] `PS1-G0` is met by Stage 1 closure documents 001 through 005.
- [x] `PS1-G1` sample frame is defined by this document.
- [x] `PS1-G5` baseline identity is defined by
      [Baseline Identity Plan](Baseline_Identity_Plan.md).
- [x] `PS1-G2` metric policy is accepted by
      [Post-Stage-1 Metric Policy](../05_evaluation/Post_Stage_1_Metric_Policy.md).
- [x] `PS1-G3` evidence sufficiency scale is accepted by
      [Post-Stage-1 Labeling Scope and Adjudication Policy](../05_evaluation/Post_Stage_1_Labeling_Scope_and_Adjudication_Policy.md).
- [x] `PS1-G4` labeling scope and adjudication policy is accepted by
      [Post-Stage-1 Labeling Scope and Adjudication Policy](../05_evaluation/Post_Stage_1_Labeling_Scope_and_Adjudication_Policy.md).
- [ ] All new fixtures validate against schemas.
- [ ] Fixture mirrors under `docs/` and `test/` are synchronized.
- [ ] The run command, model identity, harness identity, and budgets are fixed
      in the run summary before execution.

## Non-goals

- This plan does not run the larger controlled sample.
- This plan does not set acceptance thresholds.
- This plan does not claim broad validation for H1 through H5.
- This plan does not promote OpenClaw local harness results to pure model-only
  baseline results.
- This plan does not authorize full Context OS, memory writes, irreversible
  effects, external commits, or production deployment.

## Related Documents

- [Post-Stage-1 Advancement Gate](../00_manifest/Post_Stage_1_Advancement_Gate.md)
- [Post-Stage-1 Gate Inventory](../00_manifest/Post_Stage_1_Gate_Inventory.md)
- [Baseline Identity Plan](Baseline_Identity_Plan.md)
- [Document Ops Benchmark](Document_Ops_Benchmark.md)
- [Ablation Plan](Ablation_Plan.md)
- [Metrics Definition](../05_evaluation/Metrics_Definition.md)
- [Post-Stage-1 Metric Policy](../05_evaluation/Post_Stage_1_Metric_Policy.md)
- [Post-Stage-1 Labeling Scope and Adjudication Policy](../05_evaluation/Post_Stage_1_Labeling_Scope_and_Adjudication_Policy.md)
