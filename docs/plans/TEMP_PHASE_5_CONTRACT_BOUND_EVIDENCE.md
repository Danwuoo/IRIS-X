# TEMP Phase 5 — Contract-Bound Evidence

Status: **Retired — Phase 5 Batch 2 complete; see Section 15**

- **Date:** 2026-09-05 Asia/Taipei
- **Phase:** Phase 5 — provisional architecture development
- **Batch:** Batch 2
- **Repository:** `Danwuoo/IRIS-X`
- **Required baseline:** `1ccc6505c0c1e2d418fcc09c36b2e1a330d47ac0`
- **Actual starting main:** `1ccc6505c0c1e2d418fcc09c36b2e1a330d47ac0`
- **Starting origin/main:** `1ccc6505c0c1e2d418fcc09c36b2e1a330d47ac0`
- **Architecture authority:** provisional only

## 1. Exact objective

Bind evidence requirements to immutable `TaskContract` and `ExecutionContext` records so the evidence expectations used by the executor and independent verifier derive only from the bound contract and exact bound artifact bytes. Remove the independently caller-supplied expected-evidence argument from the shared execution function and both replaceable execution interfaces.

This batch tightens only C-03 evidence binding across the two existing deterministic execution paths. It does not establish general provenance, causal evidence, authenticated remote evidence, universal verifier correctness, production security, or final architecture correctness.

## 2. Inherited evidence boundary

Phase 4 and Phase 5 Batch 1 remain closed and preserved. The inherited execution order remains:

```text
TaskContract + ProgramArtifact
  -> immutable ExecutionContext
  -> conditional PolicyGate
  -> one ExecutorAdapter call producing observed EvidenceRef records
  -> independent semantic and evidence verification
  -> separate adjudication fields
  -> TerminalRecord + observations + ResourceLedger
```

`EvidenceRequirement` will represent what the contract declares. `EvidenceRef` will continue to represent what execution actually supplied. Producer claims remain separate from verifier truth, and invalid or insufficient evidence must not rewrite an otherwise successful actual outcome.

## 3. Expected implementation surface

- `irisx/core/records.py`
- `irisx/core/interfaces.py`
- `irisx/core/execution.py`
- `irisx/core/__init__.py`
- focused files under `irisx/core/tests/`
- `experiments/substrates/minimal-reliable-execution-v0/scripts/run_slice.py`
- `experiments/substrates/minimal-reliable-execution-v0/tests/test_slice.py`
- `experiments/substrates/core-execution-integration-v0/scripts/run_lookup.py`
- `experiments/substrates/core-execution-integration-v0/tests/test_integration.py`
- the two substrate READMEs only if needed for accurate binding documentation
- `docs/phase-5-contract-bound-evidence-handoff.md`
- this plan for retirement only after all exit criteria pass

No new execution path, package hierarchy, registry, service, or fixture format is authorized.

## 4. Binding invariants

1. Contract declarations construct immutable `EvidenceRequirement` records.
2. Requirement roles are unique, non-empty, and have non-empty artifact IDs and paths.
3. The `task_contract` requirement identifies the current contract.
4. The `program` requirement identifies the expected program.
5. Exact `TaskContract.content` bytes determine the task-contract evidence SHA-256.
6. Exact bound `ProgramArtifact.content` bytes determine the program evidence SHA-256 after program identity/hash validation.
7. Bound expected evidence is exposed by `ExecutionContext` and cannot be replaced by an execution caller.
8. Malformed, duplicate, or contradictory declarations fail before executor invocation.
9. Missing supplied evidence remains `insufficient`; wrong, crossed, unexpected, conflicting, or duplicate supplied evidence remains `invalid_binding`.
10. Existing terminal fields, schema version, execution ordering, and mutation/read-only semantics remain separate and stable.

## 5. Explicit exclusions

Do not implement, evaluate, or run H-G1, H-W1, H-C1, H-R1, model/provider integration, model calls, runtime network/API calls, paid APIs, persistence, crash/restart handling, multi-host state, retry, automatic recovery, routing, cascades, escalation, workflow engines/search, optimizers, fine-tuning, training, multi-agent architecture, broad architecture search, external/irreversible actions, production telemetry, distributed tracing, UI/API/server surfaces, lifecycle-cost optimization, final ontology, final product boundary, or another execution path.

Normal Git fetch/push operations required to complete the batch remain allowed.

## 6. Focused tests

Use standard-library `unittest` only. Add the smallest coverage proving:

- empty requirement fields reject;
- duplicate roles reject;
- task-contract and program requirement identities bind correctly;
- contract/program expected hashes derive from exact bound bytes;
- `execute()` exposes no `expected_evidence` parameter;
- both existing paths still succeed using context-derived expectations;
- missing supplied evidence is `insufficient`;
- wrong hash, crossed artifact/path, and duplicate supplied evidence are `invalid_binding`;
- evidence invalidity preserves a successful actual outcome;
- invalid contract-side declarations fail before executor invocation;
- the one-way `experiments -> irisx.core` dependency remains enforced.

Do not add broad combinatorial coverage or another testing framework.

## 7. Preservation requirements

Preserve byte-identical and unchanged:

- `sources/`;
- `references/papers/`;
- `research/` and Phase 4 closure artifacts;
- all 16 pre-existing `/runs/` directories and 823 files;
- all nine pre-existing plans, including retired Phase 5 Batch 1;
- the post-Phase-4 and Phase 5 Batch 1 durable handoffs;
- both existing task-contract JSON files;
- both existing program text files.

No run directory may be created. No amend, rebase, squash, history rewrite, or force-push is allowed.

## 8. Baseline-known regression debt

The baseline experiment/substrate sweep ran 89 tests across 15 test directories: 88 passed, one failed, and zero errored. The sole failure remains `HPIaContractTests.test_frozen_artifact_hashes_match_exact_bytes`, where the retired Phase 4 plan has actual SHA-256 `4f3e47a6fa8af63dee6d4397d995a917a216ce70791416909e76a5448697246b` and the preserved historical assertion expects `9e2ac0aabcae9a89ed92d9145ec787f4d6ee1920b5344be703498c6435aaf76c`.

Do not modify, skip, weaken, or relabel this historical assertion or its artifacts. Final regression may retain exactly this failure and no other.

## 9. Milestone commits

1. `docs: activate Phase 5 contract-bound evidence plan`
2. `core: bind evidence requirements to execution context`
3. `core: enforce contract-derived evidence expectations`
4. `tests: validate contract-bound evidence semantics`
5. `docs: record Phase 5 evidence-binding handoff`
6. `docs: retire Phase 5 evidence-binding plan`

Commits remain small and auditable. They must not be amended, squashed, rebased, or rewritten.

## 10. Validation

Run from the repository root:

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

Also repeat the established full experiment/substrate regression sweep and record exact counts. Every previously passing test must remain passing, the one baseline-known failure may remain exactly, and no new failure or error is permitted.

## 11. Acceptance criteria

The batch is complete only when all owner-specified criteria are satisfied: immutable contract-side requirements exist; exact bound bytes supply expected hashes; context determines expectations; no public execution/adapter/verifier signature accepts independent expectations; declarations fail closed; evidence statuses remain distinct; both existing paths retain their terminal behavior and six observations; all frozen inputs and protected repository material retain baseline identities; no third path or excluded mechanism exists; focused tests and validation pass; full regression has no new failure; H-G1/H-W1/H-C1/H-R1 remain `Not evaluated`; a durable handoff is committed; this plan is retired separately; the tree is clean; a normal push succeeds; and local/remote ahead-behind is `0/0`.

## 12. Final handoff requirements

Create `docs/phase-5-contract-bound-evidence-handoff.md` recording:

- baseline, actual start, implementation, handoff, final, origin, ahead/behind, clean state, commit sequence, and push result;
- the prior authority ambiguity and exact new records, binding/hash derivation, final signatures, and dependency direction;
- mutation/read-only results and missing, wrong, crossed, duplicate, and invalid-declaration behavior;
- focused/full test counts and exact baseline-debt status;
- preservation identities for sources, papers, research, runs, plans, handoffs, and all four frozen inputs;
- H-G1/H-W1/H-C1/H-R1 as `Not evaluated`;
- explicit confirmation that no excluded mechanism ran.

## 13. Allowed conclusion

The strongest allowed conclusion is:

> Phase 5 Batch 2 complete — evidence expectations are contract-bound within the provisional IRIS-X execution context, eliminating caller-substitutable expected-evidence authority across the two existing deterministic paths.

This is a provisional local architecture-development result only.

## 14. Hard STOP

After implementation, focused and full validation, preservation proof, durable handoff, separate plan retirement, normal push, and local/remote synchronization, **STOP**.

This plan authorizes no Phase 5 Batch 3 or additional feature.

## 15. Retirement record

- **Retired on:** 2026-09-05 Asia/Taipei
- **Required and actual starting main:** `1ccc6505c0c1e2d418fcc09c36b2e1a330d47ac0`
- **Plan activation:** `602474290e28cd0fe8662003b2634f39c1b3b854`
- **Evidence-requirement representation and binding:** `47fee90a51b9200d7446b89c2ab3782d19d2a50a`
- **Contract-derived execution interfaces:** `9d4a93308a4494bf52bfb363f4b9b67337d4e4a8`
- **Adversarial and regression coverage:** `a6d61056e442ac0256130279d9c9ba0bceca796e`
- **Durable handoff:** `5b1ca2822addfbd5298e754c993042461d385112`
- **Focused tests:** 35/35 passed (13 core, 13 mutation, 9 read-only)
- **Regression sweep:** 93 tests across 15 experiment/substrate directories; 92 passed, one unchanged baseline-known failure remained, and zero errored
- **Repository validation:** passed with 13 sources and 7 paper artifacts
- **Preservation:** protected source, paper, research, run, prior-plan, prior-handoff, and all four frozen-input identities remained unchanged
- **H-G1/H-W1/H-C1/H-R1:** `Not evaluated`
- **History:** no amend, rebase, squash, force-push, or other history rewrite
- **Push:** normal push follows this retirement commit; final local/remote identity is reported in the owner-facing response

The exact allowed conclusion is:

> Phase 5 Batch 2 complete — evidence expectations are contract-bound within the provisional IRIS-X execution context, eliminating caller-substitutable expected-evidence authority across the two existing deterministic paths.

Remaining uncertainty includes general or causal provenance, authenticated remote evidence, mutable evidence sources, universal evidence sufficiency, general verifier correctness, production security, adversarial resistance, and final architecture correctness. These remain `Not established` or `Not evaluated`.

No provider/model/network/API runtime mechanism, persistence, retry, recovery, routing, cascade, escalation, workflow search, optimizer, training, multi-agent system, architecture search, production infrastructure, or additional execution path was implemented, evaluated, or run.

This retirement completes Batch 2 only. Phase 5 remains open, and this plan authorizes no further Phase 5 batch.

**STOP.**
