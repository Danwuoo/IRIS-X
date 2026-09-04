# Phase 5 Core Interfaces and Dual-Path Integration Handoff

- **Status:** result / durable handoff
- **Date:** 2026-09-04 Asia/Taipei
- **Batch:** Phase 5 Batch 1 only
- **Starting branch:** `main`
- **Required and actual starting main:** `59367c3c50a9e089bdc476cc490c3dc9111edf07`
- **Starting `origin/main`:** `59367c3c50a9e089bdc476cc490c3dc9111edf07`
- **Validated implementation head:** `6364f252877aca18602c19bdcf0d7631d109c4c7`
- **Architecture authority:** provisional; not a final architecture, production runtime, SDK, or framework

The durable-handoff and controlling-plan-retirement commits follow the validated implementation head. Their full SHAs, the final local/remote state, and push result are reported in the owner-facing final response because a commit cannot contain its own SHA.

## Outcome

Phase 5 Batch 1 is complete at the implementation boundary: the evidence-backed execution trust distinctions are represented in a minimal `irisx.core` layer and reused by one preserved mutating path and exactly one new read-only deterministic path. This establishes only local deterministic representation and reuse of the provisional boundaries.

Phase 4 remains closed. No Phase 3/4 claim was strengthened, and Phase 5 as a whole is not closed.

## Commit sequence before handoff and retirement

1. `da5633f7488269b49b438364533edb0a116a17b5` — `docs: activate Phase 5 core-interface plan`
2. `66a62d7cdad7c8613ddffce0b1667fccc9a412fd` — `docs: authorize Phase 5 core development`
3. `c900533b6228fd10a6886c4f634a8d95f858abfd` — `core: define execution records and interfaces`
4. `4bc26af29097011b26bedd8e066465ba079ac0cc` — `core: integrate minimal reliable execution path`
5. `17347c1a6bb0d00ca6a6b7a16b4fd5b182a51b50` — `experiments: validate read-only core execution path`
6. `6364f252877aca18602c19bdcf0d7631d109c4c7` — `experiments: freeze read-only integration inputs`

No commit was amended, rebased, squashed, or otherwise rewritten.

## Changed files

### Authority, layout, and validation

- `.gitattributes`
- `AGENTS.md`
- `docs/repository-layout.md`
- `tools/repository_check.py`
- `docs/plans/TEMP_PHASE_5_CORE_INTERFACES_AND_DUAL_PATH.md`
- `docs/phase-5-core-interfaces-handoff.md`

### Provisional core

- `irisx/__init__.py`
- `irisx/core/__init__.py`
- `irisx/core/records.py`
- `irisx/core/interfaces.py`
- `irisx/core/execution.py`
- `irisx/core/tests/test_records.py`

### Preserved mutation path migration

- `experiments/substrates/minimal-reliable-execution-v0/README.md`
- `experiments/substrates/minimal-reliable-execution-v0/scripts/run_slice.py`

The mutation path's two files under `inputs/` are unchanged.

### Exactly one read-only path

- `experiments/substrates/core-execution-integration-v0/README.md`
- `experiments/substrates/core-execution-integration-v0/inputs/task-contract.json`
- `experiments/substrates/core-execution-integration-v0/inputs/lookup-program.txt`
- `experiments/substrates/core-execution-integration-v0/scripts/run_lookup.py`
- `experiments/substrates/core-execution-integration-v0/tests/test_integration.py`

No third execution path or run directory was added.

## Core boundary

`irisx/core/records.py` defines frozen records for:

- `TaskContract` and exact contract bytes;
- `ProgramArtifact` and exact program bytes;
- `ExecutionIdentity` and `ExecutionContext`;
- `ExecutionRequest` with explicit mutation-prevention classification;
- `PolicyDecision`, `EvidenceRef`, `RawResult`, and `VerificationResult`;
- ordered `Observation` entries;
- a separate `ResourceLedger` with observed zeroes and explicit `Unknown` values; and
- `TerminalRecord`, which keeps actual outcome, producer claim, evidence status, acceptance, verified-success eligibility, and terminal execution state separate.

`irisx/core/interfaces.py` defines only three replaceable protocols: `PolicyGate`, `ExecutorAdapter`, and `IndependentVerifier`. There is no registry, provider hierarchy, service container, workflow abstraction, or plugin system.

`irisx/core/execution.py` implements one ordering:

```text
bind declared identity and exact program bytes
  -> invoke policy before a mutation primitive when required
  -> otherwise record policy as not required for read-only work
  -> invoke one executor adapter exactly once
  -> invoke the independent verifier
  -> adjudicate separate outcome/evidence/acceptance fields
  -> return ordered observations and a separate resource ledger
```

Identity failure prevents executor invocation. A mutation denial prevents the primitive. Producer claims are never inputs to adjudication. Invalid evidence binding can deny verified-success eligibility while actual outcome remains successful. Retry, recovery, routing, and escalation counts are fixed at zero, and no hidden retry branch exists.

Dependency direction is one-way: experiment substrates import `irisx.core`; `irisx/` imports no module from `experiments/`, `sources/`, or `references/`. An AST-based test enforces this boundary.

## Original mutation path preservation

The migrated `minimal-reliable-execution-v0` path retains fixture-specific JSON validation, in-memory state, prefix policy, `set` operation, local adapter, semantic oracle, and CLI rendering. It delegates only the supported reusable ordering and records to `irisx.core`.

Frozen input identities remained exact:

| File | Bytes | SHA-256 | Baseline/current Git blob |
| --- | ---: | --- | --- |
| `inputs/task-contract.json` | 1,283 | `d99571c5ed28b79ef5bb9880a078b02545f7e1d51df811934a95e385785266f2` | `c5503e122d00dff5120d0ce554a785f97757d7d0` |
| `inputs/specialization-program.txt` | 257 | `30b56206f628174443bd2f7ae27e29530ac60c09ecf6d31b29c553ba5f99f242` | `1e4e57205743514ea2319898221d369bfdf844c0` |

The default CLI retains the required semantic result:

```text
actual_outcome: success
producer_claim: success
empirical_evidence_status: sufficient
acceptance_decision: accept
verified_success_eligibility: true
joint_interpretation: verified_success
terminal_execution_status: completed
ordered observations: 6
mutation primitive calls: 1
```

Its nine pre-existing deterministic tests pass without weakening or deleting an assertion.

## Read-only integration path

The only new path performs `lookup` for `records/alpha` in a two-record in-memory map. Its immutable input identities are:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `inputs/task-contract.json` | 1,228 | `359775eba550d889768228886e29acc1778cbb4e242c6bf317887b3e0985e77a` |
| `inputs/lookup-program.txt` | 278 | `8962a8a2478d1664ff4f69b7abc47ef158738b505fb05b59277908004dbae181` |

The fixture-local `ReadOnlyLookupAdapter` is a different concrete `ExecutorAdapter` from the mutation path's `LocalSetAdapter`. The shared core has no branch on either substrate or adapter identity.

The read-only CLI produced:

```text
actual_outcome: success
producer_claim: success
empirical_evidence_status: sufficient
acceptance_decision: accept
verified_success_eligibility: true
joint_interpretation: verified_success
terminal_execution_status: completed
policy_decision: not_required
state_before_sha256: 145075409d8bd61b7c86886efbdab5946d9bbdc69d40d43d1249c785a00e0727
state_after_sha256: 145075409d8bd61b7c86886efbdab5946d9bbdc69d40d43d1249c785a00e0727
changed_paths: []
mutation primitive calls: 0
ordered observations: 6
```

The supplied policy-gate probe was not called. This validates that mutation prevention is conditional while post-state and evidence verification remain explicit.

## Validation

Executed from the repository root:

```powershell
python tools\repository_check.py
python -m unittest discover -s irisx\core\tests -v
python -m unittest discover -s experiments\substrates\minimal-reliable-execution-v0\tests -v
python -m unittest discover -s experiments\substrates\core-execution-integration-v0\tests -v
python -m py_compile irisx\__init__.py irisx\core\__init__.py irisx\core\records.py irisx\core\interfaces.py irisx\core\execution.py
python experiments\substrates\minimal-reliable-execution-v0\scripts\run_slice.py
python experiments\substrates\core-execution-integration-v0\scripts\run_lookup.py
git diff --check
git diff --cached --check
```

Results before handoff and retirement:

- repository validation: PASS, 13 registered sources and 7 paper artifacts with hashes checked;
- core invariant tests: 5/5 PASS;
- original mutation tests: 9/9 PASS;
- read-only integration tests: 9/9 PASS;
- focused tests in total: 23/23 PASS;
- required Python compilation: PASS;
- both deterministic CLIs: PASS with verified success and six ordered observations each;
- whitespace checks: PASS.

The experiment/substrate regression sweep used the same per-test-directory discovery method recorded in the post-Phase-4 handoff. It covered 15 directories and ran 89 tests: 88 passed, one failed, and zero errored.

The sole failure is unchanged baseline debt:

`experiments/exp-2026-09-01-luna-structured-program-specialization/tests/test_contract.py::HPIaContractTests.test_frozen_artifact_hashes_match_exact_bytes`

It still observes SHA-256 `4f3e47a6fa8af63dee6d4397d995a917a216ce70791416909e76a5448697246b` for `docs/plans/TEMP_PHASE_4_FINAL_MODEL_SPECIALIZATION_AND_CLOSURE.md` while the frozen pre-retirement assertion expects `9e2ac0aabcae9a89ed92d9145ec787f4d6ee1920b5344be703498c6435aaf76c`. The same failure reproduced before substantive changes in the baseline 14-directory sweep (80 tests: 79 passed, one failed). This batch did not edit, skip, delete, or weaken the historical assertion or retired plan.

No new regression failure exists.

## Preservation proof

| Material | Baseline identity | Validated implementation identity | Result |
| --- | --- | --- | --- |
| `sources/` | tree `10e28d83184c789fc468ca1edc3bebf42ba40b46` | same tree | unchanged |
| `references/papers/` | tree `ed29ebcde3f01b00a0e49eb33eef1688566dcad3` | same tree | unchanged |
| `research/` including Phase 4 closure evidence | tree `0d89db5ef0d4712e6068bd499c11a852570633da` | same tree | unchanged |
| Pre-existing `/runs/` | 16 directories, 823 files, Git-tree-line manifest SHA-1 `1262137cfc396adefac7ff6accccc45ccd294cf3` | same counts and manifest | unchanged |
| Eight pre-existing retired plans | Git-tree-line manifest SHA-1 `56504fa6db28678b9557855459d0731eb9eca80e` | same count and manifest | unchanged |
| Post-Phase-4 durable handoff | blob `65cdc8eea13e308d46ee2e3bfa862f3cb9ec5bcd` | same blob | unchanged |
| Retired Phase 4 final plan | blob `9e8fd9dd6bf4e1b35bf96be1bfa0ab078fb10f2a` | same blob | unchanged |
| Retired post-Phase-4 synthesis plan | blob `957acaf4bae16a553804b9650b9560ee9fb6b824` | same blob | unchanged |

`git diff --name-only 59367c3c50a9e089bdc476cc490c3dc9111edf07 HEAD -- sources references/papers` returned zero paths. The equivalent filtered diff for every pre-existing `/runs/` path returned zero paths. No run directory was created.

## Hypothesis and exclusion status

- H-G1: `Not evaluated`.
- H-W1: `Not evaluated`.
- H-C1: `Not evaluated`.
- H-R1: `Not evaluated`.

No model or provider adapter, model call, Codex/OpenAI invocation, network call, API call, paid API call, authentication or billing change, retry, automatic recovery, route, cascade, escalation, persistence system, crash/restart state, multi-host state, workflow engine/search, optimizer, fine-tuning, training, multi-agent system, architecture search, external/irreversible action, distributed tracing, production telemetry, UI, API, server, or lifecycle-cost optimization was implemented, evaluated, or run.

The terminal ledgers for both successful paths record zero model, network, paid API, tool, retry, route, escalation, and recovery counts. Provider cost and wall time remain `Unknown`; they do not affect adjudication.

## Remaining uncertainty

The parent H-M1/H-V1/H-I1/H-O1/H-RCV1/H-P1 hypotheses remain `Not established`. Production, concurrent, multi-host, crash/restart, adversarial, shifted-distribution, days/weeks, external-action, irreversible-action, provider, and monetary lifecycle claims remain not established or not evaluated as recorded in the controlling synthesis.

The exact Python records, protocol shapes, JSON fixtures, SHA-256 use, in-memory maps, prefix policy, `set`, `lookup`, and CLI serialization remain provisional substrate choices. This batch does not establish a final ontology, architecture, runtime, SDK, framework, or product boundary.

## Stop boundary

After this handoff is committed, the temporary Phase 5 Batch 1 plan is retired, final validation passes, and `main` is pushed normally to `origin/main`, stop. Do not begin another Phase 5 batch without a new owner instruction.
