# TEMP Phase 5 — Model Task-Family Qualification and Cross-Task Isolation

Status: **Temporary — controlling execution plan; owner-authorized Phase 5 Batch 6**  
Date: **2026-09-06 Asia/Taipei**  
Repository: **Danwuoo/IRIS-X**  
Required baseline `main`: **`cd2b3f60a802a3f0438dc38792fd58b45bde820e`**  
Phase: **Phase 5 — provisional architecture development**  
Batch: **Batch 6**  
Batch goal: **qualify one admitted model-backed execution profile across three semantically distinct deterministic task families while proving cross-task identity/evidence/verifier isolation and truthful aggregate resource accounting**  
Architecture authority: **Provisional only; no final runtime, provider portability, routing, recovery, or production claim**  
Live model/provider call ceiling: **maximum 3 total; exactly 1 per authorized task; 0 retries**  
Hard terminal boundary: **STOP after the authorized task-family qualification, validation, durable handoff, plan retirement, and normal push**

---

## 1. Owner authorization and scope

This plan is the new owner-authorized scope for Phase 5 Batch 6.

Phase 4 remains closed.

Phase 5 Batch 1 through Batch 5 remain complete and retired. Their frozen evidence, handoffs, plans, execution records, historical failures, and compatibility findings must not be rewritten, reopened, or strengthened.

Batch 5 established a deterministic zero-model-call admission checker for the exact currently qualified Codex CLI 0.147.0 / Run 03 execution profile.

Batch 6 authorizes a bounded increase in **task semantic diversity**, not mechanism diversity.

The single architectural question is:

> Can the same admitted provider-specific model execution profile and adapter be reused across three semantically distinct, independently frozen, deterministic-verifier task families without modifying `irisx.core`, without collapsing task identity, and without weakening evidence, verification, adjudication, read-only, admission, or resource-accounting boundaries?

This is a task-family qualification batch.

It is not a model comparison, routing experiment, retry experiment, persistence experiment, verifier-generalization experiment, optimizer experiment, or productionization batch.

---

## 2. Required starting state

Before substantive work:

1. read every applicable `AGENTS.md`;
2. inspect `git status --short`, `git rev-parse HEAD`, `git rev-parse origin/main`, and `git rev-list --left-right --count origin/main...main`;
3. verify actual starting `main` is exactly, or is a clean descendant of, `cd2b3f60a802a3f0438dc38792fd58b45bde820e`;
4. verify unrelated owner work will not be overwritten;
5. read the Phase 5 Batch 1–5 handoffs, all Batch 4 model-execution handoffs, `docs/phase-5-model-execution-admission-handoff.md`, the accepted provider/model baseline, Batch 5 admission checker/profile/current record, existing model-execution substrate, and `irisx/core/{records,interfaces,execution}.py`;
6. confirm Batch 5 admission artifacts are intact;
7. record actual starting SHA in the Batch 6 handoff and retirement record.

If baseline or preservation materially conflicts, STOP.

---

## 3. Fixed execution profile

Batch 6 reuses the exact currently qualified execution profile:

```text
execution surface: codex-cli
qualified version: codex-cli 0.147.0
admission profile: codex-cli-0.147.0-run-03-admission-v0
provider: openai
Codex provider slot: irisx_openai_no_retry
model role: cheaper
model: gpt-5.6-luna
reasoning effort: medium
authentication: ChatGPT
billing: ChatGPT subscription
API-key fallback: prohibited
HTTP retries: 0
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

Do not substitute a different model, role, reasoning effort, Codex version, provider slot, auth mode, or sandbox.

If Batch 5 admission rejects the current environment, STOP before all live calls.

---

## 4. Live call budget

```text
Task A: <= 1 live model call
Task B: <= 1 live model call
Task C: <= 1 live model call

Batch total: <= 3 live model calls
Retries: 0
Manual retries: 0
Automatic retries: 0
Routes: 0
Fallbacks: 0
Escalations: 0
Recovery actions: 0
Alternate models: 0
```

Each task is a separately frozen qualification execution, not a retry of another task.

Do not consume an unused call allowance merely because it exists.

---

## 5. Task-family structure

Add one substrate-local task-family qualification layer under the existing model-execution qualification substrate.

Preferred structure:

```text
experiments/substrates/model-execution-qualification-v0/task-family/
    definitions/
    inputs/
    schemas/
    admission/
    summaries/
```

Provider-specific adapter reuse remains inside this substrate.

Do not create a new top-level framework or move provider-specific logic into `irisx.core`.

---

## 6. Task A — Filter / Set Selection

Freeze one deterministic bounded filtering task.

Representative input:

```json
{
  "records": [
    {"id":"a","score":17},
    {"id":"b","score":23},
    {"id":"c","score":11},
    {"id":"d","score":29}
  ],
  "threshold":20
}
```

Required semantic output:

```json
{"selected_ids":["b","d"]}
```

Verifier requirements:

- exact output schema;
- exact membership;
- no missing IDs;
- no extra IDs;
- deterministic ordering;
- unchanged read-only state;
- exact contract/program/evidence binding.

The exact fixture may differ, but freeze it before live execution.

---

## 7. Task B — Aggregation

Freeze one deterministic aggregation task.

Representative input:

```json
{
  "records": [
    {"region":"north","amount":12},
    {"region":"south","amount":19},
    {"region":"north","amount":31},
    {"region":"south","amount":7}
  ],
  "target_region":"north"
}
```

Required semantic output:

```json
{"total":43}
```

Verifier requirements:

- exact schema;
- exact numeric aggregation;
- unchanged state;
- exact task-specific identity/evidence binding.

Do not reuse Task A verifier semantics.

---

## 8. Task C — Ordered Transformation / Ranking

Freeze one deterministic ranking task.

Representative input:

```json
{
  "records":[
    {"id":"a","score":18},
    {"id":"b","score":31},
    {"id":"c","score":31},
    {"id":"d","score":22}
  ],
  "limit":2,
  "tie_break":"id_ascending"
}
```

Required semantic output:

```json
{
  "ranked":[
    {"id":"b","rank":1},
    {"id":"c","rank":2}
  ]
}
```

Verifier requirements:

- exact schema;
- sort order;
- explicit tie-break;
- exact result length;
- exact rank assignment;
- unchanged state;
- exact task-specific evidence/program/contract identity.

---

## 9. Common task-family requirements

All three tasks must be local-input, read-only, bounded, deterministically verifiable, tool-free, structured-output based, independent of internet/external APIs, independent of human judgment, and independent of a model judge.

The model should only return the requested structured output.

Do not expose hidden oracle data in prompts.

---

## 10. Shared adapter reuse

A modest substrate-local refactor is authorized to reuse one provider-specific adapter across all three tasks.

Acceptable local abstractions may include `FrozenTaskDefinition`, `QualificationCase`, `DeterministicOracle`, or `TaskFamilyModelAdapter` only if they reduce duplication.

Do not build a workflow engine, task framework, plugin system, provider SDK, or registry.

The intended reuse pattern is:

```text
same admitted provider profile
same model adapter
same core execution boundary
different task contract
different program
different output schema
different deterministic verifier semantics
```

---

## 11. Admission as execution prerequisite

Before any live call:

1. run the Batch 5 zero-model-call current admission checker;
2. require `admitted`;
3. freeze and hash the admission record;
4. bind the profile and record into each Batch 6 run manifest.

Each task run manifest must record:

```text
admission_profile_id
admission_profile_sha256
admission_record_path
admission_record_sha256
admission_status
```

Admission remains substrate-local. Do not add `AdmissionGate` to `irisx.core`.

---

## 12. Definition/code freeze discipline

Before the first live call, freeze and commit:

- all three task definitions;
- all three task inputs;
- all three schemas;
- all three task programs/prompts;
- all three deterministic verifiers;
- shared adapter code;
- task-family runner;
- negative-output fixtures/tests;
- admission binding code.

Record one **definition/code freeze SHA**.

After that freeze:

- live runs may add evidence and interpretation only;
- executable definition/code must remain byte-identical;
- if executable code must change, STOP the live phase and seek new owner authorization instead of silently re-freezing.

---

## 13. Cross-task isolation

Add adversarial zero-model-call tests proving:

1. Task A contract + Task B program => binding rejection;
2. Task A contract + Task C program => binding rejection;
3. Task A evidence presented to Task B => invalid binding;
4. Task B evidence presented to Task C => invalid binding;
5. Task A output under Task B verifier => semantic failure/rejection;
6. Task B output under Task C verifier => semantic failure/rejection;
7. Task C output under Task A verifier => semantic failure/rejection;
8. Task B schema used for Task C => reject;
9. Task C program hash paired with Task A identity => reject;
10. task-specific evidence paths cannot substitute for one another.

Target invariant:

> shared model adapter does not imply shared task authority.

---

## 14. Offline negative-output corpus

For each task, add synthetic provider-output fixtures covering:

```text
correct
malformed JSON
schema-valid but semantically wrong
missing required result
extra result
wrong order
wrong numeric value
producer-success claim with semantic failure
```

Task C additionally includes a tie-break violation.

Evaluate these through the actual deterministic verifier + canonical adjudication pipeline where practical.

No live model calls are used.

Required invariant:

```text
provider exit success != semantic success
schema validity != semantic validity
producer claim != terminal truth
```

---

## 15. Live execution stop rules

### 15.1 Admission failure

If current admission is not `admitted`:

```text
STOP all live execution
model calls consumed: 0
```

Do not attempt Task A/B/C.

### 15.2 Systemic provider/configuration failure

If a live task fails because of CLI configuration rejection, authentication failure, provider startup failure, incompatible provider slot, forbidden tool exposure, sandbox drift, unexpected routing/retry/fallback, Batch 5 admission contradiction, or another systemic failure before a usable model result:

1. preserve the task evidence;
2. adjudicate truthfully;
3. STOP all remaining live tasks.

Do not consume Task B/C allowances after a systemic failure.

### 15.3 Semantic model failure

If a task has healthy provider execution, observed model output, no forbidden tool/action, and deterministic verifier rejects semantic content:

1. preserve the semantic failure;
2. do not retry that task;
3. the next independently authorized task may continue.

A wrong model answer is not a systemic provider failure.

### 15.4 Safety/invariant violation

If any run shows tool invocation, state mutation, retry, fallback, route, escalation, recovery, unauthorized auth mode, API-key fallback, evidence identity crossing, or historical artifact overwrite, immediately STOP all remaining runs.

---

## 16. Run ordering and immutable evidence

Required live order:

```text
freeze definitions/code
    -> commit

zero-call admission snapshot
    -> commit

Task A live execution
    -> validate
    -> commit immutable evidence

Task B live execution
    -> validate
    -> commit immutable evidence

Task C live execution
    -> validate
    -> commit immutable evidence
```

Before each live task:

- working tree must be clean;
- admission snapshot must still be valid;
- executable definition/code tree must match the freeze identity.

Do not run all three tasks first and commit afterward.

Each task gets a distinct run ID and immutable run directory.

---

## 17. Per-task run artifacts

Each task run must preserve at minimum:

```text
attempt-start.json
provider-events.jsonl
provider-stderr.txt
raw-output.txt
resource-record.json
terminal-record.json
run-manifest.json
interpretation.json
```

Each run must record:

- task ID;
- contract ID/hash;
- program ID/hash;
- execution ID;
- configuration ID;
- definition/code freeze SHA;
- launch HEAD;
- admission profile ID/hash;
- admission record hash;
- provider/model identity;
- deterministic oracle identity;
- prompt hash;
- state-before/state-after hashes;
- changed paths;
- exact call ledger;
- verifier result;
- terminal adjudication.

Never overwrite a prior run directory.

---

## 18. Batch-level task-family summary

After all authorized live execution is complete, create one derived batch-level summary, for example:

```text
experiments/substrates/model-execution-qualification-v0/task-family/summaries/batch-6-summary.json
```

It may contain:

```text
task_count
attempted_tasks
completed_provider_runs
verified_successes
semantic_failures
system_failures
total_model_calls
total_input_tokens
total_output_tokens
total_wall_time_ns
total_retries
total_routes
total_fallbacks
total_escalations
total_recovery_actions
provider_cost_usd_or_unknown
```

This summary is derived data only.

It must not become adjudication authority.

Per-task `TerminalRecord` remains source of truth.

If token usage is missing for a run, preserve `Unknown` rather than inventing a total.

Provider cost remains `Unknown` unless direct run-attributable evidence exists.

Do not substitute API pricing for ChatGPT subscription cost.

---

## 19. Resource-accounting invariants

Per live task:

```text
model_calls = 1 if the task crosses the committed model invocation boundary
retry_count = 0
route_count = 0
fallback_count = 0
escalation_count = 0
recovery_count = 0
tool_calls = 0
```

Batch summary:

```text
total_model_calls = sum(per-task model_calls)
```

Only aggregate directly observed values.

Transport/network request count remains `Unknown` if Codex does not expose it.

Do not build a cost optimizer.

---

## 20. Architecture acceptance vs task-family qualification

Batch 6 must explicitly separate two conclusions.

### Architecture exercise acceptance

The architecture exercise may pass even if a model answer is wrong, provided:

- admission behaves correctly;
- call ceilings are respected;
- evidence is preserved;
- deterministic verifier correctly rejects bad semantics;
- canonical adjudication is correct;
- cross-task isolation holds;
- task state remains read-only;
- resource accounting is truthful;
- no excluded mechanisms occur.

### Full task-family qualification

Only if all three authorized tasks achieve:

```text
actual_outcome: success
evidence: sufficient
acceptance: accept
verified_success_eligibility: true
joint_interpretation: verified_success
```

may the handoff claim full three-task qualification.

If fewer than three succeed semantically, report the exact result count.

Do not convert partial success into a full qualification claim.

---

## 21. Expected successful terminal semantics

For a semantically correct task:

```text
actual_outcome: success
producer_claim: success
empirical_evidence_status: sufficient
acceptance_decision: accept
verified_success_eligibility: true
joint_interpretation: verified_success
terminal_execution_status: completed
mutation primitive calls: 0
model calls: 1
retries: 0
routes: 0
fallbacks: 0
escalations: 0
recovery actions: 0
tool calls: 0
changed_paths: []
state_before_sha256 == state_after_sha256
```

A semantic model failure must produce a truthful failure/rejection path without retry.

---

## 22. Explicitly out of scope

Do not implement or evaluate:

- GPT-5.6 Terra;
- Luna vs Terra comparison;
- second provider;
- router;
- cascade;
- fallback model;
- automatic escalation;
- retry;
- recovery;
- persistence;
- crash/restart;
- multi-host state;
- workflow engine;
- workflow search;
- optimizer integration;
- fine-tuning;
- training;
- multi-agent systems;
- model judge;
- non-deterministic verifier;
- probabilistic verifier confidence;
- human adjudication;
- external/irreversible actions;
- browser/web/tool-enabled tasks;
- general provider registry;
- provider SDK;
- generic admission framework;
- production server/API/UI;
- lifecycle-cost optimization;
- H-G1;
- H-W1;
- H-C1;
- H-R1.

These remain outside Batch 6.

---

## 23. Preferred core impact

Preferred outcome: **no `irisx.core` changes**.

Batch 6 should exercise existing identity binding, contract-bound evidence, independent verification, canonical adjudication, terminal records, and resource ledger.

If new task-family work appears to require a core abstraction, first determine whether it can remain substrate-local.

If a broad core change is necessary, STOP and report rather than silently expanding architecture.

---

## 24. Required tests

All tests make zero live model calls.

At minimum include:

### Task semantics

1. Task A correct fixture => verified success;
2. Task A malformed output => reject;
3. Task A wrong set => reject;
4. Task A extra/missing member => reject;
5. Task B correct fixture => verified success;
6. Task B wrong aggregation => reject;
7. Task B malformed output => reject;
8. Task C correct ranking => verified success;
9. Task C wrong order => reject;
10. Task C tie-break violation => reject;
11. Task C wrong rank count => reject.

### Authority separation

12. producer success claim cannot override verifier failure;
13. schema-valid wrong answer is rejected;
14. resource telemetry changes do not affect adjudication.

### Cross-task isolation

15. A contract + B program rejects;
16. A contract + C program rejects;
17. A evidence cannot satisfy B;
18. B evidence cannot satisfy C;
19. A output under B verifier rejects;
20. B output under C verifier rejects;
21. C output under A verifier rejects;
22. wrong task schema rejects;
23. wrong task program hash rejects.

### Admission/resource

24. current Batch 5 profile replay still admits;
25. admission rejection prevents live-run authorization in runner logic;
26. run manifests bind admission record/profile hashes;
27. batch summary aggregates only observed values;
28. missing token data remains `Unknown`;
29. per-task retry/route/fallback/escalation/recovery/tool counts remain zero.

### Regression

30. existing core tests remain passing;
31. existing deterministic mutation/read-only tests remain passing;
32. Batch 4 qualification tests remain passing;
33. Batch 5 admission tests remain passing.

Do not create a giant generic task framework solely to satisfy tests.

---

## 25. Preservation requirements

Preserve exact:

- `sources/`;
- `references/papers/`;
- `research/`;
- all pre-existing run directories;
- Batch 4 Run 01;
- Batch 4 Run 02;
- Batch 4 Run 03;
- all prior Phase 4/5 retired plans;
- all prior durable handoffs;
- Batch 5 compatibility profile and admission result;
- accepted provider/model baseline;
- four deterministic Phase 5 input files;
- all prior frozen model-execution definitions/artifacts.

Batch 6 may add only:

- new task-family definitions/inputs/schemas/tests;
- one new admission snapshot;
- up to three new task-family run directories;
- one derived batch summary;
- Batch 6 handoff/plan/documentation.

No history rewrite.

No force-push.

---

## 26. Authority update

After plan activation, update root `AGENTS.md` minimally.

Current objective should state:

> Phase 5 Batch 6 is qualifying the already-admitted model-backed execution profile across three semantically distinct deterministic task families while testing cross-task isolation and preserving the existing core trust boundaries.

Also state:

- maximum three separately frozen live model calls;
- zero retries/routes/fallbacks/escalations/recovery;
- deterministic verifier remains authoritative;
- admission remains required;
- provider-specific code remains outside core;
- Batch 6 does not authorize routing, model comparison, persistence, or model-judge work.

---

## 27. Suggested implementation surface

Expected additions/modifications may include:

```text
AGENTS.md
docs/plans/TEMP_PHASE_5_MODEL_TASK_FAMILY_QUALIFICATION.md
docs/phase-5-model-task-family-qualification-handoff.md

experiments/substrates/model-execution-qualification-v0/README.md

experiments/substrates/model-execution-qualification-v0/task-family/definitions/...
experiments/substrates/model-execution-qualification-v0/task-family/inputs/...
experiments/substrates/model-execution-qualification-v0/task-family/schemas/...
experiments/substrates/model-execution-qualification-v0/task-family/summaries/...

experiments/substrates/model-execution-qualification-v0/scripts/task_family.py
experiments/substrates/model-execution-qualification-v0/scripts/model_adapter.py
experiments/substrates/model-execution-qualification-v0/scripts/run_task_family_case.py

experiments/substrates/model-execution-qualification-v0/tests/test_task_family.py
experiments/substrates/model-execution-qualification-v0/tests/test_cross_task_isolation.py
```

Reuse existing code when reasonable.

Do not move frozen historical run code unnecessarily.

---

## 28. Commit sequence

Use small, auditable commits.

Suggested sequence:

1. `docs: activate Phase 5 task-family qualification plan`
2. `docs: align Phase 5 task-family authority`
3. `experiments: freeze model task-family definitions`
4. `experiments: extract reusable task-family model adapter`
5. `tests: validate task-family semantics and cross-task isolation`
6. `experiments: record task-family admission snapshot`
7. `experiments: record filter qualification run`
8. `experiments: record aggregation qualification run`
9. `experiments: record ranking qualification run`
10. `experiments: summarize task-family qualification`
11. `docs: record Phase 5 task-family qualification handoff`
12. `docs: retire Phase 5 task-family qualification plan`

If live execution stops early, omit commits for unexecuted tasks.

No amend/rebase/squash/history rewrite.

---

## 29. Validation

Before live execution:

```powershell
python tools\repository_check.py
python tools\model_baseline_check.py
python tools\model_baseline_check.py --check-local-catalog

python experiments\substrates\model-execution-qualification-v0\scripts\check_admission.py --current

python -m unittest discover -s irisx\core\tests -v
python -m unittest discover -s experiments\substrates\minimal-reliable-execution-v0\tests -v
python -m unittest discover -s experiments\substrates\core-execution-integration-v0\tests -v
python -m unittest discover -s experiments\substrates\model-execution-qualification-v0\tests -v

git diff --check
git diff --cached --check
```

After each live task:

- validate immutable run artifact hashes;
- validate terminal/resource consistency;
- validate unchanged state;
- validate one model call / zero excluded counts;
- ensure working tree clean after committing evidence.

After all authorized tasks:

- rerun all deterministic tests;
- run full established test inventory;
- validate batch summary;
- validate preservation;
- record exact counts.

Do not rerun live tasks during validation.

---

## 30. Acceptance criteria

Batch 6 architecture exercise passes only if all applicable criteria are met:

1. current Batch 5 admission passes before live execution;
2. all three task definitions are frozen before first live call;
3. executable definition/code is committed before first live call;
4. same admitted Codex/Luna profile is used for every attempted task;
5. provider-specific adapter reuse remains outside `irisx.core`;
6. no broad core change is introduced;
7. Task A uses its own contract/program/schema/verifier;
8. Task B uses its own contract/program/schema/verifier;
9. Task C uses its own contract/program/schema/verifier;
10. cross-task program substitution rejects;
11. cross-task evidence substitution rejects;
12. cross-task verifier substitution rejects;
13. offline negative-output corpus behaves correctly;
14. each live task has <= 1 model call;
15. total Batch 6 model calls <= 3;
16. retry count remains zero;
17. route count remains zero;
18. fallback count remains zero;
19. escalation count remains zero;
20. recovery count remains zero;
21. tool-call count remains zero;
22. task state remains read-only;
23. raw provider evidence is preserved immutably;
24. admission profile/record identity is bound into each run;
25. per-task terminal record remains adjudication source of truth;
26. batch summary is derived only;
27. resource aggregation is truthful;
28. provider cost remains `Unknown` absent direct evidence;
29. prior Batch 4/5 artifacts remain unchanged;
30. no new regression failure/error exists;
31. H-G1/H-W1/H-C1/H-R1 remain `Not evaluated`;
32. durable handoff exists;
33. plan is retired separately;
34. final working tree is clean;
35. main is pushed normally;
36. local/remote ahead-behind is `0/0`.

Full task-family semantic qualification additionally requires **3/3 verified successes**.

---

## 31. Allowed conclusions

### If all three tasks are verified successes

> **Phase 5 Batch 6 complete — the admitted model-backed execution profile was reused across three semantically distinct frozen deterministic task families while preserving task-specific identity, contract-bound evidence, independent verification, canonical adjudication, read-only execution, and zero-retry cross-task isolation.**

### If architecture passes but one or more tasks fail semantically

> **Phase 5 Batch 6 architecture exercise complete — the admitted model-backed execution profile was exercised across three frozen deterministic task families with preserved task isolation and correct verification/adjudication behavior; full task-family qualification was not established.**

Then state exact semantic success count.

### If systemic provider/config failure causes early stop

Use a narrower conclusion identifying tasks attempted, tasks not attempted, exact systemic failure, preserved fail-closed behavior, and no retry.

Do not imply unexecuted tasks were qualified.

---

## 32. Durable handoff

Create:

`docs/phase-5-model-task-family-qualification-handoff.md`

Record:

### Repository
- required baseline;
- actual starting SHA;
- definition/code freeze SHA;
- admission snapshot commit;
- each task run evidence commit;
- summary commit;
- handoff commit;
- retirement commit;
- final local/remote SHA;
- clean state;
- ahead/behind;
- normal push result.

### Task family
For A/B/C:
- task ID;
- semantic family;
- input/schema/program hashes;
- deterministic oracle identity;
- verifier identity.

### Admission
- profile ID/hash;
- current admission record/hash;
- admission result;
- executable/version;
- auth state;
- zero-call admission confirmation.

### Per-task execution
For each attempted task:
- run ID;
- launch HEAD;
- provider/model identity;
- model-call count;
- raw output;
- provider event hash;
- token usage if exposed;
- wall time;
- state before/after;
- verifier result;
- evidence status;
- acceptance;
- eligibility;
- joint interpretation.

### Cross-task isolation
Record all adversarial offline test outcomes.

### Batch summary
- attempted tasks;
- verified successes;
- semantic failures;
- systemic failures;
- aggregate model calls;
- aggregate tokens/wall time where known;
- excluded mechanism counts.

### Regression/preservation
- focused test counts;
- full inventory counts;
- historical Phase 4 failure status;
- prior run/plan/handoff preservation;
- no provider-specific core coupling.

### Research boundary

```text
H-G1: Not evaluated
H-W1: Not evaluated
H-C1: Not evaluated
H-R1: Not evaluated
```

---

## 33. Stop conditions

STOP rather than broaden scope if:

- Batch 5 admission rejects;
- current Codex version/profile drifts;
- executable task-family code requires post-freeze modification;
- a live task encounters systemic provider/config/auth failure;
- a forbidden tool/action occurs;
- a retry/route/fallback/escalation/recovery occurs;
- API-key fallback is required;
- state mutation occurs;
- cross-task evidence/identity isolation fails;
- a broad `irisx.core` API change appears necessary;
- a model judge becomes necessary;
- deterministic verification cannot resolve one of the frozen tasks;
- preservation fails;
- a new regression cannot be resolved within scope;
- supporting the batch would require H-G1/H-W1/H-C1/H-R1 evaluation.

Do not retry a failed task.

Do not switch models.

---

## 34. Hard STOP

After all authorized task-family execution is complete or correctly stopped, immutable evidence is committed, deterministic verification/adjudication is complete, cross-task isolation proof is complete, batch summary is committed, focused/full validation passes, durable handoff is committed, plan is retired, and `main` is pushed normally with local/remote synchronization:

**STOP.**

Do not start Phase 5 Batch 7.

Do not add routing, persistence, model comparison, model judge, recovery, or another task family without separate owner authorization.

---

## Retirement record

Phase 5 Batch 6 completed within this plan's exact task-semantic-diversity
boundary. The already-admitted Codex CLI 0.147.0 / GPT-5.6 Luna medium profile
was reused for exactly one independently authorized live call in each of the
three frozen task families. Task A, Task B, and Task C each completed with a
healthy provider result and canonical `verified_success`. Architecture exercise
acceptance and full three-task-family qualification are established.

- required and actual starting SHA:
  `cd2b3f60a802a3f0438dc38792fd58b45bde820e`;
- plan activation:
  `b9903c825504746d802a1186fc2fb9eacb70673c`;
- authority alignment:
  `ffdafa39cbf431010de64551ab45a7d19d5cdcd0`;
- task-family definition freeze:
  `272f54db77688378a798460010fd16f064be555c`;
- shared provider-specific adapter extraction:
  `bebdaeb90e57a4ade24f8ccc8023c10c42c2013c`;
- definition/code freeze SHA and offline semantics/isolation tests:
  `2320858ba1f5dc5d7c68ba426278106c565ac6b4`;
- admitted current-environment snapshot:
  `ddf9d1f9f924fcd877eb91bdfea96f645fd846ae`;
- Task A evidence:
  `9ef207b922c0b4dcb5fce61dce984bb0dfe02a22`;
- Task B evidence:
  `83782d34529b8d9ec2febed24d7899e696a91f44`;
- Task C evidence:
  `cf52d4c1b2ad3ab3f01379ff25987977f9cabe81`;
- derived batch summary:
  `81c2d48bc0c8b7390a464e7bd063666b63103342`;
- durable handoff:
  `b610dfd047b4cffeafdaca5ccbf2c2ee1cbb45c3`;
- admission profile/hash:
  `codex-cli-0.147.0-run-03-admission-v0` /
  `ab21119f80141456e7327e276fa3e470abf288cf6a3535ac5fceeace68302033`;
- admission snapshot hash and status:
  `7abfa9dc397578516f806bf1841bbc21248fe6a73ba521239c311db040f9b640` /
  `admitted`;
- per-task and batch model-call ledger: Task A `1`, Task B `1`, Task C `1`,
  total `3`; retries, routes, fallbacks, escalations, recovery actions, and tool
  calls all `0`;
- semantic outcomes: `3 / 3 verified_success`, semantic failures `0`, systemic
  failures `0`;
- offline corpus: 27/27 expected outcomes PASS, including Task C tie-break
  violation rejection;
- cross-task isolation: 12/12 PASS;
- focused validation: 125/125 PASS;
- full inventory: 196 total, 195 passed, the same one historical Phase 4
  frozen-plan hash failure, 0 errors, 0 skips, and 0 new failures/errors;
- executable task-family surface changes after freeze: `0`;
- protected prior source, paper, research, core, historical definition, and
  historical run trees: unchanged;
- new immutable run evidence: exactly three directories and 24 files; no prior
  run overwritten;
- no `irisx.core` change and no provider-specific core coupling;
- retirement commit and final local/remote synchronization: reported in the
  owner-facing final response because they occur after this record is written.

The durable result is
`docs/phase-5-model-task-family-qualification-handoff.md`. Batch 6 is closed.
H-G1, H-W1, H-C1, and H-R1 remain `Not evaluated`. Do not start Batch 7 or add
another task family or mechanism without new owner authorization.
