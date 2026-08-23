# Failure Taxonomy v0

## Purpose

Define the initial failure categories used for labeling, credit routing, targeted recovery, and regression analysis.

## Scope

- Representation failures.
- Procedural failures.
- Search or budget failures.
- Memory failures.
- Abstraction failures.
- Evaluation failures.
- Execution governance failures.

## Non-goals

- Treating the taxonomy as final.
- Assuming every failure has a single cause.
- Claiming Credit Routing has been empirically validated.

## Inputs

- Evidence Packet.
- Verifier output.
- Episode Journal.
- Human or verifier labels.
- Runtime observations.

## Outputs

- Failure class.
- Optional multi-label attribution.
- Credit vector.
- Targeted recovery recommendation.
- Regression label.

## Key Concepts

| Code | Meaning |
| --- | --- |
| `F_REP` | Representation Failure |
| `F_PROC` | Procedural Failure |
| `F_SEARCH` | Search / Budget Failure |
| `F_MEM` | Memory Failure |
| `F_ABS` | Abstraction Failure |
| `F_EVAL` | Evaluation Failure |
| `F_EXEC` | Execution Governance Failure |

Stage 0 boundary violations should route to existing v0 labels until an
experiment or labeling guide justifies a new subtype.

## Open Questions

- Should failures be single-label, multi-label, or probability vectors?
- How should annotators handle ambiguous root causes?
- What labels are needed before training signals can use failure credit?

## Related Documents

- [Stage 0 Boundary Lock](../00_manifest/Stage_0_Boundary_Lock.md)
- [Design Theory](../01_theory/Design_Theory.md)
- [Validation and Refutation Report](../01_theory/Validation_and_Refutation_Report.md)
