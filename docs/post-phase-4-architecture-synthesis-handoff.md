# Post Phase 4 Architecture Synthesis and Minimal Slice Handoff

- **Status:** result / durable handoff
- **Date:** 2026-09-04 Asia/Taipei
- **Starting branch:** `main`
- **Actual starting main:** `7ae6c6dfd643e79165d26b32cb5b9f82e897806d`
- **Known Phase 4 baseline:** `7ae6c6dfd643e79165d26b32cb5b9f82e897806d`
- **Validated implementation head:** `2061caf794fbe07c4fd185232af7191d27007f07`
- **Remote tracking state:** local `origin/main` remains `7ae6c6dfd643e79165d26b32cb5b9f82e897806d`; no push was authorized or performed
- **Final local main:** the subsequent controlling-plan retirement commit; its full SHA is reported in the owner-facing final handoff because a commit cannot contain its own SHA

## Outcome

The owner-authorized post-Phase-4 batch completed the required architecture synthesis and exactly one local deterministic executable vertical slice. The candidate architecture is provisional and not production-stable. No broad Phase 5 implementation, model experiment, routing, cascade, workflow search, fine-tuning, architecture search, or productionization began.

Phase 4 remained closed. Its task-local claims and generalization boundaries were not strengthened.

## Commit sequence before handoff and retirement

1. `98fba46a22e92515eda945f132d8fd042055df48` — `docs: activate post-phase-4 synthesis plan`
2. `4c982773d0a1a88f3979718366369716d29a1ce6` — `docs: reconcile post-phase-4 authority`
3. `e6c22dd5e2b40dee511894a6f38761d248bcaced` — `research: synthesize post-phase-4 architecture constraints`
4. `27fea795337a3bf85c8d99cafdf1f73baeaea703` — `experiments: freeze minimal execution slice contract`
5. `2061caf794fbe07c4fd185232af7191d27007f07` — `experiments: implement minimal reliable execution slice`

The durable-handoff and controlling-plan-retirement commits follow these milestones and are reported with full SHAs in the owner-facing final response. No commit was amended, rebased, squashed, or pushed.

## Changed files

### Repository authority and navigation

- `AGENTS.md`
- `docs/repository-layout.md`
- `research/README.md`
- `experiments/README.md`
- `.gitattributes`

### Controlling and durable research records

- `docs/plans/TEMP_POST_PHASE_4_ARCHITECTURE_SYNTHESIS_AND_MINIMAL_SLICE.md`
- `research/post-phase-4-architecture-synthesis.md`
- `docs/post-phase-4-architecture-synthesis-handoff.md`

### Single executable slice

- `experiments/substrates/minimal-reliable-execution-v0/README.md`
- `experiments/substrates/minimal-reliable-execution-v0/inputs/task-contract.json`
- `experiments/substrates/minimal-reliable-execution-v0/inputs/specialization-program.txt`
- `experiments/substrates/minimal-reliable-execution-v0/scripts/run_slice.py`
- `experiments/substrates/minimal-reliable-execution-v0/tests/test_slice.py`

No other implementation or experiment directory was added.

## Authority and status changes

Root `AGENTS.md` previously described the repository as early research preparation / corpus organization. The minimum authority repair now states:

- Phase 4 and initial research preparation are complete;
- current work is post-Phase-4 architecture synthesis / minimal architecture development;
- candidate architecture remains provisional, revisable, and not production-stable;
- broad implementation and the explicitly excluded mechanisms require a new owner-authorized scope.

The research and repository-layout navigation wording was updated only to remove the stale phase label and link the durable synthesis. Source-preservation, architecture neutrality, uncertainty discipline, and the research-contribution versus commodity-substrate distinction remain intact.

## Architecture synthesis and evidence matrix

`research/post-phase-4-architecture-synthesis.md` is the controlling durable synthesis. It contains:

- a ten-row evidence-to-constraint matrix covering H-M1a, H-V1a, H-V1b, H-I1a, H-O1a, H-RCV1a, H-P1a, evaluation-state semantics, H-OR1a/H-SR1a, and resource-accounting boundaries;
- direct-observation versus inference classification;
- exact task/sample/horizon boundaries;
- core, conditional, optional, substrate-only, and unresolved classifications;
- minimum interface consequences;
- counterevidence/generalization limits, falsifiers, and future experiment triggers;
- explicit separation of IRIS-X research semantics from commodity implementation substrate.

The synthesis does not treat a predecessor or external framework as authority and does not infer a universal architecture from repeated mechanisms.

## Candidate architecture and interfaces

The smallest candidate execution path is:

```text
TaskContract + immutable ProgramArtifact
  -> bind ExecutionContext and identities
  -> PolicyGate before a mutation primitive
  -> replaceable ExecutorAdapter
  -> RawResult + EvidenceRef[] + state transition
  -> IndependentVerifier for semantics and evidence binding
  -> Adjudicator for outcome, acceptance, and eligibility
  -> TerminalRecord + observations + ResourceLedger
```

Evidence-backed candidate boundaries are identity/provenance binding, producer/verifier separation, path/hash evidence binding, policy-before-mutation when prevention is required, separately sourced evaluation fields, structured observations, explicit zero/unknown resource fields, and immutable program identity.

Provisional substrate choices are Python dataclasses/protocols, JSON, SHA-256, the in-memory state map, prefix policy, one `set` operation, and CLI JSON serialization. The executor is deliberately replaceable and has no provider-specific type.

Targeted recovery is an optional explicit extension. It was not implemented because this slice can demonstrate all required core boundaries without inventing general recovery from H-RCV1a's five deterministic failure states.

## Vertical slice execution path

Location: `experiments/substrates/minimal-reliable-execution-v0/`

The frozen fixture binds:

- task `task.minimal-state-transition.v0`;
- contract `contract.minimal-state-transition.v0`;
- program `program.minimal-deterministic-specialization.v0`;
- program SHA-256 `30b56206f628174443bd2f7ae27e29530ac60c09ecf6d31b29c553ba5f99f242`;
- execution `execution.minimal-slice.v0`;
- configuration `configuration.local-deterministic.v0`;
- one permitted in-memory `scratch/result` state transition.

The CLI loads and hashes artifacts, binds identities, evaluates policy before execution, invokes the local adapter once, records the before/after state, independently verifies semantics and both evidence references, adjudicates separate fields, and prints one terminal record. The validated default path produced:

```text
actual_outcome: success
producer_claim: success
empirical_evidence_status: sufficient
acceptance_decision: accept
verified_success_eligibility: true
joint_interpretation: verified_success
terminal_execution_status: completed
ordered observations: 6
```

The record also reports zero model, network, paid API, tool, retry, route, escalation, and recovery calls. `provider_cost_usd` and `wall_time_ns` remain `Unknown` rather than fabricated.

## Deterministic tests

`experiments/substrates/minimal-reliable-execution-v0/tests/test_slice.py` contains nine passing tests:

1. valid identity/result/evidence yields verified success;
2. crossed task identity rejects before executor invocation;
3. producer success claim cannot override independent semantic failure;
4. stale program evidence hash denies eligibility while actual outcome remains success;
5. prohibited protected-path mutation is denied before the primitive and state remains byte-identical by hash;
6. enabling structured observations does not change adjudication;
7. post-freeze program modification is detected before execution;
8. terminal semantics remain separate and unauthorized behavior counts are zero;
9. frozen contract reload preserves the program hash.

## Validation commands and results

Executed from repository root:

```powershell
python tools\repository_check.py
python -m unittest discover -s experiments\substrates\minimal-reliable-execution-v0\tests -v
python -m py_compile experiments\substrates\minimal-reliable-execution-v0\scripts\run_slice.py experiments\substrates\minimal-reliable-execution-v0\tests\test_slice.py
python experiments\substrates\minimal-reliable-execution-v0\scripts\run_slice.py
git diff --check
git diff --cached --check
```

Results:

- repository validation: PASS, 13 sources and 7 paper artifacts with hashes checked;
- new deterministic tests: 9/9 PASS;
- changed/new Python compilation: PASS;
- default CLI vertical slice: PASS with verified success and six ordered observations;
- whitespace/error checks: PASS.

An additional regression sweep executed all 14 existing experiment/substrate unittest directories. It ran 80 tests: 79 passed and one pre-existing Phase 4 frozen-artifact assertion failed. The failure is in `experiments/exp-2026-09-01-luna-structured-program-specialization/tests/test_contract.py`, which expects the retired Phase 4 controlling plan to retain its pre-retirement SHA-256 `9e2ac0aabcae9a89ed92d9145ec787f4d6ee1920b5344be703498c6435aaf76c` and 55,632 bytes. The exact plan blob already present at starting baseline `7ae6c6dfd643e79165d26b32cb5b9f82e897806d` is 56,877 bytes with SHA-256 `4f3e47a6fa8af63dee6d4397d995a917a216ce70791416909e76a5448697246b` because the Phase 4 retirement record was appended later. This batch did not cause or repair that historical mismatch. Modifying the retired plan or its frozen evidence would violate preservation rules.

## Preservation proof

| Material | Starting identity | Validated identity | Result |
| --- | --- | --- | --- |
| `sources/` | tree `10e28d83184c789fc468ca1edc3bebf42ba40b46` | same tree | unchanged |
| `references/papers/` | tree `ed29ebcde3f01b00a0e49eb33eef1688566dcad3` | same tree | unchanged |
| Pre-existing `/runs/` manifest | 16 directories, 823 files, aggregate SHA-1 `bb18819d893450e18ea5608e691c02ad6f1f96e0` | same counts and aggregate | unchanged |

`git diff --name-only 7ae6c6dfd643e79165d26b32cb5b9f82e897806d -- sources references/papers` returned zero paths. The equivalent filtered diff for every existing `/runs/` path also returned zero paths. The slice created no run directory.

## Explicit exclusions and hypothesis status

- H-G1: `Not evaluated`; no trace-informed optimizer comparison.
- H-W1: `Not evaluated`; no workflow search or code-generation search space.
- H-C1: `Not evaluated`; no weak-to-strong cascade or fallback.
- H-R1: `Not evaluated`; no learned or heuristic router.

No fine-tuning, RL, training, architecture search, multi-agent topology search, provider routing, additional model experiment, model call, API call, network call, authentication change, billing change, retry, escalation, or recovery action occurred.

## Remaining uncertainty

### Unknown

- Attributable monetary provider cost and complete development/maintenance cost.
- Immutable provider implementation snapshot and Phase 4 reasoning-token values.

### Unclear

- Generated-family difficulty and real-workload representativeness.
- Sufficient telemetry for model/tool/stateful production paths.
- Whether future partial evidence needs a richer semantic lattice.

### Not established

- Complete parent H-M1, H-V1, H-I1, H-O1, H-RCV1, and H-P1.
- Final architecture, runtime, ontology, product boundary, or universal evidence contract.
- General verifier reliability, external-action safety, production operation, concurrency, multi-host behavior, adversarial resistance, crash/restart continuity, shifted-distribution reliability, and days/weeks reliability.
- A unified reliability scalar or monetary lifecycle-cost advantage.

### Not evaluated

- H-G1, H-W1, H-C1, H-R1.
- Fine-tuning, workflow optimization, routing/cascades, broad architecture search, multi-agent topology, and additional model experiments.

## Ranked future decision-critical triggers

1. If a required task lacks a deterministic oracle, run a separately scoped verifier/adjudication experiment to decide whether and how the independent verifier remains core.
2. Before external or irreversible actions, run a frozen interception/bypass and authenticated-evidence experiment to decide whether the current policy/evidence boundary generalizes.
3. If a target task requires persistent state across crash/restart, days/weeks, or hosts, run a declared-horizon state experiment to decide whether persistence becomes core or remains substrate.
4. Trigger H-G1 only if automated specialization repeatability is required and fixed/manual specialization cannot answer the design decision.
5. Trigger H-C1 only if a fixed cheap specialist misses declared requirements and explicit escalation becomes a candidate cost/reliability trade-off.
6. Trigger H-R1 only if heterogeneous tasks require feature-based model allocation that materially changes the target frontier.
7. Trigger H-W1 only if fixed/simple control flow demonstrably cannot satisfy the required task distribution.

These are triggers, not authorized next steps.

## Stop boundary

After this handoff is committed and the temporary controlling plan is retired, stop. No next phase or extension is authorized by this record.
