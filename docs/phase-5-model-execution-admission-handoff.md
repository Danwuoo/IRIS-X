# Phase 5 Batch 5 — Model Execution Admission Handoff

- **Status:** Complete — deterministic zero-model-call admission hardening
- **Date:** 2026-09-06 Asia/Taipei
- **Repository:** Danwuoo/IRIS-X
- **Required and actual starting SHA:** `21f0150aed8b8555b69dc1094a1c3d7a6441732b`
- **Architecture authority:** provisional, provider-specific, and substrate-local
- **Model/provider calls authorized and made:** `0 / 0`

## Outcome

Phase 5 Batch 5 converts the preserved Batch 4 Run 01 and Run 02 admission
failures and successful Run 03 configuration into one deterministic admission
check for the exact qualified Codex CLI 0.147.0 profile.

The checker statically evaluates the immutable historical commands and frozen
definition identities. It rejects the reserved-provider configuration used by
Run 01, rejects the unsupported `tools.view_image` field used by Run 02, and
admits Run 03 only after its complete normalized command and source hashes
match the frozen profile. A current-environment check also admits the present
machine using only local zero-call observations.

The strongest allowed conclusion is:

> **Phase 5 Batch 5 complete — the preserved Batch 4 Run 01 and Run 02 admission failures and successful Run 03 configuration are now distinguished by a deterministic zero-model-call admission check for the exact qualified Codex CLI 0.147.0 execution profile.**

Admission is only a compatibility finding. It does not authorize a future
model run, and no new run directory was created.

## Repository and commits

1. `da744ee59d76cf5c610a160d1af11c4241d4ee1e` — `docs: activate Phase 5 model-admission hardening plan`
2. `b2443365a32e3d4b2ca7bd272dda407e525f5ba5` — `docs: align Phase 5 model-admission authority`
3. `710ebc9e8631bb9b76131ad394b6481eb5fc0125` — `experiments: add model-execution admission checker`
4. `5951744381fd1d98e4e26f8e6a147a32ea8577ce` — `tests: replay model-execution admission lineage`
5. `22f175b1515aa44d9bc993c0e62c40d1a962c427` — `experiments: record current model-execution admission`
6. Durable handoff commit — reported after this file is committed.
7. Separate plan-retirement commit — reported after retirement.

No commit was amended, rebased, squashed, force-pushed, or otherwise rewritten.
The final local/remote SHA, clean-tree state, ahead/behind state, and normal push
result are reported in the owner-facing final response because they occur after
this handoff becomes immutable.

## Frozen compatibility profile

| Field | Frozen value |
| --- | --- |
| Profile ID | `codex-cli-0.147.0-run-03-admission-v0` |
| Profile path | `experiments/substrates/model-execution-qualification-v0/admission/codex-cli-0.147.0-run-03-profile.json` |
| Profile SHA-256 | `ab21119f80141456e7327e276fa3e470abf288cf6a3535ac5fceeace68302033` |
| Checker path | `experiments/substrates/model-execution-qualification-v0/scripts/check_admission.py` |
| Checker SHA-256 | `c1206f234b30b2aff4f2045134b29022c5b4efadaff1f1374385824d5a6e32c0` |
| Execution surface/version | `codex-cli` / `codex-cli 0.147.0` |
| Resolved executable | `C:\Users\wurre\AppData\Roaming\npm\codex.cmd` |
| Provider baseline | `irisx-openai-codex-dual-model-v0` |
| Provider baseline SHA-256 | `a1a85c7464fbc090c2bf2e1682bee9a22957146e50abf11ab5c41f1544046d74` |
| Upstream provider / Codex slot | `openai` / `irisx_openai_no_retry` |
| Model role / ID | `cheaper` / `gpt-5.6-luna` |
| Reasoning effort | `medium` |
| Authentication / billing | `chatgpt` / `chatgpt-subscription` |
| API-key fallback | prohibited; declared key and endpoint variables removed from a future child |
| HTTP / stream retries | `0 / 0` |
| WebSockets / transport fallback | disabled / disabled |
| Sandbox / approval | `read-only` / `never` |
| Model tool envelope | complete Run 03 disable sequence; no model tools |
| View-image representation | `--disable view_image` |
| Canonical Run 03 command SHA-256 | `459fd1b12d8e1310035192265b306ab5ba6a9094b6ad28314e751fd41607299f` |

Known rejected patterns are configuration under the reserved built-in provider
slot `model_providers.openai.*` and the Codex CLI 0.147.0-incompatible strict
configuration field `tools.view_image`. Any version, path, provider slot,
baseline hash, model, effort, retry, WebSocket, sandbox, tool envelope, API-key
fallback, source hash, or canonical-command drift fails closed as `rejected` or
`unsupported` with an explicit reason.

This is one frozen compatibility profile, not a provider registry, capability
registry, generic compatibility framework, provider SDK, or core admission API.

## Historical replay

All replays read the existing frozen contract, execution identity, preflight
observation, and immutable `attempt-start.json`. They neither use historical
outcome labels nor inspect the prior model result to decide admission.

| Run | Frozen attempt-start SHA-256 | Canonical command SHA-256 | Status | Exact reasons | Model calls |
| --- | --- | --- | --- | --- | ---: |
| `qualification-20260905-01` | `633dca513fa1d8ada2cc862b2123913f3c8c4df519056b607db0ab8d85b61de5` | `ca685dc8aee14140e479681d447b30847b3d6a1aafff003f4ff084be8a493a53` | `rejected` | `reserved_provider_configuration_incompatible` | 0 |
| `qualification-20260905-02` | `67f3e085deed532a4e50965503f633b0467dd739467ae7ece2ac7aa8cc55a2bd` | `9e68bf1a591fb5b6c7c0e2139856eddfe324123ac2350474916011311078e655` | `rejected` | `unsupported_config_field:tools.view_image` | 0 |
| `qualification-20260905-03` | `564db52edc7725ef0475c607e95b1360f3cb5d9ec37af5a93ca8c60592f544ea` | `459fd1b12d8e1310035192265b306ab5ba6a9094b6ad28314e751fd41607299f` | `admitted` | none | 0 |

The exact replay commands returned exit `2` for the two intentional rejections
and exit `0` for Run 03 admission. Every record reported provider attempts `0`,
live model calls `0`, and future model execution authorization `false`.

## Current environment admission

The authored record is
`experiments/substrates/model-execution-qualification-v0/admission/results/current-environment.json`
with SHA-256
`7abfa9dc397578516f806bf1841bbc21248fe6a73ba521239c311db040f9b640`.

| Observation | Result |
| --- | --- |
| Admission status | `admitted` |
| Reasons | none |
| Executable | `C:\Users\wurre\AppData\Roaming\npm\codex.cmd` |
| Version | `codex-cli 0.147.0` |
| Provider baseline check | `PASS` |
| Baseline ID/hash | `irisx-openai-codex-dual-model-v0` / `a1a85c7464fbc090c2bf2e1682bee9a22957146e50abf11ab5c41f1544046d74` |
| Bundled local catalog check | `PASS`; `gpt-5.6-luna` with `medium` |
| Provider slot | `irisx_openai_no_retry` |
| ChatGPT auth | locally established by `codex login status` |
| Parent API-key environment | `OPENAI_API_KEY` name present; value not read or persisted |
| Future child sanitation | all declared API-key and endpoint variables removed |
| Retries / WebSockets | `0 / 0`; disabled |
| Tools / sandbox | exact Run 03 disabled-feature sequence; `read-only` |
| Provider attempts / model calls | `0 / 0` |

No secret value appears in the profile, checker output, current record, tests,
or this handoff. The parent environment was not modified. Because local
ChatGPT status, exact CLI version, baseline, and catalog were available without
a model/provider request, no unresolved authentication uncertainty blocked the
current admission. This does not establish general authentication correctness.

## Zero-model-call proof

Batch 5's complete resource ledger is:

```text
provider attempts: 0
model calls: 0
manual retries: 0
automatic retries: 0
routes: 0
fallbacks: 0
escalations: 0
recovery actions: 0
```

Historical replay performs file parsing and hashing only. The current check
uses the existing baseline validator's `codex --version` and
`codex debug models --bundled` observations plus local `codex login status`.
It contains no subprocess path that starts `codex exec`. Unit tests replace the
subprocess runner, assert that the only admission-owned current command is
`login status`, assert no `exec` argument occurs, and confirm the committed
record reports `live_model_calls: 0` and `future_model_execution_authorized:
false`.

No background model process, live Run 03 replay, strict provider reachability
probe, provider prompt, model judge, or new qualification runner was launched.

## Validation

Required focused validation:

- core tests: 28/28 PASS;
- deterministic mutation-path tests: 13/13 PASS;
- deterministic read-only integration tests: 9/9 PASS;
- model-execution qualification and admission tests: 49/49 PASS;
- focused total: **99/99 PASS**.

The model-execution substrate count consists of 20 preserved Batch 4 tests and
29 Batch 5 admission tests. All tests are deterministic and make zero model
calls.

Additional checks:

- repository validation: PASS, 13 sources and 7 paper artifacts, hashes checked;
- accepted provider/model baseline: PASS;
- Codex 0.147.0 bundled catalog: PASS with Luna/medium;
- exact Run 01/02/03 replay: PASS with the statuses and reasons above;
- current-environment record exact-match rerun: PASS;
- immutable Run 01, Run 02, and Run 03 validators: PASS;
- Python compilation and Git whitespace checks: PASS.

The established full inventory covered 17 test directories:

```text
total: 170
passed: 169
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
the preserved historical assertion expects
`9e2ac0aabcae9a89ed92d9145ec787f4d6ee1920b5344be703498c6435aaf76c`.
It was not edited, skipped, suppressed, repaired, or reclassified.

## Preservation proof

The following Git trees are identical at the required baseline and validated
Batch 5 head:

| Material | Baseline/current Git tree |
| --- | --- |
| `sources/` | `10e28d83184c789fc468ca1edc3bebf42ba40b46` |
| `references/papers/` | `ed29ebcde3f01b00a0e49eb33eef1688566dcad3` |
| `research/` | `0d89db5ef0d4712e6068bd499c11a852570633da` |
| all model-qualification `runs/` | `088f939b85392f5df640b69133a913dcd00e1c9a` |
| all frozen model-qualification `definition/` files | `f70469ea77b55dfee12dcd838a9d94d17cc78a22` |

`git diff --name-only 21f0150...HEAD` returned no path under those trees,
`irisx/core`, the accepted provider/model baseline, or either deterministic
Phase 5 input directory. There remain exactly 19 tracked run directories and
847 tracked run files. The model-qualification run set remains exactly Run 01,
Run 02, and Run 03; no Batch 5 run directory exists.

The four deterministic Phase 5 inputs retain their established SHA-256 values:

- mutation contract:
  `d99571c5ed28b79ef5bb9880a078b02545f7e1d51df811934a95e385785266f2`;
- mutation program:
  `30b56206f628174443bd2f7ae27e29530ac60c09ecf6d31b29c553ba5f99f242`;
- read-only contract:
  `359775eba550d889768228886e29acc1778cbb4e242c6bf317887b3e0985e77a`;
- read-only program:
  `8962a8a2478d1664ff4f69b7abc47ef158738b505fb05b59277908004dbae181`.

All prior retired plans and durable handoffs remain unchanged. The only plan
change relative to the required baseline is the new Batch 5 controlling plan,
which must be retired separately after this handoff. No source, paper,
research record, historical definition, identity, output, preflight, run
artifact, or accepted baseline was changed.

No provider-specific code or admission abstraction entered `irisx.core`.

## Research boundary

```text
H-G1: Not evaluated
H-W1: Not evaluated
H-C1: Not evaluated
H-R1: Not evaluated
```

No model comparison, routing, cascade, fallback, escalation, recovery,
persistence framework, workflow engine/search, optimizer, fine-tuning,
training, multi-agent work, architecture search, model judge, external action,
production server/UI/API, provider registry, capability registry, generic
AdmissionGate abstraction, or general provider layer was implemented or
evaluated.

## Closure boundary

After this handoff is committed, retire the controlling TEMP plan in a separate
commit, run final deterministic checks, push `main` normally, confirm a clean
tree and ahead/behind `0/0`, and stop. Do not start Batch 6 and do not execute a
model even though the current environment is admitted.
