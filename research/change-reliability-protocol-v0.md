# Change Reliability Protocol v0

- **ID:** note-2026-08-31-change-reliability-protocol-v0
- **Status:** exploratory protocol
- **Question/scope:** Define a paired, task-level comparison that can detect candidate/configuration regressions. This qualifies a measurement substrate and does not establish maintainability.
- **Corpus records:** None required; the self-test candidate and cases are IRIS-X experiment-local artifacts.

## Comparison identity

A valid comparison binds the baseline and changed candidate identifiers and SHA-256 values, task frame, evaluator, task/source generation identity, and runtime envelope. A mismatch in any invariant yields `invalid_comparison`; it is not counted as improvement or regression.

## Separate task-level dimensions

The classifier supports multiple simultaneous dimensions:

```text
regression
improvement
unchanged_success
unchanged_failure
evidence_regression
cost_increase
cost_decrease
invalid_comparison
```

Outcome, evidence, and resource changes remain separate. In particular, an unchanged successful answer can still have an evidence regression or cost increase. Candidate acceptance is not inferred from these empirical fields.

## Injected-regression qualification

The qualification substrate compares an identity baseline candidate with an intentionally faulty deterministic configuration. The faulty configuration alters a required answer for one case, removes required evidence for another, and adds declared local work to a third. The evaluator is independent of candidate configuration.

Qualification requires the harness to report the known outcome regression, evidence regression, and cost increase while preserving one unchanged success. Unit tests separately exercise improvement, unchanged failure, cost decrease, and invalid-comparison classification.

## Claim boundary and uncertainty

A passing qualification means only: the regression measurement substrate detects this injected regression.

- **Unknown:** Sensitivity to future model or workflow changes.
- **Unclear:** Appropriate practical thresholds for multi-dimensional change decisions.
- **Not established:** General maintainability, causal attribution beyond the injected faults, or production regression risk.
- **Not evaluated:** External providers, model candidates, optimization, and deployment cost.
