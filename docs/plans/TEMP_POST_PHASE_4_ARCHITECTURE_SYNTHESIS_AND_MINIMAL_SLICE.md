# Temporary Post Phase 4 Architecture Synthesis and Minimal Slice Plan

Status: **Retired — execution complete; see Section 12**

Date: **2026-09-04 Asia/Taipei**

Scope: **post-Phase-4 architecture synthesis and exactly one local deterministic executable vertical slice**

Architecture authority: **Provisional candidate only**

Actual starting `main`: `7ae6c6dfd643e79165d26b32cb5b9f82e897806d`

Known Phase 4 baseline: `7ae6c6dfd643e79165d26b32cb5b9f82e897806d`

Hard terminal boundary: **retire this plan and STOP after synthesis, one slice, validation, and durable handoff**

The committed bytes of this plan control this bounded batch together with all applicable `AGENTS.md` files. Repository artifacts remain the source of truth. Phase 4 is closed and will not be reopened by this plan.

## 1. Starting state and authority reconciliation

- The working tree was clean on `main` before this plan was created.
- `git merge-base --is-ancestor 7ae6c6dfd643e79165d26b32cb5b9f82e897806d HEAD` returned success.
- Starting `main` equals the known completed Phase 4 baseline; there are no later owner commits to reconcile.
- `python tools\repository_check.py` passed with 13 sources and 7 paper artifacts before substantive work.
- Root `AGENTS.md` still states `Research preparation / corpus organization`. This is stale after the durable Phase 4 closure. The smallest authority repair is to describe the active stage as post-Phase-4 architecture synthesis and minimal architecture development while retaining provisional, non-production, architecture-neutral, and preservation boundaries.
- No scoped authority requires Phase 4 to reopen or authorizes a broad Phase 5 implementation.

## 2. Scope

Authorized work is limited to:

1. minimally reconciling stale repository phase/status wording;
2. creating one durable evidence-to-constraint-to-interface synthesis in an existing IRIS-X-authored research zone;
3. deriving the smallest provisional candidate architecture needed by the supported constraints;
4. implementing exactly one thin, local, deterministic vertical slice with a replaceable executor boundary;
5. adding deterministic tests for identity, specialization hashing, pre-execution policy timing, evidence binding, independent verification, separated adjudication fields, and structured observations;
6. validating repository, tests, compilation, diffs, preservation, and absence of unauthorized behavior;
7. creating a durable handoff and retiring this plan.

## 3. Non-goals

This plan does not authorize:

- reopening Phase 4 or strengthening its task-local claims into universal invariants;
- H-G1, H-W1, H-C1, or H-R1;
- prompt or workflow search, routing, cascades, escalation, fine-tuning, training, RL, architecture search, or additional model experiments;
- a production runtime, broad framework, final ontology, final architecture, final product boundary, provider integration, persistence layer, tracing transport, or deployment system;
- network, model, API-key, paid-provider, authentication, or billing behavior;
- implicit retry, routing, escalation, recovery, or fallback;
- modification of `sources/`, `references/papers/`, or any pre-existing experiment run directory.

H-G1, H-W1, H-C1, and H-R1 remain `Not evaluated`. They become new experiments only if a later architecture decision has a decision-critical dependency that cannot remain an extension point and the owner separately authorizes that experiment.

## 4. Preservation baseline

Before substantive work, the following Git identities were recorded at starting `main`:

| Preserved material | Starting identity |
| --- | --- |
| `sources/` tree | `10e28d83184c789fc468ca1edc3bebf42ba40b46` |
| `references/papers/` tree | `ed29ebcde3f01b00a0e49eb33eef1688566dcad3` |
| Sorted `git ls-tree -r` manifest for every path containing `/runs/` | Git blob SHA-1 `bb18819d893450e18ea5608e691c02ad6f1f96e0` |
| Pre-existing run directories | 16 |
| Pre-existing tracked run files | 823 |

The final preservation check must compare these identities and also require an empty diff from the starting commit for `sources/`, `references/papers/`, and every pre-existing `/runs/` path. New tests must use temporary directories. The executable slice must not create a committed run or mutate a historical one.

## 5. Evidence and decision discipline

- Direct observations, source-stated material, inference, and unknowns remain distinct.
- Phase 4 support remains task-local and horizon-limited.
- Parent H-M1, H-V1, H-I1, H-O1, H-RCV1, and H-P1 remain `Not established`.
- Candidate constraints are adopted only when the Phase 4 records support their need; otherwise they remain optional, substrate-only, provisional, or unresolved.
- Commodity provider adapters, generic dispatch, persistence, and tracing transport stay outside the IRIS-X research contribution and outside this slice.
- Actual outcome, producer claim, evidence status, acceptance decision, verified-success eligibility, policy decision/timing, side effects, recovery identity, and telemetry are not collapsed into one status field.
- Material ambiguity is resolved through the repository first. Any remaining interpretation must be the narrowest reversible one and recorded in the synthesis or handoff.

## 6. Milestones and commit gates

1. **Plan activation** — commit this plan before architecture or code changes.
2. **Authority reconciliation** — minimally update root phase/status wording; do not declare a final architecture.
3. **Durable synthesis** — create the evidence-to-constraint matrix, smallest candidate architecture, interface semantics, trust boundaries, failure semantics, removal tests, falsifiers, and unresolved experiment triggers.
4. **Minimal slice** — add only the contracts and deterministic end-to-end path needed to exercise the synthesized boundaries.
5. **Boundary tests** — prove valid verified success, identity mismatch rejection, producer/verifier disagreement, evidence-hash mismatch, pre-mutation policy denial with unchanged state, telemetry invariance, and specialization mutation detection. Recovery remains an explicit unimplemented extension unless the synthesis shows it is indispensable to this one slice.
6. **Validation and handoff** — run every planned check, record exact results and preservation proof in a durable handoff.
7. **Retirement** — update this plan with a retirement record only after every exit criterion passes, commit retirement, and STOP.

Use small, meaningful commits. Do not amend, rebase, squash, rewrite history, or push.

## 7. Planned validation

Run from repository root and report only commands actually executed:

```powershell
python tools\repository_check.py
python -m unittest discover -s experiments\substrates\minimal-reliable-execution-v0\tests -v
python -m py_compile experiments\substrates\minimal-reliable-execution-v0\scripts\run_slice.py
python experiments\substrates\minimal-reliable-execution-v0\scripts\run_slice.py
git diff --check
git diff --cached --check
```

Also verify:

- the starting and final `sources/` and `references/papers/` tree identities match;
- the sorted historical `/runs/` manifest remains 823 files with SHA-1 `bb18819d893450e18ea5608e691c02ad6f1f96e0`;
- `git diff 7ae6c6dfd643e79165d26b32cb5b9f82e897806d -- sources references/papers` is empty;
- no pre-existing `/runs/` path changed;
- the slice imports only the Python standard library and performs zero model, network, API, retry, routing, escalation, or recovery actions;
- every synthesis claim is linked to repository evidence or explicitly labeled inference/unknown.

If the selected slice path differs after synthesis, update the validation commands before implementation and explain the smaller evidence-backed location.

## 8. Blockers and stop conditions

Stop before substantive work or before broadening scope if:

- the completed baseline is not an ancestor or repository history materially conflicts with this scope;
- a supported constraint cannot be represented without modifying preserved source or historical evidence;
- a core decision depends critically on H-G1/H-W1/H-C1/H-R1 or another `Not evaluated` claim and cannot remain an extension point;
- the slice requires unauthorized model, network, API, provider, authentication, billing, retry, routing, escalation, or recovery behavior;
- validation or preservation fails and cannot be repaired without weakening evidence discipline;
- the work is becoming a framework or production system.

For a decision-critical unknown blocker, produce only a narrowly scoped follow-on experiment proposal stating its hypothesis, treatment/control, evaluator, held-out strategy, resource ceiling, and the exact decision it would unlock.

## 9. Exit criteria

This plan may retire only when:

- root authority accurately reflects the post-Phase-4 provisional stage;
- the durable synthesis includes explicit evidence-to-constraint traceability and uncertainty boundaries;
- the smallest candidate architecture and interfaces are documented with responsibility, trust boundary, failure semantics, side effects, and justification;
- exactly one executable local/deterministic slice passes its boundary tests;
- no broad implementation, productionization, or additional experiment has begun;
- H-G1/H-W1/H-C1/H-R1 remain `Not evaluated`;
- all validation, compilation, whitespace, and preservation checks pass;
- a durable handoff records implemented versus synthesized material, remaining unknowns, and ranked future decision triggers.

## 10. Required durable handoff

The handoff must report exact paths and full commit SHAs for:

- actual starting `main`, final local `main`, commit sequence, changed files, and push status;
- authority/status changes and their necessity;
- the architecture synthesis and evidence-to-constraint matrix;
- candidate components/interfaces, including evidence-backed versus provisional status;
- vertical-slice location, execution path, and tests;
- validation commands and results;
- preservation proof for sources, papers, and historical runs;
- H-G1/H-W1/H-C1/H-R1 status;
- every remaining `Unknown`, `Unclear`, `Not established`, and `Not evaluated` item;
- future decision-critical experiment triggers ranked by the decision they would unlock.

## 11. Hard stop

After the architecture synthesis, exactly one minimal executable slice, validation, durable handoff, and retirement of this plan:

**STOP.**

Do not continue into broad Phase 5 implementation, productionization, workflow search, routing, cascade, fine-tuning, architecture search, or additional model experiments without a new owner-authorized scope.

## 12. Retirement record

- **Retired on:** 2026-09-04 Asia/Taipei
- **Actual starting main:** `7ae6c6dfd643e79165d26b32cb5b9f82e897806d`
- **Plan activation:** `98fba46a22e92515eda945f132d8fd042055df48`
- **Authority reconciliation:** `4c982773d0a1a88f3979718366369716d29a1ce6`
- **Durable synthesis:** `e6c22dd5e2b40dee511894a6f38761d248bcaced`
- **Frozen slice contract:** `27fea795337a3bf85c8d99cafdf1f73baeaea703`
- **Executable slice implementation:** `2061caf794fbe07c4fd185232af7191d27007f07`
- **Durable handoff:** `263f33cb5bae90b222fabd4c496a5fe6db26c8ab`
- **Architecture status:** provisional candidate; not production-stable or final
- **Slice result:** local deterministic verified success
- **New boundary tests:** 9/9 passed
- **Repository validation:** passed with 13 sources and 7 paper artifacts
- **Preservation:** `sources/`, `references/papers/`, and all 16 pre-existing run directories remained unchanged; the 823-file run manifest retained SHA-1 `bb18819d893450e18ea5608e691c02ad6f1f96e0`
- **H-G1/H-W1/H-C1/H-R1:** `Not evaluated`
- **Push:** not authorized and not performed

All exit criteria were satisfied before retirement. The additional all-suite regression sweep found the same Phase 4 frozen-plan hash mismatch already present at the starting baseline; it is documented in the durable handoff and was not repaired because the retired Phase 4 plan and historical evidence are preserved.

This retirement ends the authority of this temporary plan. It does not authorize another slice, broad Phase 5 implementation, productionization, routing, cascade, workflow search, fine-tuning, architecture search, recovery implementation, or another model experiment.

**STOP.**
