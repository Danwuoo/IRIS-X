# H-P1a reviewed blind interpretation

- **Status:** result — reviewed valid blind run
- **Run:** `blind-20260902-chatgpt-03`
- **Primary result:** `Supported — task-local`
- **Evidence classification:** directly observed post-freeze generated-blind, paired, oracle-backed local evidence
- **Definition/code commit:** `9815003b02aa5868a7582960db97cd1138e5709e`
- **Candidate-freeze commit:** `6ef4c9d09e6124a9cb6c47f6b12427be29dea19e`
- **Blind-authorization commit:** `20f8c229aa2bf8bfd1b4fb8ffcaf4bc815e28523`
- **Schedule SHA-256:** `0c9b5de755fc81bb704781267c8891b8d89551891a289488e530b445c640de76`

## Validity and coverage

The frozen schedule contained 96 entries: 32 each for C0, C1, and C2 over the same 32 blind tasks. Raw reconstruction found one and only one terminal record for every schedule index 1–96, in frozen order. All 96 invocations completed. There were zero subscription-limit events, provider terminal failures, malformed outputs, invalid bindings, invalid isolation events, prohibited tool attempts, retries, recovery actions, routes, or escalations. Every empirical evidence status was `sufficient`.

The blind outputs and raw event hashes were frozen before independent evaluation. Re-evaluation directly from all 96 raw `output.json` files reproduced every committed terminal evaluation field. Raw output, event, stderr, schedule, terminal-record, result, candidate, and program hashes reconstructed successfully.

## Primary C1 versus C0 result

| Configuration | Runtime | Program SHA-256 | Program bytes | Verified / 32 | Actual outcomes | False success | Malformed | Terminal/provider/subscription failures |
| --- | --- | --- | ---: | ---: | --- | ---: | ---: | ---: |
| C0 | Luna, medium | `1736879afe750b63bb4fb1913e1520e08f658fd3d414424cb100a310765855bb` | 1,389 | 18 | 18 success; 13 partial; 1 failure; 0 unresolved | 14 | 0 | 0 |
| C1 | Luna, medium | `8bf10ea83da6c6096405d1c12a045c9830f5d4a6dc2ebefeff538a9fc5eeec1b` | 2,764 | 32 | 32 success; 0 partial; 0 failure; 0 unresolved | 0 | 0 | 0 |
| C2 reference | Terra, medium | `1736879afe750b63bb4fb1913e1520e08f658fd3d414424cb100a310765855bb` | 1,389 | 23 | 23 success; 9 partial; 0 failure; 0 unresolved | 9 | 0 | 0 |

C1 improved verified success by 14 tasks over C0, with 14 paired C1 wins and zero paired C0 wins. The transition matrix was 18 `success/sufficient -> success/sufficient`, 13 `partial/sufficient -> success/sufficient`, and 1 `failure/sufficient -> success/sufficient`. C1 also reduced false success from 14 to zero and did not worsen malformed-output or invalid-terminal counts. Under the frozen result rule, the only valid label is:

> **Supported — task-local**

No percentage-improvement threshold was imposed.

## Family results

| Blind family | C0 verified | C1 verified | C2 verified |
| --- | ---: | ---: | ---: |
| Traceability extraction | 8/8 | 8/8 | 8/8 |
| Terminology consistency | 6/8 | 8/8 | 8/8 |
| Path/action guard | 4/8 | 8/8 | 7/8 |
| Structured simulation | 0/8 | 8/8 | 0/8 |

C0's 14 false successes comprised two terminology cases, four path/action-guard cases, and all eight structured-simulation cases. C2's nine false successes comprised one path/action-guard case and all eight structured-simulation cases. C1 had no false successes in any family.

## Paired discordant task identities

C1 succeeded where C0 did not on exactly these 14 tasks:

- `path-action-guard-v0-215c51731a59670c`
- `path-action-guard-v0-aa0f9e85d5864842`
- `path-action-guard-v0-c8b09df25c210ca9`
- `path-action-guard-v0-f19bdaf7520f3cc1`
- `structured-simulation-v0-0b8327118ef4e106`
- `structured-simulation-v0-0cdccefbbc70c309`
- `structured-simulation-v0-8bf97f9637c35685`
- `structured-simulation-v0-90393851f5b77e44`
- `structured-simulation-v0-9de37d7a5088abf9`
- `structured-simulation-v0-ceb3752ab2ac7c05`
- `structured-simulation-v0-f4626338ebcedc25`
- `structured-simulation-v0-f75da9f51ba76e5d`
- `terminology-consistency-v0-5955304b0a99cb9b`
- `terminology-consistency-v0-993d70efb830136a`

There were no tasks on which C0 achieved verified success and C1 did not.

## Bounded Terra reference

C2 used Terra with the exact same 1,389 seed-program bytes and SHA as C0. C1 was no worse than C2 on every frozen strict reference dimension and had 32 versus 23 verified successes, 32 versus 23 actual successes, 0 versus 9 false successes, and no malformed output, invalid binding, unresolved outcome, or terminal failure in either configuration. The permitted finite-sample conclusion is:

> **Observed finite-sample runtime-capability substitution — task-local**

This is a bounded reference result. It is not Luna/Terra model equivalence, not a general model-capability claim, and not a second H-P1 treatment.

## Resource observations

Blind runtime usage remained separate from design-time usage:

| Configuration | Calls | Input tokens | Cached input tokens | Output tokens | Reasoning tokens | Wall time ns | Prompt bytes total (min–max) |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| C0 | 32 Luna | 504,932 | 126,464 | 5,881 | `Unknown` | 306,561,216,700 | 92,152 (2,750–3,047) |
| C1 | 32 Luna | 510,903 | 130,560 | 4,795 | `Unknown` | 297,577,123,700 | 136,152 (4,125–4,422) |
| C2 | 32 Terra | 552,939 | 189,440 | 4,339 | `Unknown` | 294,898,347,500 | 92,152 (2,750–3,047) |

The design-time ledger is separate:

| Design stage | Calls | Input tokens | Cached input tokens | Output tokens | Reasoning tokens | Wall time ns |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| DEV Luna evaluations | 168 | 2,686,489 | 926,976 | 25,575 | `Unknown` | 1,739,017,680,000 |
| Validation Luna evaluations | 112 | 1,789,444 | 1,144,832 | 16,823 | `Unknown` | 1,388,844,293,500 |
| Terra optimizer | 6 | 186,855 | 0 | 3,921 | `Unknown` | 124,288,878,800 |
| Design total | 286 | 4,662,788 | 2,071,808 | 46,319 | `Unknown` | 3,252,150,852,300 |

Across design and blind runtime, the attempt used exactly 344 Luna calls, 38 Terra calls, and 382 total calls. These are resource observations, not subscription-dollar charges. `provider_cost_usd` remains `Unknown`; monetary lifecycle-cost advantage is `Not established`; no monetary break-even point is calculated.

## Design provenance and invalid attempts

C1 is optimizer-generated candidate `opt-02-r01`. Six unique optimizer candidates were produced before validation. C1 was selected once by the frozen tuple after all validation outputs were frozen; its validation result was 16/16 verified successes versus 10/16 for the seed. Its bytes were committed before blind-seed generation and were unchanged afterward.

Two prior H-P1a design attempts remain excluded from valid aggregates and immutable:

- `design-20260901-chatgpt-01`: `incomplete-blocked`; 24 Luna plus 2 Terra formal attempts ended in deterministic provider schema compatibility errors, producing zero eligible optimizer candidates and no validation or blind data.
- `design-20260901-chatgpt-02`: `incomplete-blocked-pre-invocation`; relative admission-path binding failed before any formal model, network, or API call.

The original specialization substrate `dry-run-20260901-local-01` is also preserved unchanged with its historical outcome/evidence vocabulary. The corrected fake qualification and provider-schema preflight supersede it only for future execution semantics; they do not rewrite it.

## Interpretation boundary

The result supports H-P1a only for the frozen four generated families, generator difficulty `{"count": 4}`, 32 post-freeze blind tasks, declared evaluator/oracle, Luna/Terra aliases observed at this run, medium reasoning, no tools, and the exact candidate/runtime envelope. Difficulty calibration, real-world representativeness, provider-alias temporal drift, repeated optimizer behavior, distribution shift, concurrency, long duration, production operation, external actions, and general lifecycle economics remain `Unclear`, `Unknown`, `Not established`, or `Not evaluated` as applicable. The parent H-P1 is not established because the experiment does not establish a monetary or complete lifecycle-cost offset and does not test repeated optimizer seeds under a general task distribution.
