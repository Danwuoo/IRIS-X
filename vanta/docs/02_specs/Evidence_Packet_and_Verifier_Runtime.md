# Evidence Packet and Verifier Runtime

## Purpose

Define the structured evidence and verifier outputs needed to reduce invalid commits and make validation auditable.

## Scope

- Evidence Packet fields.
- Verifier inputs and outputs.
- Evidence sufficiency.
- False accept and false reject tracking.
- Provenance requirements.
- Requests for additional evidence.

## Non-goals

- Proving the Evidence Packet schema is optimal.
- Assuming model-generated explanations are faithful evidence.
- Replacing human review in high-risk cases.

## Inputs

- Pre-state summary.
- Execution step reference.
- Observation or tool output.
- Post-state summary.
- Constraints and policy requirements.
- Provenance metadata.

## Outputs

- Evidence Packet.
- Verifier output.
- Validity, confidence, risk, and calibration fields.
- Violated constraints.
- Required extra evidence.
- Credit hints for failure analysis.

## Key Concepts

- Evidence Packet is not an explanation; it is structured material for verification, audit, recovery, and regression.
- Provenance should come from external tools, environment diffs, source documents, or runtime metadata when possible.
- False accept is more dangerous than false reject for side-effectful actions.
- Verifier Runtime must not be reduced to final-answer-only judging.

## PS1-G6 Structured Edit Evidence And Verifier Contract

`PS1-G6` defines action-specific Evidence Packet observations and deterministic
Verifier Runtime checks for fixture-local structured Document Ops actions. A
contract validation that reports `passed: false` is a valid observation when it
includes the source hash, contract provenance, and failure list; the verifier
rejects missing or inconsistent evidence, not the mere presence of a documented
contract failure.

| Action | Required evidence | Required verifier checks |
| --- | --- | --- |
| `inspect_document_structure` | file hash, parsed structure summary, parse diagnostics, selected structure refs, source provenance | fixture-local path, no mutation, reproducible structure summary, diagnostics recorded |
| `validate_document_contract` | file hash, contract hash or contract ref, validation result, failure list, source and contract provenance | fixture-local source and contract refs, pass/fail result present, failures tied to source and contract versions, no mutation |
| `simulate_structured_edit` | before hash, after hash, candidate content, diff, operation summary, selector resolution, `source_hash_after_simulation`, source provenance | selector resolves exactly once, source hash remains unchanged, candidate content and diff are present, no source mutation occurs |
| `apply_reversible_structured_edit` | before hash, after hash, diff, backup metadata, source hash after write, operation summary, selector resolution, source provenance | selector resolves exactly once, backup artifact exists, backup metadata exists, backup policy is `fixture_backup_restore`, before/after/source hashes match evidence, write stays fixture-local, rollback metadata supports restore |

Ambiguous selectors, missing structured targets, absent contract provenance, or
source mutation during simulation cause verifier rejection or an explicit
request for additional evidence before any commit path. Fixture-local negative
tests may use explicit structured-edit `fault_injection` payloads to prove the
verifier rejects mutation, missing backup metadata, and missing backup files;
these fault injections are test fixtures, not expanded production actions.

## PS1-G8 Side-Effect Evidence Boundary

[Side-Effect Escalation Gate](../00_manifest/Side_Effect_Escalation_Gate.md)
accepts `PS1-G8` for side-effect specification, schema impact review,
evaluation planning, and implementation planning only. It does not authorize
runtime execution of `COMMITTABLE`, `IRREVERSIBLE`, or `MEMORY_WRITE` actions.

Future evidence contracts for `COMMITTABLE` actions must include target
identity, pre-effect evidence, post-effect evidence, idempotency or duplicate
guards, approval records, verifier `accept`, and journal refs. `IRREVERSIBLE`
contracts must record risk, approval escalation, `rollback_unavailable`, and
compensation or reconciliation planning before any successor gate can consider
execution. `MEMORY_WRITE` contracts must include a memory candidate, source
provenance, retention and scope policy, staleness and conflict checks, deletion
or retraction path, verifier `accept`, and journal audit.

The first routed `PS1-G8` planning bundle is
[Post-Stage-1 Side-Effect Planning Draft Spec](Post_Stage_1_Side_Effect_Planning_Draft_Spec.md).
It defines pre-effect evidence, post-effect evidence, verifier, and approval
boundaries for a fixture-local Document Ops `COMMITTABLE` planning placeholder
only. It does not collect approvals or produce post-effect evidence.

The 2026-07-16 upstream decision keeps approval as a distinct typed artifact:
a future schema batch must define standalone `approval_record.schema.json` and
typed Episode Journal `approval_record_refs`. Evidence Packet and Verifier
Output may reference and validate approval scope, but neither becomes the
approval record.

For future `fixture_commit_supersede` evaluation beyond declaration
completeness, the evidence contract must bind prior and superseding commit
identity, target identity, before/current/candidate/final hashes, append-only
lineage, prior-artifact retrieval, active-pointer transition, scoped approval,
verifier `accept`, journal refs, compensation idempotency, duplicate/conflict
outcomes, restart recovery, and replay results. No such executable evidence has
been collected.

## PS1-G9 Persistence Evidence Boundary

Evidence Packets remain distinct immutable payloads inside persistence
envelopes. A Verifier Output other than `accept` cannot update the accepted
Canonical State pointer. Every committed step must have resolvable Evidence
Packet and Verifier Output references in its committed Episode Journal;
missing, corrupt, incompatible, or hash-mismatched artifacts fail audit and
replay.

## PS1-G10 Two-Phase Evidence And Approval Boundary

The fixture-local promotion path requires two schema-valid Evidence Packets:
`pre_effect` binds the source/candidate hashes, safe target identity, approval
ref, and no-effect state; `post_effect` binds the committed artifact hash,
unchanged source/candidate hashes, target identity, approval ref, and artifact
ref. Each phase has a distinct Verifier Output and both decisions must be
`accept`.

The standalone Approval Record is separately schema-validated and persisted.
Its `approved` scope must exactly match action, target identity, candidate hash,
gate policy version, and active validity window. Evidence and verifier results
may reference approval, but cannot create or replace it. A missing phase,
missing ref, corrupt artifact, or non-`accept` verifier fails closed.

## Open Questions

- Which evidence fields are mandatory for Stage 1?
- What calibration method should be used for verifier confidence?
- How should verifier disagreement be represented?
- Which evidence fields should become first-class schema properties rather than
  remaining action-specific observation fields after G6 local testing?

## Related Documents

- [Stage 0 Boundary Lock](../00_manifest/Stage_0_Boundary_Lock.md)
- [Post-Stage-1 Runtime Scope Proposal](../00_manifest/Post_Stage_1_Runtime_Scope_Proposal.md)
- [Side-Effect Escalation Gate](../00_manifest/Side_Effect_Escalation_Gate.md)
- [Post-Stage-1 Side-Effect Planning Draft Spec](Post_Stage_1_Side_Effect_Planning_Draft_Spec.md)
- [Design Theory](../01_theory/Design_Theory.md)
- [Validation and Refutation Report](../01_theory/Validation_and_Refutation_Report.md)
