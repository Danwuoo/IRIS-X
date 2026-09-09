# Phase 6 Batch 3 — Sampling Path Repair and Requalification Handoff

- **Status:** Complete — **Result D — Provenance or authority conflict**
- **Date:** 2026-09-09 Asia/Taipei
- **Batch:** Phase 6 Batch 3 — TURN B collection and closure
- **Repository:** Danwuoo/IRIS-X
- **Required baseline:** `07a71392a59f78e41ca32f1c9c377e2a43be41e6`
- **Definition/code freeze:** `3cdbec8e46fc923f591138809f587e59446e8109`
- **Launch-ready SHA:** `8a7d8524311ce71f5210b6b0df6937c3c9414700`
- **Raw collection evidence commit:** `565280f71de59a4d01932fd4cdede8ec46ae6f93`
- **Adjudication evidence commit:** `86eedd23bfbce08cfe17be7def34be30305af09c`
- **Validation evidence commit:** `7f891abd4110ff451f5cc944fc0bcd7730ca9ef1`
- **Research result commit:** `105578fd8ccaa2d4ddc5cbc3dd8741b4a7b6cb21`
- **Authorized / actual model-call boundaries:** `6 / 6`
- **TURN B model/provider calls:** `0`

The handoff and plan-retirement commit identities are recorded in the retired
controlling plan after those commits exist.

## 1. Outcome

**Result D — Provenance or authority conflict.**

The repaired sampling path completed all six intended tasks with six
provider-accepted usable structured results. Five results exactly matched
their deterministic oracles. P4 was a semantic miss: its valid dependency
order violated the frozen lexical tie-break.

The task result is interpretable, but the frozen capability-predicate authority
is not: its task sources point to Batch 2 and its named any-miss rule uses
`equals`, which makes mixed task observations conflicting. This conflict was
preserved. It was not repaired, overridden, or converted into a capability
trigger during TURN B.

No model call, retry, rerun, alternate model, route, fallback, escalation,
recovery action, model judge, tool call, external action, or architecture
implementation occurred in TURN B. Direct-evidence triggered gates: **0**.

## 2. Starting baseline and launch identity

TURN B started from the owner-supplied launch-ready state:

```text
HEAD:         8a7d8524311ce71f5210b6b0df6937c3c9414700
main:         8a7d8524311ce71f5210b6b0df6937c3c9414700
origin/main:  8a7d8524311ce71f5210b6b0df6937c3c9414700
ahead/behind: 0 / 0
tree:         clean
```

| TURN A field | Value |
| --- | --- |
| Runner PID | `10388` |
| Launch timestamp | `Unknown` — not present in the supplied or preserved launch identity |
| Immediate TURN A observation | launch-ready state supplied by owner |
| Staging root | `C:\Users\wurre\AppData\Local\Temp\irisx-phase-6-batch-3-turn-a-20260909T114125Z` |
| Completion timestamp | `2026-09-09T11:43:52.121326+00:00` |
| Admission status | `admitted` |
| Admission record SHA-256 | `7abfa9dc397578516f806bf1841bbc21248fe6a73ba521239c311db040f9b640` |

The exactly one initial TURN B inspection found PID `10388` inactive and the
staging root present.

## 3. Admission, freeze, and collection integrity

The exact allocation remained:

```text
codex-cli 0.147.0
provider slot irisx_openai_no_retry
gpt-5.6-luna / medium
ChatGPT authentication and subscription billing
read-only / approval never / tools disabled
HTTP retries 0 / stream retries 0 / WebSockets disabled
```

All six staged commands match the admitted profile. No model, reasoning,
provider, authentication, sandbox, retry, route, fallback, escalation,
recovery, or tool drift was observed. The current frozen executable definition,
runner, collector, and tests have zero diff from the definition/code freeze.
The freeze-to-launch-ready diff contains only the Batch 3 admission record and
launch manifest.

The staging inventory contains 57 files. Every file matches the staged byte
count and SHA-256 and was copied byte-identically; the aggregate SHA-256 is
`7ff65cb707e2775e96d0d9f6963e594c3173618431ff4c6f80b2bf15c6c62c53`.
The repaired collector passed, observed zero systemic no-output cases in this
launch, and fabricated zero raw-output files. The collection record SHA-256 is
`02404e86e1ce7e8084209460109894bb0f5f6c4444ce48828b4ec794d2bfd5ba`.

Authoritative evidence commit:
`565280f71de59a4d01932fd4cdede8ec46ae6f93`.

## 4. Per-task terminal results

| Frozen task ID | Attempted | Boundaries | Provider accepted / usable | Deterministic result | Terminal result |
| --- | ---: | ---: | --- | --- | --- |
| `phase6-p1-multi-constraint-selection-v0` | yes | 1 | yes / yes | exact oracle pass | `verified_success` |
| `phase6-p2-multi-group-exact-aggregation-v0` | yes | 1 | yes / yes | exact oracle pass | `verified_success` |
| `phase6-p3-constrained-multikey-ranking-v0` | yes | 1 | yes / yes | exact oracle pass | `verified_success` |
| `phase6-p4-dependency-closure-v0` | yes | 1 | yes / yes | exact oracle miss | `semantic_miss` |
| `phase6-p5-deterministic-record-reconciliation-v0` | yes | 1 | yes / yes | exact oracle pass | `verified_success` |
| `phase6-p6-ordered-rule-precedence-v0` | yes | 1 | yes / yes | exact oracle pass | `verified_success` |

P4 returned:

```json
{"ordered_ids":["source-a","source-b","normalize-a","normalize-b","join","quality-a","quality-b","validate","summarize","package","signoff","release"]}
```

The exact oracle requires `normalize-a` and `quality-a` before `source-b` under
the frozen lexical tie-break. This is a frozen-configuration task-level
semantic shortfall at the execution-producer stage. Intrinsic model capability
failure and every intervention benefit remain **Not established**.

Aggregate:

```text
attempted: 6/6
provider acceptances: 6
usable results: 6
verified successes: 5/6
semantic shortfalls: 1
system/evidence failures: 0
missing/incomplete task results: 0
```

## 5. Resource accounting

| Resource | Direct observation |
| --- | ---: |
| Authorized model-call ceiling | 6 |
| Invocation boundaries crossed | 6 |
| Provider acceptances | 6 |
| Usable results | 6 |
| Retries | 0 |
| Routes | 0 |
| Fallbacks | 0 |
| Escalations | 0 |
| Recovery actions | 0 |
| Tool calls | 0 |
| Input tokens | 29,732 |
| Output tokens | 1,609 |
| Reasoning tokens | 869 |
| Cached input tokens | 0 |
| Total observed runner wall time | 49,396,075,100 ns |
| Model inference execution | `Unknown` |
| Provider cost | `Unknown` |

No subscription cost was inferred from API pricing.

## 6. Direct predicate provenance and capability gates

The P4 task observation is directly bound to
`runs/batch-3/p4-dependency/terminal-record.json`, SHA-256
`a0ca487abef319e6be0157582c2ada82a37d7d4846deaf5bc455342651789edb`,
at `/attribution/task_level_pressure_observed`. Its safe capability-predicate
value remains `unknown` because the frozen derivation authority conflicts.

| Capability | Direct-evidence status | Changed to triggered? |
| --- | --- | --- |
| H-G1 automated specialization | `not_triggered` | No |
| H-W1 workflow machinery/search | `not_triggered` | No |
| H-C1 cascade/escalation | `insufficient_or_ambiguous` | No |
| H-R1 feature-based routing/allocation | `not_triggered` | No |
| Runtime persistence | `not_triggered` | No |
| Nondeterministic verifier/model judge | `not_triggered` | No |
| External-action/interception expansion | `not_triggered` | No |
| General recovery/retry | `insufficient_or_ambiguous` | No |

No capability gate changed from the prior `Not triggered` state to a positive
direct-evidence trigger. H-C1 lacks a stronger-candidate comparison. H-R1 lacks
an allocation comparison. Recovery/retry lacks an observed retry or benefit.

## 7. Validation results

| Validation | Result |
| --- | --- |
| Definition/provider-schema validation | PASS — 6 tasks, 48 negative cases, 12 derivation rules, 6 provider schemas |
| Batch 3 focused tests | PASS — 41/41 |
| Phase 6 Batch 1 focused tests | PASS — 35/35 |
| Phase 5 model qualification/task-family suite | PASS — 75/75 |
| Repository check | PASS — 13 sources, 7 artifacts, hashes checked |
| Freeze and admission integrity | PASS |
| Staging/evidence hashes | PASS — 57/57 and aggregate match |
| Independent raw-output reverification | PASS — all six terminal classifications reproduced |
| Summary regeneration | PASS — byte-identical |
| Frozen predicate evaluation regeneration | PASS — byte-identical |
| Direct observation provenance | PASS — conflict preserved without override |
| Full repository inventory | 272 tests: 271 passed, 1 known failure, 0 errors |
| New failures/errors | 0 |

The known historical Phase 4 failure remains
`HPIaContractTests.test_frozen_artifact_hashes_match_exact_bytes`: observed
`4f3e47a6fa8af63dee6d4397d995a917a216ce70791416909e76a5448697246b`
versus recorded
`9e2ac0aabcae9a89ed92d9145ec787f4d6ee1920b5344be703498c6435aaf76c`.
It was not repaired or rebaselined.

## 8. Preservation status

Batch 2 evidence, its research result, handoff, retired plan, and Result C
conclusion are byte-identical to baseline
`07a71392a59f78e41ca32f1c9c377e2a43be41e6`. The Batch 2 run tree remains
`4589cf38e5cd7c9a6cd035a5f1cb0814b0b2434c`.

`irisx/core`, `sources`, and `references/papers` also retain their baseline tree
identities. No historical run, imported source, or Phase 6 Batch 1/2 evidence
was rewritten.

## 9. Supported, unsupported, and uncertain conclusions

Supported: the repaired path completed; P1, P2, P3, P5, and P6 passed; P4
exhibited a task-local lexical tie-break shortfall; zero systemic failures and
zero forbidden mechanisms occurred; zero capability gates triggered.

Unsupported: intrinsic model incapability, general model capability, general
task coverage, retry/recovery benefit, stronger-model benefit, routing or
escalation benefit, workflow benefit, provider portability, production
readiness, general reliability, final failure ontology, and final architecture.

Conflicting evidence: frozen Batch 3 task-source binding and any-miss operator.
Unknown: provider cost and independently observable internal model-inference
execution. No missing task result remains.

## 10. Exact next recommendation

Close Batch 3 as Result D. A future owner-authorized, zero-model-call-only scope
may repair and freeze the research-local Batch 3 predicate source binding and
any-miss derivation operator, then validate them against this preserved
evidence. Do not implement a capability mechanism from this result.

**Phase 6 Batch 4: NOT started.**
