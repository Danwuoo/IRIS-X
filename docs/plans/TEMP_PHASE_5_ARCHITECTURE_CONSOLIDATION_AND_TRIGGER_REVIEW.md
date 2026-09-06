# TEMP Phase 5 — Architecture Consolidation and Capability Trigger Review

Status: **Retired — Phase 5 closed by Decision A; see Section 30**
Date: **2026-09-06 Asia/Taipei**  
Repository: **Danwuoo/IRIS-X**  
Required baseline `main`: **`979c443ece39b5631ac8afddabb25229aea958a8`**  
Phase: **Phase 5 — provisional architecture development**  
Batch: **Batch 7**  
Batch goal: **consolidate Phase 5 Batch 1–6 evidence into an explicit provisional architecture state, re-evaluate deferred capability triggers, and decide whether Phase 5 can close or which next experiment is evidence-triggered**  
Architecture authority: **Evidence-backed but provisional; no final architecture or production claim**  
Live provider/model call ceiling: **0**  
Preferred core/code impact: **documentation/research only; no `irisx.core` changes**  
Hard terminal boundary: **STOP after consolidation, trigger decision, durable handoff, plan retirement, and normal push**

---

## 1. Owner authorization and scope

This plan is the new owner-authorized scope for Phase 5 Batch 7.

Phase 4 remains closed.

Phase 5 Batch 1 through Batch 6 remain complete and retired. Their evidence, run records, test results, plans, handoffs, frozen task definitions, compatibility records, and historical failures are immutable evidence for this batch.

Batch 7 is a **decision-gate batch**.

It does not authorize a new execution mechanism.

It does not authorize a new model task.

It does not authorize routing, persistence, recovery, a model judge, a second provider, or a second model.

The single question is:

> Given the complete Phase 5 Batch 1–6 evidence, what parts of the provisional IRIS-X architecture are now directly supported within the observed scope, what remains provisional or unevaluated, which deferred capability triggers are actually satisfied, and is the evidence sufficient to close Phase 5 without inventing another experiment?

---

## 2. Required starting state

Before substantive work:

1. read every applicable `AGENTS.md`;
2. inspect:
   - `git status --short`
   - `git rev-parse HEAD`
   - `git rev-parse origin/main`
   - `git rev-list --left-right --count origin/main...main`
3. verify actual starting `main` is exactly, or is a clean descendant of:
   `979c443ece39b5631ac8afddabb25229aea958a8`;
4. verify unrelated owner work will not be overwritten;
5. read:
   - `research/post-phase-4-architecture-synthesis.md`
   - Phase 4 closure and evidence synthesis records referenced by it;
   - all Phase 5 Batch 1–6 durable handoffs;
   - all Phase 5 Batch 1–6 retired controlling plans;
   - root `AGENTS.md`;
   - current `irisx/core/records.py`
   - current `irisx/core/interfaces.py`
   - current `irisx/core/execution.py`
   - Batch 5 admission profile/checker/current-environment record;
   - Batch 6 task-family summary and three terminal records;
6. record actual starting SHA and the exact evidence set reviewed in the Batch 7 handoff.

If a referenced handoff/evidence artifact is missing, contradictory, or materially changed from its recorded identity, mark the affected claim `Unclear` or `Conflicting evidence`; do not silently repair history.

---

## 3. Zero-model-call rule

Batch 7 authorizes:

```text
provider attempts: 0
model calls: 0
background model processes: 0
model retries: 0
routes: 0
fallbacks: 0
escalations: 0
recovery actions: 0
```

Do not run:

- `codex exec`;
- a background model process;
- a provider reachability prompt;
- a model-based architecture review;
- a model judge;
- a new task-family execution.

All Batch 7 reasoning must derive from existing repository evidence plus deterministic local validation.

If an unresolved architecture question appears to require a new model execution, record it as a **future trigger candidate**. Do not execute it in Batch 7.

---

## 4. Mandatory model-execution launch/collection governance for future batches

Although Batch 7 itself authorizes zero model calls, this batch must record the owner's execution-handling requirement for future owner-authorized model runs.

### 4.1 Two-turn execution protocol

Any future plan that authorizes a model execution should separate:

```text
TURN A — launch only
    freeze/commit definition + code
    deterministic preflight/admission
    verify clean tree
    launch model process in background
    redirect stdout/stderr outside repository
    record PID, launch timestamp, freeze SHA, external log paths
    perform exactly one immediate launch confirmation
    STOP

TURN B — owner-requested collection
    only after explicit owner follow-up
    inspect process completion/output
    preserve raw run artifacts
    validate/adjudicate
    commit evidence
    continue lifecycle
```

### 4.2 No monitoring after launch

After the single immediate launch confirmation, the launch turn must not:

- poll process state;
- use repeated process-status checks;
- wait on the process;
- sleep and recheck;
- tail stdout/stderr;
- watch filesystem output;
- repeatedly inspect run directories;
- infer the run result;
- collect partial result artifacts;
- report final model output.

The process may continue independently after the launch turn ends.

The owner will explicitly return in a later turn to authorize collection.

### 4.3 Immediate launch confirmation

Exactly one immediate post-launch check is allowed solely to establish:

- process creation was attempted;
- PID if available;
- whether the process had already exited at that one immediate observation.

Even if it already exited, do not inspect or interpret model output in the launch turn.

Record only factual launch state and STOP.

### 4.4 Why this is governance, not architecture

This launch/collection split is an owner-directed development and usage discipline intended to reduce unnecessary active monitoring and token/tool consumption and to improve operational stability.

Do not claim it is:

- a proven reliability mechanism;
- persistence;
- recovery;
- asynchronous orchestration architecture;
- queue semantics;
- workflow machinery;
- a research result.

It is a future execution procedure unless and until separately evaluated.

---

## 5. Required Batch 7 outputs

Batch 7 should create a compact but explicit architecture-consolidation package.

Required authored records:

```text
research/phase-5-architecture-consolidation.md
research/phase-5-capability-trigger-review.md
docs/phase-5-architecture-state.md
docs/phase-5-architecture-consolidation-handoff.md
docs/plans/TEMP_PHASE_5_ARCHITECTURE_CONSOLIDATION_AND_TRIGGER_REVIEW.md
```

If an equivalent existing document is clearly the right authority surface, update it narrowly instead of duplicating content.

Do not rewrite historical handoffs.

---

## 6. Architecture support matrix

Create a matrix mapping each current candidate boundary/mechanism to evidence.

At minimum include:

| Candidate / boundary | Primary evidence | Phase 5 exercise | Current status | Scope limitation | Next falsifier/trigger |
| --- | --- | --- | --- | --- | --- |

Required rows:

- immutable program identity;
- task-contract identity binding;
- execution-context identity binding;
- contract-bound evidence requirements;
- producer/verifier separation;
- deterministic independent verifier;
- canonical terminal adjudication;
- task-specific verifier authority;
- provider-specific executor replaceability;
- provider-specific code outside core;
- truthful resource accounting;
- `Unknown` rather than fabricated zero;
- admission before model execution;
- exact-version provider admission;
- read-only model execution;
- cross-task adapter reuse;
- cross-task identity isolation;
- cross-task evidence isolation;
- cross-task verifier isolation;
- structured observations;
- policy-before-mutation for existing mutation path;
- recovery extension point;
- persistence;
- nondeterministic verification;
- routing;
- escalation/cascade;
- automated specialization;
- workflow search;
- external/irreversible action support.

Use statuses such as:

```text
Supported within observed scope
Provisional implementation choice
Not evaluated
Not triggered
Unclear
Conflicting evidence
```

Do not collapse those categories.

---

## 7. Separate architectural invariant from substrate shape

For every supported item, distinguish:

### Evidence-backed invariant

Example:

> producer claim must not determine semantic success.

### Current provisional realization

Example:

> Python dataclass + protocol representation in `irisx.core`.

The batch must explicitly identify which current Python shapes are replaceable implementation substrate rather than research conclusions.

At minimum review:

- dataclass boundaries;
- protocol shapes;
- JSON serialization schema;
- in-memory state;
- SHA-256 binding;
- local filesystem evidence paths;
- exact terminal vocabulary;
- current resource-ledger field set;
- exact admission-record shape.

Do not promote implementation convenience into architecture authority.

---

## 8. Phase 5 evidence chain

Create a concise Batch 1–6 evidence map.

Required minimum:

```text
Batch 1
reusable execution boundary + dual deterministic paths

Batch 2
contract-bound evidence authority

Batch 3
canonical terminal semantic integrity

Batch 4
first successful admitted model-backed execution
+ preserved configuration failures

Batch 5
zero-model-call provider admission hardening

Batch 6
three-task model-backed reuse
+ cross-task isolation
+ 3/3 verified success
```

For each batch record:

- baseline;
- final/validated SHA;
- exact supported conclusion;
- direct evidence contribution;
- unresolved uncertainty.

Do not strengthen historical conclusions.

---

## 9. Trigger review framework

Review each deferred capability using explicit trigger logic.

For every mechanism, record:

```text
trigger definition
evidence examined
trigger status
reasoning
what evidence would change the status
whether a new experiment is warranted now
```

Allowed trigger statuses:

```text
Triggered
Not triggered
Evidence insufficient
Not applicable to current scope
Conflicting evidence
```

Do not use `Triggered` merely because the mechanism is interesting.

---

## 10. H-G1 — Automated specialization

Use the established criterion:

> automated specialization becomes worth testing when repeatable automated generation/specialization is required and manual/frozen programs are no longer sufficient for the declared experimental objective.

Batch 7 must determine whether Batch 1–6 evidence actually satisfies that criterion.

Unless new repository evidence establishes otherwise, do not infer H-G1 from having multiple task definitions.

Record both:

```text
H-G1 research status: Not evaluated
trigger status: <status>
```

---

## 11. H-W1 — Workflow machinery/search

Criterion:

> workflow machinery becomes worth testing when simple bounded execution/control flow is insufficient for a declared task requirement.

The existence of three sequential owner-authorized task runs is not itself evidence that a workflow engine is needed.

Explicitly evaluate whether any Batch 1–6 task required workflow search, multi-step dynamic planning, or graph orchestration.

---

## 12. H-C1 — Cascade/escalation

Use the established criterion:

> test escalation/cascade only when a cheaper specialist misses declared requirements and an escalation candidate plausibly resolves the miss.

Relevant Batch 6 evidence includes 3/3 `verified_success` on the current bounded task family.

Do not trigger H-C1 solely because a stronger model exists.

If no qualifying cheap-model failure exists, record `Not triggered`.

---

## 13. H-R1 — Feature-based routing/allocation

Use the established criterion:

> test routing when heterogeneous tasks exist and feature-based allocation is plausibly material to the performance/cost/reliability frontier.

Batch 6 supplies heterogeneous deterministic task semantics, but all used the same model/profile successfully.

Determine whether heterogeneity alone is sufficient. It normally is not.

Require evidence that different allocations may materially affect outcomes before recommending a routing experiment.

---

## 14. Persistence trigger

Review whether persistence/restart/stateful execution is now triggered.

Use the established trigger family:

- crash/restart continuity;
- execution across days/weeks;
- multi-process/multi-host continuity;
- durable state needed beyond immutable run evidence;
- task semantics requiring ongoing state.

Do not treat Git run artifacts as evidence that runtime persistence is required.

---

## 15. Nondeterministic-verifier trigger

Review whether deterministic verification is becoming insufficient.

Trigger examples:

- no deterministic oracle;
- correctness depends on semantic quality not reducible to a frozen exact rule;
- multiple acceptable answers;
- evaluator disagreement;
- confidence/reliability calibration becomes necessary;
- human judgment is part of the declared acceptance condition.

Batch 6 tasks all remained deterministic.

Do not introduce a model judge merely to increase sophistication.

---

## 16. External-action / interception trigger

Review whether external or irreversible actions are now required.

Trigger examples:

- real network/API mutation;
- payments;
- messages;
- file/system mutation outside isolated task state;
- irreversible side effects;
- need for authenticated evidence/interception.

Current Batch 4–6 model tasks were read-only and tool-free.

Distinguish local reversible mutation evidence from external action requirements.

---

## 17. Recovery trigger

Review whether recovery/retry machinery is now justified.

Distinguish:

- provider/configuration admission failure;
- semantic model failure;
- transient execution failure;
- partial external side effect;
- deterministic retry benefit.

Batch 4 deliberately preserved failed attempts without automatic retry.

Batch 5 reduced known admission failure risk.

Batch 6 completed 3/3 without retry.

Do not trigger recovery merely because failures are possible in principle.

---

## 18. Phase 5 closure decision

Batch 7 must end with exactly one of these high-level decisions.

### Decision A — Close Phase 5

Use only if evidence is sufficient to state:

> Phase 5 complete — the provisional architecture has been exercised across deterministic local mutation/read-only paths and an admitted model-backed multi-task family, with core trust boundaries and current extension triggers explicitly documented; no additional mechanism is presently evidence-triggered.

This does **not** mean the architecture is final or production-ready.

If choosing Decision A:

- create/update a Phase 5 closure record;
- state all unevaluated mechanisms explicitly;
- state future trigger conditions;
- do not start Phase 6 automatically.

### Decision B — Keep Phase 5 open with one evidence-triggered next experiment

Use only if exactly one deferred mechanism is now actually triggered.

Record:

- mechanism;
- direct triggering evidence;
- why existing evidence is insufficient;
- smallest next experiment;
- explicit exclusions.

Do not start that experiment in Batch 7.

### Decision C — Evidence insufficient to close or trigger

Use if consolidation reveals unresolved contradictions/gaps that prevent both closure and a justified next mechanism.

Record the uncertainty; do not manufacture a task.

---

## 19. Current recommended default

Based on Batch 1–6 evidence known at plan creation, the expected—but not predetermined—result is:

```text
H-G1: Not evaluated / likely not triggered
H-W1: Not evaluated / likely not triggered
H-C1: Not evaluated / likely not triggered
H-R1: Not evaluated / likely not triggered
persistence: likely not triggered
nondeterministic verifier: likely not triggered
external-action expansion: likely not triggered
recovery: likely not triggered
```

This is a planning expectation, not a conclusion.

The executing agent must independently verify against repository evidence.

---

## 20. Root authority update

The current root `AGENTS.md` still describes active Batch 6 work after Batch 6 retirement.

After this plan is committed, minimally update it so Current Objective states:

> Phase 5 Batch 7 is consolidating Batch 1–6 evidence, reviewing deferred capability triggers, and deciding Phase 5 closure versus one evidence-triggered next experiment. Batch 7 authorizes no model/provider execution and no new runtime mechanism.

Also document the owner-directed future model-execution launch/collection discipline:

- launch and collection are separate owner-authorized turns;
- launch turn does not monitor after one immediate confirmation.

Do not misrepresent this procedural rule as an evaluated reliability mechanism.

---

## 21. No core implementation expansion

Preferred Batch 7 code diff:

```text
irisx/core: no changes
model-execution runner: no changes
provider adapter: no changes
admission checker: no changes
```

Batch 7 is synthesis and governance.

Only deterministic repository-validation helpers may be changed if strictly necessary to verify evidence integrity, and only if they do not alter execution semantics.

If a new core mechanism appears necessary, that is evidence for a future batch, not permission to implement it now.

---

## 22. Deterministic validation

At minimum run:

```powershell
python tools\repository_check.py

python -m unittest discover -s irisx\core\tests -v
python -m unittest discover -s experiments\substrates\minimal-reliable-execution-v0\tests -v
python -m unittest discover -s experiments\substrates\core-execution-integration-v0\tests -v
python -m unittest discover -s experiments\substrates\model-execution-qualification-v0\tests -v

git diff --check
git diff --cached --check
```

Also run the established full test inventory.

Do not rerun any model task.

Record exact focused/full counts and preserve the known historical Phase 4 hash failure unchanged.

---

## 23. Preservation requirements

Preserve exact:

- `sources/`;
- `references/papers/`;
- all historical `research/` records except new Batch 7 authored consolidation documents;
- all pre-existing run directories;
- Batch 4 Run 01/02/03;
- Batch 6 Task A/B/C runs;
- all Phase 4/5 retired plans;
- all prior durable handoffs;
- all frozen task definitions/programs/inputs/schemas;
- Batch 5 admission profile/result;
- Batch 6 admission snapshot;
- accepted provider/model baseline;
- `irisx/core`;
- all prior terminal/resource/evidence records.

No historical evidence correction is authorized except additive clarification in new Batch 7 documents.

No amend/rebase/squash/history rewrite.

No force-push.

---

## 24. Suggested work packages and commits

### WP0 — Activate plan
`docs: activate Phase 5 architecture consolidation plan`

### WP1 — Align authority
`docs: align Phase 5 consolidation authority`

### WP2 — Build Phase 5 evidence/support matrix
Create `research/phase-5-architecture-consolidation.md`.
`research: consolidate Phase 5 architecture evidence`

### WP3 — Review capability triggers
Create `research/phase-5-capability-trigger-review.md`.
`research: review Phase 5 capability triggers`

### WP4 — Record architecture state and closure decision
Create `docs/phase-5-architecture-state.md` and, if Decision A is justified, a Phase 5 closure record.
`docs: record Phase 5 architecture state`

### WP5 — Deterministic validation and preservation
Add an authored validation record only if useful.
Suggested commit:
`tests: validate Phase 5 consolidation state`

### WP6 — Durable handoff
Create `docs/phase-5-architecture-consolidation-handoff.md`.
`docs: record Phase 5 architecture consolidation handoff`

### WP7 — Retire plan
`docs: retire Phase 5 architecture consolidation plan`

Then push `main` normally and STOP.

---

## 25. Acceptance criteria

Batch 7 passes only if:

1. zero provider/model calls occur;
2. Batch 1–6 evidence is explicitly traced;
3. architecture support matrix exists;
4. invariants are separated from provisional substrate shapes;
5. all deferred triggers are explicitly reviewed;
6. H-G1/H-W1/H-C1/H-R1 each retain exact research status plus trigger status;
7. persistence trigger is reviewed;
8. nondeterministic-verifier trigger is reviewed;
9. external-action/interception trigger is reviewed;
10. recovery trigger is reviewed;
11. no mechanism is marked triggered without direct evidence;
12. exactly one Phase 5 decision is recorded: A, B, or C;
13. no next experiment is executed;
14. future model launch/collection two-turn governance is documented;
15. no model monitoring behavior is introduced;
16. `irisx/core` remains unchanged unless preservation/validation exposes a separately reported issue;
17. no historical run/evidence artifact changes;
18. no new model run directory exists;
19. focused tests preserve all prior passing behavior;
20. full inventory introduces zero new failures/errors;
21. known historical Phase 4 failure remains unchanged;
22. durable handoff exists;
23. plan is retired separately;
24. working tree is clean;
25. normal push succeeds;
26. local/remote ahead-behind is `0/0`.

---

## 26. Allowed conclusions

### If Decision A — Phase 5 closure

> **Phase 5 complete — the provisional IRIS-X architecture has been exercised across deterministic local execution and an admitted multi-task model-backed execution family, with supported trust boundaries, provisional substrate choices, unresolved mechanisms, and future capability triggers explicitly consolidated. No additional mechanism is presently evidence-triggered.**

Do not claim final architecture correctness, general provider portability, production readiness, routing, persistence, recovery, or model-judge correctness.

### If Decision B — One triggered next experiment

> **Phase 5 Batch 7 complete — architecture consolidation identified one evidence-triggered unresolved mechanism requiring a bounded follow-up experiment: `<mechanism>`. The experiment was not started.**

### If Decision C — unresolved consolidation

> **Phase 5 Batch 7 complete with unresolved consolidation — current evidence is insufficient both to close Phase 5 and to justify a single next mechanism experiment.**

---

## 27. Durable handoff requirements

Create:

`docs/phase-5-architecture-consolidation-handoff.md`

Record:

### Repository
- required baseline;
- actual starting SHA;
- consolidation commit SHAs;
- trigger-review SHA;
- architecture-state/closure SHA;
- validation SHA if any;
- handoff SHA;
- retirement SHA;
- final local/remote SHA;
- clean state;
- ahead/behind;
- normal push result.

### Evidence reviewed
- Batch 1–6 handoff identities;
- Batch 4 model lineage;
- Batch 5 admission evidence;
- Batch 6 three-task results and summary;
- relevant core files;
- relevant Phase 4 synthesis/closure records.

### Architecture state
- supported invariants;
- provisional substrate choices;
- unsupported/generalization limits;
- unresolved mechanisms.

### Trigger decisions
For every trigger:
- criterion;
- evidence;
- status;
- reason;
- next evidence required.

### Phase decision
Record exactly A, B, or C with justification.

### Validation/preservation
- focused test counts;
- full inventory counts;
- historical failure;
- zero model calls;
- no new run directory;
- historical evidence preservation.

### Future model-run governance
Record the two-turn launch/collection rule and explicitly state it is owner-directed procedure, not an evaluated architecture result.

---

## 28. Stop conditions

STOP rather than broaden scope if:

- consolidation requires a new model run;
- a trigger review starts turning into mechanism implementation;
- more than one mechanism appears simultaneously triggered and cannot be prioritized from evidence;
- historical evidence is contradictory in a way that cannot be resolved additively;
- a broad core change appears necessary;
- preservation fails;
- a new regression cannot be resolved without changing historical artifacts;
- a model-based evaluator appears necessary;
- the task begins implementing Phase 6 or Batch 8 work.

Record the uncertainty instead.

---

## 29. Hard STOP

After consolidation is complete, trigger review is complete, architecture state/closure decision is recorded, deterministic validation passes, preservation is verified, durable handoff is committed, plan is retired, and `main` is pushed normally with local/remote synchronization:

**STOP.**

Do not start another model execution.

Do not start Phase 5 Batch 8.

Do not start Phase 6.

Any future execution requires separate owner authorization.

---

## 30. Retirement record

- **Retirement date:** 2026-09-06 Asia/Taipei
- **Required and observed starting baseline:**
  `979c443ece39b5631ac8afddabb25229aea958a8`
- **Decision:** **Decision A — Close Phase 5**
- **Durable handoff:**
  `docs/phase-5-architecture-consolidation-handoff.md` at
  `3aa4beae4d9557d535f337cefe0dd9ac5dab1872`
- **Model/provider calls authorized and performed:** `0` / `0`

The plan was executed through these pre-retirement commits:

| Purpose | Commit |
| --- | --- |
| Activate controlling plan | `aba95f35c5c3f0154c690e97babc3e9f751054aa` |
| Align repository authority | `ecd247e06440ff829829fd96b12e7aecfc429ec9` |
| Consolidate architecture evidence | `f66b188aa7673776f3fb39a719853f2e7df80b61` |
| Review capability triggers | `627dfbf8dc4bc95aae8ddc2598b806e09109af81` |
| Record architecture state | `3d3a05fbc4207a6154796c071d5fa25246a4328a` |
| Finalize closure authority wording | `e7f4f42b7d4a0e25df462a4f0092217c50eca6f1` |
| Record durable handoff | `3aa4beae4d9557d535f337cefe0dd9ac5dab1872` |

The support matrix separates evidence-backed invariants from the current
dataclass/protocol/JSON/local-filesystem/in-memory substrate. Provider-specific
code outside core remains a provisional implementation choice. General
recovery, persistence, nondeterministic verification, routing,
escalation/cascade, automated specialization, workflow search, and
external/irreversible actions remain not evaluated.

Every reviewed deferred capability trigger—H-G1, H-W1, H-C1, H-R1,
persistence, nondeterministic verification/model judging,
external-action/interception, and recovery/retry—was `Not triggered`. No next
experiment is warranted by the current evidence.

Deterministic validation before retirement recorded:

- repository check: PASS, 13 sources and 7 artifacts checked;
- focused suites: 125/125 PASS;
- full discovered inventory: 196 run, 195 pass, 1 failure, 0 errors, 0
  skipped;
- sole failure: the unchanged historical Phase 4 frozen-plan hash mismatch in
  `HPIaContractTests.test_frozen_artifact_hashes_match_exact_bytes`;
- Batch 7 introduced zero new failures or errors.

Preservation checks found no changes to imported sources, papers,
`irisx/core`, experiment configurations, provider baseline, admission records,
historical runs, Batch 6 evidence, historical Phase 5 plans, historical
handoffs, or the preserved Phase 4 plan. The tracked run inventory remained 22
run instances and 871 files with manifest SHA-256
`2263bb7c26b93f5dd4cfb46857c36628bcb29b57ad2c2343d490746c2334f6b5`.

The owner-directed future two-turn launch/collection procedure is recorded in
`AGENTS.md` and `docs/phase-5-architecture-state.md`. It is a development
procedure, not evaluated evidence for reliability architecture, persistence,
workflow, recovery, or any research result.

No model process, next experiment, Batch 8, or Phase 6 was started. The full
retirement commit SHA, final local/remote SHA, clean-tree state, and
ahead/behind result are reported after the normal push in the owner-facing
final report.
