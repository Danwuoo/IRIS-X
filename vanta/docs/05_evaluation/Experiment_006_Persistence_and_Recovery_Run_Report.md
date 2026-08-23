# Experiment 006 Persistence and Recovery Run Report

## Report Identity

- Report date: 2026-07-15
- Experiment: `experiment_006_persistence_and_recovery`
- Gate: `PS1-G9 — Storage and Persistence Gate`
- Named scope: `Fixture-Local SQLite Persistence v0`
- Accepted candidate run: `20260715_114209`
- Runner threshold status: `pass_acceptance_candidate`
- Manifest interpretation: accepted by
  [Post-Stage-1 Persistence v0 Closure](../00_manifest/Post_Stage_1_Persistence_v0_Closure.md)
- Failed predecessor retained: `20260715_114052`, `failed_no_acceptance`

## Artifact Paths

- [run.json](../04_experiments/results/persistence_and_recovery/20260715_114209/run.json)
- [summary.md](../04_experiments/results/persistence_and_recovery/20260715_114209/summary.md)
- [fixture_inventory.md](../04_experiments/results/persistence_and_recovery/20260715_114209/fixture_inventory.md)
- [failure_injection_results.json](../04_experiments/results/persistence_and_recovery/20260715_114209/failure_injection_results.json)
- [failure_injection_matrix.md](../04_experiments/results/persistence_and_recovery/20260715_114209/failure_injection_matrix.md)
- [environment_manifest.json](../04_experiments/results/persistence_and_recovery/20260715_114209/environment_manifest.json)
- [schema_hash_policy_versions.json](../04_experiments/results/persistence_and_recovery/20260715_114209/schema_hash_policy_versions.json)

The failed predecessor remains at
`docs/04_experiments/results/persistence_and_recovery/20260715_114052/` and was
not deleted or rewritten.

## Environment And Versions

| Item | Observed |
| --- | --- |
| Elixir | `1.19.5` |
| OTP | `28` |
| OS | Windows (`win32`, `nt`) |
| architecture | `x86_64-pc-windows-msvc` |
| Vanta runtime | `0.1.0` |
| SQLite driver | `exqlite 0.38.0` |
| runtime schema | `stage1-mvp-v0` |
| storage schema | `persistence-v0` |
| hash policy | `canonical-json-sha256-v1` |
| schema authority | `docs/03_schemas/*.schema.json` |

## Fixture And Failure-Injection Result

- Cases: `20`
- Passed: `20`
- Failed: `0`
- Case pass rate: `1.0`
- Failure model: deterministic protocol-boundary injection
- OS-level process kill: not executed and not claimed

| Case | Window or condition | Observed result |
| --- | --- | --- |
| `P006-01` | normal commit then restart | passed |
| `P006-02` | before Evidence Packet persistence | passed; no commit, restart recovery completed |
| `P006-03` | prepared before file effect | passed; unchanged target, safe abort |
| `P006-04` | file effect before DB commit | passed; backup restore and `rolled_back` |
| `P006-05` | DB commit before client response | passed; idempotent durable result, no duplicate effect |
| `P006-06` | before rollback starts | passed; restart completed rollback |
| `P006-07` | during rollback | passed; restart verified completed rollback |
| `P006-08` | same key and same request | passed; existing result returned |
| `P006-09` | same key, different request | passed; conflict rejected without overwrite |
| `P006-10` | artifact content corruption | passed; content-hash mismatch detected |
| `P006-11` | artifact reference missing | passed; audit incompleteness detected |
| `P006-12` | incompatible storage version | passed; reopen rejected before writes |
| `P006-13` | database busy/locked | passed; explicit busy/locked error, no partial episode |
| `P006-14` | injected transaction rollback | passed; both accepted pointers remained absent |
| `P006-15` | incomplete episode discovery | passed; episode listed recoverable |
| `P006-16` | clean workspace replay | passed; strict fidelity mismatch list empty |
| `P006-17` | structured reversible restart/replay | passed; path, selector, hashes, diff, refs, status, and final state matched |
| `P006-18` | rejected action | passed; no accepted state or journal pointer |
| `P006-19` | verifier non-`accept` | passed; commit rejected |
| `P006-20` | unsupported, memory, irreversible floor | passed; all executed/committed counts remained zero |

Detailed per-check results and duration values are in
`failure_injection_results.json` and `failure_injection_matrix.md`.

## Hard Metrics

| Metric | Required | Observed | Raw evidence |
| --- | ---: | ---: | --- |
| `persistence_artifact_schema_validity` | `1.0` | `1.0` | `64 / 64` artifacts |
| `persistence_write_success_rate` | `1.0` | `1.0` | `5 / 5` expected-success writes |
| `restart_recovery_success` | `1.0` | `1.0` | `5 / 5` recovery cases |
| `replay_consistency` | `1.0` | `1.0` | `2 / 2` strict replay cases |
| `audit_completeness` | `1.0` | `1.0` | `3 / 3` committed audit cases |
| `state_journal_atomicity_violations` | `0` | `0` | transaction rollback and pointer checks |
| `duplicate_logical_commits` | `0` | `0` | resend and response-loss cases |
| `silent_partial_commits` | `0` | `0` | injected rollback and busy/error cases |
| `committed_effects_without_journal_refs` | `0` | `0` | committed audit checks |
| `artifact_integrity_detection_rate` | `1.0` | `1.0` | `2 / 2` corruption/reference injections |
| `unsupported_commits` | `0` | `0` | process floor |
| `memory_writes` | `0` | `0` | process floor |
| `irreversible_effects` | `0` | `0` | process floor |

All hard metrics passed. The accepted run contains no missing hard metric and no
threshold reduction.

## Replay Evidence

The two replay cases use strict Persistence v0 comparison. Success required and
observed equality for episode/task identity, runtime/schema version, ordered
step identity/action/side-effect/status, commit and rollback/recovery status,
the full state-hash sequence, Evidence Packet and Verifier Output refs,
observation signatures, structured path and selector resolution, before/after
hashes, diff or contract result, and final accepted state hash. Both mismatch
lists were empty.

## Audit Completeness Evidence

Committed audit cases required resolvable accepted Canonical State and Episode
Journal pointers, state-hash agreement, and resolvable Evidence Packet and
Verifier Output references. Three of three committed audit cases passed. The
deliberate missing-reference case was detected and was not counted as an
accepted complete audit.

## Test Commands

| Command | Result |
| --- | --- |
| `mix format --check-formatted` | passed |
| `mix test.fast` | `65 tests, 0 failures` |
| `mix test.docs` | `15 tests, 0 failures` in the final closure-aware rerun |
| `mix test.tooling` | `21 tests, 0 failures` |
| `mix test.integration` | `29 tests, 0 failures` |
| `mix test.full` | `130 tests, 0 failures` in the final closure-aware rerun |

## Failed Predecessor

The first complete attempt `20260715_114052` reported `19 / 20` cases and
`failed_no_acceptance`. `P006-12` exposed that the SQLite adapter did not close
its connection after rejecting incompatible storage metadata, which caused the
Windows scratch-directory cleanup to fail. The adapter was changed to close on
open-time verification errors, and the next full 20-case run passed. The failed
directory remains immutable provenance and does not support acceptance.

## Limitations

- Failure injection is deterministic at durable protocol boundaries; it is not
  an OS process-kill or power-loss campaign.
- Scope is one process at a time over a single fixture-local SQLite database;
  busy/lock rejection is tested, but distributed concurrency is not.
- Filesystem and SQLite are coordinated by recovery protocol, not a true
  cross-resource transaction.
- No production data, external accounts, network effects, retention operator,
  backup service, replication, HA, or distributed migration was tested.
- MemoryAdapter is a parity/test adapter, not durable authority.

## Claim Boundary

This report supports only:

- completed named `Fixture-Local SQLite Persistence v0` implementation;
- a passing measured deterministic failure-injection run; and
- manifest closure review within that named fixture-local scope.

It does not support H1-H5 validation, full architecture validation, production
readiness, distributed persistence, durable memory, full Context OS, external
`COMMITTABLE`, `IRREVERSIBLE`, `MEMORY_WRITE`, or broad agent-safety claims.
