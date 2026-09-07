# TEMP Phase 6 — Capability Pressure and Failure Attribution Foundation

Status: **Retired — Phase 6 Batch 1 complete; see retirement record**  
Date: **2026-09-07 Asia/Taipei**  
Repository: **Danwuoo/IRIS-X**  
Required baseline `main`: **`4aa7256e2237e997425e8712638334088056037d`**  
Phase: **Phase 6 — capability sufficiency and intervention-trigger research**  
Batch: **Batch 1**  
Batch goal: **establish a deterministic offline research substrate that operationalizes capability-pressure and failure-attribution criteria, reproduces selected Phase 5 decisions, and distinguishes synthetic trigger-positive cases from real evidence without adding any deferred agent mechanism**  
Architecture authority: **Research instrument only; no new runtime architecture, capability mechanism, or production claim**  
Live model/provider call ceiling: **0 total**  
Hard terminal boundary: **STOP after the authorized offline substrate, validation, Batch 1 result/handoff, plan retirement, normal push, and owner-facing report**

---

## 1. Owner authorization and phase boundary

This plan is the owner-authorized controlling plan for **Phase 6 Batch 1**.

Phase 5 is closed at:

```text
4aa7256e2237e997425e8712638334088056037d
```

That closure remains authoritative for Phase 5. Batch 1 must not reopen, rewrite,
strengthen, or silently reinterpret historical Phase 4/5 results, handoffs,
terminal records, frozen definitions, admission records, plans, or failure
lineage.

Phase 6 begins from a different research question than Phase 5.

Phase 5 primarily established and exercised a bounded trust/evidence execution
surface. Phase 6 studies when that minimum-sufficient surface becomes
insufficient and how a justified next intervention should be identified without
architecture-by-intuition.

The governing Phase 6 question for this batch is:

> Under frozen task/evidence semantics and preserved Phase 5 trust boundaries,
> what observable evidence is sufficient to identify a material capability
> shortfall, attribute the shortfall to a bounded failure class, and determine
> whether a deferred architecture capability has become research-triggered?

Batch 1 does **not** authorize implementation of the deferred capability itself.
It authorizes only the research instrument used to decide whether a future
mechanism experiment is warranted.

---

## 2. Research authority and inherited evidence

Read and preserve the distinctions in at least:

```text
AGENTS.md
research/AGENTS.md
experiments/AGENTS.md
research/problem-definition.md
research/phase-5-architecture-consolidation.md
research/phase-5-capability-trigger-review.md
docs/phase-5-architecture-state.md
docs/phase-5-architecture-consolidation-handoff.md
irisx/core/records.py
irisx/core/interfaces.py
irisx/core/execution.py
```

Also inspect the exact Phase 4/5 evidence needed for the historical replay
selected in this plan.

The relevant project-level research spine is:

```text
RQ1 — Sufficient capability
RQ5 — Failure attribution and intervention
```

Batch 1 may cite RQ2/RQ3/RQ4 when needed because evidence status, lifecycle
cost, and reliability are candidate shortfall axes, but Batch 1 must not expand
into a general cost optimizer or long-term reliability runtime.

Phase 5 closed with all reviewed deferred capability triggers still
`Not triggered`. Batch 1 starts from that fact. It must not assume that Phase 6
itself makes any mechanism necessary.

---

## 3. Batch 1 research proposition

The provisional proposition to test is:

> A bounded, deterministic research instrument can represent observed
> shortfalls separately from causal attribution, evaluate predeclared capability
> trigger criteria without executing those capabilities, preserve uncertainty,
> and reproduce selected accepted Phase 5 decisions without changing historical
> authority.

This proposition is **not** equivalent to any of the following claims:

- IRIS-X has a final failure ontology;
- IRIS-X can automatically choose an architecture;
- IRIS-X can automatically diagnose all agent failures;
- routing is required;
- retry/recovery is required;
- persistence is required;
- workflow machinery is required;
- model judging is required;
- automated specialization is required;
- external-action support is required;
- escalation/cascade is required;
- synthetic fixtures are evidence that a real trigger is satisfied.

---

## 4. Hard architecture boundaries

### 4.1 `irisx/core` preservation

Do not modify:

```text
irisx/core/records.py
irisx/core/interfaces.py
irisx/core/execution.py
```

unless a preservation-only repository repair becomes strictly unavoidable. If
such a conflict appears, **STOP** and report it instead of changing core.

Do not introduce permanent core abstractions named or equivalent to:

```text
FailureAttribution
CapabilityPressure
TriggerGate
ArchitectureDecision
Router
RetryPolicy
RecoveryPolicy
PersistentState
WorkflowEngine
ModelJudge
```

Batch 1 concepts remain experiment/research-local.

### 4.2 Deferred mechanisms remain unimplemented

Do not implement or enable:

```text
automated specialization
dynamic workflow machinery or workflow search
cascade/escalation
feature-based routing/allocation
runtime persistence
nondeterministic verifier/model judge
external or irreversible actions
general recovery/retry
```

Existing historical support, extension points, resource fields, or imported
framework code do not authorize these mechanisms.

### 4.3 Provider and model boundary

```text
live model calls: 0
provider calls: 0
paid API calls: 0
new authentication use: 0
new model subprocesses: 0
```

No provider compatibility test or live execution is authorized in Batch 1.

### 4.4 Source preservation

Do not modify:

```text
sources/
references/papers/
```

Imported frameworks remain reference material only.

### 4.5 No new broad framework dependency

Do not add DSPy, GEPA, AFlow, RouteLLM, FrugalGPT, Prime Agent, NeMo Agent
Toolkit, verifiers, or another external framework as a runtime dependency for
this batch.

If a tiny standard-library implementation is sufficient, prefer it.

---

## 5. Required starting state

Before substantive work:

1. read every applicable `AGENTS.md`;
2. run and record:

   ```text
   git status --short
   git rev-parse HEAD
   git rev-parse origin/main
   git rev-list --left-right --count origin/main...main
   ```

3. verify the required baseline is exactly:

   ```text
   4aa7256e2237e997425e8712638334088056037d
   ```

   or, only if owner work has already advanced `main`, verify the actual start
   is a clean descendant that does not conflict with this plan;
4. do not reset, overwrite, rebase away, or discard unrelated owner work;
5. run the repository organization check from root;
6. inspect the Phase 5 closure validation baseline, including the known
   pre-existing full-suite failure recorded at Phase 5 retirement;
7. record the actual starting SHA in the Batch 1 handoff and retirement record.

If the repository state materially conflicts with the authorized scope, STOP.

---

## 6. Evidence and claim discipline

Every Batch 1 assessment must keep these layers separate:

```text
observation
shortfall classification
failure attribution
intervention hypothesis
trigger evaluation
architecture/research decision
```

One layer must not silently imply the next.

In particular:

```text
observed failure != known cause
known cause != justified intervention
justified intervention != triggered architecture capability
synthetic trigger-positive fixture != real trigger evidence
```

Use explicit evidence classes:

```text
direct_repository_evidence
synthetic_fixture
inferred_interpretation
unknown
conflicting_evidence
```

Use uncertainty/status vocabulary compatible with repository research rules:

```text
Unknown
Unclear
Not established
Not evaluated
Conflicting evidence
```

Where the instrument cannot uniquely attribute a condition, it must preserve
ambiguity rather than invent certainty.

---

## 7. Capability-pressure model v0

Batch 1 defines a bounded research-only pressure model.

### 7.1 Shortfall axes

At minimum support:

```text
task_success
evidence
reliability
lifecycle_cost
```

Interpretation:

- `task_success`: the task contract is not met;
- `evidence`: outcome/evidence authority is insufficient or invalid even if the
  produced answer may be correct;
- `reliability`: repeated, shifted, stateful, or post-failure operation fails a
  declared reliability requirement;
- `lifecycle_cost`: success/reliability requirements may be met but a declared
  comparison shows a materially dominated resource/cost frontier.

Do not claim that these four axes are a final ontology.

### 7.2 Failure-stage candidate vocabulary

Support at least:

```text
admission_configuration
identity_authority
execution_producer
verification
state_continuity
control_flow
allocation_capability
external_effect
resource_cost
unknown
```

These are **candidate research categories**, not normative architecture types.

### 7.3 Attribution status

Support at least:

```text
directly_supported
inferred
ambiguous
not_attributable
```

Do not introduce pseudo-precise confidence percentages.

### 7.4 Assessment record

Each assessment should preserve fields equivalent to:

```text
assessment_id
case_id
evidence_class
source_refs
observed_conditions
shortfall_axes
failure_stage
attribution_status
attribution_reasons
candidate_interventions
capability_trigger_candidates
trigger_results
conflicts
unknowns
```

Exact JSON field names may differ modestly if a smaller schema is clearer.

---

## 8. Deferred capability gates v0

Operationalize the eight Phase 5 trigger families without changing their
meaning.

Required gate IDs:

```text
H-G1 automated specialization
H-W1 workflow machinery/search
H-C1 cascade/escalation
H-R1 feature-based routing/allocation
runtime persistence
nondeterministic verifier/model judge
external-action/interception expansion
general recovery/retry
```

Each gate definition must contain at least:

```text
gate_id
capability_name
research_status_at_phase5_close
trigger_status_at_phase5_close
required_predicates
negative_controls
source_authority
```

The gate evaluator must distinguish:

```text
not_triggered
triggered_by_fixture
triggered_by_direct_evidence
insufficient_or_ambiguous
conflicting_evidence
invalid_assessment
```

A synthetic fixture may never produce `triggered_by_direct_evidence`.

---

## 9. Gate semantics

The following semantics are controlling unless direct Phase 5 text requires a
more exact representation.

### 9.1 H-G1 — Automated specialization

Trigger only when all relevant conditions are present:

- repeatable program/specialization production or maintenance is a declared
  requirement;
- manual/frozen construction fails a declared quality, time, or lifecycle-cost
  requirement;
- automated production is the actual decision variable.

Negative controls include:

- multiple manually authored programs exist;
- an optimizer exists in the corpus;
- one historical optimizer-generated candidate exists;
- maintainability pressure is merely assumed.

### 9.2 H-W1 — Workflow machinery/search

Trigger only when:

- a declared task cannot meet its frozen success requirement under simple
  bounded execution ordering; and
- workflow/control-flow structure is the material decision variable; and
- at least one concrete workflow alternative is evaluable.

Negative controls include:

- multiple tasks exist;
- multiple sequential runs exist;
- a task description sounds multi-step but the bounded path succeeds;
- imported frameworks contain workflow engines.

### 9.3 H-C1 — Cascade/escalation

Trigger only when:

- a cheaper admitted configuration materially misses declared requirements;
- a specifically declared stronger candidate plausibly resolves the miss; and
- a decision-relevant success/reliability/cost trade-off exists.

Negative controls include:

- a stronger model exists;
- intuition says a stronger model would be safer;
- the cheaper configuration has no qualifying miss.

### 9.4 H-R1 — Feature-based routing/allocation

Trigger only when:

- heterogeneous frozen task features exist;
- two or more admissible allocations are compared;
- materially different outcome/resource behavior is observed; and
- feature-dependent allocation can alter the target success/reliability/cost
  frontier.

Negative controls include:

- semantic task heterogeneity alone;
- multiple providers/models exist but are not compared;
- two allocations differ only cosmetically;
- cost differs while all target requirements/frontier decisions remain
  unchanged.

### 9.5 Runtime persistence

Trigger only when declared task semantics require continuity across at least one
of:

```text
crash/restart
days/weeks
processes
hosts
ongoing stateful operation
```

and the state has an observable restoration/continuity oracle.

Negative controls include:

- Git evidence is durable;
- completed run artifacts persist;
- many independent runs exist;
- in-memory state is sufficient for the declared task.

### 9.6 Nondeterministic verifier/model judge

Trigger only when:

- deterministic acceptance is impossible or demonstrably lossy for a required
  task contract; and
- non-reducible semantic quality, multiple acceptable answers, evaluator
  disagreement, or calibrated human/semantic judgment is material; and
- an independently reviewable reference is available.

Negative controls include:

- a task looks natural-language-heavy;
- model output is stylistic but the contract has a deterministic oracle;
- a model judge would be convenient.

### 9.7 External action/interception expansion

Trigger only when a declared task requires a real externally visible or
irreversible effect, such as:

```text
network/API mutation
message delivery
payment
mutation outside isolated task state
irreversible side effect
authenticated remote evidence/interception
```

with explicit authorization and post-state/evidence requirements.

Negative controls include local copied/in-memory mutation or read-only model
execution.

### 9.8 General recovery/retry

Trigger only when:

- a concrete failure class exists;
- a bounded retry/recovery action is specified;
- the side-effect boundary is safe/known;
- an independently checkable comparison shows benefit; and
- the action is not merely hiding configuration or semantic failure.

Negative controls include:

- configuration incompatibility that should be rejected by admission;
- a wrong answer without evidence retry helps;
- an owner-authorized new definition being mislabeled as retry.

---

## 10. Repository placement

Preferred new experiment structure:

```text
experiments/capability-pressure-attribution-v0/
    README.md
    definition/
        trigger-gates.json
        attribution-vocabulary.json
        assessment-schema.json
    fixtures/
        phase-5-replay/
        synthetic-pressure/
        attribution-boundaries/
    scripts/
        validate_definitions.py
        assess_pressure.py
        summarize_assessments.py
    tests/
        test_definition_integrity.py
        test_trigger_gates.py
        test_failure_attribution.py
        test_phase5_replay.py
    runs/
        batch-1-offline/
            manifest.json
            assessments.json
            summary.json
```

Also create:

```text
research/phase-6-capability-pressure-and-failure-attribution.md
docs/phase-6-capability-pressure-attribution-handoff.md
```

A smaller equivalent structure is acceptable if it preserves the required
separation among definition, fixture/input, execution output, derived summary,
and interpretation.

Do not introduce another broad top-level hierarchy.

---

## 11. Definition freeze discipline

Before the authoritative offline run, freeze and commit:

- trigger-gate definitions;
- candidate attribution vocabulary;
- assessment schema;
- all 32 synthetic/boundary fixture definitions;
- historical replay fixture references/snapshots as authorized below;
- validators;
- evaluator;
- summary generator;
- Batch 1 focused tests.

Record one **definition/code freeze SHA**.

After the freeze:

- the authoritative offline run may add run evidence and interpretation only;
- executable definitions/code must remain byte-identical;
- if evaluator or definitions must change after observing the authoritative run,
  STOP the authoritative run lifecycle, preserve the failed evidence, fix under
  a new owner-visible repair commit, and perform a new explicitly identified
  run; do not silently overwrite the first run.

No model call is permitted in either case.

---

## 12. Synthetic pressure suite — 24 cases

Create exactly or at least **24 primary trigger cases**: three for each of the
eight capability families.

Each family must contain:

```text
1 surface-only negative control
1 near-trigger boundary case
1 synthetic positive-trigger case
```

The case definitions must declare expected trigger result before the
authoritative run.

### 12.1 H-G1

- negative: several manually frozen programs exist and meet requirements;
- near-trigger: repeated manual work exists but no declared quality/time/cost
  failure is established;
- positive: repeated onboarding requirement plus direct synthetic maintenance or
  lifecycle constraint that manual construction cannot satisfy and automated
  generation is the declared comparison variable.

### 12.2 H-W1

- negative: multiple sequential task steps succeed under explicit bounded
  ordering;
- near-trigger: simple ordering is inconvenient/verbose but still satisfies the
  contract;
- positive: frozen task contract fails under simple ordering and succeeds under
  a declared alternative workflow structure where control flow is the decision
  variable.

### 12.3 H-C1

- negative: cheaper configuration succeeds;
- near-trigger: cheaper configuration misses but stronger candidate has not been
  shown plausible/evaluable;
- positive: cheaper configuration misses a declared requirement, stronger
  candidate meets it, and cost/reliability trade-off is decision-relevant.

### 12.4 H-R1

- negative: heterogeneous tasks with one successful allocation;
- near-trigger: two allocations differ in cost but not in a decision-relevant
  target frontier;
- positive: different frozen task features map to materially different
  success/resource outcomes under at least two admissible allocations.

### 12.5 Runtime persistence

- negative: completed evidence is durable but runtime continuity is not a task
  requirement;
- near-trigger: a multi-run process exists but independent restart is allowed;
- positive: task success requires restoration across process/restart or a
  declared longer horizon with an observable state oracle.

### 12.6 Nondeterministic verifier/model judge

- negative: natural-language output still has a deterministic acceptance oracle;
- near-trigger: multiple surface forms exist but can be canonicalized
  deterministically;
- positive: a required semantic-quality contract is demonstrably lossy under
  deterministic reduction and has an independently reviewable adjudication
  reference.

### 12.7 External action/interception

- negative: isolated reversible local mutation/read-only execution;
- near-trigger: network read or simulated external action without externally
  visible mutation;
- positive: declared externally visible/irreversible mutation with frozen
  authorization, interception point, and authenticated post-state requirement.

### 12.8 General recovery/retry

- negative: known configuration incompatibility should fail admission;
- near-trigger: transient-looking failure exists but retry benefit/safety is not
  established;
- positive: repeated unchanged-profile transient or bounded repairable failure
  plus a specified safe action and deterministic comparison showing benefit.

---

## 13. Failure-attribution collision suite — at least 8 cases

Add at least eight cases where similar symptoms must not collapse to the same
attribution.

Required semantic coverage:

1. provider/configuration incompatibility -> `admission_configuration`, not
   model capability;
2. same admitted immutable configuration with repeatable transient execution
   behavior -> recovery/retry candidate pressure only when benefit/safety is
   established;
3. deterministic semantic miss under a cheaper configuration with a successful
   stronger comparison -> allocation/capability or escalation candidate;
4. correct producer output rejected because the deterministic verifier is
   insufficient -> verification pressure, not producer failure;
5. crossed task evidence or identity -> identity/evidence authority failure,
   not semantic model failure;
6. task requiring restart continuity -> state-continuity pressure, not workflow
   pressure by default;
7. simple control flow insufficient while model capability is held adequate ->
   control-flow pressure, not automatic escalation;
8. requirements met but declared lifecycle-cost comparison is dominated ->
   resource/cost pressure without inventing a task-success failure.

At least two cases should remain intentionally `ambiguous` unless extra evidence
is supplied.

The test suite must assert that ambiguity is preserved.

---

## 14. Historical Phase 5 replay

Batch 1 must use direct repository evidence as a replay/compatibility test, not
as mutable fixture truth.

At minimum replay selected evidence from:

### 14.1 Phase 5 Batch 4 Run 01 / Run 02 failure lineage

Expected interpretation must preserve the accepted historical distinction:

```text
failure_stage: admission_configuration or equivalent bounded configuration class
model capability failure: not established
retry requirement: not established
escalation requirement: not established
```

Do not relabel the known configuration failures as semantic model failures.

### 14.2 Phase 5 Batch 6 three-task family

The replay must preserve at least:

```text
three semantically distinct frozen tasks
one shared admitted allocation/profile
3/3 verified successes
zero retries
zero routes
zero escalations
zero recovery actions
read-only execution
```

Expected capability-trigger interpretation:

```text
routing/allocation: not triggered by the observed evidence
cascade/escalation: not triggered by the observed evidence
recovery/retry: not triggered by the observed evidence
runtime persistence: not triggered by the observed evidence
```

Other gates may remain `not_triggered` where directly justified by the same
record, or `not_assessed` if the replay evidence is not sufficient for that gate.
Do not manufacture completeness.

### 14.3 Replay authority rule

Historical repository artifacts remain source evidence.

The Batch 1 replay representation may contain hashes, normalized excerpts, or
references sufficient for deterministic assessment, but it must not overwrite or
rewrite historical Phase 5 files.

If the new instrument cannot reproduce an accepted historical conclusion:

```text
record: Conflicting evidence
STOP architecture interpretation
preserve the failing replay result
```

Do not change historical evidence to make the test pass.

---

## 15. Evaluator behavior

Implement a deterministic offline evaluator with behavior equivalent to:

```text
load frozen definitions
    -> validate schema and IDs
    -> load one assessment input
    -> classify declared/observed conditions
    -> preserve evidence class
    -> evaluate shortfall axes
    -> evaluate bounded attribution rules
    -> evaluate each relevant trigger gate
    -> emit deterministic assessment record
```

The evaluator must be fail-closed for malformed definitions.

Reject or mark invalid at least:

- unknown gate ID;
- duplicate gate ID;
- missing required predicate;
- invalid evidence class;
- direct-evidence trigger claimed from synthetic evidence;
- invalid attribution status;
- malformed source reference;
- contradictory expected-result declaration;
- a gate result not derivable from the declared predicates.

Do not build a generic rule engine, DSL, plugin framework, inference engine, or
architecture planner.

Plain Python data structures/functions are preferred.

---

## 16. Determinism and identity

The authoritative offline run must be reproducible from frozen definitions.

Record SHA-256 identities for at least:

```text
gate definitions
attribution vocabulary
assessment schema
fixture inventory
evaluator code identity or definition/code freeze SHA
historical replay source references/snapshots
```

Running the same frozen inputs twice must produce byte-identical normalized
assessment output or a deterministic semantic equivalent with explicit
non-semantic timestamp exclusion.

Prefer removing timestamps from authoritative assessment payloads rather than
normalizing them later.

---

## 17. Derived summary boundary

Generate one derived Batch 1 summary containing at least:

```text
case_count
synthetic_pressure_case_count
attribution_boundary_case_count
historical_replay_case_count
valid_assessments
invalid_assessments
negative_controls_passed
near_trigger_cases_passed
synthetic_positive_triggers_passed
ambiguous_cases_preserved
historical_replays_matched
historical_replay_conflicts
direct_evidence_triggers_by_gate
synthetic_triggers_by_gate
unknowns
conflicts
```

This summary is **derived data only**.

Per-case assessment records and original historical repository evidence remain
more authoritative.

---

## 18. Direct evidence versus synthetic evidence

This distinction is a hard invariant.

A synthetic positive case proves only:

> the research instrument can recognize the predeclared trigger predicate when
> the predicate is deliberately satisfied by a fixture.

It does **not** prove:

> IRIS-X has observed that trigger in a real task distribution.

Accordingly, the Batch 1 final result must separately report:

```text
synthetic trigger recognition
real repository trigger status
```

Unless direct repository evidence independently satisfies a gate, the Phase 6
Batch 1 research conclusion should normally preserve the Phase 5 direct-evidence
trigger status as `Not triggered`.

A synthetic fixture must never mutate the direct-evidence trigger ledger.

---

## 19. Research note

Create:

```text
research/phase-6-capability-pressure-and-failure-attribution.md
```

It must clearly separate:

- source-stated Phase 5 trigger definitions;
- directly observed Batch 1 implementation/test/run behavior;
- inferred interpretation;
- synthetic fixture behavior;
- unknowns and unresolved questions.

Required sections should cover at least:

```text
Question / scope
Evidence basis
Phase 6 research framing
Candidate pressure model
Candidate attribution vocabulary
Trigger operationalization
Synthetic pressure suite
Historical replay
Observed results
Conflicts / ambiguity
What is supported
What is not established
Decision for next research action
```

Do not promote the candidate attribution vocabulary into a final project
ontology.

---

## 20. Test requirements

### 20.1 Definition integrity tests

Test at least:

- valid definitions load;
- duplicate IDs reject;
- missing required fields reject;
- unknown gate IDs reject;
- invalid status vocabulary rejects;
- synthetic evidence cannot masquerade as direct evidence;
- source references required where direct repository evidence is claimed.

### 20.2 Trigger-gate tests

For each of eight capability families:

- surface-only negative remains non-triggered;
- near-trigger remains non-triggered/insufficient as predeclared;
- synthetic positive satisfies the synthetic trigger result;
- removing one required positive predicate breaks the trigger.

### 20.3 Attribution tests

Test:

- configuration failure does not become model-capability failure;
- evidence/identity crossing does not become semantic failure;
- verifier insufficiency does not become producer failure;
- state continuity does not automatically become workflow failure;
- cost pressure does not become task-success failure;
- ambiguous cases remain ambiguous.

### 20.4 Historical replay tests

Assert selected Batch 4 and Batch 6 interpretations match durable historical
conclusions.

Do not encode stronger conclusions than the historical sources support.

### 20.5 Determinism tests

At minimum:

- same frozen input -> same normalized assessment;
- fixture ordering does not alter per-case semantics;
- summary generation is deterministic;
- malformed case cannot partially pass a gate.

---

## 21. Validation sequence

Before the authoritative offline run:

1. run definition/schema tests;
2. run trigger-gate tests;
3. run attribution tests;
4. run historical replay tests;
5. run any existing directly affected experiment tests;
6. run repository check.

After the authoritative run:

1. validate assessment inventory and hashes;
2. rerun focused tests;
3. rerun repository check;
4. run the full discovered repository test inventory using the project’s
   established method;
5. distinguish new failures from known historical failures.

Phase 5 retirement recorded a known unchanged full-suite failure in the frozen
Phase 4 plan hash contract. Batch 1 must not silently modify historical data to
make that failure disappear.

A successful Batch 1 may report the same pre-existing failure as unchanged if
confirmed. Any new unexplained failure is a Batch 1 stop condition until
resolved or truthfully reported.

---

## 22. Authoritative offline run

Create a single authoritative Batch 1 run under:

```text
experiments/capability-pressure-attribution-v0/runs/batch-1-offline/
```

At minimum preserve:

```text
manifest.json
assessments.json
summary.json
```

Optionally split per-case assessments into immutable files if that improves
traceability, but do not create unnecessary artifact volume.

The run manifest must include at least:

```text
run_id
phase
batch
starting_sha
definition_code_freeze_sha
execution_sha
model_calls = 0
provider_calls = 0
fixture_inventory_sha256
gate_definition_sha256
attribution_vocabulary_sha256
assessment_schema_sha256
historical_replay_sources
commands_or_procedures
validation_results
```

Do not include fabricated provider/model resource values.

---

## 23. Expected result categories

The Batch 1 result should be expressible as one of:

### Result A — Foundation established

Use only if:

- definitions are frozen and valid;
- trigger cases behave as predeclared;
- ambiguous cases remain ambiguous;
- selected Phase 5 replay matches durable conclusions;
- deterministic replay holds;
- no new architecture mechanism was introduced;
- no synthetic fixture is misreported as direct trigger evidence.

Allowed conclusion:

> A bounded deterministic capability-pressure and failure-attribution research
> instrument was established. It can distinguish negative, boundary, and
> synthetic trigger-positive cases and reproduce selected Phase 5 decisions
> without changing historical authority. This does not establish a final
> failure ontology or trigger any deferred capability by itself.

### Result B — Instrument incomplete

Use when implementation/tests are valid enough to preserve evidence but one or
more required distinctions cannot yet be represented without ambiguity or
unsupported rules.

Record the exact gaps. Do not broaden architecture to solve them automatically.

### Result C — Conflicting evidence

Use when historical replay conflicts materially with accepted Phase 5 durable
conclusions or direct evidence contradicts the operationalized gate logic.

Preserve the conflict and STOP architecture interpretation.

### Result D — Invalid batch execution

Use for baseline violation, source overwrite, core modification, unauthorized
model/provider execution, hidden deferred mechanism, or other plan violation.

---

## 24. Batch 1 decision gate

After the authoritative offline result, explicitly answer:

1. Can the current instrument separate observation, attribution, intervention,
   and trigger status?
2. Can it preserve ambiguity instead of forcing one cause?
3. Can it reproduce selected Phase 5 accepted decisions?
4. Does any **direct repository evidence**, not synthetic fixture evidence,
   satisfy a deferred capability trigger?
5. If yes, which exact gate and which direct evidence satisfy it?
6. If no, which next research pressure should be sampled without implementing a
   mechanism prematurely?

Do not automatically authorize Batch 2.

Batch 1 may recommend one next research direction, but subsequent execution
requires separate owner authorization.

---

## 25. Hard stop conditions

Immediately STOP substantive execution if any of the following occurs:

- required baseline cannot be reconciled safely;
- unrelated owner work would be overwritten;
- a required historical source is missing or materially contradictory;
- historical replay conflicts with accepted Phase 5 authority;
- implementing the evaluator would require changing `irisx/core`;
- a live model/provider call would be required;
- a deferred capability must be implemented merely to make the tests pass;
- synthetic evidence is the only basis for claiming a direct trigger;
- ambiguous attribution can only be removed by unsupported guessing;
- executable definitions change after authoritative-run freeze without a new
  explicit repair lifecycle;
- imported source material would need substantive modification;
- tests reveal a new unexplained integrity failure that invalidates the result.

Preserve partial evidence and report the exact stop reason.

---

## 26. Commit discipline

Prefer clear, bounded commits. A reasonable lifecycle is:

```text
1. docs: activate Phase 6 capability-pressure plan
2. research: define Phase 6 pressure and attribution model
3. experiment: freeze capability-pressure definitions and fixtures
4. experiment: implement offline pressure assessment substrate
5. test: validate trigger gates attribution and historical replay
6. experiment: record Batch 1 offline assessment evidence
7. docs: record Phase 6 Batch 1 handoff
8. docs: retire Phase 6 Batch 1 controlling plan
```

Exact commit count/messages may differ if a cleaner history is justified.

Do not squash away evidence boundaries after they have become part of the
recorded lifecycle.

Use normal push behavior. Do not force-push.

---

## 27. Durable handoff requirements

Create:

```text
docs/phase-6-capability-pressure-attribution-handoff.md
```

It must include at least:

```text
status
owner-authorized scope
required baseline
actual starting SHA
definition/code freeze SHA
authoritative offline-run SHA
research/result SHA
live model/provider calls: 0 / 0
files/directories added or modified
case inventory
historical replay sources
validation commands/results
full-suite result and known historical failures
exact supported conclusions
exact unsupported conclusions
direct-evidence trigger status by capability
synthetic trigger recognition status by capability
ambiguities/conflicts
next research recommendation
commit lineage
```

The handoff must explicitly say whether the candidate vocabulary remains
research-local and non-normative.

---

## 28. Controlling-plan retirement

After the durable handoff is committed, update this plan:

```text
Status: Retired — Phase 6 Batch 1 complete; see retirement record
```

Append a retirement record containing:

```text
retirement date
required/observed baseline
definition/code freeze SHA
authoritative run SHA
handoff SHA
model/provider calls authorized/performed: 0 / 0
validation summary
preservation summary
final Batch 1 result category
normal push result
final local/remote SHA
clean-tree status
ahead/behind result
```

The retirement commit is the Batch 1 lifecycle boundary, not additional
research evidence.

---

## 29. Owner-facing final report

After normal push, report concisely:

```text
Phase 6 Batch 1 result category
final commit SHA
origin/main SHA
clean/ahead-behind state
new research/experiment/handoff artifacts
case counts and pass/fail summary
historical replay result
full repository validation result
model/provider calls: 0
whether any direct-evidence capability trigger changed from Phase 5
exact next research recommendation
```

If no direct trigger changed, say so explicitly.

Do not start Phase 6 Batch 2.

---

## 30. Acceptance checklist

Batch 1 is complete only if all applicable items are satisfied:

- [ ] required baseline/preservation checks completed;
- [ ] all applicable `AGENTS.md` rules followed;
- [ ] Phase 6 research framing recorded;
- [ ] candidate shortfall/attribution vocabulary remains non-normative;
- [ ] eight Phase 5 capability gates operationalized without semantic drift;
- [ ] at least 24 trigger-pressure cases exist;
- [ ] at least 8 attribution collision/boundary cases exist;
- [ ] at least two ambiguity cases remain intentionally ambiguous;
- [ ] selected Phase 5 Batch 4 and Batch 6 evidence is replayed;
- [ ] replay does not rewrite historical evidence;
- [ ] synthetic evidence cannot produce direct-evidence trigger status;
- [ ] deterministic evaluator and summary tests pass;
- [ ] `irisx/core` unchanged;
- [ ] deferred mechanisms remain unimplemented;
- [ ] imported sources unchanged;
- [ ] live model/provider calls remain exactly 0;
- [ ] authoritative offline run recorded immutably;
- [ ] research result distinguishes direct, synthetic, inferred, unknown, and
      conflicting evidence;
- [ ] repository check completed;
- [ ] focused tests completed;
- [ ] full repository test inventory completed and historical failures
      distinguished from new failures;
- [ ] durable handoff committed;
- [ ] controlling plan retired;
- [ ] normal push completed;
- [ ] final repository state reported;
- [ ] Phase 6 Batch 2 not started.

---

## 31. Final scope statement

Phase 6 Batch 1 is intentionally substantial in implementation volume but
conservative in architecture authority.

Its purpose is to build the research machinery required to answer:

```text
Capability Pressure
        -> Failure Attribution
        -> Minimal Intervention Hypothesis
        -> Evidence-Triggered Architecture Experiment
```

It is successful if it makes future architecture expansion **harder to claim
without evidence**, not if it makes the architecture larger.

No model process, provider execution, routing system, recovery loop, persistence
runtime, workflow engine, model judge, specialization engine, external action,
or Phase 6 Batch 2 is authorized by this plan.

---

## 32. Retirement record

- **Retirement date:** 2026-09-08 Asia/Taipei
- **Required and observed starting baseline:**
  `4aa7256e2237e997425e8712638334088056037d`
- **Definition/code freeze and execution SHA:**
  `9b46fb55bbbe400823efcd08b3b09d74196e869b`
- **Authoritative offline-run evidence commit:**
  `89dc196357c991ece19f10ab6fbfbb5c8d83cb34`
- **Research/result commit:**
  `904053c271cf6091786213dbea2d6b7cc0d9e0f4`
- **Durable handoff:**
  `docs/phase-6-capability-pressure-attribution-handoff.md` at
  `90fa347617b6840f30cf4c21f38059ff667477ed`
- **Model/provider calls authorized and performed:** `0 / 0`
- **Paid API calls / model subprocesses:** `0 / 0`
- **Final result:** **Result A — Foundation established**

The plan was executed through these pre-retirement commits:

| Purpose | Commit |
| --- | --- |
| Activate owner-provided controlling plan | `38b9db1ec7f9460fc0861f22caeeac3f9124ef9b` |
| Record Phase 6 research framing | `8852de2302f4377727e263342d999340fa6b22e8` |
| Define gates and fixtures | `d5175af152a7d8423d5e2b7cca2b2d51e2e65840` |
| Implement offline assessment substrate | `136c7423c8091c5cdca00cba1fcf8f52d998b483` |
| Add focused tests | `b29f4f3f8adf7b025cc3f4a7869684182f49e61e` |
| Finalize definition/code freeze | `9b46fb55bbbe400823efcd08b3b09d74196e869b` |
| Preserve authoritative offline run | `89dc196357c991ece19f10ab6fbfbb5c8d83cb34` |
| Interpret Batch 1 evidence | `904053c271cf6091786213dbea2d6b7cc0d9e0f4` |
| Record durable handoff | `90fa347617b6840f30cf4c21f38059ff667477ed` |

The authoritative offline run recorded 34 valid assessments: 24 synthetic
pressure cases, eight attribution collision/boundary cases, and two selected
Phase 5 historical replays. All 34 matched their frozen expectations. The
primary pressure suite passed 8/8 negative controls, 8/8 near-trigger cases,
and 8/8 synthetic positive cases. Both intentional ambiguities remained
ambiguous, both historical replays matched, and conflicts were zero.

Every direct-evidence capability trigger remains `Not triggered`. Synthetic
positive fixtures recognized all eight gate predicates but did not mutate or
imply the direct-evidence trigger ledger.

Deterministic validation before retirement recorded:

- definition/schema suite: 9/9 PASS;
- trigger-gate suite: 8/8 PASS;
- attribution suite: 8/8 PASS;
- historical replay suite: 5/5 PASS;
- determinism suite: 5/5 PASS;
- focused Batch 1 total: 35/35 PASS;
- existing model-qualification suite: 75/75 PASS;
- authoritative run hash, freeze-byte, source-reference, replay, and
  deterministic-regeneration validation: PASS;
- repository check: PASS, 13 sources and 7 artifacts checked;
- full discovered inventory: 231 run, 230 pass, one failure, zero errors, zero
  skipped;
- sole failure: the unchanged historical Phase 4 frozen-plan hash contract in
  `HPIaContractTests.test_frozen_artifact_hashes_match_exact_bytes`;
- new failures or errors: zero.

Preservation checks found zero changes under `sources/`, `references/papers/`,
or `irisx/core/` from the required baseline. The historical Batch 4 and Batch 6
artifacts used by replay remain byte-identical to their recorded SHA-256
references. No historical plan, handoff, evidence file, or model run was
rewritten. No deferred mechanism or external framework dependency was added.

The exact next recommendation is a separately owner-authorized,
mechanism-free pressure-sampling definition batch: freeze a bounded set of
deterministically verifiable tasks under one unchanged admitted allocation and
predeclare how a real task-level miss will be distinguished from admission,
identity, and verifier failures. Collect direct failure-pressure evidence
before comparing a stronger allocation or testing retry. This is a
recommendation only and does not authorize Phase 6 Batch 2 or model execution.

The retirement commit is the Batch 1 lifecycle boundary. Its own full SHA, the
normal push result, final local/remote SHA, clean-tree state, and ahead/behind
result are necessarily reported after the commit and normal push in the
owner-facing final report; a commit cannot contain its own final identity or a
future push observation.
