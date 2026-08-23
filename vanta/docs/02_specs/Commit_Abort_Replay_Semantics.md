# Commit Abort Replay Semantics

## Purpose

Define the semantics for committing, aborting, rolling back, reconciling, and replaying runtime episodes.

## Scope

- Commit status transitions.
- Abort behavior.
- Rollback and compensation notes.
- Replay-safe logging requirements.
- Runtime manifest references.
- Audit completeness.

## Non-goals

- Treating all external side effects as reversible.
- Implementing distributed transactions in the MVP.
- Hiding unsafe actions behind prompt-only checks.

## Inputs

- Execution step.
- Evidence Packet.
- Verifier output.
- Side-effect class.
- Runtime manifest.
- State hash.

## Outputs

- Commit, abort, rollback, or reconciliation status.
- Episode Journal update.
- Replay record.
- Audit artifact.

## Key Concepts

- `commit` applies a verified change to the accepted runtime state.
- `abort` stops an uncommitted action path.
- `rollback` applies only to reversible changes.
- `reconcile` or compensation is required when external effects cannot be strictly rolled back.
- Phase 4 fixture-local compensable actions must record compensation treatment
  rather than claiming strict rollback.
- `replay` requires enough versioned runtime and tool metadata to reconstruct the episode.
- Episode Journal records audit and replay data; it is not durable memory.

## PS1-G6 Structured Edit Commit And Replay Contract

`PS1-G6` preserves the existing Stage 1 commit, rollback, and replay
boundaries while adding fixture-local structured Document Ops actions.

| Action class | Commit behavior | Abort or reject behavior | Replay requirement |
| --- | --- | --- | --- |
| `READ_ONLY` structured inspection and contract validation | May update accepted runtime state only with verified observation summaries and audit refs; source files remain unchanged. | Reject or request evidence when source, contract, parse, or provenance evidence is missing. | Replay must reproduce the same fixture-local read or validation observation from versioned source and contract refs. |
| `SIMULATED` structured edit | May commit only the verified simulated observation, candidate content reference, diff, and state event; source files remain unchanged. | Reject if simulation mutates source, lacks diff/candidate content, or has ambiguous selector resolution. | Replay must reproduce the candidate content, diff, before/after hashes, and unchanged source hash. |
| `REVERSIBLE` structured edit | May commit only after verifier `accept`, required Evidence Packet fields, fixture-local write, and backup metadata are present. | Abort or reject when backup metadata, hash agreement, fixture-local path safety, or verifier accept is missing. | Replay must reconstruct the edit path and confirm backup metadata is sufficient for fixture-local restore. |

Replay compares commit status, step count, state hash, and observation
signatures when artifacts are available. The observation signature covers
action kind, path, selector resolution status, diff, before/after hashes, and
contract pass/failure result.

`PS1-G6` does not expand `COMPENSABLE`, `COMMITTABLE`, `IRREVERSIBLE`, or
`MEMORY_WRITE` behavior. Rollback must be recorded only for reversible
fixture-local edits with concrete backup metadata.

## PS1-G8 Side-Effect Commit Boundary

[Side-Effect Escalation Gate](../00_manifest/Side_Effect_Escalation_Gate.md)
accepts `PS1-G8` for side-effect specification, schema impact review,
evaluation planning, and implementation planning only. It does not authorize
runtime execution of `COMMITTABLE`, `IRREVERSIBLE`, or `MEMORY_WRITE` actions.

Future `COMMITTABLE` commit paths must record approval, verifier `accept`,
pre/post effect evidence, idempotency or duplicate guards, and either rollback
availability or compensation declaration before commit. `IRREVERSIBLE` paths
must remain blocked until a successor gate defines explicit escalation,
`rollback_unavailable`, risk records, compensation or reconciliation plans, and
post-action audit requirements. `MEMORY_WRITE` paths must record the memory
candidate, provenance, retention and scope, deletion or retraction path,
approval policy, verifier `accept`, and Episode Journal audit refs; memory
append is not learning.

The first routed `PS1-G8` planning bundle is
[Post-Stage-1 Side-Effect Planning Draft Spec](Post_Stage_1_Side_Effect_Planning_Draft_Spec.md).
It defines a fixture-local Document Ops `COMMITTABLE` commit-proposal planning
surface with required rollback or compensation statements. It does not create a
commit path, rollback path, approval record, or replayable runtime episode.

The 2026-07-16 upstream decision selects copied-workspace Document Ops
candidate promotion as the first post-`PS1-G8` domain. A future separately
authored and accepted `Fixture-Local Document Commit Execution v0` gate may
authorize implementation and actual execution only for explicitly marked
ephemeral copied fixtures. Until that gate exists and is accepted, runtime
dispatch remains blocked and no action enum or allowlist change is authorized.

For future `fixture_commit_supersede`, replay must prove append-only linkage
between prior and superseding commit identities, shared target identity,
before/current/candidate/final hashes, an immutable retrievable prior artifact,
the active-pointer transition, scoped approval, verifier and evidence refs,
compensation idempotency and duplicate/conflict outcomes, restart recovery, and
the final accepted state hash. A declaration alone is not compensation
adequacy.

## PS1-G9 Persistence, Hash, And Replay Contract

`PS1-G9` resolves Canonical State hashing as deterministic semantic JSON under
`canonical-json-sha256-v1`, excluding `state_hash` and non-canonical runtime
metadata while retaining the existing SHA-256 digest algorithm.

Replay success is fail-closed. Episode/task identity, runtime/schema version,
ordered step count, action type, side-effect class, step/commit status,
rollback/recovery status, the full Canonical State hash sequence, Evidence
Packet and Verifier Output references, observation signatures, structured-edit
path and selector resolution, before/after hashes, diff or contract result, and
final accepted state hash must all be present and match. "When artifacts are
available" is not sufficient for the Persistence v0 acceptance path.

The accepted Canonical State pointer, committed Episode Journal pointer, typed
artifacts, and logical idempotency record are one SQLite transaction. A
fixture-local reversible effect is prepared before filesystem mutation and
recovered according to
[Persistence and Recovery Semantics](Persistence_and_Recovery_Semantics.md).

## PS1-G10 Prepared Promotion, Restore, And Replay

Before candidate promotion, SQLite must contain a durable `prepared` intent
with the idempotency/request identity, target identity, pre-effect target hash,
backup metadata, and strict `fixture_commit_restore` policy. The file effect
cannot be committed until post-effect evidence and verifier acceptance exist
and one SQLite logical transaction persists state, step, Approval Record,
pre/post evidence, pre/post verifier outputs, Episode Journal, committed
artifact, and accepted refs.

Same-key same-request retries return the recorded result without another file
effect. Same-key different-request retries are conflicts. A crash or uncertain
state never defaults to committed. An uncommitted effect must restore the prior
target or remove a newly created target; failure to prove that restore becomes
`recovery_required`.

Strict replay additionally compares approval and committed-artifact refs,
target identity, candidate/committed hashes, evidence phases, idempotency
identity, and recovery result. Missing or corrupt refs and injected mismatch
must fail replay. G10 v0 does not execute `fixture_commit_supersede`.

## Open Questions

- Resolved by `PS1-G10`: copied-workspace Document Ops candidate promotion is
  executable only within the accepted task-specific G10 boundary.
- Resolved pointer: Canonical State hash granularity is defined by `PS1-G9` and
  `canonical-json-sha256-v1`.
- How should compensation be represented for non-reversible actions beyond the
  Phase 4 fixture-local compensation record?
- What additional replay fields should be compared before using structured
  edits in larger measured runs?

## Related Documents

- [Stage 0 Boundary Lock](../00_manifest/Stage_0_Boundary_Lock.md)
- [Post-Stage-1 Runtime Scope Proposal](../00_manifest/Post_Stage_1_Runtime_Scope_Proposal.md)
- [Side-Effect Escalation Gate](../00_manifest/Side_Effect_Escalation_Gate.md)
- [Post-Stage-1 Side-Effect Planning Draft Spec](Post_Stage_1_Side_Effect_Planning_Draft_Spec.md)
- [Design Theory](../01_theory/Design_Theory.md)
- [Validation and Refutation Report](../01_theory/Validation_and_Refutation_Report.md)
