# Post-Stage-1 Runtime Scope Proposal

## Purpose

Define the `PS1-G6` runtime-scope artifact for the first post-Stage-1 runtime
capability expansion.

This document names the structured edit capability and records its local
implementation boundary. The G6 implementation updates runtime schemas, code,
fixtures, and tests together, but it does not authorize broader validation
claims.

## Status

Accepted as the `PS1-G6` implementation-planning artifact on 2026-05-10.
Implemented as a local schema-backed runtime batch on 2026-05-12.

The accepted next runtime capability is `Document Ops Structured Edit Action
Surface v0`.

## Scope

The implemented expansion stays inside the current Document Ops vertical
domain. It remains fixture-local and uses only the already accepted side-effect
classes:

- `READ_ONLY`
- `SIMULATED`
- `REVERSIBLE`

All action proposals must continue to pass through task allowlists,
side-effect-class allowlists, workspace path guards, Evidence Packet
construction, Verifier Runtime checks, Commit Controller handling, and Episode
Journal audit and replay records.

## Non-goals

- Measured experiment results.
- Full Context OS beyond `Working Set Compiler v0`.
- Learned retrieval, ranking, compression, or memory governance.
- `MEMORY_WRITE` effects.
- `COMMITTABLE` external effects.
- `IRREVERSIBLE` effects.
- New non-Document-Ops benchmark domains.
- Production deployment.

## Action Surface

These action types are schema-backed runtime interfaces in the local G6 batch.

| Action | Side-effect class | Expected payload | Required evidence | Verifier checks | Journal and rollback requirements | Acceptance criteria |
| --- | --- | --- | --- | --- | --- | --- |
| `inspect_document_structure` | `READ_ONLY` | `path`, optional `format`, optional `selectors` for headings, sections, line ranges, or JSON paths | file hash, parsed structure summary, parse diagnostics, source path provenance | path stays fixture-local; source is not mutated; parser diagnostics are recorded; requested selectors are represented or explicitly absent | record execution step, Evidence Packet ref, verifier output ref, state hash, and `rollback_policy: not_applicable` | accepted only when the structure summary is reproducible from the source artifact and no mutation occurs |
| `validate_document_contract` | `READ_ONLY` | `path`, `contract_ref` or inline contract, optional `selectors` | file hash, contract hash or contract ref, validation result, failures, source and contract provenance | path and contract refs stay fixture-local; result includes pass/fail and failures; source is not mutated | record audit refs and `rollback_policy: not_applicable` | accepted only when validation output is tied to the exact source and contract versions |
| `simulate_structured_edit` | `SIMULATED` | `path`, `operation`, selector or structured target, replacement or inserted content, optional contract expectations | before hash, after hash, candidate content, diff, operation summary, selector resolution, source provenance | source hash remains unchanged after simulation; diff or result summary exists; selector resolution is explicit; no source mutation occurs | record simulated action step and `rollback_policy: not_applicable`; no backup metadata required | accepted only when candidate output is reconstructable and the source file remains unchanged |
| `apply_reversible_structured_edit` | `REVERSIBLE` | same payload shape as `simulate_structured_edit`, plus optional backup policy metadata | before hash, after hash, diff, backup metadata, source hash after write, operation summary, selector resolution, source provenance | backup file and backup metadata exist; before/after hashes match evidence; write stays fixture-local; rollback can restore the prior source | record `rollback_policy: fixture_backup_restore`, backup metadata, commit status, rollback status, evidence ref, and verifier output ref | accepted only when the edit commits after verifier `accept` and rollback metadata is sufficient for fixture-local restore |

## Common Contract

- Structured-edit actions must not bypass existing planner action
  sequence validation, Execution IR compilation, verifier checks, or commit
  rules.
- Action payloads must identify a concrete fixture-local source path
  and a structured target rather than relying on free-form prose alone.
- Structured target resolution must be auditable. If a selector is ambiguous or
  absent, the action must reject or request additional evidence before commit.
- Simulated edits must include `candidate_content`, `diff`, `before_hash`, and
  `after_hash`, and must leave the source hash unchanged.
- Reversible edits must include backup metadata and must use
  `fixture_backup_restore` as the rollback policy.
- The implemented selector set is `heading`, `section`, `line_range`, and
  `json_path`; the implemented operation set is `replace`, `insert_before`,
  and `insert_after`.
- `COMPENSABLE` remains limited to the existing Phase 4 fixture-local receipt
  treatment. This G6 batch does not expand compensation semantics or external
  side effects.

## Spec And Schema Path

The implementation batch updates the relevant runtime specs and schemas
together:

- [Execution IR and Episode Semantics](../02_specs/Execution_IR_and_Episode_Semantics.md)
  defines the structured-edit action semantics, side-effect class mapping,
  rollback policy, and rejection conditions.
- [Evidence Packet and Verifier Runtime](../02_specs/Evidence_Packet_and_Verifier_Runtime.md)
  defines required evidence fields and verifier checks for each
  action.
- [Commit Abort Replay Semantics](../02_specs/Commit_Abort_Replay_Semantics.md)
  defines commit, abort, rollback, replay, and audit behavior for simulated
  and reversible structured edits.
- `execution_step.schema.json`, `planner_action_sequence.schema.json`, and
  `benchmark_task.schema.json` accept the new action names and structured
  payload contracts in the same implementation batch.

## Evaluation And Reporting Boundary

This G6 batch is a local implementation and test batch. Any future measured
claim requires:

- updated schemas and runtime tests
- fixtures that exercise positive and negative structured-edit cases
- Evidence Packet, verifier, journal, replay, and rollback checks
- the accepted post-Stage-1 metric policy when results are reported as a Lane A
  acceptance candidate
- the accepted labeling policy when human or secondary labels are used

Until measured results are collected and accepted by the relevant future gate,
reports may describe this capability only as
`PS1-G6 structured edit runtime interface implemented and locally tested`, not
as validated or accepted by measured closure.

## Related Documents

- [Project Manifest](Project_Manifest.md)
- [Post-Stage-1 Advancement Gate](Post_Stage_1_Advancement_Gate.md)
- [Post-Stage-1 Gate Inventory](Post_Stage_1_Gate_Inventory.md)
- [Stage 1 MVP Entry Gate](Stage_1_MVP_Entry_Gate.md)
- [Execution IR and Episode Semantics](../02_specs/Execution_IR_and_Episode_Semantics.md)
- [Evidence Packet and Verifier Runtime](../02_specs/Evidence_Packet_and_Verifier_Runtime.md)
- [Commit Abort Replay Semantics](../02_specs/Commit_Abort_Replay_Semantics.md)
