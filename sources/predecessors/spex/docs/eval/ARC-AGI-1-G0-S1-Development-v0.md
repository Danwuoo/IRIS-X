# ARC-AGI-1 G0/S1 Development v0

- **Version:** v0.1
- **Date:** 2026-08-06
- **Status:** Partially implemented Stage 3 development substrate; configured model calibration and paired ARC run blocked
- **Scope:** Provider-independent fixed-backbone `G0` / `S1` contracts, disclosure binding, resource settlement, calibration proposal derivation, and paired task-level result reconstruction
- **Document role:** Durable operational implementation record. It is not a provider approval, preregistration, formal run manifest, score report, decision record, official evaluator, sealed-evaluation protocol, or empirical adjudication.
- **Authoritative evaluation definition:** [ARC Evaluation Definition v0](./ARC-Eval-Definition-v0.md) sections 5–9 and 13–18
- **Implementation-stage source:** [ARC Evaluation Implementation Development Stages](../temp/ARC-Evaluation-Implementation-Development-Stages.md), Stage 3

## 1. Boundary and status

The implementation in [`src/spex_arc/solvers`](../../src/spex_arc/solvers) and [`src/spex_arc/baselines`](../../src/spex_arc/baselines) supplies the engineering contracts needed to configure an actual direct-generalist `G0` and fixed-structured-prompt `S1` comparison. It does **not** select or call a real provider, choose a model ID or snapshot, set an external-tool policy, spend API funds, read ARC public tasks for calibration, or create a formal result.

Consequently, this document records a tested Stage 3 implementation substrate, not Stage 3 acceptance. The project operational stage remains the accepted Stage 2 local run/artifact substrate. Any future use of A1 public evaluation data remains `public-exposed` development evidence and must be recorded in the [development query log](./ARC-AGI-1-Development-Query-Log.md) before interpretation.

The local evaluator remains `local-reference-non-official`; official A1 parser, scorer, evaluator, and submission-writer material remains **Unavailable in checkout**. The pre-existing Stage 0 `rules_snapshot_mismatch` is unchanged.

## 2. Implemented G0/S1 contract

`G0Solver` and `S1Solver` take the same provider-independent `ModelAdapter` boundary:

```python
class ModelAdapter(Protocol):
    identity: ModelIdentity
    requires_network: bool
    required_tools: tuple[str, ...]

    def prepare(self, request: ModelRequest, budget: InferenceBudget) -> PreparedModelRequest: ...
    def complete(self, prepared: PreparedModelRequest) -> ModelResponse: ...
```

`prepare()` may not contact a provider. It returns the exact outgoing request and its upper-bound token/call/rollout/cost reservation. The solver records this reservation through the common runner before calling `complete()`. A response must report usage no greater than that reservation; unused token and cost allowance is then settled into the event and cost ledgers. The runner therefore retains a per-task trace of both the pre-request boundary and observed usage without accepting provider-specific post-hoc accounting alone.

Both policies use the strict Stage 1 solver view: training input/output pairs and test inputs only. The model cannot receive test outputs through the prompt builder.

| Configuration | Unit | Frozen intervention | Explicitly absent |
|---|---|---|---|
| `G0` | `G` | Minimal direct task prompt and candidate-set JSON output protocol | Structured representation, tools, retrieval, memory, search, verifier, adapted weights |
| `S1` | `S` | Fixed object/component and transformation-checklist prompt | Tools, retrieval, memory, search, verifier, executable transformation, adapted weights |

The prompt policy object—including instructions, representation, output protocol, and policy ID—is canonicalized and SHA-256 hashed. A malformed model response becomes an empty candidate set and is scored by the existing evaluator as structured invalid output; it is not treated as a successful solve.

## 3. Frozen disclosure and comparison binding

The Stage 3 revision updates [`arc-agi-1-run-manifest.schema.json`](../../schemas/arc-agi-1-run-manifest.schema.json) to schema version `1.1`. In addition to the Stage 2 fields, each run manifest now requires:

- configuration ID and canonical configuration SHA-256;
- provider-adapter ID;
- non-secret provider request parameters and their SHA-256;
- complete prompt-policy object and SHA-256; and
- retry policy, including `max_retries`.

`BaselineConfiguration.binding_failures()` rejects a manifest whose model provider, model ID, model snapshot, weights hash, request parameters, request date, prompt policy, retry policy, tools, network access, unit, or configuration identity differs from the frozen configuration.

`paired_precondition_failures()` then rejects a `G0`/`S1` pair unless both configurations share the same model identity, request parameters, request date, retry/tool/network/context policies, evaluator/data identity, task ordering, seed, budget, cost ceiling, and all other comparison-boundary manifest fields. The allowed differences are the distinct run/configuration IDs, `G` versus `S` unit, and the two explicit prompt-policy objects/hashes. This is a development contract; it is not a preregistration.

`BaselineSolverFactory` is the execution entrypoint for these configurations. It verifies the manifest binding again, checks the adapter identity/network/tools against the same frozen record, creates only the label-matching solver, and supplies the manifest's frozen retry count to `ArcA1Runner`.

## 4. Calibration and paired-result utilities

`load_calibration_observation()` reads only the immutable `manifest.json` and `costs.json` from a completed run bundle. `derive_budget_proposal()` derives `Low`, `Matched`, and `High` proposals from observed per-task maxima and an explicitly supplied multiplier policy. It records source run IDs, maxima, multipliers, proposed `InferenceBudget` values, and estimated cost. It does not choose multipliers or turn a proposal into an approved compute tier.

`summarize_paired_task_comparison()` reconstructs `Exact@1` differences from both bundles' `predictions.jsonl` files. It preserves one task row per task ID and reports `G0`-only and `S1`-only solves separately, rather than treating aggregate scores as sufficient evidence.

## 5. Validation record

From repository root:

```powershell
python -m compileall -q src tests
python -m unittest discover -s tests -p 'test_*.py' -v
```

The suite passes **18 tests**. The Stage 3 regression cases use a deterministic, no-network replay adapter and the existing synthetic fixture task; they do not call a provider or query local ARC public data.

| Check | Result |
|---|---|
| G0/S1 share an exact model identity and differ only in policy/unit/configuration identifiers | Pass — symmetric fields are checked and an asymmetric budget is rejected. |
| Provider request reservation is recorded before completion and settled to observed use | Pass — fixture ledger records 7 input tokens, 5 output tokens, and USD 0.03 after a larger reservation. |
| Complete task-level pairing is reconstructable from two run bundles | Pass — fixture records retain one task row and the expected G0/S1 difference. |
| Calibration proposal is derived from observed per-task ledger data with explicit multipliers | Pass — fixture produces ordered `Low`, `Matched`, and `High` proposals. |
| Actual provider/model calibration on A1 data | Not run — provider, model snapshot, external-access policy, and cost approval remain `TBD`. |
| Numerical Low/Matched/High tiers and an actual paired G0/S1 result | Not established — requires an approved configuration and real baseline calibration. |

The fixture's intentional `G0`/`S1` outcome is a contract test only. It is not an ARC benchmark observation, a calibration result, or evidence of superiority.

## 6. Remaining blockers and status impact

The following authoritative decisions remain `TBD`: first fixed backbone/provider/model snapshot; approved model/API and external-tool policy; approved calibration task selection and query-log event; numerical `Low`/`Matched`/`High` tier policy; seed count and cost ceiling; formal preregistration; sealed governance; and official evaluator material. Executing a real adapter may incur paid external usage and must receive the required approval before it is configured or called.

- **Empirical claim impact:** none.
- **Evidence adjudication impact:** none.
- **ARC stage-status impact:** none. No `A1-Research-Qualified`, public-complete, or verified-complete criterion is evidenced; the Stage 3 acceptance conditions requiring actual calibration and paired runs remain unmet.
- **Winning-hypothesis impact:** none.

## 7. Change log

| Date | Version | Change | Status impact |
|---|---|---|---|
| 2026-08-06 | v0.1 | Added provider-independent G0/S1 solvers, frozen disclosure binding, manifest schema v1.1, pre-request resource reservation/settlement, calibration proposal derivation, paired task-level reconstruction, and regression coverage. | Tested implementation substrate only; no empirical, adjudication, or ARC stage-status change. |
