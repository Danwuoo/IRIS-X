# ARC Evaluation Implementation Development Stages (Temporary)

- **Version:** v0.1
- **Date:** 2026-08-05
- **Status:** Temporary working plan
- **Scope:** ARC-AGI-1 evaluation implementation and the minimum reusable substrate for later ARC-AGI-2 work
- **Authority:** Non-authoritative. This document does not replace the current Project State, Project Evaluation Definition, ARC Evaluation Definition, Dataset and Toolkit Status, a preregistration, a run manifest, or a decision record.
- **Retirement condition:** Remove or archive this file after the implementation stages are represented by accepted code, durable `docs/current/` or `docs/eval/` artifacts, and tracked work items.

## 1. Purpose

This document converts the current ARC evaluation requirements into a temporary implementation sequence. It is an engineering plan, not evidence that an evaluator, baseline, experiment, or ARC stage has been completed.

Authoritative inputs:

- [Project State](../current/PROJECT-STATE.md)
- [Project Evaluation Definition v0](../current/Project-Evaluation-Definition-v0.md)
- [ARC Evaluation Definition v0](../eval/ARC-Eval-Definition-v0.md)
- [ARC Dataset and Toolkit Status v0](../eval/ARC-Dataset-Toolkit-Status-v0.md)

If this file conflicts with an authoritative input, the authoritative input controls. Unresolved values remain `TBD`; implementation must not silently fill them by inference.

## 2. Temporary implementation decision

The recommended first round is evaluation-first and fixed-backbone:

1. freeze the ARC-AGI-1 data and evaluation substrate;
2. implement and validate the evaluator and artifact contracts;
3. establish a reproducible runner with resource and cost accounting;
4. implement `G0 -> S1 -> S2 -> S3` using the same model snapshot;
5. perform a preregistered paired comparison and at least one key component ablation;
6. defer `M1` and `H1` until model adaptation is explicitly brought into scope.

The evaluation units for this round are:

| Configuration | Unit | Temporary interpretation |
|---|---|---|
| `G0` | `G` | Direct generalist baseline with a minimal fixed interface |
| `S1` | `S` | Same model plus fixed structured prompting or representation |
| `S2` | `S` | Same model plus executable transformation or program synthesis |
| `S3` | `S` | Same model plus candidate search and verification |
| `M1` | `M` | Deferred; no model-level claim is eligible without this comparison |
| `H1` | `H` | Deferred until model and system effects can be separated |

This sequence can support same-backbone system-level comparisons. It cannot by itself support model-level specialization, persistent superiority, private generalization, broad capability, professional capability, or AGI claims.

## 3. Development stages

### Stage 0 - Freeze the A1 substrate

**Goal:** Make every task, rule, parser, scorer, and submission contract uniquely identifiable before a formal run.

Deliverables:

- canonical ARC-AGI-1 repository URL and commit or release pin;
- non-recursive task inventory for training and public evaluation tiers;
- machine-readable file manifest with per-file SHA-256 hashes;
- dataset-level manifest hash;
- immutable task-format and attempt-policy snapshot;
- parser, scorer, evaluator, and submission-writer source identity;
- contamination status and development-query log location;
- explicit label for every tier: training, development, milestone holdout, public-exposed, sealed, semi-private, or private.

Acceptance:

- regenerating the manifest from an unchanged checkout produces the same hash;
- missing, extra, renamed, or modified task files fail validation;
- no local public set is described as sealed or private without a separately accepted governance record;
- unavailable official scorer material is recorded as `Unavailable in checkout`, not reconstructed and called official.

Current blocker:

- sealed-validation split, custodian, and private or semi-private access path remain `TBD`.

### Stage 1 - Implement the domain and evaluator core

**Goal:** Establish a strict, model-independent ARC-AGI-1 evaluation contract.

Deliverables:

- `Grid`, `TrainPair`, `TestCase`, `Task`, `Prediction`, and `CandidateSet` types;
- strict JSON parser and schema validation;
- solver-facing task view that excludes test outputs;
- prediction validation for shape, rectangularity, cell range, test count, and attempt count;
- `Exact@1` scoring;
- native-attempt exact scoring using the frozen A1 attempt policy;
- diagnostic metrics such as pixel accuracy, shape accuracy, invalid-output rate, failure type, and additional-attempt salvage;
- deterministic submission reader and writer;
- regression fixtures and tests.

Task success must require exact matches for all test outputs in the task. Diagnostic metrics must not replace exact task accuracy.

Required regression cases:

- one and multiple test inputs;
- correct grid, wrong cell, wrong shape, empty grid, ragged grid, illegal value, missing output, and extra output;
- correct answer in the first attempt and only in a later allowed attempt;
- duplicate candidates and too many candidates;
- deterministic candidate ordering and serialization;
- malformed task and prediction JSON;
- evaluator version and rules-hash mismatch.

Acceptance:

- unit and regression suites pass from a clean environment;
- all invalid outputs become explicit structured failures rather than uncaught exceptions;
- scorer output is deterministic;
- local reference scoring remains labelled non-official until parity with an authoritative scorer is established.

### Stage 2 - Implement the run and artifact substrate

**Goal:** Make any solver executable under a common budget and fully reconstructable from its artifacts.

Minimum solver interface:

```python
class Solver(Protocol):
    def solve(
        self,
        task: TaskView,
        budget: InferenceBudget,
    ) -> CandidateSet: ...
```

Runner responsibilities:

- task selection and deterministic ordering;
- model and solver initialization;
- seed control;
- token, model-call, rollout, attempt, wall-clock, and concurrency limits;
- timeout, retry, cancellation, and failure classification;
- network and tool-policy enforcement;
- cost capture;
- atomic artifact writing and resumability without double counting;
- deviation recording;
- scorer invocation only after solver output is finalized.

Required run bundle:

```text
runs/<run_id>/
|-- manifest.json
|-- predictions.jsonl
|-- events.jsonl
|-- metrics.json
|-- costs.json
|-- failures.jsonl
`-- deviations.json
```

The files above are the source of truth. A database or analytical table may be generated as a derived index, but must not replace the immutable run bundle.

Acceptance:

- a deterministic dummy solver completes an end-to-end run;
- rerunning the same frozen configuration produces identical predictions and metrics;
- an interrupted run can resume without changing completed task records;
- every aggregate result traces back to per-task predictions, failures, budget use, and the run manifest;
- required manifest fields from the ARC Evaluation Definition are present and schema-validated.

### Stage 3 - Establish `G0` and `S1`

**Goal:** Freeze the direct generalist comparator and test one minimal system-level intervention.

Deliverables:

- provider-independent model adapter interface;
- exact provider, model ID, model snapshot, request parameters, date, and policy hashes;
- `G0` minimal prompt and output protocol;
- `S1` fixed structured representation or prompting policy;
- small development-only calibration runs;
- proposed `Low`, `Matched`, and `High` inference budgets based on observed baseline usage;
- paired task-level comparison under the same backbone and matched budget.

Acceptance:

- `G0` and `S1` differ only in the preregistered system intervention;
- prompts, parsing, retries, tools, context, and budgets are fully disclosed;
- public evaluation is not repeatedly queried for architecture selection;
- stochastic configurations use the accepted seed policy and never report the best seed as the primary result;
- the calibration result defines budget proposals but does not itself establish superiority.

### Stage 4 - Add `S2`, `S3`, and the key ablation

**Goal:** Attribute gains from executable transformations, candidate generation, search, and verification.

Deliverables:

- typed executable transformation or program representation;
- deterministic execution boundary with time, memory, and output limits;
- candidate provenance and train-pair consistency checks;
- search policy with explicit expansion, pruning, rollout, and stopping rules;
- verifier interface separated from candidate generation;
- `S2` and `S3` configurations under frozen model and budget contracts;
- at least one preregistered key ablation.

Preferred first ablation:

- `S3 full` versus `S3 without verifier`; or
- when verifier removal changes the candidate contract, `S3 full` versus `single-candidate / no-search`.

Acceptance:

- executable code cannot escape the defined sandbox or resource boundary;
- every candidate records its generator, execution result, verifier result, rank, and cost;
- disabling a component does not silently increase another resource to compensate;
- residual resource asymmetry is recorded when exact matching is impossible;
- candidate-generation ceiling and candidate-selection accuracy can be computed separately.

### Stage 5 - Run the first formal A1 comparison

**Goal:** Produce the first evidence package eligible for an `A1-Research-Qualified` decision, without presuming that status.

Prerequisites:

- Stages 0-4 accepted;
- frozen configuration and dependency lock;
- approved data-governance and evaluation-firewall protocol;
- approved compute tiers, seed count, cost ceiling, and comparator;
- formal preregistration with allowed and prohibited claims.

Execution requirements:

- complete frozen `G0 -> S1 -> S2 -> S3` runs at the selected budget point;
- at least one key ablation;
- per-task output, failure, cost, and deviation preservation;
- deterministic solver: at least one complete frozen run;
- stochastic solver: default at least five independent seeds; a three-seed high-cost exception must be labelled;
- task-level uncertainty and paired analysis using paired bootstrap or McNemar where appropriate;
- no best-seed primary result.

Acceptance:

- result reconstruction succeeds from a clean checkout;
- aggregate metrics match recomputation from the archived per-task records;
- public evaluation remains `public-exposed` unless stronger governance evidence exists;
- a decision record states unit, advantage type, construct, resource parity, effect size, uncertainty, generalization status, allowed claim, prohibited claim, and reversible-if condition;
- the decision record, not this temporary plan, determines whether any A1 stage criterion is evidenced.

### Stage 6 - Prepare the A1-to-A2 handoff

**Goal:** Make the frozen A1 system portable without beginning an A2 claim prematurely.

Deliverables:

- benchmark-neutral domain interfaces where A1 and A2 semantics agree;
- benchmark-specific attempt and submission policies outside solver logic;
- frozen A1-port configuration for later A2 transfer evaluation;
- compatibility tests against A2 task schemas without A2 evaluation tuning;
- list of A2-specific changes requiring a separate preregistration.

Acceptance:

- the A1 frozen port can be distinguished from an A2-adapted system;
- no A2 score is interpreted as transfer evidence without the required frozen-port comparison;
- A2 work does not begin before the applicable A1 entry gate is formally decided.

## 4. Proposed repository layout

```text
src/spex_arc/
|-- domain/
|-- data/
|-- evaluator/
|-- runner/
|-- artifacts/
|-- solvers/
|   |-- base.py
|   |-- g0.py
|   |-- s1.py
|   |-- s2.py
|   `-- s3.py
`-- cli.py

schemas/
|-- dataset-manifest.schema.json
|-- prediction.schema.json
|-- run-manifest.schema.json
`-- decision-record.schema.json

tests/
|-- unit/
|-- regression/
`-- fixtures/

experiments/
|-- configs/
`-- preregistrations/
```

Actual paths may change during implementation. Path changes do not relax the artifact, reproducibility, or governance requirements.

## 5. Open decisions before formal evaluation

| Decision | Current value | Blocking effect |
|---|---|---|
| First fixed backbone, provider, and model snapshot | `TBD` | Blocks executable `G0-S3` comparison |
| Official A1 parser, scorer, and submission source | `Unavailable in checkout` | Blocks official or parity-validated score language |
| Sealed-validation split and custodian | `TBD` | Blocks sealed generalization evidence |
| Private or semi-private access path | `TBD` | Blocks verified completion evidence |
| `Low / Matched / High` numerical budgets | `TBD` pending baseline calibration | Blocks resource-matched and efficiency claims |
| Final stochastic seed count and cost ceiling | `TBD` | Blocks formal run approval |
| Model API and external-tool policy | `TBD` | Blocks information-access parity |
| Artifact retention, secrets, and incident policy | `TBD` | Blocks production-grade run operations |
| First-round inclusion of `M1 / H1` | Deferred by this temporary plan; authority remains `TBD` | Prohibits model-level and hybrid claims |

## 6. Stop conditions

Stop the affected stage and report rather than guessing when:

- the canonical dataset or evaluator source cannot be identified;
- scorer behavior conflicts with the frozen rules;
- a test output can reach solver or model context;
- an executable transformation cannot be resource-contained;
- model snapshot, budget, tools, information access, cost, or attempt policy is missing;
- public evaluation has been used repeatedly for tuning without contamination disclosure;
- unrelated repository changes prevent isolation of the implementation diff;
- a formal run would proceed with an unresolved prerequisite listed above.

Partial implementation may continue in unaffected layers, but resulting artifacts must retain `development`, `local-reference`, `public-exposed`, `Unknown`, `TBD`, or `Not evaluated` labels as applicable.

## 7. Temporary completion definition

This temporary plan is complete when it provides an actionable implementation order and explicit gates. It does not complete an implementation stage merely by existing.

The temporary file may be retired when:

1. evaluator and run schemas are implemented and validated by the actual pipeline;
2. the development stages are represented by accepted tracked work;
3. durable manifests, preregistrations, reports, and decisions have entered `docs/current/` or `docs/eval/` where required;
4. any remaining open decisions are preserved as `TBD` in an authoritative artifact or accepted tracker;
5. retirement does not remove historical evidence or an authoritative record.

## 8. Status impact

- **Empirical claim impact:** none.
- **Evidence adjudication impact:** none.
- **ARC stage-status impact:** none.
- **Winning-hypothesis impact:** none.
- **Global experiment-design readiness impact:** none.
- **ARC-specific design readiness impact:** none; this file only sequences implementation work already required by current authoritative documents.
