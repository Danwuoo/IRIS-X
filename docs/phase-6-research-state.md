# Phase 6 Current Research State

- **Status:** Phase 6 closure record / durable current research state
- **Decision date:** 2026-09-10 Asia/Taipei
- **Required and actual closure baseline:**
  `de7a8471806c284d76c6c49bc52bedaabb1509c9`
- **Closure decision:** **Decision A — Close Phase 6**
- **Primary research authority:**
  `research/phase-6-formal-closure-and-research-state.md`
- **Closure-scope model/provider calls:** `0 / 0`
- **Architecture authority:** provisional, revisable, and not production-stable

## Decision

Phase 6 is closed because the repository now preserves a coherent bounded path:

```text
real task observation
-> conservative failure attribution
-> provenance-bound capability-pressure derivation
-> fail-closed deferred-capability gate adjudication
```

Batch 1 established the research instrument. Batch 2 preserved a provider-
schema sampling-path failure as Result C rather than misclassifying it as
capability pressure. Batch 3 completed the six-task sample and directly
observed one P4 semantic miss, while correctly closing historically as Result D
because its frozen predicate authority was defective. The separately identified
post-Batch-3 repair then bound the six preserved terminal records to validated
`any_equals` semantics without new task evidence or a model/provider call.

The repaired direct predicate is:

```text
cheaper_admitted_configuration_misses_requirement = true
```

This establishes bounded sampled task/configuration-level capability pressure.
It does not establish intrinsic model incapability or any intervention benefit.

## Current gate state

| Gate | Trigger status | Direct evidence boundary | Mechanism experiment authorized |
| --- | --- | --- | --- |
| H-G1 automated specialization | `not_triggered` | No demonstrated automation requirement or failed manual/frozen construction | No |
| H-W1 workflow machinery/search | `not_triggered` | No simple-flow insufficiency or evaluated workflow alternative | No |
| H-C1 cascade/escalation | `insufficient_or_ambiguous` | Cheaper miss `true`; stronger resolution `unknown`; trade-off `unknown` | No |
| H-R1 feature routing/allocation | `not_triggered` | Heterogeneity `true`; multiple allocations/frontier change `false` | No |
| Runtime persistence | `not_triggered` | No runtime-continuity requirement or restoration oracle | No |
| Nondeterministic verifier/model judge | `not_triggered` | Deterministic oracle insufficiency `false` | No |
| External-action/interception expansion | `not_triggered` | External/irreversible requirement `false` | No |
| General retry/recovery | `insufficient_or_ambiguous` | One semantic miss; no treatment comparison; benefit `unknown` | No |

**Deferred capability gates triggered by direct evidence: `0 / 8`.**

`unknown` has not been converted to `false`. `insufficient_or_ambiguous` is not
a positive trigger.

## Supported current conclusion

> IRIS-X can observe real bounded task pressure, distinguish it from substrate
> failure, attribute it conservatively, bind it to deterministic
> provenance-aware predicates, and stop before unsupported architecture
> expansion.

## Preserved uncertainty

Still `Not established`: P4 repeatability, intrinsic model incapability, retry
or recovery benefit, stronger-allocation resolution or benefit, cascade,
routing, workflow, automated-specialization, model-judge, persistence, or
external-action benefit; generalization beyond the sample; long-term
reliability; lifecycle-cost frontier or superiority; provider portability;
production readiness; final failure ontology; and final architecture.

## Historical authority

The following classifications remain unchanged:

```text
Phase 6 Batch 1: Result A — Foundation established
Phase 6 Batch 2: Result C — Sampling not semantically interpretable
Phase 6 Batch 3: Result D — Provenance or authority conflict
Post-Batch-3 repair: Result A — Authority repaired and re-derived
```

Later success or repair does not rewrite earlier negative or conflicting
results.

## Current stop boundary

```text
Phase 6: CLOSED
Architecture: provisional
Phase 6 Batch 4: NOT selected / NOT started / NOT authorized
Next phase/experiment: NOT selected / NOT started / NOT authorized
Model execution: NOT authorized
```

Any future sampling, repeatability test, treatment comparison, mechanism
experiment, or architecture work requires a new owner-authorized scope.
