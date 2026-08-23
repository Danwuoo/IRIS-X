# Evaluation Report Template

## Experiment

- Experiment ID:
- Date:
- Runtime version:
- Evaluator:
- Dataset or benchmark:
- Status: `Not yet run`
- Metric policy version:
- Threshold status: `not_applicable | blocked_missing_metric | failed_no_acceptance | pass_acceptance_candidate | accepted_by_closure`

## Setup

- Baseline:
- Treatment:
- Backbone model:
- Tool interface:
- Compute budget:
- Side-effect classes:

## Metrics

| Metric | Baseline | Treatment | Notes |
| --- | --- | --- | --- |
| `task_success_rate` | TODO | TODO | TODO |
| `invalid_action_rate` | TODO | TODO | TODO |
| `verifier_false_accept_rate` | TODO | TODO | TODO |
| `verifier_false_reject_rate` | TODO | TODO | TODO |
| `evidence_sufficiency_score` | TODO | TODO | TODO |
| `commit_integrity_score` | TODO | TODO | TODO |
| `replay_consistency` | TODO | TODO | TODO |
| `audit_completeness` | TODO | TODO | TODO |

## Labeling Contract

- Label policy version:
- Label source: `none | fixture_oracle | automated_structural | human | secondary_review | double_human_adjudicated`
- Label packet path:
- Human Labeling Guide version:
- Blinding policy:
- Adjudication policy:
- Inter-annotator agreement:
- Fixture oracle metadata exposed before label freeze: `yes | no | not_applicable`

For reports that include Phase 5 or later long-context working-set evaluation:

| Working-set label | Baseline | Treatment | Label source | Notes |
| --- | --- | --- | --- | --- |
| `working_set_omission_severity` | TODO | TODO | TODO | TODO |
| `working_set_relevance_quality` | TODO | TODO | TODO | TODO |
| `working_set_provenance_audit` | TODO | TODO | TODO | TODO |

## Interpretation Boundaries

- Claim level: `local_smoke | exploratory_pilot | labeling_pilot | broader_evaluation_evidence | acceptance_claim`
- Acceptance claim rule: requires threshold pass plus manifest or closure acceptance.
- Hypothesis claim allowed:
- Hypothesis claim prohibited:
- Boundary notes:

## Findings

TODO: Report measured findings only. Do not claim validation without evidence.

## Failures And Risks

TODO: Summarize observed failure classes, missing evidence, and unresolved risks.

## Next Steps

TODO: Define the next ablation or implementation correction.
