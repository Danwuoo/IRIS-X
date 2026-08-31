# H-RCV1a — Targeted Recovery to Valid State

- **Experiment ID:** `exp-2026-08-31-targeted-recovery-valid-state`
- **Status:** definition frozen before measured execution
- **Reliability dimension:** recovery reliability
- **Task frame:** five `frame_v1_recovery` fixtures

## Hypothesis

> Holding the frozen injected failure state, task contract, final-state oracle, and execution envelope fixed, a targeted recovery procedure will restore the workspace and/or evidence state required by the task contract more often than no-recovery handling, without introducing new invalid side effects in the declared finite sample.

## Arms and isolation

Both `detect-only-v0` and `targeted-recovery-v0` start from byte-identical regenerated failure-state manifests. The control validates/detects the failure and makes no recovery mutation. The treatment executes one predeclared targeted procedure, freezes its output, and then undergoes independent exact-state adjudication.

Recovery code receives only its recovery policy/specification. It cannot receive the independent oracle's expected final files/hashes or a precomputed success label. Failure detection, recovery attempted, recovery action completion, final-state validity, final actual outcome, final evidence status, and new side-effect violations remain separate fields.

## Frozen horizon

```text
5 qualified recovery fixtures × 2 arms × 3 repetitions = 30 episodes
```

The failure states cover two missing-backup rollback reconstructions, two audit-reference gaps, and one fixture-local compensable receipt. This does not test autonomous arbitrary diagnosis. An intentionally corrupted recovery-output self-test must be rejected by the independent oracle before measured execution.

## Evidence retention

Normal records retain initial/final state manifests, path/hash/byte comparisons, detection/recovery fields, and terminal resources. Expected detect-only failures are compact control evidence. Full workspaces are retained only for invalid initial states, unexpected side effects, or failed targeted recovery.

## Command

After the definition commit is frozen:

```powershell
python experiments\exp-2026-08-31-targeted-recovery-valid-state\scripts\run_experiment.py --run-id <id> --definition-commit <earlier-definition-commit>
```

No model, network, credential, paid service, retry, or unplanned recovery is authorized.
