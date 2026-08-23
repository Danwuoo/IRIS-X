# Verifier Labeling Guide

## Purpose

Define how verifier decisions should be labeled and compared against human or oracle labels.

## Decision Labels

- `accept`
- `reject`
- `abstain`
- `request_evidence`

These labels match `verifier_output.schema.json`. Escalation is a label-review
or runtime-routing policy, not a verifier decision label in the current schema.

## Required Checks

- Pre-action feasibility.
- Pre-action safety.
- Post-action validity.
- Evidence sufficiency.
- Constraint violations.
- Provenance completeness.
- Side-effect risk.

## Evaluation Notes

- False accept is prioritized as a critical safety failure.
- False reject should be tracked because overly conservative verification can block useful work.
- Verifier confidence must be evaluated separately from correctness.
- Post-Stage-1 human or secondary review for verifier labels is governed by
  [Post-Stage-1 Labeling Scope and Adjudication Policy](Post_Stage_1_Labeling_Scope_and_Adjudication_Policy.md).
- `abstain` and `request_evidence` must be mapped by the experiment policy
  before false reject rates are reported as broader evaluation evidence.

## Post-Stage-1 Review Requirements

Use policy version `PS1-LB-LABEL-001` for Lane B verifier label packets.

Verifier false accept and false reject labels require a verifier output,
Evidence Packet, action validity label, and the experiment's decision-mapping
policy. Double human annotation or documented secondary review is required
when the underlying validity label is oracle-sensitive.

Adjudication is required for all accept-invalid disagreements, reject-valid
disagreements, `abstain` or `request_evidence` mapping disputes, and any
`needs_review` label in the packet.

## Open Questions

- What calibration method should be used?
- Should a future verifier schema add an explicit escalation decision?
