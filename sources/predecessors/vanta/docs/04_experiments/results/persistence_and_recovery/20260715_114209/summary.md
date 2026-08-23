# Experiment 006 Persistence And Recovery Summary

- Experiment: `experiment_006_persistence_and_recovery`
- Status: `pass_acceptance_candidate`
- Cases: `20 / 20`
- Storage schema: `persistence-v0`
- Runtime schema: `stage1-mvp-v0`
- Hash policy: `canonical-json-sha256-v1`
- Failure injection: deterministic protocol-boundary simulation; no OS-level kill claim

## Hard Metrics

| Metric | Required | Observed |
| --- | ---: | ---: |
| `artifact_integrity_detection_rate` | `1.0` | `1.0` |
| `audit_completeness` | `1.0` | `1.0` |
| `committed_effects_without_journal_refs` | `0` | `0` |
| `duplicate_logical_commits` | `0` | `0` |
| `irreversible_effects` | `0` | `0` |
| `memory_writes` | `0` | `0` |
| `persistence_artifact_schema_validity` | `1.0` | `1.0` |
| `persistence_write_success_rate` | `1.0` | `1.0` |
| `replay_consistency` | `1.0` | `1.0` |
| `restart_recovery_success` | `1.0` | `1.0` |
| `silent_partial_commits` | `0` | `0` |
| `state_journal_atomicity_violations` | `0` | `0` |
| `unsupported_commits` | `0` | `0` |

## Claim Boundary

This result is a closure candidate only for `Fixture-Local SQLite Persistence v0`.
It does not validate H1-H5, the full architecture, production readiness,
distributed persistence, durable memory, full Context OS, external
`COMMITTABLE`, `IRREVERSIBLE`, `MEMORY_WRITE`, or broad agent safety.
