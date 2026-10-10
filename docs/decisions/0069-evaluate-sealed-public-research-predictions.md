# Decision 0069: Evaluate sealed public research predictions

Date: 2026-10-10. Status: accepted owner scope; source and CPU review passed; provider execution pending.

## Owner direction

The owner requested Astra ultra to plan, develop and test the next step, move
the project's ARC-AGI-2 public scorer to the private Kaggle research workflow,
explicitly distinguish these predictions from competition GPU inference, and
push Git and Kaggle. The exact message is Sentinel_73529baff3ac8191a215f3cb5d5463f2.
The owner previously chose native internal threads for this work.

## Narrow boundary change

This decision permits the pinned, already-public ARC-AGI-2 evaluation data and
unchanged project scorer in a separate private, versioned research Dataset and
manual notebook. A trusted data-only preparer verifies the exact public source
and strips every test output from solver assets. Original public answers remain
in the evaluator role. No hidden, private or competition answers are authorized.
No answers may enter prompts, ranking, selection or model processes.

Only after query predictions and their fresh verification proofs are frozen,
model ownership is closed with process evidence, and an exact prediction
inventory is sealed may a separate CPU process read public answers. Results
must not influence generation or selection in that run. This is a trusted-code
and dataflow barrier, not a claim of hostile same-UID filesystem isolation.
The old local-evaluator policy otherwise remains in force.

## Frozen research profile

PUBLIC120 uses the project's pinned 120-task, 167-test upstream evaluation
reference at f3283f727488ad98fe575ea6a5ac981e4a188e49. Completeness and license
are checked against that reference; prior public development exposure is
explicit and no fresh holdout claim is made. Reuse the unchanged solver-neutral
project scorer, its exact grid/schema checks and full denominators. Do not
substitute the separate NVARC 172-test variant.

The raw and native-token-trie arms each make at most one call per task, sharing
the same frozen 5965-plan support, prompt, seed and sampling. This is finite-pool
selection and format reliability, not unrestricted program synthesis. Two
CPU ranking arms, uniform and shape_palette_v1, each verify 64 candidates per
task with strictly positive support. No witness injection, hard pruning, query
answer features, coverage cache or full enumeration is included.

Admission requires 128 independent synthetic controls, source/data provenance
and tokenizer/schema validation. It is a new research evaluation contract; the
old consolidated FULL witness gate is preserved unchanged. A zero-score public
run remains valid evidence if all contracts hold. Invalid, missing and
inconclusive states retain their denominators and separate diagnostics.

The bounds are 240 model calls and 17064 CPU verifier calls, including up to
1336 query executions, within a 7200-second session and four verifier workers.
Existing program gas, memory, CPU, wall, AST, grid and output limits remain.
Unknown reservations consume budget and cannot be retried silently.

## Delivery and claims

Publish reviewed code and data as independently versioned private Kaggle
Datasets, a manual default-inert private notebook, and private Git main. Preserve
existing five offline asset pins. Preserve only the owner's existing ARC3
metadata association, without reading or using competition data. All switches,
GPU, TPU and Internet are off in the save. No agent GPU execution, paid
provisioning, training, credentials changes or official submission is authorized.

Each result records model, tokenizer, adapter status, hardware, source, data,
exposure, physical costs and prediction origin. competition_gpu_equivalent is
false and official competition score is null. CPU fixtures and native-tokenizer
checks do not establish real model/GPU success. Later owner-run results are
analyzed against the exact saved version and sealed run artifacts.

## Owner-authorized existing-resource GPU run and stopping condition

The initial no-agent-GPU execution boundary above is superseded only for this
reviewed PUBLIC120 run by the owner's later explicit direction:

- Sentinel_71256fb6295c8191b93d0600aa9270ed requests direct GPU execution with the
  ARC-AGI-3 association, operational monitoring until success, repair/retry on
  error, and no result analysis after success.
- Sentinel_3b3a5c54cf3c81919a701b00017b9ba0 confirms the owner has already configured
  GCP and asks only for GPU activation and the existing ARC-AGI-3 attachment.
- Sentinel_92f8f5c59d588191b62107e80407f5ab approves resolving this round's push
  problems while the owner is away; a generic tool cancellation is not their stop.

Use only the existing configured integration and reviewed NvidiaRtxPro6000
selection, exact approved source/data and a fresh output identity. No new cloud
purchase, provisioning, credential grant, billing-plan change or competition
submission follows. ARC-AGI-3 remains metadata association only; the ARC-AGI-2
solver does not read its task data. Keep Internet off and the 7200-second program
session ceiling. Provider quota observability is not a spending or availability
claim; retain real admission errors instead of bypassing them.

First retain a private inactive source save, then a separately bound config-only
active version. Each create/update has its own durable one-shot intent and exact
readback. Never launch a replacement while an earlier owned run is active or its
write outcome is unknown. An error may be repaired and a newly reviewed source
version retried under the same scope, with prior failure evidence preserved.

Success requires the intended active version to be provider COMPLETE plus the
model phase, prediction seal, public scorer and final stopped-process closure
being operationally complete. A source renderer COMPLETE, disabled model run,
partial session or SCORING_BLOCKED is insufficient. After success, stop. Do not
interpret scientific scores, compare methods or begin a new research iteration.
