# Analysis Custodian Packet

Freeze an analysis bundle using `analysis-bundle.schema.json` only after the
task/oracle, authority, verifier, and calibration bundle identities are sealed.
The analysis plan must depend on those exact bundle IDs/digests and may consume
only admitted sealed inputs.

Before analysis freeze, do not observe held-out results. After results exist,
you may not revise task/oracle rules, verifier logic, authority policy,
perturbation exclusions, calibration thresholds, comparator functions,
outcome-vector definitions, or the interpretation matrix.

Report the full vector with explicit denominators and task-family strata before
any preference. Compare R1-R5, perform the R5 factorized decomposition, report
Pareto relations without a primary scalar, preserve `unknown`, and quarantine
non-identifying strata. Optional weighted loss remains disabled unless a
separately authorized pre-frozen versioned contract exists.

Hash and seal the plan and provenance assets. Distinct analysis authorship does
not repair upstream independence defects; those remain
`independence_not_established`.
