# Failure Labeling Guide

## Purpose

Define initial labels for runtime failure analysis and targeted recovery experiments.

## Labels

| Code | Label | Description |
| --- | --- | --- |
| `F_REP` | Representation Failure | State representation is wrong, missing, fragmented, or inconsistent. |
| `F_PROC` | Procedural Failure | Procedure, plan, or action schema is wrong. |
| `F_SEARCH` | Search / Budget Failure | Branching, resource allocation, stopping, or exploration strategy is wrong. |
| `F_MEM` | Memory Failure | Memory read, omission, write, pollution, or staleness causes failure. |
| `F_ABS` | Abstraction Failure | Compression, abstraction granularity, or macro use causes failure. |
| `F_EVAL` | Evaluation Failure | Verifier, confidence, calibration, or risk judgment is wrong. |
| `F_EXEC` | Execution Governance Failure | Side effect, commit, rollback, replay, or tool provenance governance fails. |

## Phase 4 `F_EXEC` Sublabels

These labels are Experiment 004 scoring labels under `F_EXEC`; they are not new
top-level taxonomy classes.

| Code | Parent | Description |
| --- | --- | --- |
| `F_EXEC_ROLLBACK_FAILURE` | `F_EXEC` | Reversible action cannot be restored because rollback backup or metadata is missing or unusable. |
| `F_EXEC_AUDIT_GAP` | `F_EXEC` | Episode Journal or related artifacts omit refs needed for audit completeness. |
| `F_EXEC_COMPENSATION_REQUIRED` | `F_EXEC` | Action is compensable rather than strictly rollbackable and needs explicit compensation handling. |

## Labeling Rules

- Use multi-label attribution when multiple causes materially contributed.
- Prefer direct evidence over narrative plausibility.
- Mark `unknown` when logs are insufficient.
- Record whether the proposed recovery targeted the labeled failure class.
- For Experiment 004, fixture oracle labels are used only for scoring; treatment
  must use the OpenClaw recovery decision.

## Post-Stage-1 Review Requirements

Post-Stage-1 failure labels used for broader evaluation evidence must follow
[Post-Stage-1 Labeling Scope and Adjudication Policy](Post_Stage_1_Labeling_Scope_and_Adjudication_Policy.md)
with `label_policy_version: PS1-LB-LABEL-001`.

`failure_label_accuracy` requires double human annotation or documented
secondary review before broader label claims. `targeted_recovery_success`
requires double annotation or secondary review when the recovery policy choice
is not fixture-trivial.

Adjudication is required when reviewers disagree on a top-level taxonomy label,
omit a material multi-label cause, disagree on recovery policy match, or mark
the packet as `needs_review`.

## Open Questions

- Should credit vectors be normalized probabilities?
- What minimum evidence is required to label `F_EXEC` outside the current
  Document Ops recovery fixtures?
