# Pre-Synthesis Readiness Package

- **Status:** readiness infrastructure complete; foundational synthesis not started or authorized
- **Execution-start commit:** `db053dcc9c614965bcaeeb96d28ebd6a57c967fa`
- **Controlling plan:** `docs/plans/TEMP_PRE_SYNTHESIS_READINESS_FOR_SINGLE_ULTRA_SESSION.md`
- **Downstream mode:** one later, separately authorized, continuous GPT-5.6 Sol Ultra session

## Purpose

This package precomputes navigation, provenance, evidence boundaries, construct
collisions, cross-source tensions, and retrieval structure. It does not select
the IRIS-X thesis, core research problem, research questions, hypotheses,
architecture, framework, or experimental program.

`research/problem-definition.md` is represented as a provisional prior. The
later synthesis may retain, revise, split, or reject it. Phase 5 is represented
as bounded provisional operationalization, not proof of a research thesis.
Phase 6 is represented with Batch 2 Result C, historical Batch 3 Result D, the
separate post-Batch-3 Result A repair, all eight gate states, and every missing
intervention predicate preserved.

## Artifact Set

| Artifact | Role |
| --- | --- |
| `baseline-manifest.json` | Frozen execution baseline and critical file identities. |
| `source-interface.yaml` | Synthesis-facing interface over the existing source and paper registries. |
| `phase-evidence-ledger.yaml` | Bounded Phase 1-6 claim/evidence ledger. |
| `construct-map.yaml` | Source-specific meanings, collisions, and unresolved normalization questions. |
| `assumption-tension-matrix.md` | Cross-source scope, assumption, and terminology tensions. |
| `claim-evidence-index.jsonl` | Retrieval-oriented claim-to-authority index. |
| `candidate-formulation-template.md` | Neutral structure for genuinely competing formulations. |
| `ultra-session-contract.md` | One-continuous-session research protocol. |
| `ultra-session-prompt.md` | Complete but unexecuted downstream prompt. |
| `readiness-report.md` | Coverage, limitations, validation, and handoff state. |

## Retrieval and Authority Order

Tier is retrieval priority, not epistemic rank.

1. **Tier 0:** root/scoped governance and current Phase 6 state.
2. **Tier 1:** direct terminal records, run results, definitions, and repaired
   derivation authority.
3. **Tier 2:** IRIS-X syntheses, closure decisions, provisional formulation,
   and provisional architecture records.
4. **Tier 3:** predecessor primary material.
5. **Tier 4:** external project entry points and preserved papers.
6. **Tier 5:** low-level implementation details loaded only when a material
   claim depends on them.

For a formulation-defining, disputed, surprising, or high-priority claim, open
the listed primary path. A readiness row, later synthesis, closure summary, or
paper/project pair is not independent corroboration of its own source. Where a
direct record and a later synthesis coexist, the direct record controls the
observation and the synthesis controls only its stated interpretation or
decision scope.

## Interpretation Boundary

The package records source-stated material, directly observed repository
evidence, readiness inferences, and unknowns separately. It exposes plausible
units and tensions without imposing canonical definitions. Paper inspection
was limited to registry verification plus local text extraction sufficient for
retrieval metadata; paper-scale adjudication remains for the Ultra session.

This package is not a literature review, source replacement, RAG system,
vector store, cumulative model state, or multi-run formulation program.

## Validation

From repository root:

```powershell
python tools\validate_pre_synthesis_readiness.py
python tools\repository_check.py
```

The validator checks structure and referential integrity only. A passing result
does not establish scientific truth or authorize the downstream session.

**STOP:** Foundational synthesis is not started or authorized. Do not execute
`ultra-session-prompt.md` without a separate owner authorization.
