# TEMP Phase 5 — Model Execution Qualification

Status: **Temporary — controlling execution plan; owner-authorized Phase 5 Batch 4**  
Date: **2026-09-05 Asia/Taipei**  
Repository: **Danwuoo/IRIS-X**  
Required baseline `main`: **`0d738fec43bafc72b5f6ca0f1ca39a6426b0b751`**  
Phase: **Phase 5 — provisional architecture development**  
Batch: **Batch 4**  
Batch goal: **qualify exactly one model-backed execution path through the existing provisional trust boundaries while retaining a deterministic independent verifier**  
Architecture authority: **Provisional only; no production-runtime or final-architecture claim**  
Provider authority: **reuse the already accepted provider/model baseline; this plan separately authorizes only the frozen qualification run defined below**  
Hard terminal boundary: **STOP after the one qualification run, validation, durable handoff, retirement, and normal push**

---

## 1. Owner authorization and scope

This plan is the new owner-authorized scope for Phase 5 Batch 4.

Phase 4 remains closed.

Phase 5 Batch 1, Batch 2, and Batch 3 remain complete and retired. Their frozen evidence, handoffs, plans, and conclusions must not be reopened or strengthened.

This batch authorizes the first bounded model-backed execution through the provisional `irisx.core`.

The single question is:

> Can one frozen model-backed `ExecutorAdapter` execute through the already-established identity, evidence, independent-verification, adjudication, observation, and terminal-record boundaries without introducing hidden routing, retries, recovery, provider authority into core, or a second unknown verifier mechanism?

This is a qualification batch, not a model benchmark.

Exactly one model-backed execution path may be added.

Exactly one qualification provider invocation may be attempted.

A failed provider/model invocation is a valid qualification outcome and must be preserved as evidence. Do not retry merely to obtain a green result.

---

## 2. Required starting state

Before substantive work:

1. read all applicable `AGENTS.md` files;
2. inspect `git status --short`;
3. inspect `git rev-parse HEAD`;
4. inspect `git rev-parse origin/main`;
5. inspect `git rev-list --left-right --count origin/main...main`;
6. verify the actual starting `main` is exactly, or a clean descendant of,  
   `0d738fec43bafc72b5f6ca0f1ca39a6426b0b751`;
7. verify unrelated owner work will not be overwritten;
8. read:
   - `docs/phase-5-core-interfaces-handoff.md`
   - `docs/phase-5-contract-bound-evidence-handoff.md`
   - `docs/phase-5-terminal-semantic-integrity-handoff.md`
   - `research/post-phase-4-architecture-synthesis.md`
   - `docs/decisions/0002-openai-codex-model-baseline.md`
   - `experiments/configurations/provider-model-baseline-v0.json`
   - `tools/model_baseline_check.py`
   - `irisx/core/records.py`
   - `irisx/core/interfaces.py`
   - `irisx/core/execution.py`
9. record the exact starting SHA and provider-baseline SHA-256 in the new run definition and eventual handoff.

If the baseline materially diverges, owner work conflicts, or the accepted provider/model configuration can no longer be resolved, STOP rather than silently substituting a different model or provider.

---

## 3. Provider/model authorization

Reuse the repository's accepted machine-readable provider/model baseline:

`experiments/configurations/provider-model-baseline-v0.json`

Do not invent a new provider baseline in this batch.

For this qualification, use the accepted **cheaper** role unless the frozen local catalog check proves it unavailable:

```text
provider_id: openai
execution_surface: codex-cli
model_role: cheaper
model_id: gpt-5.6-luna
reasoning_effort: medium
```

Required pre-run checks:

```powershell
python tools\model_baseline_check.py
python tools\model_baseline_check.py --check-local-catalog
```

The actual run record must explicitly record:

- baseline ID;
- exact baseline SHA-256;
- provider ID;
- execution surface;
- resolved Codex executable path;
- Codex CLI version;
- catalog-check time;
- model role;
- exact model ID;
- reasoning effort;
- tool envelope;
- sandbox/approval policy;
- authentication mode;
- billing mode;
- candidate/program identity;
- token usage if exposed;
- provider cost as observed or `Unknown`;
- retry/failure events;
- wall time.

### Authentication and billing

This batch authorizes the existing connected ChatGPT subscription path **only if it is the actual active authenticated mode at run time**.

Record the actual mode.

API-key fallback is **not authorized**.

Do not change authentication, billing, or account configuration to make the run work.

If the accepted ChatGPT-authenticated Codex path is unavailable, STOP and report `provider execution unavailable`.

---

## 4. Call ceiling

The total Batch 4 model/provider call ceiling is:

```text
qualification provider invocations: 1
automatic retries: 0
manual retries after a completed/failed provider attempt: 0
routes: 0
escalations: 0
recovery actions: 0
```

Preflight commands that make zero model calls are allowed.

Tests must not make provider/model calls.

CLI/unit tests after the qualification run must replay or inspect frozen run artifacts rather than invoke the provider again.

No additional model call is permitted because the first answer was malformed, incorrect, interrupted, or inconvenient.

A provider failure is evidence, not permission to retry.

---

## 5. Qualification task

Add exactly one new substrate:

```text
experiments/substrates/model-execution-qualification-v0/
```

The qualification must be:

- local-input;
- read-only with respect to task state;
- bounded;
- deterministic to verify;
- simple enough that model capability is not the primary experimental variable;
- structured enough to exercise parsing, producer claim, evidence, and terminal adjudication.

Use one frozen record-selection task conceptually equivalent to:

```json
{
  "records": [
    {"id": "alpha", "label": "Alpha", "value": 17},
    {"id": "beta", "label": "Beta", "value": 23},
    {"id": "gamma", "label": "Gamma", "value": 11}
  ],
  "request": "Return the id of the record whose label is Alpha."
}
```

The required semantic output should be a minimal deterministic JSON object:

```json
{"selected_id":"alpha"}
```

The exact fixture values may differ if necessary, but freeze them before the provider call.

The deterministic verifier must compare parsed semantics to the frozen oracle.

Do not introduce a model judge.

Do not use human adjudication as the success oracle.

Do not ask the model to modify repository files or execute tools.

---

## 6. Frozen qualification artifacts

Before any provider/model call, commit the complete qualification definition.

At minimum create and freeze:

```text
experiments/substrates/model-execution-qualification-v0/README.md
experiments/substrates/model-execution-qualification-v0/definition/execution-identity.json
experiments/substrates/model-execution-qualification-v0/definition/qualification-contract.json
experiments/substrates/model-execution-qualification-v0/inputs/task-input.json
experiments/substrates/model-execution-qualification-v0/inputs/model-program.txt
experiments/substrates/model-execution-qualification-v0/scripts/run_qualification.py
experiments/substrates/model-execution-qualification-v0/tests/test_qualification.py
```

The frozen definition must include:

- exact task ID;
- contract ID;
- program ID;
- program SHA-256;
- execution ID;
- configuration ID;
- provider baseline ID/hash;
- provider ID;
- model role and model ID;
- reasoning effort;
- explicit tool envelope;
- auth/billing requirement;
- qualification call ceiling = 1;
- no retry;
- no route;
- no escalation;
- no recovery;
- deterministic semantic oracle;
- evidence requirements;
- terminal record path;
- raw provider event/output path;
- resource/run record path;
- definition/code commit identities required before the call.

Commit the frozen definition and code before the provider invocation.

Do not execute a model from an uncommitted definition.

---

## 7. Model adapter boundary

Implement the provider-specific adapter only inside the new substrate.

Conceptually:

```python
class CodexModelExecutorAdapter(ExecutorAdapter):
    ...
```

Do not add `OpenAI`, `Codex`, `Luna`, or provider-specific classes/types to `irisx.core`.

The adapter may:

1. consume the bound `ExecutionContext`;
2. construct the exact prompt from frozen task input + frozen program;
3. invoke the accepted Codex CLI once;
4. capture raw JSON/event output;
5. extract the model's final textual/structured answer;
6. return one `RawResult`;
7. emit observed task-contract/program evidence refs from the bound context.

The adapter must not decide:

- semantic correctness;
- evidence sufficiency;
- acceptance;
- verified-success eligibility;
- joint interpretation.

Those remain verifier/core responsibilities.

---

## 8. Tool and side-effect envelope

The model qualification is read-only.

The model is not authorized to:

- write repository files;
- mutate task state;
- invoke shell tools for task completion;
- browse the web;
- call external APIs;
- route to another model;
- spawn subagents;
- retry itself.

Use the narrowest Codex CLI sandbox/tool envelope supported by the already accepted local execution surface.

If the installed CLI cannot enforce a sufficiently narrow envelope for this qualification, STOP rather than broadening permissions.

The qualification task itself must require no tools.

---

## 9. Deterministic verifier

Keep the verifier fixture-local.

It must independently evaluate:

1. provider output was captured;
2. the final answer is parseable under the frozen minimal output contract;
3. `selected_id` equals the frozen oracle value;
4. required evidence refs match the bound execution context;
5. read-only task state is unchanged.

The verifier must not trust:

- producer success claim;
- provider exit success alone;
- model self-report;
- telemetry;
- resource usage.

The verifier may classify malformed output as semantic failure.

Do not introduce stochastic or model-based verification.

---

## 10. Resource-accounting requirement

A model-backed execution must not produce a terminal ledger that falsely says zero model usage.

Before the qualification call, inspect the current core resource flow and make the **smallest** change necessary to carry directly observed adapter usage into the terminal `ResourceLedger`.

Preferred constraint:

> Only add the minimum resource-reporting path required by the model-backed adapter; do not build a telemetry framework.

The model-backed terminal/run record must distinguish:

- `model_calls`: exact logical model invocation count if directly controlled/observed;
- `retry_count`: exact zero;
- `route_count`: exact zero;
- `escalation_count`: exact zero;
- `recovery_count`: exact zero;
- `provider_cost_usd`: observed value or `Unknown`;
- token usage: record in the run record if exposed by Codex CLI;
- wall time: directly measured at the adapter/run boundary.

Do not fabricate transport-level network request counts that the CLI does not expose.

If existing `ResourceLedger` cannot represent an unknown transport/network count without falsely recording zero, minimally correct that representation or explicitly add a separate observed-provider-usage record while preserving truthful terminal semantics.

Any core change here must be narrowly justified by truthful accounting for the one model-backed path.

Do not add cost optimization logic.

---

## 11. Run artifacts

The one provider attempt must create a new immutable run directory, for example:

```text
experiments/substrates/model-execution-qualification-v0/runs/qualification-20260905-01/
```

Use a run ID chosen before invocation.

At minimum preserve:

```text
run-manifest.json
provider-events.jsonl
raw-output.txt or raw-output.json
terminal-record.json
resource-record.json
```

If the provider invocation fails before output, preserve:

- command metadata;
- exit code;
- stderr/stdout or event stream;
- failure classification;
- elapsed time;
- zero retry count;
- terminal record showing failure/rejection as appropriate.

Never overwrite a run directory.

Never edit raw provider evidence after creation.

Corrections must create new authored interpretation files, but this batch does not authorize a second provider run.

---

## 12. Run lifecycle

Required order:

```text
plan activation
  -> authority update if needed
  -> qualification definition/code
  -> tests/preflight with zero model calls
  -> commit/freeze definition and code
  -> verify clean tree
  -> verify provider baseline/catalog/auth mode
  -> exactly one provider invocation
  -> preserve raw run evidence
  -> deterministic verification/adjudication
  -> commit run evidence and interpretation
  -> regression validation
  -> durable handoff
  -> plan retirement
  -> normal push
  -> STOP
```

Do not call the provider before the definition and implementation are frozen in Git.

---

## 13. Expected success path

If the model returns the correct structured answer and all bindings are valid, the terminal semantics should be:

```text
actual_outcome: success
producer_claim: success or equivalent observed producer claim
empirical_evidence_status: sufficient
acceptance_decision: accept
verified_success_eligibility: true
joint_interpretation: verified_success
terminal_execution_status: completed
mutation primitive calls: 0
retry count: 0
route count: 0
escalation count: 0
recovery count: 0
model calls: 1
```

This is not a required outcome.

A semantically wrong or malformed model answer is still a valid qualification result if the system correctly records:

- actual failure;
- producer claim separately;
- deterministic verifier result;
- rejected acceptance;
- not eligible;
- resource usage;
- raw provider evidence.

The batch succeeds as an architecture qualification if the boundaries behave correctly, even if the model task itself fails.

---

## 14. Explicitly out of scope

Do not implement or evaluate:

- a second model call;
- model comparison;
- Terra-vs-Luna comparison;
- H-G1;
- H-W1;
- H-C1;
- H-R1;
- router;
- cascade;
- fallback model;
- escalation;
- retry;
- automatic recovery;
- persistence;
- crash/restart;
- multi-host state;
- workflow engine;
- workflow search;
- optimizer integration;
- fine-tuning;
- training;
- multi-agent systems;
- architecture search;
- non-deterministic verifier;
- model judge;
- external/irreversible actions;
- production server/API/UI;
- lifecycle-cost optimization;
- general provider SDK;
- final ontology;
- final architecture.

API-key fallback is explicitly out of scope.

---

## 15. Existing deterministic paths

Both prior paths remain regression anchors:

```text
experiments/substrates/minimal-reliable-execution-v0/
experiments/substrates/core-execution-integration-v0/
```

Their frozen inputs must remain exact.

Their CLI semantics must remain unchanged.

Do not refactor them merely for style.

If the minimum resource-accounting core change affects their ledgers, preserve their directly observed zero model/provider usage and existing adjudication results.

---

## 16. Required tests

Tests must make **zero provider/model calls**.

At minimum cover:

1. model adapter satisfies `ExecutorAdapter` structurally;
2. prompt construction is deterministic from frozen inputs;
3. provider command construction matches the frozen accepted model/config;
4. API-key fallback is not present;
5. retry path does not exist;
6. a frozen successful provider-event fixture can be parsed into `RawResult`;
7. malformed provider output becomes a verifier-detected failure;
8. semantically wrong structured output becomes failure/reject/not eligible;
9. correct structured output becomes verified success;
10. producer success claim cannot override semantic failure;
11. evidence binding still comes from the bound context;
12. read-only state remains unchanged;
13. model-backed resource accounting cannot report `model_calls == 0` after an observed model invocation;
14. retry/route/escalation/recovery remain zero;
15. prior mutation path still passes;
16. prior read-only path still passes;
17. core imports no provider-specific implementation.

Do not add a large provider mocking framework.

Small frozen event/output fixtures are sufficient.

---

## 17. Known regression debt

Preserve the sole existing historical Phase 4 failure exactly.

Final full regression condition:

```text
zero new failures
zero new errors
```

The known retired-plan hash failure may remain.

Do not alter the retired plan, expected hash, test, skip state, or classification.

---

## 18. Preservation requirements

Preserve unchanged:

- `sources/`
- `references/papers/`
- `research/`
- all pre-existing `/runs/`
- all retired Phase 4 plans
- retired post-Phase-4 plan
- retired Phase 5 Batch 1 plan
- retired Phase 5 Batch 2 plan
- retired Phase 5 Batch 3 plan
- all prior durable handoffs
- all four frozen inputs from the two deterministic Phase 5 paths
- accepted provider/model baseline unless a separately justified metadata-only catalog observation is explicitly required

This batch may add exactly one new model-qualification run directory.

No history rewrite.

No force-push.

---

## 19. Authority update

After the plan is committed, minimally update root `AGENTS.md` if necessary so the Current Objective accurately states:

> Phase 5 provisional architecture development is now qualifying exactly one model-backed execution path through the established trust boundaries, while keeping provider-specific implementation outside core and retaining deterministic independent verification.

Do not claim broad model runtime support or production readiness.

---

## 20. Milestone commits

Use small auditable commits.

### WP0 — Activate plan

Add:

`docs/plans/TEMP_PHASE_5_MODEL_EXECUTION_QUALIFICATION.md`

Suggested:

`docs: activate Phase 5 model-execution qualification plan`

### WP1 — Align authority and freeze qualification definition

Add the new substrate definition, frozen task/program, scripts/tests, and minimal authority documentation.

No provider call yet.

Suggested:

`experiments: freeze model-execution qualification definition`

### WP2 — Implement provider-specific adapter and truthful resource flow

Implement only what is required for the one qualification path.

Still no provider call.

Suggested:

`experiments: implement model-execution qualification adapter`

If a minimal core resource-flow change is required, keep it in this milestone or one narrowly named core commit.

### WP3 — Preflight and freeze code

Run all zero-call tests/preflight.

Commit any final deterministic corrections before the provider call.

Suggested:

`tests: qualify model-execution preflight`

After this commit, freeze definition and code SHAs for the run record.

### WP4 — Execute exactly one qualification attempt

Run exactly one provider invocation.

Preserve immutable run evidence.

Commit the run artifacts and factual interpretation.

Suggested:

`experiments: record model-execution qualification run`

No second provider call.

### WP5 — Durable handoff

Create:

`docs/phase-5-model-execution-qualification-handoff.md`

Suggested:

`docs: record Phase 5 model-execution qualification handoff`

### WP6 — Retire plan

Append retirement record only after validation passes.

Suggested:

`docs: retire Phase 5 model-execution qualification plan`

Then push `main` normally.

---

## 21. Validation

Before provider invocation, run zero-call checks including:

```powershell
python tools\repository_check.py
python tools\model_baseline_check.py
python tools\model_baseline_check.py --check-local-catalog

python -m unittest discover -s irisx\core\tests -v
python -m unittest discover -s experiments\substrates\minimal-reliable-execution-v0\tests -v
python -m unittest discover -s experiments\substrates\core-execution-integration-v0\tests -v
python -m unittest discover -s experiments\substrates\model-execution-qualification-v0\tests -v

git diff --check
git diff --cached --check
```

After the one provider attempt, run the same deterministic suites again plus:

- run-artifact structural validation;
- terminal-record consistency validation;
- resource-record validation;
- full established experiment/substrate regression sweep.

Do not rerun the live provider qualification.

Record exact counts.

---

## 22. Acceptance criteria

Batch 4 is accepted if all are true:

1. one and only one new model-backed execution path exists;
2. provider-specific adapter code remains outside `irisx.core`;
3. the accepted provider/model baseline is used;
4. the model/configuration is explicitly frozen before invocation;
5. auth/billing mode is recorded;
6. API-key fallback does not occur;
7. exactly one provider invocation is attempted;
8. retry count is zero;
9. route count is zero;
10. escalation count is zero;
11. recovery count is zero;
12. raw provider evidence is preserved immutably;
13. deterministic independent verification remains authoritative;
14. producer claim remains non-authoritative;
15. contract-bound evidence semantics remain intact;
16. canonical terminal adjudication remains intact;
17. task state remains read-only/unchanged;
18. resource accounting truthfully records observed model usage and unknown values;
19. both existing deterministic paths remain unchanged in behavior;
20. no new regression failure/error exists;
21. H-G1/H-W1/H-C1/H-R1 remain `Not evaluated`;
22. no second model, router, cascade, retry, fallback, persistence, workflow, or model judge is added;
23. preservation checks pass;
24. durable handoff exists;
25. plan is retired separately;
26. final working tree is clean;
27. normal push succeeds;
28. local/remote ahead-behind is `0/0`.

The model answer itself does **not** have to be semantically correct for architectural acceptance, provided the system records and adjudicates the failure correctly.

---

## 23. Allowed conclusions

If the one model-backed path completes and the trust boundaries behave correctly, the strongest allowed conclusion is:

> **Phase 5 Batch 4 complete — one frozen model-backed execution path was qualified through the provisional IRIS-X identity, evidence, deterministic verification, canonical adjudication, and terminal-record boundaries without routing, retry, recovery, or provider-specific core coupling.**

If the provider invocation fails before a model result but failure recording behaves correctly, use a narrower conclusion:

> **Phase 5 Batch 4 complete with provider-execution failure — the frozen model-backed qualification path preserved fail-closed execution, evidence, and terminal accounting boundaries, but successful model-backed execution was not established.**

Do not claim:

- general model-runtime support;
- provider portability;
- model reliability;
- model equivalence;
- production readiness;
- cost advantage;
- final architecture correctness.

---

## 24. Durable handoff

Create:

`docs/phase-5-model-execution-qualification-handoff.md`

Record:

### Repository
- required baseline;
- actual starting SHA;
- definition/code freeze SHA;
- run-evidence commit SHA;
- validated implementation SHA;
- handoff SHA;
- retirement SHA;
- final local/remote SHA;
- ahead/behind;
- clean-tree state;
- push result.

### Provider/configuration
- provider baseline ID/hash;
- Codex path/version;
- catalog observation;
- provider ID;
- model role/model ID;
- reasoning effort;
- auth mode;
- billing mode;
- tool/sandbox envelope;
- API fallback status.

### Call ledger
- provider attempts;
- model calls;
- retries;
- routes;
- escalations;
- recovery;
- token usage if exposed;
- provider cost or `Unknown`;
- wall time.

### Qualification
- task/program identities;
- deterministic oracle;
- raw output path/hash;
- terminal record path/hash;
- semantic verifier result;
- evidence status;
- acceptance;
- eligibility;
- joint interpretation;
- state-before/state-after identity.

### Regression/preservation
- focused counts;
- full regression counts;
- known historical failure;
- sources/papers/research/prior-run preservation;
- prior frozen input preservation.

### Research boundary
Explicitly state H-G1/H-W1/H-C1/H-R1 remain `Not evaluated`.

---

## 25. Retirement

Only after:

- the single provider attempt is preserved;
- deterministic verification/adjudication is complete;
- tests and regression checks pass;
- preservation is verified;
- durable handoff is committed;

append the retirement record.

The retirement must state:

- one-call ceiling consumed or not consumed;
- exact provider outcome;
- exact allowed conclusion;
- remaining uncertainty;
- Phase 5 remains open;
- this plan authorizes no Batch 5.

Commit retirement separately.

---

## 26. Stop conditions

STOP rather than broaden scope if:

- accepted provider/model baseline no longer resolves;
- ChatGPT-authenticated Codex execution is unavailable;
- API-key fallback would be required;
- the model requires a tool-enabled/broader sandbox to complete this simple task;
- frozen definition/code cannot be committed before the call;
- truthful resource accounting requires a broad telemetry redesign;
- a second provider call appears necessary;
- provider output requires a model judge;
- deterministic verifier cannot adjudicate the frozen task;
- a new regression cannot be resolved within scope;
- preservation fails;
- implementation would evaluate H-G1/H-W1/H-C1/H-R1;
- routing/cascade/retry/recovery/persistence/workflow machinery becomes necessary.

A failed first provider attempt is not a reason to retry.

---

## 27. Hard STOP

After:

- exactly one frozen model-backed qualification attempt has been consumed or explicitly blocked before invocation;
- raw evidence is preserved;
- deterministic verification and canonical adjudication are complete;
- focused and full validation complete;
- durable handoff is committed;
- plan is retired;
- `main` is pushed normally;
- local/remote are synchronized;

**STOP.**

Do not start Phase 5 Batch 5.

A future owner instruction must separately authorize the next batch.
