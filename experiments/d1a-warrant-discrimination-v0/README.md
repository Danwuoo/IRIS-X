# D1a Warrant Discrimination Qualification Substrate v0

- **Status:** qualification-development package; `ready_for_independent_custodians`
- **Scientific status:** D1a remains unqualified and unexecuted
- **Provider/model calls authorized or performed by this package:** 0
- **D1b authority:** none

This package is a neutral, deterministic intake and instrument-qualification
surface for the frozen D1 construct in
`research/d1-held-out-warrant-generalization-spec.md`. It does not contain
independently authored held-out tasks, an authority policy, a semantic verifier,
an exact-configuration calibration bundle, or a sealed analysis submission.
Passing its meta-fixtures establishes only that the instrument can represent the
required controls and rival win regions. It is not D1 evidence.

The package separates:

1. immutable scientific contracts in `definition/`;
2. role instructions in `custodian-packets/`;
3. strict submission schemas in `submission-schemas/`;
4. coordinator-authored synthetic instrument tests in `meta-fixtures/`;
5. zero-provider-call validators and evaluators in `scripts/`; and
6. focused deterministic tests in `tests/`.

No empirical `runs/` directory exists. Real custodian assets must be authored
outside the coordinating session, sealed, admitted, and assembled without
changing the frozen contracts or interpretation matrix.

## Deterministic qualification

From the repository root:

```powershell
python -m unittest discover -s experiments\d1a-warrant-discrimination-v0\tests -v
python experiments\d1a-warrant-discrimination-v0\scripts\qualify_instrument.py
python experiments\d1a-warrant-discrimination-v0\scripts\assemble_d1a_bundle.py --meta-qualified
```

The last command reports `ready_for_independent_custodian_submission` while
real submissions are absent. It never fabricates placeholders.

## Admission boundary

`schema_valid`, `provenance_complete`,
`information_boundary_declared`,
`information_boundary_mechanically_checkable`, `independence_supported`,
`independence_not_established`, and `rejected` are distinct states. A valid
schema or a signed-looking declaration is not scientific independence.

`ready_for_d1a_qualification` is available only after all real role bundles are
sealed, digest-valid, boundary-valid, cross-role provenance is distinct, and
the analysis bundle depends on the exact admitted component identities.
