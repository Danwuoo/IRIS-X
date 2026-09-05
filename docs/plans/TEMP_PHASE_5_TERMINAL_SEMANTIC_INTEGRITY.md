# TEMP Phase 5 — Terminal Semantic Integrity

Status: **Temporary — controlling execution plan; owner-authorized Phase 5 Batch 3**  
Date: **2026-09-05 Asia/Taipei**  
Repository: **Danwuoo/IRIS-X**  
Required baseline `main`: **`954b95d0126ac057789d1eee5584ec7bef391614`**  
Phase: **Phase 5 — provisional architecture development**  
Batch: **Batch 3**  
Goal: **centralize terminal adjudication and make terminal semantic states canonically derived and internally consistent**  
Architecture authority: **Provisional only**  
Hard boundary: **STOP after validation, durable handoff, retirement, and normal push**

---

## 1. Authorization and scope

Phase 4 remains closed. Phase 5 Batch 1 and Batch 2 remain complete and retired. Their evidence, frozen inputs, plans, and handoffs must not be reopened or strengthened.

This batch authorizes exactly one hardening step:

> Make terminal adjudication a single canonical core operation and reject internally inconsistent terminal semantic states, while preserving the behavior and serialized outputs of the two existing deterministic execution paths.

This batch does **not** authorize provider/model integration, additional execution paths, persistence, retry, recovery implementation, routing, cascades, workflow engines/search, optimizer integration, fine-tuning, training, multi-agent systems, architecture search, production infrastructure, external actions, or ontology redesign.

---

## 2. Required starting state

Before substantive work:

1. inspect `git status --short`;
2. inspect `git rev-parse HEAD`;
3. inspect `git rev-parse origin/main`;
4. inspect `git rev-list --left-right --count origin/main...main`;
5. verify actual starting `main` is exactly, or a clean descendant of, `954b95d0126ac057789d1eee5584ec7bef391614`;
6. verify unrelated owner work will not be overwritten;
7. read all applicable `AGENTS.md` files;
8. read:
   - `docs/phase-5-core-interfaces-handoff.md`
   - `docs/phase-5-contract-bound-evidence-handoff.md`
   - `research/post-phase-4-architecture-synthesis.md`
   - `irisx/core/records.py`
   - `irisx/core/interfaces.py`
   - `irisx/core/execution.py`

If baseline materially diverges or owner work cannot be preserved safely, STOP.

---

## 3. Inherited baseline

Batch 2 established:

- immutable task/program identity;
- contract-bound evidence requirements;
- exact task-contract/program hash binding;
- producer claim separated from independent verification;
- outcome/evidence/acceptance/verified-success/execution-state separation;
- one mutating and one read-only deterministic path;
- no caller-supplied expected-evidence authority;
- no provider/model/network/API/retry/recovery/routing/escalation/persistence/workflow-search behavior.

Do not weaken any of these properties.

H-G1, H-W1, H-C1, H-R1 remain `Not evaluated`.

---

## 4. Problem to solve

Current execution code derives terminal semantics in `execute()`, while `TerminalRecord` can also be constructed directly. The architecture needs one explicit source of truth for:

```text
VerificationResult
  -> actual_outcome
  -> acceptance_decision
  -> verified_success_eligibility
  -> joint_interpretation
```

Target invariant:

> For the currently supported deterministic semantics, terminal outcome, evidence status, acceptance, verified-success eligibility, and joint interpretation must be canonically derived from authoritative inputs and must not be independently forgeable into contradictory combinations.

Do not claim general adjudication is solved.

---

## 5. Authority documentation update

After this plan is committed and before core changes, update root `AGENTS.md` minimally so the Current Objective reflects:

> Phase 5 provisional core hardening, with the current authorized batch limited to terminal adjudication integrity across the existing deterministic paths.

Preserve architecture neutrality, source preservation, evidence-first development, uncertainty discipline, and imported-framework non-authority.

---

## 6. Canonical adjudication operation

Introduce one small pure deterministic core adjudication operation. A reasonable shape is:

```python
@dataclass(frozen=True)
class AdjudicationResult:
    actual_outcome: str
    acceptance_decision: str
    verified_success_eligibility: bool
    joint_interpretation: str


def adjudicate(
    verification: VerificationResult,
    *,
    terminal_execution_status: str,
) -> AdjudicationResult:
    ...
```

The exact API may differ if simpler.

Requirements:

- one canonical implementation;
- no dependence on producer claim;
- no dependence on telemetry/observations;
- no dependence on `ResourceLedger`;
- no provider/model identity dependency;
- deterministic for identical authoritative inputs;
- no rules engine or plugin architecture;
- limited to the currently supported vocabulary.

---

## 7. Supported bounded semantics

### Verified success

If semantic verification succeeds, evidence is `sufficient`, and terminal execution completed:

```text
actual_outcome = success
acceptance_decision = accept
verified_success_eligibility = true
joint_interpretation = verified_success
```

### Semantic success + insufficient evidence

```text
actual_outcome = success
acceptance_decision = reject
verified_success_eligibility = false
joint_interpretation = unverified_success
```

### Semantic success + invalid evidence binding

```text
actual_outcome = success
acceptance_decision = reject
verified_success_eligibility = false
joint_interpretation = unverified_success
```

### Semantic failure

Producer claims cannot override verifier truth. For the supported deterministic failure path:

```text
actual_outcome = failure
acceptance_decision = reject
verified_success_eligibility = false
joint_interpretation = correctly_recognized_failure
```

### Pre-execution rejection

Preserve existing rejected/binding-failure semantics. Do not fabricate semantic execution when execution never occurred.

---

## 8. Do not redesign the vocabulary

Do not redesign `partial`, `unresolved`, probabilistic confidence, human disagreement, multi-verifier consensus, richer evidence lattices, or a reliability scalar.

Preserve unused enum values unless correctness requires otherwise.

---

## 9. Refactor `execute()`

Normal completed execution should become conceptually:

```text
verification
  -> adjudicate(...)
  -> TerminalRecord
```

Remove duplicate mapping logic from `execute()`. Do not recreate alternate mappings in serializers, adapters, CLIs, or tests.

---

## 10. Defensive `TerminalRecord` validation

Direct construction of contradictory terminal states must fail closed.

At minimum reject:

1. semantic valid + `actual_outcome=failure`;
2. semantic invalid + `actual_outcome=success`;
3. terminal evidence status differing from verifier evidence status;
4. `accept` when canonical adjudication says reject;
5. eligibility true when canonical adjudication says false;
6. non-canonical `joint_interpretation`;
7. eligibility true for non-success;
8. eligibility true without sufficient evidence;
9. eligibility true without acceptance;
10. any attempt for producer claim to determine terminal truth.

Avoid circular validation. Prefer comparison against the canonical adjudication result for adjudicable states.

---

## 11. Preserve producer/evidence authority separation

These must remain true:

```text
producer_claim != decision authority
```

and:

```text
semantic success + insufficient/invalid evidence
=> actual_outcome remains success
=> acceptance reject
=> eligibility false
```

Do not turn evidence invalidity into semantic failure.

---

## 12. Telemetry/resource non-authority

Add focused proof that changes to observations or resource fields cannot change adjudication.

Do not add runtime accounting functionality. Preserve explicit zero/`Unknown` semantics.

---

## 13. Serialized contract preservation

Preserve terminal serialization layout and keep:

```text
schema_version = 1
```

unless an actual compatibility break is unavoidable.

Prefer no schema change, no field rename, no top-level additions.

---

## 14. Preserve both execution paths

Do not add a third path.

Mutation path must retain verified-success default semantics and one mutation primitive.

Read-only path must retain verified-success default semantics, `policy_decision=not_required`, zero mutation primitives, empty `changed_paths`, and identical before/after state hash.

All four frozen input artifacts must remain byte-identical.

---

## 15. Focused tests

At minimum cover:

1. semantic valid + sufficient evidence => verified success;
2. semantic valid + insufficient evidence => success/reject/not eligible/unverified success;
3. semantic valid + invalid binding => success/reject/not eligible/unverified success;
4. semantic failure + producer success claim => failure/reject/not eligible;
5. semantic failure cannot produce verified success;
6. inconsistent direct `actual_outcome` fails;
7. inconsistent acceptance fails;
8. inconsistent eligibility fails;
9. inconsistent joint interpretation fails;
10. terminal evidence status must match verifier evidence status;
11. telemetry changes do not alter adjudication;
12. resource changes do not alter adjudication;
13. producer claim changes do not alter adjudication;
14. mutation CLI semantics unchanged;
15. read-only CLI semantics unchanged;
16. terminal schema version remains 1 with existing keys.

Do not create an exhaustive combinatorial matrix.

---

## 16. Known regression debt

Preserve the single known historical Phase 4 frozen-artifact failure exactly.

Do not modify the retired plan, expected hash, assertion, skip state, or test classification.

Final condition:

```text
zero new failures
zero new errors
```

If the historical failure changes/disappears unexpectedly, investigate before closure.

---

## 17. Preservation

Preserve unchanged:

- `sources/`
- `references/papers/`
- `research/`
- all pre-existing `/runs/`
- all retired Phase 4 plans
- retired post-Phase-4 synthesis plan
- retired Phase 5 Batch 1 plan
- retired Phase 5 Batch 2 plan
- Phase 4 closure artifacts
- post-Phase-4 durable handoff
- Batch 1 durable handoff
- Batch 2 durable handoff

Preserve exact bytes of:

```text
experiments/substrates/minimal-reliable-execution-v0/inputs/task-contract.json
experiments/substrates/minimal-reliable-execution-v0/inputs/specialization-program.txt
experiments/substrates/core-execution-integration-v0/inputs/task-contract.json
experiments/substrates/core-execution-integration-v0/inputs/lookup-program.txt
```

No new run directory. No history rewrite. No force-push.

---

## 18. Expected implementation surface

Keep changes concentrated around:

```text
AGENTS.md
docs/plans/TEMP_PHASE_5_TERMINAL_SEMANTIC_INTEGRITY.md
docs/phase-5-terminal-semantic-integrity-handoff.md
irisx/core/records.py
irisx/core/execution.py
irisx/core/__init__.py
irisx/core/tests/...
experiments/substrates/minimal-reliable-execution-v0/tests/test_slice.py
experiments/substrates/core-execution-integration-v0/tests/test_integration.py
```

Touch fixture scripts only if required. Avoid unrelated refactoring or naming cleanup.

---

## 19. Milestone commits

### WP0 — Activate plan

`docs: activate Phase 5 terminal-integrity plan`

### WP1 — Align authority

`docs: align Phase 5 terminal-integrity authority`

### WP2 — Centralize adjudication

`core: centralize terminal adjudication`

### WP3 — Enforce invariants

`core: enforce terminal semantic consistency`

and/or:

`tests: validate terminal semantic integrity`

### WP4 — Durable handoff

Create `docs/phase-5-terminal-semantic-integrity-handoff.md`.

`docs: record Phase 5 terminal-integrity handoff`

### WP5 — Retire plan

Append retirement record only after all criteria pass.

`docs: retire Phase 5 terminal-integrity plan`

Then validate and push `main` normally.

---

## 20. Validation

Run at minimum:

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

Also run the established full experiment/substrate regression sweep and record exact counts.

---

## 21. Acceptance criteria

This batch is accepted only if:

1. one canonical adjudication operation exists;
2. normal `execute()` paths use it;
3. no duplicate terminal decision mapping remains;
4. producer claim cannot affect adjudication;
5. telemetry cannot affect adjudication;
6. resource ledger cannot affect adjudication;
7. insufficient evidence does not rewrite semantic success;
8. invalid evidence does not rewrite semantic success;
9. verifier failure cannot become success through producer claim;
10. inconsistent direct `TerminalRecord` construction fails closed;
11. joint interpretation is canonical;
12. eligibility is canonical;
13. terminal evidence status remains verifier-sourced;
14. mutation path unchanged;
15. read-only path unchanged;
16. serialized schema remains version 1;
17. frozen inputs unchanged;
18. no third path;
19. no excluded mechanism;
20. H-G1/H-W1/H-C1/H-R1 remain `Not evaluated`;
21. no new regression failure/error;
22. preservation passes;
23. durable handoff committed;
24. plan retired separately;
25. final tree clean;
26. normal push completed;
27. local/remote ahead-behind `0/0`.

---

## 22. Allowed conclusion

If all criteria pass, the strongest allowed conclusion is:

> **Phase 5 Batch 3 complete — terminal outcome, evidence, acceptance, verified-success eligibility, and joint interpretation are canonically derived and consistency-checked across the existing provisional deterministic execution paths.**

Do not claim general adjudication, universal verifier correctness, probabilistic reliability, production reliability, or final architecture correctness.

---

## 23. Durable handoff requirements

Create `docs/phase-5-terminal-semantic-integrity-handoff.md` and record:

### Repository
- required baseline;
- actual starting main;
- validated implementation head;
- handoff SHA;
- retirement SHA;
- final local/origin main;
- ahead/behind;
- clean/dirty state;
- commit sequence;
- push result.

### Architecture
- previous ambiguity;
- canonical adjudication API;
- authoritative inputs;
- explicitly non-authoritative fields;
- TerminalRecord consistency rules;
- unchanged schema;
- dependency direction.

### Behavioral proof
- verified success;
- insufficient evidence;
- invalid binding;
- producer false-success claim;
- semantic failure;
- inconsistent construction rejection;
- telemetry/resource invariance.

### Preservation/regression
- protected tree/input identities;
- focused counts;
- full sweep counts;
- exact known historical failure;
- zero new failures/errors.

### Research boundary

```text
H-G1: Not evaluated
H-W1: Not evaluated
H-C1: Not evaluated
H-R1: Not evaluated
```

Confirm no provider/model/network/API/retry/recovery/routing/cascade/escalation/persistence/workflow-search/optimizer work occurred.

---

## 24. Retirement

Only after implementation, validation, preservation proof, and durable handoff pass, append a retirement record to this plan with:

- retirement date;
- actual starting SHA;
- implementation SHAs;
- handoff SHA;
- test counts;
- regression result;
- preservation result;
- exact allowed conclusion;
- remaining uncertainty;
- statement that Phase 5 remains open;
- statement that this plan authorizes no Batch 4.

Commit retirement separately.

---

## 25. Stop conditions

STOP instead of broadening scope if:

- baseline materially conflicts;
- frozen inputs would need to change;
- integrity requires redesigning the entire outcome ontology;
- a rules engine becomes necessary;
- another execution path becomes necessary;
- provider/model/network functionality becomes necessary;
- persistence/retry/recovery/routing/cascade/workflow/optimizer machinery becomes necessary;
- evidence/outcome separation would be weakened;
- a new regression cannot be resolved within this scope;
- preservation fails;
- H-G1/H-W1/H-C1/H-R1 would be evaluated;
- broader owner authorization is needed.

Do not weaken criteria to get green.

---

## 26. Hard STOP

After canonical adjudication, TerminalRecord consistency enforcement, validation, durable handoff, plan retirement, normal push, clean tree, and local/remote synchronization:

**STOP.**

Do not start Phase 5 Batch 4 under this plan.

---

## 27. Retirement record

- **Retired on:** 2026-09-05 Asia/Taipei
- **Required and actual starting `main`:** `954b95d0126ac057789d1eee5584ec7bef391614`
- **Plan activation:** `45828999ff39e7617a21e308ef6c5f4cda40027f`
- **Authority alignment:** `0e7ec248480ac6598b56c53e161b4abe100d2361`
- **Canonical adjudication:** `587e3a12767caa31bcdfc5b6436687ba78fa7c47`
- **Terminal consistency enforcement and proof:** `fd3b179ec7515f435f941b18055077f1ad8a6c81`
- **Validated implementation head:** `fd3b179ec7515f435f941b18055077f1ad8a6c81`
- **Durable handoff:** `30c5e75fb83e0b0c4efd7b17ff63f7d27c6a312d`
- **Focused tests:** 50/50 passed (28 core, 13 mutation, 9 read-only)
- **Regression sweep:** 93 tests across 15 experiment/substrate directories; 92 passed, the one unchanged baseline-known failure remained, and zero errored
- **Repository validation:** passed with 13 registered sources and 7 paper artifacts
- **Compilation and CLIs:** required Python compilation and both deterministic CLIs passed; terminal schema remained version 1
- **Preservation:** protected source, paper, research, run, prior-plan, prior-handoff, and all four frozen-input identities remained unchanged; no run directory or third execution path was added
- **H-G1/H-W1/H-C1/H-R1:** `Not evaluated`
- **History:** no amend, rebase, squash, force-push, or other history rewrite
- **Push:** normal push follows this retirement commit; final local/remote identity and ahead/behind are reported in the owner-facing response

The exact allowed conclusion is:

> **Phase 5 Batch 3 complete — terminal outcome, evidence, acceptance, verified-success eligibility, and joint interpretation are canonically derived and consistency-checked across the existing provisional deterministic execution paths.**

Remaining uncertainty includes `partial` and `unresolved` semantics,
probabilistic confidence, human disagreement, multi-verifier consensus, general
verifier correctness, production reliability, and final architecture
correctness. These remain `Not established` or `Not evaluated`; the exact core
function and record shapes remain provisional.

No provider/model adapter, model call, network/API behavior, paid API, external
action, persistence, retry, recovery, routing, cascade, escalation, workflow
machinery/search, optimizer integration, fine-tuning, training, multi-agent
logic, architecture search, production infrastructure, telemetry system,
ontology redesign, additional execution path, or new run was implemented,
evaluated, or run.

This retirement completes Phase 5 Batch 3 only. Phase 5 remains open, and this
plan authorizes no Phase 5 Batch 4.

**STOP.**
