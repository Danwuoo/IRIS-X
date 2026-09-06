# Phase 5 Provisional Architecture State

- **Status:** Phase 5 closure record / provisional architecture state
- **Decision date:** 2026-09-06 Asia/Taipei
- **Required and actual Batch 7 baseline:** `979c443ece39b5631ac8afddabb25229aea958a8`
- **Architecture authority:** evidence-backed within observed scope; provisional, revisable, and not production-stable
- **Primary research records:** `research/phase-5-architecture-consolidation.md` and `research/phase-5-capability-trigger-review.md`
- **Batch 7 provider/model call ceiling and actual:** `0 / 0`

## Phase Decision

# Decision A — Close Phase 5

> **Phase 5 complete — the provisional IRIS-X architecture has been exercised
> across deterministic local execution and an admitted multi-task model-backed
> execution family, with supported trust boundaries, provisional substrate
> choices, unresolved mechanisms, and future capability triggers explicitly
> consolidated. No additional mechanism is presently evidence-triggered.**

This decision closes Phase 5. It does not establish final architecture
correctness, production readiness, provider portability, universal verifier
correctness, external-action safety, persistence, recovery, routing,
escalation, workflow search, automated specialization, or lifecycle-cost
advantage. It does not authorize Phase 6, Batch 8, or another model execution.

## Observed Scope

The state is supported only across:

- one deterministic local in-memory mutation path with policy before the
  primitive;
- one deterministic local read-only lookup path;
- one exact Codex CLI 0.147.0 / OpenAI / GPT-5.6 Luna / medium / ChatGPT
  subscription / read-only / tool-free / zero-retry profile;
- one accepted Batch 4 model-backed record-selection task;
- three Batch 6 model-backed deterministic task families: filtering,
  aggregation, and ordered ranking;
- task-specific deterministic verifiers and local contract/program path-hash
  evidence;
- the finite local failure, identity, evidence, instrumentation, mutation, and
  recovery studies preserved from Phase 4.

The Batch 6 live result is 3/3 `verified_success`, not a general capability or
reliability estimate.

## Supported Trust Boundaries

Within that scope, the evidence supports:

1. explicit immutable behavior-producing program identity;
2. task/contract/program/execution/configuration binding before execution;
3. evidence requirements sourced from the immutable bound contract;
4. producer claim separated from semantic and evidence authority;
5. task-specific independent deterministic verification;
6. canonical derivation of outcome, evidence, acceptance, verified-success
   eligibility, and joint interpretation;
7. conditional policy evaluation before mutation when prevention is required;
8. replaceable executor adapters whose claims remain untrusted;
9. ordered structured observations and separate truthful resource facts;
10. explicit `Unknown` for unavailable network, transport, cost, or other
    measurements instead of fabricated zero;
11. exact-profile admission before the authorized model execution boundary;
12. read-only model execution for the qualified profile;
13. shared adapter reuse without shared task authority; and
14. cross-task contract/program/evidence/schema/verifier isolation.

The authoritative detail, evidence paths, limits, and falsifiers are in
`research/phase-5-architecture-consolidation.md`.

## Current Provisional Realization

The current minimum realization is:

```text
TaskContract + ProgramArtifact
  -> bind ExecutionContext and contract evidence
  -> PolicyGate before mutation when required
  -> one ExecutorAdapter invocation
  -> RawResult + observed EvidenceRef/resource facts
  -> task-specific IndependentVerifier
  -> canonical adjudicate(...)
  -> TerminalRecord + observations + ResourceLedger
```

For the exact qualified model path, the substrate-local admission checker runs
before a separately authorized provider invocation. Provider/Codex/model code
remains outside `irisx.core`.

The following are implementation substrate, not final architectural
requirements:

- Python frozen dataclasses and `Protocol` shapes;
- JSON and JSONL serialization;
- SHA-256 as the binding algorithm;
- local filesystem paths and Git-managed evidence;
- in-memory state maps and the current prefix policy;
- exact class, field, role, stage, and terminal vocabulary;
- terminal schema version 1;
- the current `ResourceLedger` and admission-record field sets;
- the exact Codex CLI 0.147.0 path, command shape, provider slot, and local
  directory layout.

Those shapes may change only under a later evidence-backed, owner-authorized
scope that preserves the supported distinctions.

## Capability State and Future Triggers

| Capability | Evaluation status | Trigger status | Trigger that would reopen the question |
| --- | --- | --- | --- |
| H-G1 automated specialization | `Not evaluated` | `Not triggered` | Repeatable automated program generation becomes required and manual/frozen programs are insufficient. |
| H-W1 workflow machinery/search | `Not evaluated` | `Not triggered` | A declared task cannot meet requirements with simple fixed control flow. |
| H-C1 cascade/escalation | `Not evaluated` | `Not triggered` | The cheaper admitted profile misses a declared requirement and a candidate escalation plausibly resolves it. |
| H-R1 feature-based routing/allocation | `Not evaluated` | `Not triggered` | Alternative allocations show a task-feature-dependent frontier difference. |
| Runtime persistence | `Not evaluated` | `Not triggered` | A task requires crash/restart, multi-day, multi-process, or multi-host state continuity. |
| Nondeterministic verification/model judge | `Not evaluated` | `Not triggered` | A required acceptance condition has no sufficient deterministic oracle. |
| External/irreversible actions | `Not evaluated` beyond local H-I1a | `Not triggered` | A declared task requires authenticated external mutation or irreversible effects. |
| General recovery/retry | `Not evaluated` beyond task-local H-RCV1a | `Not triggered` | A concrete failure class has a specified safe recovery/retry action and a decision-relevant expected benefit. |

These are future trigger conditions, not queued experiments. No next experiment
has been selected or started.

## Owner-Directed Future Model-Run Procedure

Any later owner-authorized model execution must use two separate turns:

1. **Launch turn:** freeze and commit definition/code, pass deterministic
   admission/preflight, verify a clean tree, launch the process in the
   background with stdout/stderr outside the repository, record PID, launch
   timestamp, freeze SHA, and log paths, perform exactly one immediate launch
   confirmation, and stop. Do not poll, wait, sleep/recheck, tail logs, watch
   artifacts, infer results, or inspect output after that confirmation, even if
   the process already exited.
2. **Collection turn:** only after a later explicit owner request, inspect
   completion/output, preserve raw artifacts, validate/adjudicate, commit
   evidence, and continue the separately authorized lifecycle.

This procedure is owner-directed development governance. It is not evaluated
architecture evidence, persistence, recovery, workflow machinery, queue
semantics, or a research result.

## Preserved Uncertainty

- **Unknown:** complete provider and lifecycle cost, provider transport count,
  and immutable provider implementation snapshot.
- **Unclear:** provider/model alias stability, provider portability,
  real-workload representativeness, difficulty calibration, and sufficient
  telemetry for long-running or tool-enabled systems.
- **Not established:** production reliability, general model capability,
  causal provenance, authenticated remote evidence, external-action safety,
  crash/restart or multi-host continuity, general recovery, nondeterministic
  verifier correctness, and a final architecture/product boundary.
- **Not evaluated:** every capability in the trigger table.

## Authority After Closure

Phase 5 evidence, plans, handoffs, definitions, admission records, and run
artifacts remain immutable historical authority within their stated scopes.
The provisional architecture may guide a later separately authorized phase,
but this closure creates no automatic next batch or implementation mandate.

**STOP: no Phase 6, Batch 8, next experiment, or model run is authorized by
this record.**
