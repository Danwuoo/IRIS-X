# Temporary Phase 4 Mechanism Experiments Plan

Status: **Active temporary plan — sequential single-mechanism experiments**  
Date: **2026-08-30**  
Scope: Phase 4 mechanism experiments only  
Architecture authority: **None**  
Research authority: `research/problem-definition.md` remains the provisional project-level research problem  
Planning baseline: GitHub `main` was `ddfb3eca071a34f37bad275254f21ecf189e4cf4` when this plan was prepared; a 2026-08-30 fetch confirmed local `main` and `origin/main` still resolved to that commit before Phase 4 edits  
Removal / retirement condition: retire this plan after the three scoped experiments are completed or explicitly invalid/deferred, their interpretations are recorded, repository validation passes, and no additional Phase 4 mechanism has been started.

## 1. Why Phase 4 Exists

Phase 3 established:

- one bounded development task distribution;
- one explicit task/evaluation contract;
- independent recording of actual outcome, evidence status, system claim, and execution-path attributes;
- task-local success, operational-repeatability, and lifecycle-cost observables;
- corpus-grounded candidate mechanisms and falsifiable hypotheses;
- a completed deterministic baseline experiment.

Phase 3 did not establish a final architecture or any mechanism as an IRIS-X requirement.

Phase 4 therefore exists to produce discriminating evidence about individual mechanisms.

The governing progression is:

```text
Phase 3 baseline
    -> isolated mechanism intervention
    -> paired empirical result
    -> task-local support / rejection / uncertainty
    -> additional isolated mechanism experiments
    -> later supported constraints
    -> only later architecture synthesis
```

Phase 4 must not use implementation volume as evidence of progress.

## 2. Phase 4 Scope

This temporary plan authorizes exactly three mechanism experiments:

1. **H-M1a — Registered Source Snapshot Assertion**
2. **H-V1a — Independent Acceptance Verification**
3. **H-O1a — Structured Instrumentation Completeness**

No other H-* hypothesis is authorized by this plan.

The following are explicitly prohibited in this scoped batch:

- `H-I1`;
- `H-P1`;
- `H-G1`;
- `H-W1`;
- `H-C1`;
- `H-R1`;
- model-based experiments;
- paid APIs;
- network use;
- new agent runtime implementation;
- Phase 5 architecture synthesis.

After H-O1a, **STOP**.

Do not automatically start any fourth experiment or additional Phase 4
mechanism.

## 3. Research Priority Versus Execution Order

The primary substantive Phase 4 question is H-V1a because it directly addresses RQ2, evidence of success.

However, the execution order is:

```text
H-M1a
  -> H-V1a
  -> H-O1a
  -> Phase 4 scoped result summary
  -> STOP
```

H-M1a is executed first because Phase 3 identified a lightweight provenance hardening gap: the run manifest records `source_snapshot_id` and `source_tree_oid_at_code_commit`, but the baseline runner does not currently resolve the registered snapshot through `corpus/sources.yaml` and assert that the observed source tree equals the registered snapshot tree.

Running this small integrity experiment before creating further Phase 4 evidence avoids building new results on an unasserted provenance relation.

This ordering does not establish manifest/provenance mechanisms as more important than evidence-aware acceptance.

## 4. Hypothesis Refinements

The current parent hypotheses in `research/candidate-mechanism-hypotheses.md` remain preserved. Phase 4 should add narrower sub-hypotheses rather than silently rewriting the originals.

### H-M1a — Registered Source Snapshot Assertion

> Resolving a run's `source_id` and `source_snapshot_id` through `corpus/sources.yaml` and asserting that the observed Git source-tree OID equals the registered snapshot tree OID will detect deliberately injected source-identity mismatches that a record-only provenance path does not detect, while accepting the valid registered identity.

This tests only a narrow provenance-integrity part of H-M1.

It does not establish the complete H-M1 parent hypothesis about manifests, terminal records, resource ledgers, or all forms of configuration mismatch.

### H-V1a — Independent Acceptance Verification

> Holding producer output, system claim, task bytes, evidence/path-hash substrate, and actual-outcome adjudication fixed, requiring an independent deterministic verification decision before accepting a claimed success will reduce false-success acceptance relative to claim-only acceptance on frozen invalid-output challenges, without rejecting semantically valid claimed-success outputs in the evaluated finite sample.

This deliberately separates two mechanisms that are bundled in the current H-V1 parent:

- independent acceptance verification; and
- evidence/provenance binding.

Path/hash evidence remains fixed in H-V1a.

A possible future **H-V1b** about missing, stale, or incorrect evidence bindings is explicitly deferred and must not be executed under this plan.

### H-O1a — Structured Instrumentation Completeness

> Holding task, control behavior, evaluator, resource envelope, and execution policy fixed, structured profiling will reduce missingness for a predeclared set of runtime-profile fields while preserving paired output and actual-outcome behavior. Artifact-size and timing overhead will be measured descriptively rather than assumed.

This is a narrower Phase 4 refinement of H-O1.

No unsupported wall-time threshold is part of the hypothesis.

## 5. Global Experimental Discipline

All three experiments must follow these rules.

### Fixed research boundary

Use the existing development distribution:

`taskdist-2026-08-28-vanta-docops-readonly-12`

Do not claim that these 12 fixtures represent:

- held-out generalization;
- real workloads;
- model capability;
- broad agentic intelligence;
- long-term reliability;
- stateful reliability;
- robustness;
- recovery reliability;
- lifecycle-cost optimality.

### Source preservation

Do not modify:

```text
sources/
references/papers/
```

Do not mutate the selected VANTA fixtures.

Synthetic mismatch/challenge cases must live under IRIS-X-authored experiment inputs or run artifacts.

### Resource boundary

All three experiments must remain:

- local;
- deterministic where practical;
- network-free;
- model-free;
- credential-free;
- paid-service-free;
- imported-source read-only.

Do not introduce model/API access.

### Single-intervention attribution

Within each experiment:

- freeze all components not explicitly designated as the intervention;
- use paired cases whenever possible;
- keep actual outcome separate from mechanism decision;
- keep evidence status separate from actual outcome;
- keep execution-path fields separate;
- do not alter multiple research variables and attribute the result to one mechanism.

### Evidence discipline

A verifier decision is not empirical truth by definition.

A profiler record is not proof that every lifecycle cost is captured.

A registered Git tree proves only the declared local snapshot identity, not upstream provenance.

Fixture oracles remain declared local evaluation oracles; their broader scientific validity is `Not established`.

### Lifecycle cost

Report observable cost components as a vector.

Do not construct a universal scalar lifecycle-cost score.

Continue to record unavailable components as `Unknown` where relevant.

### Invalid runs

Never overwrite a run directory.

If a runner or harness fails after producing artifacts:

1. preserve the failed attempt;
2. write an explicit failure record;
3. mark it invalid;
4. fix the harness;
5. use a new run ID for the rerun.

Do not cite invalid-run aggregates as completed results.

## 6. Work Package 0 — Repository and Hypothesis Preflight

Before implementation:

1. fetch/reload latest `main`;
2. read all applicable repository instructions;
3. inspect current Phase 3 research and experiment artifacts;
4. inspect the actual current baseline runner and run artifacts;
5. inspect `corpus/sources.yaml`;
6. verify whether repository state has changed since planning baseline `ddfb3eca071a34f37bad275254f21ecf189e4cf4`.

At minimum read:

```text
AGENTS.md
research/AGENTS.md
experiments/AGENTS.md
research/problem-definition.md
research/README.md
experiments/README.md
research/task-distribution-selection.md
research/task-contract-docops-readonly-12.md
research/first-cycle-operationalization.md
research/candidate-mechanism-hypotheses.md
docs/plans/TEMP_PHASE_3_RESEARCH_OPERATIONALIZATION.md
experiments/exp-2026-08-28-docops-readonly-baseline/README.md
experiments/exp-2026-08-28-docops-readonly-baseline/scripts/run_baseline.py
experiments/exp-2026-08-28-docops-readonly-baseline/runs/pilot-20260828-local-rerun-01/
corpus/sources.yaml
```

Also inspect only the relevant original corpus material for the mechanism being tested.

Before experiment execution, add the Phase 4 sub-hypotheses to `research/candidate-mechanism-hypotheses.md` without deleting the parent hypotheses.

Explicitly record H-V1b as deferred.

## 7. Work Package 1 — H-M1a Registered Source Snapshot Assertion

Suggested experiment ID:

`exp-2026-08-30-source-snapshot-assertion`

Suggested location:

```text
experiments/exp-2026-08-30-source-snapshot-assertion/
```

### Research question

Does resolving the registered source snapshot and enforcing exact tree identity detect provenance mismatches that the current record-only behavior would merely record?

### Control

`record-only-v0`

The control emulates the current provenance behavior:

- records `source_id`;
- records `source_snapshot_id`;
- records observed source tree OID;
- does not resolve and enforce equality with the registered snapshot OID.

### Treatment

`registry-assert-v0`

The treatment:

1. resolves `source_id` in `corpus/sources.yaml`;
2. resolves the specified `source_snapshot_id`;
3. verifies the expected active/current snapshot relationship where defined by the registry;
4. obtains the registered snapshot tree OID;
5. obtains the observed Git tree OID for the registered source path at the code commit;
6. asserts exact equality;
7. fails closed before experiment episodes if the identity cannot be resolved or does not match.

Do not construct a large provenance framework.

### Challenge cases

At minimum include frozen cases covering:

- correct source ID + correct snapshot ID + matching observed tree OID;
- unknown source ID;
- unknown snapshot ID;
- mismatching observed tree OID;
- snapshot/source relationship inconsistency if representable without modifying the live corpus registry.

Synthetic mismatch values must not require modifying `sources/` or the registered live snapshot.

### Dependent variables

Record at least:

- mismatch expected / not expected;
- mismatch detected / not detected;
- false-positive valid-identity rejection;
- resolution failure reason;
- run validity;
- deterministic repeat agreement;
- small local verification-cost fields.

### Support condition

H-M1a is task-locally supported only if:

- the valid registered identity is accepted;
- every predefined mismatch case is rejected by the treatment;
- the record-only control misses at least one mismatch that the treatment detects;
- results are deterministic across the declared repetition horizon.

Do not invent a probabilistic reliability claim from deterministic synthetic cases.

### Rejection / redesign condition

Record H-M1a as rejected, mixed, or requiring redesign if:

- valid registered identity is rejected;
- a predefined mismatch passes treatment;
- treatment cannot resolve the current registry deterministically;
- detection depends on mutation of imported source;
- the experiment's negative cases leak directly into hard-coded expected answers rather than exercising the actual resolver/assertion.

### Post-result hardening

Only after a valid H-M1a result supports the assertion:

- add the smallest practical registered-snapshot assertion to Phase 4 execution paths;
- it is permissible to harden the Phase 3 baseline runner's startup validation so that its documented source-snapshot mismatch invalid-run condition is actually enforced;
- preserve all existing Phase 3 run artifacts unchanged;
- do not create a general provenance subsystem.

If H-M1a is not supported, do not integrate the assertion as though it were established.

## 8. Work Package 2 — H-V1a Independent Acceptance Verification

Suggested experiment ID:

`exp-2026-08-30-docops-acceptance-verification`

Suggested location:

```text
experiments/exp-2026-08-30-docops-acceptance-verification/
```

### Research question

For frozen claimed-success outputs on the existing 12-task development distribution, does independent deterministic verification reduce accepted false successes relative to claim-only acceptance without rejecting semantically valid outputs?

### Essential isolation rule

H-V1a must vary **acceptance policy only**.

Hold fixed:

- task and fixture bytes;
- source snapshot;
- produced output;
- system claim;
- evidence/path-hash completeness;
- resource envelope;
- actual-outcome adjudication;
- challenge case;
- task order;
- repetitions.

Do not inject missing/stale/wrong evidence hashes in H-V1a.

Those belong to deferred H-V1b.

### Arms

#### `claim-only-v0`

Accept if the system claims success.

This arm does not independently validate output correctness before accepting the success claim.

#### `independent-verify-v0`

Accept only when:

```text
system claims success
AND
independent verifier returns accept
```

The verifier must not receive precomputed `actual_outcome`, challenge validity, or expected accept/reject labels.

It may use the declared fixture oracle and source/evidence data required by the experiment contract.

### Frozen challenge set

Create and freeze deterministic challenge cases before the measured run.

For every task where the transformation is well-defined, include:

1. **canonical valid**
   - exact semantically correct output;
   - claim success.

2. **semantic-equivalent valid**
   - different JSON serialization, ordering, or irrelevant formatting;
   - parsed semantic result unchanged;
   - claim success.

3. **omission invalid**
   - deterministically remove required content;
   - claim success.

4. **fabrication invalid**
   - deterministically insert unexpected or fabricated content;
   - claim success.

5. **corruption / wrong-value invalid**
   - deterministically alter required semantic content;
   - claim success.

If a generic mutation operator is not applicable to a task, use an explicitly documented deterministic fallback rather than silently dropping the case.

The challenge generator must verify that:

- valid semantic variants remain semantically equal to the oracle;
- invalid variants are semantically unequal under the task contract.

The independent verifier must not branch on mutation type.

### Actual outcome

Actual outcome remains independently adjudicated under the existing Phase 3 task contract.

Do not define actual success as "verifier accepted."

### Primary measurements

For both arms report paired:

- true accept;
- true reject;
- false accept;
- false reject;
- accepted-success count;
- rejected-success count;
- verifier error/invalid count;
- verification wall/CPU time where available;
- additional output/artifact bytes.

Do not collapse these into one scalar.

### Support condition

H-V1a is task-locally supported when, on a valid completed finite-sample run:

- treatment has fewer false accepts than claim-only control;
- canonical valid outputs are not newly rejected;
- semantic-equivalent valid outputs are not newly rejected;
- treatment does not alter actual outcome;
- no challenge validity labels leak into verifier decisions.

A zero false-accept result may be reported descriptively if observed, but it does not establish broad verifier reliability.

### Mixed/rejection conditions

Record mixed evidence or redesign rather than forcing a positive conclusion if:

- invalid outputs are still accepted;
- semantically valid variants are falsely rejected;
- verifier implementation directly shares challenge labels;
- verifier and actual-outcome adjudicator are circularly defined;
- challenge construction is too trivial to distinguish acceptance behavior;
- a harness error invalidates the comparison.

### Interpretation boundary

A positive H-V1a result supports only the narrow proposition that independent deterministic success gating improves acceptance discrimination under this fixed oracle-backed development protocol.

It does not establish:

- a universal verifier;
- reliable model judging;
- production evidence sufficiency;
- generalization to other task distributions;
- H-V1b provenance/evidence sufficiency;
- final IRIS-X architecture.

## 9. Work Package 3 — H-O1a Structured Instrumentation Completeness

Suggested experiment ID:

`exp-2026-08-30-docops-profile-instrumentation`

Suggested location:

```text
experiments/exp-2026-08-30-docops-profile-instrumentation/
```

### Research question

Can structured profiling capture a richer declared runtime profile while preserving behavior on identical deterministic episodes, and what local artifact/time overhead is observed?

### Configuration

Prefer the existing `structured-readonly-v0` behavior because it succeeds on all 12 current development tasks and avoids mixing unsupported-handler failures into the instrumentation comparison.

Use:

```text
12 tasks
× 2 instrumentation arms
× 3 repetitions
= 72 paired episodes
```

unless current repository evidence requires a different equally controlled horizon.

### Arms

#### `instrumentation-off-v0`

Capture only the existing experiment-required terminal and cost fields.

#### `instrumentation-on-v0`

Execute the identical task/control path while adding a predeclared structured profile.

Do not add behavior-changing retries, verification policies, routing, caching, or optimization.

### Predeclared profile coverage

Before running, define a fixed profile-field contract.

It may include task-locally meaningful fields such as:

- episode/stage identity;
- generation/invocation stage duration;
- evaluation stage duration;
- read operation count;
- bytes read;
- serialized output bytes;
- terminal status;
- instrumentation event count;
- profiler failure/error field.

Do not add fields merely to maximize field count.

Do not adopt NeMo Agent Toolkit as an IRIS-X dependency merely because its profiling concepts informed the hypothesis.

A standard-library task-local profiler is sufficient if it answers the research question.

### Primary measurements

Report:

- declared profile-field coverage;
- missing required profile fields;
- paired produced-output equality;
- paired actual-outcome equality;
- paired terminal-status equality;
- invalid/harness failures;
- instrumentation artifact bytes;
- total output bytes;
- measured wall/CPU timing fields.

### Timing interpretation

Single-host short-duration timing is noisy.

Report raw paired measurements and descriptive aggregates.

Do not invent:

- a meaningful overhead threshold;
- stable performance superiority/inferiority;
- production latency claims.

If timing direction is unstable, label the timing-overhead magnitude `Not established`.

### Support condition

H-O1a is task-locally supported if:

- structured instrumentation increases coverage of the predeclared profile contract;
- paired task outputs remain unchanged;
- paired actual outcomes remain unchanged;
- no new invalid episodes arise from instrumentation.

Artifact/time overhead is reported as an observed trade-off, not a prerequisite for claiming measurement completeness.

### Rejection / redesign condition

Record mixed/rejected evidence if:

- profiler changes output or actual outcome;
- instrumentation causes run instability;
- target fields remain missing;
- the field contract is defined after observing results;
- instrumentation requires adopting an unrelated framework stack.

## 10. Experiment Artifact Structure

Each experiment should retain the existing lightweight separation discipline.

A suitable structure is:

```text
experiments/<experiment-id>/
  README.md
  inputs/
  scripts/
  runs/
    <run-id>/
      run-manifest.json
      raw/
      results.json
      interpretation.md
```

Exact names may differ when the experiment needs a clearly justified additional artifact.

Do not create speculative framework hierarchies.

Definitions, raw records, aggregates, and interpretation must remain distinguishable.

## 11. Phase 4 Scoped Research Summary

After all three experiments have valid results, create one concise IRIS-X research note, suggested:

```text
research/phase-4-mechanism-experiment-results.md
```

It should record, separately for each sub-hypothesis:

- hypothesis tested;
- exact experiment/run;
- directly observed result;
- support status;
- evidence boundary;
- cost/reliability observations;
- remaining uncertainty;
- whether any narrow supported constraint is justified.

Allowed status language includes:

- `Supported — task-local`
- `Mixed evidence`
- `Rejected — task-local`
- `Not established`
- `Not evaluated`
- `Invalid run`

Do not turn this note into Phase 5 architecture synthesis.

Do not rank the three mechanisms into one scalar winner.

## 12. Navigation

Update only minimal navigation where needed:

```text
research/README.md
experiments/README.md
```

Update root `README.md` only if the repository entry workflow materially changes.

Do not duplicate experiment contents into navigation documents.

## 13. Phase 4 Scoped Exit Criteria

This temporary Phase 4 plan is complete only when:

- H-M1a is explicitly defined;
- a valid H-M1a run is completed and interpreted;
- any provenance hardening applied afterward is supported by the experiment and remains lightweight;
- H-V1a is explicitly defined;
- its frozen challenge set is inspectable and reproducible;
- a valid H-V1a run is completed and interpreted;
- actual outcome and acceptance decision remain separate;
- H-O1a is explicitly defined;
- its instrumentation field contract is frozen before execution;
- a valid H-O1a run is completed and interpreted;
- all invalid attempts, if any, are preserved and disqualified;
- Phase 4 sub-hypotheses and result statuses are recorded in research artifacts;
- imported source material remains unchanged;
- no network/model/paid service was used;
- repository checks pass;
- changed Python scripts compile;
- navigation is updated minimally;
- no final runtime or architecture specification has been introduced;
- H-I1, H-P1, H-G1, H-W1, H-C1, H-R1, and other mechanisms remain untouched;
- the temporary plan is marked retired with links to closure artifacts.

## 14. Validation

At minimum run from repository root:

```powershell
python tools\repository_check.py
```

For all changed Python files:

```powershell
python -m py_compile <changed-python-files>
```

Run targeted experiment validation/tests where implemented.

Report actual commands and outcomes.

Do not claim a check passed unless it was executed.

## 15. Hard Stop

After:

```text
H-M1a
H-V1a
H-O1a
Phase 4 scoped summary
validation
temporary-plan retirement
```

**STOP.**

Do not automatically choose or implement a fourth mechanism.

Do not begin Phase 5.

The next mechanism or architecture-synthesis decision belongs to a separate owner review of the Phase 4 evidence.
