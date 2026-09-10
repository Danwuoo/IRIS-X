# Phase 6 Post-Batch-3 Predicate/Provenance Authority Repair Handoff

- **Status:** Complete — **Result A — Authority repaired and re-derived**
- **Date:** 2026-09-10 Asia/Taipei
- **Scope:** owner-authorized zero-model-call repair over preserved Batch 3
  evidence; not Phase 6 Batch 4
- **Repository:** Danwuoo/IRIS-X
- **Required and actual starting SHA:**
  `fc42646466b697e5723d6ae2db58fafcb8e13448`
- **Controlling-plan activation:**
  `e58c8225645b3b2f7d23bfea00f374aa5f64d3b6`
- **Definition/test freeze:**
  `6beafccc2595808bcfac3ba8796a581156d76592`
- **Deterministic derived evidence:**
  `4f6b426c8721569cf264187a2709a47e14e01e91`
- **Research result:**
  `c27cb195e16de6c4b969121182238130b7e28671`
- **Model/provider calls:** `0 / 0`
- **Phase 6 Batch 4:** `NOT started / NOT authorized`

The handoff and later plan-retirement commit identities are recorded in the
controlling-plan retirement record after those commits exist.

## 1. Outcome

**Result A — Authority repaired and re-derived.**

A separately identified post-Batch-3 authority now deterministically derives
the intended direct predicates from preserved Batch 3 evidence. Six terminal
records are bound by exact path, SHA-256, JSON pointer, and observed value. The
mixed task-pressure vector is evaluated by the existing proven `any_equals`
semantics, not by a manual Boolean.

The repaired result is:

```text
cheaper_admitted_configuration_misses_requirement = true
```

H-C1 still requires all three predeclared predicates. Its stronger-candidate
and trade-off predicates are `unknown`, so H-C1 is
`insufficient_or_ambiguous`, not `triggered_by_direct_evidence`.

No capability gate triggered. No capability mechanism was implemented.

Historical Phase 6 Batch 3 remains **Result D — Provenance or authority
conflict**. This handoff records a new repair result and does not rewrite Batch
3 as Result B.

## 2. Exact authority defects repaired

### Wrong source namespace

The historical Batch 3 rule named six task terminal sources under
`runs/batch-2/`. The new authority binds:

```text
runs/batch-3/p1-selection/terminal-record.json
runs/batch-3/p2-aggregation/terminal-record.json
runs/batch-3/p3-ranking/terminal-record.json
runs/batch-3/p4-dependency/terminal-record.json
runs/batch-3/p5-reconciliation/terminal-record.json
runs/batch-3/p6-rule-precedence/terminal-record.json
```

All use `/attribution/task_level_pressure_observed`. Missing
stronger-candidate, trade-off, and retry-comparison observations are sought in
the Batch 3 namespace and remain missing/`unknown`; Batch 2 absence is not used
as Batch 3 authority.

### Incorrect aggregation operator

The historical any-miss rule used `equals`, which treats mixed observations as
conflicting. The repaired rule
`rule-hc1-any-semantic-miss-batch3-v1` uses the evaluator's existing
`any_equals` operator with expected `true`.

Code inspection and focused tests verify that `any_equals` returns true if any
observation equals the expected value. No operator implementation changed and
no new rules engine was introduced.

## 3. Repaired authority identity

| Item | Identity |
| --- | --- |
| Authority ID | `phase-6-post-batch-3-predicate-provenance-authority-v1` |
| Definition/test freeze | `6beafccc2595808bcfac3ba8796a581156d76592` |
| Authority definition SHA-256 | `65fd34bb8c25c3de62a8a3e559c2cf86c2fea98ee7459a7e07079819965f13a1` |
| Reused evaluator SHA-256 | `7978320f97144d774b2e0f7a9a4e4e2c9e3e4d19ff4d6e6700f3184429a9c74a` |
| Direct predicates SHA-256 | `b9c83b45129c4bc689f688606d689a28577b094c8a90d7dadff134fd61ffc5b1` |
| Gate adjudication SHA-256 | `185b6867ad1d51ef26b1d0e661ff7f4dac9d03ed6b2af9775b4319c1c6174c5e` |
| Manifest SHA-256 | `5ae0df5993d9c97c2b0fd18d6989c6510cf1414d955019b902e7e086a51448b1` |

The derived artifacts are under
`experiments/phase-6-predicate-authority-repair-v0/runs/authority-repair-20260910/`.

## 4. Preserved direct evidence

| Task | Terminal result | Pressure observation | Terminal SHA-256 |
| --- | --- | --- | --- |
| P1 | `verified_success` | `false` | `0b7f527167a010388747ea910c59818fcdfacae35ebf15b161bcbca52e1dc4ca` |
| P2 | `verified_success` | `false` | `920be7ad5888e1bf61f906a20fa7efc3c7989b92f14016b9abea602f4a63569c` |
| P3 | `verified_success` | `false` | `adca3dab6d07464943c99cd0281da0b8089ac0190502d9ece212890b66e4ee66` |
| P4 | `semantic_miss` | `true` | `a0ca487abef319e6be0157582c2ada82a37d7d4846deaf5bc455342651789edb` |
| P5 | `verified_success` | `false` | `7382d4dd63f07e9c9f125236b6d08111d52111ec64c1c4e68a1a34afddbb1577` |
| P6 | `verified_success` | `false` | `e5e32bfe87bb57ce228de3b144329f2c5bffaa42aecdc8b7f2fc8cba7ffb4cc2` |

P4 remains a task-success shortfall attributed directly to the
execution-producer stage under the frozen configuration. Intrinsic model
incapability and every intervention benefit remain `Not established`.

## 5. H-C1 required predicates

| Required predicate | Value | Status |
| --- | --- | --- |
| `cheaper_admitted_configuration_misses_requirement` | `true` | Derived from six preserved terminal observations with `any_equals`. |
| `stronger_candidate_resolves_miss` | `unknown` | No stronger-candidate experiment or Batch 3 comparison observation exists. |
| `decision_relevant_tradeoff_established` | `unknown` | No comparison establishes a decision-relevant success/reliability/cost trade-off. |

First prerequisite satisfied: **yes**.  
H-C1 triggered: **no**.  
H-C1 status: **`insufficient_or_ambiguous`**.

The Phase 5 canonical H-C1 wording additionally requires that a specifically
declared stronger candidate plausibly resolve the miss and create a
decision-relevant trade-off. Those conditions are not established.

## 6. All eight capability gates

| Gate | Required operational predicate values | Missing evidence | Gate status | Experiment triggered |
| --- | --- | --- | --- | --- |
| H-G1 automated specialization | `false` | Direct automation need and failed manual/frozen construction absent | `not_triggered` | No |
| H-W1 workflow machinery/search | `false` | Simple-flow insufficiency and evaluated workflow alternative absent | `not_triggered` | No |
| H-C1 cascade/escalation | `true`, `unknown`, `unknown` | Stronger resolution and trade-off comparison | `insufficient_or_ambiguous` | No |
| H-R1 routing/allocation | `true`, `false`, `false` | Multiple allocations, material differential, frontier change | `not_triggered` | No |
| Runtime persistence | `false` | Continuity requirement and restoration oracle | `not_triggered` | No |
| Nondeterministic verifier/model judge | `false` | Deterministic-oracle insufficiency and independent semantic reference | `not_triggered` | No |
| External-action/interception expansion | `false` | External/irreversible requirement, authorization, authenticated post-state | `not_triggered` | No |
| General retry/recovery | `unknown` | Specified safe treatment and independently compared benefit | `insufficient_or_ambiguous` | No |

Direct-evidence triggered gates: **0 / 8**.

## 7. Newly supported and still unsupported

Newly supported beyond Batch 3 Result D:

> Preserved Batch 3 direct evidence authoritatively establishes that the
> frozen admitted cheaper configuration missed at least one sampled task
> requirement.

This is bounded task/configuration-level capability pressure. It is an
authority-layer advance, not new task evidence.

Still `Not established`:

- intrinsic model incapability;
- retry or recovery benefit;
- stronger-allocation resolution or benefit;
- escalation/cascade benefit;
- routing/allocation benefit;
- workflow benefit;
- persistence, judge, automated-specialization, or external-action benefit;
- generalization beyond the six sampled tasks;
- long-term reliability, lifecycle-cost superiority, provider portability,
  production readiness, final failure ontology, or final architecture.

## 8. Validation

| Validation | Result |
| --- | --- |
| New authority-repair focused tests | PASS — 10/10 |
| New repaired-authority validator | PASS |
| Existing Phase 6 definition/provider-schema validator | PASS |
| Existing Phase 6 sampling tests | PASS — 41/41 |
| Phase 6 Batch 1 attribution tests | PASS — 35/35 |
| Phase 5 qualification/task-family tests | PASS — 75/75 |
| Deterministic direct predicate regeneration | PASS — byte-identical |
| Deterministic gate adjudication regeneration | PASS — byte-identical |
| Deterministic manifest regeneration | PASS — byte-identical |
| Two independent complete regenerations | PASS — byte-identical |
| Repository check | PASS — 13 sources, 7 artifacts, hashes checked |
| Full discovered inventory | 282 tests; 281 passed; 1 known historical failure; 0 errors |
| New failures / errors | `0 / 0` |

The sole failure is the unchanged Phase 4
`HPIaContractTests.test_frozen_artifact_hashes_match_exact_bytes` mismatch for
`docs/plans/TEMP_PHASE_4_FINAL_MODEL_SPECIALIZATION_AND_CLOSURE.md`: observed
`4f3e47a6fa8af63dee6d4397d995a917a216ce70791416909e76a5448697246b`,
recorded
`9e2ac0aabcae9a89ed92d9145ec787f4d6ee1920b5344be703498c6435aaf76c`.
It was not repaired, rebaselined, skipped, or suppressed.

## 9. Preservation status

The following match the starting baseline exactly:

- Batch 2 run tree;
- Batch 3 run tree, including raw outputs, P1–P6 terminal records, collection
  evidence, original direct predicates, and frozen evaluation;
- original Batch 3 predicate definition;
- Batch 3 Result D research note, durable handoff, and retired plan;
- Phase 6 Batch 1 evidence;
- historical Phase 4/5 run evidence;
- `irisx/core/`, `sources/`, and `references/papers/`.

No historical commit was amended, rebased, squashed, reset, or overwritten.

## 10. Files added

Added during this scope:

- `docs/plans/TEMP_PHASE_6_BATCH_3_PREDICATE_PROVENANCE_AUTHORITY_REPAIR.md`;
- `experiments/phase-6-predicate-authority-repair-v0/README.md`;
- `experiments/phase-6-predicate-authority-repair-v0/definition/predicate-derivation-rules.json`;
- `experiments/phase-6-predicate-authority-repair-v0/scripts/derive_repair.py`;
- `experiments/phase-6-predicate-authority-repair-v0/scripts/validate_repair.py`;
- `experiments/phase-6-predicate-authority-repair-v0/tests/test_authority_repair.py`;
- four JSON artifacts under
  `experiments/phase-6-predicate-authority-repair-v0/runs/authority-repair-20260910/`;
- `research/phase-6-predicate-provenance-authority-repair.md`;
- this durable handoff.

No pre-existing file was modified except the new controlling plan's later
in-place retirement record.

## 11. Commit lineage before handoff

| Purpose | Commit |
| --- | --- |
| Required baseline | `fc42646466b697e5723d6ae2db58fafcb8e13448` |
| Activate controlling plan | `e58c8225645b3b2f7d23bfea00f374aa5f64d3b6` |
| Freeze definition and tests | `6beafccc2595808bcfac3ba8796a581156d76592` |
| Preserve derived evidence and validation | `4f6b426c8721569cf264187a2709a47e14e01e91` |
| Record research result | `c27cb195e16de6c4b969121182238130b7e28671` |

## 12. Closure and next-step boundary

The bounded repair scope satisfies its stop conditions and may be retired as
Result A. The current Phase 6 evidence chain is coherent enough for the owner
to close the presently authorized Phase 6 work: Batch 1 established the
instrument, Batch 2 preserved an uninterpretable sample, Batch 3 produced
interpretable direct observations but historical Result D authority conflict,
and this scope repaired that derivation authority without new calls.

That is a closure condition, not authorization for intervention research. Any
P4 repetition, stronger-model comparison, retry/recovery treatment, cascade,
router, workflow, persistence, model judge, automated specialization,
external-action work, or additional sampling requires separate owner
authorization.

**Phase 6 Batch 4: NOT started / NOT authorized.**
