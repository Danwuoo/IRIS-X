# Stage 0 Boundary Lock

## Purpose

Lock the conceptual boundaries that must hold before Stage 1 runtime work starts.
This document is a governance checkpoint, not experimental validation and not an
implementation order.

## Status

Accepted as the Stage 0 boundary-lock document. These boundaries route theory
into specs, schemas, experiments, and evaluation without claiming that the
architecture has been empirically validated.

## Boundary Locks

| Boundary | Locked interpretation | Downstream impact |
| --- | --- | --- |
| Canonical state is not execution trace | Canonical state stores accepted task-relevant state, uncertainty, relations, events, and provenance; it does not replay every action or tool call. | Execution trace belongs in Execution IR records and Episode Journal entries. |
| Tool log is not canonical state | Raw tool output may inform state only after normalization into observations and accepted state-relevant events. | Tool logs remain provenance or audit inputs, not the state source of truth. |
| Evidence Packet is not explanation | Evidence Packet is structured material for verifier, audit, recovery, and regression; fluent rationale is not sufficient evidence. | Evidence must prefer observations, diffs, source references, runtime metadata, and provenance over self-report. |
| Episode Journal is not memory | Episode Journal records episode-level steps, hashes, evidence refs, verifier outputs, commit status, rollback status, and memory-write effects for audit and replay. | Durable memory stores and retrieval policies are separate from journal logging. |
| Memory append is not learning | Appending an item to memory is a governed write, not model training, capability acquisition, or validated learning. | Runtime feedback cannot be described as learning until a training or evaluation document defines and measures it. |
| Context OS is not long-context stuffing | Context OS / Working Set Compiler selects, compresses, and cites a task working set under constraints; it is not dumping all available context into the prompt. | Working set artifacts must preserve references, selection policy, token budget, and omitted-context notes. |
| Verifier Runtime is not final-answer-only judging | Verifier Runtime checks action feasibility, constraints, evidence sufficiency, side-effect safety, state consistency, and final correctness where applicable. | Evaluation must track false accept, false reject, abstain, and evidence-request behavior. |
| Rollback is not always possible | Rollback applies only to reversible actions; non-reversible effects require compensation, reconciliation, escalation, or explicit non-goal treatment. | Side-effect classes and commit semantics must distinguish reversible, compensable, irreversible, and memory-write actions. |

## Failure Taxonomy Extension Position

Stage 0 does not add new top-level failure classes. Boundary violations should be
recorded as evidence-backed notes under the existing v0 taxonomy:

- State or working-set boundary violations usually route to `F_REP`, `F_MEM`, or
  `F_ABS`.
- Evidence and verifier boundary violations usually route to `F_EVAL`.
- Commit, rollback, replay, side-effect, and provenance boundary violations
  usually route to `F_EXEC`.
- If logs are insufficient, labeling guides may use `unknown` without inventing
  a new failure class.

Future experiments may propose additional sublabels, but those sublabels must be
specified and evaluated before they become normative taxonomy.

## Completion Checklist

- [x] State vs Execution boundary note exists.
- [x] Evidence Packet boundary is locked as structured evidence, not explanation.
- [x] Episode Journal boundary is locked as audit and replay record, not memory.
- [x] Failure taxonomy extension position is documented.
- [x] Context OS / Working Set Compiler note exists.
- [x] Canonical state is not treated as execution trace.
- [x] Tool log is not treated as canonical state.
- [x] Memory append is not treated as learning.
- [x] Verifier Runtime is not treated as final-answer-only judging.
- [x] Rollback is not treated as always possible.

## Related Documents

- [Project Manifest](Project_Manifest.md)
- [Glossary](Glossary.md)
- [Traceability Matrix](Traceability_Matrix.md)
- [Minimal Closed Loop Runtime Spec](../02_specs/Minimal_Closed_Loop_Runtime_Spec.md)
- [Execution IR and Episode Semantics](../02_specs/Execution_IR_and_Episode_Semantics.md)
- [Evidence Packet and Verifier Runtime](../02_specs/Evidence_Packet_and_Verifier_Runtime.md)
- [Commit Abort Replay Semantics](../02_specs/Commit_Abort_Replay_Semantics.md)
- [Context OS and Working Set Compiler Note](../02_specs/Context_OS_and_Working_Set_Compiler_Note.md)
