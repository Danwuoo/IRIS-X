# Phase 5 Architecture Consolidation

- **ID:** `note-2026-09-06-phase-5-architecture-consolidation`
- **Status:** result / provisional architecture consolidation
- **Question/scope:** What architecture boundaries are supported by Phase 4 and Phase 5 Batch 1 through Batch 6 evidence, and which current Python/substrate choices remain replaceable? This note does not establish a final architecture, production runtime, provider portability, or authority for a new experiment.
- **Controlling plan:** `docs/plans/TEMP_PHASE_5_ARCHITECTURE_CONSOLIDATION_AND_TRIGGER_REVIEW.md`
- **Required and actual Batch 7 baseline:** `979c443ece39b5631ac8afddabb25229aea958a8`
- **Provider/model calls in Batch 7:** `0`

## Evidence Basis

The following were inspected directly from the required baseline before this
consolidation was authored.

### Phase 4 and post-Phase-4 records

- `research/problem-definition.md` — IRIS-X-authored provisional research
  proposition.
- `research/phase-4-mechanism-experiment-results.md` — reviewed direct local
  evidence for H-M1a, H-V1a, and H-O1a.
- `research/phase-4-evidence-interception-results.md` — reviewed direct local
  evidence for H-V1b and H-I1a.
- `research/phase-4-reliability-specialization-readiness.md` — reviewed direct
  local evidence for H-OR1a, H-SR1a, H-RCV1a, and qualified substrates.
- `research/phase-4-closure.md` and `docs/phase-4-closure-validation.md` — Phase
  4 closure synthesis and validation, including H-P1a.
- `research/post-phase-4-architecture-synthesis.md` and
  `docs/post-phase-4-architecture-synthesis-handoff.md` — inferred candidate
  constraints and the first local deterministic slice.

### Phase 5 durable records

- Batch 1: `docs/phase-5-core-interfaces-handoff.md` and retired
  `docs/plans/TEMP_PHASE_5_CORE_INTERFACES_AND_DUAL_PATH.md`.
- Batch 2: `docs/phase-5-contract-bound-evidence-handoff.md` and retired
  `docs/plans/TEMP_PHASE_5_CONTRACT_BOUND_EVIDENCE.md`.
- Batch 3: `docs/phase-5-terminal-semantic-integrity-handoff.md` and retired
  `docs/plans/TEMP_PHASE_5_TERMINAL_SEMANTIC_INTEGRITY.md`.
- Batch 4: all four durable handoffs and all four retired plans for the original
  qualification, qualification repair, tool-compatibility repair, and Run 03.
- Batch 5: `docs/phase-5-model-execution-admission-handoff.md` and retired
  `docs/plans/TEMP_PHASE_5_MODEL_EXECUTION_ADMISSION_HARDENING.md`.
- Batch 6: `docs/phase-5-model-task-family-qualification-handoff.md` and retired
  `docs/plans/TEMP_PHASE_5_MODEL_TASK_FAMILY_QUALIFICATION.md`.

### Current implementation and direct execution evidence

- `irisx/core/records.py`, `irisx/core/interfaces.py`, and
  `irisx/core/execution.py` — current provisional realization.
- Batch 5 admission profile, checker, and current-environment record under
  `experiments/substrates/model-execution-qualification-v0/admission/` and
  `scripts/check_admission.py`.
- Batch 6 admission snapshot, derived summary, and the three task-family
  `terminal-record.json` files.

The Batch 6 terminal records are direct repository evidence. Each records one
model call, sufficient contract/program evidence, independently valid task
semantics, canonical acceptance, unchanged state, zero retry/route/escalation/
recovery/tool counts, and `Unknown` network/provider cost. The summary is
derived-only and does not replace those terminals.

No cited record was missing or materially contradictory. No status in this note
uses `Conflicting evidence`. Real-workload representativeness remains `Unclear`,
but that uncertainty does not contradict the bounded observations.

## Phase 5 Evidence Chain

The lifecycle SHA is included so a validated/result SHA is not mistaken for the
later handoff or plan-retirement commit.

| Batch | Baseline | Validated/result SHA | Lifecycle final SHA | Exact allowed conclusion retained | Direct contribution | Remaining uncertainty |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `59367c3c50a9e089bdc476cc490c3dc9111edf07` | `6364f252877aca18602c19bdcf0d7631d109c4c7` | `1ccc6505c0c1e2d418fcc09c36b2e1a330d47ac0` | Provisional core boundaries were implemented and reused across one mutating and one read-only deterministic local path. | Reusable execution ordering, two concrete adapters, conditional policy, independent verification, and explicit terminal/resource records. | Representation and reuse only; no provider, persistence, recovery, production, or final-architecture conclusion. |
| 2 | `1ccc6505c0c1e2d418fcc09c36b2e1a330d47ac0` | `a6d61056e442ac0256130279d9c9ba0bceca796e` | `954b95d0126ac057789d1eee5584ec7bef391614` | Evidence expectations are contract-bound within the provisional execution context, eliminating caller-substitutable expected-evidence authority across the two paths. | Immutable evidence declarations, exact-byte binding, and adversarial missing/crossed/stale/duplicate evidence rejection. | No causal, authenticated remote, mutable-source, or universal evidence claim. |
| 3 | `954b95d0126ac057789d1eee5584ec7bef391614` | `fd3b179ec7515f435f941b18055077f1ad8a6c81` | `0d738fec43bafc72b5f6ca0f1ca39a6426b0b751` | Terminal outcome, evidence, acceptance, eligibility, and joint interpretation are canonically derived and consistency-checked across the deterministic paths. | One pure adjudication mapping and fail-closed direct-record consistency checks. | No general adjudication, partial/unresolved semantics, probabilistic confidence, or human disagreement result. |
| 4 | `0d738fec43bafc72b5f6ca0f1ca39a6426b0b751` | Run 03 evidence `ccfa44fc255357ba42c8f4ebbd22deda475055e6` | `21f0150aed8b8555b69dc1094a1c3d7a6441732b` | Exactly the frozen Run 03 configuration and bounded task achieved accepted model-backed `verified_success`; provider portability and general capability were not established. | Run 01 and Run 02 preserved fail-closed configuration failures; tool repair passed zero-call strict compatibility; Run 03 exercised one read-only model adapter through deterministic verification and truthful accounting. | One CLI version, provider slot, model, task, auth path, and tool-free envelope; transport count and provider cost `Unknown`. |
| 5 | `21f0150aed8b8555b69dc1094a1c3d7a6441732b` | `22f175b1515aa44d9bc993c0e62c40d1a962c427` | corrected retirement `cd2b3f60a802a3f0438dc38792fd58b45bde820e` | Run 01/02 incompatibilities and the Run 03 configuration are distinguished by a deterministic zero-model-call admission check for the exact Codex CLI 0.147.0 profile. | Exact profile, static historical replay, current-environment admission, fail-closed drift checks, and provider-specific admission outside core. | Admission is compatibility evidence only; future versions, paths, providers, authentication correctness, and production admission remain unestablished. |
| 6 | `cd2b3f60a802a3f0438dc38792fd58b45bde820e` | definition/code freeze `2320858ba1f5dc5d7c68ba426278106c565ac6b4`; summary `81c2d48bc0c8b7390a464e7bd063666b63103342` | `979c443ece39b5631ac8afddabb25229aea958a8` | The same admitted profile was reused across three semantically distinct frozen deterministic tasks while preserving task-specific authority, read-only execution, zero retry, and cross-task isolation; all three were `verified_success`. | Shared substrate-local adapter, three task-specific contracts/programs/schemas/verifiers, 12 crossed-authority rejections, 27/27 offline cases, and 3/3 live verified successes. | No allocation comparison, failure frontier, nondeterministic verifier, persistence, external action, recovery, or generalization beyond the three tasks. |

Batch 4's complete lineage is retained: the original evidence SHA
`d85320d57007677be747924426270feb79cc92e2` and repair evidence SHA
`39f7d2c2344bfd701e30e165d5f30bf913aa07e7` remain correctly adjudicated
failures; `663fdcdffa73305496107a3ed0b86d32f9b90616` repairs strict-config
compatibility without a model call; Run 03 alone supplies successful model-backed
qualification evidence. The earlier failures are not reclassified as model
failures and the later success does not erase them.

## Provisional Architecture Support Matrix

`Current status` describes evidence support for the architecture item, not the
separate capability trigger decision. Trigger status is recorded in
`research/phase-5-capability-trigger-review.md` so `Not evaluated` is not
silently converted to `Not triggered`.

| Candidate / boundary | Primary evidence | Phase 5 exercise | Current status | Scope limitation | Next falsifier/trigger |
| --- | --- | --- | --- | --- | --- |
| Immutable program identity | Phase 4 H-P1a; C-07 | Batches 1, 2, 4, and 6 bind exact program identity/bytes before execution; Batch 6 wrong/crossed program cases reject. | Supported within observed scope | Exact local bytes and frozen task artifacts only. | A task where behavior-producing material cannot be frozen, or a smaller binding with equal crossed/stale detection. |
| Task-contract identity binding | H-M1a; C-01 | Batch 1 binding rejection; Batch 2 contract evidence; Batch 6 distinct contract hashes. | Supported within observed scope | Local immutable contracts; no remote/distributed identity. | Mutable or remote contract authority that current binding cannot identify safely. |
| Execution-context identity binding | H-M1a/H-V1b synthesis | Batches 1–2 bind task, contract, program, execution, and configuration; Batch 6 uses distinct execution IDs. | Supported within observed scope | Single-process local binding and current identity fields. | Cross-host or concurrent execution where the binding cannot prevent crossed authority. |
| Contract-bound evidence | H-V1b; C-03 | Batch 2 removes caller-substitutable expectations; Batch 6 crossed evidence rejects. | Supported within observed scope | Local task-contract/program path/hash evidence; causal provenance is not established. | Authenticated remote/mutable evidence or evidence types not expressible by current declarations. |
| Producer/verifier separation | H-V1a; C-02 | All Phase 5 paths keep producer claim out of adjudication; offline false-claim cases reject. | Supported within observed scope | Deterministic task oracles only. | Evidence of verifier coupling or a target distribution where separation adds no decision information. |
| Deterministic independent verification | H-V1a/H-V1b | Mutation/read-only paths, Run 03, and all Batch 6 tasks use fixture-local deterministic verification. | Supported within observed scope | Oracle validity is task-specific; no claim for open-ended semantic quality. | A required task without a deterministic oracle or with evaluator disagreement. |
| Canonical adjudication | C-08; evaluation-state semantics | Batch 3 centralizes and consistency-checks the current mapping; Batch 4–6 reuse it. | Supported within observed scope | Current deterministic vocabulary and terminal statuses only. | Required partial/unresolved/human-disagreement states that cannot be represented without loss. |
| Task-specific verifier authority | Batch 6 terminal records and isolation suite | Three distinct verifiers; crossed outputs/verifiers reject. | Supported within observed scope | Three bounded deterministic semantics. | Shared adapter or schema behavior bypassing the selected task verifier. |
| Replaceable executor adapter | Post-Phase-4 component boundary | Local mutation, local lookup, Run 03, and Batch 6 model adapter all use the core adapter boundary. | Supported within observed scope | Feasibility of substitution, not universal portability or stable ABI. | A required executor whose resource/evidence/failure behavior cannot pass through the boundary without core provider coupling. |
| Provider-specific code outside core | Batch 4–6 dependency boundary and unchanged `irisx/core` in Batch 6 | Codex/Luna command, parsing, admission, and adapter remain substrate-local. | Provisional implementation choice | Evidence shows this separation works, not that the filesystem/module boundary is uniquely required. | Direct evidence that provider-neutral trust semantics cannot remain independent of a required provider capability. |
| Truthful resource accounting | C-05/C-10; Batch 4–6 resource records | Logical calls and zero mechanism counts are explicit; token/time fields are recorded when observed. | Supported within observed scope | Field completeness and lifecycle-cost boundary are not established. | Reconstruction failure, hidden resource use, or a target decision requiring missing resource dimensions. |
| `Unknown` rather than fabricated zero | Phase 4 resource boundary; Batch 4–6 terminals | Network/transport count and provider cost remain `Unknown`; observed model/tool/retry counts remain numeric. | Supported within observed scope | No complete monetary lifecycle accounting. | Direct attributable measurement would replace `Unknown`; finding a fabricated zero would falsify conformance. |
| Admission before model execution | Batch 4 failure lineage; Batch 5 checker; Batch 6 manifests | Batch 6 records admitted current state before each of three calls; static negative cases consume zero calls. | Supported within observed scope | Exact frozen profile and known configuration failure class. | An admitted execution reproduces a pre-execution configuration failure the checker was intended to reject. |
| Exact-version provider admission | Batch 5 profile/checker/current record | Codex CLI 0.147.0 path/version/config are exact; drift fails closed. | Supported within observed scope | The literal version/profile is evidence scope, not a universal core requirement. | A separately qualified version/profile or proof that a version-independent smaller check preserves the same detection. |
| Read-only model execution | Batch 4 Run 03 and Batch 6 terminals | Four accepted model-backed runs have identical before/after state, empty changed paths, and zero mutation primitives/tools. | Supported within observed scope | Tool-free local-input tasks only. | A required model task with mutation or external side effects. |
| Cross-task adapter reuse | Batch 6 shared adapter and three terminals | One admitted model profile/adapter serves filtering, aggregation, and ranking. | Supported within observed scope | One model/provider/configuration and three small tasks. | Task-specific adapter branching that changes authority or cannot preserve the common boundary. |
| Cross-task identity isolation | Batch 6 isolation suite | Crossed contracts/programs/hashes reject before or during verification. | Supported within observed scope | Frozen local identities only. | Any crossed task identity reaches accepted execution or verified success. |
| Cross-task evidence isolation | Batch 6 isolation suite | Task A/B/C evidence and paths cannot substitute for each other. | Supported within observed scope | Contract/program evidence roles only. | Cross-task evidence accepted under another task contract. |
| Cross-task verifier isolation | Batch 6 isolation suite | A/B/C outputs evaluated under the wrong verifier reject. | Supported within observed scope | Three deterministic verifier implementations. | A wrong verifier can confer acceptance or task semantics become ambiguous. |
| Structured observations | H-O1a; C-05 | Core emits ordered stage observations across deterministic and model-backed paths. | Supported within observed scope | Six current stages and Phase 4's 17-field profile are not universal. | A smaller set reconstructs all decisions, or current fields fail on a required long-running/tool path. |
| Policy before mutation | H-I1a; C-04 | Preserved mutation path gates before the primitive; read-only paths record policy as not required. | Supported within observed scope | Deterministic local copied/in-memory state; no sandbox or external safety claim. | A required mutation surface that can bypass classification/interception or produces unacceptable false blocks. |
| Recovery | H-RCV1a; Phase 5 zero-recovery records | Phase 5 records zero recovery and core rejects implicit retry/recovery; no recovery mechanism was exercised. | Not evaluated | H-RCV1a supports only explicit, bounded, independently rechecked recovery over five deterministic states; general recovery is not established. | A qualifying semantic/transient/partial-effect failure with a specified safe action and decision need. |
| Persistence | H-OR1a/H-SR1a limits; Phase 5 run records | Immutable Git evidence is durable, but runtime state is in-memory/read-only and no restart continuity is exercised. | Not evaluated | No crash/restart, days/weeks, multi-process, or multi-host task requirement. | A declared task requiring state continuity beyond one process/run. |
| Nondeterministic verification | Phase 4/5 deterministic oracle boundary | No model judge, human adjudication, confidence calibration, or evaluator disagreement was used. | Not evaluated | All exercised tasks have frozen deterministic acceptance conditions. | A required task whose correctness cannot be reduced to a deterministic oracle. |
| Routing | H-R1 | Batch 6 holds the allocation fixed across heterogeneous tasks; no alternative allocation is evaluated. | Not evaluated | Heterogeneity alone supplies no frontier comparison. | Evidence that task features predict materially different success/cost/reliability under alternative allocations. |
| Escalation/cascade | H-C1 | Luna achieves 3/3 Batch 6 verified successes; Terra is not exercised in Phase 5. | Not evaluated | No qualifying cheap-profile miss and no escalation comparison. | A declared requirement missed by the cheaper profile plus a plausible resolving candidate. |
| Automated specialization | H-G1; H-P1a boundary | Programs are manually defined or previously frozen; Phase 5 does not automate generation/specialization. | Not evaluated | Multiple frozen programs do not establish a need for automation. | A declared objective requiring repeatable program generation that manual/frozen programs cannot satisfy. |
| Workflow search/machinery | H-W1 | Phase 5 uses fixed bounded one-call control flow; sequential owner launches are not workflow evidence. | Not evaluated | No dynamic planning, graph execution, or workflow candidate comparison. | A required task where simple fixed control flow demonstrably fails. |
| External/irreversible action support | H-I1a generalization limit | Only local reversible/in-memory mutation is exercised; model paths are read-only and tool-free. | Not evaluated | No authenticated network mutation, payment, message, or irreversible effect. | A declared external action requiring pre-execution interception, authorization, and authenticated post-state evidence. |
| Provider portability/general compatibility | Batch 4–6 exact-profile scope | One OpenAI/Codex/Luna/ChatGPT-subscription path is qualified. | Unclear | Provider implementation snapshot and alias stability are unavailable; no second provider/profile comparison exists. | A separately frozen provider/profile qualification with equivalent trust-boundary evidence. |

## Evidence-Backed Invariants Versus Current Realization

The supported conclusion is about trust and information boundaries. It is not
authority for the current data model or repository layout to become permanent.

| Evidence-backed invariant | Current provisional Python/substrate realization | Classification |
| --- | --- | --- |
| Behavior-producing program material is explicit and immutable for an execution claim. | Frozen `ProgramArtifact` dataclass with exact bytes and SHA-256. | Dataclass and SHA-256 are replaceable substrate. |
| Task, contract, program, execution, and configuration identities are bound before evidence-producing execution. | Frozen `TaskContract`, `ExecutionIdentity`, and `ExecutionContext`; `bind_execution()` compares fields. | Record names, field set, and pure-Python binder are provisional. |
| Required evidence authority comes from the bound contract, not a caller or producer. | `EvidenceRequirement` and `BoundEvidenceRequirement` tuples; exactly `task_contract` and `program` roles. | Tuple/role vocabulary and two-role limit are provisional. |
| Observed producer evidence stays distinct from required evidence and verifier decision. | `EvidenceRef` tuples and local path/hash comparison in `evidence_binding()`. | Local filesystem paths and SHA-256 are substrate, not causal provenance. |
| Producer claim does not determine semantic success, evidence sufficiency, acceptance, or eligibility. | `IndependentVerifier` protocol plus `VerificationResult`; `adjudicate()` has no producer-claim parameter. | Protocol/function signatures are provisional; separation is supported. |
| Terminal semantics are canonically derived from authoritative verifier/execution inputs. | `AdjudicationResult`, `adjudicate()`, and `TerminalRecord.__post_init__()` checks. | Exact vocabulary and schema version 1 are revisable. |
| Mutation prevention, when required, occurs before the mutation primitive and remains separately observable. | `requires_mutation_prevention`, optional `PolicyGate`, in-memory state hashes, and `PolicyDecision`. | Boolean classification, prefix policy, and in-memory map are provisional. |
| Executor/provider details do not gain semantic authority, and the execution mechanism can be replaced within the tested boundary. | Python `ExecutorAdapter` protocol; local and Codex adapters remain outside core. | Protocol shape and module/filesystem placement are provisional implementation choices. |
| Execution emits enough ordered observations to reconstruct the tested decision path without telemetry changing adjudication. | Tuple of six `Observation` stages in current paths. | Stage vocabulary and field payloads are provisional. |
| Resource facts remain separate from outcome; observed zero and unavailable values are represented truthfully. | `AdapterResourceReport`/`ResourceLedger`, integer counts, and string `Unknown`. | Exact field set and `Unknown` encoding are provisional. |
| Known-incompatible provider configurations are rejected before a separately authorized model invocation. | Substrate-local JSON admission profile and `check_admission.py` for Codex CLI 0.147.0. | Exact JSON shape, local paths, command canonicalization, and version literal are provider-specific substrate. |
| Each task retains its own contract/program/evidence/schema/verifier authority even when the adapter is shared. | Three Batch 6 file trees and task-family dispatch in the substrate. | Directory layout, filenames, and exact task vocabulary are provisional. |

Additional replaceable shapes include JSON serialization, CLI JSONL capture,
Git-managed local evidence paths, schema version 1, the terminal vocabulary,
the current resource-ledger fields, and the exact admission-record schema. They
are useful concrete realizations and preserved evidence identities, but Phase 5
did not compare them against alternatives.

## Consolidated Provisional Architecture

Within the observed scope, the smallest supported ordering remains:

```text
immutable task contract + program identity
  -> bind execution context and contract evidence requirements
  -> policy decision before a mutation primitive when prevention is required
  -> one replaceable executor adapter invocation
  -> untrusted raw result + observed evidence/resource facts
  -> task-specific independent deterministic verification
  -> canonical adjudication of outcome/evidence/acceptance/eligibility
  -> terminal record + ordered observations + separate resource ledger
```

For the exact qualified provider path, deterministic admission precedes model
execution and provider-specific code remains outside core. For cross-task reuse,
the shared adapter grants no task authority; contracts, programs, schemas,
evidence, oracles, and verifiers remain isolated.

This ordering is an inferred minimum consistent with the observations. It is
not evidence that a general runtime, one ontology, one serializer, one hash
algorithm, or one filesystem layout is final.

## Remaining Uncertainty

- **Unknown:** complete monetary lifecycle cost, transport request counts,
  provider implementation snapshot, and any unobserved provider-side resource
  dimensions.
- **Unclear:** real-workload representativeness, task difficulty calibration,
  provider alias stability, sufficient telemetry for long-running/tool-enabled
  paths, and provider portability.
- **Not established:** final architecture, production readiness, universal
  verifier/evidence correctness, causal provenance, authenticated remote
  evidence, external-action safety, persistence, crash/restart or multi-host
  continuity, general recovery, general model capability, and lifecycle-cost
  advantage.
- **Not evaluated:** H-G1, H-W1, H-C1, H-R1, nondeterministic verification,
  general recovery/retry, persistence, external/irreversible execution,
  routing, escalation, workflow search, and automated specialization.

The separate trigger review determines whether any of these unevaluated
capabilities is presently evidence-triggered. This note itself authorizes no
new experiment or implementation.
