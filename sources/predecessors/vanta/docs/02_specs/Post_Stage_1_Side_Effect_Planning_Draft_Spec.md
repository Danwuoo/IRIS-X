# Post-Stage-1 Side-Effect Planning Draft Spec

## Purpose

Define the first minimum routable side-effect planning contract allowed by
`PS1-G8`.

This draft names a fixture-local Document Ops `COMMITTABLE` planning surface so
future schema, verifier, approval, rollback, compensation, and evaluation work
can route through a concrete object. It is not a runtime implementation spec.

## Status

Spec status: `Side-effect planning draft`.

Planning surface ID: `PS1-LC-SIDEFX-COMMITTABLE-DOCOPS-001`.

Gate policy version: `PS1-LC-SIDEFX-GATE-001`.

Surface name: `Fixture-Local Document Ops Commit Proposal Surface v0`.

Run status: `committable_docops_planning_pilot` complete at
`docs/04_experiments/results/side_effect_planning/20260715_223158/`.

Implementation status: `Not authorized`.

Runtime execution status: `Not authorized`.

Schema status: no schema changes in this planning batch.

Allowed side-effect scope in this draft: `COMMITTABLE` planning placeholder for
fixture-local Document Ops only.

Blocked side-effect scope in this draft: runtime `COMMITTABLE` execution,
`IRREVERSIBLE` execution or planning surface, and `MEMORY_WRITE` execution or
planning surface.

Claim level: planning artifact only. This document does not validate H5, approve
production readiness, or create a runtime approval path.

The measured pilot implements the planning-record validator and runner for this
draft without promoting the draft to an executable runtime spec. Its proposal
format remains pilot-local and is not a JSON Schema authority.

Upstream successor decisions: `OQ-SCHEMA-013`, `OQ-SCHEMA-014`,
`OQ-IMPL-007`, `OQ-IMPL-008`, and `OQ-MEAS-010` were resolved on 2026-07-16.
They constrain a future successor batch but do not create its gate, change a
schema, add an action, expand an allowlist, or authorize execution.

## Inputs

This planning draft depends on:

- [Side-Effect Escalation Gate](../00_manifest/Side_Effect_Escalation_Gate.md)
- [Post-Stage-1 Advancement Gate](../00_manifest/Post_Stage_1_Advancement_Gate.md)
- [Execution IR and Episode Semantics](Execution_IR_and_Episode_Semantics.md)
- [Evidence Packet and Verifier Runtime](Evidence_Packet_and_Verifier_Runtime.md)
- [Commit Abort Replay Semantics](Commit_Abort_Replay_Semantics.md)
- [Post-Stage-1 Runtime Scope Proposal](../00_manifest/Post_Stage_1_Runtime_Scope_Proposal.md)
- [Post-Stage-1 Metric Policy](../05_evaluation/Post_Stage_1_Metric_Policy.md)

The accepted Lane A `20260601_113121` closure proves only that the named
fixture-local Document Ops sample held its existing process-integrity floors. It
is not evidence that `COMMITTABLE` execution is safe.

## Planning Boundary

| Area | Planning rule |
| --- | --- |
| Domain | Fixture-local Document Ops only. |
| Surface type | Planning records for a future `COMMITTABLE` document commit proposal. |
| Runtime action | No new action is added to the runtime allowlist or schema action enum in this batch. |
| Current executable side-effect classes | Stay limited to accepted `READ_ONLY`, `SIMULATED`, `REVERSIBLE`, and existing fixture-local `COMPENSABLE` behavior. |
| Target scope | Future targets must be copied fixture-workspace artifacts, never source fixtures, repository docs, external systems, user files, production services, or memory stores. |
| Approval | Approval policy and approval record requirements are specified as future requirements only. No approval record is collected or accepted by this draft. |
| Verifier | Verifier requirements are planning requirements. Verifier `accept` is never an approval substitute. |
| Rollback | Rollback is not assumed. A plan must state strict rollback availability or a compensation declaration before any later execution batch can be considered. |
| Compensation | Fixture-local supersession may be planned as compensation, but it is not strict rollback. |
| Claims | No H5, runtime safety, production, broad side-effect governance, or external-action claim is allowed. |

## Resolved Successor Boundary

The first post-`PS1-G8` executable domain, if its separate successor gate is
later authored and accepted, is copied-workspace Document Ops candidate
promotion. The future scope is limited to explicitly marked ephemeral copied
fixture workspaces. Source fixtures, repository documents, user files,
external or production systems, memory stores, and irreversible targets remain
out of scope.

The working successor name is `Fixture-Local Document Commit Execution v0`.
This document does not create, accept, or close that gate. A future accepted
gate may authorize implementation and actual `COMMITTABLE` execution only
inside the named copied-fixture scope. Until then, runtime dispatch remains
blocked.

## Surface Definition

`Fixture-Local Document Ops Commit Proposal Surface v0` plans a future effect in
which a verified candidate document artifact would be promoted to a fixture-local
committed artifact location in a copied run workspace.

Within the completed `PS1-G8` planning batch, the future action name
`commit_fixture_document_candidate` was a planning placeholder only: that batch
did not add it to action schemas or send it to `Vanta.Runtime.run_task/3`.
The later accepted `PS1-G10` successor now adds the explicit action and may send
it through the runtime only under its dedicated payload, approval, copied-
workspace, SQLite, evidence, verifier, rollback, audit, and replay gates. This
does not retroactively turn the G8 pilot into an executable run.

`OQ-SCHEMA-014` is resolved for successor design: the future executable
surface must use the explicit `commit_fixture_document_candidate` action enum
and a dedicated payload contract. It must not be implemented as a policy-gated
extension of `simulate_structured_edit` or
`apply_reversible_structured_edit` output. This resolution does not add the
enum or payload to current schemas.

The surface is intentionally narrow:

- one fixture-local source document
- one candidate document artifact
- one proposed commit target path inside a copied fixture workspace
- one idempotency key
- one approval policy reference
- one rollback or compensation declaration
- no external service, user account, durable memory store, production system, or
  irreversible target

## Minimum Commit Proposal Record

The minimum routable planning object is a Markdown or future machine-readable
record with these fields. These are planning fields, not current JSON Schema
requirements.

| Field | Required meaning |
| --- | --- |
| `proposal_id` | Stable planning identifier for the proposed commit. |
| `surface_id` | `PS1-LC-SIDEFX-COMMITTABLE-DOCOPS-001`. |
| `gate_policy_version` | `PS1-LC-SIDEFX-GATE-001`. |
| `side_effect_class` | `COMMITTABLE`, planning placeholder only. |
| `fixture_id` | The Document Ops fixture that would own the copied workspace. |
| `target_identity` | Structured identity of the fixture workspace, source artifact, candidate artifact, and proposed committed artifact path. |
| `source_artifact_ref` | Fixture-local source document ref and content hash. |
| `candidate_artifact_ref` | Candidate document ref, content hash, and generation step ref. |
| `proposed_commit_target` | Path inside a copied fixture workspace where the candidate would be promoted. |
| `expected_effect` | Precise statement of the intended committed artifact and manifest effect. |
| `preconditions` | Required source hash, candidate hash, target path guard, contract checks, and duplicate guard. |
| `postconditions` | Required committed artifact hash, target path, manifest entry, and audit refs for a future execution batch. |
| `approval_policy_ref` | Versioned policy defining who or what may approve the future commit. |
| `approval_record_requirement` | Required fields for a future approval record; no record is accepted in this draft. |
| `idempotency_key` | Duplicate guard binding fixture, source hash, candidate hash, and target identity. |
| `duplicate_guard` | Rule for rejecting repeated or conflicting commits to the same target. |
| `pre_effect_evidence_requirements` | Evidence required before any future effect. |
| `post_effect_evidence_requirements` | Evidence required after any future effect. |
| `verifier_policy_ref` | Versioned verifier policy required before commit. |
| `rollback_or_compensation_statement` | Explicit strict rollback availability or compensation declaration. |
| `journal_requirements` | Execution step, Evidence Packet, verifier output, approval record, commit status, and rollback or compensation refs required for future audit. |
| `rejection_conditions` | Conditions that make the proposal invalid before runtime execution. |

## Evidence, Verifier, And Approval Boundary

Future `COMMITTABLE` execution must not be considered until the evidence,
verifier, and approval layers are distinct.

| Layer | Required future content | Boundary |
| --- | --- | --- |
| Pre-effect evidence | Source hash, candidate hash, diff, selector or target resolution, contract validation, target path safety, idempotency key, duplicate guard, and policy refs. | Evidence is structured input to verification, not an approval decision. |
| Verifier output | `decision: accept`, `side_effect_safety`, `policy_constraints`, `state_consistency`, and explicit rejection of missing approval, missing duplicate guard, path escape, or missing rollback or compensation statement. | Verifier `accept` is necessary but insufficient for commit. |
| Approval record | Standalone typed approval artifact with approver type, approver identity or policy engine identity, scope, timestamp, target identity, policy version, and approval result; the Episode Journal links it through typed approval-record refs. | Human labels, fixture oracle labels, verifier outputs, and final-answer judgments are not runtime approvals. Approval objects must not be inlined into the Episode Journal. |
| Post-effect evidence | Committed artifact hash, target path, manifest diff, post-state hash, and audit refs. | Post-effect evidence cannot be fabricated from the plan; it only exists after a later authorized execution batch. |

This planning batch does not collect approval records. A future evaluation may
check whether a plan names the approval boundary, but it must not report that
runtime approval occurred.

`OQ-SCHEMA-013` is resolved for successor design: a future schema batch must
define standalone `approval_record.schema.json` authority and add typed
`approval_record_refs` to the Episode Journal. The approval artifact remains
distinct from Evidence Packet, Verifier Output, labels, and fixture oracles.
No JSON Schema file changes in this decision-only batch.

## Rollback Or Compensation Statement

Every commit proposal must state one of these planning outcomes before any later
runtime batch can be considered.

| Statement | Meaning | Current status |
| --- | --- | --- |
| `fixture_commit_restore` | Strict rollback would be available because the target is fixture-local, a pre-effect backup exists, and restore evidence can be verified. | Future schema and runtime candidate only; not implemented here. |
| `fixture_commit_supersede` | Strict rollback is not claimed; compensation would create a superseding fixture-local commit record that marks the prior commit superseded. | Future schema and runtime candidate only; not implemented here. |
| `rollback_or_compensation_missing` | The proposal lacks a rollback or compensation declaration. | Must reject at planning review. |

`fixture_commit_supersede` is a compensation or reconciliation statement, not a
claim that the original effect was rolled back.

### Minimum Supersession Compensation Evidence

`OQ-MEAS-010` is resolved for future executable evaluation. Declaration
completeness is insufficient. Evaluation beyond the completed planning pilot
must require all of the following:

- prior and superseding commit identities bound to the same typed target
  identity;
- prior committed, current pre-compensation, superseding candidate, and final
  active artifact hashes;
- append-only supersession lineage that leaves the prior artifact immutable and
  retrievable while moving the active pointer to the superseding commit;
- a target-scoped approval record, verifier `accept`, pre/post-effect Evidence
  Packet refs, Episode Journal refs, and final accepted state hash;
- a compensation idempotency key, deterministic request hash, and duplicate or
  conflicting-commit guard; and
- measured happy-path supersession, same-key retry without duplicate effect,
  stale or conflicting predecessor rejection, restart recovery, audit
  completeness, and replay consistency.

No such evidence has been collected yet. `fixture_commit_supersede` remains
non-executable until a future accepted gate, implementation, fixtures, and
measured run satisfy this floor.

## Rejection Conditions

A `COMMITTABLE` Document Ops planning proposal must be rejected or labeled
`blocked_missing_approval`, `blocked_missing_compensation_policy`, or the
closest successor report label if it:

- omits `PS1-LC-SIDEFX-GATE-001`
- appears in current runtime `allowed_actions`
- targets repository source docs, source fixtures, test fixture roots, external
  systems, user files, production services, or memory stores
- lacks target identity, candidate hash, source hash, idempotency key, or
  duplicate guard
- lacks an approval policy reference or approval record requirement
- treats verifier `accept`, a human label, or a fixture oracle as runtime
  approval
- lacks a rollback or compensation statement
- treats compensation as strict rollback
- introduces `IRREVERSIBLE` or `MEMORY_WRITE` behavior
- reports H5 validation, production readiness, or runtime approval

## Outputs

The source planning bundle is:

| Output | Path in this batch | Status |
| --- | --- | --- |
| Side-effect planning draft spec | `docs/02_specs/Post_Stage_1_Side_Effect_Planning_Draft_Spec.md` | Draft |
| Schema impact review | `docs/03_schemas/Post_Stage_1_Side_Effect_Schema_Impact_Review.md` | Draft, no schema changes |
| Side-effect evaluation plan | `docs/04_experiments/Post_Stage_1_Side_Effect_Evaluation_Plan.md` | Executed by named planning pilot |

These outputs are routing artifacts. They do not replace runtime specs, schemas,
fixtures, implementation code, tests, or measured reports required by a later
implementation batch.

The completed planning pilot additionally writes immutable planning fixtures
under `docs/04_experiments/fixtures/side_effect_planning/`, measured artifacts
under `docs/04_experiments/results/side_effect_planning/20260715_223158/`, and
the
[planning pilot run report](../05_evaluation/Post_Stage_1_Side_Effect_Planning_Pilot_Run_Report.md).
These are evaluation artifacts and do not replace an executable action spec or
schema batch.

## Resolved Pointers And Open Questions

- Resolved pointer: `OQ-SCHEMA-013` selects standalone future
  `approval_record.schema.json` authority plus typed Episode Journal
  `approval_record_refs`.
- Resolved pointer: `OQ-SCHEMA-014` selects explicit future action
  `commit_fixture_document_candidate` with a dedicated payload contract.
- Resolved pointer: `OQ-IMPL-007` selects copied-workspace Document Ops
  candidate promotion as the first post-`PS1-G8` domain.
- Resolved pointer: `OQ-IMPL-008` requires a separately authored and accepted
  `Fixture-Local Document Commit Execution v0` successor gate before
  implementation or execution.
- Resolved pointer: `OQ-MEAS-010` defines the minimum executable supersession
  compensation-evidence floor above; evidence is not yet collected.
- Which future label packet, if any, should review approval-boundary adequacy
  without converting labels into runtime approval?

## Related Documents

- [Project Manifest](../00_manifest/Project_Manifest.md)
- [Document Map](../00_manifest/Document_Map.md)
- [Traceability Matrix](../00_manifest/Traceability_Matrix.md)
- [Side-Effect Escalation Gate](../00_manifest/Side_Effect_Escalation_Gate.md)
- [Post-Stage-1 Advancement Gate](../00_manifest/Post_Stage_1_Advancement_Gate.md)
- [Execution IR and Episode Semantics](Execution_IR_and_Episode_Semantics.md)
- [Evidence Packet and Verifier Runtime](Evidence_Packet_and_Verifier_Runtime.md)
- [Commit Abort Replay Semantics](Commit_Abort_Replay_Semantics.md)
- [Post-Stage-1 Side-Effect Schema Impact Review](../03_schemas/Post_Stage_1_Side_Effect_Schema_Impact_Review.md)
- [Post-Stage-1 Side-Effect Evaluation Plan](../04_experiments/Post_Stage_1_Side_Effect_Evaluation_Plan.md)
- [Post-Stage-1 Side-Effect Planning Pilot Run Report](../05_evaluation/Post_Stage_1_Side_Effect_Planning_Pilot_Run_Report.md)
