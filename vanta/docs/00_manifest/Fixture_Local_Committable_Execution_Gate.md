# PS1-G10 — Fixture-Local COMMITTABLE Execution Gate

## Authority

- Gate ID: `PS1-G10`
- Formal name: `Fixture-Local COMMITTABLE Execution Gate`
- Gate policy version: `PS1-LC-FIXTURE-COMMIT-GATE-001`
- Named implementation scope: `Fixture-Local COMMITTABLE Document Promotion v0`
- Gate/spec acceptance date: 2026-07-16
- Gate status: `Accepted and closed for the named scoped implementation`
- Measured status: run `20260716_020716` is `pass_acceptance_candidate` (`28 / 28`)
- Closure status: `accepted_by_closure`

This gate is the separately authored successor required by accepted decision
`OQ-IMPL-008`. It authorizes one named action,
`commit_fixture_document_candidate`, only for explicitly marked ephemeral
copied Document Ops fixture workspaces. Gate acceptance authorizes the schema,
runtime, persistence, fixture, failure-injection, test, and measured-evaluation
batch defined here. It is not `accepted_by_closure` by itself.

## Upstream Accepted Decisions

This gate is authorized only because the following Decision Log entries are
already `Accepted`:

- `OQ-SCHEMA-013`: standalone `approval_record.schema.json` plus typed Episode
  Journal `approval_record_refs`;
- `OQ-SCHEMA-014`: explicit `commit_fixture_document_candidate` action and
  dedicated payload;
- `OQ-IMPL-007`: copied-workspace Document Ops candidate promotion is the first
  executable domain;
- `OQ-IMPL-008`: a separately accepted successor gate may authorize that
  implementation and execution; and
- `OQ-MEAS-010`: executable compensation needs identity, hash, lineage,
  approval, verifier, evidence, journal, idempotency, restart, audit, and replay
  evidence.

`PS1-G9` and its accepted `Fixture-Local SQLite Persistence v0` closure provide
the durable intent, SQLite transaction, idempotency, restart recovery, strict
replay, integrity, and audit substrate. G10 does not replace or broaden G9.

## Authorized Action And Target Boundary

The only newly executable `COMMITTABLE` action is:

```text
commit_fixture_document_candidate
```

It may copy one already generated and hash-verified candidate document to one
committed-artifact path inside the same copied workspace. The workspace must
contain a schema-checked marker declaring it ephemeral and fixture-local. The
source path must be under `inputs/`, the candidate path under `candidates/`, and
the committed path under `committed/`. All paths must resolve inside the copied
workspace and bind to the action's typed target identity.

This gate does not add the action to general model-planner action sets. The
runtime may compile it only when the task explicitly allowlists the named
action and `COMMITTABLE`, the dedicated payload validates, the copied-workspace
marker validates, and SQLite persistence is configured.

## Commit Preconditions

Every successful effect requires all of the following:

- complete target identity and safe copied-workspace paths;
- actual source and candidate hashes equal the action payload;
- a standalone schema-valid runtime Approval Record;
- approval decision `approved` whose scope exactly binds action, target
  identity, candidate hash, policy version, and a non-expired time window;
- pre-effect Evidence Packet completeness;
- pre-effect Verifier Output decision `accept`;
- a unique idempotency key and deterministic request hash;
- a durable `prepared` recovery record before the file effect;
- post-effect Evidence Packet completeness after promotion;
- post-effect Verifier Output decision `accept`;
- unchanged source and candidate hashes;
- committed artifact hash equal to the candidate hash;
- one SQLite logical-commit transaction containing state, step, approval,
  evidence, verifier, journal, and accepted pointers; and
- strict `fixture_commit_restore` rollback metadata for v0.

Verifier `accept` is necessary and cannot substitute for Approval Record
approval. Labels, fixture oracles, planning records, and final-answer judgments
are not approvals.

## Crash, Rollback, And Recovery Rules

- A crash before durable prepare has no authorized effect and recovers to
  `aborted`.
- A prepared record with no effect and an unchanged target recovers to
  `aborted`.
- An effect without the logical database commit is restored from durable
  backup metadata and becomes `rolled_back`, or becomes `recovery_required` if
  restore cannot be proven.
- A logical database commit without a client response is returned through the
  same-key idempotent result and does not repeat the effect.
- Same key plus different request hash is `idempotency_conflict` and cannot
  mutate or overwrite.
- Crash or uncertainty never defaults to committed.

G10 v0 supports strict `fixture_commit_restore`. It does not execute
`fixture_commit_supersede`; the accepted upstream evidence floor remains a
successor requirement if supersession compensation is later implemented.

## Failure-Injection And Acceptance Gate

The executable experiment must cover positive approval, authorization
failures, scope/hash mismatches, verifier rejection/request-evidence, missing
evidence, path/source guards, idempotent duplicate and conflict, all four crash
windows, restart, rollback success/failure detection, corrupt or missing refs,
irreversible misclassification, memory-write smuggling, and strict replay
mismatch detection.

Closure requires one complete measured run with these hard gates:

| Metric | Required |
| --- | ---: |
| `valid_approved_commit_success` | `1.0` |
| `unauthorized_commit_count` | `0` |
| `approval_verifier_substitution_count` | `0` |
| `duplicate_effects` | `0` |
| `idempotency_conflicts_incorrectly_accepted` | `0` |
| `path_escapes_or_source_mutations` | `0` |
| `silent_partial_commits` | `0` |
| `committed_effects_without_durable_refs` | `0` |
| `restart_recovery_success` | `1.0` |
| `rollback_success` | `1.0` for applicable cases |
| `replay_consistency` | `1.0` |
| `audit_completeness` | `1.0` |
| `unsupported_commits` | `0` |
| `irreversible_effects` | `0` |
| `memory_writes` | `0` |

Any failure requires `failed_no_acceptance`, retention of the complete failed
run, an in-scope repair, and a new complete run. Thresholds may not be lowered.
Only a manifest closure may assign `accepted_by_closure` and the exact wording
`validated for Fixture-Local COMMITTABLE Document Promotion v0`.

## Explicit Non-Goals

- repository source, source fixtures, user documents, external systems, or
  production targets;
- general `COMMITTABLE` authority or broad side-effect safety;
- `IRREVERSIBLE`, `MEMORY_WRITE`, durable memory, or full Context OS;
- `fixture_commit_supersede` execution in v0;
- distributed transactions, multi-process authority, HA, or production
  readiness; and
- H1-H5 or full-architecture validation.

## Required Downstream Artifacts

- [Fixture-Local COMMITTABLE Document Promotion v0 Spec](../02_specs/Fixture_Local_Committable_Document_Promotion_v0.md)
- [G10 Schema Impact Review](../03_schemas/Fixture_Local_Committable_Schema_Impact_Review.md)
- action, approval, Evidence Packet, Episode Journal, and persisted-artifact
  schema updates
- runtime and Persistence v0 integration
- immutable fixtures, validator, runner, Mix task, and tests
- [Experiment 007](../04_experiments/Experiment_007_Fixture_Local_Committable_Execution.md)
- measured result directory and evaluation report
- [manifest closure](Post_Stage_1_Fixture_Local_Committable_v0_Closure.md),
  accepted after every hard gate and required test passed

## Measured Candidate

The complete Experiment 007 run at
`docs/04_experiments/results/fixture_local_committable_execution/20260716_020716/`
passed all 28 fixtures and all 15 hard gates. The
[run report](../05_evaluation/Experiment_007_Fixture_Local_Committable_Execution_Run_Report.md)
records the measured evidence. This result remains
`pass_acceptance_candidate` at runner level. After every required repository
command passed, the
[manifest closure](Post_Stage_1_Fixture_Local_Committable_v0_Closure.md)
accepted the exact named scope as `accepted_by_closure`.

The earlier complete development diagnostic
`docs/04_experiments/results/fixture_local_committable_execution/20260716_015841/`
remains `failed_no_acceptance` provenance (27/28). It exposed an incorrect
missing-evidence commit and aggregate-accounting defects; it has no acceptance
use and was not rewritten after repair.
