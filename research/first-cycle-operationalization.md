# First-Cycle Research-Variable Operationalization

- **ID:** `note-2026-08-28-first-cycle-operationalization`
- **Status:** exploratory — active for the first baseline cycle
- **Question/scope:** Map the project-level success–reliability–cost variables to observables for `taskdist-2026-08-28-vanta-docops-readonly-12`. These definitions are task-local and non-universal.
- **Contract:** `contract-2026-08-28-docops-readonly-12`
- **Corpus records:** `src.vanta`, `src.spex`, `src.nemo-agent-toolkit-develop`

## Evidence Basis

- `src.vanta`, `sources/predecessors/vanta/docs/04_experiments/fixtures/README.md` and the selected fixture files: source-stated strata, success criteria, allowed actions, and deterministic expected observations.
- `src.spex`, `sources/predecessors/spex/docs/eval/ARC-AGI-1-Run-Artifact-Substrate-v0.md` and `sources/predecessors/spex/src/spex_arc/runner/arc_a1.py`: source-stated and directly observed examples of frozen run manifests, terminal per-task records, failure artifacts, budgets, and cost ledgers. Their ARC-specific semantics are not inherited.
- `src.nemo-agent-toolkit-develop`, `sources/external/NeMo-Agent-Toolkit-develop/docs/source/improve-workflows/evaluate.md` and `docs/source/improve-workflows/profiler.md`: source-stated evaluation outputs and profiling fields such as latency, token counts, model names, and errors. The toolkit is not required by the first baseline.

## Task Success

For configuration `c` over the fixed 12-task set and `r` repetitions:

```text
task_success_rate(c) = successful episodes / attempted valid episodes
```

The report also preserves counts and rates for `partial` and `failure`; they are not assigned invented numeric utilities. Results are reported per configuration, per task, and per repetition. No exclusions are allowed after execution except episodes marked invalid by the contract, and every invalid episode remains in the raw log with its reason.

The full enumerated sample and three fixed-environment repetitions are used. Because this is not a probability sample from a known population, binomial confidence intervals would imply a population interpretation that is **Not established**. The pilot reports exact counts and cross-repetition agreement instead.

No task-success requirement or deployment threshold is asserted. The first result is a reference point, not a pass/fail architecture gate.

## Evidence and Epistemic Status

The harness recomputes input SHA-256 values and compares parsed output to the fixture oracle. It audits evidence completeness and derives the joint labels in the task contract. The following are reported separately:

- actual `success` / `partial` / `failure`;
- evidence `sufficient` / `insufficient`;
- system claim `success` / `partial` / `failure`;
- `verified_success`, `unverified_success`, `false_success`, `false_failure`, `correctly_recognized_failure`, and unresolved joint states.

The deterministic evaluator is evidence under a declared fixture oracle, not automatic empirical truth. Oracle validity outside these fixture bytes is **Not established**.

## Applicable Reliability Dimensions

| Dimension | First-cycle observable | Interpretation boundary |
| --- | --- | --- |
| Operational reliability | completed/attempted episodes, harness error count, invalid-run count, and whether each configuration produces the same outcome/output across three same-environment repetitions | Tests deterministic repeatability and execution completion only; three repetitions do not establish long-term operation |
| Robustness | `Not evaluated` | The fixed set contains some distractors and missing/negative conditions, but no controlled perturbation or distribution-shift protocol exists |
| Stateful reliability | `Not evaluated` | Episodes are deliberately independent and carry no state |
| Change reliability / maintainability | `Not evaluated` | No fixture, prompt, tool, dependency, or policy change is applied across the horizon |
| Recovery reliability | `Not evaluated` | Retry, repair, escalation, and recovery are fixed at zero in the baseline |

These dimensions are not aggregated into a reliability scalar.

## Lifecycle Cost

### Measured fields

Per episode and configuration aggregate:

- generation wall milliseconds;
- generation process CPU milliseconds;
- evaluator wall milliseconds;
- bytes read from declared task inputs;
- serialized output bytes;
- tool/read count;
- retry, repair, escalation, and recovery counts;
- harness/environment failure count;
- model calls, input tokens, output tokens, and model/API cost, represented as `0` / `Not applicable` for the baseline controls.

### Included but unavailable fields

The accounting boundary includes these concepts but records them as `Unknown`: development/specialization labor, fixture-authoring labor, maintenance/remediation labor, electricity, hardware depreciation, and external failure impact. Their absence prevents a complete lifecycle-cost total.

### Resource envelope versus accounting boundary

The envelope prohibits network/model calls, limits each episode to one local invocation, and fixes retries/interventions at zero. The accounting boundary asks what the comparison costs over its lifecycle, including unavailable design and maintenance components. A prohibited resource is not silently treated as evidence that its lifecycle cost is universally zero.

### Amortization and comparison

The workload is the 72-episode pilot. No deployment volume is assumed and no design-time cost is amortized. The first cycle reports a vector of observed costs rather than currency total or universal scalar. A later configuration that uses a model must add provider/model snapshot, request parameters, token/call usage, price basis and date, verifier calls, and paid cost before comparison.

## Failure Recording

Every terminal episode records configuration, task, repetition, actual outcome, system claim, evidence status, joint status, output, expected oracle, evidence, input hash comparison, execution path, measured resources, and failure/invalid reason. Aggregates are derived only from those raw records.

## Current Unknowns

- **Unknown:** electricity, hardware depreciation, human development effort, maintenance effort, and real deployment volume.
- **Unclear:** which operational horizon is sufficient to expose meaningful failure accumulation for future model agents.
- **Not established:** task-success or reliability thresholds and whether either baseline control is sufficient for any real use.
- **Not evaluated:** stochastic variance, distribution shift, state persistence, recovery, maintenance, paid-model cost, or human adjudication.
- **Not established:** a valid scalar combining success, any reliability dimension, and lifecycle cost.

