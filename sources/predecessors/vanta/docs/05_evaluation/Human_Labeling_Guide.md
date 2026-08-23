# Human Labeling Guide

## Purpose

Define human labeling responsibilities for Vanta experiments. Human labels are
evaluation artifacts only. They are not runtime approval decisions, verifier
outputs, or proof that a hypothesis has been validated.

## Labeling Targets

- Task success.
- Action validity.
- Evidence sufficiency.
- Failure class.
- Commit integrity.
- Audit completeness.
- Working-set omission.
- Working-set relevance.
- Working-set provenance.

## General Rules

- Label the observed artifact, not the intended design.
- Do not infer missing provenance.
- Mark ambiguous cases as `needs_review`.
- Separate correctness from auditability.
- Record the source document, benchmark task, and criteria version used for each
  label.
- For working-set labels, judge the context artifact before looking at the
  final answer unless the labeling plan explicitly defines a causal-failure
  label.
- Do not expose fixture oracle fields such as `required_refs`,
  `relevant_refs`, `irrelevant_refs`, or `omission_trap_refs` to primary human
  labelers. Those fields may be compared only after labels are frozen.
- For post-Stage-1 Lane B labels, use
  [Post-Stage-1 Labeling Scope and Adjudication Policy](Post_Stage_1_Labeling_Scope_and_Adjudication_Policy.md)
  as the scope, scale, review, and adjudication authority.

## Required Outputs

- Label type.
- Label value.
- Confidence.
- Rationale.
- Referenced evidence packet, episode step, context artifact, or working-set
  reference.
- Reviewer identity or anonymized reviewer ID.
- Label guide version or criteria version.

## Post-Stage-1 Evidence Sufficiency Labels

Evidence sufficiency labels for `PS1-G3` use policy version
`PS1-LB-LABEL-001`.

The label unit is one Evidence Packet or linked set of Evidence Packets
supporting a verifier decision or commit decision. Labelers must judge whether
the packet contains provenance-backed observations, state references,
constraints, and postconditions sufficient for the decision under review. They
must not reward fluent explanations that lack resolvable evidence.

| Value | Label | Rule |
| --- | --- | --- |
| `4` | `sufficient` | Evidence is provenance-backed, resolves the relevant action or commit, covers required preconditions and postconditions, and supports the decision without material ambiguity. |
| `3` | `mostly_sufficient` | Evidence supports the decision with only minor or redundant defects and no task-critical gap. |
| `2` | `partial` | Evidence is materially incomplete or ambiguous; it may support conservative rejection or `request_evidence`, but not acceptance of a commit. |
| `1` | `minimal` | Evidence is thin, mostly narrative, or cannot resolve the relevant state transition. |
| `0` | `absent_or_misleading` | Evidence is missing, fabricated, stale, contradictory, explanation-only, or provenance-invalid. |
| `needs_review` | `needs_review` | The packet or task boundary is too ambiguous to label. |

For metric computation, `evidence_sufficiency_score` uses
`label_value / 4` over adjudicated labels only. Reports must include raw labels,
normalized scores, reviewer identity or anonymized ID, confidence, rationale,
artifact refs, and unresolved `needs_review` counts.

Double human annotation or documented secondary review is required before these
labels may be reported as broader evaluation evidence.

## Phase 5 Working-Set Labeling Contract

This contract covers human or secondary labels for `Working Set Compiler v0`
and later long-context Document Ops evaluations. It evaluates the quality of a
bounded context artifact. It does not evaluate full Context OS, learned
retrieval, memory governance, or H3 validation by itself.

### Label Unit

A working-set label is attached to one tuple:

```text
experiment_id + run_id + task_id + arm + context_artifact_id
```

For treatment arms, `context_artifact_id` is normally the `working_set_id`. For
bounded raw-trace baselines, it is the raw-trace context artifact ID.

### Required Artifact Packet

| Artifact | Required contents | Used for |
| --- | --- | --- |
| Label plan | `experiment_id`, `run_id`, label policy version, annotator visibility rules, adjudication policy, arm labels | All working-set labels |
| Task packet | `task_id`, active goal, prompt, task type, success criteria, failure criteria, allowed side-effect classes | Omission and relevance |
| Redacted candidate-ref inventory | `ref_id`, `kind`, `source`, `path`, `content_hash`, and inspectable content or excerpt; fixture oracle role fields hidden | Omission and relevance |
| Context artifact | For treatment: `WorkingSet` fields including selected refs, token budget, provenance, selection policy, selection rationale, and `omitted_context_notes`; for baseline: included and dropped refs under the same budget | Omission, relevance, and provenance |
| Source artifacts | Canonical state, Evidence Packets, constraints, recovery context, and document inputs needed to resolve candidate refs | Omission, relevance, and provenance |
| Run metadata | baseline and treatment labels, model, harness, prompt and response budgets, result path, schema versions, unsupported commits, and memory-write counts | Claim boundaries |
| Fixture oracle metadata | deterministic `required_refs`, `relevant_refs`, `irrelevant_refs`, and `omission_trap_refs`, held back until labels are frozen | Post-label comparison only |

If the packet lacks the task packet, redacted candidate-ref inventory, context
artifact, or source artifacts needed to inspect a ref, the labeler must use
`needs_review` rather than inventing a label.

### Working-Set Omission

Definition: a working-set omission is a task-critical candidate ref that was
available to the context construction arm but absent from the included or
selected refs.

Rules:

- Determine task-critical refs from the task packet and source artifacts, not
  from fixture oracle role fields.
- Count only refs that appear in the redacted candidate-ref inventory. If the
  task appears to require a ref absent from that inventory, record
  `candidate_inventory_defect` in the rationale.
- Do not count omitted optional noise as an omission.
- If critical content appears in raw text but has no auditable ref, mark it as
  semantically present and provenance-defective rather than fully present.
- If a task-critical ref cannot fit under the declared budget, still record the
  omission and add `budget_conflict` to the rationale.

| Value | Label | Rule |
| --- | --- | --- |
| `0` | `no_omission` | All task-critical candidate refs are included or selected. |
| `1` | `minor_omission` | A supporting or redundant ref is omitted, but included refs still support correct and auditable execution. |
| `2` | `material_omission` | At least one task-critical ref is omitted, but the remaining context may still support partial execution, verification, or recovery. |
| `3` | `critical_omission` | An omitted ref is required to identify the source artifact, evidence, constraint, or recovery context needed for correct and auditable execution. |
| `needs_review` | `needs_review` | The artifact packet or task boundary is too ambiguous to label. |

For broader metric computation, the human-derived omission rate is:

```text
human_omitted_task_critical_refs / human_task_critical_candidate_refs
```

Use the ordinal severity only when the denominator is unresolved or
adjudication has not completed.

### Working-Set Relevance

Definition: working-set relevance measures whether included refs directly
support the active goal, verification requirements, constraints, recovery
context, or auditability under the fixed budget.

Per included ref, use one of these labels:

| Label | Counts as relevant | Rule |
| --- | --- | --- |
| `task_critical` | yes | Necessary for correct or auditable execution. |
| `supporting` | yes | Useful for execution, verification, constraints, or recovery, but not strictly necessary. |
| `irrelevant` | no | Unrelated or avoidable context for the active goal. |
| `harmful` | no | Misleading, conflicting, disallowed, raw-log-like, full-memory-dump-like, or memory-write-like context. |
| `needs_review` | no claim | Ambiguous without adjudication. |

Packet-level relevance quality:

| Value | Label | Rule |
| --- | --- | --- |
| `3` | `high_relevance` | Included refs are task-critical or supporting, with no harmful refs and no avoidable noise that crowds the budget. |
| `2` | `adequate_relevance` | Most included refs are relevant and no harmful ref is present. |
| `1` | `low_relevance` | Some relevant refs are present, but irrelevant refs dominate or crowd the budget. |
| `0` | `irrelevant_or_harmful` | No clear relevant ref is included, or harmful/prohibited context is included. |
| `needs_review` | `needs_review` | The packet cannot support a stable relevance label. |

For broader metric computation, refs labeled `task_critical` or `supporting`
count as relevant. Relevance must always be interpreted with omission severity;
a tiny incomplete context can look precise while omitting critical refs.

### Working-Set Provenance

Definition: working-set provenance measures whether each included ref can be
audited back to a source, path, version or content hash, and source artifact. It
is not evidence sufficiency and not final-answer correctness.

Per included ref, use one of these labels:

| Label | Rule |
| --- | --- |
| `complete` | `ref_id`, `kind`, `source`, `path`, and `content_hash` are present and resolve to the supplied source artifact. |
| `incomplete_fields` | One or more required provenance fields are missing. |
| `unresolved_source` | Fields are present, but the source artifact cannot be resolved from the packet. |
| `hash_mismatch` | The supplied content hash does not match the resolved artifact. |
| `invalid_source` | The ref represents a raw tool log dump, full memory dump, memory write, or another source disallowed by the Phase 5 boundary. |
| `needs_review` | Resolution cannot be completed from the packet. |

Packet-level provenance audit:

| Value | Label | Rule |
| --- | --- | --- |
| `3` | `complete_provenance` | Every included ref has complete, resolving provenance and no invalid source. |
| `2` | `usable_with_minor_defects` | All task-critical refs have complete provenance; only optional refs have minor provenance defects. |
| `1` | `partial_provenance` | A task-critical ref has a provenance defect, or multiple optional refs are defective. |
| `0` | `unauditable` | Most refs lack usable provenance, a critical ref has a hash mismatch, or an invalid source is accepted. |
| `needs_review` | `needs_review` | The artifact packet is insufficient for provenance audit. |

The structural metric `working_set_provenance_completeness` remains the fraction
of included refs with required provenance fields. Human provenance audit labels
may be reported as broader reviewability evidence, but must not be silently
substituted for the structural metric unless a metric policy version defines the
mapping.

### Review And Adjudication

- Double human annotation or documented secondary review is required before
  using working-set omission or relevance labels as broader evaluation evidence.
- Structural provenance completeness can be computed automatically, but human
  provenance audit requires secondary review when source resolution, hash
  resolution, or invalid-source status is disputed.
- Adjudication is required when labels differ by two or more ordinal levels,
  when one reviewer marks `needs_review`, or when reviewers disagree on
  `task_critical`, `critical_omission`, `harmful`, `hash_mismatch`, or
  `invalid_source`.
- Reports using these labels must state inter-annotator agreement or explain
  why the sample is too small for agreement statistics.

### Claim Boundaries

| Evidence type | May be reported as | Must not be reported as |
| --- | --- | --- |
| Experiment 005 fixture-oracle omission and relevance metrics | Local smoke scoring against controlled fixture metadata | Human label result or H3 validation |
| Experiment 005 structural provenance completeness | Local smoke auditability check for selected refs | Evidence that selected context was sufficient or that H3 is validated |
| Human labels on the five Experiment 005 smoke fixtures | Labeling pilot or qualitative broader-evaluation evidence | Statistical support, broad H3 validation, or full Context OS validation |
| Human or secondary labels on a larger controlled sample with fixed packets, double review, and adjudication | Broader evaluation evidence for working-set quality and H3 pressure testing | Proof that H3 is true unless a later acceptance gate explicitly permits that claim |
| Budget adherence, schema validity, unsupported-commit count, and memory-write count | Process-integrity and boundary evidence | Context-quality superiority, learned retrieval validation, or full Context OS validation |
| Task success or stability without working-set quality labels | Outcome sanity check under the fixed run controls | Evidence that the working set caused success or that H3 is validated |

## Open Questions

- What minimum larger-sample size is required before agreement statistics are
  meaningful?
- Which future Context OS labels are needed if the program expands beyond
  deterministic reference-backed `Working Set Compiler v0`?
