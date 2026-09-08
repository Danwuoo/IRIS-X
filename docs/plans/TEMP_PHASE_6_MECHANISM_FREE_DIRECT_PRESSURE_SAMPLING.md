# TEMP Phase 6 — Mechanism-Free Direct Pressure Sampling and Predicate Provenance

Status: **Retired — Phase 6 Batch 2 closed as Result C; see Section 34**
Date: **2026-09-08 Asia/Taipei**  
Repository: **Danwuoo/IRIS-X**  
Required baseline `main`: **`a0ca60de39cc291fb9ad185d7de40cd6b4b5909d`**  
Phase: **Phase 6 — capability sufficiency and intervention-trigger research**  
Batch: **Batch 2**  
Batch goal: **collect bounded direct task-level pressure evidence under one unchanged admitted allocation, while binding every direct trigger predicate to deterministic source observations and preserving failure attribution without implementing or comparing deferred mechanisms**  
Architecture authority: **research evidence only; no new runtime architecture or mechanism claim**  
Live model/provider call ceiling: **maximum 6 total; maximum 1 per frozen task; 0 retries**  
Execution governance: **mandatory two-turn launch/collection protocol; no monitoring after launch**  
Hard terminal boundary: **STOP at the mandatory launch/collection boundary and do not start Phase 6 Batch 3 without separate owner authorization**

---

## 1. Owner authorization and research question

Phase 6 Batch 1 is closed at:

```text
a0ca60de39cc291fb9ad185d7de40cd6b4b5909d
```

Batch 1 established a bounded deterministic capability-pressure and failure-attribution instrument. It did not establish a final failure ontology and it did not trigger any deferred capability.

Batch 2 authorizes one new evidence class:

> **direct task-level pressure observations under one unchanged admitted cheaper allocation.**

The governing question is:

> Under one frozen admitted cheaper allocation and deterministic task/evidence semantics, does a bounded semantic pressure sample reveal any real fixed-configuration task shortfall, and can every resulting direct trigger predicate be deterministically traced to immutable source observations without conflating admission, identity, verifier, or provider failures with capability pressure?

A valid result may be that no pressure is observed. Do not design tasks merely to force failure.

---

## 2. Required authority and preserved evidence

Read and preserve at least:

```text
AGENTS.md
research/AGENTS.md
experiments/AGENTS.md
research/problem-definition.md
research/phase-5-architecture-consolidation.md
research/phase-5-capability-trigger-review.md
research/phase-6-capability-pressure-and-failure-attribution.md
docs/phase-5-architecture-state.md
docs/phase-5-architecture-consolidation-handoff.md
docs/phase-5-model-execution-admission-handoff.md
docs/phase-5-model-task-family-qualification-handoff.md
docs/phase-6-capability-pressure-attribution-handoff.md
docs/plans/TEMP_PHASE_5_ARCHITECTURE_CONSOLIDATION_AND_TRIGGER_REVIEW.md
experiments/capability-pressure-attribution-v0/
experiments/substrates/model-execution-qualification-v0/
irisx/core/records.py
irisx/core/interfaces.py
irisx/core/execution.py
```

The Phase 6 research spine remains:

```text
RQ1 — Sufficient capability
RQ5 — Failure attribution and intervention
```

Batch 2 must preserve:

```text
observation != attribution
attribution != intervention
intervention != trigger
synthetic trigger-positive != direct-evidence trigger
failure != retry requirement
heterogeneous tasks != routing requirement
```

---

## 3. Batch 1 review refinements become Batch 2 requirements

### 3.1 Negative controls are not vetoes

A negative control means a named surface fact is **not sufficient by itself** to trigger a capability.

It does not mean the presence of that fact can override separately established direct positive predicates.

Batch 2 direct-evidence assessment must therefore:

- record surface-only observations separately;
- derive required positive predicates independently;
- never implement `any negative control => forced not_triggered`;
- convert genuine contradictions into `Conflicting evidence` or `insufficient_or_ambiguous`.

Do not rewrite the frozen Batch 1 evaluator to change its historical result.

### 3.2 Direct predicate provenance is mandatory

Every direct-evidence predicate must bind to:

1. a frozen derivation rule;
2. immutable source artifact(s);
3. exact source SHA-256 identities;
4. machine-addressable source location(s), e.g. JSON Pointer / field path where practical;
5. observed value(s) or deterministic reduction;
6. deterministic predicate result: `true`, `false`, `unknown`, or `conflicting`.

Manual Boolean injection after reading the run is prohibited.

If a predicate is not deterministically derivable, preserve `unknown` / `Not established`.

---

## 4. Hard boundaries

Do not modify:

```text
irisx/core/
sources/
references/papers/
experiments/capability-pressure-attribution-v0/
historical Phase 4/5 evidence and run artifacts
```

Do not implement or enable:

```text
automated specialization
dynamic workflow machinery/search
cascade/escalation
feature-based routing/allocation
runtime persistence
nondeterministic verifier/model judge
external or irreversible actions
general recovery/retry
```

Do not add a broad external framework dependency.

Batch 2 concepts remain experiment/research-local.

---

## 5. Required starting state

Before substantive edits:

1. inspect:

   ```text
   git status --short
   git rev-parse HEAD
   git rev-parse main
   git rev-parse origin/main
   git rev-list --left-right --count origin/main...main
   ```

2. require a clean tree;
3. require actual start to be exactly, or a clean owner-authorized descendant of:

   ```text
   a0ca60de39cc291fb9ad185d7de40cd6b4b5909d
   ```

4. run `python tools/repository_check.py`;
5. verify the known historical Phase 4 frozen-plan hash failure remains the only known baseline full-suite failure;
6. verify Batch 1 evidence and Phase 5 admission/model-execution evidence are intact.

If preservation materially conflicts, STOP.

---

## 6. Fixed experimental allocation

Use only the exact currently qualified profile, subject to current admission:

```text
execution surface: codex-cli
required version: codex-cli 0.147.0
admission profile: codex-cli-0.147.0-run-03-admission-v0
provider: openai
provider slot: irisx_openai_no_retry
model role: cheaper
model: gpt-5.6-luna
reasoning effort: medium
authentication: ChatGPT
billing: ChatGPT subscription
API-key fallback: prohibited
HTTP request retries: 0
stream reconnect retries: 0
WebSocket transport: disabled
sandbox: read-only
approval: never
model tools: disabled
routes: 0
fallbacks: 0
escalations: 0
recovery actions: 0
```

Historical profile path:

```text
experiments/substrates/model-execution-qualification-v0/
  admission/codex-cli-0.147.0-run-03-profile.json
```

Do not edit its historical `model_calls_authorized: false`. This Batch 2 plan supplies the separate owner authorization for these bounded calls.

Before launch, the existing zero-model-call admission check must return `admitted`.

If not admitted: consume 0 live calls, record Result C, and STOP live execution.

---

## 7. Live call budget

```text
P1 <= 1
P2 <= 1
P3 <= 1
P4 <= 1
P5 <= 1
P6 <= 1
batch total <= 6

retries = 0
routes = 0
fallbacks = 0
escalations = 0
recovery actions = 0
alternate allocations = 0
stronger-model comparisons = 0
model judges = 0
model tool calls = 0
external actions = 0
```

A semantic miss is never retried.

---

## 8. Pressure-sample design principles

All six tasks must be:

- local-input only;
- read-only;
- tool-free;
- structured-output;
- bounded in context size;
- exactly deterministically verifiable;
- independently frozen;
- independent of human/model judging;
- free of hidden oracle data in prompts.

Pressure must come from semantic composition, not malformed instructions, huge contexts, ambiguous contracts, provider stress, token starvation, or trick schemas.

---

## 9. Six required pressure tasks

### P1 — Multi-constraint set selection

- 12–20 records;
- >=4 inclusion/exclusion constraints;
- explicit disqualifying condition;
- exact membership and deterministic ordering.

Expected output shape:

```json
{"selected_ids":["..."]}
```

### P2 — Multi-group exact aggregation

- 12–20 records;
- >=3 groups;
- multiple filtering conditions;
- exact integer or integer-cent arithmetic;
- >=2 aggregate fields such as count/total/min/max.

### P3 — Constrained multi-key ranking

- 10–18 candidates;
- eligibility filter;
- primary score plus >=2 deterministic tie-break keys;
- exact top-N rank assignment.

### P4 — Dependency closure

- DAG with ~10–16 nodes;
- transitive prerequisites;
- shared prerequisite;
- branch depth >=3;
- deterministic topological order with explicit tie-break.

Do not introduce cycles; cycle handling is not the decision variable.

### P5 — Deterministic record reconciliation

- two local record sets;
- exact IDs/reference keys;
- integer-cent amounts;
- explicit duplicate/repeated-reference rule;
- matched + mismatch/unmatched output categories.

### P6 — Ordered rule precedence

- 8–14 records;
- >=5 deterministic rules;
- >=2 records where multiple rules match and precedence decides;
- exact class plus exact rule/reason ID.

Each task must have task-local schema, oracle/verifier, negative fixtures, and immutable identity.

---

## 10. Frozen descriptive task-feature manifest

Before launch, freeze for every task:

```text
task_id
semantic_family
input_bytes
record_count
rule_count
join_required
multi_hop_dependency_required
exact_arithmetic_required
ordering_key_count
precedence_depth
expected_output_cardinality
deterministic_oracle_id
```

These are descriptive only. Do not train a classifier, router, learned predictor, or feature policy.

Six samples are not enough for a general feature-performance claim.

---

## 11. Preferred repository structure

Create a new Batch 2 experiment surface, preferably:

```text
experiments/phase-6-pressure-sampling-v0/
    README.md
    definition/
        sample-manifest.json
        task-feature-schema.json
        direct-predicate-schema.json
        predicate-derivation-rules.json
        launch-policy.json
    tasks/
        p1-selection/
        p2-aggregation/
        p3-ranking/
        p4-dependency/
        p5-reconciliation/
        p6-rule-precedence/
    fixtures/
        verifier-negative-outputs/
    scripts/
        validate_definitions.py
        pressure_tasks.py
        prepare_launch.py
        run_pressure_batch.py
        collect_pressure_batch.py
        derive_direct_predicates.py
        summarize_pressure.py
    tests/
    runs/
        batch-2/
```

After collection create:

```text
research/phase-6-direct-pressure-sampling.md
docs/phase-6-direct-pressure-sampling-handoff.md
```

A smaller equivalent shape is allowed if definition, raw evidence, verification, predicate derivation, summary, and interpretation remain separate.

---

## 12. Direct predicate provenance record

Each direct predicate must preserve fields equivalent to:

```text
predicate_record_id
gate_id
predicate_id
predicate_value            # true | false | unknown | conflicting
evidence_class             # direct_repository_evidence
derivation_rule_id
derivation_rule_sha256
source_refs[]
  path
  sha256
  pointer_or_field
  observed_value
derivation_status
derivation_notes
```

Frozen derivation rules must exist before live execution.

Required chain:

```text
immutable terminal/verifier/resource observations
    -> frozen derivation rule
    -> predicate value
    -> provenance-bound predicate record
```

Do not permit:

```text
read run manually -> type direct Boolean -> call it direct evidence
```

---

## 13. Failure attribution predeclaration

Freeze this decision logic before launch.

### Admission rejection

```text
failure_stage: admission_configuration
task-level semantic pressure: not observed
model capability failure: Not established
calls: 0
```

### Identity/definition/binding failure

```text
failure_stage: identity_authority / definition_integrity
task-level semantic pressure: not observed
model capability failure: Not established
```

### Provider/systemic failure

Examples: auth/config rejection, provider startup failure, forbidden tool exposure, sandbox drift, unexpected retry/route/fallback, unusable result before semantic verification.

```text
failure_stage: systemic_execution_failure
task-level semantic pressure: Not established
model capability failure: Not established
retry requirement: Not established
```

STOP remaining calls.

### Verifier integrity failure

If the verifier/oracle fails frozen golden/negative integrity tests:

```text
failure_stage: verification
task-level semantic pressure: Not established
model capability failure: Not established
```

STOP interpretation.

### Valid semantic miss

A task-level semantic miss requires all of:

```text
admission = admitted
identity/binding valid
one authorized model invocation
usable output exists
no forbidden tool/action/retry/route/escalation
verifier integrity valid
deterministic verifier rejects task semantics
evidence binding sufficient
```

Then record:

```text
task_level_pressure_observed: true
shortfall_axis: task_success
failure_locus: execution_producer
frozen_configuration_shortfall: directly_supported
model_intrinsic_capability_failure: Not established
retry_benefit: Not established
stronger_allocation_benefit: Not established
routing_benefit: Not established
```

`execution_producer` is a bounded locus, not proof that model weights are the causal source.

### Verified success

```text
task_level_pressure_observed: false
verified_success: true
```

Do not infer broad capability.

---

## 14. Gate-specific Batch 2 interpretation

Batch 2 deliberately does not compare mechanisms.

### H-G1

Six manually frozen tasks do not prove automated specialization is needed.

### H-W1

A semantic miss does not prove control-flow insufficiency. No workflow alternative is compared.

### H-C1

If a valid semantic miss occurs:

```text
cheaper_admitted_configuration_misses_requirement = true
```

But Batch 2 does not run a stronger candidate, so stronger resolution and trade-off predicates remain `unknown`.

### H-R1

Semantic feature heterogeneity may be true, but:

```text
multiple_admissible_allocations_compared = false
feature_dependent_allocation_changes_target_frontier = false
```

No routing trigger may be claimed.

### Persistence

All tasks are single-run/read-only. No persistence requirement exists.

### Nondeterministic verifier/model judge

All tasks require deterministic oracles. If the oracle/verifier is insufficient, classify a verifier/design conflict; do not add a judge.

### External action

All tasks are local/read-only.

### General recovery/retry

A semantic miss does not establish retry benefit. No recovery action is compared.

If any gate unexpectedly produces `triggered_by_direct_evidence`, preserve the evidence and STOP for owner review before mechanism work.

---

## 15. Definition/code freeze

Before any live launch, freeze and commit:

- six task contracts/inputs/schemas/programs;
- six deterministic oracles/verifiers;
- task-feature manifest;
- direct-predicate schema;
- predicate derivation rules;
- failure-attribution decision table;
- negative-control application policy;
- launch policy;
- batch runner and collection tooling;
- verifier negative fixtures;
- focused tests.

Record one full **definition/code freeze SHA**.

After freeze, executable definitions/code must remain byte-identical through the live run.

If code must change after observing a live result, preserve the failed run and require new owner-visible authorization rather than silently refreezing.

---

## 16. Required pre-launch deterministic validation

### Definition integrity

Validate unique task IDs and exact contract/program/input/schema/oracle hashes, exact profile identity, bounded input size, no oracle leakage, and zero retry/route/escalation policy.

### Oracle/verifier corpus

For every task require:

- exact correct fixture passes;
- malformed JSON rejects;
- schema invalid rejects;
- schema-valid semantic error rejects;
- missing result rejects;
- extra result rejects where forbidden;
- wrong ordering rejects where relevant;
- task-specific adversarial negatives reject.

### Cross-task authority

At minimum crossed task outputs/schemas/program identities must reject.

### Predicate provenance

Test:

- direct evidence without source refs rejects;
- source SHA mismatch rejects;
- bad pointer/field rejects;
- derivation-rule SHA mismatch rejects;
- manual Boolean override rejects;
- missing source observation -> `unknown`;
- conflicting observations -> `conflicting`;
- synthetic evidence cannot masquerade as direct evidence.

### Negative-control semantics

Test:

- a surface negative control does not trigger by itself;
- it does not veto separately proven required positives;
- real contradiction becomes conflicting/ambiguous rather than silently `not_triggered`.

### Regression

Require:

- Batch 1 frozen tests pass unchanged;
- Phase 5 model-qualification tests pass unchanged;
- repository check passes;
- full discovered inventory has zero new failures/errors.

Preserve the known historical Phase 4 hash mismatch unchanged.

---

## 17. Admission snapshot before launch

After freeze and validation:

1. run the existing Batch 5 zero-call admission checker;
2. require `admitted`;
3. preserve/hash-bind a Batch 2 admission snapshot/reference;
4. record profile ID/hash, admission record path/hash, CLI version/path, configuration ID, model, reasoning effort;
5. prepare a launch manifest.

If admission rejects, use Result C with 0 live calls and STOP live execution.

---

## 18. Mandatory two-turn execution protocol

The owner-directed Phase 5 no-monitoring procedure is mandatory.

### TURN A — launch only

TURN A may:

1. complete implementation;
2. freeze/commit definitions/code;
3. validate deterministically;
4. run admission;
5. commit launch-ready metadata;
6. verify clean tree;
7. launch **one background batch-runner process**;
8. redirect runner stdout/stderr and temporary raw model outputs to an external staging directory outside the repository;
9. record PID, launch timestamp, freeze SHA, staging paths;
10. perform exactly one immediate launch confirmation;
11. **STOP**.

Even if the process already exited at the single immediate check, do not inspect output.

### Fixed background runner

The runner may execute P1–P6 sequentially using frozen definitions.

It may:

- invoke each task once at most;
- stop remaining tasks on systemic/safety failure;
- continue after a semantic task miss;
- write factual raw execution data to external staging.

It must not:

- retry;
- route/fallback/escalate;
- repair prompts;
- modify definitions;
- choose tasks dynamically;
- use a stronger model;
- invoke model tools;
- write final evidence into the repository during TURN A.

### No monitoring after launch

TURN A must not:

- poll process state;
- wait;
- sleep/recheck;
- tail logs;
- inspect staging files;
- inspect task completion markers;
- infer results;
- collect partial evidence.

### TURN B — owner-requested collection

Only after explicit owner follow-up:

1. check process completion once;
2. if still running, report only that fact and STOP;
3. if complete, copy/preserve external staging evidence into immutable run directories;
4. hash raw evidence;
5. verify/adjudicate;
6. derive provenance-bound direct predicates;
7. produce summary;
8. validate;
9. author research result + durable handoff;
10. commit evidence;
11. retire this plan;
12. push normally;
13. report final synchronization.

No new model calls are authorized in TURN B.

---

## 19. External staging requirements

Before launch, commit paths/identities for:

```text
runner_stdout_path
runner_stderr_path
staging_root
per_task_raw_output_path
per_task_provider_events_path
per_task_provider_stderr_path
```

Do not store secrets.

At collection, preserve the required raw evidence into immutable repository run artifacts with SHA-256 identities.

---

## 20. Per-task collected artifacts

For each attempted task preserve at least:

```text
attempt-start.json
provider-events.jsonl
provider-stderr.txt
raw-output.txt
resource-record.json
verification-record.json
terminal-record.json
predicate-source-map.json
run-manifest.json
interpretation.json
```

Record task identity, feature manifest identity, contract/program/input/schema/oracle hashes, freeze SHA, admission hashes, provider/model identity, verifier result, state hashes where applicable, changed paths, and exact resource counts.

---

## 21. Resource invariants

Per attempted task:

```text
model_calls = 1 iff the committed model invocation boundary is crossed
retry_count = 0
route_count = 0
fallback_count = 0
escalation_count = 0
recovery_count = 0
tool_calls = 0
```

Batch:

```text
total_model_calls <= 6
total_model_calls = sum(per-task model_calls)
```

Record network/transport count and provider cost as `Unknown` if not directly observed.

Do not infer subscription cost from API pricing.

---

## 22. Derived direct-pressure summary

After collection summarize at least:

```text
authorized_task_count
attempted_task_count
verified_success_count
semantic_miss_count
systemic_failure_count
identity_failure_count
verifier_integrity_failure_count
unresolved_count
total_model_calls
total_retries
total_routes
total_fallbacks
total_escalations
total_recovery_actions
total_tool_calls
task_level_pressure_observed
pressure_task_ids
direct_predicates_true
direct_predicates_false
direct_predicates_unknown
direct_predicates_conflicting
direct_trigger_results_by_gate
```

The summary is derived only. Per-task evidence and predicate provenance remain authoritative.

---

## 23. Result categories

### Result A — No direct task-level pressure observed

Use if all six authorized semantic evaluations complete authoritatively with 0 semantic misses and no evidence/provenance conflict.

Allowed conclusion:

> The fixed admitted cheaper allocation satisfied this bounded six-task pressure sample with no observed task-level semantic miss. This does not establish broad sufficiency, but it supplies direct evidence against immediate architecture expansion for the sampled tasks.

### Result B — Direct task-level pressure observed; no mechanism triggered

Use if >=1 valid semantic miss occurs, verifier/evidence authority remains valid, and no deferred gate is fully satisfied.

Allowed conclusion:

> The fixed admitted allocation exhibited bounded direct task-level pressure on specific frozen task instances. The result establishes a fixed-configuration shortfall but not model-intrinsic causality or a justified retry/routing/escalation mechanism.

### Result C — Sampling not semantically interpretable

Use for admission, identity, systemic provider, verifier-integrity, or required-evidence failure.

Do not reinterpret as model failure.

### Result D — Provenance / authority conflict

Use for source hash mismatch, contradictory predicate derivation, invalid negative-control application, or an unexpected direct trigger that cannot be validated.

STOP architecture interpretation.

---

## 24. Live stop rules

Stop remaining live tasks after:

- admission contradiction;
- auth/config/provider systemic failure;
- tool exposure/invocation;
- sandbox mutation/drift;
- unexpected retry/route/fallback/escalation;
- API-key fallback;
- model/profile drift;
- executable-definition hash drift;
- cross-task identity/evidence contamination.

A semantic task miss may continue to the next independently frozen task.

Never retry a semantic miss.

---

## 25. Post-collection validation

Require:

1. collected source hashes match manifests;
2. freeze bytes match the freeze commit;
3. admission source is unchanged;
4. per-task and batch call ledgers reconcile;
5. direct predicate derivation regenerates byte-identically;
6. every direct predicate has provenance;
7. negative controls do not act as unconditional vetoes;
8. Batch 1 frozen evidence remains unchanged;
9. Batch 1 tests pass;
10. Phase 5 model-qualification tests pass;
11. repository check passes;
12. full inventory has zero new failures/errors;
13. `sources/`, `references/papers/`, and `irisx/core/` remain unchanged.

---

## 26. Required research result

Create after TURN B collection:

```text
research/phase-6-direct-pressure-sampling.md
```

Separate:

- source-stated authority;
- directly observed Batch 2 evidence;
- inference;
- `Unknown` / `Not established`.

At minimum preserve as not established unless directly evaluated:

```text
model-intrinsic causal failure
retry benefit
stronger allocation benefit
routing benefit
workflow benefit
generalization beyond six tasks
long-term reliability
lifecycle-cost superiority
```

---

## 27. Required durable handoff

After TURN B create:

```text
docs/phase-6-direct-pressure-sampling-handoff.md
```

Record:

- start SHA;
- definition/code freeze SHA;
- launch-ready commit;
- launch metadata;
- collection/evidence commit;
- result commit;
- authorized/actual calls;
- all six task outcomes;
- semantic miss count;
- direct predicate status by gate;
- ambiguity/conflicts;
- validation/preservation results;
- exact next recommendation;
- unsupported conclusions.

Do not author final closure during TURN A as if the run were complete.

---

## 28. Commit discipline

Preferred lifecycle:

```text
activate controlling plan -> commit
research/experiment definition -> commit
six tasks + verifiers + derivation rules -> commit
focused tests + deterministic validation -> commit
definition/code freeze -> commit
admission + launch-ready manifest -> commit
TURN A background launch -> immediate confirmation -> STOP
TURN B collection -> preserve raw evidence -> commit
derive predicates + summary -> commit
research result -> commit
durable handoff -> commit
retire controlling plan -> commit
normal push -> final report
```

Do not amend, rebase, squash, or force-push evidence lineage.

---

## 29. No architecture-by-small-sample

Six task instances do not establish a population failure rate, general capability frontier, routing advantage, operational reliability, model superiority, or production readiness.

If 6/6 pass, report exactly that this sample did not expose insufficiency.

If some fail, report bounded fixed-configuration shortfall on those exact instances.

---

## 30. Next-step logic

### Result A

Do not expand architecture. Either broaden bounded pressure coverage under the same allocation or justify a different pressure dimension.

### Result B

Do not immediately implement routing/retry/escalation. Identify the smallest missing trigger predicate and design a separate decision experiment.

Example: if H-C1 is missing stronger-candidate resolution/trade-off evidence, propose a separately authorized two-allocation comparison on the exact failed frozen tasks. Do not mix retry into that comparison.

### Result C

Repair the non-semantic sampling path under separate owner-visible scope before capability claims.

### Result D

Resolve research-instrument authority/provenance before more live work.

---

## 31. Explicitly prohibited conclusions

Batch 2 cannot establish by itself:

- final minimum-sufficient architecture;
- final failure ontology;
- general causal diagnosis;
- routing necessity;
- retry/recovery necessity;
- cascade/escalation value;
- workflow value;
- persistence value;
- model-judge value;
- specialization value;
- external-action design;
- general model capability;
- provider portability;
- production reliability;
- lifecycle-cost optimum.

---

## 32. Completion checklist

- [ ] baseline and preservation verified;
- [ ] six tasks frozen;
- [ ] deterministic oracles/verifiers frozen;
- [ ] task-feature manifest frozen;
- [ ] predicate derivation rules frozen;
- [ ] negative-control non-veto tests pass;
- [ ] provenance tests pass;
- [ ] definition/code freeze recorded;
- [ ] current admission passed or Result C recorded with 0 calls;
- [ ] TURN A launch-only/no-monitoring protocol followed;
- [ ] TURN B occurred only after owner request;
- [ ] live calls <= 6;
- [ ] retry/route/fallback/escalation/recovery/tools = 0;
- [ ] raw evidence preserved immutably;
- [ ] predicates regenerate deterministically;
- [ ] exact task outcomes reported;
- [ ] no unsupported mechanism trigger claim;
- [ ] Batch 1 evidence unchanged;
- [ ] `irisx/core`, sources, papers, historical evidence unchanged;
- [ ] zero new test failures/errors;
- [ ] research result authored;
- [ ] durable handoff authored;
- [ ] plan retired;
- [ ] normal push complete;
- [ ] Phase 6 Batch 3 not started.

---

## 33. Hard terminal instruction

This plan authorizes **Phase 6 Batch 2 only**.

During the first execution invocation, if the live-run path is reached:

> **TURN A must STOP immediately after the one allowed background-launch confirmation.**

Do not monitor or collect.

A later explicit owner request is required for TURN B.

After Batch 2 eventually completes and is pushed:

> **STOP. Do not start a stronger-allocation comparison, retry experiment, routing experiment, workflow experiment, or Phase 6 Batch 3 without separate owner authorization.**

---

## 34. Retirement record — 2026-09-08 Asia/Taipei

Phase 6 Batch 2 completed its authorized TURN A/TURN B lifecycle and is
retired as:

> **Result C — Sampling not semantically interpretable.**

The original runner produced three verified successes, then P4 failed at the
provider response-format schema boundary because `uniqueItems` was reported as
not permitted. No P4 raw model result existed, and the fixed systemic-stop
policy left P5 and P6 unattempted. No task was retried, rerun, repaired, or
replaced. The available staging bytes were preserved exactly, including the
explicit missing-output evidence.

Actual lifecycle lineage:

| Purpose | Commit |
| --- | --- |
| Required Batch 2 baseline | `a0ca60de39cc291fb9ad185d7de40cd6b4b5909d` |
| Activate controlling plan | `08547ecbfea2646548efdc6d7c15519ca8af0776` |
| Definition/code freeze | `ba7ef9964d268d1342d7cec02beedd5563c0136a` |
| Admission and launch-ready metadata | `cacdb53105f8b2d378e618d8ac785eac4501c1c1` |
| Preserve immutable TURN A staging evidence | `3e240434a72b9fe48d0456ad039d91048169a5d4` |
| Validate and adjudicate pressure observations | `7340167a466ce013a96bf2b0cb1834cca73ed863` |
| Record Batch 2 research result | `a7adb31e2c4fa44bdf26f050f4e32453c9540b77` |
| Record durable handoff | `11d0ca86ed39b46484d56d9c5bd6f7e2d530de5d` |
| Retire controlling plan | this normal commit; full SHA is reported in the owner-facing final response |

Resource and terminal result:

```text
authorized logical model-call ceiling: 6
actual logical model-call boundaries crossed: 4
completed usable provider/model results: 3
verified successes: 3/6
semantic misses: 0
systemic failures: 1
incomplete/not attempted: 2
retry / route / fallback / escalation / recovery / tool counts: 0 / 0 / 0 / 0 / 0 / 0
```

No capability gate became `triggered_by_direct_evidence`. H-C1 and general
recovery/retry remain `insufficient_or_ambiguous` because required task or
comparison observations are absent; every other gate is `not_triggered`.

Validation passed for freeze and admission integrity, 38-file staging hash
preservation, P1–P3 exact semantic re-verification, predicate provenance,
byte-identical derived regeneration, Batch 2 focused tests (27/27), Phase 6
Batch 1 tests (35/35), Phase 5 model qualification/task-family tests (75/75),
and repository validation. The full inventory ran 258 tests: 257 passed, the
one unchanged historical Phase 4 hash assertion failed, and zero errors or new
failures occurred.

The exact next recommendation is separately owner-authorized repair and
requalification of only the non-semantic sampling path: deterministically
cover provider response-schema admissibility and make missing-output systemic
evidence collectable without fabricating a raw answer. This retirement does
not authorize a rerun, mechanism experiment, use of expired Batch 2 allowance,
or Phase 6 Batch 3.

**Phase 6 Batch 3: NOT started.**
