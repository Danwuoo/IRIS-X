# TEMP Phase 6 — Batch 3 Sampling Path Repair and Requalification

Status: **Active — owner-authorized; TURN A repair, freeze, admission, and launch pending**  
Date: **2026-09-09 Asia/Taipei**  
Repository: **Danwuoo/IRIS-X**  
Required baseline `main`: **`07a71392a59f78e41ca32f1c9c377e2a43be41e6`**  
Phase: **Phase 6**  
Batch: **Batch 3**  
Scope: **research-local repair and requalification of the Phase 6 direct-pressure sampling path**  
Model-call ceiling: **6 invocation boundaries total; at most 1 per task; 0 retries**  
Execution governance: **mandatory owner-separated TURN A launch and TURN B collection**

## 1. Authority and question

The owner authorizes a narrow repair in
`experiments/phase-6-pressure-sampling-v0` and one fresh six-task
requalification under the exact Batch 2 admitted allocation/profile.

Batch 3 asks:

> After repairing the observed non-semantic sampling-path defects, can the
> intended six-task sample complete without a schema, configuration, systemic,
> or evidence-collection failure, and what provenance-bound direct pressure
> evidence does that one fresh run produce?

This plan does not authorize Phase 6 Batch 4 or any architecture mechanism.

## 2. Immutable preservation boundary

The following are historical authority and must remain byte-identical to the
required baseline:

- `experiments/phase-6-pressure-sampling-v0/runs/batch-2/`
- `research/phase-6-direct-pressure-sampling.md`
- `docs/phase-6-direct-pressure-sampling-handoff.md`
- `docs/plans/TEMP_PHASE_6_MECHANISM_FREE_DIRECT_PRESSURE_SAMPLING.md`

Batch 2 remains **Result C — Sampling not semantically interpretable**. Batch 3
must not rewrite, repair, complete, rerun, or reinterpret Batch 2.

Protected imported and architecture paths remain unchanged:

- `irisx/core/`
- `sources/`
- `references/papers/`
- prior Phase 4/5/6 historical run paths

## 3. Authorized repairs

Only these repairs are authorized:

1. deterministic provider response-schema admissibility validation tied to the
   admitted compatibility profile;
2. removal of P4's unsupported provider-facing `uniqueItems` constraint while
   retaining exact deterministic oracle comparison as terminal authority;
3. state-aware collection of legitimate systemic no-output evidence without
   creating or normalizing `raw-output.txt`;
4. distinct accounting for invocation-boundary crossing, directly observed
   provider acceptance, usable-result observation, and unknown model inference;
5. regression coverage for schema rejection, systemic no-output collection,
   contradictory evidence, exact-byte preservation, and Batch 2 preservation.

All changes remain research-local. No routing, fallback, escalation, recovery,
retry, alternate model, model judge, tool use, external action, persistence,
workflow machinery, or automated specialization is authorized.

## 4. Definition and execution invariants

- Allocation/profile: `codex-cli-0.147.0-run-03-admission-v0`.
- Provider slot: `irisx_openai_no_retry`.
- Model/reasoning: `gpt-5.6-luna` / `medium`.
- Sandbox: read-only; approval never; model tools disabled.
- Task order: the same six semantic task families as Batch 2.
- One invocation boundary maximum per task and six total.
- Stop immediately after a systemic or safety failure.
- Missing and not-attempted results remain evidence; never replace them.
- Provider/configuration/schema failures do not establish capability pressure.
- Exact deterministic verifier/oracle comparison remains semantic authority.

The repaired provider schema policy is a closed-world, versioned compatibility
claim for this admitted execution boundary, not a general JSON Schema or
provider-portability claim.

## 5. Accounting semantics

Each attempted task must separately record:

- `invocation_boundary_crossed`: directly observed Boolean;
- `model_call_boundaries`: 0 or 1, derived from that boundary;
- `provider_acceptance`: `true`, `false`, or `Unknown`, only when directly
  supported by provider events/results;
- `usable_result_observed`: directly observed Boolean;
- `model_inference_execution`: `Unknown` unless directly instrumented;
- retry, route, fallback, escalation, recovery, and tool counts.

Do not convert missing instrumentation into zero.

## 6. Collector contract

For every attempted task, core identity, provider-event, stderr, resource,
verification, terminal, provenance-map, and run-manifest artifacts are required.

- A non-systemic terminal requires a preserved non-empty `raw-output.txt`.
- A systemic terminal that declares `provider_output_missing` requires the raw
  output to be absent.
- A raw output contradicting a declared missing-output failure is conflicting
  evidence and must fail closed.
- A missing raw output without an explicit systemic missing-output observation
  is conflicting/incomplete evidence and must fail closed.
- All collected bytes and manifest hashes must be validated before immutable
  copy into `runs/batch-3/`.

## 7. Direct-evidence discipline

For every direct predicate preserve:

```text
predicate_id
predicate_value
evidence_class
source_path
source_sha256
observation_locator
derivation_rule
derivation_version_or_sha256
attribution_status
```

Maintain:

```text
raw observation
-> shortfall axis
-> failure-stage evidence
-> attribution status
-> candidate intervention
-> capability-trigger predicate
-> research decision
```

A semantic miss is not by itself intrinsic capability failure, retry benefit,
escalation benefit, routing benefit, or stronger-model benefit.

## 8. Required zero-call validation

Before freezing and again as applicable after TURN B collection:

1. Batch 3 focused tests and definition validation;
2. Phase 6 Batch 1 focused tests;
3. Phase 5 model qualification and task-family affected suites;
4. `python tools/repository_check.py`;
5. full discovered repository unittest inventory;
6. Batch 2 preservation comparison against the required baseline;
7. deterministic regeneration and provider-schema validation.

The known historical Phase 4 frozen-plan hash assertion must remain visible and
must not be repaired or rebaselined. Every new failure/error must be accounted
for.

## 9. Result categories

### Result A — Requalified sample complete; no direct task-level pressure

All six intended tasks produce valid, provenance-bound terminal evidence and
all six are verified successes. No capability gate is triggered.

### Result B — Requalified sample complete; direct task-level pressure observed

All six intended tasks produce valid, provenance-bound terminal evidence and at
least one task has a semantic miss. Gate status follows only from independently
satisfied provenance-bound predicates; a miss alone triggers no mechanism.

### Result C — Sampling not semantically interpretable

A schema, provider/configuration, systemic, safety, missing-evidence, or
sampling-path failure prevents completion of the intended six-task sample.
Downstream task evidence invalidated by the stop is not capability evidence.

### Result D — Provenance or authority conflict

Freeze, admission, identity, immutable-byte, derivation, or evidence bindings
conflict such that the intended inference cannot be made safely.

## 10. Mandatory two-turn lifecycle

### TURN A — repair, freeze, admit, launch, stop

TURN A must:

1. repair and test the sampling path with zero model calls;
2. commit the definition/code freeze;
3. prepare and commit Batch 3 admission and launch-ready metadata;
4. verify a clean synchronized launch-ready tree;
5. start exactly one background runner with stdout/stderr outside the repository;
6. record PID, launch timestamp, freeze SHA, launch-ready SHA, and staging paths;
7. perform exactly one immediate process/staging existence confirmation;
8. stop without polling, waiting, tailing, reading partial outputs, or collecting.

### TURN B — explicit later owner collection only

Only a later owner request may inspect runner completion, collect staged bytes,
adjudicate each task, derive direct predicates, write the Batch 3 research
result and durable handoff, retire this plan, commit, and push final closure.
TURN B authorizes no new model call, retry, rerun, or replacement.

If the runner is still active at TURN B's single initial inspection, record the
deferred collection state and stop without modifying experiment evidence or
retiring this plan.

## 11. Commit and retirement discipline

Use normal, semantic commits. Do not amend, squash, rebase, reset, force-push,
or overwrite immutable paths. The definition/code freeze must precede launch
metadata. Batch 3 run evidence belongs only under `runs/batch-3/`.

Retire this plan only after TURN B has completed collection, preservation,
adjudication, validation, research result, durable handoff, and normal push.
The retirement record must contain actual lifecycle commit lineage and must
state: **Phase 6 Batch 4: NOT started.**

## 12. Current lifecycle record

| Purpose | Commit |
| --- | --- |
| Required Batch 3 baseline | `07a71392a59f78e41ca32f1c9c377e2a43be41e6` |
| Activate controlling plan | Pending |
| Definition/code freeze | Pending |
| Admission and launch-ready metadata | Pending |
| TURN A launch identity | Pending |
| TURN B evidence collection | Pending |
| Research result | Pending |
| Durable handoff | Pending |
| Retirement | Pending |

**Phase 6 Batch 4: NOT authorized.**
