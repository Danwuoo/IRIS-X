# Phase 6 Capability Pressure and Failure Attribution Handoff

- **Status:** durable Phase 6 Batch 1 handoff — Result A
- **Date:** 2026-09-08 Asia/Taipei
- **Batch:** Phase 6 Batch 1 — Capability Pressure and Failure Attribution Foundation
- **Owner-authorized scope:** deterministic offline research instrument only;
  no deferred capability implementation
- **Required and actual starting baseline:**
  `4aa7256e2237e997425e8712638334088056037d`
- **Definition/code freeze and execution SHA:**
  `9b46fb55bbbe400823efcd08b3b09d74196e869b`
- **Authoritative offline-run evidence commit:**
  `89dc196357c991ece19f10ab6fbfbb5c8d83cb34`
- **Research/result commit:**
  `904053c271cf6091786213dbea2d6b7cc0d9e0f4`
- **Live model/provider calls authorized and performed:** `0 / 0`
- **Paid API calls / model subprocesses:** `0 / 0`

The handoff commit and later controlling-plan retirement commit necessarily do
not exist while this document is authored. Their full SHAs and final
local/remote synchronization state are recorded in the plan retirement record
and owner-facing final report.

## 1. Outcome

**Result A — Foundation established.**

> A bounded deterministic capability-pressure and failure-attribution research
> instrument was established. It can distinguish negative, boundary, and
> synthetic trigger-positive cases and reproduce selected Phase 5 decisions
> without changing historical authority. This does not establish a final
> failure ontology or trigger any deferred capability by itself.

The authoritative offline run contains 34 valid assessments. All 34 match their
frozen expected results; invalid assessments, historical replay conflicts, and
other conflicts are zero. Two intentionally ambiguous attribution collisions
remain ambiguous.

No direct repository evidence changed any Phase 5 capability trigger. Every
direct-evidence trigger remains `Not triggered`.

## 2. Scope and architecture boundary

Batch 1 implemented only research-local definitions, fixtures, validators,
assessment functions, a derived summary, and tests. It did not modify
`irisx/core`, implement a provider or model path, or add an external framework
dependency.

No routing/allocation runtime, retry/recovery runtime, persistence runtime,
workflow engine/search, cascade/escalation, model judge, nondeterministic
verifier, automated specialization, external action, or irreversible action
was implemented or invoked.

The shortfall axes, failure-stage labels, and attribution statuses remain
**research-local, provisional, and non-normative**. They are not a final IRIS-X
ontology and do not have architecture authority.

## 3. Files and directories added or modified

Added:

- `docs/plans/TEMP_PHASE_6_CAPABILITY_PRESSURE_AND_FAILURE_ATTRIBUTION.md` —
  owner-provided controlling plan, activated byte-for-byte and retired only
  after this handoff;
- `experiments/capability-pressure-attribution-v0/README.md`;
- `experiments/capability-pressure-attribution-v0/definition/` — eight gate
  definitions, the candidate vocabulary, and the assessment schema;
- `experiments/capability-pressure-attribution-v0/fixtures/` — 24 pressure
  cases, eight attribution-boundary cases, and two historical replay cases;
- `experiments/capability-pressure-attribution-v0/scripts/` — explicit offline
  definition validator, assessment evaluator, and summary generator;
- `experiments/capability-pressure-attribution-v0/tests/` — definition, gate,
  attribution, replay, and determinism tests;
- `experiments/capability-pressure-attribution-v0/runs/batch-1-offline/` — one
  immutable manifest, assessment payload, and derived summary;
- `research/phase-6-capability-pressure-and-failure-attribution.md`;
- this durable handoff.

No existing Phase 4/5 evidence, plan, handoff, run artifact, imported source,
paper, or `irisx/core` file was modified.

## 4. Case inventory

| Suite | Cases | Frozen expectation/result |
| --- | ---: | --- |
| Primary synthetic pressure | 24 | 24/24 matched |
| Surface-only negative controls | 8 | 8/8 `not_triggered` |
| Near-trigger boundaries | 8 | 8/8 `insufficient_or_ambiguous` |
| Primary synthetic positives | 8 | 8/8 `triggered_by_fixture` only |
| Attribution collision/boundary | 8 | 8/8 matched |
| Intentionally ambiguous attribution | 2 | 2/2 preserved as `ambiguous` / `unknown` stage |
| Historical replay | 2 | 2/2 matched; 0 conflicts |
| **Total assessments** | **34** | **34 valid; 0 invalid; 34 expectations matched** |

The candidate shortfall axes are `task_success`, `evidence`, `reliability`, and
`lifecycle_cost`. The candidate failure stages are
`admission_configuration`, `identity_authority`, `execution_producer`,
`verification`, `state_continuity`, `control_flow`,
`allocation_capability`, `external_effect`, `resource_cost`, and `unknown`.
Attribution status is one of `directly_supported`, `inferred`, `ambiguous`, or
`not_attributable`.

## 5. Historical replay sources and result

### Batch 4 configuration-failure lineage

The replay reads the immutable `terminal-record.json`, `interpretation.json`,
and `provider-stderr.txt` files for:

- `experiments/substrates/model-execution-qualification-v0/runs/qualification-20260905-01/`;
- `experiments/substrates/model-execution-qualification-v0/runs/qualification-20260905-02/`.

The frozen replay specification records each exact SHA-256. The assessment
reproduces:

```text
failure_stage: admission_configuration
attribution_status: directly_supported
model capability failure: Not established
retry requirement: Not established
escalation requirement: Not established
logical attempts: 2
retries/routes/escalations/recovery actions: 0/0/0/0
```

Neither failure was relabeled as a model capability miss or retry/escalation
evidence.

### Batch 6 shared-allocation task family

The replay reads the immutable admission snapshot, derived summary, and source
terminal records at:

- `experiments/substrates/model-execution-qualification-v0/task-family/admission/current-environment-20260906.json`;
- `experiments/substrates/model-execution-qualification-v0/task-family/summaries/batch-6-summary.json`;
- the A-filter, B-aggregation, and C-ranking `terminal-record.json` files under
  `experiments/substrates/model-execution-qualification-v0/task-family/runs/`.

The assessment reproduces three semantically distinct task identities, one
shared admitted configuration, 3/3 read-only verified successes, and zero
retry, route, escalation, and recovery actions. Routing/allocation,
cascade/escalation, recovery/retry, and runtime persistence remain
`not_triggered` by this evidence.

Historical repository artifacts remain the source of truth. The replay
representation is a hash-bound compatibility check and does not replace them.

## 6. Direct-evidence and synthetic trigger status

| Gate | Direct repository evidence after Batch 1 | Synthetic recognition |
| --- | --- | --- |
| H-G1 automated specialization | `Not triggered` — unchanged | positive predicate recognized |
| H-W1 workflow machinery/search | `Not triggered` — unchanged | positive predicate recognized |
| H-C1 cascade/escalation | `Not triggered` — unchanged | positive predicate recognized |
| H-R1 feature-based routing/allocation | `Not triggered` — unchanged | positive predicate recognized |
| Runtime persistence | `Not triggered` — unchanged | positive predicate recognized |
| Nondeterministic verifier/model judge | `Not triggered` — unchanged | positive predicate recognized |
| External-action/interception expansion | `Not triggered` — unchanged | positive predicate recognized |
| General recovery/retry | `Not triggered` — unchanged | positive predicate recognized |

`triggered_by_fixture` proves only evaluator recognition of deliberately
satisfied predicates. It never writes to or implies the direct-evidence
trigger ledger.

## 7. Definition and run identity

The definition/code freeze contains the gate definitions, candidate
vocabulary, assessment schema, all 32 synthetic/boundary fixtures, both
historical replay definitions, validators, evaluator, summary generator, and
35 focused tests.

The authoritative run manifest records:

| Identity | SHA-256 / Git SHA |
| --- | --- |
| Definition/code freeze and execution | `9b46fb55bbbe400823efcd08b3b09d74196e869b` |
| Gate definitions | `c7d03c6c8c3f9fe2fb56b07264fe21e6a9c6db0212b762b0f6bbb9be951055d6` |
| Attribution vocabulary | `2eb075863b2e400cd5e71d1436691b974405c80cabc15dfe2f88358d03f31346` |
| Assessment schema | `270e1d600e375db66151836993194458765ce6cbeae241168257135e4937bc7a` |
| Fixture inventory | `7d42679ea62413ce60e7ccd23d262d23d37c9b1fe6834ff60cc9bec6538aba23` |
| Definition/code inventory | `10a571293e786117a665fdbdb45e3b8fdd1172cdc03d6c037ce75b8b96af7dcc` |
| Historical replay sources | `8dfb272ecd0994e11c23f10c107bfd5f9abe880c39dd12a331dea1321c261cdf` |
| Assessments | `e06f7055e5413166a903688f2d28a9074b987a2da664f955f203f2adf21ace1f` |
| Derived summary | `63fa11dffc678df704320d15f4cf49679b3dddc4842cc288703932ca6dc64266` |

The validator rehashes these inputs, confirms the freeze commit contains the
recorded bytes, reads the historical sources directly, and regenerates the
assessment and summary payloads byte-identically.

## 8. Validation commands and results

### Pre-authoritative-run frozen validation

| Command/check | Result |
| --- | --- |
| `python ...\scripts\validate_definitions.py` | PASS — 8 gates, 24 pressure, 8 attribution, 2 replay cases |
| Definition/schema suite | 9/9 PASS |
| Trigger-gate suite | 8/8 PASS |
| Attribution suite | 8/8 PASS |
| Historical replay suite | 5/5 PASS |
| Determinism suite | 5/5 PASS |
| Focused Batch 1 total | 35/35 PASS |
| Existing model-qualification suite | 75/75 PASS |
| `python tools\repository_check.py` | PASS — 13 sources, 7 artifacts, hashes checked |
| Freeze-tree state | clean at `9b46fb55bbbe400823efcd08b3b09d74196e869b` |

### Authoritative offline run

```powershell
python experiments\capability-pressure-attribution-v0\scripts\assess_pressure.py --output-dir experiments\capability-pressure-attribution-v0\runs\batch-1-offline --starting-sha 4aa7256e2237e997425e8712638334088056037d --freeze-sha 9b46fb55bbbe400823efcd08b3b09d74196e869b
```

Result: PASS — `Result A — Foundation established`; model/provider calls
`0 / 0`.

### Post-run focused validation

- authoritative inventory, file hashes, frozen-byte checks, source references,
  regenerated assessments, and regenerated summary: PASS;
- focused Batch 1 tests: 35/35 PASS;
- repository check: PASS.

### Full discovered repository inventory

The established per-directory `unittest discover` inventory covered
`irisx/core/tests` and all 17 discovered `experiments/**/tests` directories:

- 231 tests run;
- 230 passed;
- 1 failed;
- 0 errors;
- 0 skipped;
- new failures/errors: 0.

The sole failure is the unchanged historical Phase 4 contract:

- test:
  `HPIaContractTests.test_frozen_artifact_hashes_match_exact_bytes`;
- file:
  `docs/plans/TEMP_PHASE_4_FINAL_MODEL_SPECIALIZATION_AND_CLOSURE.md`;
- expected SHA-256:
  `9e2ac0aabcae9a89ed92d9145ec787f4d6ee1920b5344be703498c6435aaf76c`;
- observed SHA-256:
  `4f3e47a6fa8af63dee6d4397d995a917a216ce70791416909e76a5448697246b`.

It was not edited, rebaselined, skipped, or suppressed. Its status is unchanged
from Phase 5 retirement.

## 9. Supported conclusions

Within the exact frozen fixture and replay scope, the instrument can:

- represent observation, shortfall classification, attribution, intervention
  hypothesis, trigger evaluation, and research decision as separate fields;
- preserve ambiguous attribution instead of forcing one stage;
- fail closed on malformed gate IDs, predicate inventories, evidence classes,
  attribution vocabulary, source references, and contradictory expectations;
- distinguish `triggered_by_fixture` from
  `triggered_by_direct_evidence`;
- deterministically recognize all eight predeclared synthetic positive gates;
- reproduce the selected Batch 4 and Batch 6 accepted distinctions; and
- produce byte-stable assessments and derived summaries from frozen inputs.

## 10. Unsupported conclusions

Batch 1 does not establish:

- a final failure ontology or general causal diagnosis;
- that any deferred capability is needed, safe, correct, or cost-effective;
- routing, allocation, escalation, retry, recovery, persistence, workflow,
  judging, specialization, or external-action behavior;
- provider portability, model capability, production readiness, general
  reliability, or lifecycle-cost advantage;
- authority for Phase 6 Batch 2 or a model/provider execution.

## 11. Ambiguities and conflicts

Two synthetic collisions intentionally remain ambiguous:

1. repeated no-result behavior under an admitted immutable profile cannot be
   uniquely assigned to producer execution versus resource conditions without
   additional stage-specific evidence; retry benefit and safety remain
   unknown;
2. a cheaper miss and stronger success supports a candidate escalation
   comparison but does not uniquely isolate producer behavior from
   allocation-capability cause.

Historical replay conflicts: **0**. Other Batch 1 conflicts: **0**.
Transfer of the candidate vocabulary beyond the bounded suite remains
`Unknown`.

## 12. Next research recommendation

If the owner authorizes further work, the exact next recommendation is a
mechanism-free pressure-sampling definition batch: freeze a bounded set of
deterministically verifiable tasks under one unchanged admitted allocation and
predeclare how a real task-level miss will be distinguished from admission,
identity, and verifier failures. Collect direct failure-pressure evidence
before comparing a stronger allocation or testing retry.

This recommendation seeks the missing decision evidence without assuming
routing, cascade, or recovery. It is not authorization to execute Phase 6 Batch
2 or make a model/provider call.

## 13. Commit lineage before handoff

| Purpose | Commit |
| --- | --- |
| Required Phase 5 closure baseline | `4aa7256e2237e997425e8712638334088056037d` |
| Activate owner-provided Phase 6 plan | `38b9db1ec7f9460fc0861f22caeeac3f9124ef9b` |
| Record Phase 6 research framing | `8852de2302f4377727e263342d999340fa6b22e8` |
| Define gates and fixtures | `d5175af152a7d8423d5e2b7cca2b2d51e2e65840` |
| Implement offline assessment substrate | `136c7423c8091c5cdca00cba1fcf8f52d998b483` |
| Add focused tests | `b29f4f3f8adf7b025cc3f4a7869684182f49e61e` |
| Final definition/code freeze | `9b46fb55bbbe400823efcd08b3b09d74196e869b` |
| Preserve authoritative offline run | `89dc196357c991ece19f10ab6fbfbb5c8d83cb34` |
| Interpret Batch 1 result | `904053c271cf6091786213dbea2d6b7cc0d9e0f4` |

No commit was amended, rebased, squashed, or force-pushed. The handoff commit
follows this table; plan retirement follows the handoff as the lifecycle
boundary.

## 14. Preservation and handoff boundary

Compared with the required baseline, `git diff` contains zero paths under:

```text
sources/
references/papers/
irisx/core/
```

All model-execution evidence used by replay remains byte-identical to the
frozen source references. Model calls, provider calls, paid API calls, model
subprocesses, retries, routes, escalations, recovery actions, and external
effects performed by Batch 1 are all zero.

After this handoff is committed, retire the controlling plan, run final
deterministic validation, push `main` normally, confirm clean synchronized
state, report to the owner, and stop. Do not start Phase 6 Batch 2.
