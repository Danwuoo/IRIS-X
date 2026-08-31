# Held-Out Evaluation Protocol v0

- **ID:** note-2026-08-31-heldout-evaluation-protocol-v0
- **Status:** exploratory protocol
- **Question/scope:** Govern future specialization evaluation visibility and post-freeze instance generation. This protocol does not authorize a model experiment or materialize a future blind set.
- **Corpus records:** Existing `src.vanta` fixtures are visibility-governed evidence, not automatically unseen instances.

## Evidence classes

### `development-visible`

Instances or families available for implementation, debugging, prompt editing, optimizer feedback, candidate selection, or manual error analysis. They cannot later become held-out evidence for the candidate that used them.

### `protocol-instance-heldout`

Existing instances assigned away from development and optimizer feedback by a predeclared split. They remain repository-visible in principle, so this is a procedural property rather than proof of being unseen.

### `protocol-family-heldout`

A whole task family or stratum excluded from development and optimization, opened only after candidate freeze and evaluation authorization. Repository visibility still prevents a guaranteed-unseen claim.

### `post-freeze-generated-blind`

New instances generated after candidate freeze from an evaluator/generator protocol frozen beforehand. `Blind` means instance-blind after candidate freeze; the generator implementation is not claimed to be secret.

Existing repository fixtures may occupy the first three classes under a valid declaration. They are not automatically unseen and cannot be called `post-freeze-generated-blind`.

## Required future split declaration

Before any H-P1-like optimization, declare and freeze:

```text
development_set
optimizer_visible_validation_set
protocol_heldout_set
blind_generation_protocol
candidate_freeze_point
evaluation_authorization_point
validity_and_inclusion_rules
```

Anything inspected or used for prompt editing, candidate selection, optimizer feedback, debugging, or pre-freeze error analysis is `development-visible` for that candidate. Holdout status cannot be assigned retroactively.

## Post-freeze generated sequence

The required order is:

```text
candidate freeze
→ candidate SHA
→ evaluator and generator freeze
→ runtime/resource envelope freeze
→ close design-time cost ledger
→ new generation seed
→ generate every declared instance
→ validate inclusion without outcome inspection
→ candidate execution on candidate-visible bundles only
→ freeze candidate outputs
→ independent oracle evaluation
```

The generation manifest must bind the candidate SHA, generator/evaluator identities, seed, inclusion rules, and the complete set of valid generated instances. Generator or validation failures are terminal evidence.

## Blind-set invalidation

Once blind contents or results have been inspected, modifying the candidate invalidates that set as blind evidence for the modified candidate. The new candidate requires a new freeze, candidate SHA, generation seed, and newly generated instances. Prior evidence remains preserved under its original candidate identity.

## No post-generation cherry-picking

Validity and inclusion rules freeze before generation. Every generated instance satisfying those rules must be evaluated. Hard but valid cases may not be discarded after content or outcome inspection. Invalid generation attempts remain recorded with reasons and are not silently regenerated unless the frozen protocol predeclares that procedure.

## Cost boundary

Design-time costs close before blind instance generation. Runtime costs begin with candidate execution and remain a separate ledger. Neither unknown ledger values nor generator failures are converted to zero. Amortization requires a separately declared deployment horizon.

## Current qualification status

The companion generator substrate uses only declared `development-visible` qualification seeds. It does not create or commit a future real blind evaluation set. No candidate, model, optimizer, or paid provider is authorized in this batch.

## Uncertainty

- **Unknown:** Future candidate identity, provider, candidate freeze SHA, and blind generation seed.
- **Unclear:** Difficulty calibration and real-world representativeness of the generated families.
- **Not established:** That protocol-heldout repository fixtures are unseen; that generated qualification cases predict model specialization gains.
- **Not evaluated:** Any model candidate, optimizer, workflow search, router, cascade, or blind-set result.
