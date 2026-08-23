# Experiment 007 — Fixture-Local COMMITTABLE Execution

## Identity

- Experiment ID: `experiment_007_fixture_local_committable_execution`
- Gate: `PS1-G10 — Fixture-Local COMMITTABLE Execution Gate`
- Named scope: `Fixture-Local COMMITTABLE Document Promotion v0`
- Runner: `mix vanta.fixture_commit_experiment`
- Status: `Complete; measured run 20260716_020716 is accepted_by_closure for the named scope`

## Purpose

Measure the complete G10 authorization, prepared-effect, promotion,
transaction, recovery, rollback, audit, and strict replay path under
deterministic protocol-boundary failure injection.

## Fixture Matrix

Immutable case fixtures must cover valid approval; missing, denied, expired,
wrong-scope, wrong-target, and wrong-candidate approval; verifier reject and
request-evidence; missing evidence; path escape and source-target mutation;
same-key duplicate and conflicting request; crash before prepare, after prepare,
after effect, and after database commit; restart recovery; rollback success and
failure detection; corrupt or missing approval/evidence/journal refs;
irreversible misclassification; memory-write smuggling; and strict replay
mismatch detection.

## Required Artifacts

Each complete run writes under:

```text
docs/04_experiments/results/fixture_local_committable_execution/<timestamp>/
```

Required files are `run.json`, `fixture_results.json`,
`failure_injection_matrix.md`, `fixture_inventory.md`,
`environment_manifest.json`, `schema_policy_versions.json`, and `summary.md`.

## Hard Gates

The exact gates and required values are defined by
[PS1-G10](../00_manifest/Fixture_Local_Committable_Execution_Gate.md). Every
rate must be `1.0` and every violation/count floor `0`. A runner may report only
`pass_acceptance_candidate` or `failed_no_acceptance`; only the later manifest
closure may report `accepted_by_closure`.

## Failure Rule

Any failed case or hard gate makes the whole run `failed_no_acceptance`. Preserve
the run, repair only in-scope behavior, and execute the entire fixture matrix
again. Focused reruns cannot create closure.

## Claim Boundary

Even a passing closure is limited to the named copied-fixture promotion scope.
It does not validate H5 or H1-H5, broad side-effect safety, production
readiness, source/repository/user/external operations, irreversible effects,
memory writes, durable memory, full Context OS, distributed transactions, or
multi-process authority.

## Measured Run

The complete pre-measurement development diagnostic at
`docs/04_experiments/results/fixture_local_committable_execution/20260716_015841/`
is retained as `failed_no_acceptance`: 27/28 cases passed. It exposed missing-
evidence fail-open behavior plus replay/silent-partial aggregate bugs. Those
in-scope defects were fixed before the complete run was repeated.

The complete run at
`docs/04_experiments/results/fixture_local_committable_execution/20260716_020716/`
passed `28 / 28` fixtures and every hard gate. It is
`pass_acceptance_candidate`; see the
[measured run report](../05_evaluation/Experiment_007_Fixture_Local_Committable_Execution_Run_Report.md).
The runner remains `pass_acceptance_candidate`; the
[manifest closure](../00_manifest/Post_Stage_1_Fixture_Local_Committable_v0_Closure.md)
assigns `accepted_by_closure` after all required repository commands passed.
