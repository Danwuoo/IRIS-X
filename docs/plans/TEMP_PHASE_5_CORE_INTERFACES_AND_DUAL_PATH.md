# TEMP Phase 5 — Core Execution Interfaces and Dual-Path Integration

Status: **Temporary — controlling execution plan; owner-authorized Phase 5 Batch 1**  
Date: **2026-09-04 Asia/Taipei**  
Repository: **Danwuoo/IRIS-X**  
Required baseline `main`: **`59367c3c50a9e089bdc476cc490c3dc9111edf07`**  
Phase: **Phase 5 — provisional architecture development**  
Batch goal: **extract the evidence-backed execution boundaries into a minimal IRIS-X core interface layer and prove reuse across two deterministic execution paths**  
Architecture authority: **Provisional only; no final architecture claim**  
Hard terminal boundary: **STOP after this batch is validated, handed off, retired, and pushed**

---

## 1. Owner authorization and scope

This plan is the new owner-authorized scope required by the post-Phase-4 handoff.

Phase 4 remains closed. The completed post-Phase-4 architecture-synthesis batch remains historical evidence and must not be reopened or strengthened.

This batch formally begins Phase 5 development, but it does **not** authorize broad Phase 5 implementation. It authorizes only the smallest implementation step needed to turn the already-synthesized execution boundaries into reusable IRIS-X-authored code.

The exact objective is:

> Establish a minimal provisional `irisx` core execution layer that preserves the Phase 3/4 evidence-backed trust boundaries, migrate the existing deterministic minimal slice to that layer without changing its frozen fixture semantics, and demonstrate interface reuse with exactly one second deterministic read-only execution path.

Success in this batch establishes only that the candidate boundaries can be represented and reused in local deterministic code. It does not establish production readiness, general architecture correctness, provider integration, persistence, recovery generality, routing, cascades, workflow search, or lifecycle-cost advantage.

---

## 2. Required starting state

Before substantive work:

1. inspect `git status --short`;
2. inspect `git rev-parse HEAD`;
3. inspect `git rev-parse origin/main`;
4. verify the actual starting `main` is exactly, or is a clean descendant of, `59367c3c50a9e089bdc476cc490c3dc9111edf07`;
5. verify there is no uncommitted owner work that would be overwritten;
6. confirm the following are present:
   - `AGENTS.md`
   - `research/post-phase-4-architecture-synthesis.md`
   - `docs/post-phase-4-architecture-synthesis-handoff.md`
   - `experiments/substrates/minimal-reliable-execution-v0/README.md`
   - `docs/repository-layout.md`
7. record the actual starting full SHA in the eventual retirement record and durable handoff.

If `main` materially diverges from the required baseline, or owner work cannot be preserved safely, STOP rather than silently adapting scope.

---

## 3. Evidence boundary inherited into Phase 5

The controlling synthesis already identifies candidate constraints C-01 through C-10:

- registered execution identity;
- independent semantic verification;
- evidence/path/hash binding;
- pre-execution policy for mutating paths;
- structured observations;
- explicit targeted recovery as an optional extension only;
- immutable specialization/program artifact;
- separated evaluation semantics;
- declared state and reliability horizon;
- separate resource observations.

This batch may encode only the minimum interfaces needed to preserve those distinctions. It must not strengthen the scientific claims behind them.

The following remain unresolved or unevaluated and must not be smuggled into core:

- H-G1 — `Not evaluated`;
- H-W1 — `Not evaluated`;
- H-C1 — `Not evaluated`;
- H-R1 — `Not evaluated`;
- complete parent H-M1/H-V1/H-I1/H-O1/H-RCV1/H-P1 — `Not established`;
- production, concurrent, multi-host, crash/restart, adversarial, shifted-distribution, days/weeks, external-action, irreversible-action, and monetary lifecycle claims — not established.

---

## 4. Why this is the right first Phase 5 batch

The previous batch demonstrated:

```text
TaskContract + immutable ProgramArtifact
  -> ExecutionContext / identity binding
  -> PolicyGate before mutation
  -> ExecutorAdapter
  -> RawResult + EvidenceRef[] + state transition
  -> IndependentVerifier
  -> Adjudicator
  -> TerminalRecord + observations + ResourceLedger
```

The immediate architectural uncertainty is now:

> Can these supported trust boundaries be represented as a reusable IRIS-X core without inheriting fixture-specific behavior, and can a second execution path reuse that core without changing the semantics of the first?

That is the only architecture-development question this batch should answer.

---

## 5. In scope

### 5.1 Minimal IRIS-X-authored core package

Introduce one deliberately small root package:

```text
irisx/
  __init__.py
  core/
    __init__.py
    records.py
    interfaces.py
    execution.py
```

Update `docs/repository-layout.md` minimally to document:

- `irisx/` contains provisional IRIS-X-authored architecture code;
- it is not a production-stable SDK or framework;
- imported source trees remain separate and are never architecture authority;
- experiment substrates may depend on `irisx/`, but `irisx/` must not depend on `experiments/`.

Do not introduce a packaging/build system unless repository-root execution cannot support the required imports. Prefer Python standard library only.

### 5.2 Core records

At minimum represent:

- `TaskContract`
- `ProgramArtifact`
- `ExecutionContext`
- `ExecutionRequest`
- `PolicyDecision`
- `EvidenceRef`
- `RawResult`
- `VerificationResult`
- `Observation`
- `ResourceLedger`
- `TerminalRecord`

Requirements:

- identities are explicit;
- immutable/frozen records are preferred where practical;
- actual outcome, producer claim, evidence status, acceptance, verified-success eligibility, and execution state stay separate;
- no overloaded universal `status` field;
- directly observed zeroes remain zero;
- unavailable values remain explicit `Unknown` or equivalent;
- fixture-specific `set` or read semantics must not become universal core concepts unless truly required by the minimum interface.

### 5.3 Core interfaces

Define only:

- `PolicyGate`
- `ExecutorAdapter`
- `IndependentVerifier`

An adjudication function/class may remain concrete unless evidence requires it to be pluggable.

Do not create a plugin registry, DI framework, workflow engine, provider hierarchy, event bus, or service container.

### 5.4 One explicit execution function

Implement one core execution function or equivalent small orchestrator:

```text
bind identities/artifacts
  -> classify whether mutation prevention is required
  -> policy decision before mutation when required
  -> execute exactly once
  -> independently verify semantics and evidence binding
  -> adjudicate separate terminal fields
  -> emit ordered observations and resource record
```

Required properties:

- identity failure prevents executor invocation;
- prohibited mutation prevents the primitive;
- producer claim cannot override verifier results;
- stale/crossed evidence can deny verified-success eligibility without rewriting an otherwise successful actual outcome;
- retry/recovery/routing/escalation counts remain explicit and zero;
- no hidden retry path exists.

---

## 6. Preserve and migrate the existing slice

Regression anchor:

`experiments/substrates/minimal-reliable-execution-v0/`

Do not change the exact bytes of:

- its frozen task contract;
- its frozen specialization program;
- the program SHA-256 identity declared by the existing handoff.

The default path must keep the same semantic result:

```text
actual_outcome: success
producer_claim: success
empirical_evidence_status: sufficient
acceptance_decision: accept
verified_success_eligibility: true
joint_interpretation: verified_success
terminal_execution_status: completed
```

Its existing nine deterministic checks must remain valid in substance.

Refactor only the minimum code necessary so the slice uses `irisx.core`. Keep fixture-specific mechanics local:

- in-memory state;
- prefix policy;
- `set`;
- fixture semantic verification;
- CLI rendering.

The core must not import the substrate.

---

## 7. Exactly one second deterministic execution path

Add:

```text
experiments/substrates/core-execution-integration-v0/
```

Use one **read-only deterministic lookup/read operation** over a small in-memory record/map.

It must:

- bind task/contract/program identities;
- use an immutable program artifact;
- execute through a different concrete `ExecutorAdapter`;
- perform no mutation;
- record identical before/after state hashes;
- treat mutation prevention as not required for this request;
- independently verify semantic result;
- verify required evidence binding;
- adjudicate using the same terminal semantic fields;
- emit ordered observations and resource ledger;
- use zero model/network/API/retry/route/escalation/recovery calls.

This validates conditional policy behavior and interface reuse. Do not add a third path.

---

## 8. Required tests

Keep the test set compact and architecture-focused.

At minimum demonstrate:

1. migrated mutation path still yields verified success;
2. identity mismatch fails before executor invocation;
3. prohibited mutation executes zero mutation primitives;
4. producer success cannot override verifier failure;
5. stale program/evidence hash can deny eligibility without rewriting actual outcome;
6. read-only path succeeds through the same core orchestrator;
7. read-only path leaves state hash unchanged;
8. two concrete executor adapters work without branching on substrate identity;
9. `irisx/` imports no module from `experiments/`, `sources/`, or `references/`;
10. observations/resource fields do not determine adjudication;
11. retry/recovery/route/escalation/model/network/API counts remain explicitly zero;
12. frozen existing fixture/program identities reconstruct exactly.

Do not introduce a large new testing framework.

---

## 9. Explicitly out of scope

Do not implement or evaluate:

- H-G1, H-W1, H-C1, H-R1;
- model/provider adapters;
- OpenAI/Codex invocation;
- network or API calls;
- routing or cascades;
- retries or automatic recovery;
- persistence or crash/restart state;
- multi-host state;
- workflow engines/search;
- optimizer integration;
- fine-tuning/training;
- multi-agent systems;
- architecture search;
- external/irreversible actions;
- distributed tracing;
- production telemetry;
- UI/API/server layers;
- lifecycle-cost optimization;
- final ontology or final product boundary.

Recovery stays an explicit extension point only.

---

## 10. Known baseline regression debt

The post-Phase-4 handoff records one pre-existing failure:

`experiments/exp-2026-09-01-luna-structured-program-specialization/tests/test_contract.py`

It expects the pre-retirement Phase 4 plan hash while the current baseline contains the later retirement record.

This batch must:

1. reproduce/record the baseline failure before substantive changes if practical;
2. not modify retired Phase 4 evidence or plan bytes to satisfy it;
3. not silently skip/delete/weaken the assertion;
4. allow no new full-suite failures;
5. investigate if the exact baseline failure changes or disappears unexpectedly.

A separate owner-authorized cleanup may reconcile this debt later.

---

## 11. Preservation rules

Remain unchanged unless explicitly named:

- `sources/`
- `references/papers/`
- all pre-existing experiment `/runs/`
- Phase 4 closure artifacts
- retired Phase 4 plans
- retired post-Phase-4 synthesis plan
- frozen inputs of `minimal-reliable-execution-v0`

No amend, rebase, squash, or history rewrite. No force push.

---

## 12. Authority update

After committing this plan and before implementation, minimally update root `AGENTS.md` so current status becomes:

> **Phase 5 — provisional architecture development**

State that the current authorized batch is extracting and validating core execution boundaries, not broad production implementation.

Preserve architecture neutrality, source preservation, uncertainty labels, evidence-first decisions, research/substrate separation, and imported-framework non-authority.

---

## 13. Work packages and milestone commits

### WP0 — Activate plan

Add:

`docs/plans/TEMP_PHASE_5_CORE_INTERFACES_AND_DUAL_PATH.md`

Suggested commit:

`docs: activate Phase 5 core-interface plan`

### WP1 — Phase 5 authority and layout

Update:

- root `AGENTS.md`;
- `docs/repository-layout.md`;
- minimal `irisx/` package skeleton if useful.

Suggested commit:

`docs: authorize Phase 5 core development`

### WP2 — Core contracts/interfaces

Implement:

- `irisx/core/records.py`
- `irisx/core/interfaces.py`

Add focused invariant tests.

Suggested commit:

`core: define execution records and interfaces`

### WP3 — Core execution ordering + original path migration

Implement:

- `irisx/core/execution.py`

Migrate existing slice while preserving frozen inputs and semantic output.

Suggested commit:

`core: integrate minimal reliable execution path`

### WP4 — Second read-only path

Add exactly one integration substrate and focused tests.

Suggested commit:

`experiments: validate read-only core execution path`

### WP5 — Durable handoff

Create:

`docs/phase-5-core-interfaces-handoff.md`

Record starting SHA, implementation SHA, changed files, interfaces, dependency direction, original-path preservation, second-path result, validation, baseline-known regression, preservation proof, exclusions, and uncertainty.

Suggested commit:

`docs: record Phase 5 core-interface handoff`

### WP6 — Retire plan

Append retirement record only after exit criteria pass. State explicitly that this batch is complete but Phase 5 as a whole is not closed.

Suggested commit:

`docs: retire Phase 5 core-interface plan`

After validation and retirement, push `main` normally to `origin/main`. Never force-push.

---

## 14. Validation

Required minimum:

```powershell
python tools\repository_check.py

python -m unittest discover -s experiments\substrates\minimal-reliable-execution-v0\tests -v

python -m unittest discover -s experiments\substrates\core-execution-integration-v0\tests -v

python -m py_compile `
  irisx\__init__.py `
  irisx\core\__init__.py `
  irisx\core\records.py `
  irisx\core\interfaces.py `
  irisx\core\execution.py

python experiments\substrates\minimal-reliable-execution-v0\scripts\run_slice.py

# Also run the equivalent deterministic CLI command for the read-only integration path.

git diff --check
git diff --cached --check
```

Also run the existing experiment/substrate regression sweep using the same method documented in the post-Phase-4 handoff.

Expected full regression condition:

- every previously passing test still passes;
- the one baseline-known Phase 4 retired-plan hash assertion may reproduce exactly;
- no new failures.

Record exact counts.

---

## 15. Acceptance criteria

This batch is accepted only if all are true:

1. `irisx/core` exists as a minimal provisional architecture layer.
2. `irisx/core` has no dependency on experiment/imported-source trees.
3. Existing frozen minimal-slice input/program bytes are unchanged.
4. Existing minimal-slice terminal semantics are preserved.
5. Mutating execution still enforces policy before primitive execution.
6. Independent verification remains separate from producer claims.
7. Evidence sufficiency remains separate from actual outcome.
8. The read-only path uses the same core execution function.
9. The read-only path uses a different concrete executor adapter.
10. Read-only execution performs no state mutation.
11. No retry/recovery/routing/escalation/model/network/API path is introduced.
12. H-G1/H-W1/H-C1/H-R1 remain `Not evaluated`.
13. No new full-suite regression failure exists.
14. `sources/`, `references/papers/`, pre-existing `/runs/`, and retired artifacts are preserved.
15. Repository/whitespace validation passes.
16. Durable handoff exists and the temporary plan is retired.
17. Final `main` is pushed normally to `origin/main`.

---

## 16. Allowed conclusion

If all criteria pass, the strongest allowed conclusion is:

> **Phase 5 Batch 1 complete — the provisional IRIS-X core execution boundaries are implemented and reused across one mutating and one read-only deterministic local path.**

This does not establish final architecture, production runtime, provider integration, persistence, recovery generality, routing/cascades, workflow architecture, optimizer superiority, long-term reliability, or monetary lifecycle advantage.

---

## 17. Future triggers

Do not automatically execute these:

1. no deterministic oracle -> verifier/adjudication experiment;
2. external/irreversible action -> interception/bypass + authenticated evidence experiment;
3. crash/restart/days-weeks/multi-host requirement -> state/persistence experiment;
4. automated specialization repeatability -> H-G1;
5. cheap specialist misses requirement and escalation is proposed -> H-C1;
6. heterogeneous allocation materially affects frontier -> H-R1;
7. fixed/simple control flow is insufficient -> H-W1.

---

## 18. Stop conditions

STOP and report rather than expand scope if:

- starting `main` materially conflicts with baseline;
- frozen input bytes cannot be preserved;
- existing slice migration requires changing task/program semantics;
- core needs to import experiment-specific code;
- second path requires workflow/provider/persistence/routing/cascade/recovery machinery;
- a new regression appears and cannot be attributed cleanly;
- repository/source/run preservation fails;
- a required decision would silently establish H-G1/H-W1/H-C1/H-R1;
- broader owner authorization is required.

Do not weaken criteria to get green.

---

## 19. Required final handoff

Report full SHAs and exact paths for:

- repository baseline/start/final/origin/ahead-behind/clean state/commit sequence/push;
- core files, dependency direction, records/interfaces, execution ordering;
- original path fixture/program preservation and semantic result;
- second path operation, adapter, no-mutation proof, terminal result;
- targeted/full regression counts and exact baseline-known failure status;
- preservation identities for `sources/`, `references/papers/`, pre-existing `/runs/`, retired artifacts;
- H-G1/H-W1/H-C1/H-R1 status;
- explicit confirmation of zero model/provider/network/API/retry/recovery/routing/escalation/persistence/workflow-search work.

Then STOP.

---

## 20. Hard stop

After the core layer is implemented, the original mutation path is migrated/preserved, exactly one read-only path validates reuse, validation is complete, the durable handoff is committed, this plan is retired, and `main` is normally pushed:

**STOP.**

Do not begin another Phase 5 batch under this plan.

A future owner instruction must separately authorize the next Phase 5 scope.
