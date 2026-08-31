# Temporary Phase 4 Reliability Expansion and Specialization Substrate Plan

Status: **Retired — reliability expansion and specialization substrate batch completed and validated**
Date: **2026-08-31**
Scope: reliability expansion, broader task-frame qualification, held-out governance, and model-specialization substrate preparation
Architecture authority: **None**
Planning baseline: GitHub `main` = `36de9056efaff002dcdbb15f8335fcabf261a751` when this plan was prepared
Execution model: one large plan, multiple separately frozen work packages and experiments
Hard terminal boundary: **STOP before any H-P1/H-G1/H-W1/H-C1/H-R1 model-based experiment**

Retirement record: all exit criteria were satisfied within their stated boundaries. The durable result and decision are recorded in [`research/phase-4-reliability-specialization-readiness.md`](../../research/phase-4-reliability-specialization-readiness.md). Retirement means this execution contract is complete; it does not authorize H-P1, H-G1, H-W1, H-C1, H-R1, architecture synthesis, or Phase 5.

---

## 1. Purpose

IRIS-X has completed two scoped Phase 4 mechanism batches.

Task-local support currently exists for:

- H-M1a — Registered Source Snapshot Assertion;
- H-V1a — Independent Acceptance Verification;
- H-O1a — Structured Instrumentation Completeness;
- H-V1b — Evidence / Provenance Binding;
- H-I1a — Pre-execution Write Prevention.

Those results establish narrow local constraints only. They do not establish:

- complete parent H-M1, H-V1, H-O1, or H-I1;
- broad task-family generalization;
- long-term reliability;
- lifecycle-cost sufficiency;
- model specialization gains;
- routing/cascade gains;
- workflow-search gains;
- a final architecture.

The next Phase 4 batch has two parallel goals:

1. **Expand long-term reliability research beyond short deterministic repeat agreement.**
2. **Prepare a defensible held-out evaluation substrate for later model-based specialization experiments without actually running those model experiments in this batch.**

The plan intentionally becomes broader in implementation scope, but every empirical experiment must still isolate one causal variable.

The intended progression is:

```text
existing narrow deterministic mechanism evidence
    ↓
evaluation semantics hardening
    ↓
broader Document Ops frame qualification
    ↓
dimension-specific reliability protocol
    ↓
H-OR1a operational reliability
    ↓
H-SR1a stateful reliability
    ↓
H-RCV1a recovery reliability
    ↓
robustness substrate qualification
    ↓
change-reliability substrate qualification
    ↓
defensible held-out substrate
    ↓
provider-neutral specialization execution contract
    ↓
consolidated readiness gate
    ↓
STOP before H-P1
```

No architecture synthesis is authorized.

---

## 2. Governing Research Principles

All applicable repository `AGENTS.md` files remain authoritative.

### 2.1 Research before architecture

Imported systems, prior IRIS-X mechanisms, fixture schemas, and experimental harnesses are evidence, hypotheses, or reusable substrate.

They are not architecture requirements.

Do not produce a final IRIS-X architecture from this batch.

### 2.2 Large plan does not mean mixed experiments

This plan is intentionally large to reduce planning overhead.

Every empirical experiment must still be separately:

- defined;
- frozen;
- executed;
- recorded;
- interpreted;
- committed.

Do not combine multiple reliability dimensions into one treatment.

### 2.3 Reliability dimensions remain separate

IRIS-X currently distinguishes:

- operational reliability;
- stateful reliability;
- robustness;
- change reliability / maintainability;
- recovery reliability.

Do not collapse these into one scalar reliability score.

Evidence in one dimension does not establish another dimension.

### 2.4 Outcome, evidence, acceptance, and execution state remain separate

Future records must distinguish at least:

1. actual outcome status;
2. empirical evidence status;
3. system/verifier acceptance decision;
4. verified-success eligibility;
5. execution/state status.

Do not define evidence truth from system acceptance.

Do not define actual outcome from verifier acceptance.

### 2.5 Lifecycle cost remains a vector

Record cost/resource components separately.

Do not scalarize lifecycle cost without an explicitly justified accounting and decision boundary.

Unknown cost is `Unknown`, not zero.

### 2.6 Invalid runs are preserved

Never overwrite run directories.

If a measured run becomes invalid:

1. preserve its artifacts;
2. record the failure;
3. disqualify the aggregate;
4. fix the harness;
5. rerun under a new run ID.

### 2.7 Imported source remains read-only

Do not modify:

```text
sources/
references/papers/
```

State-changing experiments must operate only on IRIS-X-authored or validated copied workspaces.

---

## 3. Hard Scope Boundary

This plan authorizes:

### Reliability/evaluation work

- evaluation-semantics hardening;
- qualification of the complete 48-fixture Document Ops frame;
- Reliability Protocol v0;
- H-OR1a operational-reliability experiment;
- H-SR1a stateful-reliability experiment;
- H-RCV1a recovery-reliability experiment;
- robustness perturbation substrate qualification;
- change/regression substrate qualification.

### Specialization preparation

- held-out taxonomy and governance;
- protocol-instance and protocol-family heldout definitions;
- post-freeze generated instance-blind protocol;
- deterministic generated-task substrate;
- oracle separation;
- leakage audit;
- candidate freeze contract;
- provider-neutral model/program execution contract;
- design-time/runtime cost ledgers;
- deterministic fake-candidate end-to-end dry-run.

This plan does **not** authorize:

- H-P1 execution;
- H-G1 execution;
- H-W1 execution;
- H-C1 execution;
- H-R1 execution;
- model API calls;
- paid model calls;
- optimizer calls;
- reflection-model calls;
- workflow search;
- router training;
- cascade calibration;
- fine-tuning;
- architecture synthesis;
- Phase 5.

At the final readiness gate: **STOP**.

---

# PART A — Evaluation and Broader Task Frame

## 4. Preflight

Before implementation:

1. reload latest `main`;
2. record actual HEAD;
3. confirm ancestry from planning baseline where applicable;
4. read all applicable `AGENTS.md` files;
5. inspect current Phase 3/4 definitions and results;
6. inspect the full VANTA Document Ops catalog;
7. inspect the actual fixture contracts required for broader qualification;
8. inspect candidate-hypothesis and uncertainty records.

At minimum inspect:

```text
AGENTS.md
research/AGENTS.md
experiments/AGENTS.md

research/problem-definition.md
research/task-distribution-selection.md
research/task-contract-docops-readonly-12.md
research/candidate-mechanism-hypotheses.md
research/phase-4-mechanism-experiment-results.md
research/phase-4-evidence-interception-results.md

docs/plans/TEMP_PHASE_4_EVIDENCE_INTERCEPTION.md

experiments/exp-2026-08-28-docops-readonly-baseline/
experiments/exp-2026-08-30-docops-acceptance-verification/
experiments/exp-2026-08-30-docops-evidence-binding/
experiments/exp-2026-08-30-preexecution-write-interception/

corpus/sources.yaml
tools/source_snapshot_assertion.py

sources/predecessors/vanta/docs/04_experiments/fixtures/README.md
```

Inspect actual source definitions relevant to:

- simulated patch/diff;
- reversible edit/commit;
- invalid action/path guard;
- evidence/verifier challenge;
- journal/replay/recovery;
- working-set long context.

Do not infer executability merely from fixture names.

---

## 5. WP0 — Evaluation State Semantics v1

Create:

```text
research/evaluation-state-semantics-v1.md
```

### 5.1 Purpose

Resolve the terminology issue exposed during H-V1b review.

Future schemas must explicitly distinguish:

### Actual outcome

Suggested values:

```text
success
partial
failure
unresolved
```

### Empirical evidence status

Suggested values:

```text
sufficient
insufficient
invalid_binding
not_assessed
unresolved
```

### Acceptance decision

Suggested values:

```text
accept
reject
abstain
not_applicable
```

### Verified-success eligibility

A protocol-derived eligibility field.

### Joint empirical interpretation

Examples:

```text
verified_success
unverified_success
false_success
false_failure
correctly_recognized_failure
correctly_recognized_partial
unresolved
```

Explicitly state:

> `accept` is not synonymous with `verified_success`.

Historical immutable runs must not be rewritten.

Where old schemas overload terminology, document the compatibility boundary.

---

## 6. WP1 — Document Ops Task Frame v1 Qualification

Create:

```text
research/document-ops-task-frame-v1.md
research/task-frames/document-ops-v1.json
```

or equivalent repository-consistent paths.

### 6.1 Source frame

Inventory all 48 preserved Document Ops fixtures across:

1. Traceability extraction;
2. Terminology consistency;
3. Simulated patch and diff;
4. Reversible edit and commit;
5. Invalid action and path guard;
6. Evidence and verifier challenge;
7. Journal, replay, and recovery;
8. Working-set long context.

H-I1a permits reconsideration of the broader frame because copied-workspace mutation containment has now been independently tested task-locally.

This does **not** automatically validate all 48 fixtures.

### 6.2 Required inventory fields

For every fixture record at least:

```text
fixture_id
source_id
source_snapshot_id
source_fixture_path
stratum
source_stated_purpose
action_mode
requires_mutation
requires_copied_workspace
oracle_location
oracle_type
expected_output_shape
state_oracle_required
evidence_oracle_required
recovery_state_required
long_context_required
known_external_dependency
known_framework_dependency
safe_local_candidate
qualification_status
qualification_reasons
```

Inspect actual fixture content where these fields cannot be established from the catalog alone.

### 6.3 Qualification statuses

Use:

```text
qualified-local
qualified-with-copied-workspace
qualified-for-substrate-only
deferred-framework-dependent
deferred-contract-unclear
rejected-for-current-frame
```

### 6.4 Necessary qualification gates

A current IRIS-X executable fixture must have, where relevant:

- an explicit task contract;
- local declared inputs;
- a locally available oracle/evaluator or defensible IRIS-X-authored oracle;
- no network requirement;
- no credential requirement;
- no paid service requirement;
- no imported-source mutation;
- state-changing behavior redirected to copied workspaces;
- empirically measurable state/recovery truth;
- no requirement to inherit predecessor runtime semantics as architecture authority.

### 6.5 Machine-readable groups

Produce explicit eligible groups such as:

```text
frame_v1_readonly
frame_v1_simulation
frame_v1_reversible_state
frame_v1_guard
frame_v1_evidence
frame_v1_recovery
frame_v1_long_context
```

### 6.6 Claim boundary

Do not call this a validated or representative benchmark.

Use bounded language such as:

```text
broader research frame
qualified local task frame
protocol evaluation frame
development/evaluation substrate
```

All 48 fixtures must be accounted for exactly once.

---

## 7. WP2 — Reliability Protocol v0

Create:

```text
research/reliability-protocol-v0.md
```

### 7.1 Common record identity

Future reliability records should identify:

```text
experiment_id
run_id
reliability_dimension
task_or_action_id
configuration_id
episode_id
cycle_or_sequence_index
task-frame/source identity
code commit
frozen definition hash
environment identity
actual outcome
empirical evidence status
acceptance decision if applicable
verified-success eligibility if applicable
terminal execution status
resource vector
```

### 7.2 Operational reliability

Measure stability of a fixed configuration under nominally equivalent execution.

Possible observables:

- outcome drift;
- deterministic output drift;
- evidence-status drift;
- terminal-status drift;
- invalid episodes;
- sequence-position effects;
- unexpected process-state accumulation.

### 7.3 Stateful reliability

Measure preservation of required invariants across persistent/accumulated state.

Possible observables:

- baseline restoration;
- cumulative state drift;
- stale backups;
- residual files;
- journal divergence;
- later-cycle degradation.

### 7.4 Robustness

Measure persistence under an independently validated shift.

Every perturbation requires an equivalence or expected-change contract.

### 7.5 Change reliability

Measure regressions resulting from a configuration change while keeping task/evaluator/runtime comparison identity explicit.

### 7.6 Recovery reliability

Separate:

```text
failure detected
recovery attempted
recovery action completed
final state valid
final task outcome
final evidence status
```

A recovery claim is not recovery truth.

### 7.7 Aggregation

Do not create a unified reliability score.

Each experiment declares its own horizon and dimension-specific measurements.

Commit Reliability Protocol v0 before measured reliability runs.

---

# PART B — Reliability Experiments

## 8. H-OR1a — Process-Lifetime Operational Stability

Suggested experiment:

```text
exp-2026-08-31-process-lifetime-stability
```

### Hypothesis

> Holding task bytes, configuration behavior, evaluator, evidence policy, source snapshot, and execution order fixed, a long-lived execution process will preserve task outcome, expected deterministic output/evidence state, and terminal validity across the declared sequence horizon as reliably as fresh-process execution; any sequence-position drift or persistent-process contamination is observable as a paired reliability difference.

### Arms

```text
fresh-process-v0
long-lived-process-v0
```

`fresh-process-v0` isolates each task execution in fresh interpreter/process state.

`long-lived-process-v0` executes the same frozen sequence repeatedly in one process.

### Critical isolation

Hold fixed:

- configuration;
- task bytes;
- task order;
- evaluator;
- evidence policy;
- source snapshot;
- no retries;
- no recovery;
- no model/network use.

The intended difference is process lifetime only.

### Candidate workload

Prefer the qualified deterministic structured read-only control or another equally controlled WP1-qualified subset.

Justify and freeze the selection before the run.

### Horizon

Suggested default:

```text
12 tasks × 10 sequence passes × 2 arms = 240 episodes
```

If execution remains trivial, 20 sequence passes is acceptable.

Freeze exact horizon before measured execution.

### Measurements

Include:

- actual outcome;
- output hash;
- evidence status;
- terminal status;
- pass index;
- position in sequence;
- invalid episodes;
- drift count;
- wall/CPU timing;
- artifact bytes;
- memory/resource observations only where measurement is reliable.

### Result vocabulary

Use bounded statuses such as:

```text
Stable under declared horizon
Drift observed — task-local
Mixed evidence
Not established
Invalid run
```

A stable result does not establish production or days/weeks reliability.

Complete and interpret before H-SR1a measured execution.

---

## 9. H-SR1a — Reversible-Cycle Stateful Stability

Suggested experiment:

```text
exp-2026-08-31-reversible-cycle-state-stability
```

### Hypothesis

> Holding the reversible action definition, copied-workspace baseline, state oracle, evaluator, and rollback policy fixed, persistent repeated apply→verify→rollback cycles will return the workspace to the frozen baseline after every completed cycle without cumulative state drift over the declared horizon; a fresh-workspace control distinguishes persistent-state accumulation from one-cycle correctness.

Use only WP1-qualified reversible-edit fixtures.

Do not inherit the predecessor runtime wholesale.

Implement the smallest IRIS-X-authored copied-workspace semantics required by the tested contracts.

### Arms

#### `fresh-workspace-cycle-v0`

```text
fresh baseline copy
→ apply
→ verify
→ rollback
→ verify baseline restoration
→ discard
```

#### `persistent-workspace-cycle-v0`

```text
one copied workspace
→ apply
→ verify
→ rollback
→ verify baseline
→ repeat on same workspace
```

### Causal variable

Workspace persistence across cycles.

Action logic, rollback logic, evaluator, policy, source bytes, and operation order stay fixed.

### Empirical state truth

Compare against a frozen baseline using:

- path set;
- SHA-256 by path;
- directory membership;
- backup/journal metadata where contractually required;
- residual artifacts;
- explicit harness state if introduced.

`rollback_success=true` is not sufficient evidence.

### Horizon

Suggested:

```text
qualified reversible fixtures × 10 cycles × 2 arms
```

If all six reversible fixtures qualify:

```text
6 × 10 × 2 = 120 cycle records
```

Freeze before measured execution.

### Measurements

Record:

- apply outcome;
- rollback action result;
- baseline restoration;
- drift count;
- first drift cycle;
- residual paths/bytes;
- journal/backup divergence;
- later-cycle degradation;
- invalid cycles;
- wall/CPU time;
- artifact bytes.

### Efficient evidence retention

Do not commit a full copied workspace for every normal successful cycle.

Normally preserve:

```text
baseline state manifest
post-apply state manifest
post-rollback state manifest
hashes
changed paths
required diff/payload evidence
terminal record
```

Preserve a complete copied workspace for:

- invalid cycles;
- unexpected drift;
- rollback failures;
- cases where compact evidence is insufficient.

Include a self-test with an intentional residual artifact and ensure the state oracle detects it.

Complete and interpret before H-RCV1a.

---

## 10. H-RCV1a — Targeted Recovery to Valid State

Suggested experiment:

```text
exp-2026-08-31-targeted-recovery-valid-state
```

### Hypothesis

> Holding the frozen injected failure state, task contract, final-state oracle, and execution envelope fixed, a targeted recovery procedure will restore the workspace and/or evidence state required by the task contract more often than no-recovery handling, without introducing new invalid side effects in the declared finite sample.

Use only WP1-qualified recovery fixtures.

Possible source cases include:

- rollback failure;
- audit gap;
- compensable action;
- structured rollback recovery;
- audit-reference repair;
- structured replay.

### Frozen failure states

This first recovery experiment does not test autonomous arbitrary diagnosis.

Create and freeze deterministic failure state per task.

Both arms start from identical failure state.

### Arms

```text
detect-only-v0
targeted-recovery-v0
```

The control only adjudicates the failure.

The treatment applies a predeclared targeted recovery, then undergoes independent final-state/outcome evaluation.

### Record separately

```text
failure_state_validated
recovery_attempted
recovery_action_completed
final_state_valid
final_actual_outcome
final_evidence_status
new_side_effect_violation
```

### Oracle separation

Recovery code must not receive the expected final-success label.

Final-state truth must come from an independent oracle.

### Horizon

Suggested:

```text
qualified recovery fixtures × 2 arms × 3 repetitions
```

If all six qualify:

```text
6 × 2 × 3 = 36 episodes
```

### Measurements

Include:

- final state validity;
- final actual task outcome;
- evidence sufficiency;
- unrecovered failures;
- recovery-induced failures;
- side-effect violations;
- recovery action count;
- recovery wall/CPU cost;
- artifact bytes.

Include an injected failed-recovery self-test to establish oracle sensitivity.

A positive result establishes only targeted local recovery over frozen failure states.

---

# PART C — Robustness and Change-Reliability Substrate

## 11. WP3 — Semantics-Preserving Robustness Substrate

Create:

```text
research/robustness-perturbation-protocol-v0.md
experiments/substrates/docops-robustness-v0/
```

This is substrate qualification, **not** a system robustness result.

### Candidate transformation families

Only use transformations whose semantic effect can be independently validated.

Candidates include:

- irrelevant context insertion;
- order permutation where contractually order-invariant;
- equivalent JSON serialization;
- equivalent path presentation where canonical identity is provable;
- long-context distractor placement for qualified working-set tasks.

Do not assume these are semantics-preserving without validators:

- task paraphrases;
- terminology substitutions;
- context deletion;
- selector modification;
- entity renaming;
- source-byte substitution.

### Every transformation requires

```text
transformation_id
precondition
deterministic builder
seed/parameters
equivalence validator
expected oracle identity or expected change
```

### Sensitivity test

Include at least one known semantics-changing transformation that the equivalence validator must reject.

Passing this self-test only qualifies the substrate.

Do not run model candidates in this work package.

---

## 12. WP4 — Change Reliability / Regression Substrate

Create:

```text
research/change-reliability-protocol-v0.md
experiments/substrates/config-regression-v0/
```

### Required comparison identities

```text
baseline_candidate_id
baseline_candidate_sha256
candidate_id
candidate_sha256
task_frame_id
evaluator_id
task/source generation identity
runtime envelope
```

### Per-task change dimensions

At minimum support:

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

Multiple dimensions may apply.

### Required injected-regression self-test

Create an experiment-local intentionally faulty deterministic candidate/configuration, for example:

- remove a required output field;
- alter a known output;
- remove required evidence.

The regression harness must detect it.

Do not modify imported sources or historical controls.

Passing this test means only:

> The regression measurement substrate detects this injected regression.

It does not establish general maintainability.

---

# PART D — Defensible Held-Out Task Substrate

## 13. WP5 — Held-Out Evaluation Protocol v0

Create:

```text
research/heldout-evaluation-protocol-v0.md
```

Existing repository fixtures cannot automatically be described as unseen.

Define at least four evidence classes.

### `development-visible`

Available for:

- implementation;
- debugging;
- optimizer feedback;
- manual analysis.

### `protocol-instance-heldout`

Existing instances frozen away from optimizer feedback after split declaration.

They remain repository-visible in principle.

### `protocol-family-heldout`

A task family/stratum excluded from development/optimization and opened only after candidate freeze.

Again, protocol-heldout rather than guaranteed unseen.

### `post-freeze-generated-blind`

Fresh instances generated only **after candidate freeze**, using generator and oracle rules frozen beforehand.

This term means **instance-blind after candidate freeze**, not that the generator implementation is secret.

### Future specialization split declaration

Before optimization, future H-P1-like experiments must declare:

```text
development set
optimizer-visible validation set
protocol-heldout set
blind generation protocol
candidate freeze point
evaluation authorization point
```

### No retroactive holdout

Anything used for:

- prompt editing;
- candidate selection;
- optimizer feedback;
- debugging;
- pre-freeze error analysis

cannot later become heldout evidence for that candidate.

### Candidate freeze rule

Before generating future blind instances:

1. freeze/commit candidate;
2. record candidate SHA;
3. freeze evaluator;
4. freeze generator;
5. freeze runtime/resource envelope;
6. close and record design-time cost accumulated so far.

Only then generate evaluation instances.

### Blind-set invalidation

If blind results are inspected and the candidate is modified:

```text
old blind set ≠ blind evidence for new candidate
```

The modified candidate requires:

```text
new candidate freeze
→ new generation seed
→ new instances
```

### No post-generation cherry-picking

For a future blind run:

- freeze validity/inclusion rules beforehand;
- evaluate every generated instance that passes those rules;
- record generator/validation failures;
- do not selectively discard hard but valid cases after seeing their content or outcomes.

---

## 14. WP6 — Post-Freeze Generated Task Substrate

Create:

```text
experiments/substrates/docops-generated-heldout-v0/
```

### Design rule

Do not merely alter expected outputs of existing VANTA tasks.

Create IRIS-X-authored generators with explicit generative rules and independently computable oracles.

Prefer fewer strong task families over many weak contracts.

### Initial candidate generated families

#### 1. Traceability extraction

Generate:

- markdown documents;
- explicit reference graph;
- requested extraction target.

Derive oracle independently from generator state.

#### 2. Terminology consistency

Generate:

- small document sets;
- canonical terminology dictionary;
- controlled conflict/no-conflict state.

Derive oracle from hidden generation state.

#### 3. Path/action guard

Generate:

- workspace tree;
- allowed/protected regions;
- safe/unsafe relative action proposals.

Derive oracle from deterministic policy.

#### 4. Structured simulation

Generate:

- markdown or JSON input;
- deterministic selector;
- proposed simulation/edit;
- expected transformed output/diff.

### Generator/oracle separation

Use a conceptual pipeline like:

```text
generator specification
→ hidden generation state
→ public task input
→ independent hidden oracle
```

Candidate execution receives only public task input.

### Every generated instance records

```text
generator_id
generator_version_sha256
generation_seed
instance_id
family_id
public_input_hash
hidden_oracle_hash
candidate_freeze_sha
```

### Reproducibility requirements

Validate:

- same seed → same instance and oracle;
- different seeds → distinct instances;
- oracle deterministic;
- public task contains enough information to solve the task;
- hidden oracle not embedded in candidate-visible bundle;
- invalid generator configurations are rejected.

### Leakage audit

Automate checks that candidate-visible files contain no:

- expected answer;
- expected validity;
- hidden oracle;
- hidden label;
- answer-revealing generation metadata.

### Future blind materialization

This plan may use explicitly declared development/test seeds to validate the generator.

Do **not** generate and commit the real future blind evaluation set now.

Real blind instances must be generated after the future candidate has been frozen.

### Minimum exit requirement

At least **two** generator families must qualify cleanly.

Prefer all four if validity remains strong.

Do not weaken oracle/leakage requirements simply to reach four.

Difficulty calibration and real-world representativeness remain `Unclear` unless separately established.

---

# PART E — Model-Specialization Execution Readiness

## 15. WP7 — Provider-Neutral Candidate / Run Contract

Create:

```text
research/model-specialization-execution-contract-v0.md
experiments/substrates/model-specialization-v0/
```

No model call is authorized.

### Candidate identity

Future records should support:

```text
candidate_id
candidate_type
candidate_source_or_prompt
candidate_sha256
base_model_id
base_model_provider
provider_snapshot_if_known
tool_envelope
program/workflow definition
creation method
optimizer identity if any
```

### Design-time cost ledger

Keep separate fields for future:

```text
optimizer_model_calls
reflection_model_calls
candidate_evaluations
tokens
provider_cost_usd
wall_time
human_intervention
search_iterations
failed_candidate_count
```

Unknown values remain `Unknown`.

### Runtime cost ledger

Support:

```text
model_calls
input_tokens
output_tokens
provider_cost_usd
tool_calls
verification_cost
retry_count
recovery_count
wall_time
artifact_bytes
```

### No premature amortization

Do not amortize design-time cost into runtime cost without a declared deployment volume/horizon.

### Candidate/evaluator boundary

Candidate receives only candidate-visible task inputs.

Evaluator and hidden oracle operate only after candidate output is frozen.

### Failure retention

Future:

- provider errors;
- malformed output;
- timeout;
- tool failure

must become terminal evidence.

Do not silently retry unless retry itself is under study.

### Fake-candidate dry-run

Implement deterministic local fake candidate adapters sufficient to validate:

- candidate loading;
- candidate hash;
- public task packaging;
- terminal records;
- evaluator separation;
- design/runtime ledger shape;
- failure retention.

Include both a successful deterministic fake and an explicit failure case.

No external model/provider calls.

### Required tests

Verify:

- hidden oracle never enters candidate input;
- modifying candidate changes SHA;
- post-freeze generation manifest binds candidate SHA;
- design-time/runtime ledgers remain separate;
- unknown provider cost is not silently converted to zero;
- failed executions are retained;
- existing run directory cannot be overwritten.

---

# PART F — Consolidated Readiness Gate

## 16. WP8 — Phase 4 Reliability and Specialization Readiness

Create:

```text
research/phase-4-reliability-specialization-readiness.md
```

Include separate sections for:

1. evaluation-state semantics;
2. 48-fixture qualification;
3. Reliability Protocol v0;
4. H-OR1a;
5. H-SR1a;
6. H-RCV1a;
7. robustness substrate;
8. change-reliability substrate;
9. held-out governance;
10. generated task substrate;
11. specialization execution contract;
12. remaining uncertainty;
13. readiness decision.

### Empirical result vocabulary

Use bounded terms such as:

```text
Supported — task-local
Stable under declared horizon
Drift observed — task-local
Mixed evidence
Rejected — task-local
Not established
Invalid run
```

### Substrate vocabulary

Use:

```text
Qualified for later use
Qualified with limitations
Needs redesign
Not ready
Not evaluated
```

Do not present substrate self-tests as system-performance results.

### Required readiness questions

#### Task frame

- Are all 48 fixtures accounted for?
- How many qualified per stratum/status?
- Which were deferred/rejected, and why?

#### Reliability

- Did process lifetime produce drift?
- Did persistent reversible cycles accumulate state drift?
- Did targeted recovery restore valid final state?
- Which reliability dimensions remain untested?

#### Robustness/change

- Does perturbation substrate include independently validated transformations?
- Does its negative sensitivity test work?
- Does regression substrate detect an injected known regression?

#### Held-out

- Is held-out terminology explicit?
- Is retroactive holdout prohibited?
- Can new instances be reproducibly generated after candidate freeze?
- Does leakage audit pass?
- Is the future real blind set still unmaterialized?

#### Specialization

- Can fake candidate traverse the full candidate/evaluator contract?
- Is candidate identity frozen?
- Are design-time and runtime costs separate?

### Final readiness status

Choose exactly one:

```text
Ready to design H-P1
Conditionally ready — blockers listed
Not ready — blockers listed
```

This decision means readiness to **design**, not permission to execute H-P1.

---

## 17. Research-State Maintenance

Update current research records minimally.

Do not rewrite historical results.

H-OR1a, H-SR1a, and H-RCV1a are RQ4 reliability sub-hypotheses; do not falsely describe them as imported mechanism hypotheses.

H-P1, H-G1, H-W1, H-C1, and H-R1 remain:

```text
Not evaluated
```

even if the supporting substrate becomes ready.

Do not promote any mechanism to architecture requirement.

---

## 18. Artifact Efficiency

Normal successful stateful/recovery runs should not commit hundreds of complete workspace copies.

Prefer durable evidence composed of:

```text
terminal records
state manifests
hashes
changed-path lists
diffs
required changed payloads
```

Preserve full workspaces only for:

- invalid runs;
- unexpected state drift;
- failed rollback;
- failed recovery;
- evidence cases where compact manifests cannot reconstruct the relevant fact.

Generated-task substrate should preserve:

- generator;
- schema/spec;
- qualification seeds;
- compact validation cases;

rather than a large future blind corpus.

---

## 19. Validation

At minimum execute:

```powershell
python tools\repository_check.py
git diff --check
```

Compile every changed Python file:

```powershell
python -m py_compile <changed-python-files>
```

### Task-frame tests

Verify:

- exactly 48 source fixtures accounted for;
- no duplicates;
- valid status vocabulary;
- registered source paths resolve;
- source unchanged.

### H-OR1a tests

Verify:

- identical tasks/config across arms;
- process lifetime is the intended difference;
- horizon frozen;
- aggregates reconstruct from raw records.

### H-SR1a tests

Verify:

- starting baseline identity;
- identical apply/rollback definitions;
- independent baseline-restoration oracle;
- intentional residual state is detected.

### H-RCV1a tests

Verify:

- identical frozen failure state across arms;
- recovery cannot consume expected final-success label;
- final-state oracle independent;
- injected recovery failure detected.

### Robustness tests

Verify:

- deterministic perturbation reproduction;
- valid equivalence accepted;
- known semantics-changing case rejected.

### Change-regression tests

Verify injected faulty candidate is detected.

### Held-out/generator tests

Verify:

- same seed reproducibility;
- different seed variation;
- oracle determinism;
- no oracle leakage;
- candidate freeze SHA binding;
- invalid generator rejection;
- no real future blind set pre-materialized.

### Specialization-contract tests

Verify:

- deterministic fake candidate E2E;
- candidate hash mutation sensitivity;
- evaluator isolation;
- separate cost ledgers;
- `Unknown` preserved;
- failed run retention;
- run immutability.

### Preservation

Confirm no changes under:

```text
sources/
references/papers/
```

and no modifications to prior completed run artifacts.

Report only commands actually executed.

---

## 20. Commit Discipline

Prefer coherent milestones:

1. add/activate this temporary plan;
2. evaluation semantics + 48-fixture qualification;
3. Reliability Protocol v0;
4. define/freeze H-OR1a;
5. execute/record H-OR1a;
6. define/freeze H-SR1a;
7. execute/record H-SR1a;
8. define/freeze H-RCV1a;
9. execute/record H-RCV1a;
10. robustness substrate;
11. change-reliability substrate;
12. held-out protocol + generated-task substrate;
13. specialization execution contract + fake-candidate dry-run;
14. consolidated readiness summary/navigation/validation;
15. retire this temporary plan.

Adjacent commits may be combined when still reviewable.

However:

> Every measured reliability run must reference a definition/frozen-input commit that predates the result.

Do not alter experiment criteria after observing results.

Do not rewrite history to hide failures.

---

## 21. Autonomous Execution Rules

Proceed with the smallest evidence-preserving decision without owner interruption when:

- some of the 48 fixtures fail qualification;
- a source fixture requires too much predecessor runtime;
- a platform-specific metric is unavailable;
- one generator family proves ambiguous;
- only a subset cleanly supports an experiment.

Record exclusions and continue.

Do not weaken a research contract simply to keep all fixtures/families.

Require owner intervention only for:

- secrets or credentials;
- paid/model API use;
- destructive action outside validated copies;
- a material scope change;
- evidence that invalidates the overall held-out strategy.

---

## 22. Exit Criteria

The plan is complete only when:

### Evaluation semantics

- evidence state and acceptance decision are explicitly separated;
- old runs remain immutable.

### Task frame

- all 48 fixtures inventoried;
- every fixture qualified/deferred/rejected with reason;
- eligible groups machine-readable.

### Reliability protocol

- five dimensions separately defined;
- no scalar reliability score introduced.

### H-OR1a

- definition/horizon frozen before run;
- measured result validly recorded or explicitly invalid/rejected;
- drift/stability interpreted within horizon.

### H-SR1a

- reversible fixture subset qualified;
- fresh/persistent comparison isolated;
- baseline state restoration empirically measured;
- result recorded.

### H-RCV1a

- failure states frozen;
- detect-only/recovery arms isolated;
- final state independently adjudicated;
- result recorded.

### Robustness substrate

- at least one useful transformation family qualified;
- negative sensitivity test passes.

### Change reliability substrate

- regression harness exists;
- injected known regression detected.

### Held-out governance

- visibility taxonomy explicit;
- no-retroactive-holdout rule explicit;
- candidate-freeze rule explicit;
- no cherry-picking rule explicit.

### Generated held-out substrate

- at least two clean deterministic generator families;
- reproducibility passes;
- distinct-seed generation passes;
- oracle separation passes;
- leakage audit passes;
- future real blind set remains unmaterialized.

Prefer all four initial generator families if cleanly supported.

### Model readiness

- provider-neutral contract exists;
- design/runtime cost ledgers separate;
- fake candidate runs end-to-end;
- no model/provider call occurred.

### Closure

- consolidated readiness summary exists;
- uncertainty updated accurately;
- validations pass;
- source/papers preserved;
- prior runs preserved;
- plan retired;
- H-P1/G1/W1/C1/R1 not executed;
- architecture synthesis not started;
- Phase 5 not started.

---

## 23. Hard Stop

After:

```text
evaluation semantics
48-fixture qualification
Reliability Protocol v0
H-OR1a
H-SR1a
H-RCV1a
robustness substrate
change-reliability substrate
held-out governance
generated held-out substrate
model-specialization execution contract
fake-candidate dry-run
readiness summary
validation
plan retirement
```

**STOP.**

Do not execute:

```text
H-P1
H-G1
H-W1
H-C1
H-R1
```

Do not call a model.

Do not call a paid API.

Do not synthesize architecture.

Do not begin Phase 5.

The next owner review determines whether IRIS-X is ready to design the first model-based specialization experiment.

---

## 24. Required Final Handoff

Report:

### Repository

- starting HEAD;
- final HEAD;
- commit sequence;
- changed files.

### 48-fixture frame

- all 48 accounted for;
- status counts;
- counts by stratum;
- deferred/rejected reasons.

### H-OR1a

- experiment/run ID;
- horizon;
- drift/stability result;
- invalid attempts;
- resource observations.

### H-SR1a

- qualified fixtures;
- cycles;
- state-restoration result;
- drift;
- invalid attempts;
- resource observations.

### H-RCV1a

- failure states;
- recovery outcomes;
- final-state validity;
- recovery-induced failures;
- invalid attempts;
- resource observations.

### Substrate readiness

- robustness families qualified;
- negative sensitivity result;
- regression injected-failure result;
- held-out taxonomy;
- generated families;
- leakage audit;
- fake-candidate dry-run.

### Validation

List exact executed commands and their results.

### Preservation

Confirm unchanged:

```text
sources/
references/papers/
prior completed run artifacts
```

### Uncertainty

List separately:

```text
Unknown
Unclear
Not established
Not evaluated
```

### Boundary

Explicitly confirm:

- zero external model calls;
- zero paid API calls;
- H-P1 not started;
- H-G1 not started;
- H-W1 not started;
- H-C1 not started;
- H-R1 not started;
- no architecture synthesis;
- no Phase 5.

Then **STOP**.
