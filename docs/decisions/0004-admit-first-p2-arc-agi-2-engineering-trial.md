# Decision 0004: Admit the First P2 ARC-AGI-2 Engineering Trial

Status: Accepted

Date: 2026-09-18

## Context

Decision 0003 recorded P2 as admission-blocked until the owner selected a real
domain and workload, data authorization, baseline, specialization intervention,
evaluation and acceptance rules, execution path and budget, and deployment
target. The owner has selected the local/offline path for a first bounded
ARC-AGI-2 Engineering Trial.

This decision authorizes the minimum repository implementation needed to
materialize and safely prepare that trial. It does not authorize the real trial
run as part of the implementation task. A real run still requires a separate
explicit execution authorization and satisfaction of every preflight gate in
this decision.

Implementation begins from the then-current `origin/main` and must obey every
applicable `AGENTS.md`. It must not redesign IRIS-X architecture or introduce a
general agent framework, provider SDK, training framework, workflow framework,
or production runtime.

## Decision

The first real P2 Engineering Trial is admitted with this exact identity and
boundary:

- domain: ARC-AGI-2;
- execution path: local/offline;
- official upstream: `arcprize/ARC-AGI-2`;
- pinned upstream commit: `f3283f727488ad98fe575ea6a5ac981e4a188e49`;
- specialization material: the official public training split only;
- frozen evaluation material: the official public evaluation split only;
- prohibited material: all third-party ARC data;
- out of scope: semi-private and private ARC data;
- external provider and network execution: prohibited;
- maximum external paid-execution budget: USD 0;
- retention: through trial completion and Domain Package verification, followed
  by owner review; and
- deployment target: a self-contained, single-machine, offline ARC-AGI-2
  research solver package.

The real-trial implementation uses the existing P2 conventions and the already
reserved `trials/first-real-domain/` location unless a narrower repository rule
requires a more specific path. Its README and artifact identifiers must make
the ARC-AGI-2 identity explicit.

## Preserve existing authority and evidence

Implementation must not modify historical P0 or P1 evidence to fit P2. It must
preserve:

- `PRODUCT_THESIS.md`;
- Decisions 0001–0003;
- existing P1 provider-neutral contracts;
- P1 canonical serialization and digest semantics;
- deterministic P1 selection and package-verification behavior; and
- the existing `irisx/p2-admission` v1.0 blocked snapshot as historical
  evidence.

The old admission snapshot must not be mutated into an authorization token.

## Source materialization

The implementation must provide a deliberate source-materialization path for
the official ARC-AGI-2 repository that:

1. accepts or acquires only the approved official upstream;
2. verifies the exact pinned Git commit;
3. rejects an unpinned branch head, wrong repository, wrong commit, missing
   files, or stale snapshot;
4. records source provenance and per-file SHA-256 digests;
5. keeps raw domain data local and disposable under repository data policy
   unless separate authorization gives a reason to commit it;
6. never silently vendors or rewrites upstream ARC files; and
7. never accesses third-party ARC solution sources.

If a network fetch is supported, it must be an explicit materialization command
that is structurally separate from Engineering Trial execution. Default tests
and validation remain offline.

## Evaluation-data isolation

The public evaluation files contain evaluator ground truth. The solver-facing
case representation may contain only information legitimately available to an
ARC test taker:

- training demonstration inputs;
- training demonstration outputs; and
- test input grids.

Expected test outputs must be stored or referenced separately as evaluator-only
evidence. The baseline solver, candidate solver, specialization builder, and
normal logs must never receive expected evaluation outputs. No evaluation score
or case-level correctness feedback may flow back into specialization
construction. Negative tests must prove this boundary.

## P1 artifacts and workload

The trial must materialize real artifacts through the existing contracts rather
than parallel schemas wherever possible:

- `irisx/domain-specification`;
- `irisx/workload-definition`;
- `irisx/requirement-set`;
- `irisx/evaluator-definition`;
- a baseline `irisx/candidate-configuration`;
- a specialized `irisx/candidate-configuration`; and
- `irisx/engineering-trial`.

These artifacts must use real evidence, never the P1 qualification fixture.

The workload must contain all 120 cases in the complete official public
ARC-AGI-2 evaluation split and set `frozen: true`. Every case must have exact
source and expected references. It should use the stable segment `public_eval`
unless the official source provides a stronger authoritative segmentation; the
implementation must not invent semantic ARC categories.

## Evaluator

The evaluator artifact and scorer must implement the pinned official
ARC-AGI-2 pass@2 semantics:

- exactly two predictions for every test input;
- exact grid dimensions;
- exact cell values;
- no partial credit; and
- deterministic aggregation.

The evaluator must be versioned and digest-bound. Reference fixtures must prove
that a correct first prediction passes, a correct second prediction passes,
neither prediction correct fails, wrong dimensions fail, malformed grids fail,
and extra hidden attempts are rejected.

If official scoring semantics discovered during implementation conflict
materially with this decision, implementation must stop and report the
discrepancy rather than silently choose a new scoring interpretation.

## Baseline and candidate intervention

The baseline is one fixed local base model or solver plus minimal ARC task and
interface instruction plus common validation. It contains no specialization
derived from ARC-AGI-2 training data.

Implementation must not automatically select or download an external provider
model. A concrete locally executable model or solver artifact must be bound
explicitly before trial execution. Its reference must contain immutable
identity, version, and digest evidence, and execution preflight must fail when
that reference is absent.

Trial 001 permits exactly one specialization difference: a versioned static
ARC-AGI-2 reasoning policy or program derived solely from the official public
training split. It is represented by the existing `prompts_programs` candidate
component.

Trial 001 must not add weight training or fine-tuning, retrieval, new tools,
workflow search, routing, ensembles, additional model-call budget, or external
models. Baseline and candidate must otherwise bind the exact same model or
solver and execution controls.

The implementation should create only the smallest useful initial
specialization artifact or deterministic builder needed to exercise this
contract. It must not attempt to build an ARC state-of-the-art solver. It must
document exactly how the specialization artifact was derived and which
authorized training material influenced it.

## Requirements and metrics

The trial uses existing `RequirementSet` and `EvaluationResult` semantics. Hard
metrics must provide enough evidence to prove:

- zero evaluation-leak events;
- zero network or provider calls during trial execution;
- zero external paid cost;
- zero malformed or missing result cases;
- exact workload completeness; and
- exact identity binding.

ARC accuracy is a maximization objective. Local runtime and resource
observations must also be recorded without becoming a Trial 001 optimization
target. Unavailable resource observations must not be fabricated; the existing
`observed`, `unknown`, and `not_evaluated` semantics apply.

## P2 acceptance gate

Generic P1 selection may still identify any strictly better eligible candidate.
The implementation must add the minimum trial-level P2 acceptance check needed
to distinguish a strictly better result from a successful first P2
specialization, without changing generic P1 selection semantics.

The first P2 trial is accepted only when every hard requirement passes and:

```text
candidate ARC score - baseline ARC score >= 0.05
```

If improvement is positive but less than `0.05`, the evidence is retained and
the trial is recorded as a valid negative or insufficient result. It must not
promote a successful P2 Domain Package.

## Execution envelope and run authorization

Before a real run, one immutable execution-envelope record must identify at
minimum:

- the local model or solver reference;
- hardware identity;
- model-call or solver-invocation limit;
- attempt limit;
- timeout policy;
- random-seed and determinism policy; and
- output limits.

Baseline and candidate must bind the same envelope; any difference fails
preflight. Trial execution must have network disabled or verified absent, no
provider credentials, and external spend of USD 0. Unexpected network
activity, provider use, credentials, or external cost is an immediate stop
condition.

This decision admits trial definition, source materialization, implementation,
offline validation, and preflight work. It does not itself authorize the real
model or solver run. That run requires a separate explicit owner authorization
after the concrete local model or solver and execution envelope are bound and
all preflight gates pass.

## Stop conditions

The trial must fail closed on any of the following:

- wrong or missing ARC upstream commit;
- changed source digest;
- workload mutation;
- evaluator mutation;
- missing expected-output isolation;
- evaluation feedback entering specialization;
- third-party ARC data;
- model substitution;
- baseline/candidate execution-envelope mismatch;
- network or provider activity;
- paid external execution;
- stale contract reference; or
- incomplete result evidence.

These conditions must not be repaired silently during a trial.

## Domain Package eligibility

A Domain Package may be constructed only if the candidate passes every hard
requirement, improves on the baseline by at least `0.05` absolute, result
evidence validates, deterministic selection evidence is complete, and every
package reference is exact and non-stale.

The package must state these known limitations:

- evaluation covers only the pinned public ARC-AGI-2 evaluation snapshot;
- no claim is made about semi-private or private performance;
- no ARC Prize or state-of-the-art claim is made; and
- only the first minimal specialization intervention was tested.

## Required offline tests and validation

Deterministic offline tests must cover at least:

- exact source-identity acceptance and rejection;
- workload immutability;
- representation of all 120 workload cases;
- solver/evaluator ground-truth isolation;
- pass@2 scorer behavior;
- baseline/candidate identity equivalence;
- unauthorized candidate-component differences;
- missing local model binding;
- network and external-cost stop conditions;
- a valid but unaccepted improvement below five percentage points;
- an accepted improvement of at least five percentage points;
- stale references and digests; and
- package ineligibility after failed acceptance.

Existing P0, P1, and P2-admission tests must continue to pass. Repository
validation and every new P2 trial validation command must run offline. A real
ARC model run must not be executed merely to make tests pass.

The repository's existing validation suite, including
`python tools/repository_check.py`, must be run after implementation.

## Implementation deliverable

The implementation report must return:

1. files changed;
2. the exact owner-decision artifact;
3. real-trial artifacts and validators added;
4. source-materialization commands;
5. offline-preflight commands;
6. the command that would run the real trial after authorization;
7. result-validation, selection, and package-verification commands;
8. tests executed and their results;
9. any remaining execution binding that prevents a real run; and
10. any discrepancy among this owner decision, official ARC semantics, and
    existing IRIS-X contracts.

Implementation should prefer the smallest reversible change that satisfies
these requirements.

## Consequences

- Decision 0003 and its `irisx/p2-admission` v1.0 artifact remain immutable
  historical evidence of the prior blocked state; they are not current
  execution authorization.
- P2 is no longer admission-blocked for the selected ARC-AGI-2 trial definition
  and its repository implementation, materialization, offline validation, and
  preflight work.
- Real trial execution remains gated by a separate explicit owner authorization
  and the concrete local model or solver binding and preflight evidence required
  above.
- External provider execution, networked trial execution, third-party ARC data,
  external paid execution, P3/P4 work, and production-runtime construction
  remain unauthorized.
- P0 archive identities, `PRODUCT_THESIS.md`, the P1 contract and qualification
  guarantees, and generic P1 selection semantics remain unchanged.
