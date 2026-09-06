# Phase 5 Batch 6 — Model Task-Family Qualification Handoff

- **Status:** Complete — architecture exercise accepted and full three-task-family qualification established
- **Date:** 2026-09-06 Asia/Taipei
- **Repository:** Danwuoo/IRIS-X
- **Required and actual starting SHA:** `cd2b3f60a802a3f0438dc38792fd58b45bde820e`
- **Definition/code freeze SHA:** `2320858ba1f5dc5d7c68ba426278106c565ac6b4`
- **Architecture authority:** provisional and substrate-local
- **Live model calls authorized/made:** `3 / 3`, exactly one independently authorized call per task

## Outcome

Phase 5 Batch 6 reused the already-admitted Codex CLI 0.147.0 / GPT-5.6 Luna
medium execution profile across exactly three independently frozen, read-only,
deterministically verified task families: ordered threshold filtering, grouped
numeric aggregation, and top-N ranking with an explicit tie-break. All three
live results were healthy provider completions and independently adjudicated as
`verified_success`.

The shared provider-specific adapter remained outside `irisx.core`. Task,
contract, program, evidence, verifier, schema, oracle, execution, and run-path
authority remained task-specific. The adversarial zero-model-call suite rejected
every crossed identity/evidence/program/verifier case. The offline corpus
accepted all three correct synthetic outputs and rejected all 24 malformed or
semantically invalid outputs through the real deterministic verifier and
canonical adjudication path.

The strongest allowed conclusion is:

> **Phase 5 Batch 6 complete — the admitted model-backed execution profile was reused across three semantically distinct frozen deterministic task families while preserving task-specific identity, contract-bound evidence, independent verification, canonical adjudication, read-only execution, and zero-retry cross-task isolation.**

Architecture exercise acceptance is established. Full task-family qualification
is also established because the exact semantic success count is `3 / 3`.

## Repository and commits

1. `b9903c825504746d802a1186fc2fb9eacb70673c` — `docs: activate Phase 5 task-family qualification plan`
2. `ffdafa39cbf431010de64551ab45a7d19d5cdcd0` — `docs: align Phase 5 task-family authority`
3. `272f54db77688378a798460010fd16f064be555c` — `experiments: freeze model task-family definitions`
4. `bebdaeb90e57a4ade24f8ccc8023c10c42c2013c` — `experiments: extract reusable task-family model adapter`
5. `2320858ba1f5dc5d7c68ba426278106c565ac6b4` — `tests: validate task-family semantics and cross-task isolation`
6. `ddf9d1f9f924fcd877eb91bdfea96f645fd846ae` — `experiments: record task-family admission snapshot`
7. `9ef207b922c0b4dcb5fce61dce984bb0dfe02a22` — `experiments: record filter qualification run`
8. `83782d34529b8d9ec2febed24d7899e696a91f44` — `experiments: record aggregation qualification run`
9. `cf52d4c1b2ad3ab3f01379ff25987977f9cabe81` — `experiments: record ranking qualification run`
10. `81c2d48bc0c8b7390a464e7bd063666b63103342` — `experiments: summarize task-family qualification`
11. Durable handoff commit — reported after this file is committed.
12. Separate plan-retirement commit — reported after retirement.

No commit was amended, rebased, squashed, force-pushed, or otherwise rewritten.
The final local/remote SHA, clean-tree state, ahead/behind state, and normal push
result are reported in the owner-facing final response because they occur after
this handoff becomes immutable.

The executable task-family surface did not change after the definition/code
freeze. A path-scoped diff from `2320858ba1f5dc5d7c68ba426278106c565ac6b4`
through the summary commit returned zero paths for definitions, inputs, schemas,
programs, negative fixtures, the shared adapter, runner, verifier helpers, and
task-family tests.

## Frozen task family

| Task | Task ID | Semantic family | Contract ID / SHA-256 | Oracle | Verifier |
| --- | --- | --- | --- | --- | --- |
| A | `task-family-filter-threshold-v0` | `filter-set-selection` | `contract-task-family-filter-threshold-v0` / `b2b86fa439a9d8705856b53940c681f47f3ad67e3daa74a26595bc6e48743ce0` | `oracle-filter-score-gte-threshold-input-order-v0` | `filter-selection-verifier-v0` |
| B | `task-family-aggregation-region-v0` | `grouped-numeric-aggregation` | `contract-task-family-aggregation-region-v0` / `4eb1ace0cc27e967895d0572a034ec5c52481fd96fa2aaaa932d43daaa991b31` | `oracle-sum-amount-for-target-region-v0` | `aggregation-total-verifier-v0` |
| C | `task-family-ranking-top-n-v0` | `ordered-ranking-transformation` | `contract-task-family-ranking-top-n-v0` / `902042c0b3f7198b8cecdc856d40652bd56fc6ca58aa4b5ac3da5791f5759e3e` | `oracle-score-desc-id-ascending-top-n-v0` | `ordered-ranking-verifier-v0` |

| Task | Input SHA-256 | Schema SHA-256 | Program ID / SHA-256 | Prompt SHA-256 |
| --- | --- | --- | --- | --- |
| A | `b0c055410b58ca893a03d7dc04414334c3942fd90c69c7b0597dc518922b7cd5` | `f1afcc3ba3a34e9aae9dbd5c459e386136efed0edecb87cf55b3991c8f34fdb8` | `program-task-family-filter-threshold-v0` / `f6a4facd6c10511d7f1f56574bd36e62d41d0948be81d308fb4911687795ba01` | `2d5cb98f53537b3bb046161123bc6e890c81e5b6a4cfa1ca10d1364bb011b91b` |
| B | `9a0b2d77938db9fce15bac432cd854d11c1a20f18f616f82bc7d2ce3bfcb7240` | `6f01a7914bb3021f975dd9079ad85ccee38ebd27df0163e993147e205985bffc` | `program-task-family-aggregation-region-v0` / `54eee9495c249d68cc309a0569f4673ee3b32d82b653e860afcc0841efd605d1` | `071b2f77e04dad1ea1e9e12959226138bff2611121d88169b7fd51eb7e50c46c` |
| C | `fd7a8059f74c3076a509b7550377014e46856b6d3a17038e94b3cd4a31c55814` | `4b61b9089ac175bf94687df8e1b4f7f4168ad9dfc02877681375870730412f18` | `program-task-family-ranking-top-n-v0` / `1dc285bccd14dcf156accc3ef68b57b63d9d5eab0bb741556668e69516f4266d` | `6baef75d687a74e09cf93b4e550adc173e0e944d88a2ac88efb237ab57c0699c` |

All definitions, inputs, output schemas, programs, deterministic verifier code,
shared adapter code, negative fixtures, runner code, and tests were committed
before the admission snapshot or first live task.

## Admission binding

| Field | Bound value |
| --- | --- |
| Admission profile ID | `codex-cli-0.147.0-run-03-admission-v0` |
| Admission profile SHA-256 | `ab21119f80141456e7327e276fa3e470abf288cf6a3535ac5fceeace68302033` |
| Batch 6 snapshot path | `experiments/substrates/model-execution-qualification-v0/task-family/admission/current-environment-20260906.json` |
| Batch 6 snapshot SHA-256 | `7abfa9dc397578516f806bf1841bbc21248fe6a73ba521239c311db040f9b640` |
| Snapshot commit | `ddf9d1f9f924fcd877eb91bdfea96f645fd846ae` |
| Admission result | `admitted`; no reasons |
| Executable / version | `C:\Users\wurre\AppData\Roaming\npm\codex.cmd` / `codex-cli 0.147.0` |
| Provider / slot | `openai` / `irisx_openai_no_retry` |
| Model / role / reasoning | `gpt-5.6-luna` / `cheaper` / `medium` |
| Authentication / billing | ChatGPT / ChatGPT subscription |
| API-key fallback | prohibited; none used |
| Sandbox / approval / tools | `read-only` / `never` / disabled |
| HTTP / stream retries / WebSockets | `0 / 0` / disabled |

The snapshot is byte-identical to the accepted Batch 5 current-environment
record. Each task manifest binds its profile ID/hash, this snapshot path/hash,
`admitted` status, the definition/code freeze SHA, and its own launch HEAD.
Immediately before each live call, the Batch 5 checker returned `admitted` with
provider attempts `0` and live model calls `0`. No `AdmissionGate` or other
provider-specific admission interface entered `irisx.core`.

## Per-task live execution

### Task A — Filter / Set Selection

| Field | Result |
| --- | --- |
| Run ID / evidence commit | `task-family-20260906-a-filter` / `9ef207b922c0b4dcb5fce61dce984bb0dfe02a22` |
| Launch HEAD | `ddf9d1f9f924fcd877eb91bdfea96f645fd846ae` |
| Raw output | `{"selected_ids":["b","d"]}` |
| Raw output SHA-256 | `14427fec4c08966df21bad3d6127ccbbac5bbbb092376d3c698a29196509ce11` |
| Provider events SHA-256 | `4437f7146614750f2cbf7053bb96a6b2b43dd26b2ff249fa44ed2da2ab6681e7` |
| Terminal record SHA-256 | `1536719c3da17a7ac12cab6c83e2c431cba387d4efe4f0e7c437f239f7c2014c` |
| Model/provider calls | `1 / 1` |
| Token usage | input `4160`; cached input `0`; cache-write input `0`; output `19`; reasoning `0` |
| Wall time | `4,256,864,200 ns` |
| State before / after | `e3b7d26e6d6525a8980adc700ecd334f347e3f6713270e6a99dd2a53aeb41ec5` / same |
| Verifier | semantic valid: `true`; `deterministic_filter_selection_match` |
| Terminal semantics | evidence `sufficient`; acceptance `accept`; eligibility `true`; execution `completed`; joint `verified_success` |

### Task B — Aggregation

| Field | Result |
| --- | --- |
| Run ID / evidence commit | `task-family-20260906-b-aggregation` / `83782d34529b8d9ec2febed24d7899e696a91f44` |
| Launch HEAD | `9ef207b922c0b4dcb5fce61dce984bb0dfe02a22` |
| Raw output | `{"total":43}` |
| Raw output SHA-256 | `0b8a389282e2a945b0faa96fd9ec7d925a4f3a1a5ece30e599ea222bc2dfdec2` |
| Provider events SHA-256 | `80d718a16715812c0ddb457bb392e41987d059f44bde47e2ada9490c718978dd` |
| Terminal record SHA-256 | `0f6f55237883d58bf2dfab79be9ddea1eec708acf52b6e60b0080a54db084b62` |
| Model/provider calls | `1 / 1` |
| Token usage | input `4130`; cached input `0`; cache-write input `0`; output `36`; reasoning `19` |
| Wall time | `3,555,293,200 ns` |
| State before / after | `3d2d941751536363f029124b4376bca7a5acbea890445ff8b9727602e784506e` / same |
| Verifier | semantic valid: `true`; `deterministic_aggregation_match` |
| Terminal semantics | evidence `sufficient`; acceptance `accept`; eligibility `true`; execution `completed`; joint `verified_success` |

### Task C — Ordered Ranking / Transformation

| Field | Result |
| --- | --- |
| Run ID / evidence commit | `task-family-20260906-c-ranking` / `cf52d4c1b2ad3ab3f01379ff25987977f9cabe81` |
| Launch HEAD | `83782d34529b8d9ec2febed24d7899e696a91f44` |
| Raw output | `{"ranked":[{"id":"b","rank":1},{"id":"c","rank":2}]}` |
| Raw output SHA-256 | `a4d7160269976561643c3816f7b84d5623f31a4840f5f27e868450ce778640ee` |
| Provider events SHA-256 | `dd225af031decba4262c99b2957c5248bf6458921ba4daa5869d7b8d370101d8` |
| Terminal record SHA-256 | `017be5556ce0eccd665eeed94bb7236bba1a555a5cea2f5498e17054384b34bb` |
| Model/provider calls | `1 / 1` |
| Token usage | input `4206`; cached input `0`; cache-write input `0`; output `57`; reasoning `23` |
| Wall time | `6,018,089,400 ns` |
| State before / after | `11851ecf7e4517a80b30b1d7797973d7fe403f3a7bf55ce1282ee57c4f5750d6` / same |
| Verifier | semantic valid: `true`; `deterministic_ordered_ranking_match` |
| Terminal semantics | evidence `sufficient`; acceptance `accept`; eligibility `true`; execution `completed`; joint `verified_success` |

Every run recorded changed paths `[]`. For every task, retry, route, fallback,
escalation, recovery, and tool counts were `0`; network and transport request
counts were `Unknown`; provider cost was `Unknown`; and no API price estimate
was applied to ChatGPT subscription usage.

## Cross-task isolation

All 12 adversarial tests passed without a model call:

| Adversarial case | Outcome |
| --- | --- |
| Task A contract + Task B program | rejected before execution — PASS |
| Task A contract + Task C program | rejected before execution — PASS |
| Task A evidence used for Task B | rejected — PASS |
| Task B evidence used for Task C | rejected — PASS |
| Task A output under Task B verifier | rejected — PASS |
| Task B output under Task C verifier | rejected — PASS |
| Task C output under Task A verifier | rejected — PASS |
| Task B schema used for Task C | rejected — PASS |
| Task C program identity paired with Task A | rejected — PASS |
| Crossed task-specific evidence path | rejected — PASS |
| Wrong program hash | rejected before execution — PASS |
| Task-specific contract/program hashes are distinct | established — PASS |

This establishes the target invariant: **shared adapter does not grant shared
task authority**.

## Offline negative-output corpus

All 27 synthetic cases passed their expected canonical outcome: the three
`correct` cases became `verified_success`; all 24 negative cases were rejected.
No live model or model judge was used.

| Task | Fixture SHA-256 | Cases | Result |
| --- | --- | ---: | --- |
| A | `6e1e7a427e930e836109fd06ef467aff5d7d1b13c86402fcc0f75074aba35e22` | 8 | 1 correct accepted; 7 negatives rejected |
| B | `8710178f686ae774147d0f9d9972090af1a774e7ca57fb67b48919ea8320471c` | 8 | 1 correct accepted; 7 negatives rejected |
| C | `77ec11abdccf0e7ccd49a1b7f0557cdf0e06e8ead2a4a97c5dd6e5f8e6d6dd1e` | 11 | 1 correct accepted; 10 negatives rejected |

Task A covers malformed JSON, schema-valid semantic error, missing result,
extra result, wrong order, wrong schema, and a producer success claim paired
with semantic failure. Task B covers the same required classes with wrong
aggregate. Task C additionally covers tie-break violation, wrong rank
assignment, and wrong rank count. Producer claims never overrode independent
semantic failure.

## Derived batch summary

The derived summary is
`experiments/substrates/model-execution-qualification-v0/task-family/summaries/batch-6-summary.json`,
SHA-256 `7f045a2f604843e9d41c4e02274b2a6758d0677c15be0dfcfeb824ef2c5ec05c`,
committed at `81c2d48bc0c8b7390a464e7bd063666b63103342`. The three per-task
`TerminalRecord` files remain the source of truth.

| Batch field | Observed value |
| --- | --- |
| Attempted / completed / verified-success tasks | `3 / 3 / 3` |
| Semantic / systemic failures | `0 / 0` |
| Provider attempts / model calls | `3 / 3` |
| Input / cached / cache-write tokens | `12,496 / 0 / 0` |
| Output / reasoning tokens | `112 / 42` |
| Aggregate wall time | `13,830,246,800 ns` |
| Retries / routes / fallbacks | `0 / 0 / 0` |
| Escalations / recovery actions / tool calls | `0 / 0 / 0` |
| Network / transport requests | `Unknown / Unknown` |
| Provider cost | `Unknown` |
| Architecture exercise accepted | `true` |
| Full task-family qualification | `true` |

## Validation and regression

Focused deterministic validation after all live evidence was committed:

- core tests: 28/28 PASS;
- deterministic mutation-path tests: 13/13 PASS;
- deterministic read-only integration tests: 9/9 PASS;
- model-execution substrate tests: 75/75 PASS;
- focused total: **125/125 PASS**.

The model-execution count consists of 29 Batch 5 admission tests, 20 preserved
Batch 4 qualification tests, 14 Batch 6 task-family tests, and 12 Batch 6
cross-task isolation tests. The 27 offline output cases execute within the
task-family corpus test.

Additional deterministic checks passed:

- repository validation: 13 sources and 7 paper artifacts, hashes checked;
- accepted provider/model baseline and bundled Codex 0.147.0 catalog;
- current admission check: `admitted`, zero provider attempts/model calls;
- all three frozen task definitions;
- all three immutable run validators;
- derived batch-summary validator;
- post-freeze executable-surface diff: zero paths;
- Git whitespace check: no findings.

The established full inventory covered 17 test directories:

```text
total: 196
passed: 195
failures: 1
errors: 0
skipped: 0
new failures/errors: 0
```

The sole failure remains the unchanged historical Phase 4 assertion
`HPIaContractTests.test_frozen_artifact_hashes_match_exact_bytes` for
`docs/plans/TEMP_PHASE_4_FINAL_MODEL_SPECIALIZATION_AND_CLOSURE.md`. Its
observed SHA-256 remains
`4f3e47a6fa8af63dee6d4397d995a917a216ce70791416909e76a5448697246b`;
the preserved assertion expects
`9e2ac0aabcae9a89ed92d9145ec787f4d6ee1920b5344be703498c6435aaf76c`.
It was not edited, skipped, suppressed, repaired, or reclassified. There were
no new failures, errors, or skips.

## Preservation proof

The following Git trees are identical at the required baseline and the Batch 6
summary head:

| Material | Baseline/current Git tree |
| --- | --- |
| `sources/` | `10e28d83184c789fc468ca1edc3bebf42ba40b46` |
| `references/papers/` | `ed29ebcde3f01b00a0e49eb33eef1688566dcad3` |
| `research/` | `0d89db5ef0d4712e6068bd499c11a852570633da` |
| `irisx/core/` | `773856fec635535f28c5df37c19bc7914f3a3f64` |
| historical model-qualification `definition/` | `f70469ea77b55dfee12dcd838a9d94d17cc78a22` |
| historical model-qualification `runs/` | `088f939b85392f5df640b69133a913dcd00e1c9a` |

No prior plan or durable handoff changed. Relative to the baseline, the plans
directory contains only the newly added Batch 6 TEMP plan; retirement appends
only this plan's record. All prior Phase 4/5 evidence, Run 01/02/03 artifacts,
frozen definitions, accepted baseline, Batch 5 profile/result, deterministic
inputs, sources, papers, and research records remain unchanged.

The overall tracked run inventory changed only by the three new immutable
Batch 6 task-family run directories and their 24 artifacts: 19 directories / 847
files before, and 22 directories / 871 files after. No prior run was overwritten.

No provider-specific code, provider registry, SDK, task registry, workflow
engine, plugin architecture, or `AdmissionGate` was introduced in `irisx.core`.

## Excluded mechanisms and research boundary

Terra, model comparison, a second provider, routing, cascades, fallbacks,
escalation, retries, recovery, persistence, workflow search, optimizers, model
judges, non-deterministic verifiers, multi-agent execution, training or
fine-tuning, external actions, tool-enabled tasks, a provider registry/SDK,
production API/UI, and architecture search were not implemented or evaluated.
No mechanism diversity was added. Provider/model identity stayed fixed across
all three tasks.

```text
H-G1: Not evaluated
H-W1: Not evaluated
H-C1: Not evaluated
H-R1: Not evaluated
```

## Closure boundary

After this handoff is committed, retire the controlling TEMP plan in a separate
commit, run final deterministic checks, push `main` normally, confirm a clean
tree and ahead/behind `0/0`, and stop. Do not start Batch 7 or add another task
family or mechanism without separate owner authorization.
