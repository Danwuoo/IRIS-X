# Pilot Interpretation: `pilot-20260828-local-rerun-01`

- **Status:** reviewed local pilot result
- **Run manifest:** `run-manifest.json`
- **Raw episodes:** `raw/episodes.jsonl`
- **Derived aggregates:** `results.json`
- **Code revision executed:** `98b7103dcc735d41e246bebbfea1e794c84ba019`
- **Interpretation scope:** the fixed 12 development fixtures, two deterministic narrow controls, three same-environment repetitions

## Observed Results

The corrected run completed 72/72 episodes with zero invalid episodes, zero input mutations, zero model calls, zero retries/repairs/escalations/recoveries, and no paid or external service use.

| Configuration | Success | Partial | Failure | Task success rate | Joint evidence labels | Repeat agreement |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| `literal-readonly-v0` | 21/36 | 0/36 | 15/36 | 0.5833 | 21 `verified_success`; 15 `correctly_recognized_failure` | 12/12 tasks |
| `structured-readonly-v0` | 36/36 | 0/36 | 0/36 | 1.0000 | 36 `verified_success` | 12/12 tasks |

The literal control succeeded on the seven tasks in its declared link-extraction and terminology-inconsistency repertoire. It explicitly declined the two structure tasks and three contract-result tasks on every repetition. Those were actual task failures with sufficient evidence and matching failure claims, not false successes. The structured control produced the declared oracle output on all 12 tasks in all repetitions.

Within this development sample, H-B0 is contradicted and H-B1 is observed: adding the structured handlers changed success by 15/36 episodes, or five distinct tasks repeated three times. This result is mechanically expected from the declared repertoire difference and does not identify a generally superior agent design.

## Measured Cost Vector

| Configuration | Generation wall ms | Process CPU ms | Evaluation wall ms | Bytes read | Output bytes | Read operations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `literal-readonly-v0` | 22.8769 | 15.625 | 4.3691 | 5,391 | 19,326 | 51 |
| `structured-readonly-v0` | 25.9631 | 31.250 | 4.5884 | 5,391 | 20,760 | 51 |

The structured control recorded 3.0862 additional generation wall milliseconds and 1,434 additional output bytes across 36 episodes. These sub-second single-host timings are descriptive only; timer granularity, cache state, and operating-system scheduling were not controlled enough for a stable performance claim. Equal read bytes/counts follow from the shared evidence envelope.

Both controls report USD 0 model/API cost because model calls were prohibited and did not occur. Total lifecycle cost is not zero: electricity, hardware depreciation, development/specialization effort, fixture authoring, maintenance/remediation, and external failure impact remain `Unknown` and were not amortized.

## Reliability Interpretation

Both controls produced identical task outputs/outcomes across three same-environment repetitions for all 12 tasks, and the harness completed without an invalid episode on the corrected run. This is limited operational-repeatability evidence.

- Robustness: `Not evaluated`.
- Stateful reliability: `Not evaluated`.
- Change reliability / maintainability: `Not evaluated`.
- Recovery reliability: `Not evaluated`.

No reliability scalar is calculated.

## Failure Provenance

The preceding directory `../pilot-20260828-local/` preserves an invalid first attempt. That attempt wrote raw episodes and an aggregate, then exited nonzero because final run-manifest serialization used `false` instead of Python `False`. Its `failure.md` explicitly disqualifies its aggregate. The corrected run used a new directory and the clean code revision above.

## Decision Boundary

This pilot establishes that the Phase 3 manifest, outcome/evidence separation, local evaluator, resource fields, failure preservation, and two narrow controls execute reproducibly on the selected bytes. It does not establish:

- held-out or real-workload performance;
- a language-model or learned-agent baseline;
- robustness, recovery, stateful, change, or long-term reliability;
- lifecycle-cost sufficiency or a deployment threshold;
- that exact fixture oracles are universally valid;
- a final IRIS-X architecture or default framework.

The repository is ready to choose a later one-mechanism experiment at the Phase 3 decision gate. No Phase 4 mechanism is implemented here.
