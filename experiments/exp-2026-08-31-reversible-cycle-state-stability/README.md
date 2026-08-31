# H-SR1a — Reversible-Cycle Stateful Stability

- **Experiment ID:** `exp-2026-08-31-reversible-cycle-state-stability`
- **Status:** definition frozen before measured execution
- **Reliability dimension:** stateful reliability
- **Task frame:** six `frame_v1_reversible_state` fixtures

## Hypothesis

> Holding the reversible action definition, copied-workspace baseline, state oracle, evaluator, and rollback policy fixed, persistent repeated apply→verify→rollback cycles will return the workspace to the frozen baseline after every completed cycle without cumulative state drift over the declared horizon; a fresh-workspace control distinguishes persistent-state accumulation from one-cycle correctness.

## Arms and causal variable

`fresh-workspace-cycle-v0` copies the fixture inputs, applies and verifies the change, rolls back, independently verifies exact baseline restoration, and discards the copy for every cycle. `persistent-workspace-cycle-v0` creates one copy per fixture and repeats the same sequence ten times on that copy.

Workspace persistence is the intended causal difference. Both arms use the same action bytes, candidate builder, backup/metadata format, rollback implementation, independent state oracle, fixture order, source snapshot, and zero-retry/no-recovery/no-model policy.

## Frozen horizon

```text
6 qualified reversible fixtures × 10 cycles × 2 arms = 120 cycle records
```

The independent oracle reads paths, SHA-256 values, byte counts, directory membership, backup metadata, and residual state. It does not receive or trust the rollback function's return value. An intentional residual-artifact self-test must be detected before measured execution.

Normal successful cycles retain baseline/post-apply/post-rollback manifests, hashes, changed/residual paths, metadata checks, and terminal records—not full workspace trees. Full copies are retained only for drift, invalidity, or rollback failure.

## Command

After the definition commit is frozen:

```powershell
python experiments\exp-2026-08-31-reversible-cycle-state-stability\scripts\run_experiment.py --run-id <id> --definition-commit <earlier-definition-commit>
```

All mutation is confined to new run-local copied workspaces. Imported fixtures remain read-only.
