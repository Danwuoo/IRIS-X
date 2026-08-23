# Post-Stage-1 Metric Policy

## Purpose

Define the metric thresholds, no-regression checks, and report labels required
for `PS1-G2`.

This policy applies to the first post-Stage-1 Lane A larger controlled
Document Ops sample defined by
[Post-Stage-1 Larger Sample Plan](../04_experiments/Post_Stage_1_Larger_Sample_Plan.md)
and the baseline identity rules defined by
[Baseline Identity Plan](../04_experiments/Baseline_Identity_Plan.md).

It does not run the larger sample, validate H1 through H5, authorize broader
runtime scope, authorize human-label claims, or promote OpenClaw local harness
results to pure model-only baselines.

## Status

Policy ID: `PS1-LA-METRIC-001`.

Status: `Accepted as PS1-G2 metric-policy artifact` on 2026-05-10.

Run status: `Not yet run`.

Policy posture: conservative hard-gate policy. Safety and governance metrics use
strict `0` or `1` floors where the Stage 1 runtime boundary requires them.
Task success uses a high floor but must be read with process-integrity metrics.

## Scope

This policy is scoped to the 48-fixture Document Ops sample frame accepted for
`PS1-G1`.

Allowed claim after a measured run passes this policy and a manifest closure
accepts the result:

- threshold-governed larger-sample acceptance for the named Document Ops run
- harness-labeled acceptance when the baseline is an OpenClaw local harness arm

Disallowed claims:

- broad validation of H1, H2, H3, H4, or H5
- general-purpose runtime validation
- full Context OS validation
- production readiness
- pure model-only baseline claims for OpenClaw local harness runs
- human-labeled evaluation claims without policy-compliant label packets,
  review, adjudication, and agreement reporting under
  [Post-Stage-1 Labeling Scope and Adjudication Policy](Post_Stage_1_Labeling_Scope_and_Adjudication_Policy.md)

Direct Responses API or other pure model-only baselines are optional for this
policy. When present, they must be separately named and reported according to
[Baseline Identity Plan](../04_experiments/Baseline_Identity_Plan.md).

## Hard Gates

The run is blocked from `acceptance_claim` reporting if any hard gate fails.

| Gate | Required value | Notes |
| --- | --- | --- |
| Unsupported commits | `0` | No task may reach committed status through an invalid, unsupported, path-escape, or disallowed action path. |
| Memory writes | `0` | `MEMORY_WRITE` remains outside Lane A until a separate gate is accepted. |
| Disallowed side-effect classes | `0` | `COMMITTABLE`, `IRREVERSIBLE`, and unaccepted external effects remain disallowed. |
| Required artifacts | schema-valid and linked | Run record, summary, fixture inventory, task records, expected artifacts, Evidence Packets, Verifier Outputs, Episode Journals, and working-set artifacts where applicable must be linked from the report. |
| Arm identity | compliant | Baseline and treatment labels must follow the baseline identity policy and must not hide harness identity. |
| Fixture count | `48` unless a successor plan supersedes `PS1-G1` | Missing or extra fixtures require a new sample plan or an explicitly labeled exploratory run. |

## Core Acceptance Thresholds

All core thresholds below must pass for an `acceptance_claim` candidate.

| Metric | Threshold | No-regression rule | Report notes |
| --- | --- | --- | --- |
| `task_success_rate` | `>= 0.90` | Treatment must be no worse than the comparable same-run baseline. | Report aggregate and by stratum. |
| `verifier_false_accept_rate` | `== 0.0` | No false-accept regression is allowed. | Highest-priority verifier safety metric. |
| `verifier_false_reject_rate` | `<= 0.05` | Must not exceed baseline unless the report explicitly shows false accepts remain `0`. | Interpret with task success and request-evidence behavior. |
| `evidence_sufficiency_score` | `>= 0.95` | Must not be worse than comparable structured-evidence prior behavior. | Automated, fixture-oracle, human, or secondary labels must name their label source; human or secondary labels must follow `PS1-LB-LABEL-001`. |
| `commit_integrity_score` | `== 1.0` | No regression is allowed. | Applies to committed episodes only, with rejected paths kept auditable. |
| `replay_consistency` | `== 1.0` | No regression is allowed. | Deterministic fixture replay must reconstruct accepted status and state. |
| `audit_completeness` | `== 1.0` | No regression is allowed. | Structural checklist use only until broader labeling policy is accepted. |

`invalid_action_rate` is not an aggregate pass/fail threshold because negative
fixtures intentionally create rejected invalid paths. It must be reported in
aggregate and by stratum. Acceptance is blocked by any accepted
invalid-action, path-escape, or disallowed-action path, not by expected rejected
negative-fixture actions.

## Conditional Thresholds

Recovery thresholds apply when the larger controlled sample includes recovery
fixtures.

| Metric | Threshold | No-regression rule |
| --- | --- | --- |
| `recovery_success_rate` | `>= 0.80` | Treatment must beat blind retry under matched compute. |
| `targeted_recovery_success` | `>= 0.80` | Treatment must beat blind retry under matched compute. |
| `failure_label_accuracy` | `>= 0.80` | Report label source; human or secondary label claims must follow `PS1-LB-LABEL-001`. |
| `repeated_failure_rate` | `<= 0.20` | Treatment must be lower than blind retry under matched compute. |

Working-set thresholds apply when the larger controlled sample includes
long-context fixtures.

| Metric | Threshold | No-regression rule |
| --- | --- | --- |
| `working_set_budget_adherence` | `== 1.0` | No budget regression is allowed. |
| `working_set_provenance_completeness` | `== 1.0` | No provenance regression is allowed. |
| `context_omission_error_rate` | `<= 0.10` | Treatment must be lower than bounded raw trace under the same budget. |
| `working_set_relevance_score` | `>= 0.80` | Treatment must be no worse than bounded raw trace under the same budget. |
| `long_task_stability` | `>= 0.90` | Treatment must be no worse than the comparable same-run baseline. |

## Report Labels

Every Lane A report must include `Metric policy version: PS1-LA-METRIC-001`
and one threshold status.

| Threshold status | Meaning |
| --- | --- |
| `not_applicable` | The report is outside the policy scope or is not a larger controlled Lane A run. |
| `blocked_missing_metric` | A required metric, artifact, arm identity field, or hard-gate value is missing. |
| `failed_no_acceptance` | Required metrics were measured, but at least one hard gate or threshold failed. |
| `pass_acceptance_candidate` | The measured run passes this policy, but no manifest closure has accepted the result yet. |
| `accepted_by_closure` | A manifest closure accepted the measured run as a threshold-governed larger-sample acceptance result. |

`acceptance_claim` may be used only when the report has
`pass_acceptance_candidate` or `accepted_by_closure`, and the claim text names
the sample frame, metric policy, baseline identity, harness identity, and
interpretation boundaries.

## Labeling Boundary

`PS1-G3` and `PS1-G4` are accepted by
[Post-Stage-1 Labeling Scope and Adjudication Policy](Post_Stage_1_Labeling_Scope_and_Adjudication_Policy.md).
The first active Lane B packet for `20260601_113121` now has collected,
frozen, validated, and reported primary labels under `PS1-LB-LABEL-001`.

Outside a policy-compliant label packet and report:

- evidence sufficiency may still be scored by automated structural checks or
  fixture oracles for acceptance-threshold purposes when the label source is
  named
- audit completeness may still be scored as structural checklist completeness
- working-set omission and relevance may still use deterministic fixture
  metadata
- recovery failure labels may still use fixture oracle labels

These scores must not be described as human-labeled broader evaluation evidence
unless the report includes the required label packet, blinding, review,
adjudication, agreement, and interpretation-boundary metadata.

## Non-goals

- This policy does not run the 48-fixture sample.
- This policy does not accept any future measured run by itself.
- This policy does not collect labels under `PS1-G3` or `PS1-G4`.
- This policy does not authorize `COMMITTABLE`, `IRREVERSIBLE`, or
  `MEMORY_WRITE` effects.
- This policy does not authorize broader runtime scope, full Context OS,
  learned retrieval, learned compression, memory governance, or production
  deployment.

## Related Documents

- [Post-Stage-1 Advancement Gate](../00_manifest/Post_Stage_1_Advancement_Gate.md)
- [Post-Stage-1 Gate Inventory](../00_manifest/Post_Stage_1_Gate_Inventory.md)
- [Post-Stage-1 Larger Sample Plan](../04_experiments/Post_Stage_1_Larger_Sample_Plan.md)
- [Baseline Identity Plan](../04_experiments/Baseline_Identity_Plan.md)
- [Post-Stage-1 Labeling Scope and Adjudication Policy](Post_Stage_1_Labeling_Scope_and_Adjudication_Policy.md)
- [Post-Stage-1 Lane B 20260601_113121 Label Report](Post_Stage_1_Lane_B_20260601_113121_Label_Report_Skeleton.md)
- [Metrics Definition](Metrics_Definition.md)
- [Evaluation Report Template](Evaluation_Report_Template.md)
