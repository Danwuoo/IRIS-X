# Fixture-Local COMMITTABLE Document Promotion v0

## Authority And Status

- Gate: `PS1-G10 — Fixture-Local COMMITTABLE Execution Gate`
- Gate policy: `PS1-LC-FIXTURE-COMMIT-GATE-001`
- Spec version: `fixture-local-committable-document-promotion-v0`
- Action: `commit_fixture_document_candidate`
- Side-effect class: `COMMITTABLE`
- Status: `Accepted implementation specification`
- Measured status: run `20260716_020716` passed 28/28 and all hard gates
- Closure status: `accepted_by_closure`

This specification implements the accepted G10 scope. Normative behavior is
limited to one copied ephemeral Document Ops fixture workspace and one candidate
promotion. It does not authorize any other `COMMITTABLE` action or target.

## Typed Action Payload

The dedicated payload requires:

| Field | Contract |
| --- | --- |
| `target_identity` | Exact `fixture_id`, `workspace_id`, marker path, source path, candidate path, and committed path. |
| `source_hash` | Actual SHA-256 of the immutable copied-workspace source document. |
| `candidate_hash` | Actual SHA-256 of the already generated candidate document. |
| `approval_record_ref` | Standalone Approval Record ID supplied to runtime and persisted as its own artifact. |
| `approval_policy_version` | Must equal the approval scope policy version. |
| `idempotency_key` | Globally unique within the SQLite authority for this logical request. |
| `rollback_or_compensation_statement` | `fixture_commit_restore` only in v0. |

The action is allowed only when task `allowed_actions` contains the exact action
and task `side_effect_classes` contains `COMMITTABLE`. It remains absent from
general model-planner action enumeration.

## Workspace And Path Contract

The copied workspace must contain `.vanta_fixture_workspace.json` with
`scope = fixture_local_committable_v0`, `ephemeral = true`, and identity equal
to the action payload. Safe-resolution and directory rules are:

- source: `inputs/**`;
- candidate: `candidates/**`;
- committed artifact: `committed/**`;
- none of the three paths may be equal;
- paths must remain inside the copied workspace after expansion;
- source and candidate must exist before preparation; and
- the source-fixture root used to create the copy is never an effect target.

## Approval Boundary

`approval_record.schema.json` is standalone authority. The runtime receives a
record through an explicit approval-record map, validates it before effect, and
persists the record as an immutable `approval_record` artifact only if it is
schema-valid.

Commit approval requires:

- `decision = approved`;
- `action_type = commit_fixture_document_candidate`;
- target identity exactly equal to the action target;
- candidate hash exactly equal to action and file hash;
- scope policy version equal to the action policy version;
- `not_before <= runtime time < expires_at`; and
- an approver type and identity recorded by the schema.

Denied, missing, corrupt, expired, wrong-action, wrong-target, wrong-candidate,
or wrong-policy records reject before effect. Verifier output, labels, fixture
oracles, and planning pilots never satisfy this boundary.

## Evidence And Verification Phases

Two Evidence Packets and two Verifier Outputs are required.

### Pre-effect

The normalized observation records workspace marker identity, safe resolved
relative paths, source/candidate hashes, pre-target existence/hash, approval
record ref, policy version, idempotency key, request hash, and rollback policy.
The pre-effect verifier must return `accept` before durable prepare or effect.
Missing evidence returns `request_evidence`; policy, approval, identity, path,
or hash failures return `reject`.

### Post-effect

The observation records committed artifact path/hash, unchanged source and
candidate hashes, target identity, effect count, prepared recovery ID, and
rollback availability. The post-effect verifier requires the committed hash to
equal the candidate hash and both source and candidate inputs to remain
unchanged. Non-accept triggers rollback or `recovery_required`, never commit.

## Durable Protocol

1. Compile and schema-validate the named action.
2. Compute deterministic request identity and enforce idempotency/conflict.
3. Validate marker, paths, hashes, Approval Record, pre-effect Evidence Packet,
   and pre-effect verifier `accept`.
4. Create target backup metadata and persist recovery status `prepared`.
5. Copy candidate bytes to the committed path.
6. Mark effect applied durably.
7. Build post-effect Evidence Packet and require verifier `accept`.
8. Construct accepted Canonical State and Episode Journal with typed approval,
   evidence, verifier, and committed-artifact refs.
9. In one SQLite transaction persist step, Approval Record, both Evidence
   Packets, both Verifier Outputs, Canonical State, Episode Journal, accepted
   pointers, and logical idempotency result.
10. Mark recovery `commit_completed`, then return.

`prepared` must precede the filesystem effect. Database commit must not precede
post-effect verification. No crash window defaults to committed.

## Idempotency And Conflict

The request hash binds episode/task/step, action payload, side-effect class,
pre-state hash, runtime/schema/hash-policy versions, approval ref, target
identity, source/candidate hashes, and policy version.

- same key + same request returns the durable prior result with zero new effect;
- same key + different request returns `idempotency_conflict` with zero new
  effect; and
- incomplete prepared state resumes only through durable recovery evidence.

## Rollback And Recovery

`fixture_commit_restore` is strict rollback for the copied fixture. If the
target did not exist, restore removes the created artifact and verifies absence.
If it existed, restore copies the durable backup and verifies the pre-effect
hash. Missing or corrupt backup evidence becomes `recovery_required`; it is not
reported as successful rollback.

The v0 implementation does not execute supersession compensation. The upstream
`fixture_commit_supersede` evidence floor remains a successor requirement.

## Journal, Audit, And Replay

A committed journal must contain:

- the committed action step;
- the full accepted state-hash sequence;
- both Evidence Packet IDs;
- both Verifier Output IDs;
- the standalone Approval Record ID;
- a typed committed-artifact ref with target identity and candidate/committed
  hash;
- `commit_status = committed`;
- rollback status; and
- no memory-write effects.

Audit fails closed on missing, corrupt, incompatible, or mismatched state,
journal, approval, evidence, verifier, or artifact refs. Strict replay compares
all identities, ordering, action and side-effect class, approval scope, evidence
phases, verifier decisions, hashes, artifact path, rollback/recovery status,
and final state hash. A mismatch is detected and cannot report consistency.

## Rejection Conditions

Reject without authorized commit for any missing or invalid prerequisite,
path escape, source/candidate/target overlap, source-fixture targeting,
approval/verifier substitution, duplicate conflict, missing durable prepare,
missing post-effect evidence, rollback failure, corrupt ref, irreversible
classification, memory-write field/effect, non-SQLite persistence, or general
planner dispatch attempt.

## Claim Boundary

Implementation or tests alone do not create closure. Only a complete hard-gate
run plus manifest closure may support the exact scoped validation wording. No
H1-H5, broad side-effect safety, production, external target, irreversible,
memory, Context OS, or distributed authority claim follows.
