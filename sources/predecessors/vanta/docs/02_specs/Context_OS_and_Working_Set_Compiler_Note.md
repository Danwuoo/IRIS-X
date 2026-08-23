# Context OS and Working Set Compiler Note

## Purpose

Define the Stage 0 boundary for Context OS and the minimum Working Set Compiler
contract without pulling full Context OS optimization into Stage 1.

## Status

Stage 0 boundary note. This is not a full Context OS implementation spec and not
an empirical claim that working-set compilation improves performance.

Phase 5 narrows this note into `Working Set Compiler v0`: deterministic,
reference-backed selection for local Document Ops smoke only. Phase 5 remains a
candidate compiler test, not full Context OS.

`PS1-G7` is accepted by
[Context OS Expansion Gate](../00_manifest/Context_OS_Expansion_Gate.md) for
Context OS specification and evaluation planning only. It does not authorize
runtime implementation, schema changes, learned retrieval, ranking,
compression, memory governance, memory writes, or H3 validation claims.

The first `PS1-G7` planning bundle aligned to the `20260601_113121` Lane A
closure run is
[Post-Stage-1 Context OS Planning Draft Spec](Post_Stage_1_Context_OS_Planning_Draft_Spec.md),
[Post-Stage-1 Context OS Schema Impact Review](../03_schemas/Post_Stage_1_Context_OS_Schema_Impact_Review.md),
and
[Post-Stage-1 Context OS Evaluation Plan](../04_experiments/Post_Stage_1_Context_OS_Evaluation_Plan.md).
It uses measured Lane A working-set metrics for planning only. A later active
Lane B report adds packet-level human-labeled context-quality evidence for the
named `20260601_113121` packet only; it does not change this note into an
implementation spec or H3 validation.

## Scope

- Working set artifact boundaries.
- Context selection references.
- Provenance requirements.
- Omitted-context notes.
- Relationship to canonical state, evidence, memory, and recovery context.

## Non-goals

- Full long-term memory governance.
- Retrieval, ranking, or compression algorithm design.
- Training on runtime feedback.
- Treating a larger context window as equivalent to Context OS.
- Treating raw tool logs or full memory dumps as a working set.
- Writing memory, appending memory, or treating memory append as learning.

## Inputs

- Active goal or task reference.
- Current canonical state reference.
- Candidate memory references.
- Evidence Packet references.
- Constraint and policy references.
- Recovery context references, when relevant.
- Token, latency, and provenance constraints.

## Outputs

- `WorkingSet` record.
- Selected references to canonical state, memory, evidence, constraints, and
  recovery context.
- Selection policy and selection rationale.
- Token budget metadata.
- Provenance for included context.
- Notes about important omitted context.

## Key Concepts

- Context OS compiles a working set; it does not store all memory or replace
  native long-context capability.
- Working set content should be reference-backed and budget-aware.
- Omitted context is part of the audit surface because omissions can cause
  representation, memory, abstraction, or evaluation failures.
- Working set selection may inform verifier, recovery, and evaluation, but it is
  not itself proof that the selected context is sufficient.
- Stage 1 may reference `WorkingSet` records, but full Context OS optimization is
  deferred until earlier loop, evidence, verifier, and journal phases produce
  stable logs and metrics.

## Minimum Data Contract

The minimum data contract is defined by
[`working_set.schema.json`](../03_schemas/working_set.schema.json). The schema
uses references and provenance instead of raw context dumps, raw tool logs, or
full memory dumps.

## Phase 5 v0 Compiler Boundary

`Working Set Compiler v0` takes only explicit candidate refs:

- canonical state refs
- Evidence Packet refs
- constraint refs
- recovery context refs

The compiler may include candidate memory refs only when the fixture provides a
specific reference. It must not read a memory store, dump memory, or write
memory.

The v0 policy is deterministic:

- select required refs first
- select optional refs by fixture metadata and stable kind priority
- preserve provenance for every selected ref
- record omitted optional refs in `omitted_context_notes`
- reject `raw_tool_log`, `full_memory_dump`, and `memory_write` refs

The v0 output is useful only if it is schema-valid, budget-aware, and auditable.
It is not proof that the selected context is sufficient.

## Post-Stage-1 Expansion Boundary

Any work beyond deterministic `Working Set Compiler v0` must route through
`PS1-G7` and keep these boundaries:

- Full Context OS requires a later spec and implementation batch; this note is
  not that spec.
- Learned retrieval, learned ranking, learned compression, and memory
  governance require explicit future contracts before implementation.
- `MEMORY_WRITE`, `COMMITTABLE`, and `IRREVERSIBLE` effects remain blocked by
  [Side-Effect Escalation Gate](../00_manifest/Side_Effect_Escalation_Gate.md)
  and successor implementation gates, not by this note.
- Larger controlled evidence, policy-compliant omission/relevance/provenance
  labels, fixed baseline identity, and process-integrity floors are required
  before broader Context OS claims can be considered.

## Open Questions

- What selection policy beyond deterministic reference-backed v0 is justified
  after larger controlled evidence and policy-compliant labels exist?
- What additional label scale, if any, is needed beyond `PS1-LB-LABEL-001` for
  future Context OS quality claims?
- Which failures should trigger working-set recompilation rather than verifier
  rejection or targeted recovery?

## Related Documents

- [Stage 0 Boundary Lock](../00_manifest/Stage_0_Boundary_Lock.md)
- [Project Manifest](../00_manifest/Project_Manifest.md)
- [Context OS Expansion Gate](../00_manifest/Context_OS_Expansion_Gate.md)
- [Post-Stage-1 Context OS Planning Draft Spec](Post_Stage_1_Context_OS_Planning_Draft_Spec.md)
- [Post-Stage-1 Context OS Schema Impact Review](../03_schemas/Post_Stage_1_Context_OS_Schema_Impact_Review.md)
- [Post-Stage-1 Context OS Evaluation Plan](../04_experiments/Post_Stage_1_Context_OS_Evaluation_Plan.md)
- [Side-Effect Escalation Gate](../00_manifest/Side_Effect_Escalation_Gate.md)
- [Research Questions](../00_manifest/Research_Questions.md)
- [Ablation Plan](../04_experiments/Ablation_Plan.md)
- [Metrics Definition](../05_evaluation/Metrics_Definition.md)
