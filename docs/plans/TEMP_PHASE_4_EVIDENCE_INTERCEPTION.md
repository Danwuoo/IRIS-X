# Temporary Phase 4 Evidence Binding and Interception Plan

Status: **Active temporary plan — second scoped Phase 4 batch**  
Date: **2026-08-30**  
Scope: Phase 4 mechanism experiments only  
Architecture authority: **None**  
Planning baseline: GitHub `main` = `9c0a66ebe1cc1738b51e688b4ec19d00d5bb6832` when this plan was prepared  
Sequence: **H-V1b → H-I1a → STOP / owner reassessment**

## 1. Purpose

The first scoped Phase 4 batch established task-local support for:

- H-M1a — registered source snapshot assertion;
- H-V1a — independent acceptance verification;
- H-O1a — structured instrumentation completeness.

Those results do not establish the parent H-M1, H-V1, or H-O1 hypotheses, a final architecture, or broader reliability.

The second scoped Phase 4 batch targets two remaining uncertainties:

1. whether evidence/provenance binding distinguishes verified success from merely correct output with insufficient or incorrect evidence;
2. whether pre-execution interception prevents prohibited side effects rather than only detecting them afterward.

The governing sequence is:

```text
H-V1a established narrow output-verification discrimination
    ↓
H-V1b test evidence/provenance binding
    ↓
H-I1a test pre-execution write prevention
    ↓
scoped result summary
    ↓
STOP / owner reassessment
```

No third mechanism is authorized by this plan.

## 2. Hard Scope Boundary

This plan authorizes exactly:

1. **H-V1b — Evidence / Provenance Binding**
2. **H-I1a — Pre-execution Write Prevention**

Do not start:

- H-P1;
- H-G1;
- H-W1;
- H-C1;
- H-R1;
- model-based experiments;
- retry/recovery experiments;
- routing/escalation experiments;
- architecture synthesis;
- Phase 5.

After H-I1a and the scoped result summary: **STOP**.

## 3. Global Research Discipline

All work must follow repository `AGENTS.md`, `research/AGENTS.md`, and `experiments/AGENTS.md`.

### 3.1 Imported systems are evidence, not authority

VANTA and Prime Intellect Verifiers may motivate mechanisms and experimental designs. Their schemas, runtimes, abstractions, or architectures are not inherited requirements.

### 3.2 Preserve outcome/evidence separation

Actual task outcome and epistemic/evidence status remain separate variables.

A correct output with insufficient evidence may remain an actual success while being ineligible for `verified_success`.

A verifier or interceptor decision is not empirical truth by definition.

### 3.3 Single-variable attribution

Within each experiment, hold all non-intervention variables fixed.

Do not combine evidence binding with output verification changes in H-V1b.

Do not combine interception with retries, repair, routing, or model behavior in H-I1a.

### 3.4 Resource boundary

Both experiments must remain:

- local;
- deterministic where practical;
- model-free;
- network-free;
- credential-free;
- paid-service-free;
- imported-source read-only.

Prefer Python standard library and minimal experiment-local code.

### 3.5 Source preservation

Do not modify:

```text
sources/
references/papers/
```

Do not mutate the registered VANTA fixtures.

Any state-changing H-I1a action must execute only inside an IRIS-X-authored copied workspace or temporary sandbox whose path is explicitly validated.

### 3.6 Invalid runs

Never overwrite run directories.

If a harness fails after producing artifacts:

1. preserve the attempt;
2. write an explicit failure record;
3. mark it invalid;
4. fix the harness;
5. rerun under a new run ID.

Invalid-run aggregates cannot be cited as completed evidence.

### 3.7 Cost and reliability claims

Report measured resource components separately.

Do not scalarize success, reliability, and lifecycle cost.

Short same-host timing is descriptive only.

Do not infer held-out, production, long-term, robustness, stateful, or recovery reliability unless directly tested.

## 4. Preflight

Before implementation:

1. reload latest `main`;
2. confirm whether it still descends from planning baseline `9c0a66ebe1cc1738b51e688b4ec19d00d5bb6832`;
3. inspect all applicable instructions;
4. inspect the first Phase 4 result summary and current candidate-hypothesis note;
5. inspect H-V1a implementation/results to preserve its separation boundary;
6. inspect the original VANTA evidence/verifier material relevant to evidence binding;
7. inspect the Prime Intellect bash interception example relevant to H-I1a;
8. inspect Phase 3 task contract and problem definition.

At minimum inspect:

```text
AGENTS.md
research/AGENTS.md
experiments/AGENTS.md
research/problem-definition.md
research/task-contract-docops-readonly-12.md
research/candidate-mechanism-hypotheses.md
research/phase-4-mechanism-experiment-results.md
experiments/exp-2026-08-30-docops-acceptance-verification/
tools/source_snapshot_assertion.py
corpus/sources.yaml
sources/predecessors/vanta/docs/02_specs/Evidence_Packet_and_Verifier_Runtime.md
sources/predecessors/vanta/docs/04_experiments/Experiment_002_Evidence_Verifier.md
sources/external/prime_intellect_verifiers_v1/environments/bash_interception/bash_interception/taskset.py
```

Do not silently copy source behavior into IRIS-X. Record what is source-stated versus IRIS-X-authored experiment design.

## 5. Hypothesis Refinements

Preserve the parent hypotheses in `research/candidate-mechanism-hypotheses.md`.

Add narrower Phase 4 refinements without rewriting historical results.

### 5.1 H-V1b — Evidence / Provenance Binding

Proposed falsifiable hypothesis:

> Holding actual output, actual outcome, system claim, task bytes, semantic verifier behavior, and execution path fixed, evidence-bound verification will distinguish success supported by complete path/hash evidence from success accompanied by missing, stale, crossed, unrelated, conflicting, or otherwise invalid evidence, while leaving actual outcome unchanged.

The primary causal variable is **evidence binding**, not semantic output correctness.

### 5.2 H-I1a — Pre-execution Write Prevention

Proposed falsifiable hypothesis:

> Holding the proposed action, copied-workspace starting state, policy, and state oracle fixed, pre-execution interception will prevent prohibited state mutations, whereas post-hoc checking can detect but cannot prevent those same mutations after execution.

The primary causal variable is **pre-execution interception**.

Do not infer model/tool-agent reliability from frozen deterministic actions.

## 6. Experiment 1 — H-V1b Evidence / Provenance Binding

Suggested experiment ID:

`exp-2026-08-30-docops-evidence-binding`

Exact date suffix may follow repository convention if execution occurs later.

### 6.1 Research question

When the produced result is semantically correct and the system claims success, can evidence-bound verification distinguish evidence that genuinely supports the result from evidence that is incomplete, stale, wrong, crossed, unrelated, or conflicting?

### 6.2 Critical isolation rule

For every paired challenge, hold fixed:

- task;
- source fixture bytes;
- registered source snapshot;
- producer output;
- actual outcome;
- semantic output-verifier result;
- system claim;
- task order;
- repetition;
- execution path;
- resource envelope.

All producer outputs in the main H-V1b challenge set must be semantically correct under the task contract.

Do not re-test wrong-output discrimination as the primary manipulation.

### 6.3 Arms

#### `semantic-only-v0`

Eligibility for success evidence is based on:

- claimed success;
- semantically correct output;

without enforcing that the supplied evidence envelope completely and correctly binds the declared input bytes.

This is a conceptual experiment control, not a claim that the Phase 4 H-V1a implementation is identical to this arm.

#### `evidence-bound-v0`

A claimed-success result is eligible for `verified_success` only when:

- semantic output verification succeeds;
- every required input evidence entry is present;
- each evidence path is valid and within the declared fixture boundary;
- each path identifies the intended declared input;
- SHA-256 is recomputed from the actual bytes and matches;
- no required evidence is stale, crossed, unrelated, duplicated-conflicting, or missing;
- the evidence envelope is internally consistent.

The treatment must not consume precomputed challenge-validity labels.

### 6.4 Frozen challenge set

Build deterministic evidence variants against semantically correct outputs.

At minimum include:

1. **complete-correct**
   - all required evidence entries;
   - correct paths;
   - correct recomputed hashes.

2. **missing-required-entry**
   - one required input omitted.

3. **wrong-hash**
   - correct path, deliberately incorrect SHA-256.

4. **stale-hash**
   - hash sourced from a different frozen byte version or deterministic stale-value fixture authored inside experiment inputs;
   - do not modify imported source to create staleness.

5. **crossed-evidence**
   - path/hash association from two declared inputs deliberately crossed where a multi-input task permits it;
   - use a documented deterministic fallback when a task has only one declared input.

6. **unrelated-existing-file**
   - evidence points to an existing file that is not a declared input for that task.

7. **conflicting-duplicate**
   - duplicate evidence for the same declared input with conflicting hash or metadata.

8. **correct-hash-wrong-path**
   - hash may match some known bytes, but the declared evidence path is not the intended input path.

If a variant cannot be meaningfully instantiated for a task, use a predeclared deterministic applicability/fallback rule. Do not silently drop cases after observing treatment behavior.

Freeze and hash the complete challenge artifact before measured execution.

### 6.5 Actual outcome and evidence status

Actual outcome must be adjudicated independently from evidence eligibility.

For the main H-V1b challenge set:

```text
actual_outcome = success
```

for semantically correct and non-mutating outputs.

The evidence mechanism determines epistemic/evidence status, such as:

- sufficient / verified;
- insufficient;
- invalid binding;
- unresolved, if genuinely unavoidable.

Do not relabel actual success as actual failure solely because evidence is bad.

### 6.6 Primary dependent variables

Report separately:

- actual success count;
- `verified_success` eligibility;
- `unverified_success` / insufficient-evidence count;
- false verified-success acceptance;
- false rejection of complete-correct evidence;
- evidence-reason category;
- verifier/harness invalid count;
- repeat agreement;
- evidence verification wall/CPU time;
- evidence artifact bytes;
- terminal artifact bytes.

Avoid collapsing these into one scalar score.

### 6.7 Support condition

H-V1b is `Supported — task-local` only if, on a valid finite-sample run:

- complete-correct evidence is accepted as sufficient;
- every predefined invalid/insufficient evidence variant is denied `verified_success` eligibility;
- actual outcome remains success and unchanged across paired arms;
- semantic verifier result remains unchanged across paired arms;
- no challenge-validity labels enter the treatment interface;
- results are deterministic under the declared horizon.

### 6.8 Rejection / redesign conditions

Record `Mixed evidence`, `Rejected — task-local`, or `Not established` rather than forcing support if:

- complete-correct evidence is rejected;
- invalid evidence is accepted as sufficient;
- actual outcome changes because of evidence manipulation;
- the treatment consumes precomputed case-validity labels;
- evidence variants are trivially identified by case ID rather than real path/hash checks;
- challenge construction depends on mutating imported source;
- the experiment conflates evidence binding with output correctness.

### 6.9 Interpretation boundary

A positive result establishes only that the tested path/hash evidence contract discriminates these frozen evidence-integrity challenges on the selected development tasks.

It does not establish:

- universal evidence sufficiency;
- causal provenance beyond registered local bytes;
- trustworthy model-generated citations;
- real-world data lineage;
- complete parent H-V1;
- architecture requirements.

Complete and interpret H-V1b before H-I1a begins.

## 7. Experiment 2 — H-I1a Pre-execution Write Prevention

Suggested experiment ID:

`exp-2026-08-30-preexecution-write-interception`

### 7.1 Research question

For identical deterministic proposed actions, does pre-execution interception prevent prohibited copied-workspace mutations that post-hoc checking can only detect after execution?

### 7.2 Environment boundary

Do not run destructive tests against the repository working tree or imported source.

Create a small IRIS-X-authored source template under experiment inputs, then instantiate a fresh copied workspace per episode under an experiment-local run sandbox or OS temporary directory.

The harness must verify that the action target resolves inside the copied workspace before any action executes.

No action may address:

- repository root outside the experiment sandbox;
- `sources/`;
- `references/papers/`;
- home directory;
- system paths;
- network paths.

Prefer Python standard-library filesystem actions over shell commands when they provide equivalent causal tests.

### 7.3 Frozen starting state

Define and hash a small workspace template containing multiple files/directories sufficient to test:

- existing-file content;
- file existence;
- directory membership;
- rename/move state;
- newly created files.

Every episode starts from a fresh byte-identical copy.

### 7.4 Frozen proposed actions

At minimum include prohibited actions:

1. overwrite an existing protected file;
2. append to an existing protected file;
3. delete a protected file;
4. create a forbidden new file;
5. rename or move a protected file;
6. replace content via another equivalent write primitive if meaningfully distinct.

Include positive controls:

7. permitted read-only action;
8. optionally a permitted write to an explicitly allowed scratch path, if needed to show the interceptor is policy-sensitive rather than reject-all.

All actions must be deterministic and fixture-local.

### 7.5 Arms

#### `post-hoc-check-v0`

Execute the proposed action without pre-execution blocking, then compare workspace state against the frozen policy/state oracle.

This arm may detect the prohibited mutation after it happened.

Do not automatically restore state before the empirical post-state snapshot is recorded.

Each episode uses a fresh copy, so restoration is unnecessary for experimental isolation.

#### `pre-execution-intercept-v0`

Evaluate the identical proposed action against the same frozen policy before execution.

If prohibited:

- block before the mutation primitive executes;
- produce an explicit blocked decision/result;
- then compute the empirical workspace post-state.

If permitted:

- allow execution;
- record post-state normally.

### 7.6 Empirical truth

The primary empirical truth is the copied workspace before/after state.

Compute at least:

- per-file path set;
- file SHA-256;
- relevant directory membership;
- expected/observed mutation class.

Do not define success as "interceptor said blocked."

A prohibited action is empirically prevented only if the protected post-state remains unchanged under the state oracle.

### 7.7 Primary dependent variables

Report separately by arm:

- prohibited actions proposed;
- prohibited actions executed;
- prohibited mutations observed;
- prohibited mutations prevented;
- post-hoc detections;
- false blocks of permitted actions;
- allowed actions completed;
- terminal/harness invalid count;
- repeat agreement;
- interception/checking wall/CPU time;
- artifact bytes.

### 7.8 Support condition

H-I1a is `Supported — task-local` only if:

- post-hoc arm demonstrates at least one prohibited mutation actually occurs before detection;
- pre-execution arm prevents every predefined prohibited mutation in the finite sample;
- permitted read-only control is not falsely blocked;
- any permitted-write control, if included, is not falsely blocked;
- starting state is identical across paired episodes;
- proposed action identity is identical across arms;
- empirical post-state confirms prevention;
- results are deterministic under the declared horizon.

### 7.9 Rejection / redesign conditions

Record mixed/rejected evidence if:

- a prohibited mutation occurs despite pre-execution interception;
- a permitted control is blocked;
- action identity differs between arms;
- sandbox boundary enforcement is ambiguous;
- post-state truth is inferred from interceptor logs rather than measured;
- repository/imported-source mutation occurs;
- the experiment silently adds repair/retry/recovery.

Any accidental repository/imported-source mutation invalidates the run and requires immediate stop and explicit preservation/reporting of the failure.

### 7.10 Interpretation boundary

A positive result supports only a narrow statement about deterministic local pre-execution interception over the tested copied-workspace mutation classes.

It does not establish:

- complete tool safety;
- shell/process isolation;
- OS sandbox security;
- model compliance;
- adversarial bypass resistance;
- stateful long-term reliability;
- recovery reliability;
- architecture requirements.

## 8. Experiment Artifact Discipline

Use the existing lightweight pattern:

```text
experiments/<experiment-id>/
  README.md
  inputs/
  scripts/
  tests/
  runs/
    <run-id>/
      run-manifest.json
      raw/
      results.json
      interpretation.md
```

Additional experiment-local files are allowed only when justified.

Definitions, frozen inputs, raw records, aggregates, and interpretation must remain distinguishable.

## 9. Scoped Research Summary

After both experiments are complete and interpreted, create or append a concise durable research result artifact.

Prefer a new batch-specific note if that preserves historical clarity, for example:

```text
research/phase-4-evidence-interception-results.md
```

For H-V1b and H-I1a separately record:

- exact hypothesis;
- experiment/run ID;
- directly observed result;
- support status;
- evidence classification;
- applicable reliability observation;
- cost observation;
- narrow supported constraint, if any;
- remaining uncertainty.

Allowed status language:

- `Supported — task-local`
- `Mixed evidence`
- `Rejected — task-local`
- `Not established`
- `Not evaluated`
- `Invalid run`

Do not rank mechanisms into a winner.

Do not synthesize Phase 5 architecture.

## 10. Candidate-Hypothesis Maintenance

After valid interpretation:

- update `research/candidate-mechanism-hypotheses.md` minimally;
- record H-V1b and H-I1a status accurately;
- preserve parent H-V1 and H-I1 as not fully established unless evidence truly covers them;
- keep all untested mechanisms explicitly `Not evaluated`.

Do not rewrite prior Phase 4 results.

## 11. Navigation

Update only minimal navigation:

```text
research/README.md
experiments/README.md
```

Do not expand root navigation unless necessary.

## 12. Validation

At minimum run:

```powershell
python tools\repository_check.py
```

For every changed Python file:

```powershell
python -m py_compile <changed-python-files>
```

Run targeted tests that establish:

### H-V1b

- frozen challenge reproducibility;
- actual-outcome/evidence-status separation;
- verifier interface excludes challenge-validity labels;
- complete-correct evidence passes;
- invalid evidence variants fail evidence sufficiency;
- imported source remains unchanged.

### H-I1a

- copied workspace starts byte-identically;
- sandbox boundary checks reject paths outside allowed workspace;
- post-hoc arm truly mutates prohibited state before detecting it;
- pre-execution arm prevents the same mutation;
- permitted control is not falsely blocked;
- post-state oracle is independent of interceptor decision.

Also run:

```powershell
git diff --check
```

Before completion confirm no modifications under:

```text
sources/
references/papers/
```

and no mutation of prior completed experiment run artifacts.

Do not claim a command passed unless it was executed.

## 13. Commit Discipline

Prefer coherent evidence milestones:

1. define second scoped Phase 4 batch and sub-hypotheses;
2. define/freeze H-V1b;
3. execute/record H-V1b;
4. define/freeze H-I1a;
5. execute/record H-I1a;
6. record scoped summary, update minimal navigation/hypothesis status, validate, and retire this temporary plan.

If a run fails, preserve the invalid run and make the correction traceable.

Do not rewrite history to hide failures.

## 14. Exit Criteria

This plan is complete only when:

- H-V1b is explicitly defined;
- H-V1b frozen evidence challenges are inspectable and reproducible;
- a valid H-V1b run is completed and interpreted;
- actual success is kept separate from evidence sufficiency;
- H-I1a is explicitly defined;
- H-I1a copied-workspace starting state and proposed actions are frozen;
- a valid H-I1a run is completed and interpreted;
- empirical post-state, not interceptor self-report, determines mutation prevention;
- no imported source/paper was modified;
- no model/network/paid service was used;
- invalid attempts, if any, are preserved and disqualified;
- targeted tests and repository validation pass;
- candidate-hypothesis status is updated accurately;
- a scoped result summary exists;
- this temporary plan is marked retired;
- no third mechanism or Phase 5 work has started.

## 15. Hard Stop

After:

```text
H-V1b
H-I1a
scoped result summary
validation
temporary-plan retirement
```

**STOP.**

Do not automatically select another hypothesis.

The next mechanism or architecture-synthesis decision requires owner review of the accumulated evidence.
