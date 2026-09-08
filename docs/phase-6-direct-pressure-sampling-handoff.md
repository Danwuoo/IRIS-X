# Phase 6 Batch 2 — Direct Pressure Sampling Handoff

- **Status:** Complete — **Result C — Sampling not semantically interpretable**
- **Date:** 2026-09-08 Asia/Taipei
- **Batch:** Phase 6 Batch 2 — TURN B collection and closure
- **Repository:** Danwuoo/IRIS-X
- **Required Batch 2 baseline:** `a0ca60de39cc291fb9ad185d7de40cd6b4b5909d`
- **Definition/code freeze:** `ba7ef9964d268d1342d7cec02beedd5563c0136a`
- **Launch-ready SHA:** `cacdb53105f8b2d378e618d8ac785eac4501c1c1`
- **Raw collection evidence commit:** `3e240434a72b9fe48d0456ad039d91048169a5d4`
- **Adjudication evidence commit:** `7340167a466ce013a96bf2b0cb1834cca73ed863`
- **Research result commit:** `a7adb31e2c4fa44bdf26f050f4e32453c9540b77`
- **Authorized / actual logical model-call boundaries:** `6 / 4`
- **TURN B model/provider calls:** `0`

The handoff commit and later plan-retirement commit do not exist while this
document is authored. Their full SHAs are recorded in the controlling-plan
retirement record and final owner report.

## 1. Outcome

**Result C — Sampling not semantically interpretable.**

The original TURN A runner produced three authoritative verified successes,
then P4 was rejected at the provider response-format boundary because its
frozen schema used `uniqueItems`, which that boundary reported as not
permitted. No P4 raw model result exists. The frozen stop policy correctly
prevented P5 and P6 from being attempted.

This is an execution/evidence-path result, not a task-level semantic miss and
not model-capability evidence. P1–P3 remain valid bounded successes, but the
intended six-task sample did not complete authoritatively.

No capability gate became `triggered_by_direct_evidence`. No retry, rerun,
replacement task, alternate allocation, stronger-model comparison, route,
fallback, escalation, recovery action, model judge, tool call, or external
action occurred in TURN B.

## 2. Starting and launch identity

Repository preflight began at the owner-supplied launch-ready state:

```text
HEAD:        cacdb53105f8b2d378e618d8ac785eac4501c1c1
main:        cacdb53105f8b2d378e618d8ac785eac4501c1c1
origin/main: cacdb53105f8b2d378e618d8ac785eac4501c1c1
ahead/behind: 0 / 0
tree: clean
```

TURN A immutable metadata:

| Field | Value |
| --- | --- |
| Runner PID | `16592` |
| Launch timestamp | `2026-09-08T14:08:05.8263057Z` |
| Immediate observation | running / had not exited |
| Staging root | `C:\Users\wurre\AppData\Local\Temp\irisx-phase-6-batch-2-turn-a-20260908T140530Z` |
| Definition/code freeze | `ba7ef9964d268d1342d7cec02beedd5563c0136a` |
| Launch-ready SHA | `cacdb53105f8b2d378e618d8ac785eac4501c1c1` |
| Admission status | `admitted` |
| Admission record SHA-256 | `7abfa9dc397578516f806bf1841bbc21248fe6a73ba521239c311db040f9b640` |
| TURN A collection/monitoring | not performed / not performed |

The single initial TURN B inspection found PID `16592` inactive and the
staging root present. No additional process-state inspection was needed.

## 3. Admission and freeze integrity

The exact allocation remained:

```text
codex-cli 0.147.0
provider slot irisx_openai_no_retry
gpt-5.6-luna / medium
ChatGPT authentication and subscription billing
read-only / approval never / tools disabled
HTTP retries 0 / stream retries 0 / WebSockets disabled
```

The admission record remains byte-identical to the accepted Phase 5 current
record. All four staged commands normalize to the admitted profile. The frozen
definition, task, verifier, derivation, runner, collector, and test paths have
zero diff between the freeze and launch-ready SHAs. Only the admission record
and launch manifest were added after the freeze.

No profile, model, reasoning effort, provider, authentication fallback,
sandbox, retry, route, fallback, escalation, recovery, or tool drift was
observed.

## 4. Collection and evidence identity

The external staging completion record has SHA-256
`ef019de2325bb20e37ee1ec2017c271df07d91fc305f77851a9a1d8e764df6bc`.
It records completion at `2026-09-08T14:08:31.745406+00:00`, four attempted
tasks, and `stopped_on_systemic_or_safety_failure: true`.

The frozen collector failed closed with:

```text
staging task artifacts missing for p4-dependency: ['raw-output.txt']
```

No missing output was created. All 38 available staging files were copied
byte-for-byte into immutable Batch 2 paths. The complete pre-copy inventory is
`runs/batch-2/staging-inventory.json`, SHA-256
`5037ac06e91dfb6fdbb63eab147ace630d71f9efdbe667f60a66dd7d909188c9`.
The collection record SHA-256 is
`d91bc2a16b4b3cc64c0ad184699680d03f2762f3225dcb62307d6d82dfa72412`.

Authoritative derived identities:

| Artifact | SHA-256 |
| --- | --- |
| `runs/batch-2/direct-predicates.json` | `7049f18d308d665408c15eb9fe10d6c260e8b640fc5c3d84370c871865f8adcc` |
| `runs/batch-2/summary.json` | `aeb0ba8d4327f00a6fc91d92b420950962d37a38b1af73801dfa0c60d16e1a36` |
| `runs/batch-2/adjudication-summary.json` | `ee2ba2c639a7b78b0b43f06a804582639ff1be6b3e1267691b8d15b0ee261a34` |

The direct-predicate SHA-256 is fully recorded in the validation record and is
repeated correctly below:
`7049f18d308d665408c15eb9fe10d6c260e8b640fc5c3d84370c871865f8adcc`.

## 5. Per-task terminal results

| Frozen task ID | Attempted | Logical model calls | Provider/model result | Structured/schema/semantic status | Terminal result |
| --- | ---: | ---: | --- | --- | --- |
| `phase6-p1-multi-constraint-selection-v0` | yes | 1 | usable result | parse pass; schema pass; exact oracle pass | `verified_success` |
| `phase6-p2-multi-group-exact-aggregation-v0` | yes | 1 | usable result | parse pass; schema pass; exact oracle pass | `verified_success` |
| `phase6-p3-constrained-multikey-ranking-v0` | yes | 1 | usable result | parse pass; schema pass; exact oracle pass | `verified_success` |
| `phase6-p4-dependency-closure-v0` | yes | 1 | no usable result; response schema rejected | parse/schema/semantic model-result checks not assessed | `systemic_failure` |
| `phase6-p5-deterministic-record-reconciliation-v0` | no | 0 | not invoked after systemic stop | not assessed | `incomplete_not_attempted` |
| `phase6-p6-ordered-rule-precedence-v0` | no | 0 | not invoked after systemic stop | not assessed | `incomplete_not_attempted` |

Aggregate:

```text
attempted: 4/6
completed usable provider/model results: 3
verified successes: 3/6
semantic failures: 0
systemic failures: 1
missing/incomplete task results: 2
```

P4 attribution is `systemic_execution_failure`, directly supported by the
provider event and absent raw output. Task-level pressure and model-intrinsic
capability failure are `Not established`. P5/P6 are not attributable task
failures because their invocation boundaries were never crossed.

## 6. Resource accounting

| Resource | Direct observation |
| --- | ---: |
| Authorized model-call ceiling | 6 |
| Logical model-call boundaries crossed | 4 |
| Completed usable provider/model results | 3 |
| Retries | 0 |
| Routes | 0 |
| Fallbacks | 0 |
| Escalations | 0 |
| Recovery actions | 0 |
| Tool calls | 0 |
| Paid API calls | 0 |
| Total observed runner wall time | 24,759,044,700 ns |
| Network / transport requests | `Unknown` / `Unknown` |
| Provider cost | `Unknown` |

P1–P3 expose a partial observed token sum of 15,235 input, 643 output,
and 408 reasoning tokens. P4 token usage is `Unknown`; therefore complete
batch token totals remain `Unknown`.

## 7. Predicate provenance and gate status

Direct-predicate provenance validation passed. The 12 records contain one
`true`, seven `false`, four `unknown`, and zero `conflicting` values. Every
resolved predicate binds a frozen rule identity/hash, exact source path and
SHA-256, JSON pointer, and observed value. Unknowns remain unknown where task or
comparison observations do not exist. No manual Boolean override occurred.

| Capability | Direct-evidence result | Changed from Phase 5 `Not triggered`? |
| --- | --- | --- |
| H-G1 automated specialization | `not_triggered` | No |
| H-W1 workflow machinery/search | `not_triggered` | No |
| H-C1 cascade/escalation | `insufficient_or_ambiguous` | No positive trigger; complete required evidence is absent |
| H-R1 feature-based routing/allocation | `not_triggered` | No |
| Runtime persistence | `not_triggered` | No |
| Nondeterministic verifier/model judge | `not_triggered` | No |
| External-action/interception expansion | `not_triggered` | No |
| General recovery/retry | `insufficient_or_ambiguous` | No positive trigger; no benefit comparison exists |

Direct-evidence triggered gates: **0**. The ambiguous statuses are retained
rather than fabricated as false predicates. Negative controls did not act as
vetoes and no negative-control conflict was observed.

## 8. Validation results

| Validation | Result |
| --- | --- |
| Batch 2 definition validation | PASS — 6 tasks, 48 verifier cases, 12 derivation rules |
| Batch 2 focused tests | PASS — 27/27 |
| Phase 6 Batch 1 focused tests | PASS — 35/35 |
| Phase 5 model qualification/task-family suite | PASS — 75/75 |
| Repository check | PASS — 13 sources, 7 artifacts, hashes checked |
| Freeze integrity | PASS |
| Admission and four command identities | PASS |
| Staging manifest and exact-byte collection hashes | PASS |
| P1–P3 raw-output deterministic re-verification | PASS |
| Direct predicate provenance | PASS |
| Predicate and summary byte-identical regeneration | PASS |
| Full discovered inventory | 258 run; 257 passed; 1 failed; 0 errors |
| New failures/errors | 0 |

The sole full-inventory failure is the unchanged historical Phase 4 contract
`HPIaContractTests.test_frozen_artifact_hashes_match_exact_bytes` for
`docs/plans/TEMP_PHASE_4_FINAL_MODEL_SPECIALIZATION_AND_CLOSURE.md`: expected
`9e2ac0aabcae9a89ed92d9145ec787f4d6ee1920b5344be703498c6435aaf76c`,
observed
`4f3e47a6fa8af63dee6d4397d995a917a216ce70791416909e76a5448697246b`.
It was not changed, suppressed, skipped, or rebaselined.

## 9. Preservation status

The following Git trees match the required Batch 2 baseline exactly:

| Protected material | Git tree identity |
| --- | --- |
| `sources/` | `10e28d83184c789fc468ca1edc3bebf42ba40b46` |
| `references/papers/` | `ed29ebcde3f01b00a0e49eb33eef1688566dcad3` |
| `irisx/core/` | `773856fec635535f28c5df37c19bc7914f3a3f64` |
| Phase 6 Batch 1 experiment | `bbd024379bd00d4b9420872f8d94c9a76b2117f1` |
| Phase 5 model-qualification substrate | `4e868e10c07b1de7db34f04435281a37289c6b13` |

Historical Phase 4/5/6 Batch 1 plans, handoffs, definitions, and evidence were
not rewritten. No `irisx/core` architecture semantics changed.

## 10. Supported and unsupported conclusions

Supported:

- P1–P3 were verified successes under the exact frozen allocation.
- P4 encountered a non-semantic response-schema compatibility failure.
- The systemic stop and zero-retry/no-mechanism invariants held.
- Direct predicate provenance is valid and zero gates triggered.

Not established:

- semantic capability on P4, P5, or P6;
- model-intrinsic causality;
- retry, stronger-allocation, routing, workflow, persistence, judge,
  specialization, recovery, or external-action benefit;
- general task coverage, provider portability, production reliability,
  lifecycle-cost superiority, final failure ontology, or final architecture.

Ambiguities: H-C1 and recovery/retry cannot be fully evaluated from missing
task/comparison observations. Unknowns include P4 inference status, complete
token totals, network/transport counts, provider cost, and P4–P6 semantic
outcomes. Conflicting evidence: none.

## 11. Exact next recommendation and stop boundary

Under a new, separate owner-authorized scope, repair and requalify only the
non-semantic sampling path by adding deterministic provider-response-schema
admissibility coverage and allowing a systemic missing-output record to be
collected without fabricating a raw answer. Do not consume the expired Batch 2
allowance and do not reinterpret or rerun this batch.

No mechanism experiment is triggered or authorized. Phase 6 Batch 3 is **NOT
started**.
