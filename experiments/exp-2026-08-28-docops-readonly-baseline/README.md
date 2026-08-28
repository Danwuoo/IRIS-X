# Experiment: Read-Only Document Ops Narrow Baseline

- **Experiment ID:** `exp-2026-08-28-docops-readonly-baseline`
- **Status:** defined; safe local pilot eligible
- **Distribution:** `taskdist-2026-08-28-vanta-docops-readonly-12`
- **Task contract:** `research/task-contract-docops-readonly-12.md`
- **Operationalization:** `research/first-cycle-operationalization.md`
- **Corpus records:** `src.vanta`, with run-artifact patterns informed by `src.spex`

## Research Question

On the fixed 12-task read-only Document Ops development distribution, what outcome/evidence reference point and observed local execution-cost vector are produced by:

1. a literal-only narrow control; and
2. a structured narrow control that adds heading/selector and document-contract handlers?

This is a comparison of two deterministic fixture-local controls, not a claim about language models, learned agents, or a final IRIS-X architecture.

## Hypotheses

- **H-B0 (null):** Adding the structured handlers does not change actual task success on the fixed distribution.
- **H-B1:** The structured control succeeds on more enumerated tasks than the literal-only control because it can attempt the four output families rather than two.
- **Cost observation:** The experiment will report measured wall/CPU time, bytes, and read operations without predicting an unsupported overhead threshold or collapsing them into a scalar.

These hypotheses are development-fixture-specific. Because configuration design had access to the task family definitions, a positive result does not establish held-out generalization.

## Configurations

Exact machine-readable definitions are in `inputs/configurations.json`.

### `literal-readonly-v0`

- deterministic Python standard-library control;
- supports exact Markdown-link extraction and one declared terminology-alias check (`evidence package` against `Evidence Packet`);
- returns an explicit failure/refusal record for structure and document-contract output families;
- one invocation, no retries, no model, no network, no external tools.

### `structured-readonly-v0`

- same interpreter, manifest, task order, evidence envelope, evaluator, and intervention policy;
- adds Markdown heading/selector inspection and fixture-local document-contract validation;
- one invocation, no retries, no model, no network, no external tools.

The variable is the supported handler repertoire. The structured control is intentionally fixture-bounded; it is not a reusable agent runtime.

## Fixed Components

- 12-row enumerated manifest and task order;
- preserved `src.vanta` input and oracle paths;
- task/evaluation contract;
- evidence generation and independent evaluator;
- three sequential repetitions;
- Python standard library and local filesystem;
- zero retry, repair, escalation, and recovery;
- no mutation, model, network, credentials, or paid service.

## Operating Environment and Resource Envelope

The controlling definitions are in `research/task-contract-docops-readonly-12.md`. The pilot is valid only from an IRIS-X checkout containing the registered VANTA source snapshot. The runner rejects paths outside the repository and refuses to overwrite an existing run directory.

Resource envelope per episode: one local configuration invocation; read-only access to declared files; zero model calls, external tools, retries, repairs, escalations, and recoveries. Execution is sequential.

## Sampling and Repetition

- Enumeration: all 12 manifest rows in manifest order.
- Configurations: both, in `configurations.json` order.
- Repetitions: three identical-environment repetitions per configuration.
- Total intended episodes: 72.
- Random seed: recorded for protocol completeness; the controls are deterministic and do not sample.
- Exclusions: none after execution. Invalid episodes remain recorded and are excluded only from the success-rate denominator specified by the task contract.

## Outcome, Evidence, Reliability, and Cost Recording

For every episode the runner records:

- produced and expected JSON;
- actual outcome, system claim, evidence status, and joint label;
- pre/post SHA-256 for every declared input;
- handler/refusal and retry/repair/escalation/recovery counts;
- generation wall/process-CPU time, evaluation wall time, bytes read, output bytes, and read/tool count;
- terminal error or invalid reason.

Operational repeatability is the only reliability dimension evaluated: completion/error counts and cross-repetition output/outcome agreement. Robustness, stateful reliability, change reliability, and recovery reliability are `Not evaluated`.

The lifecycle-cost boundary includes unavailable design, maintenance, electricity, hardware, and failure-impact costs as `Unknown`. No deployment-volume amortization is applied. Model/token/API fields are `Not applicable` for these controls, not a general claim of zero lifecycle cost.

## Procedure

From repository root, after validating the definition:

```powershell
python -m py_compile experiments\exp-2026-08-28-docops-readonly-baseline\scripts\run_baseline.py
python experiments\exp-2026-08-28-docops-readonly-baseline\scripts\run_baseline.py `
  --manifest experiments\exp-2026-08-28-docops-readonly-baseline\inputs\task-manifest.json `
  --configurations experiments\exp-2026-08-28-docops-readonly-baseline\inputs\configurations.json `
  --output-dir experiments\exp-2026-08-28-docops-readonly-baseline\runs\pilot-20260828-local `
  --run-id pilot-20260828-local `
  --repetitions 3
```

The run directory is immutable by convention. Use a new run ID/path for another run.

## Output Separation

```text
runs/<run-id>/
  run-manifest.json          # frozen procedure, environment, source identities, boundary
  raw/episodes.jsonl         # one terminal record per episode
  results.json               # aggregates derived from raw records
  interpretation.md          # reviewed interpretation, written separately
```

The runner produces the first three artifacts. Interpretation is authored only after inspecting them.

## Stop and Invalid-Run Conditions

Stop before execution if the manifest/configuration schema is invalid, a path escapes the repository, a source or oracle is missing, task IDs disagree, or the output directory exists. Stop during execution on imported input mutation or inability to persist a terminal record.

An environment/harness exception, source mutation, incomplete episode count, or source-snapshot mismatch makes the affected episode/run invalid. A task failure produced normally by a control is a valid measured failure, not an invalid run.

## Interpretation Boundary

- A successful pilot proves that this harness and these controls ran on these bytes under the recorded environment.
- It does not establish a model comparison, architecture requirement, real-workload sufficiency, long-term reliability, robustness, or lifecycle-cost optimum.
- The exact evaluator is independent of the controls but depends on source-provided fixture oracles.
- Later experiments may add one intervention at a time: evidence-aware acceptance, retry/recovery, routing/escalation, prompt/program optimization, workflow optimization, or a model-based specialist.

## Blocked Model Baseline

A cheap-versus-strong model comparison is **defined conceptually but not configured or run** in Phase 3. Exact provider/model snapshots, price basis, approved paid-use ceiling, and owner authorization are unavailable for this task. The intended future procedure is to add two frozen configurations that implement the same output/evidence protocol, then run this manifest/evaluator unchanged. Such a run would produce per-task outputs, evidence, usage, failures, and a success–reliability–cost vector. No API call is made by this experiment.

