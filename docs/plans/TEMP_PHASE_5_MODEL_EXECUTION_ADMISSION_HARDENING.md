# TEMP Phase 5 — Model Execution Admission Hardening

Status: **Retired — Phase 5 Batch 5 completed and handed off**
Date: **2026-09-05 Asia/Taipei**  
Repository: **Danwuoo/IRIS-X**  
Required baseline `main`: **`21f0150aed8b8555b69dc1094a1c3d7a6441732b`**  
Phase: **Phase 5 — provisional architecture development**  
Batch: **Batch 5**  
Batch goal: **convert the Batch 4 Run 01/02 admission failures and Run 03 success into a deterministic zero-model-call execution-admission check for the currently qualified Codex CLI configuration**  
Architecture authority: **Provisional only; no general provider compatibility or production-runtime claim**  
Live model/provider call ceiling: **0**  
Hard terminal boundary: **STOP after admission hardening, replay validation, durable handoff, retirement, and normal push**

---

## 1. Owner authorization and scope

This plan is the new owner-authorized scope for Phase 5 Batch 5.

Phase 4 remains closed.

Phase 5 Batch 1 through Batch 4 remain complete and retired. Their frozen evidence, plans, handoffs, and run artifacts must not be reopened, overwritten, or strengthened.

Batch 4 ultimately established one successful model-backed qualification for the exact frozen Run 03 configuration:

`qualification-20260905-03`

However, the Batch 4 lineage also contains two preserved admission/configuration failures:

- Run 01: reserved built-in `openai` provider configuration rejection;
- Run 02: Codex CLI 0.147.0 strict-config rejection of unsupported `tools.view_image`;
- Run 03: accepted configuration using the repaired custom provider slot and supported tool-disable form.

The single purpose of Batch 5 is:

> Build the smallest deterministic pre-execution admission mechanism that can identify the known incompatible Run 01 and Run 02 configurations before a model invocation boundary is consumed, while admitting the exact frozen Run 03 configuration under the same observed Codex CLI 0.147.0 environment.

This is an admission-hardening batch.

It is **not** a new model experiment.

It must make **zero provider/model calls**.

---

## 2. Required starting state

Before substantive work:

1. read every applicable `AGENTS.md`;
2. inspect:
   - `git status --short`
   - `git rev-parse HEAD`
   - `git rev-parse origin/main`
   - `git rev-list --left-right --count origin/main...main`
3. verify actual starting `main` is exactly, or is a clean descendant of:
   `21f0150aed8b8555b69dc1094a1c3d7a6441732b`;
4. verify unrelated owner work will not be overwritten;
5. read:
   - `docs/phase-5-model-execution-qualification-handoff.md`
   - `docs/phase-5-model-execution-qualification-repair-handoff.md`
   - `docs/phase-5-model-execution-tool-compatibility-repair-handoff.md`
   - `docs/phase-5-model-execution-qualification-run-03-handoff.md`
   - `docs/plans/TEMP_PHASE_5_MODEL_EXECUTION_QUALIFICATION_RUN_03.md`
   - `docs/decisions/0002-openai-codex-model-baseline.md`
   - `experiments/configurations/provider-model-baseline-v0.json`
   - `tools/model_baseline_check.py`
   - `experiments/substrates/model-execution-qualification-v0/README.md`
   - `experiments/substrates/model-execution-qualification-v0/scripts/run_qualification.py`
   - all three Run 01/02/03 frozen definitions and identities;
6. record the actual starting SHA in this plan's retirement record and the durable Batch 5 handoff.

If baseline or owner state materially conflicts, STOP.

---

## 3. Evidence inherited from Batch 4

Batch 5 must preserve the Batch 4 lineage exactly.

### Run 01

Observed outcome:

- the committed execution attempt crossed its logical invocation boundary;
- Codex CLI rejected local configuration before provider events/model result;
- the reserved built-in provider ID `openai` could not be configured with the frozen retry overrides;
- no retry occurred;
- raw failure remains immutable.

### Run 02

Observed outcome:

- separately owner-authorized corrective attempt;
- custom provider slot avoided the Run 01 reserved-provider problem;
- Codex CLI 0.147.0 rejected `tools.view_image` as an unrecognized strict-config field;
- no provider event/model result;
- no retry;
- raw failure remains immutable.

### Run 03

Observed outcome:

- separately frozen and owner-authorized formal attempt;
- custom provider slot `irisx_openai_no_retry`;
- Codex CLI 0.147.0;
- `gpt-5.6-luna`, medium reasoning;
- ChatGPT authentication;
- API-key fallback absent;
- supported `--disable view_image` form;
- zero retries/routes/fallbacks/escalations/recovery/tools;
- model returned `{"selected_id":"alpha"}`;
- deterministic verification passed;
- canonical adjudication = `verified_success`.

Batch 5 may use these facts only as **known compatibility observations for the exact frozen lineage**.

Do not convert them into a general Codex compatibility claim.

---

## 4. Zero-model-call rule

The entire Batch 5 live provider/model call ceiling is:

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

No command that may begin a model turn is authorized.

In particular:

- do not execute `codex exec` for admission testing;
- do not launch a background model process;
- do not replay Run 03 live;
- do not probe provider output with a trivial prompt;
- do not test authentication by sending a model request.

Allowed local observations include commands that are known not to invoke a model, such as:

- `codex --version`;
- existing repository baseline/catalog checkers that explicitly make zero model calls;
- static file/config parsing;
- local executable path resolution;
- environment-variable presence/sanitization checks that do not contact the provider;
- deterministic unit tests.

If a proposed admission test requires a live model/provider call, it is out of scope.

---

## 5. Scope of the admission checker

Implement the admission checker inside the existing model qualification substrate.

Preferred location:

```text
experiments/substrates/model-execution-qualification-v0/admission/
experiments/substrates/model-execution-qualification-v0/scripts/check_admission.py
```

Do not add provider-specific admission logic to `irisx.core`.

The checker is intentionally scoped to:

```text
execution surface: Codex CLI
observed version family: exact codex-cli 0.147.0
accepted provider baseline: irisx-openai-codex-dual-model-v0
qualified model role: cheaper
qualified model: gpt-5.6-luna
qualified reasoning effort: medium
qualified authentication: ChatGPT
qualified billing: ChatGPT subscription
qualified Run 03 tool/sandbox envelope
```

If the observed CLI version differs from the frozen compatibility profile, return **not admitted / unsupported_version**.

Do not guess compatibility for newer or older versions.

---

## 6. Admission record

Create one small immutable authored admission result schema.

A reasonable shape is:

```json
{
  "schema_version": 1,
  "status": "admitted",
  "reasons": [],
  "execution_surface": "codex-cli",
  "observed_cli_version": "codex-cli 0.147.0",
  "observed_cli_path": "...",
  "provider_baseline_id": "...",
  "provider_baseline_sha256": "...",
  "configuration_identity": "...",
  "command_sha256": "...",
  "compatibility_profile_id": "...",
  "authentication_mode": "chatgpt",
  "api_key_fallback_present": false,
  "live_model_calls": 0
}
```

The exact field names may differ.

The record must distinguish:

- `admitted`;
- `rejected`;
- `unsupported`.

Do not use a single Boolean without reasons.

Admission is only permission for a **future separately authorized run**.

It must not launch that run.

---

## 7. Compatibility profile

Create one frozen compatibility profile for the exact successful Batch 4 environment.

Suggested path:

```text
experiments/substrates/model-execution-qualification-v0/admission/codex-cli-0.147.0-run-03-profile.json
```

The profile should contain only what is needed to distinguish the known lineage:

- exact CLI version string;
- execution surface ID;
- accepted provider baseline ID/hash;
- required custom provider slot ID;
- prohibited reserved built-in provider override pattern;
- qualified model ID;
- qualified reasoning effort;
- required ChatGPT authentication mode;
- API-key fallback prohibited;
- required zero retry settings;
- WebSocket disabled;
- read-only sandbox;
- no model tools;
- accepted view-image disable representation;
- known unsupported `tools.view_image` configuration field;
- expected command/template structural constraints.

Do not encode an exhaustive list of every Codex option.

Do not create a generic provider capability registry.

---

## 8. Deterministic admission checks

At minimum, admission must fail closed on:

1. CLI executable missing;
2. CLI version differs from the frozen supported version;
3. provider baseline missing or hash mismatch;
4. provider/model baseline does not select the qualified Luna/medium configuration;
5. built-in reserved provider `openai` is being overridden in the Run 01-incompatible form;
6. unsupported `tools.view_image` field is present;
7. custom provider slot differs from the frozen qualified slot;
8. retry settings are not explicit zero;
9. WebSocket transport is enabled;
10. tool-enabled envelope differs materially from the Run 03 frozen tool-free envelope;
11. sandbox is broader than read-only;
12. API-key fallback is configured or required;
13. expected ChatGPT auth mode cannot be locally established without a provider call;
14. model differs from `gpt-5.6-luna`;
15. reasoning effort differs from `medium`;
16. command/definition identity is malformed;
17. unknown configuration features materially affect the frozen qualification envelope.

Where local auth state cannot be established without contacting the provider, return `unsupported` or `rejected` rather than making a live call.

Do not mutate user auth configuration.

---

## 9. Command identity

The admission checker must reason about the exact frozen command/configuration, not an informal description.

Create deterministic canonicalization for the proposed qualification command/config.

Record:

- canonical command argument sequence;
- relevant environment/sanitization declaration;
- provider slot/config;
- model;
- reasoning effort;
- sandbox/tool envelope;
- retry settings;
- hash of the canonical admission input.

The Run 03 admission replay must bind to its actual frozen definition rather than a newly handwritten equivalent.

Do not edit Run 03 artifacts.

---

## 10. Replay the three Batch 4 configurations

This is the central Batch 5 acceptance test.

The checker must evaluate frozen historical configuration material without changing it.

### Run 01 replay

Expected:

```text
status: rejected
reason includes: reserved_provider_configuration_incompatible
live model calls: 0
```

### Run 02 replay

Expected:

```text
status: rejected
reason includes: unsupported_config_field:tools.view_image
live model calls: 0
```

### Run 03 replay

Expected:

```text
status: admitted
reasons: no blocking findings
live model calls: 0
```

Do not infer Run 03 admission merely because the historical live run succeeded.

The static checker must independently evaluate its frozen configuration against the compatibility profile.

---

## 11. Fresh-current-environment admission check

In addition to historical replay, evaluate the **current local environment** against the frozen Run 03 profile with zero model calls.

At minimum observe:

- resolved Codex executable path;
- `codex --version`;
- accepted provider/model baseline check;
- local catalog check using existing zero-call repository tooling;
- required model/effort availability;
- environment/API-key sanitation policy;
- frozen compatibility-profile identity.

Write an authored current-environment admission record.

Do not treat it as a run record.

Do not create a model run directory.

If current environment is no longer identical/compatible, record `rejected` or `unsupported`.

Batch 5 can still succeed if the checker correctly rejects current drift.

---

## 12. Authentication handling

Batch 4 demonstrated successful ChatGPT-authenticated execution.

Batch 5 must not assume an API key is acceptable.

Rules:

- ChatGPT is the qualified auth mode;
- API-key fallback remains prohibited;
- do not expose or persist secret values;
- test only presence/classification/sanitization state;
- never write key contents into admission artifacts;
- if API-key variables exist in the parent environment, record only that they are present and must be removed from a future child environment;
- never alter the user's global environment;
- never perform a live authentication/model request.

If local ChatGPT-auth status cannot be checked without provider contact, admission must explicitly represent that uncertainty.

Do not fabricate `authenticated: true`.

---

## 13. Relationship to existing `model_baseline_check.py`

Reuse existing repository checks where they already answer the question.

Do not duplicate:

- provider baseline identity validation;
- baseline schema validation;
- local model catalog validation.

Batch 5 admission logic should compose those existing checks with the new version/config/tool-envelope compatibility profile.

Do not turn `tools/model_baseline_check.py` into a provider-execution framework.

Prefer substrate-local composition.

---

## 14. No core architecture expansion

Preferred outcome: **no `irisx.core` code changes**.

Batch 5 is admission hardening for a provider-specific execution surface, so it should remain outside core.

Only modify core if a genuinely provider-neutral invariant is impossible to represent elsewhere and the change is both minimal and directly justified.

If such a core change appears necessary, STOP and explain before broadening the implementation.

Do not add:

- AdmissionGate protocol;
- provider registry;
- capability registry;
- provider SDK;
- generalized tool registry;
- provider-version abstraction hierarchy.

This batch should remain a small substrate-level hardening.

---

## 15. Required tests

All tests make zero model/provider calls.

At minimum test:

1. exact Run 01 frozen configuration is rejected;
2. Run 01 rejection reason is stable/specific;
3. exact Run 02 frozen configuration is rejected;
4. Run 02 rejection identifies `tools.view_image`;
5. exact Run 03 frozen configuration is admitted;
6. version drift rejects or marks unsupported;
7. provider baseline hash drift rejects;
8. model drift rejects;
9. reasoning-effort drift rejects;
10. retry nonzero rejects;
11. WebSocket enabled rejects;
12. broader sandbox rejects;
13. tool-enabled envelope rejects;
14. API-key fallback configuration rejects;
15. custom provider slot mismatch rejects;
16. canonical command identity is deterministic;
17. historical replay does not modify any run artifact;
18. current-environment check makes zero model calls;
19. admission records do not contain secret values;
20. prior core tests still pass;
21. prior deterministic mutation/read-only tests still pass;
22. Batch 4 model qualification zero-call validation tests still pass.

Do not create a large compatibility framework.

---

## 16. No new run directory

Batch 5 must not create:

```text
experiments/substrates/model-execution-qualification-v0/runs/qualification-...
```

No new model-execution run exists in this batch.

Admission artifacts belong under an authored non-run path such as:

```text
experiments/substrates/model-execution-qualification-v0/admission/results/
```

These are static authored/preflight records, not provider evidence.

Make the distinction explicit.

---

## 17. Known regression debt

Preserve the one known historical Phase 4 frozen-plan hash failure.

Do not edit, skip, suppress, reclassify, or repair it.

Final regression requirement:

```text
zero new failures
zero new errors
```

The same historical failure may remain.

---

## 18. Preservation requirements

Preserve exact:

- `sources/`;
- `references/papers/`;
- `research/`;
- all pre-existing `/runs/`;
- Batch 4 Run 01 directory;
- Batch 4 Run 02 directory;
- Batch 4 Run 03 directory;
- all prior Phase 4/5 retired plans;
- all prior durable handoffs;
- all four frozen deterministic Phase 5 input files;
- all frozen Run 01/02/03 definition/identity/output artifacts;
- accepted provider/model baseline.

Batch 5 may only add new admission-related authored files and make explicitly scoped documentation/test changes.

No history rewrite.

No force-push.

---

## 19. Authority update

The current root `AGENTS.md` still describes the completed Batch 4 corrective continuation.

After this plan is committed, update the Current Objective minimally to:

> Phase 5 provisional architecture development is currently hardening model-execution admission for the exact qualified Codex CLI configuration, using zero-model-call deterministic checks derived from the preserved Batch 4 admission failures and successful Run 03.

State explicitly:

- no new model execution is authorized;
- Batch 5 is admission-only;
- provider-specific admission remains outside core;
- successful Run 03 remains the only qualified model-backed configuration in this lineage.

Do not declare a general provider layer.

---

## 20. Suggested implementation surface

Keep changes concentrated.

Expected new/modified files:

```text
AGENTS.md
docs/plans/TEMP_PHASE_5_MODEL_EXECUTION_ADMISSION_HARDENING.md
docs/phase-5-model-execution-admission-handoff.md

experiments/substrates/model-execution-qualification-v0/README.md
experiments/substrates/model-execution-qualification-v0/admission/codex-cli-0.147.0-run-03-profile.json
experiments/substrates/model-execution-qualification-v0/admission/results/current-environment.json
experiments/substrates/model-execution-qualification-v0/scripts/check_admission.py
experiments/substrates/model-execution-qualification-v0/tests/test_admission.py
```

If replay fixtures can reference existing frozen definitions directly, do not duplicate them.

Avoid modifying `run_qualification.py` unless a small extraction is required to prevent duplicated command canonicalization.

Do not modify any historical run artifact.

---

## 21. Work packages and commits

### WP0 — Activate Batch 5 plan
Suggested commit: `docs: activate Phase 5 model-admission hardening plan`

### WP1 — Align current authority
Suggested commit: `docs: align Phase 5 model-admission authority`

### WP2 — Freeze compatibility profile and checker
Suggested commit: `experiments: add model-execution admission checker`

### WP3 — Replay Batch 4 lineage
Suggested commit: `tests: replay model-execution admission lineage`

### WP4 — Record current-environment admission
Suggested commit: `experiments: record current model-execution admission`

### WP5 — Durable handoff
Create `docs/phase-5-model-execution-admission-handoff.md`.
Suggested commit: `docs: record Phase 5 model-admission handoff`

### WP6 — Retire plan
Suggested commit: `docs: retire Phase 5 model-admission plan`

Then push `main` normally.

No amend/rebase/squash/history rewrite.

---

## 22. Validation

Required zero-call validation includes:

```powershell
python tools\repository_check.py

python tools\model_baseline_check.py
python tools\model_baseline_check.py --check-local-catalog

python experiments\substrates\model-execution-qualification-v0\scripts\check_admission.py --replay-run-01
python experiments\substrates\model-execution-qualification-v0\scripts\check_admission.py --replay-run-02
python experiments\substrates\model-execution-qualification-v0\scripts\check_admission.py --replay-run-03
python experiments\substrates\model-execution-qualification-v0\scripts\check_admission.py --current

python -m unittest discover -s irisx\core\tests -v
python -m unittest discover -s experiments\substrates\minimal-reliable-execution-v0\tests -v
python -m unittest discover -s experiments\substrates\core-execution-integration-v0\tests -v
python -m unittest discover -s experiments\substrates\model-execution-qualification-v0\tests -v

git diff --check
git diff --cached --check
```

Also run the established full test inventory.

Required results:

- no provider/model invocation;
- Run 01 rejected;
- Run 02 rejected;
- Run 03 admitted;
- current environment produces an explicit deterministic admission result;
- all previously passing tests remain passing;
- only the same historical Phase 4 failure may remain;
- zero new failures/errors.

Record exact test counts.

---

## 23. Acceptance criteria

Batch 5 passes only if all are true:

1. one narrow provider-specific admission checker exists outside `irisx.core`;
2. zero live provider/model calls occur;
3. exact Run 01 replay rejects before any invocation;
4. exact Run 02 replay rejects before any invocation;
5. exact Run 03 replay admits;
6. Run 01 reason identifies the reserved-provider incompatibility;
7. Run 02 reason identifies the unsupported `tools.view_image` config field;
8. Run 03 admission is based on static frozen configuration, not historical success alone;
9. exact Codex CLI version/path is observed;
10. version drift fails closed;
11. provider baseline identity/hash is checked;
12. Luna/medium identity is checked;
13. zero-retry configuration is checked;
14. WebSocket/tool/sandbox envelope is checked;
15. API-key fallback remains prohibited;
16. secret values never enter admission artifacts;
17. canonical command/config identity is deterministic;
18. current-environment admission record exists;
19. no new model run directory exists;
20. no historical run/definition artifact changed;
21. no provider registry or generalized compatibility framework is added;
22. no `irisx.core` provider-specific coupling is added;
23. all prior deterministic/model qualification tests remain passing;
24. no new full-suite regression failure/error exists;
25. H-G1/H-W1/H-C1/H-R1 remain `Not evaluated`;
26. preservation checks pass;
27. durable handoff exists;
28. plan is retired separately;
29. final working tree is clean;
30. `main` is pushed normally;
31. local/remote ahead-behind is `0/0`.

---

## 24. Allowed conclusion

If all acceptance criteria pass, the strongest allowed conclusion is:

> **Phase 5 Batch 5 complete — the preserved Batch 4 Run 01 and Run 02 admission failures and successful Run 03 configuration are now distinguished by a deterministic zero-model-call admission check for the exact qualified Codex CLI 0.147.0 execution profile.**

This does not establish:

- general Codex compatibility checking;
- compatibility with future Codex versions;
- provider portability;
- general authentication correctness;
- model reliability;
- production admission control;
- final runtime architecture.

---

## 25. Durable handoff requirements

Create `docs/phase-5-model-execution-admission-handoff.md`.

Record:

### Repository
- required baseline;
- actual starting SHA;
- compatibility/checker implementation SHA;
- replay-validation SHA;
- current-environment record SHA;
- handoff SHA;
- retirement SHA;
- final local/remote SHA;
- clean state;
- ahead/behind;
- push result.

### Compatibility profile
- profile ID/path/hash;
- exact supported CLI version;
- provider baseline ID/hash;
- provider slot;
- model/role;
- reasoning effort;
- auth/billing expectations;
- retry/WebSocket/tool/sandbox constraints;
- known rejected patterns.

### Historical replay
For Run 01/02/03, record frozen input identity, admission status, exact reasons, and zero model calls.

### Current environment
Record executable path, version, baseline/catalog result, admission result, uncertainty, and zero-call confirmation.

### Regression and preservation
Record focused test count, full inventory, historical failure status, exact prior-run preservation, no new run directory, and no core provider coupling.

### Research boundary
Explicitly state:

```text
H-G1: Not evaluated
H-W1: Not evaluated
H-C1: Not evaluated
H-R1: Not evaluated
```

---

## 26. Stop conditions

STOP rather than broaden scope if:

- the admission checker requires `codex exec`;
- authentication can only be determined by sending a model request;
- current version differs and supporting it would require new compatibility research;
- a generic provider registry becomes necessary;
- implementing admission requires a broad `irisx.core` API change;
- historical Run 01/02/03 files would need modification;
- admission cannot distinguish Run 01/02/03 without using their historical outcomes as labels instead of evaluating configuration;
- a new regression cannot be resolved within this exact scope;
- preservation fails;
- work would evaluate H-G1/H-W1/H-C1/H-R1.

Do not perform a model call to solve an admission-checking problem.

---

## 27. Hard STOP

After:

- zero-call admission checker is implemented;
- Run 01/02/03 are replayed deterministically;
- current environment is evaluated without a model call;
- focused/full regression validation passes;
- durable handoff is committed;
- plan is retired;
- `main` is pushed normally;
- local/remote are synchronized;

**STOP.**

Do not start Batch 6.

Do not run a model simply because the current environment is admitted.

Any future model execution or Phase 5 Batch 6 requires separate owner authorization.

---

## Retirement record

Phase 5 Batch 5 completed within this plan's exact zero-model-call boundary.
The preserved Run 01 configuration is deterministically rejected for
`reserved_provider_configuration_incompatible`; Run 02 is rejected for
`unsupported_config_field:tools.view_image`; and Run 03 is admitted under the
exact frozen `codex-cli-0.147.0-run-03-admission-v0` profile. The current local
environment is also admitted by zero-call checks. Admission authorizes no model
execution.

- required and actual starting SHA:
  `21f0150aed8b8555b69dc1094a1c3d7a6441732b`;
- plan activation:
  `da744ee59d76cf5c610a160d1af11c4241d4ee1e`;
- authority alignment:
  `b2443365a32e3d4b2ca7bd272dda407e525f5ba5`;
- compatibility profile and checker:
  `710ebc9e8631bb9b76131ad394b6481eb5fc0125`;
- historical replay tests:
  `5951744381fd1d98e4e26f8e6a147a32ea8577ce`;
- current-environment admission record:
  `22f175b1515aa44d9bc993c0e62c40d1a962c427`;
- durable handoff:
  `a0a7ebc86cc403f04287cea8266425c52cd46476`;
- focused validation: 99/99 PASS;
- full inventory: 170 total, 169 passed, the same one historical Phase 4
  frozen-plan hash failure, 0 errors, 0 skips, and 0 new failures/errors;
- provider attempts/model calls: `0/0`;
- no new run directory and no `irisx.core` change;
- retirement commit and final local/remote synchronization: reported in the
  owner-facing final response because they occur after this record is written.

The durable result is
`docs/phase-5-model-execution-admission-handoff.md`. Batch 5 is closed. H-G1,
H-W1, H-C1, and H-R1 remain `Not evaluated`. Do not start Batch 6 and do not
run a model without new owner authorization.
