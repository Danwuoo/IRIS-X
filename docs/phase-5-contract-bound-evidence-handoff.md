# Phase 5 Contract-Bound Evidence Handoff

- **Status:** result / durable handoff
- **Date:** 2026-09-05 Asia/Taipei
- **Phase:** Phase 5 — provisional architecture development
- **Batch:** Batch 2 only
- **Required and actual starting main:** `1ccc6505c0c1e2d418fcc09c36b2e1a330d47ac0`
- **Starting origin/main:** `1ccc6505c0c1e2d418fcc09c36b2e1a330d47ac0`
- **Validated implementation head:** `a6d61056e442ac0256130279d9c9ba0bceca796e`
- **Architecture authority:** provisional; not a final architecture, runtime, SDK, framework, or provenance claim

The handoff commit, separate plan-retirement commit, final local/remote SHA, ahead/behind state, and push result follow this validated implementation head. Their full values are reported in the owner-facing final response because a commit cannot contain its own SHA.

## Outcome

Phase 5 Batch 2 eliminates the caller-substitutable expected-evidence channel across the two existing deterministic execution paths. Evidence declarations now originate in immutable `TaskContract` records, exact artifact hashes are attached during `ExecutionContext` binding, executors emit observed `EvidenceRef` records, and independent verifiers compare those observations against the bound context.

This tightens the provisional C-03 evidence-binding boundary only. It does not establish general or causal provenance, authenticated remote evidence, universal evidence sufficiency, general verifier reliability, production security, or final architecture correctness. Phase 4 and Phase 5 Batch 1 remain closed and unchanged; Phase 5 as a whole remains open.

## Repository and commit sequence

1. `602474290e28cd0fe8662003b2634f39c1b3b854` — `docs: activate Phase 5 contract-bound evidence plan`
2. `47fee90a51b9200d7446b89c2ab3782d19d2a50a` — `core: bind evidence requirements to execution context`
3. `9d4a93308a4494bf52bfb363f4b9b67337d4e4a8` — `core: enforce contract-derived evidence expectations`
4. `a6d61056e442ac0256130279d9c9ba0bceca796e` — `tests: validate contract-bound evidence semantics`

No commit was amended, rebased, squashed, or otherwise rewritten.

## Changed files

### Controlling and durable records

- `docs/plans/TEMP_PHASE_5_CONTRACT_BOUND_EVIDENCE.md`
- `docs/phase-5-contract-bound-evidence-handoff.md`

### Provisional core

- `irisx/core/__init__.py`
- `irisx/core/records.py`
- `irisx/core/interfaces.py`
- `irisx/core/execution.py`
- `irisx/core/tests/test_records.py`

### Existing mutation path

- `experiments/substrates/minimal-reliable-execution-v0/README.md`
- `experiments/substrates/minimal-reliable-execution-v0/scripts/run_slice.py`
- `experiments/substrates/minimal-reliable-execution-v0/tests/test_slice.py`

### Existing read-only path

- `experiments/substrates/core-execution-integration-v0/README.md`
- `experiments/substrates/core-execution-integration-v0/scripts/run_lookup.py`

No input artifact, run, third execution path, package system, or unrelated file changed.

## Prior ambiguity

At the Batch 1 baseline, `execute()` accepted both a bound `TaskContract` and an independent `expected_evidence` sequence. The same independent sequence was also passed through `ExecutorAdapter.execute()` and `IndependentVerifier.verify()`. A caller could therefore theoretically bind one contract while supplying a different expectation set.

The two fixture loaders did derive that argument correctly in practice, but the core API did not enforce a single authority. Batch 2 removes the ambiguity rather than adding a compatibility path.

## Contract-side and observed evidence records

`EvidenceRequirement` is a frozen declaration record containing only:

```text
role
artifact_id
path
```

It means what the immutable task contract requires. Empty fields reject. `TaskContract` stores an immutable tuple of these declarations, rejects duplicate roles, requires the current supported `task_contract` and `program` roles, and requires their artifact identities to match the current contract and expected program.

`BoundEvidenceRequirement` combines one immutable declaration with a SHA-256 derived during context binding. It is not executor output. `ExecutionContext` stores the resulting immutable tuple.

`EvidenceRef` remains separate and means what the executor actually supplied. Evidence validity is not decided by the executor.

No evidence hierarchy, service, registry, artifact database, provider type, or generalized evidence mechanism was added.

## Binding and hash derivation

The binding order is:

```text
validate immutable contract declarations
  -> verify execution identity
  -> verify bound program identity
  -> recompute and verify exact program-content SHA-256
  -> verify declared program-evidence path matches ProgramArtifact.path
  -> bind task_contract declaration to SHA-256(TaskContract.content)
  -> bind program declaration to SHA-256(ProgramArtifact.content)
  -> construct immutable ExecutionContext evidence requirements
```

The existing JSON remains unchanged and contains no circular self-hash. Its role/artifact/path rows construct `EvidenceRequirement` records. Exact bound bytes supply the hashes:

```text
task-contract expected evidence SHA = SHA-256(exact TaskContract.content)
program expected evidence SHA = SHA-256(exact validated ProgramArtifact.content)
```

Malformed, duplicate, missing, or contradictory supported declarations reject during contract construction or binding before executor invocation. No requirement is synthesized from request state or an independent execution argument.

## Final public provisional signatures

```python
execute(
    *,
    contract: TaskContract,
    program: ProgramArtifact | None,
    supplied_identity: ExecutionIdentity,
    request: ExecutionRequest,
    state: MutableMapping[str, Any],
    executor: ExecutorAdapter,
    verifier: IndependentVerifier,
    policy_gate: PolicyGate | None = None,
    collect_observations: bool = True,
) -> TerminalRecord
```

```python
ExecutorAdapter.execute(
    self,
    context: ExecutionContext,
    request: ExecutionRequest,
    state: MutableMapping[str, Any],
) -> RawResult
```

```python
IndependentVerifier.verify(
    self,
    context: ExecutionContext,
    request: ExecutionRequest,
    raw_result: RawResult,
    before_state: Mapping[str, Any],
    after_state: Mapping[str, Any],
) -> VerificationResult
```

There is no `expected_evidence` or equivalent caller parameter. Both concrete adapters read bound requirements from `context` solely to emit their observed evidence. Both independent verifiers separately compare supplied `EvidenceRef` values with `context.evidence_requirements`.

Dependency direction remains `experiments/* -> irisx.core`. The AST guard confirms `irisx/` imports no module from `experiments/`, `sources/`, or `references/`.

## Behavioral proof

### Mutation path

The unchanged default fixture still produces:

```text
actual_outcome: success
producer_claim: success
empirical_evidence_status: sufficient
acceptance_decision: accept
verified_success_eligibility: true
joint_interpretation: verified_success
terminal_execution_status: completed
executor calls: 1
mutation primitive calls: 1
ordered observations: 6
```

Policy remains before the mutation primitive, and prohibited mutation still invokes zero primitives.

### Read-only path

The unchanged default fixture still produces verified success with:

```text
policy_decision: not_required
executor calls: 1
mutation primitive calls: 0
changed_paths: []
state_before_sha256 == state_after_sha256
ordered observations: 6
```

The two paths retain different concrete executor adapters and the same shared orchestration. No third path was added.

### Evidence challenges

Focused tests directly establish the bounded behavior:

| Challenge | Actual outcome | Evidence status | Acceptance | Eligible |
| --- | --- | --- | --- | --- |
| Complete correct supplied evidence | success | sufficient | accept | true |
| Missing required program evidence | success | insufficient | reject | false |
| Wrong/stale program hash | success | invalid_binding | reject | false |
| Crossed artifact identity | success | invalid_binding | reject | false |
| Crossed evidence path | success | invalid_binding | reject | false |
| Duplicate supplied evidence | success | invalid_binding | reject | false |

Evidence invalidity does not rewrite actual outcome. Producer success claims do not override semantic verifier failure. A crossed contract-side program declaration raises before executor invocation, leaving the adapter mutation count at zero. A mismatched declared program-evidence path fails during context binding.

The terminal-record schema remains version 1 and its serialized fields remain unchanged.

## Validation

Executed from the repository root before handoff and retirement:

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

Results:

- repository validation: PASS, 13 registered sources and 7 paper artifacts with hashes checked;
- core tests: 13/13 PASS;
- mutation-path tests: 13/13 PASS;
- read-only-path tests: 9/9 PASS;
- focused total: 35/35 PASS;
- required Python compilation: PASS;
- mutation CLI: PASS with required semantics and six observations;
- read-only CLI: PASS with required semantics, six observations, and unchanged state hash;
- signature inspection: PASS, with no independent expected-evidence parameter;
- whitespace checks: PASS.

The established experiment/substrate sweep covered 15 test directories and ran 93 tests: 92 passed, one failed, and zero errored. The four added experiment tests all pass.

The sole failure is the unchanged baseline debt:

`experiments/exp-2026-09-01-luna-structured-program-specialization/tests/test_contract.py::HPIaContractTests.test_frozen_artifact_hashes_match_exact_bytes`

It observes actual SHA-256 `4f3e47a6fa8af63dee6d4397d995a917a216ce70791416909e76a5448697246b` for `docs/plans/TEMP_PHASE_4_FINAL_MODEL_SPECIALIZATION_AND_CLOSURE.md`, while the preserved historical assertion expects `9e2ac0aabcae9a89ed92d9145ec787f4d6ee1920b5344be703498c6435aaf76c`. The baseline sweep was 88/89 with the same sole failure and zero errors. This batch did not edit, skip, weaken, relabel, or delete the assertion or retired plan.

No new failure or error exists.

## Preservation proof

| Material | Baseline identity | Validated implementation identity | Result |
| --- | --- | --- | --- |
| `sources/` | tree `10e28d83184c789fc468ca1edc3bebf42ba40b46` | same | unchanged |
| `references/papers/` | tree `ed29ebcde3f01b00a0e49eb33eef1688566dcad3` | same | unchanged |
| `research/` and Phase 4 closure | tree `0d89db5ef0d4712e6068bd499c11a852570633da` | same | unchanged |
| Pre-existing `/runs/` | 16 directories, 823 files, manifest SHA-1 `1262137cfc396adefac7ff6accccc45ccd294cf3` | same counts and manifest | unchanged |
| Nine pre-existing plans | manifest SHA-1 `8c719654d902696601e353d905e8fd215d299e0c` | same count and manifest | unchanged |
| Phase 5 Batch 1 durable handoff | blob `972036e40751e200a98573695a76db4b93e95715` | same | unchanged |
| Retired Phase 5 Batch 1 plan | blob `ebfe673ed110cac1745bbfe2f5e011f5843b0cd4` | same | unchanged |
| Post-Phase-4 durable handoff | blob `65cdc8eea13e308d46ee2e3bfa862f3cb9ec5bcd` | same | unchanged |

All four frozen inputs remain exact:

| Path | Bytes | SHA-256 | Baseline/current Git blob |
| --- | ---: | --- | --- |
| `minimal-reliable-execution-v0/inputs/task-contract.json` | 1,283 | `d99571c5ed28b79ef5bb9880a078b02545f7e1d51df811934a95e385785266f2` | `c5503e122d00dff5120d0ce554a785f97757d7d0` |
| `minimal-reliable-execution-v0/inputs/specialization-program.txt` | 257 | `30b56206f628174443bd2f7ae27e29530ac60c09ecf6d31b29c553ba5f99f242` | `1e4e57205743514ea2319898221d369bfdf844c0` |
| `core-execution-integration-v0/inputs/task-contract.json` | 1,228 | `359775eba550d889768228886e29acc1778cbb4e242c6bf317887b3e0985e77a` | `c2c4e08849bd4e3842878e7c2ec5d13476b31336` |
| `core-execution-integration-v0/inputs/lookup-program.txt` | 278 | `8962a8a2478d1664ff4f69b7abc47ef158738b505fb05b59277908004dbae181` | `a8ff6ec77279fa8b5526e282549a324e3a31e994` |

The protected-path diff from baseline returned zero paths, the filtered pre-existing `/runs/` diff returned zero paths, and no run directory was created.

## Research and exclusion boundary

- H-G1: `Not evaluated`.
- H-W1: `Not evaluated`.
- H-C1: `Not evaluated`.
- H-R1: `Not evaluated`.

No model/provider integration, model call, Codex/OpenAI runtime invocation, runtime network/API call, paid API, routing, cascade, escalation, retry, automatic recovery, persistence, crash/restart handling, multi-host state, workflow engine/search, optimizer, fine-tuning, training, multi-agent architecture, broad architecture search, external/irreversible action, production telemetry, distributed tracing, HTTP/API/server surface, UI, lifecycle-cost optimization, final ontology, final product boundary, or additional execution path was implemented, evaluated, or run.

The two successful terminal ledgers retain explicit zero model, network, paid API, tool, retry, route, escalation, and recovery counts. Provider cost and wall time remain `Unknown` and do not determine adjudication.

## Remaining uncertainty and stop boundary

The exact Python record shapes, local JSON construction, SHA-256 mechanism, and two fixture adapters/verifiers remain provisional. General provenance, causal lineage, remote/mutable evidence, authenticated evidence, tasks without deterministic oracles, adversarial resistance, production behavior, and universal evidence sufficiency remain `Not established` or `Not evaluated`.

After this handoff is committed, the Batch 2 plan is retired separately, final validation passes, and `main` is pushed normally to `origin/main`, stop. This handoff does not authorize Phase 5 Batch 3.
