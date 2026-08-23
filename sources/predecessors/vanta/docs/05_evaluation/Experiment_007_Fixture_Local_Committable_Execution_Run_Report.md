# Experiment 007 — Fixture-Local COMMITTABLE Execution Run Report

## Report Identity

- Gate: `PS1-G10 — Fixture-Local COMMITTABLE Execution Gate`
- Named scope: `Fixture-Local COMMITTABLE Document Promotion v0`
- Measured run: `20260716_020716`
- Result path: `docs/04_experiments/results/fixture_local_committable_execution/20260716_020716/`
- Completion status: `complete`
- Runner status: `pass_acceptance_candidate`
- Closure status: `accepted_by_closure` by manifest closure

## Outcome

The complete deterministic failure-injection run passed `28 / 28` fixtures and
all 15 hard gates. The runner cannot assign `accepted_by_closure`; after all
required repository commands passed, the
[manifest closure](../00_manifest/Post_Stage_1_Fixture_Local_Committable_v0_Closure.md)
accepted the named scope only.

The complete pre-measurement diagnostic at
`docs/04_experiments/results/fixture_local_committable_execution/20260716_015841/`
is retained as `failed_no_acceptance` provenance: 27/28 cases passed,
`G10-010` missing evidence incorrectly committed, and replay/partial aggregate
accounting failed. The repaired implementation was followed by the complete
passing run; the failed diagnostic is not closure evidence.

## Approval Boundary

A successful promotion required a standalone schema-valid Approval Record whose
`approved` scope exactly matched the action, target identity, candidate hash,
gate policy version, and active time window. A pre-effect verifier `accept` was
also required, but did not substitute for approval. Missing, denied, expired,
wrong-scope, wrong-target, and wrong-candidate approvals all failed closed.

The authorized effect was limited to copying a hash-verified candidate from
`candidates/` to `committed/` inside an explicitly marked ephemeral copied
fixture workspace. The source remained under `inputs/`; path escape and source
mutation attempts were rejected.

## Measured Hard Gates

| Metric | Observed | Required | Result |
| --- | ---: | ---: | --- |
| `valid_approved_commit_success` | `1 / 1 = 1.0` | `1.0` | pass |
| `unauthorized_commit_count` | `0` | `0` | pass |
| `approval_verifier_substitution_count` | `0` | `0` | pass |
| `duplicate_effects` | `0` | `0` | pass |
| `idempotency_conflicts_incorrectly_accepted` | `0` | `0` | pass |
| `path_escapes_or_source_mutations` | `0` | `0` | pass |
| `silent_partial_commits` | `0` | `0` | pass |
| `committed_effects_without_durable_refs` | `0` | `0` | pass |
| `restart_recovery_success` | `5 / 5 = 1.0` | `1.0` | pass |
| `rollback_success` | `5 / 5 = 1.0` | `1.0` for applicable cases | pass |
| `replay_consistency` | `4 / 4 = 1.0` | `1.0` | pass |
| `audit_completeness` | `4 / 4 = 1.0` | `1.0` | pass |
| `unsupported_commits` | `0` | `0` | pass |
| `irreversible_effects` | `0` | `0` | pass |
| `memory_writes` | `0` | `0` | pass |

The source-fixture tree hash was unchanged before and after the run:
`sha256:5eb133c5f5b3e1b3dbc35253269831deca9dced1638e9fb1742b7c71f16e8544`.

## Durable Protocol Findings

- The durable `prepared` recovery record preceded every authorized effect.
- Same-key, same-request retries returned the persisted result without a second
  file effect; same-key, different-request conflicts were rejected.
- Crash-before-prepare, prepare-before-effect, effect-before-database-commit,
  and database-commit-before-response windows all recovered without silently
  treating uncertainty as committed.
- Successful logical commits retained state, step, Approval Record, pre/post
  Evidence Packet, pre/post Verifier Output, Episode Journal, and committed
  artifact references.
- Strict restore rollback succeeded for every applicable recoverable case.
  Injected restore failure was detected as `recovery_required`, not reported as
  rollback success or commit success.
- Corrupt or missing approval, evidence, journal, and replay references failed
  audit or strict replay checks.

## Fixture Coverage

The 28 cases cover valid approval; missing, denied, expired, wrong-scope,
wrong-target, and wrong-candidate approvals; verifier reject and
request-evidence; missing evidence; path escape; source mutation; duplicate and
conflicting idempotency requests; four crash windows; restart recovery;
rollback success and failure; corrupt or missing approval/evidence/journal
references; irreversible misclassification; memory-write smuggling; and strict
replay mismatch.

## Required Repository Verification

The following commands passed on the completed batch before closure:

```text
mix format --check-formatted
mix test.fast
mix test.docs
mix test.tooling
mix test.integration
mix test.full
git diff --check
```

The closure document records exact counts and the closure-aware rerun; this
measured report did not itself assign acceptance.

## Result Artifacts

- `run.json`: run identity, claim boundary, source integrity, and hard metrics
- `fixture_results.json`: case-level oracle and observed results
- `fixture_inventory.md`: immutable fixture inventory
- `failure_injection_matrix.md`: injection-to-outcome mapping
- `environment_manifest.json`: measured environment
- `schema_policy_versions.json`: schema and policy versions
- `summary.md`: human-readable runner summary

## Claim Boundary

This evidence does not validate H5 or H1-H5, broad side-effect safety,
production readiness, repository source or real user documents, external
systems, `IRREVERSIBLE`, `MEMORY_WRITE`, durable memory, full Context OS,
distributed transactions, or multi-process authority. The only possible
closure claim is `validated for Fixture-Local COMMITTABLE Document Promotion
v0`.
