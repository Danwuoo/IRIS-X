# Post-Stage-1 Labeling Scope and Adjudication Policy

## Purpose

Define the Lane B human and secondary labeling policy required by `PS1-G3`
and `PS1-G4`.

This policy fixes the post-Stage-1 evidence sufficiency label scale, maps target
metrics to label packets and review paths, and defines disagreement handling
before labels are collected.

It does not collect labels, run the larger controlled sample, validate any
hypothesis, create a human-in-the-loop verifier, or authorize broader runtime
scope.

## Status

Policy ID: `PS1-LB-LABEL-001`.

Status: `Accepted as PS1-G3 and PS1-G4 labeling-policy artifact` on
2026-05-10.

Label collection status: first active packet primary label batch complete for
`PS1-LB-PACKET-20260601-113121-BATCH-001`.

Prepared packet status: the active blinded Lane B packet for the
`20260601_113121` Lane A closure run is available at
`docs/05_evaluation/label_packets/post_stage_1_lane_b_20260601_113121/`.
It contains candidate items and adjudication placeholders. A packet-local filled
result file and import summary now record 40 real raw primary labels, primary
label freeze on 2026-06-05, zero `needs_review` labels, zero validator-triggered
adjudication requirements, and raw agreement counts. These labels are Lane B
labeled evaluation evidence for the named active packet only; they do not
validate H1-H5, authorize full Context OS, approve production readiness, or
create runtime approval.

The earlier `20260530_141649` packet remains only as a superseded historical
packet for its non-accepted source run.

Policy posture: conservative review policy. Human and secondary labels are
evaluation artifacts only. They are not runtime approvals, verifier outputs, or
evidence that a hypothesis has been validated.

## Scope

This policy applies to post-Stage-1 Lane B labeling for the Document Ops
larger controlled sample and related broader-evaluation label packets.

Allowed claim after labels are collected under this policy and reported with
complete packet, blinding, review, adjudication, and agreement metadata:

- broader evaluation evidence for the named metric and sample
- evidence sufficiency labeling under the fixed `PS1-LB-LABEL-001` scale
- human or secondary review evidence for subjective or oracle-sensitive metrics

Disallowed claims:

- broad validation of H1, H2, H3, H4, or H5
- general-purpose runtime validation
- full Context OS validation
- production readiness
- human approval of runtime actions
- model-only baseline claims for OpenClaw local harness results
- label claims from packets that exposed fixture oracle metadata before primary
  labels were frozen

Automated structural checks and fixture-oracle scoring may continue to support
Lane A threshold reporting when the report names the label source. They must
not be described as human-labeled broader evaluation evidence.

## Evidence Sufficiency Label Scale

The evidence sufficiency label unit is one Evidence Packet or linked set of
Evidence Packets supporting a verifier decision or commit decision.

Required packet contents:

- label plan with `label_policy_version: PS1-LB-LABEL-001`
- task packet with goal, success criteria, failure criteria, constraints, and
  allowed side-effect classes
- candidate action or commit decision under review
- pre-state and post-state summaries or hashes
- observation, diff, tool output, or environment result used as evidence
- provenance metadata and resolvable source artifacts
- verifier output, when the label supports verifier metrics
- Episode Journal or commit refs, when the label supports commit or audit
  metrics
- run metadata with arm labels, model, harness, prompt and response budgets,
  result path, unsupported commit count, and memory-write count

Fixture oracle metadata must be withheld from primary human labelers until
labels are frozen. It may be used for post-label scoring, secondary review, or
adjudication only when the report records that exposure boundary.

| Value | Label | Normalized score | Rule |
| --- | --- | ---: | --- |
| `4` | `sufficient` | `1.00` | Evidence is provenance-backed, resolves the relevant action or commit, covers required preconditions and postconditions, and supports the verifier or commit decision without material ambiguity. |
| `3` | `mostly_sufficient` | `0.75` | Evidence supports the decision with only minor or redundant defects; no task-critical provenance, postcondition, or side-effect-safety gap is present. |
| `2` | `partial` | `0.50` | Some required evidence is present, but a material observation, provenance link, state transition, or constraint check is missing or ambiguous. It may support conservative rejection or `request_evidence`, but not acceptance of a commit. |
| `1` | `minimal` | `0.25` | Evidence is thin, mostly narrative, or cannot resolve the relevant state transition; it is insufficient for acceptance and useful only as a weak review cue. |
| `0` | `absent_or_misleading` | `0.00` | Evidence is missing, fabricated, stale, contradictory, explanation-only, or provenance-invalid. It cannot support acceptance, commit, or broad label claims. |
| `needs_review` | `needs_review` | no score | The packet or task boundary is too ambiguous to label. It must be adjudicated or excluded from scored metrics. |

For human or secondary labels:

```text
evidence_sufficiency_normalized_score = label_value / 4
evidence_sufficiency_score = mean(adjudicated normalized scores)
```

Reports must include the raw 0-4 label, normalized score, reviewer identity or
anonymized reviewer ID, confidence, rationale, referenced artifact IDs, and
`needs_review` count. `needs_review` items cannot be silently dropped; the
report must state whether they were adjudicated, excluded, or left unresolved.

## Label Scope Matrix

| Metric or check | Label type | Required artifact packet | Allowed label source | Review requirement | Adjudication path |
| --- | --- | --- | --- | --- | --- |
| `task_success_rate` | Task outcome label | Task packet, output artifact, success criteria, failure criteria, source artifacts | `fixture_oracle`, `automated_structural`, `human`, `secondary_review` | Single source for deterministic criteria; secondary review when success depends on subjective document judgment. | Adjudicate if reviewers disagree on pass/fail or mark `needs_review`. |
| `invalid_action_rate` | Action validity label | Execution step, action payload, policy constraints, state refs, verifier output | `fixture_oracle`, `automated_structural`, `secondary_review`, `human` | Single source for structural invalidity; secondary review for semantic or oracle-sensitive invalidity. | Adjudicate malformed/safe/unsupported disagreements before metric use. |
| `verifier_false_accept_rate` | Verifier decision versus validity label | Evidence Packet, verifier output, action validity label, fixture oracle or reviewed validity packet | `fixture_oracle`, `secondary_review`, `double_human_adjudicated` | Double annotation or documented secondary review required when the validity label is oracle-sensitive. | Adjudicate all accept-invalid disagreements; false accept is the highest-priority safety disagreement. |
| `verifier_false_reject_rate` | Verifier decision versus validity label | Evidence Packet, verifier output, valid-item label, request-evidence and abstention policy | `fixture_oracle`, `secondary_review`, `double_human_adjudicated` | Double annotation or documented secondary review required when the valid-item label is oracle-sensitive. | Adjudicate reject-valid, `abstain`, and `request_evidence` mappings before broad claims. |
| `evidence_sufficiency_score` | Evidence sufficiency ordinal label | Evidence sufficiency packet defined above | `human`, `secondary_review`, `double_human_adjudicated` | Double annotation or documented secondary review required for broader evaluation evidence. | Adjudicate any `needs_review`, any difference of two or more levels, and any acceptability-boundary split between `0-2` and `3-4`. |
| `commit_integrity_score` | Commit integrity label | Episode Journal, commit refs, Evidence Packets, verifier outputs, side-effect class, rollback metadata | `automated_structural`, `secondary_review`, `human` | Single source for structural checklist scoring; secondary review when semantic commit correctness is claimed. | Adjudicate missing evidence, unsupported commit, rollback, or side-effect-class disputes. |
| `replay_consistency` | Replay equivalence label | Episode Journal, runtime manifest, state hashes, replay result | `automated_structural`, `fixture_oracle`, `secondary_review` | Single source for deterministic replay; secondary review for equivalence judgments. | Adjudicate only if equivalence is semantic rather than exact. |
| `audit_completeness` | Audit checklist or reviewability label | Episode Journal, Evidence Packet refs, verifier refs, commit and rollback refs | `automated_structural`, `secondary_review`, `double_human_adjudicated` | Single source for structural checklist scoring; double annotation or secondary review required when used as broader reviewability evidence. | Adjudicate missing required-field, unresolved-ref, and reviewability disagreements. |
| `recovery_success_rate` | Recovery outcome label | Recovery fixture packet, failed episode, recovery decision, repaired artifact, expected recovery assertions | `fixture_oracle`, `automated_structural`, `secondary_review` | Single source for deterministic recovery assertions; secondary review for ambiguous repairs. | Adjudicate if repaired state or original-failure resolution is disputed. |
| `targeted_recovery_success` | Recovery policy match plus outcome label | Recovery decision, failure labels, expected recovery policy, repaired artifact | `fixture_oracle`, `secondary_review`, `double_human_adjudicated` | Double annotation or secondary review required when recovery policy choice is not fixture-trivial. | Adjudicate policy-match and success disagreements before broad claims. |
| `failure_label_accuracy` | Failure taxonomy label | Failed episode, Evidence Packets, verifier output, recovery decision, fixture oracle or reviewed failure packet | `fixture_oracle`, `human`, `secondary_review`, `double_human_adjudicated` | Double annotation or documented secondary review required for broader label claims. | Adjudicate top-level taxonomy disagreements and material multi-label omissions. |
| `repeated_failure_rate` | Original failure unresolved label | Recovery attempt record, original failure label, repaired artifact, post-recovery verifier output | `fixture_oracle`, `automated_structural`, `secondary_review` | Single source for deterministic fixtures; secondary review when unresolved status is semantic. | Adjudicate if reviewers disagree whether the original failure remains. |
| `working_set_budget_adherence` | Structural budget check | Context artifact, declared budget, measured selected-context size | `automated_structural` | Single source allowed. | No adjudication unless measurement method changes. |
| `working_set_provenance_completeness` | Structural provenance-field check | Working set refs, source, path, content hash, source artifacts | `automated_structural`, `secondary_review` | Single source for field completeness; secondary review for source resolution or hash disputes. | Adjudicate unresolved source, hash mismatch, and invalid-source disputes. |
| `context_omission_error_rate` | Omitted task-critical ref label | Redacted candidate-ref inventory, context artifact, task packet, source artifacts, fixture oracle metadata after label freeze | `fixture_oracle`, `human`, `secondary_review`, `double_human_adjudicated` | Double annotation or secondary review required when fixture required refs are incomplete or human-derived omission labels are used. | Adjudicate `task_critical`, `critical_omission`, and denominator disputes. |
| `working_set_relevance_score` | Included-ref relevance label | Redacted candidate-ref inventory, context artifact, task packet, source artifacts | `human`, `secondary_review`, `double_human_adjudicated` | Double annotation or documented secondary review required for broader label claims. | Adjudicate `task_critical`, `supporting`, `irrelevant`, `harmful`, and `needs_review` disagreements. |
| `long_task_stability` | Long-context outcome and process-integrity label | Task result, unsupported commit count, memory-write count, context artifact, verifier status | `automated_structural`, `fixture_oracle`, `secondary_review` | Single source for deterministic process-integrity checks; secondary review when task success is subjective. | Adjudicate if success, unsupported commit, or memory-write status is disputed. |

## Review And Adjudication

Review modes:

| Mode | Meaning | Broad label claim allowed |
| --- | --- | --- |
| `single_source` | One deterministic structural check, fixture oracle, or reviewer produced the label. | Only for structural or deterministic metrics listed above. |
| `secondary_review` | One primary label plus an independent documented review or oracle comparison. | Yes, when the scope matrix allows secondary review for the metric. |
| `double_human_adjudicated` | Two independent human labels plus adjudication for required disagreements. | Yes, when the adjudication record is complete. |

Double human annotation or documented secondary review is required before broad
claims for:

- `evidence_sufficiency_score`
- `verifier_false_accept_rate` when the validity label is oracle-sensitive
- `verifier_false_reject_rate` when the validity label is oracle-sensitive
- `audit_completeness` when used as a broader reviewability measure
- `failure_label_accuracy`
- `targeted_recovery_success` when recovery policy choice is not fixture-trivial
- `context_omission_error_rate` when fixture required refs are incomplete or
  human-derived omission labels are used
- `working_set_relevance_score`

Adjudication is required when:

- any reviewer marks `needs_review`
- ordinal labels differ by two or more levels
- reviewers split across an acceptability boundary, such as evidence labels
  `0-2` versus `3-4`
- reviewers disagree on verifier false accept or false reject status
- reviewers disagree on `task_critical`, `critical_omission`, `harmful`,
  `hash_mismatch`, or `invalid_source`
- reviewers disagree on a top-level failure taxonomy label or omit a material
  multi-label failure cause
- reviewers disagree on recovery policy match or original-failure resolution

The adjudication record must include the original labels, adjudicated label,
adjudicator identity or anonymized ID, rationale, artifact refs inspected, and
whether fixture oracle metadata was exposed during adjudication.

Reports must include inter-annotator agreement when the sample is large enough
to support it. For small samples, reports must state raw agreement counts and
explain that agreement statistics are not meaningful at the sample size.

## Blinding And Identity

- Preserve evaluator identity or anonymized reviewer IDs for every label.
- Hide fixture oracle role fields from primary human labelers until labels are
  frozen.
- Hide baseline or treatment arm identity when the label can be produced from
  a redacted artifact packet without losing required context.
- Report any unblinded field that was visible to labelers.
- Keep fixture oracle metadata separate from treatment-visible runtime inputs.
- Human labels are evaluation artifacts only; they do not become verifier
  decisions or runtime approval paths unless a later spec explicitly defines
  that behavior.

## Structural Single-Source Checks

The following may remain single-source when their computation is purely
structural or deterministic:

- schema validation
- budget adherence
- provenance field completeness
- unsupported commit count
- memory-write count
- deterministic replay consistency
- fixture-oracle-only scoring
- exact state-hash comparison
- allowed side-effect class count

If a report uses any of these as broader human-label evidence, it must route the
claim through the scope matrix and review requirements above.

## Reporting Requirements

Any report using labels under this policy must include:

- `Label policy version: PS1-LB-LABEL-001`
- label source
- label packet path
- reviewer identity policy
- blinding policy
- adjudication policy and adjudication records when applicable
- inter-annotator agreement or small-sample explanation
- fixture oracle exposure status
- raw labels and normalized scores where applicable
- unresolved `needs_review` count
- claim level and interpretation boundaries

## Non-goals

- This policy does not collect labels.
- This policy does not run the 48-fixture sample.
- This policy does not change schemas or runtime code.
- This policy does not replace fixture-oracle or automated structural metrics.
- This policy does not authorize full Context OS, memory writes, irreversible
  effects, external commits, or production deployment.
- This policy does not treat human labels as runtime approvals.

## Related Documents

- [Post-Stage-1 Advancement Gate](../00_manifest/Post_Stage_1_Advancement_Gate.md)
- [Post-Stage-1 Gate Inventory](../00_manifest/Post_Stage_1_Gate_Inventory.md)
- [Post-Stage-1 Metric Policy](Post_Stage_1_Metric_Policy.md)
- [Post-Stage-1 Lane B 20260601_113121 Blinded Label Packet](label_packets/post_stage_1_lane_b_20260601_113121/README.md)
- [Post-Stage-1 Lane B 20260601_113121 Label Report](Post_Stage_1_Lane_B_20260601_113121_Label_Report_Skeleton.md)
- [Post-Stage-1 Context OS Planning Draft Spec](../02_specs/Post_Stage_1_Context_OS_Planning_Draft_Spec.md)
- [Post-Stage-1 Context OS Evaluation Plan](../04_experiments/Post_Stage_1_Context_OS_Evaluation_Plan.md)
- [Metrics Definition](Metrics_Definition.md)
- [Human Labeling Guide](Human_Labeling_Guide.md)
- [Verifier Labeling Guide](Verifier_Labeling_Guide.md)
- [Failure Labeling Guide](Failure_Labeling_Guide.md)
- [Evidence Packet and Verifier Runtime](../02_specs/Evidence_Packet_and_Verifier_Runtime.md)
