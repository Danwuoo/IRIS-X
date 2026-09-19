# P2 ARC-AGI-2 Trial 001 Temporary Development Plan

Status: temporary implementation plan, not product authority

Date: 2026-09-18

Authority: Decision 0004 remains product authority outside the narrow venue,
transport, and frozen-model changes made by Decision 0005. This document
sequences implementation work and must not reinterpret, broaden, or replace
either decision. Where this temporary plan says repository-host execution or
an unselected model, Decision 0005 controls.

## Current task authorization

The owner has authorized broad implementation of the admitted P2 ARC-AGI-2
Engineering Trial, with the following additional task-level permission:

- Codex may deliberately acquire the official `arcprize/ARC-AGI-2` source and
  public data at commit `f3283f727488ad98fe575ea6a5ac981e4a188e49` for source
  materialization and offline validation.
- Raw upstream data and generated local outputs remain under `.irisx/` and out
  of Git unless a later review explicitly promotes an authorized artifact.
- The implementation should deliver as much of the complete P2 flow as is
  possible without selecting, downloading, binding, or executing a real model
  or solver.

This authorization does not permit a real ARC model/solver trial run. It does
not permit third-party ARC data, external providers, networked trial execution,
paid execution, P3/P4 work, or a production runtime.

## Objective

Deliver a Decision-0004-compliant ARC-AGI-2 Trial 001 repository path that can:

1. deliberately materialize the pinned official source;
2. verify exact repository, commit, split, file, and digest identity;
3. construct isolated solver-facing and evaluator-only views;
4. materialize the existing P1 contract graph with real official evidence;
5. validate ARC grids and deterministic pass@2 semantics offline;
6. build and validate the minimal training-derived `prompts_programs`
   specialization artifact;
7. preflight model-independent and execution-envelope gates;
8. fail closed on the missing real model/solver binding and missing separate
   owner run authorization;
9. validate future results, recompute generic selection, apply the P2
   five-percentage-point acceptance gate, and verify package eligibility; and
10. preserve all existing P0, P1, and historical P2-admission behavior.

## Non-goals and hard stops

- Do not select, recommend, download, synthesize, or execute a model or solver.
- Do not execute the real Trial 001 workload, even with a locally discovered
  model.
- Do not use ARC data from any repository or source other than the pinned
  official upstream.
- Do not expose evaluation expected outputs, expected-output digests, scores,
  or case feedback to the solver or specialization builder.
- Do not add fine-tuning, weight training, retrieval, tools, workflow search,
  routing, ensembles, extra attempt budget, external models, or provider SDKs.
- Do not change the generic P1 selection semantics.
- Do not modify Decisions 0001-0003, `PRODUCT_THESIS.md`, or the historical
  `trials/p2-admission/admission.json` snapshot.
- Do not introduce a new core contract schema unless the existing contracts are
  proven insufficient. Stop and report that discrepancy before a schema change.
- If official scoring semantics materially conflict with Decision 0004, stop
  and report the exact conflict rather than choosing a new interpretation.

## Required invariants

- Official upstream: `arcprize/ARC-AGI-2`.
- Pinned commit: `f3283f727488ad98fe575ea6a5ac981e4a188e49`.
- Specialization input: official public training split only.
- Frozen evaluation: complete official public evaluation split only.
- Workload: exactly 120 task-level cases, `frozen: true`, stable segment
  `public_eval` unless the official source supplies a stronger authoritative
  segmentation.
- Evaluation: exactly two predictions for every test input, exact dimensions,
  exact cells, no partial credit, deterministic aggregation.
- Baseline and candidate: the same model/solver reference, execution envelope,
  validation, limits, and controls. The only permitted difference is the
  versioned `prompts_programs` specialization component.
- External network/provider calls during trial execution: zero.
- External paid cost: USD 0.
- Successful P2 acceptance: every hard requirement passes and candidate ARC
  score minus baseline ARC score is at least `0.05` absolute.
- A positive result below `0.05` is retained as valid evidence but is not P2
  accepted and cannot produce an eligible Domain Package.

## Recommended repository surface

Keep the implementation profile-specific and small. The exact module split is
an engineering choice, but the expected surface is:

- `src/irisx/`: ARC-AGI-2 materialization, source validation, isolated view
  construction, scorer, artifact construction, preflight, result validation,
  P2 acceptance, and package-profile integration;
- `src/irisx/cli.py`: explicit ARC-AGI-2 commands kept separate from the P1
  fixture runner;
- `trials/first-real-domain/`: tracked README, static trial profile inputs, and
  any reviewed non-raw artifacts needed to reproduce materialization;
- `tests/`: deterministic offline positive and negative coverage using small
  synthetic ARC-shaped fixtures, never real model execution;
- `docs/`: command and evidence-flow documentation; and
- `tools/repository_check.py`: current-surface and offline-boundary checks for
  the admitted trial.

Raw source, generated contract bundles, preflight reports, future run evidence,
and packages should default to a disposable local tree such as:

```text
.irisx/arc-agi-2/trial-001/
├── source/
│   ├── upstream/             # preserved official bytes
│   └── provenance.json       # commit and per-file SHA-256 evidence
├── materialized/
│   ├── solver-cases.json     # demonstrations and test inputs only
│   ├── evaluator-truth.json  # expected outputs; evaluator-only
│   └── specialization/       # public-training-derived artifact and provenance
├── trial/                    # P1 contracts and supporting artifacts
├── preflight/                # immutable readiness evidence
├── run/                      # reserved; no real run in this authorization
└── package/                  # only future eligible evidence
```

The implementation may refine names, but it must preserve the capability and
trust boundaries above.

## Artifact flow

```text
pinned official Git checkout
  -> byte-preserving local source snapshot + provenance manifest
  -> strict public-training/public-evaluation validation
  -> solver-facing view + evaluator-only truth view
  -> DomainSpecification + WorkloadDefinition + RequirementSet
  -> evaluator definition + baseline/candidate components
  -> EngineeringTrial
  -> offline validation and preflight
  -> [blocked: real model/solver and separate run authorization]
  -> future prediction evidence
  -> EvaluationResults
  -> generic SelectionDecision
  -> P2 acceptance evidence
  -> eligible Domain Package only when all gates pass
```

## Implementation sequence

### 0. Preserve and verify the authority transition

- Begin from the supplied working tree, which contains the Decision 0004
  authority transition on top of `origin/main`.
- Preserve all pre-existing user changes; do not reset, revert, or rewrite them.
- Confirm the current repository checks pass before functional work.
- Keep Decision 0004 as the sole product authority for Trial 001.

### 1. Official source materialization

- Provide an explicit command for the fixed official repository and commit.
- It may fetch the official source because the owner has authorized that source
  acquisition, but fetching must remain structurally separate from trial
  execution and from default tests.
- Prefer a fixed upstream constant rather than an arbitrary repository argument.
- Verify remote identity, exact commit, expected split locations, required file
  set, exactly 120 public evaluation tasks, and per-file SHA-256 digests.
- Preserve upstream bytes. Derived views must be written separately and record
  their transformation provenance.
- Revalidation must reject a wrong remote, branch head, wrong commit, missing or
  extra required task, changed byte digest, stale manifest, or unsupported ARC
  source.

### 2. Evaluation-data isolation

- Treat one official evaluation task as one IRIS-X workload case.
- Each solver-facing case may contain only training demonstration inputs,
  training demonstration outputs, and test input grids.
- Store expected test outputs in a separate evaluator-only artifact.
- Never pass the WorkloadDefinition, expected refs, truth artifact, source
  manifest containing expected-output digests, or evaluator feedback to the
  solver-facing interface.
- Ensure the specialization builder receives only the official public training
  split and cannot access evaluation truth or result feedback.
- Add negative tests that capture every payload delivered to fake solver and
  specialization interfaces and prove that forbidden fields and values are
  absent.

### 3. Existing-contract materialization

- Reuse schema version `1.0` for DomainSpecification, WorkloadDefinition,
  RequirementSet, CandidateConfiguration, EngineeringTrial, EvaluationResult,
  SelectionDecision, and DomainPackageManifest.
- Use supporting-artifact envelopes for source provenance, evaluator profile,
  local model/solver descriptors, execution envelope, predictions, preflight,
  specialization derivation, and P2 acceptance. These are evidence profiles,
  not replacement core contracts.
- Build exactly 120 frozen workload cases with exact source and expected refs.
- Use ARC task identifiers as case IDs and `public_eval` as the segment unless
  the pinned official source proves a stronger segmentation.
- Define hard requirements for zero leaks, zero network/provider use, zero
  external cost, complete results, exact workload completeness, and exact
  identity bindings. Make ARC accuracy the only Trial 001 maximization
  objective. Record runtime/resources without optimizing them.

### 4. Baseline and specialization components

- Create a minimal baseline `prompts_programs` artifact containing only common
  ARC task/interface instruction and validation behavior.
- Create the smallest useful deterministic static reasoning policy or program
  derived only from the official public training split.
- Record exactly which public training files influenced it and the deterministic
  derivation procedure.
- Build baseline and candidate configurations so every component and execution
  control is identical except `prompts_programs`.
- Use an explicit unbound-state/preflight failure until the owner later supplies
  a real local model/solver descriptor. Do not create a fake production binding.

### 5. ARC pass@2 scorer and result evidence

- Validate ARC grid shape, integer cells, cell range, dimensions, and malformed
  structures before comparison.
- Require exactly two predictions for every test input and reject missing or
  hidden extra attempts.
- A task passes only under the pinned official pass@2 interpretation. Retain
  per-test attempt evidence so the task result can be independently recomputed.
- Produce task-level case outcomes compatible with EvaluationResult and
  deterministic overall/segment metrics.
- Prove with fixtures that a correct first prediction passes, a correct second
  prediction passes, neither correct fails, wrong dimensions fail, malformed
  grids fail, and extra attempts fail.

### 6. Preflight and real-run guard

- Define one immutable execution-envelope artifact containing local model/solver
  identity, hardware identity, invocation limit, attempt limit, timeout policy,
  seed/determinism policy, and output limits.
- Validate the same envelope and model/solver reference for baseline and
  candidate.
- Fail preflight when the concrete model/solver descriptor or its immutable
  digest evidence is absent.
- Detect configured provider use, provider credentials, network-enabled trial
  mode, non-zero external cost, or unsupported candidate differences and fail
  closed.
- Separate technical preflight readiness from owner run authorization. Decision
  0004 is not itself a run-authorization artifact.
- Any real-run command added during implementation must remain unreachable
  without both the missing model binding and a later explicit owner
  authorization. Do not invoke it in this task.

### 7. Selection, P2 acceptance, and package verification

- Reuse the generic P1 selection engine unchanged.
- Add a separate digest-bound P2 acceptance check that recomputes the baseline
  and candidate ARC scores and requires an absolute improvement of at least
  `0.05` plus all hard requirements.
- Retain a generic strictly-better selection below `0.05` as evidence while
  marking P2 acceptance and package eligibility false.
- Add a P2 package build/verify profile without weakening the P1 qualification
  verifier.
- Package verification must independently resolve and recompute source
  identity, prediction evidence, result metrics, hard requirements, generic
  selection, P2 acceptance, required limitations, exact references, byte
  digests, and closed-world membership.
- The P2 package must state all four limitations required by Decision 0004.
- Determine an implementation that can verify opaque local solver assets or a
  self-contained solver closure without redefining the deployment target. If
  this cannot be expressed without a contract change, stop and report it.

### 8. Documentation, tests, and repository integration

- Document materialization, offline validation, preflight, future run,
  result-validation, selection, and package-verification commands.
- Clearly label commands that acquire official source versus commands that must
  remain offline.
- Update repository navigation and validation for the tracked trial workspace.
- Keep all default test and repository-validation paths offline.
- Preserve the existing P1 fixture CLI and package semantics exactly.

## Minimum command surface

Exact spelling is an engineering choice. The completed implementation should
provide equivalents of:

```powershell
# Explicit official-source acquisition/materialization; network is allowed only here.
python -m irisx arc-agi-2 source materialize --output .irisx\arc-agi-2\trial-001\source

# Offline source and split validation.
python -m irisx arc-agi-2 source validate .irisx\arc-agi-2\trial-001\source

# Offline isolated views and contract construction.
python -m irisx arc-agi-2 trial prepare --source .irisx\arc-agi-2\trial-001\source --output .irisx\arc-agi-2\trial-001\trial

# Offline contract, isolation, identity, and scorer validation.
python -m irisx arc-agi-2 trial validate .irisx\arc-agi-2\trial-001\trial

# Offline preflight; expected to fail closed while the model/solver is unbound.
python -m irisx arc-agi-2 trial preflight .irisx\arc-agi-2\trial-001\trial

# Future-only commands; implement and test with fixtures but do not perform a real run.
python -m irisx arc-agi-2 result validate <run-directory>
python -m irisx arc-agi-2 select <run-directory>
python -m irisx arc-agi-2 package verify <package-directory>
```

If a future run command is exposed, documentation must show the exact additional
model-binding and owner-authorization prerequisites and must not imply that this
plan supplies them.

## Required tests

At minimum, add deterministic offline tests for:

- official repository and exact pinned commit acceptance;
- wrong repository, branch head, wrong commit, stale manifest, changed file,
  missing file, and incomplete or extra evaluation-task rejection;
- exact representation of 120 task-level workload cases;
- preserved raw bytes and per-file SHA-256 provenance;
- no third-party or non-allowlisted ARC source ingestion;
- strict separation of solver-facing input and evaluator-only truth;
- specialization construction receiving training material only;
- pass@2 first-success, second-success, failure, dimensions, malformed grid,
  missing attempt, and hidden extra-attempt behavior;
- baseline/candidate identity equivalence except `prompts_programs`;
- rejection of retrieval, adaptation, tools/workflow differences, ensembles,
  extra call budget, or model substitution;
- missing model/solver binding and stale model digest;
- execution-envelope mismatch;
- network/provider/credential/external-cost stop conditions;
- complete and recomputable result evidence;
- `+0.04` valid-but-unaccepted and `+0.05` accepted improvement;
- package ineligibility after any hard or P2 acceptance failure;
- stale references, digests, unexpected package files, and opaque-asset
  corruption; and
- continued success of every existing P0, P1, and historical P2-admission test.

Official source may be materialized for development, but tests must not require
network access or a pre-existing `.irisx/` snapshot. Use small synthetic
ARC-shaped test fixtures or generated fixtures for unit coverage.

## Validation before handoff

Run from the repository root:

```powershell
python tools\repository_check.py --self-test
python tools\repository_check.py
python -m unittest discover -s tests -v
git diff --check
```

Also run every new offline source-validation, trial-validation, preflight,
result-validation, selection, and package-verification command against its
deterministic fixtures. Materializing the real official source is permitted;
running a real model/solver is not.

## Definition of done for this development task

The task is complete when:

1. the pinned official source can be deliberately materialized and revalidated;
2. official training and evaluation material is strictly separated and
   provenance-bound;
3. the 120-case P1 contract graph can be materialized from official evidence;
4. the minimal specialization artifact can be deterministically built from
   public training data only;
5. pass@2 and future result evidence can be independently recomputed;
6. preflight reports the exact remaining model/solver and run-authorization
   blockers without attempting execution;
7. generic selection, P2 acceptance, and package eligibility are implemented
   and covered offline;
8. current P0/P1/P2-admission guarantees remain green; and
9. the final report lists files changed, commands, tests, downloaded official
   source identity, remaining blockers, and any contract or official-semantics
   discrepancy.

The task must stop short of model acquisition, model selection, model binding,
and real Trial 001 execution.
