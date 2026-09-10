# Phase 6 Post-Batch-3 Predicate/Provenance Authority Repair

- **ID:** `note-2026-09-10-phase-6-predicate-provenance-authority-repair`
- **Status:** result — **Result A — Authority repaired and re-derived**
- **Scope:** zero-model-call repair of research-local Batch 3 predicate source
  authority and any-match semantics over preserved Batch 3 evidence
- **Controlling plan:**
  `docs/plans/TEMP_PHASE_6_BATCH_3_PREDICATE_PROVENANCE_AUTHORITY_REPAIR.md`
- **Required and actual starting baseline:**
  `fc42646466b697e5723d6ae2db58fafcb8e13448`
- **Definition/test freeze:**
  `6beafccc2595808bcfac3ba8796a581156d76592`
- **Derived evidence commit:**
  `4f6b426c8721569cf264187a2709a47e14e01e91`
- **Model/provider calls:** `0 / 0`
- **Phase 6 Batch 4:** `NOT started / NOT authorized`

## Question and authority boundary

This bounded scope asks whether the two capability-predicate authority defects
preserved by Phase 6 Batch 3 Result D can be repaired without producing new
task evidence or implementing a capability mechanism.

The evidence ordering remains:

```text
Observation
-> Attribution
-> Capability-pressure predicate
-> Gate adjudication
```

This result stops at gate adjudication. It does not authorize minimal
intervention testing or architecture expansion.

Historical Batch 3 remains **Result D — Provenance or authority conflict**.
Its definition, frozen evaluation, direct-predicate artifact, result note,
handoff, and retired plan remain unchanged. This note records a new
post-Batch-3 Result A about repaired derivation authority, not a retrospective
Batch 3 Result B.

## Evidence basis

### Source-stated authority

- `research/problem-definition.md` separates task outcome, evidence status,
  execution-path attributes, and downstream architecture decisions.
- `research/phase-5-capability-trigger-review.md` defines the eight canonical
  deferred-capability trigger families and requires direct decision evidence,
  not mechanism availability or intuition.
- `experiments/capability-pressure-attribution-v0/definition/trigger-gates.json`
  freezes the Phase 6 Batch 1 canonical predicate inventories.
- `research/phase-6-capability-pressure-and-failure-attribution.md` requires
  every predeclared positive predicate and separates fixture recognition from
  direct-evidence triggers.
- `research/phase-6-direct-pressure-sampling.md` and its handoff preserve Batch
  2 Result C.
- `research/phase-6-sampling-path-repair-and-requalification.md`, its handoff,
  and its retired plan preserve Batch 3 Result D and identify the exact source
  and operator defects.

### Preserved direct observations

The repaired predicate binds the six immutable Batch 3 terminal records at
`/attribution/task_level_pressure_observed`:

| Task | Observed value | Terminal SHA-256 |
| --- | --- | --- |
| P1 selection | `false` | `0b7f527167a010388747ea910c59818fcdfacae35ebf15b161bcbca52e1dc4ca` |
| P2 aggregation | `false` | `920be7ad5888e1bf61f906a20fa7efc3c7989b92f14016b9abea602f4a63569c` |
| P3 ranking | `false` | `adca3dab6d07464943c99cd0281da0b8089ac0190502d9ece212890b66e4ee66` |
| P4 dependency | `true` | `a0ca487abef319e6be0157582c2ada82a37d7d4846deaf5bc455342651789edb` |
| P5 reconciliation | `false` | `7382d4dd63f07e9c9f125236b6d08111d52111ec64c1c4e68a1a34afddbb1577` |
| P6 rule precedence | `false` | `e5e32bfe87bb57ce228de3b144329f2c5bffaa42aecdc8b7f2fc8cba7ffb4cc2` |

P4's terminal record directly supports `shortfall_axis: task_success`,
`failure_locus/failure_stage: execution_producer`,
`frozen_configuration_shortfall: directly_supported`, and
`task_level_pressure_observed: true`. It retains
`model_intrinsic_capability_failure`, `retry_benefit`,
`routing_benefit`, and `stronger_allocation_benefit` as `Not established`.

## Authority repair

The new authority is
`phase-6-post-batch-3-predicate-provenance-authority-v1`, frozen at definition
SHA-256
`65fd34bb8c25c3de62a8a3e559c2cf86c2fea98ee7459a7e07079819965f13a1`.
It reuses the already existing evaluator whose SHA-256 is
`7978320f97144d774b2e0f7a9a4e4e2c9e3e4d19ff4d6e6700f3184429a9c74a`.

Two defects were repaired:

1. all six task-pressure sources now bind exact `runs/batch-3/` terminal paths;
   absent stronger-candidate, trade-off, and retry-comparison observations are
   likewise sought only in the Batch 3 evidence namespace and remain absent;
2. `rule-hc1-any-semantic-miss-batch3-v1` uses the evaluator's existing
   `any_equals` operator with expected `true`.

Direct inspection and focused tests establish that `any_equals` returns true
when any source observation equals the expected value. It therefore evaluates
the mixed Batch 3 vector `[false, false, false, true, false, false]` as true.
No new operator, evaluator redesign, or manual Boolean override was introduced.

Every resolved predicate record carries the rule ID/hash and exact source
path/hash/pointer/value. Missing observations remain `unknown`. Rule-hash
drift, source-hash drift, bad pointers, manual overrides, and contradictory
observations fail closed under the reused evaluator and focused regression
tests.

## Repaired predicate result

`cheaper_admitted_configuration_misses_requirement = true`.

This means exactly:

> At least one of the six preserved Batch 3 sampled tasks did not satisfy its
> frozen requirement under the admitted cheaper configuration.

It is bounded direct capability pressure at the sampled task/configuration
level. It is not evidence of intrinsic model incapability or of an
intervention's benefit.

## H-C1 adjudication

The Phase 5 canonical H-C1 authority requires a qualifying cheaper miss, a
specifically declared stronger candidate that plausibly resolves it, and a
decision-relevant trade-off. The Batch 3 sampling operationalization preserves
that three-part conjunction with these identifiers:

| Required operational predicate | Derived value | Provenance / missing evidence |
| --- | --- | --- |
| `cheaper_admitted_configuration_misses_requirement` | `true` | Derived by `any_equals` from six hash/pointer-bound Batch 3 terminal observations. |
| `stronger_candidate_resolves_miss` | `unknown` | `runs/batch-3/comparison-observation.json` is absent because no stronger-candidate treatment was authorized or run. |
| `decision_relevant_tradeoff_established` | `unknown` | The same comparison authority is absent; no cost/reliability trade-off was evaluated. |

Therefore:

```text
first H-C1 prerequisite satisfied: yes
H-C1 triggered: no
H-C1 status: insufficient_or_ambiguous
architecture experiment triggered: no
```

`predicate true != gate triggered`.

## All capability-gate adjudications

The table reports the actual repaired sampling operational predicates. The
more detailed Batch 1 canonical inventories remain authoritative context; the
repaired evidence does not bypass them. For gates with a derived false
necessary condition, additional canonical predicates cannot convert the gate
to a trigger. Unknown comparison predicates remain explicit rather than being
fabricated as false.

| Gate | Required predicates and derived values | Provenance status / missing evidence | Gate status | Architecture experiment triggered |
| --- | --- | --- | --- | --- |
| H-G1 automated specialization | `automated_specialization_required=false` | Hash-bound launch policy records manual frozen authoring; no direct automation need. | `not_triggered` | No |
| H-W1 workflow machinery/search | `simple_fixed_control_flow_insufficient=false` | Hash-bound launch policy records one fixed control flow; no control-flow insufficiency observation. | `not_triggered` | No |
| H-C1 cascade/escalation | cheaper miss=`true`; stronger resolution=`unknown`; trade-off=`unknown` | Six Batch 3 terminal bindings valid; no Batch 3 comparison observation. | `insufficient_or_ambiguous` | No |
| H-R1 feature routing/allocation | heterogeneity=`true`; multiple allocations=`false`; frontier change=`false` | Hash-bound manifest/policy; one allocation and no allocation comparison. | `not_triggered` | No |
| Runtime persistence | `runtime_state_continuity_required=false` | Hash-bound launch policy; no continuity requirement or restoration observation. | `not_triggered` | No |
| Nondeterministic verifier/model judge | `deterministic_oracle_insufficient=false` | Hash-bound launch policy and deterministic terminal authority; no oracle insufficiency. | `not_triggered` | No |
| External action/interception expansion | `external_or_irreversible_action_required=false` | Hash-bound launch policy; zero external actions and no external-effect task requirement. | `not_triggered` | No |
| General retry/recovery | `bounded_retry_or_recovery_benefit_compared=unknown` | No Batch 3 retry/recovery comparison observation; actual retry/recovery counts remain zero. | `insufficient_or_ambiguous` | No |

Direct-evidence triggered gates: **0 / 8**.

The canonical Batch 1 gate inventories give the same safe upper-bound
interpretation:

- H-G1 lacks a repeatable specialization requirement, failure of manual/frozen
  construction, and an automated-production decision variable.
- H-W1 lacks failure of simple ordering, a material control-flow decision, and
  an evaluated workflow alternative.
- H-C1 has only its first prerequisite; stronger-candidate resolution and a
  decision-relevant trade-off are missing.
- H-R1 has task heterogeneity but lacks multiple compared allocations,
  material allocation outcome/resource differences, and a frontier change.
- persistence lacks a continuity requirement and restoration oracle.
- nondeterministic verification lacks deterministic-oracle insufficiency,
  material non-reducible judgment, and an independent reference.
- external-action expansion lacks an external/irreversible requirement,
  authorization boundary, and authenticated post-state requirement.
- recovery/retry lacks a specified treatment, safe treatment comparison, and
  independently observed benefit; a wrong answer alone is a negative control,
  not a trigger.

## Result classification

**Result A — Authority repaired and re-derived.**

The new, separately identified authority deterministically and
provenance-boundly derives all predicates and safely adjudicates all eight
gates from the preserved Batch 3 and frozen-definition observations. There is
no remaining source, operator, hash, pointer, or derived-output conflict in
this repair surface. This does not erase the historical defect or Batch 3
Result D.

## What is newly supported beyond Batch 3 Result D

Batch 3 already directly supported P4's task-level semantic shortfall. This
repair newly supports an authoritative capability-predicate statement:

> Preserved Batch 3 direct evidence establishes that the frozen admitted
> cheaper configuration missed at least one sampled task requirement.

The additional support is at the derivation-authority layer. It does not add a
new model observation, expand the sampled task distribution, or establish a
mechanism benefit.

## Not established

- intrinsic model incapability or general model capability;
- retry benefit, repeated-retry benefit, or recovery benefit;
- stronger-allocation resolution or benefit;
- cascade or escalation benefit;
- routing/allocation benefit;
- workflow machinery/search benefit;
- persistence, nondeterministic-judge, specialization, or external-action
  benefit;
- generalization beyond the six Batch 3 sampled tasks;
- provider portability, production readiness, long-term reliability, or a
  lifecycle-cost frontier;
- a final failure ontology or final architecture.

## Validation and preservation

- repair focused tests: `10/10` passed;
- existing Phase 6 sampling tests: `41/41` passed;
- Phase 6 Batch 1 tests: `35/35` passed;
- Phase 5 model qualification/task-family tests: `75/75` passed;
- definition and repaired-authority validators: PASS;
- direct predicate, gate adjudication, and manifest regeneration:
  byte-identical, including two independent regenerations;
- repository check: PASS — 13 sources, 7 artifacts, hashes checked;
- full discovered inventory: 282 tests, 281 passed, one unchanged historical
  Phase 4 hash failure, zero errors, zero new failures/errors.

The Batch 2 run tree, Batch 3 run tree, original Batch 3 predicate definition,
Batch 3 Result D note/handoff/retired plan, `irisx/core`, `sources`, and
`references/papers` match baseline identities. Model/provider calls were zero.

## Closure interpretation and recommendation

This bounded authority-repair scope has met its research question and can
close as Result A. Phase 6 now has a coherent bounded chain through Batch 3 and
this post-Batch-3 repair: the Batch 3 sample is task-semantically interpretable,
and its task-pressure predicate is now authoritatively derivable.

This is a reasonable condition for closing the currently authorized Phase 6
work, not proof that Phase 6 has answered intervention-benefit questions or
that the architecture is final. Any stronger-allocation, retry/recovery,
routing, workflow, persistence, judge, specialization, external-action, or new
sampling experiment requires a new owner-authorized scope.
