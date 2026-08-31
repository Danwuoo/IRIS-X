# H-OR1a — Process-Lifetime Operational Stability

- **Experiment ID:** `exp-2026-08-31-process-lifetime-stability`
- **Status:** definition frozen before measured execution
- **Reliability dimension:** operational reliability
- **Task frame:** the 12 `frame_v1_readonly` fixtures in `document-ops-task-frame-v1`

## Hypothesis

> Holding task bytes, configuration behavior, evaluator, evidence policy, source snapshot, and execution order fixed, a long-lived execution process will preserve task outcome, expected deterministic output/evidence state, and terminal validity across the declared sequence horizon as reliably as fresh-process execution; any sequence-position drift or persistent-process contamination is observable as a paired reliability difference.

## Arms and causal isolation

`fresh-process-v0` launches the same worker implementation in a fresh Python process for every episode. `long-lived-process-v0` keeps one instance of that worker alive for the entire frozen sequence. Both arms receive byte-identical request JSON in the same 12-task order for 20 passes. The same handler, evaluator, evidence policy, source snapshot, task inputs, zero-retry policy, and no-recovery/no-model envelope apply to both arms. Process lifetime is the intended causal difference.

The orchestrator executes each fresh episode and then its paired long-lived episode. This fixed pair order is part of the frozen definition. Worker PID and process-local sequence counter are diagnostic metadata and are excluded from the deterministic response-core hash.

## Frozen horizon

```text
12 tasks × 20 sequence passes × 2 arms = 480 episodes
```

This is materially longer than the prior three-repetition experiments. It remains a finite local sequence, not evidence of production, concurrent, shifted, or days/weeks reliability.

## Artifacts

- `inputs/experiment-definition.json` freezes identity, horizon, order, policy, and validity rules.
- `scripts/worker.py` is the shared deterministic worker/evaluator.
- `scripts/run_experiment.py` is the paired orchestrator and aggregate derivation.
- `runs/<run-id>/raw/terminal-records.jsonl` is raw evidence.
- `runs/<run-id>/results.json` is derived only from raw records.
- `runs/<run-id>/interpretation.md` is the bounded reviewed interpretation.

Run directories are immutable. A failed/invalid attempt must receive a new run ID.

## Command

After the definition commit is frozen:

```powershell
python experiments\exp-2026-08-31-process-lifetime-stability\scripts\run_experiment.py --run-id <id> --definition-commit <earlier-definition-commit>
```

No network, credential, model, external tool, retry, repair, escalation, or recovery use is authorized.
