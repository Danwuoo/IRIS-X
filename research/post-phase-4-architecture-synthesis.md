# Post Phase 4 Candidate Architecture Synthesis

- **ID:** `note-2026-09-04-post-phase-4-architecture-synthesis`
- **Status:** exploratory / architecture synthesis
- **Question/scope:** Which minimum responsibilities and data distinctions are justified by the completed Phase 3/4 evidence, and what single local deterministic slice can test those boundaries? This is not a final architecture, production runtime, framework selection, or authorization for another experiment.
- **Primary evidence:** `research/phase-4-closure.md`, the reviewed result records it cites, and `research/problem-definition.md`
- **Controlling plan:** `docs/plans/TEMP_POST_PHASE_4_ARCHITECTURE_SYNTHESIS_AND_MINIMAL_SLICE.md`

## Synthesis conclusion

The smallest defensible candidate is one explicit execution function over immutable identity records, with a policy decision before any mutation, one replaceable executor adapter, an independent verifier that computes semantic and evidence-binding decisions, a separate adjudication step, and one structured terminal record. The exact Python records, JSON shape, SHA-256 use, and local adapter are provisional substrate choices.

The evidence does not justify a general runtime, provider layer, router, cascade, workflow engine, optimizer, persistence system, tracing transport, or automatic recovery loop. Targeted recovery remains an explicit extension point because H-RCV1a supports only five deterministic failure states. H-G1, H-W1, H-C1, and H-R1 remain `Not evaluated`.

## Evidence to constraint matrix

| ID | Evidence and source | Observation or inference | Exact supported scope and horizon | Candidate constraint | Status | Minimum interface consequence |
| --- | --- | --- | --- | --- | --- | --- |
| C-01 | H-M1a in `research/phase-4-mechanism-experiment-results.md`; closure | Directly observed local deterministic result | Registered source identity; 30 records, three repetitions, four injected mismatch types | Evidence-producing execution must carry registered identities and fail closed when identity binding fails. | Core candidate, task-local basis | `ExecutionContext` carries task, contract, program, execution, and configuration identities; a rejected identity cannot call the executor. |
| C-02 | H-V1a in `research/phase-4-mechanism-experiment-results.md`; closure | Directly observed paired oracle-backed result | 360 records over frozen Document Ops outputs; 108 invalid claimed-success records | A producer claim cannot establish accepted or verified success when independent deterministic semantic verification exists. | Core candidate for verifiable bounded tasks | `RawResult.producer_claim` is input to, not output of, `IndependentVerifier`; verifier result is a separate record. |
| C-03 | H-V1b in `research/phase-4-evidence-interception-results.md`; closure | Directly observed paired path/hash result | 576 records; 252 invalid or insufficient evidence variants; local declared files | Evidence must bind to the intended execution and artifact bytes; stale, crossed, missing, extra, or conflicting evidence denies verified-success eligibility without rewriting actual outcome. | Core candidate, evidence type remains task-specific | `EvidenceRef` carries role, artifact identity, path, and hash; verification returns a distinct evidence status. |
| C-04 | H-I1a in `research/phase-4-evidence-interception-results.md`; closure | Directly observed copied-workspace mutation result | 48 records; six prohibited mutation types and two permitted controls over local copies | If prevention is required, policy evaluation must occur before the mutation primitive and a post-state observation must remain separate. | Conditional core boundary on mutating paths | `PolicyGate.evaluate(request)` precedes `ExecutorAdapter.execute`; terminal record exposes decision timing, primitive execution, and before/after state hashes. |
| C-05 | H-O1a in `research/phase-4-mechanism-experiment-results.md`; closure | Directly observed paired instrumentation result | 72 episodes; declared 17-field local profile; deterministic control | Execution must emit enough typed observations and resource fields to reconstruct the path, while preserving `Unknown` when unavailable. The 17-field profile is not universal. | Core record discipline; exact schema provisional | Ordered `Observation` entries and a `ResourceLedger` are attached without deriving outcome from telemetry. |
| C-06 | H-RCV1a in `research/phase-4-reliability-specialization-readiness.md`; closure | Directly observed deterministic recovery result | 30 episodes; five frozen failure states; exactly one declared action | Any recovery must be explicit, bounded, attributable, independently rechecked, and never a hidden retry. | Optional extension; not implemented in this slice | Terminal record always states recovery/retry counts; a future `RecoveryAction` may run only after an explicit adjudicated failure and before independent re-verification. |
| C-07 | H-P1a and reviewed blind interpretation; closure | Directly observed post-freeze model-backed result plus bounded inference | Four generated families, 32 blind tasks, exact Luna program C1, fixed medium/no-tool envelope | A specialization/program used by execution must be an explicit immutable artifact with identity and content hash. Optimizer choice is not a runtime requirement. | Core candidate artifact boundary; optimizer lifecycle unresolved | `ProgramArtifact` contains ID, exact bytes, and SHA-256; loading verifies the contract-bound expected hash before execution. |
| C-08 | `research/evaluation-state-semantics-v1.md`; H-V1a/H-V1b; `research/problem-definition.md` | IRIS-X-authored synthesis supported by direct local observations | Future-facing vocabulary; completeness beyond current task families is not established | Actual outcome, producer claim, evidence status, acceptance, verified-success eligibility, and execution state remain independently sourced. | Core semantic constraint; vocabulary revisable | `TerminalRecord` has separate fields; no generic single `status` field is allowed. |
| C-09 | H-OR1a/H-SR1a in readiness and closure | Directly observed stable-under-horizon results | 480 process-lifetime episodes and 120 reversible cycles; same host and deterministic fixtures | State and process lifetime are declared execution conditions, not evidence of universal durability; state changes require before/after identity. | Context/observation constraint, not a stateful runtime requirement | Context declares state identity; mutating execution records pre/post state hashes. No persistence subsystem is added. |
| C-10 | Phase 4 closure resource and provider boundary | Directly observed resource vectors plus explicit unknowns | 382 H-P1a calls; ChatGPT subscription path; provider cost and reasoning tokens partly unknown | Resource observations remain separate from outcome and monetary lifecycle cost; absent values remain `Unknown`. | Core record discipline; accounting formula unresolved | `ResourceLedger` records directly observed zeroes and `Unknown` fields separately; it cannot change adjudication. |

## Detailed constraint records

### C-01 Registered execution identity

- **Why needed:** H-M1a observed that record-only provenance accepted injected mismatches that registered tree resolution rejected.
- **Boundary:** It establishes only registered local source-snapshot identity checks, not causal provenance or a universal manifest system.
- **Counterevidence/generalization limit:** Upstream provenance is `Unknown`; non-source identity classes and distributed identity are `Not established`.
- **Falsifier:** A frozen comparison showing identity mismatch cannot contaminate evidence or acceptance, or that a smaller binding provides identical detection under the target contract.
- **Decision-critical experiment:** Only if execution spans mutable remote artifacts or multiple hosts; compare the smallest proposed distributed identity binding against injected crossed/stale identities.

### C-02 Independent semantic verification

- **Why needed:** H-V1a found 108 false accepts under claim-only acceptance and zero under independent deterministic comparison in the finite sample.
- **Boundary:** This does not establish perfect verifier reliability, one universal verifier, model-judge truth, or oracle validity outside the fixture contract.
- **Counterevidence/generalization limit:** Human disagreement, stochastic verification, and tasks without deterministic oracles remain `Not evaluated`.
- **Falsifier:** Evidence that an independent verifier is coupled to the producer, materially increases false failure, or adds no information beyond the producer claim on the target task distribution.
- **Decision-critical experiment:** If a required task lacks a deterministic oracle, compare independently authored/human adjudication against candidate verifier designs before making one core.

### C-03 Evidence binding

- **Why needed:** H-V1b showed semantically correct outcomes with stale, crossed, unrelated, conflicting, or missing evidence were not eligible for verified success.
- **Boundary:** SHA/path equality establishes byte binding, not causal lineage, source truth, or universal evidence sufficiency.
- **Counterevidence/generalization limit:** Model-generated citations, remote mutable data, and real-world provenance are `Not established`.
- **Falsifier:** A task contract where evidence identity is intrinsically carried by an independently authenticated result and separate path/hash references add no detection or create false invalidation.
- **Decision-critical experiment:** If remote or mutable evidence becomes required, test authenticated content/version identity and stale/crossed evidence challenges under that exact source contract.

### C-04 Pre-execution policy

- **Why needed:** H-I1a demonstrated that post-hoc checking detected but could not prevent 18 prohibited mutations; the pre-execution arm prevented all 18 and allowed six controls.
- **Boundary:** Only deterministic local actions over copied workspaces were tested. Shell containment, adversarial bypass, external or irreversible actions, and OS sandbox security are `Not established`.
- **Counterevidence/generalization limit:** A read-only operation does not require a mutation gate; a post-state check remains necessary even when policy permits.
- **Falsifier:** A mutation path where the gate can run only after the primitive, or where pre-execution classification cannot distinguish prohibited from permitted action without unacceptable false blocks.
- **Decision-critical experiment:** Before external/irreversible actions, test interception coverage and bypass resistance with a frozen action surface and state oracle.

### C-05 Structured observations

- **Why needed:** H-O1a increased declared field coverage from 0/612 to 612/612 without changing paired outcomes, at measurable artifact cost.
- **Boundary:** The tested 17 fields are insufficient evidence for model, tool, stateful, or production workflows; timing direction was not established.
- **Counterevidence/generalization limit:** More telemetry can add storage, privacy, latency, or coupling costs without improving reconstruction.
- **Falsifier:** A smaller declared field set reconstructs every decision and identity needed by the target contract, making additional fields unnecessary.
- **Decision-critical experiment:** If a production or long-running path is proposed, compare reconstruction failures and overhead across candidate field profiles.

### C-06 Explicit targeted recovery

- **Why needed:** H-RCV1a restored 15/15 frozen deterministic failure states with exactly one declared action and independent final-state checks.
- **Boundary:** Arbitrary diagnosis, retry policy, compensation for external effects, and general recovery are `Not established`.
- **Counterevidence/generalization limit:** Recovery can introduce side effects or obscure terminal failures; no implicit recovery is permitted.
- **Falsifier:** A broader frozen failure distribution where targeted action cannot restore validity or causes new violations at an unacceptable rate.
- **Decision-critical experiment:** Required only when a candidate architecture decision needs recovery beyond an explicit extension; freeze failure taxonomy, one-action treatment, detect-only control, and independent final-state oracle.

### C-07 Immutable specialization artifact

- **Why needed:** H-P1a depended on an optimizer-generated candidate frozen before blind generation; changing bytes would invalidate its identity and result attribution.
- **Boundary:** The evidence supports the exact task-local program artifact and evaluation lifecycle, not optimizer superiority, general model substitution, or monetary lifecycle advantage.
- **Counterevidence/generalization limit:** Repeated optimizer behavior, maintenance economics, distribution shift, and provider alias stability are `Not established` or `Unclear`.
- **Falsifier:** A target execution where program content cannot affect behavior or where an equally small configuration identity already binds exact behavior-producing bytes.
- **Decision-critical experiment:** H-G1 only if automated specialization quality/repeatability becomes required and simpler fixed/manual baselines cannot answer the decision.

### C-08 Separated evaluation semantics

- **Why needed:** H-V1a/H-V1b directly produced false-success and unverified-success cases that a single status would erase.
- **Boundary:** The exact vocabulary is future-facing and may require extension for human disagreement or richer partial evidence.
- **Counterevidence/generalization limit:** No evidence supports a universal scalar reliability label.
- **Falsifier:** A formally defined task contract proving one field can losslessly reconstruct all outcome, evidence, acceptance, and execution distinctions needed for decisions.
- **Decision-critical experiment:** If richer partial evidence is required, compare candidate lattices on adjudicator disagreement and downstream decision errors.

### C-09 Declared state and horizon

- **Why needed:** H-OR1a and H-SR1a results are meaningful only because process lifetime, cycle index, and exact state restoration were explicit.
- **Boundary:** No days/weeks, crash/restart, concurrency, multi-host, or production durability evidence exists.
- **Counterevidence/generalization limit:** A stateless pure task may need no state identity beyond its inputs.
- **Falsifier:** A target task whose complete result is independent of prior/post state and whose contract cannot observe mutation.
- **Decision-critical experiment:** Trigger only when persistent state or long-lived execution becomes a proposed requirement; select a declared duration/failure horizon rather than inferring from current local runs.

### C-10 Separate resource observations

- **Why needed:** Phase 4 observed call, token, byte, and time vectors while provider cost and some fields remained `Unknown`; combining them would fabricate monetary conclusions.
- **Boundary:** No deployment volume, amortization rule, monetary provider cost, or full lifecycle accounting boundary was established.
- **Counterevidence/generalization limit:** Zero local calls in this slice is an observed value, not evidence of zero lifecycle cost.
- **Falsifier:** A future contract with directly attributable complete monetary and non-monetary accounting may support a declared comparison function, but only within that boundary.
- **Decision-critical experiment:** Establish workload horizon and attributable cost sources before using cost to select architecture.

## Smallest candidate architecture

```text
TaskContract + ProgramArtifact
        |
        v
bind immutable ExecutionContext
        |
        v
PolicyGate before mutation (conditional on requested action)
        |
        v
replaceable ExecutorAdapter
        |
        v
RawResult + EvidenceRef[] + observed state transition
        |
        v
IndependentVerifier
  - semantic decision
  - evidence-binding status
        |
        v
Adjudicator
  - actual outcome
  - acceptance
  - verified-success eligibility
        |
        v
TerminalRecord + ordered observations + ResourceLedger

ExplicitRecoveryAction: optional post-failure extension, not in the slice
```

The flow is an inferred minimum ordering that satisfies the observed causal boundaries. It is not evidence that one orchestration topology is universally optimal.

## Candidate data contracts

| Contract | Minimum fields | Why fields stay separate | Status |
| --- | --- | --- | --- |
| `TaskContract` | task ID, contract ID, expected program ID/hash, allowed action policy, semantic success condition, evidence requirements | Binds requested outcome, allowed effects, verifier rule, and evidence expectation before execution | Evidence-backed need; exact JSON provisional |
| `ProgramArtifact` | program ID, exact bytes, content SHA-256 | Preserves behavior-producing artifact identity and detects post-freeze modification | Evidence-backed need; SHA-256 mechanism substrate |
| `ExecutionContext` | task/contract/program/execution/configuration identities and artifact references | Prevents evidence from floating free of the intended execution | Evidence-backed need; record layout provisional |
| `ExecutionRequest` | action ID, operation, target, value | Makes the proposed state change inspectable before the primitive | Evidence-backed for mutating path; fixture operation provisional |
| `PolicyDecision` | decision, reasons, timing, primitive-executed Boolean | Distinguishes prevention from post-hoc detection | Evidence-backed need |
| `RawResult` | producer claim, returned value/state, evidence references, executor observations | Keeps producer assertion and effects separate from verifier/adjudicator truth | Evidence-backed need; adapter payload provisional |
| `VerificationResult` | semantic validity/reasons, evidence status/reasons, observed post-state hash | Separates semantic correctness from evidence sufficiency and state observation | Evidence-backed need |
| `TerminalRecord` | all identities; outcome; producer claim; evidence; acceptance; eligibility; execution; policy; side effects; recovery/retry; observations; resources | Prevents information loss through one overloaded status field | Evidence-backed semantics; complete vocabulary provisional |

## Component decisions

### Context binder

- **Responsibility:** Load and hash the task contract and program, validate expected identities, and produce an immutable execution context.
- **Input/output:** Frozen local artifact paths and execution/configuration IDs -> bound `ExecutionContext` or pre-execution rejection.
- **Trust boundary:** Does not trust filename, caller claim, or stored hash without recomputing bytes.
- **Failure semantics:** Identity or hash mismatch fails closed before executor invocation; outcome/evidence/acceptance remain separately recorded.
- **Side effects:** Reads local fixture bytes only.
- **Why it exists:** C-01, C-03, and C-07.
- **Removal consequence:** Crossed or modified program/contract bytes could enter evidence-producing execution without detection.
- **Classification:** Candidate IRIS-X boundary; JSON loading and hashing are commodity substrate.

### Policy gate

- **Responsibility:** Decide whether a proposed mutation is permitted before the adapter can execute it.
- **Input/output:** `TaskContract` policy plus `ExecutionRequest` -> `PolicyDecision`.
- **Trust boundary:** Receives no executor result and cannot infer post-state.
- **Failure semantics:** Denial prevents adapter invocation; unexpected policy error fails closed.
- **Side effects:** None.
- **Why it exists:** C-04.
- **Removal consequence:** A later post-state check may detect a prohibited mutation but cannot claim prevention.
- **Classification:** Evidence-backed conditional boundary; exact prefix policy is provisional fixture substrate.

### Executor adapter

- **Responsibility:** Apply exactly one permitted request and return a producer claim, raw result, evidence references, and observed primitive count.
- **Input/output:** Bound context plus permitted request -> `RawResult`.
- **Trust boundary:** Its claim and evidence are untrusted inputs to independent verification.
- **Failure semantics:** One terminal failure; zero implicit retries, routes, escalations, or recovery actions.
- **Side effects:** Only the declared in-memory fixture mutation in this slice.
- **Why it exists:** Some execution mechanism is operationally necessary, but its provider/runtime implementation is not an IRIS-X research contribution.
- **Removal consequence:** The slice cannot test execution-to-verification boundaries.
- **Classification:** Commodity/reusable substrate behind a replaceable protocol.

### Independent verifier

- **Responsibility:** Independently recompute semantic validity, evidence bindings, and post-state identity without copying the producer claim.
- **Input/output:** Contract, context, raw result, actual artifact bytes, before/after state -> `VerificationResult`.
- **Trust boundary:** Must not receive challenge validity or a precomputed outcome; does not mutate state.
- **Failure semantics:** Invalid binding and insufficient evidence remain distinct; verifier error cannot yield verified success.
- **Side effects:** Reads artifact bytes only.
- **Why it exists:** C-02 and C-03; semantic and binding decisions remain separate inside one minimal verifier boundary.
- **Removal consequence:** Producer claims or stale/crossed evidence could become accepted success.
- **Classification:** Evidence-backed trust boundary; task oracle implementation is replaceable substrate.

### Adjudicator

- **Responsibility:** Derive actual outcome, acceptance decision, and verified-success eligibility from separately frozen observations.
- **Input/output:** Policy, raw result, and verification -> distinct evaluation fields.
- **Trust boundary:** Never treats producer claim or acceptance as empirical truth.
- **Failure semantics:** Missing/invalid verification denies eligibility; actual success may remain success when only evidence binding fails.
- **Side effects:** None.
- **Why it exists:** C-08.
- **Removal consequence:** The terminal record would collapse false success, unverified success, and execution failure.
- **Classification:** Candidate IRIS-X research semantics expressed as a pure function.

### Terminal record builder

- **Responsibility:** Emit one reconstructable record containing identities, decisions, state transition, observations, recovery/retry declarations, and resource vector.
- **Input/output:** Frozen stage records -> immutable serializable terminal record.
- **Trust boundary:** Records observed unknowns; it does not change adjudication based on telemetry.
- **Failure semantics:** Missing required identity or semantic fields is a terminal-record construction failure, never verified success.
- **Side effects:** CLI prints JSON; tests keep records in memory.
- **Why it exists:** C-05, C-08, C-09, and C-10.
- **Removal consequence:** Execution becomes non-reconstructable and unsupported scalar status may hide distinctions.
- **Classification:** Evidence-backed record discipline; serialization and transport are commodity substrate.

## Selected minimal vertical slice

The slice will live at `experiments/substrates/minimal-reliable-execution-v0/`. This location follows the existing qualification-substrate convention without claiming a measured mechanism experiment or modifying any preserved run.

One deterministic fixture requests an in-memory state transition under a local task contract. The CLI path will:

1. load a JSON task contract and exact program bytes;
2. recompute and verify contract/program identity and hashes;
3. establish explicit execution/configuration identity;
4. evaluate a path policy before the adapter mutation primitive;
5. execute through one injected local adapter with no model or network access;
6. capture producer claim, evidence references, primitive count, and before/after state hashes;
7. independently verify semantic state and artifact bindings;
8. adjudicate outcome, evidence, acceptance, and verified-success eligibility separately;
9. emit a terminal record with ordered observations and directly observed zero/`Unknown` resource fields.

Tests will alter only the fixture or injected adapter to exercise mismatch, false-claim, stale-evidence, prohibited-action, telemetry-invariance, and post-freeze program modification paths. These are boundary tests for one slice, not new empirical evaluations of H-G1/H-W1/H-C1/H-R1 or the complete parent hypotheses.

Recovery is deliberately excluded. The terminal record will state zero recovery actions and zero retries. This is the narrowest reversible interpretation because the required core boundaries can be demonstrated without creating a recovery mechanism, and H-RCV1a does not establish general recovery.

## Explicit extension points and future triggers

| Rank | Extension | Current status | Trigger and decision unlocked |
| ---: | --- | --- | --- |
| 1 | Richer or non-deterministic verifier | `Not evaluated` for human/stochastic adjudication | Trigger when a required task has no deterministic oracle. The experiment would decide whether an independent verifier can remain core and which evidence contract it needs. |
| 2 | Remote/external action policy and evidence binding | `Not established` | Trigger before permitting irreversible, networked, or externally visible effects. The experiment would decide whether the current pre-execution/post-state boundary generalizes or requires a stronger containment/authorization interface. |
| 3 | Persistent/long-running execution state | `Not established` beyond local horizons | Trigger when a candidate task requires continuity across crash/restart, days/weeks, or hosts. The experiment would decide whether state identity/persistence becomes core or remains substrate. |
| 4 | H-G1 optimizer method | `Not evaluated` | Trigger only if automated specialization repeatability is decision-critical and a fixed/manual baseline is inadequate. It would decide whether an optimizer interface belongs in design-time architecture. |
| 5 | H-C1 cascade | `Not evaluated` | Trigger only if one fixed cheap specialist cannot meet declared success/reliability requirements and escalation becomes a candidate trade-off. It would decide whether explicit escalation belongs in runtime architecture. |
| 6 | H-R1 router | `Not evaluated` | Trigger only if heterogeneous tasks require feature-based strong/weak allocation and that allocation changes the frontier. It would decide whether routing belongs in runtime architecture. |
| 7 | H-W1 workflow search | `Not evaluated` | Trigger only if fixed/simple control flow demonstrably cannot satisfy the required task distribution. It would decide whether workflow structure/search belongs in design-time architecture. |

## Remaining uncertainty

- **Unknown:** attributable monetary provider cost, immutable provider implementation snapshot, reasoning-token values for H-P1a, and complete development/maintenance cost.
- **Unclear:** real-workload representativeness and difficulty calibration of the generated families; the appropriate richer partial-evidence semantics; sufficient telemetry for model/tool/stateful production paths.
- **Not established:** complete parent H-M1/H-V1/H-I1/H-O1/H-RCV1/H-P1; final architecture/runtime/product boundary; universal evidence sufficiency; general verifier reliability; external-action safety; production, concurrent, multi-host, adversarial, crash/restart, shifted-distribution, and days/weeks reliability; unified reliability scalar; monetary lifecycle advantage.
- **Not evaluated:** H-G1, H-W1, H-C1, H-R1; fine-tuning; broad architecture search; multi-agent topology; provider routing; cascades; workflow optimization; additional model experiments.

## Decision boundary

This synthesis authorizes only the selected local deterministic substrate slice under the controlling plan. The candidate architecture remains provisional and falsifiable. Completing the slice does not establish the parent hypotheses, a production design, or authority to continue into broad Phase 5 implementation.
