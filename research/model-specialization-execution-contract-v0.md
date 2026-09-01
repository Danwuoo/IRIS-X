# Model Specialization Execution Contract v0

- **ID:** note-2026-08-31-model-specialization-execution-contract-v0
- **Status:** exploratory execution contract
- **Question/scope:** Define provider-neutral candidate identity, execution, evaluation, failure, and cost records for a future specialization experiment. This is substrate only; it authorizes no model call, optimization, or H-P1 execution.
- **Corpus records:** None required. The qualification adapters and task are IRIS-X-authored deterministic fakes.

## Candidate identity

A candidate freeze record supports:

```text
candidate_id
candidate_type
candidate_source_or_prompt
candidate_sha256
base_model_id
base_model_provider
provider_snapshot_if_known
tool_envelope
program_or_workflow_definition
creation_method
optimizer_identity_if_any
```

The candidate SHA is computed over the exact frozen candidate bytes. Any change creates a different candidate identity. Candidate loading must verify the bound SHA before execution.

## Visibility and evaluator boundary

Candidate-visible packages contain only public task identity and public task input. Hidden generation state, hidden oracle, expected validity, evaluator configuration, and answer labels are excluded. Candidate output is serialized and hashed before the independent evaluator receives it.

For future `post-freeze-generated-blind` work, each generation manifest binds the already-frozen candidate SHA, frozen generator/evaluator identities, runtime envelope, new seed, and complete valid instance set.

## Design-time ledger

The design-time ledger remains distinct and supports:

```text
optimizer_model_calls
reflection_model_calls
candidate_evaluations
tokens
provider_cost_usd
wall_time
human_intervention
search_iterations
failed_candidate_count
```

Unknown values remain the string `Unknown`. In particular, a missing provider price is not zero. Design cost is not amortized into runtime cost without a declared deployment volume and horizon.

## Runtime ledger

Each terminal execution supports:

```text
model_calls
input_tokens
output_tokens
provider_cost_usd
tool_calls
verification_cost
retry_count
recovery_count
wall_time
artifact_bytes
```

Actual zero use may be recorded as zero when directly observed. Unknown price remains `Unknown`, even when this local fake uses zero model calls.

## Definition and code identity

Every new run manifest records both `definition_commit` and `code_commit` as
full 40-character Git commit SHAs. Each value must resolve to a commit in the
execution repository. Abbreviated, missing, symbolic, or non-commit identities
are invalid. The two fields may identify the same commit when the definition
and implementation were frozen together.

## Terminal evidence

Provider error, malformed output, timeout, tool failure, and explicit adapter failure become terminal records. There is no silent retry. Actual outcome, empirical evidence status, acceptance decision, verified-success eligibility, and execution state remain distinct.

A provider, adapter, timeout, tool, or deliberate fake failure that clearly
establishes task non-completion without frozen candidate output is recorded as
`actual_outcome: failure`, `empirical_evidence_status: sufficient`,
`acceptance_decision: not_applicable`,
`verified_success_eligibility: false`, and a failed terminal execution state.
The evaluator is not invoked as if candidate output existed.

Use `actual_outcome: unresolved` only when output existence or task completion
genuinely cannot be adjudicated. Its evidence status must be one of the
canonical Evaluation State Semantics v1 values and must describe the observed
evidence rather than substitute a legacy availability label. New records must
never emit `Unknown` as `actual_outcome` or `unavailable` as
`empirical_evidence_status`.

## Qualification claim boundary

The deterministic dry-run checks candidate loading/hash, public packaging, evaluator separation, post-freeze manifest binding, terminal evidence, separate ledgers, unknown-cost preservation, failure retention, and run-directory immutability. It makes zero external model/provider calls.

- **Unknown:** Future provider pricing, provider snapshot, model identity, and design-time search cost.
- **Unclear:** Which future specialization mechanism, if any, should be tested first.
- **Not established:** Model-specialization readiness by this contract alone, candidate quality, or lifecycle-cost advantage.
- **Not evaluated:** H-P1, model candidates, optimization, workflow search, routing, fine-tuning, and blind evaluation.
