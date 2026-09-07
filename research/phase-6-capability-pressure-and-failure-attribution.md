# Phase 6 Capability Pressure and Failure Attribution

- **ID:** `note-2026-09-07-phase-6-capability-pressure-attribution`
- **Status:** experiment / result pending authoritative Batch 1 run
- **Question/scope:** Under preserved Phase 5 task and evidence semantics, can a
  bounded deterministic offline instrument keep observed shortfall, causal
  attribution, intervention hypothesis, and deferred-capability trigger status
  separate while reproducing selected Phase 5 decisions? This note does not
  define a final failure ontology or authorize a deferred mechanism.
- **Controlling plan:**
  `docs/plans/TEMP_PHASE_6_CAPABILITY_PRESSURE_AND_FAILURE_ATTRIBUTION.md`
- **Required and actual starting baseline:**
  `4aa7256e2237e997425e8712638334088056037d`
- **Provider/model call ceiling:** `0 / 0`

## Question / scope

Phase 6 Batch 1 addresses the project-level RQ1 sufficient-capability and RQ5
failure-attribution questions through an offline research instrument. The
instrument may recognize a deliberately satisfied fixture predicate, but it
does not execute or recommend architecture mechanisms automatically.

The controlling distinctions are:

```text
observation != attribution
attribution != intervention
intervention != trigger
synthetic trigger-positive != direct-evidence trigger
failure != retry requirement
heterogeneous tasks != routing requirement
durable Git evidence != runtime persistence
natural-language output != model-judge requirement
```

## Evidence basis

### Source-stated authority

- `research/problem-definition.md` states that outcome status and
  epistemic/evidence status are distinct, retry/escalation/recovery are
  execution-path attributes, and architecture is a downstream research result.
- `research/phase-5-architecture-consolidation.md` records supported trust
  boundaries, provisional substrate choices, and the limits of Batch 4 and
  Batch 6 evidence.
- `research/phase-5-capability-trigger-review.md` states the eight deferred
  capability criteria and records each direct-evidence trigger as
  `Not triggered` at Phase 5 close.
- `docs/phase-5-architecture-state.md` and
  `docs/phase-5-architecture-consolidation-handoff.md` preserve the Phase 5
  closure scope, evidence lineage, validation baseline, and known historical
  test failure.

### Direct repository evidence selected for replay

- Batch 4 Run 01 and Run 02 terminal, resource, interpretation, and stderr
  records under
  `experiments/substrates/model-execution-qualification-v0/runs/` directly
  record two local configuration rejections, no model result, and zero retry,
  route, escalation, or recovery actions.
- The Batch 6 derived summary and three source terminal records under
  `experiments/substrates/model-execution-qualification-v0/task-family/`
  directly record one shared admitted configuration, three distinct task
  identities, 3/3 verified success, read-only state, and zero retry, route,
  escalation, or recovery actions. The terminal records remain authoritative
  over the derived summary.

### Directly observed Batch 1 baseline

- `git` inspection observed `HEAD`, `main`, and `origin/main` at the required
  baseline with no divergence before plan activation.
- `python tools/repository_check.py` passed with 13 sources and 7 artifacts.
- The pre-edit full discovered inventory ran 196 tests: 195 passed and the one
  failure was the already-recorded Phase 4 frozen-plan hash mismatch. This
  observation does not repair or reclassify that historical contract.

## Phase 6 research framing

The provisional proposition is that explicit finite predicates can make
architecture-trigger claims harder to infer from surface symptoms. A useful
instrument must fail closed, preserve ambiguity, and keep synthetic evidence
from changing the direct-evidence trigger ledger.

The architecture decision layer remains outside the evaluator. An assessment
can identify candidate pressure and intervention hypotheses; it cannot
authorize routing, retry, persistence, a judge, or another deferred mechanism.

## Candidate pressure model

The research-local shortfall axes are:

- `task_success`: a frozen task contract is not met;
- `evidence`: outcome/evidence authority is insufficient or invalid;
- `reliability`: a declared repeated, shifted, stateful, or post-failure
  requirement is not met;
- `lifecycle_cost`: requirements may be met, but an explicit comparison is
  materially dominated within a declared accounting boundary.

These axes are provisional. In particular, lifecycle cost is retained as a
pressure classification for a declared comparison, not promoted into a fourth
project-level outcome dimension.

## Candidate attribution vocabulary

The research-local candidate stages are:

```text
admission_configuration
identity_authority
execution_producer
verification
state_continuity
control_flow
allocation_capability
external_effect
resource_cost
unknown
```

The attribution statuses are `directly_supported`, `inferred`, `ambiguous`, and
`not_attributable`. Multiple supported stage signals must remain `ambiguous`
rather than being resolved by a numeric confidence or an unsupported tie-break.
This vocabulary is non-normative and is not an `irisx/core` ontology.

## Trigger operationalization

The instrument operationalizes the Phase 5 families H-G1, H-W1, H-C1, H-R1,
runtime persistence, nondeterministic verification/model judging, external
action/interception expansion, and general recovery/retry. Each finite gate
requires every predeclared positive predicate. Missing predicates produce a
negative or insufficient result; a fixture can produce only
`triggered_by_fixture`.

Direct repository evidence may produce `triggered_by_direct_evidence` only when
its source paths and SHA-256 identities are present and all gate predicates are
derived from that evidence. The selected Phase 5 replay is expected to preserve
`not_triggered` for every gate it assesses.

## Synthetic pressure suite

The frozen design will contain 24 primary cases: one surface-only negative,
one near-trigger boundary, and one positive predicate fixture for each of the
eight gates. Positive synthetic behavior tests gate recognition only. It is not
evidence about the observed IRIS-X task distribution.

## Historical replay

The Batch 4 replay must retain `admission_configuration`, with model-capability
failure, retry need, and escalation need `Not established`. The Batch 6 replay
must retain one allocation, three successes, and no routing, escalation,
recovery/retry, or persistence trigger. Source files are hash-bound inputs and
will not be rewritten.

If either accepted distinction cannot be reproduced, the result becomes
`Result C — Conflicting evidence` and architecture interpretation stops.

## Observed results

Pending the definition/code freeze and authoritative offline run. No result is
inferred from fixture design or pre-run tests.

## Conflicts / ambiguity

- **Conflicting evidence:** none observed in the pre-run source inspection.
- **Ambiguity:** at least two collision fixtures will deliberately preserve
  multiple causal candidates until additional evidence is supplied.
- **Unknown:** whether the candidate stage vocabulary transfers beyond the
  bounded fixtures and selected Phase 5 replay.

## What is supported

Pending authoritative evidence. The maximum allowed Result A conclusion is
limited to deterministic distinction of the predeclared cases and successful
compatibility replay of selected Phase 5 decisions.

## What is not established

- a final failure ontology or general causal diagnosis;
- need, correctness, or value of any deferred capability;
- production or provider behavior;
- general reliability or lifecycle-cost advantage;
- authority for a model call or Phase 6 Batch 2.

## Decision for next research action

Pending the authoritative offline result. Any recommendation will identify one
pressure to sample and will require separate owner authorization before
execution.
