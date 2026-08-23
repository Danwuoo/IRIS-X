# Testing Strategy

## Purpose

Define how the current Post-Stage-1 implementation, documentation contracts,
and generated artifacts are tested without converting local smoke or planning
evidence into validation claims.

## Test Layers

- Schema validation tests for all runtime artifacts.
- Unit tests for state transitions, Execution IR compilation, evidence construction, and journal writes.
- Integration tests for `state -> plan -> action -> evidence -> verify -> commit / abort`.
- Replay tests using controlled fixtures.
- Regression tests for invalid actions, false accepts, audit gaps, and rollback failures.
- Documentation consistency tests for routing, closure status, fixture mirrors,
  and ChatGPT Project Knowledge export parity where applicable.
- Generated artifact and tooling tests for packet builders, label-result
  validators, scaffold generators, and Mix task wrappers.
- Persistence adapter contract, Memory/SQLite parity, transaction rollback,
  idempotency/conflict, recovery lifecycle, corruption/version, clean restart,
  strict replay, and result-artifact tests.
- Schema source tests that validate runtime artifacts against
  `docs/03_schemas/*.schema.json`; this batch does not test packaged runtime
  schema assets because no such asset path is accepted.

## Test Tags and Commands

`mix test` remains the complete local test command. `test/test_helper.exs` must
not globally exclude any tag; all tagged tests still run in the full suite by
default.

| Tag | Intended scope |
| --- | --- |
| `:fast_unit` | Deterministic unit, schema, parser, adapter, guard, and small contract tests suitable for quick local feedback. |
| `:integration` | Fixture loops, replay paths, experiment runners, Lane A artifact generation, and other tests that exercise the closed-loop runtime or measured-run machinery. |
| `:docs_consistency` | Fixture mirror checks, documentation routing, closure status, traceability, manifest/map parity, and mirrored export consistency. |
| `:generated_artifact_tooling` | Packet generation, label-result validation/import tooling, planning scaffolds, and Mix task rerun checks. |

| Command | Coverage |
| --- | --- |
| `mix test.fast` | `:fast_unit` only. |
| `mix test.docs` | `:docs_consistency` only. |
| `mix test.tooling` | `:generated_artifact_tooling` only. |
| `mix test.integration` | `:integration` only. |
| `mix test.smoke` | `:fast_unit` plus `:docs_consistency`; this is the quick smoke gate. |
| `mix test.full` | Alias for full `mix test`. |

## CI Layering

GitHub Actions runs two ordered jobs:

- `smoke`: installs dependencies and runs `mix test.smoke`.
- `full`: runs after `smoke` and executes `mix test.full`.

The smoke job is an early feedback gate only. The full job remains the final
CI test gate because it includes integration and generated-artifact/tooling
coverage.

## Required Fixtures

- Successful minimal task.
- Invalid action task.
- Missing evidence task.
- Commit then replay task.
- Rollback or abort task.
- Ambiguous failure-label task.

## Acceptance Criteria

- Runtime artifacts validate against schemas.
- Runtime schema validation continues to load contracts from
  `docs/03_schemas/*.schema.json`; any packaged schema asset path requires a
  later migration test batch.
- Episode journal contains required audit fields.
- Verifier cannot commit missing-evidence actions in controlled tests.
- Replay succeeds in deterministic fixtures.
- Document Ops fixture mirrors under `docs/` and `test/` remain byte-for-byte
  synchronized.
- Stage 1 commit controller rejects non-`accept` verifier decisions and
  disallowed side-effect classes.
- Runtime integration tests cover positive commit paths, negative rejection
  paths, rollback metadata, baseline invalid-action recording, mock LLM
  structured output, mock OpenClaw agent payload parsing, replay consistency,
  and compact experiment run output.
- Experiment 002 tests cover mock OpenClaw verifier output parsing, JSON fence
  parsing, parse-failure-to-abstain normalization, fixture oracle review item
  generation, strict false-reject policy, and compact three-arm metrics.
- Experiment 004 tests cover OpenClaw recovery output parsing, JSON fence
  parsing, malformed-output normalization to `no_recovery`, rollback-failure
  recovery, audit-gap repair, compensation record creation, and matched-budget
  blind retry metrics.
- Experiment 005 tests cover schema-valid `WorkingSet` generation, budget
  overflow notes, provenance completeness, rejection of raw tool log / full
  memory dump / memory write refs, bounded raw trace truncation, OpenClaw
  context planner JSON parsing, mock experiment metrics, and fixture mirror
  synchronization.
- PS1-G6 tests cover structured selectors (`heading`, `section`, `line_range`,
  `json_path`), contract pass/fail observations, simulated source hash
  preservation, reversible backup metadata and rollback, selector rejection,
  path escape rejection, wrong diff rejection, replay consistency, and fixture
  mirror synchronization.
- Post-Stage-1 Lane A tests and docs checks cover required artifact generation,
  threshold-status reporting, replay consistency, audit completeness,
  process-integrity hard gates, and the boundary that `accepted_by_closure` for
  `20260601_113121` is not H1-H5 validation or production readiness.
- Lane B packet and label-result tooling tests cover packet generation,
  validator/import-summary behavior, reported label metrics, source-run routing,
  and mirror parity without creating runtime approval or schema changes.
- PS1-G7 planning checks must keep Context OS work planning-only: no full
  Context OS implementation, learned retrieval, compression, memory governance,
  memory writes, or H3 validation.
- PS1-G8 planning checks must keep side-effect work planning-only: no executable
  `COMMITTABLE`, `IRREVERSIBLE`, or `MEMORY_WRITE` behavior, no approval
  collection, no production readiness, and no H5 validation.
- PS1-G8 pilot tests must cover two valid rollback/compensation declarations;
  missing target, approval, idempotency/duplicate guard, and rollback or
  compensation fields; path escape; source-fixture targeting; irreversible
  misclassification; memory-write smuggling; exact fixture-oracle comparison;
  output-path isolation; source-tree pre/post hash equality; failed-run
  retention; complete artifact generation; and every planning/process floor.
- The complete `20260715_223158` planning run must retain 10/10 oracle
  conformance, 8/8 rejection-rule accuracy, all other planning metrics at
  `1.0`, and every process-integrity count at `0`.
- PS1-G9 tests must cover MemoryAdapter/SQLiteAdapter parity, atomic accepted
  state and journal pointers, same-key idempotency, conflicting-key rejection,
  deterministic Canonical State JSON hashing, prepared-effect recovery, all
  documented crash windows, artifact corruption and missing refs, incompatible
  versions, database busy/locked, transaction rollback, incomplete discovery,
  strict clean replay, rejected/non-accept isolation, zero unsupported commits,
  zero memory writes, and zero irreversible effects.
- Experiment 006 result validation must preserve failed predecessor provenance,
  validate all required files, require 20/20 cases, and keep runner output at
  `pass_acceptance_candidate` until manifest closure.
- PS1-G10 fast tests must validate all changed JSON schemas, standalone Approval
  Record scope, the explicit action payload, and isolation from the general
  planner/action allowlist.
- PS1-G10 integration/tooling tests must execute all 28 fixtures, including
  approval failures, verifier/evidence failures, safe-path/source guards,
  duplicate/conflict handling, four crash windows, restart, rollback success
  and failure, corrupt/missing refs, irreversible and memory smuggling, audit,
  and strict replay mismatch.
- Experiment 007 result validation must require 28/28 cases, all 15 hard gates,
  unchanged source-fixture tree hash, the complete result artifact set, and
  `pass_acceptance_candidate` until the separate manifest closure.

## Open Questions

- How should non-deterministic tool outputs be simulated?
- Resolved pointer: minimum replay fidelity is locked by `PS1-G9` and
  [Persistence and Recovery Semantics](../02_specs/Persistence_and_Recovery_Semantics.md).
