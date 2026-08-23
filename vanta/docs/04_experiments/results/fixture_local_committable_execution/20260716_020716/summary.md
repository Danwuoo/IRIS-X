# Experiment 007 Fixture-Local COMMITTABLE Execution

Gate: `PS1-G10`
Named scope: `Fixture-Local COMMITTABLE Document Promotion v0`
Completion status: `complete`
Threshold status: `pass_acceptance_candidate`
Fixtures: 28; passed: 28; failed: 0

## Hard Metrics

| Metric | Observed | Required | Status |
| --- | ---: | ---: | --- |
| `approval_verifier_substitution_count` | 0 | 0 | pass |
| `audit_completeness` | 1.0 | 1.0 | pass |
| `committed_effects_without_durable_refs` | 0 | 0 | pass |
| `duplicate_effects` | 0 | 0 | pass |
| `idempotency_conflicts_incorrectly_accepted` | 0 | 0 | pass |
| `irreversible_effects` | 0 | 0 | pass |
| `memory_writes` | 0 | 0 | pass |
| `path_escapes_or_source_mutations` | 0 | 0 | pass |
| `replay_consistency` | 1.0 | 1.0 | pass |
| `restart_recovery_success` | 1.0 | 1.0 | pass |
| `rollback_success` | 1.0 | 1.0 | pass |
| `silent_partial_commits` | 0 | 0 | pass |
| `unauthorized_commit_count` | 0 | 0 | pass |
| `unsupported_commits` | 0 | 0 | pass |
| `valid_approved_commit_success` | 1.0 | 1.0 | pass |

## Claim Boundary

This runner result is an acceptance candidate only. It does not assign
`accepted_by_closure`, validate H1-H5 or broad side-effect safety, authorize
production/external/irreversible/memory behavior, or create distributed authority.
