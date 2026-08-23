# ARC-AGI-1 Run and Artifact Substrate v0

- **Version:** v0.1
- **Date:** 2026-08-06
- **Status:** Accepted Stage 2 development-only implementation
- **Scope:** Deterministic local ARC-AGI-1 run execution, resource/cost capture, and reconstructable run artifacts
- **Document role:** Durable operational implementation record. It is not a preregistration, formal run manifest, score report, decision record, official evaluator, sealed-evaluation protocol, or empirical adjudication.
- **Authoritative evaluation definition:** [ARC Evaluation Definition v0](./ARC-Eval-Definition-v0.md) sections 6–9, 15–18
- **Evaluator dependency:** [ARC-AGI-1 Evaluator Core v0](./ARC-AGI-1-Evaluator-Core-v0.md)

## 1. Boundary and status

The implementation under [`src/spex_arc/runner`](../../src/spex_arc/runner) establishes the Stage 2 development substrate for an ARC-AGI-1 solver. It executes only a strict `TaskView`, so test outputs are not in the solver interface. It has no provider adapter, model call, prompt policy, G0/S1 baseline, search, verifier, executable transformation, model adaptation, sealed split, or official submission path.

The runner uses the frozen local-reference evaluator identity. Its manifest requires `local-reference-non-official`, `official_status: Unavailable in checkout`, and `parity_status: not-established`. Any result produced through this code remains development-only and, when public A1 data is selected, `public-exposed` benchmark-proxy evidence. It must not be called official, parity-validated, sealed, private, research-qualified, public-complete, or verified-complete.

The pre-existing Stage 0 `rules_snapshot_mismatch` remains unresolved. This implementation reads the actual local rules hash through the Stage 1 evaluator and does not alter the Stage 0 manifest or rules snapshot.

## 2. Implemented contract

The minimum solver interface is:

```python
class Solver(Protocol):
    def solve(self, task: TaskView, budget: InferenceBudget) -> CandidateSet: ...
```

`ArcA1Runner` receives a frozen `RunManifest`, a `LocalReferenceEvaluator`, a factory that initializes the solver only after the manifest is fixed, and an artifact root. It sorts and checks the manifest's selected task IDs, derives a deterministic per-task seed, and supports retry, timeout classification, cooperative cancellation, and structured initialization, policy, budget, invalid-output, timeout, interruption, and solver-exception records.

`InferenceBudget` records and enforces per-task `num_attempts`, input/output-token, model-call, rollout, wall-clock, and concurrency limits. The current in-process implementation only accepts `concurrency_limit: 1`; this makes Python RNG control and artifact commit order deterministic. `record_usage()` reserves instrumented resource use before a solver request or rollout and immediately rejects a request that would exceed the frozen budget. It also records estimated USD cost.

The manifest's `network_access` and `tools` are enforced against a solver's declared `requires_network` and `required_tools` requirements before it is invoked. This is a configuration policy boundary, not an OS-level sandbox for arbitrary in-process Python. A solver that can evade its declaration cannot support a resource- or access-attribution claim; any future external provider or executable solver boundary must enforce the policy outside the process. This limitation is recorded rather than represented as a security guarantee.

The local evaluator is invoked only after the solver returns a candidate set. Its task score, any runner failure, and resource usage are then committed as terminal per-task artifacts.

## 3. Run manifest and artifact bundle

[`schemas/arc-agi-1-run-manifest.schema.json`](../../schemas/arc-agi-1-run-manifest.schema.json) contains the machine-readable manifest contract. The standard-library validator checks its required ARC Evaluation Definition resource-ledger fields and cross-field semantics that schema alone cannot express: active evaluator/rules identity, native-attempt limit, canonical task ordering, task selection, and the Stage 2 concurrency boundary.

Each run writes exactly this source-of-truth bundle, at `runs/<run_id>/` by default when that root is chosen by the caller:

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

All writes replace a fully written temporary file atomically. `predictions.jsonl` has one terminal record per task ID; it includes the returned candidate set (or `null`), local task score, structured runner failures, terminal status, and usage. `metrics.json` is derived from those per-task records, while `costs.json` is derived from the append-only usage and wall-clock events. `failures.jsonl` is reconciled from terminal records so an interrupted file sequence cannot erase a failure trace.

On restart, an existing `manifest.json` must exactly equal the frozen manifest. Completed task IDs are never invoked again. If the process stopped after a task-attempt start event but before a terminal artifact, the runner records `interrupted_before_finalization` rather than rerunning the task; this deliberately favours no double counting over speculative recovery. Every aggregate therefore links back to its selected per-task prediction/failure and resource records.

## 4. Validation and Stage 2 acceptance record

From repository root:

```powershell
python -m compileall -q src tests
python -m unittest discover -s tests -p 'test_*.py' -v
```

The suite has 16 passing tests. The Stage 2 cases use deterministic, no-network, no-tool dummy solvers and cover the full artifact bundle, schema/identity validation, deterministic re-run (identical predictions and metrics), resume without re-invoking an interrupted task, cost and wall-clock trace, retry, cooperative timeout cancellation, and structured budget/policy failures. The existing Stage 0 and Stage 1 regressions remain in the same suite.

| Stage 2 acceptance condition | Result |
|---|---|
| Deterministic dummy solver completes an end-to-end run | Pass — complete seven-file bundle and local-reference score record. |
| Re-running the same frozen configuration preserves predictions and metrics | Pass — terminal task records prevent a second invocation. |
| Interrupted work resumes without changing completed task records or double counting | Pass — unfinished started task is terminally recorded, not rerun. |
| Aggregate result traces to per-task prediction, failure, budget, and run-manifest records | Pass — metrics/cost ledgers name their source records and are derived from terminal/event artifacts. |
| ARC Evaluation Definition manifest fields are present and schema-validated | Pass — JSON Schema and active-identity semantic validator are shipped and regression-tested. |

## 5. Remaining blockers and status impact

The authoritative official A1 parser, scorer, evaluator, and submission writer remain **Unavailable in checkout**. The Stage 0 rules-manifest integrity conflict remains unresolved. Sealed-validation governance, custodian, private/semi-private access, model/provider snapshot, numerical Low/Matched/High budgets, seed/cost approval, and external-tool policy remain `TBD`. Those items block formal model runs and every official, sealed, private, efficiency, superiority, or generalization interpretation.

- **Empirical claim impact:** none.
- **Evidence adjudication impact:** none.
- **ARC stage-status impact:** none. This is local development infrastructure, not evidence for `A1-Research-Qualified`, `A1-Public-Complete`, or `A1-Verified-Complete`.
- **Winning-hypothesis impact:** none.

## 6. Change log

| Date | Version | Change | Status impact |
|---|---|---|---|
| 2026-08-06 | v0.1 | Added the validated Stage 2 local runner, run-manifest schema, atomic run bundle, resume/no-double-counting rule, resource/cost ledger, and regression record. | Operational development readiness only; no empirical, ARC stage-status, or winning-hypothesis change. |
