# Experiment 003 Local Run Report

## Experiment

- Experiment ID: `experiment_003_commit_journal`
- Date: 2026-05-04
- Runtime version: local `vanta` workspace, Mix project version `0.1.0`
- Evaluator: fixture oracle plus audit checklist
- Dataset or benchmark: seven Document Ops fixtures
- Status: `Completed local smoke run`
- Result path:
  `docs/04_experiments/results/experiment_003/20260504_215304/`

## Setup

- Baseline: `tool_trace_only_direct_execution`
- Treatment: `stage1_episode_journal_replay_runtime`
- Action source: fixture `expected/acceptance.json` action sequences
- Side-effect classes: `READ_ONLY`, `SIMULATED`, and `REVERSIBLE`
- Scope: journal audit and replay pipeline stability, not model capability

The baseline executes the same fixture action sequences without Episode Journal,
Evidence Packet, Verifier Output, or ReplayRunner artifacts. Its
`audit_completeness` and `replay_consistency` are therefore `0.0` by definition
for this experiment.

## Metrics

| Metric | Baseline | Treatment | Notes |
| --- | --- | --- | --- |
| `commit_integrity_score` | `0.0` | `1.0` | Treatment committed episodes passed verifier/evidence/side-effect checks. |
| `replay_consistency` | `0.0` | `1.0` | All treatment journals replayed to matching status, state hash, and step count. |
| `audit_completeness` | `0.0` | `1.0` | All treatment journals passed the Experiment 003 audit checklist. |
| `invalid_action_rate` | `0.42857142857142855` | `0.42857142857142855` | Three negative fixtures intentionally produce invalid action paths. |

## Run Command

Command run on 2026-05-04:

```powershell
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$out = "docs/04_experiments/results/experiment_003/$timestamp"
mix vanta.experiment003 --out $out
```

Observed result path:

```text
docs/04_experiments/results/experiment_003/20260504_215304/
```

`run.json` and `summary.md` were produced. `run.json` validates against
`experiment_run.schema.json`.

## Findings

- The run status is `completed`.
- All seven treatment journals passed the audit checklist.
- All seven replay attempts were consistent by commit status, final accepted
  state hash, and step count.
- Compile rejects now produce auditable rejected steps, Evidence Packets, and
  Verifier Outputs without adding rejected candidate state to accepted state
  hashes.
- This is a seven-fixture local smoke result. It must not be reported as
  validation of H5 or as a broader safety benchmark.

## Next Steps

- Keep Experiment 003 results local-smoke scoped until larger Document Ops
  samples exist.
- Add human or secondary audit labels before treating audit completeness as a
  broader reviewability measure.
- Revisit commit integrity thresholds when multi-step and compensable action
  fixtures are added.
