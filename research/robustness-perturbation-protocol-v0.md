# Robustness Perturbation Protocol v0

- **ID:** note-2026-08-31-robustness-perturbation-protocol-v0
- **Status:** exploratory protocol
- **Question/scope:** Define when a deterministic input transformation may enter a future robustness experiment. This protocol qualifies measurement substrate; it does not measure or establish system robustness.
- **Corpus records:** `src.vanta` provides background examples only. The protocol and qualification cases are IRIS-X-authored.

## Admission record

Every transformation record must bind:

```text
transformation_id
precondition
deterministic_builder
seed_or_parameters
equivalence_validator
expected_oracle_identity_or_expected_change
```

A transformation may be labeled `semantics_preserving` only when its independent validator accepts both the precondition and the claimed semantic identity. Builder success, byte similarity, or a self-declared label is insufficient.

## Qualified candidate families

The accompanying substrate exercises four narrow contracts:

- irrelevant context insertion, where the task contract explicitly excludes the inserted `context.irrelevant` field from the oracle;
- equivalent JSON serialization, where independently parsed values are equal;
- item order permutation, where the task explicitly declares set semantics and item identifiers are unique;
- equivalent path presentation, where both relative paths independently canonicalize to the same in-boundary identity.

These validators apply only to their declared structures and preconditions. They do not license task paraphrase, terminology substitution, deletion, selector modification, entity renaming, or arbitrary source-byte substitution.

## Sensitivity rule

Qualification must include a transformation that changes an oracle-relevant selector. The equivalence validator must reject that claim. Failure to reject disqualifies the substrate.

## Evidence and claim boundary

The qualification runner records builder identity, parameters, source/transformed hashes, oracle hashes, validator decision, and reason. No candidate is executed. A passing run means only that the substrate accepts its declared positive cases and rejects the injected semantic change.

## Uncertainty

- **Unknown:** Future candidate behavior under any qualified perturbation.
- **Unclear:** Whether these four narrow families approximate real operational variation.
- **Not established:** System robustness, general semantic equivalence, or task-distribution representativeness.
- **Not evaluated:** Model candidates, prompts, workflows, and external providers.

