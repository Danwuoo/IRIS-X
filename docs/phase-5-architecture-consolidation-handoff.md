# Phase 5 Architecture Consolidation Handoff

- **Status:** durable Phase 5 closure handoff
- **Date:** 2026-09-06
- **Batch:** Phase 5 Batch 7 — Architecture Consolidation and Capability Trigger Review
- **Required and observed starting baseline:** `979c443ece39b5631ac8afddabb25229aea958a8`
- **Decision:** **Decision A — Close Phase 5**
- **Model/provider calls authorized and performed:** `0` / `0`

## 1. Outcome

Phase 5 Batch 7 consolidated the Phase 5 Batch 1–6 evidence into an explicit
provisional architecture state and reviewed every deferred capability trigger.
No reviewed capability is evidence-triggered. The supported boundaries are now
explicit enough to close Phase 5 without inventing a Batch 8 experiment.

This decision does not declare a final architecture, stable SDK, production
runtime, provider-portable execution layer, general reliability result, or
final product boundary. It closes the current provisional-architecture phase at
the exact observed scopes recorded in the evidence.

No model task, next experiment, Batch 8, or Phase 6 was started.

## 2. Authority and scope

The owner-supplied controlling plan was activated unchanged from the initial
working tree as
`docs/plans/TEMP_PHASE_5_ARCHITECTURE_CONSOLIDATION_AND_TRIGGER_REVIEW.md`.
The repository root authority was then aligned to Batch 7 before synthesis.

Batch 7 remained a research and governance batch:

- no core, adapter, runner, admission-checker, experiment, or source code was
  changed;
- no model/provider execution was allowed or performed;
- no deferred runtime mechanism was implemented;
- supported evidence was separated from provisional Python representation;
- capability research status was kept separate from capability-trigger status.

The controlling-plan retirement commit necessarily follows this handoff commit.
Its full SHA and the final synchronized repository SHA are reported in the
owner-facing final report.

## 3. Batch 7 commit chain before this handoff

| Purpose | Commit |
| --- | --- |
| Activate owner-supplied Batch 7 plan | `aba95f35c5c3f0154c690e97babc3e9f751054aa` |
| Align root authority to active Batch 7 and zero-call scope | `ecd247e06440ff829829fd96b12e7aecfc429ec9` |
| Consolidate Phase 5 architecture evidence | `f66b188aa7673776f3fb39a719853f2e7df80b61` |
| Review deferred capability triggers | `627dfbf8dc4bc95aae8ddc2598b806e09109af81` |
| Record provisional architecture state and Decision A | `3d3a05fbc4207a6154796c071d5fa25246a4328a` |
| Finalize root Phase 5 closure wording | `e7f4f42b7d4a0e25df462a4f0092217c50eca6f1` |

The starting baseline is an ancestor of every Batch 7 commit. No amend, rebase,
squash, force push, or history rewrite was used.

## 4. Exact evidence set reviewed

### 4.1 Applicable authority and research discipline

- `AGENTS.md`
- `research/AGENTS.md`
- `experiments/AGENTS.md`
- `sources/AGENTS.md`
- `research/README.md`
- `research/problem-definition.md`
- `docs/plans/TEMP_PHASE_5_ARCHITECTURE_CONSOLIDATION_AND_TRIGGER_REVIEW.md`

### 4.2 Post-Phase-4 synthesis and Phase 4 closure/evidence

- `research/post-phase-4-architecture-synthesis.md`
- `docs/post-phase-4-architecture-synthesis-handoff.md`
- `research/phase-4-closure.md`
- `docs/phase-4-closure-validation.md`
- `research/phase-4-mechanism-experiment-results.md`
- `research/phase-4-evidence-interception-results.md`
- `research/phase-4-reliability-specialization-readiness.md`

Direct cited Phase 3/4 result, manifest, selection, and resource records were
also checked at:

- `experiments/exp-2026-08-28-docops-readonly-baseline/runs/pilot-20260828-local-rerun-01/interpretation.md`
- `experiments/exp-2026-08-28-docops-readonly-baseline/runs/pilot-20260828-local-rerun-01/results.json`
- `experiments/exp-2026-08-28-docops-readonly-baseline/runs/pilot-20260828-local-rerun-01/run-manifest.json`
- `experiments/exp-2026-09-01-luna-structured-program-specialization/design/design-20260902-chatgpt-03/design-ledger.json`
- `experiments/exp-2026-09-01-luna-structured-program-specialization/design/design-20260902-chatgpt-03/run-manifest.json`
- `experiments/exp-2026-09-01-luna-structured-program-specialization/design/design-20260902-chatgpt-03/selection-reconstruction.json`
- `experiments/exp-2026-09-01-luna-structured-program-specialization/design/design-20260902-chatgpt-03/validation-output-freeze.json`
- `experiments/exp-2026-09-01-luna-structured-program-specialization/runs/blind-20260902-chatgpt-03/completion-manifest.json`
- `experiments/exp-2026-09-01-luna-structured-program-specialization/runs/blind-20260902-chatgpt-03/results.json`
- `experiments/exp-2026-09-01-luna-structured-program-specialization/runs/blind-20260902-chatgpt-03/reviewed-interpretation.md`
- `experiments/exp-2026-09-01-luna-structured-program-specialization/runs/blind-20260902-chatgpt-03/run-manifest.json`
- `experiments/exp-2026-09-01-luna-structured-program-specialization/runs/blind-20260902-chatgpt-03/runtime-ledger.json`

The reviewed result remains `Supported — task-local`; provider cost and full
lifecycle economics remain `Unknown` or `Not established` as recorded. It does
not support a general specialization, routing, or escalation result.

### 4.3 Every Phase 5 Batch 1–6 durable handoff

- `docs/phase-5-core-interfaces-handoff.md`
- `docs/phase-5-contract-bound-evidence-handoff.md`
- `docs/phase-5-terminal-semantic-integrity-handoff.md`
- `docs/phase-5-model-execution-qualification-handoff.md`
- `docs/phase-5-model-execution-qualification-repair-handoff.md`
- `docs/phase-5-model-execution-tool-compatibility-repair-handoff.md`
- `docs/phase-5-model-execution-qualification-run-03-handoff.md`
- `docs/phase-5-model-execution-admission-handoff.md`
- `docs/phase-5-model-task-family-qualification-handoff.md`

### 4.4 Every retired Phase 5 Batch 1–6 controlling plan

- `docs/plans/TEMP_PHASE_5_CORE_INTERFACES_AND_DUAL_PATH.md`
- `docs/plans/TEMP_PHASE_5_CONTRACT_BOUND_EVIDENCE.md`
- `docs/plans/TEMP_PHASE_5_TERMINAL_SEMANTIC_INTEGRITY.md`
- `docs/plans/TEMP_PHASE_5_MODEL_EXECUTION_QUALIFICATION.md`
- `docs/plans/TEMP_PHASE_5_MODEL_EXECUTION_QUALIFICATION_REPAIR.md`
- `docs/plans/TEMP_PHASE_5_MODEL_EXECUTION_TOOL_COMPATIBILITY_REPAIR.md`
- `docs/plans/TEMP_PHASE_5_MODEL_EXECUTION_QUALIFICATION_RUN_03.md`
- `docs/plans/TEMP_PHASE_5_MODEL_EXECUTION_ADMISSION_HARDENING.md`
- `docs/plans/TEMP_PHASE_5_MODEL_TASK_FAMILY_QUALIFICATION.md`

### 4.5 Current provisional core

- `irisx/core/records.py`
- `irisx/core/interfaces.py`
- `irisx/core/execution.py`

### 4.6 Batch 4 terminal evidence and Batch 5 admission

- `experiments/substrates/model-execution-qualification-v0/runs/qualification-20260905-01/terminal-record.json`
- `experiments/substrates/model-execution-qualification-v0/runs/qualification-20260905-02/terminal-record.json`
- `experiments/substrates/model-execution-qualification-v0/runs/qualification-20260905-03/terminal-record.json`
- `experiments/substrates/model-execution-qualification-v0/admission/codex-cli-0.147.0-run-03-profile.json`
- `experiments/substrates/model-execution-qualification-v0/scripts/check_admission.py`
- `experiments/substrates/model-execution-qualification-v0/admission/results/current-environment.json`

The first two Batch 4 terminal records preserve deterministic executor failure
with one call and no retry, route, escalation, or recovery. Run 03 preserves the
single verified success. Batch 5 records the exact-version, fail-closed
admission response to the known configuration failure mode.

### 4.7 Batch 6 admission, summary, and all terminal records

- `experiments/substrates/model-execution-qualification-v0/task-family/admission/current-environment-20260906.json`
- `experiments/substrates/model-execution-qualification-v0/task-family/summaries/batch-6-summary.json`
- `experiments/substrates/model-execution-qualification-v0/task-family/runs/task-family-20260906-a-filter/terminal-record.json`
- `experiments/substrates/model-execution-qualification-v0/task-family/runs/task-family-20260906-b-aggregation/terminal-record.json`
- `experiments/substrates/model-execution-qualification-v0/task-family/runs/task-family-20260906-c-ranking/terminal-record.json`

These records preserve three separately frozen, read-only, single-call,
deterministically verified successes under one admitted Luna allocation, with
zero retry, route, fallback, escalation, or recovery action.

## 5. Phase 5 Batch 1–6 evidence chain

| Batch | Starting baseline | Validated/evidence SHA(s) | Durable handoff | Lifecycle final | Exact retained contribution |
| --- | --- | --- | --- | --- | --- |
| 1 | `59367c3c50a9e089bdc476cc490c3dc9111edf07` | `6364f252877aca18602c19bdcf0d7631d109c4c7` | `961bdd10999a76bbc30652ac438c76a19e64cfc3` | `1ccc6505c0c1e2d418fcc09c36b2e1a330d47ac0` | Minimal provisional core plus one mutation and one read-only path; no final architecture. |
| 2 | `1ccc6505c0c1e2d418fcc09c36b2e1a330d47ac0` | `a6d61056e442ac0256130279d9c9ba0bceca796e` | `5b1ca2822addfbd5298e754c993042461d385112` | `954b95d0126ac057789d1eee5584ec7bef391614` | Evidence bindings made task/contract/execution context explicit; representation remained provisional. |
| 3 | `954b95d0126ac057789d1eee5584ec7bef391614` | `fd3b179ec7515f435f941b18055077f1ad8a6c81` | `30c5e75fb83e0b0c4efd7b17ff63f7d27c6a312d` | `0d738fec43bafc72b5f6ca0f1ca39a6426b0b751` | Terminal semantics fail closed across malformed, executor-failure, and evidence states; no general recovery result. |
| 4 | `0d738fec43bafc72b5f6ca0f1ca39a6426b0b751` | Failures `d85320d57007677be747924426270feb79cc92e2`, `39f7d2c2344bfd701e30e165d5f30bf913aa07e7`; tool fix `663fdcdffa73305496107a3ed0b86d32f9b90616`; freeze `47d9173fa929119377fdf01034c399792bdde8ba`; successful evidence `ccfa44fc255357ba42c8f4ebbd22deda475055e6` | Final Run 03 handoff `7c6b93e20593a506b4eb211a425aa31dc06b04da` plus preserved failed-attempt handoffs | `21f0150aed8b8555b69dc1094a1c3d7a6441732b` | One exact model-backed read-only qualification succeeded after preserving two configuration/tool failures; no portability, retry, or recovery conclusion. |
| 5 | `21f0150aed8b8555b69dc1094a1c3d7a6441732b` | `22f175b1515aa44d9bc993c0e62c40d1a962c427` | `a0a7ebc86cc403f04287cea8266425c52cd46476` | `cd2b3f60a802a3f0438dc38792fd58b45bde820e` | Exact Codex CLI 0.147.0 fail-closed admission profile/checker; no provider execution. |
| 6 | `cd2b3f60a802a3f0438dc38792fd58b45bde820e` | Freeze `2320858ba1f5dc5d7c68ba426278106c565ac6b4`; tasks `9ef207b922c0b4dcb5fce61dce984bb0dfe02a22`, `83782d34529b8d9ec2febed24d7899e696a91f44`, `cf52d4c1b2ad3ab3f01379ff25987977f9cabe81`; summary `81c2d48bc0c8b7390a464e7bd063666b63103342` | `b610dfd047b4cffeafdaca5ccbf2c2ee1cbb45c3` | `979c443ece39b5631ac8afddabb25229aea958a8` | 3/3 task-local verified successes with one adapter/configuration and isolated identity, evidence, program, schema, and verifier bindings; no routing or cross-provider result. |

No historical conclusion was strengthened during consolidation.

## 6. Authored Batch 7 records

- `research/phase-5-architecture-consolidation.md` contains the full support
  matrix, evidence chain, falsifiers, and evidence-versus-substrate split.
- `research/phase-5-capability-trigger-review.md` contains the trigger-by-trigger
  review and Decision A.
- `docs/phase-5-architecture-state.md` is the concise current provisional
  architecture authority.
- `AGENTS.md` now records Phase 5 closure, zero current model authorization, and
  the owner-directed future two-turn model procedure.
- This file is the durable Batch 7 handoff.

## 7. Provisional architecture support matrix summary

### Supported within observed scope

- immutable program identity;
- contract/execution identity binding;
- contract-bound evidence;
- producer/verifier separation;
- deterministic independent verification;
- canonical adjudication;
- task-specific verifier authority;
- replaceable executor adapter;
- truthful resource accounting, including literal `Unknown` values;
- admission before model execution;
- exact-version provider admission for the admitted Codex CLI 0.147.0 profile;
- read-only model execution;
- cross-task adapter reuse;
- cross-task identity, evidence, program, schema, and verifier isolation;
- structured observations;
- policy-before-mutation for the observed mutation slice.

Each item is supported only within its recorded task, fixture, mutation,
provider-profile, and verifier scope.

### Provisional implementation choice

- provider-specific code outside `irisx/core`.

Keeping provider integration out of core is the current clean boundary and is
consistent with the evidence, but the corpus has not compared alternative
module/package layouts. The layout itself is therefore not an empirical
architecture requirement.

### Not evaluated

- general recovery;
- runtime persistence;
- nondeterministic verification or model judging;
- routing;
- escalation/cascades;
- automated specialization;
- workflow search;
- external or irreversible actions.

Provider portability and broader compatibility remain `Unclear`. No matrix row
requires `Conflicting evidence`; observed results are bounded but compatible.

## 8. Evidence-backed invariants versus provisional substrate

The supported architecture claim is about boundaries, not the current Python
vocabulary. In particular:

| Evidence-backed invariant | Current provisional realization; not promoted to a final requirement |
| --- | --- |
| Program bytes are frozen and bound to execution. | `ProgramIdentity`, SHA-256 fields, and local file paths. |
| Evidence identifies the task, contract, execution, artifact role, and frozen content. | Python dataclasses serialized to the current JSON shape. |
| Producer claims do not decide semantic validity. | Separate executor and verifier protocols plus canonical Python adjudication. |
| Mutation is preceded by an explicit policy decision. | In-memory records and the current mutation adapter/test fixture. |
| Model execution is refused unless the frozen profile admits the environment. | A JSON profile, local checker script, and local admission record. |
| Resource facts remain truthful when unavailable. | Current ledger field names and literal string value `Unknown`. |
| Task families do not share semantic authority merely because they reuse an adapter. | Three local schemas/programs/verifiers and local run directories. |

Dataclasses, protocols, JSON field names, SHA-256 as the eventual algorithm,
local filesystem layout, in-memory state, and exact terminology remain
replaceable provisional substrate unless later evidence constrains them.

## 9. Deferred capability trigger decisions

Capability research status remains separate from trigger status.

| Capability | Trigger status | Research status | Experiment now? | Reason retained |
| --- | --- | --- | --- | --- |
| H-G1 automated specialization | `Not triggered` | `Not evaluated` | No | Multiple frozen task programs and an earlier manually governed task-local specialization result do not show repeated design demand or a design-time bottleneck. |
| H-W1 workflow mechanisms/search | `Not triggered` | `Not evaluated` | No | The observed paths are bounded single-stage executions; multiple task definitions are not workflow-search evidence. |
| H-C1 cascade/escalation | `Not triggered` | `Not evaluated` | No | Batch 6 achieved 3/3 with one admitted Luna allocation and no observed insufficiency event; Terra's existence is not a trigger. |
| H-R1 routing/allocation | `Not triggered` | `Not evaluated` | No | Semantically heterogeneous tasks succeeded under the same fixed allocation; no allocation frontier or differentiated need was observed. |
| Persistence | `Not triggered` | `Not evaluated` | No | Durable Git evidence is research provenance, not evidence that runtime persistence is needed. |
| Nondeterministic verifier/model judge | `Not triggered` | `Not evaluated` | No | The qualified task families have deterministic authoritative oracles; a model judge would weaken the observed authority boundary without identified need. |
| External action/interception | `Not triggered` | General external/irreversible action `Not evaluated`; local H-I1a remains task-local | No | Local reversible mutation evidence does not establish current need or safety for external/irreversible effects. |
| Recovery/retry | `Not triggered` | General recovery `Not evaluated`; local H-RCV1a remains task-local | No | Batch 4 failures were configuration/tool-compatibility failures addressed by exact admission. Batch 5/6 provide no repeated task-level failure that warrants retry or recovery. |

Evidence that could change these decisions is recorded explicitly in
`research/phase-5-capability-trigger-review.md`. No trigger crossed its defined
threshold in the current evidence.

## 10. Decision

**Decision A — Close Phase 5.**

No additional mechanism is evidence-triggered, and the provisional architecture
state is explicit enough to preserve the supported trust boundaries without
turning implementation choices into final requirements. There is no authorized
next experiment.

## 11. Deterministic validation

### Focused suites

| Check | Result |
| --- | ---: |
| `python tools\repository_check.py` | PASS — 13 sources, 7 artifacts, hashes checked |
| `python -m unittest discover -s irisx\core\tests -v` | 28/28 PASS |
| `python -m unittest discover -s experiments\substrates\minimal-reliable-execution-v0\tests -v` | 13/13 PASS |
| `python -m unittest discover -s experiments\substrates\core-execution-integration-v0\tests -v` | 9/9 PASS |
| `python -m unittest discover -s experiments\substrates\model-execution-qualification-v0\tests -v` | 75/75 PASS |

Focused total: **125/125 passed**.

The model-qualification tests are deterministic/mocked contract tests; the live
runner and admission-refresh path were not invoked.

### Full discovered inventory

The inventory covered `irisx/core/tests` and all 16 discovered
`experiments/**/tests` directories:

- **196 tests run**;
- **195 passed**;
- **1 failed**;
- **0 errors**;
- **0 skipped**.

The sole failure is the required unchanged historical Phase 4 frozen-plan hash
failure:

- test:
  `HPIaContractTests.test_frozen_artifact_hashes_match_exact_bytes`;
- file:
  `docs/plans/TEMP_PHASE_4_FINAL_MODEL_SPECIALIZATION_AND_CLOSURE.md`;
- expected SHA-256:
  `9e2ac0aabcae9a89ed92d9145ec787f4d6ee1920b5344be703498c6435aaf76c`;
- observed SHA-256:
  `4f3e47a6fa8af63dee6d4397d995a917a216ce70791416909e76a5448697246b`.

It was not modified, regenerated, suppressed, or rebaselined. Batch 7 introduced
zero new failures or errors.

## 12. Zero-model-call evidence

Batch 7's execution ledger is:

| Action | Count |
| --- | ---: |
| Model/provider calls | 0 |
| `codex exec` invocations | 0 |
| Background model processes launched | 0 |
| Provider prompts submitted | 0 |
| Model judges invoked | 0 |
| Retries, routes, fallbacks, escalations, or recovery actions | 0 |

Evidence for the zero-call boundary:

- commands were limited to Git/static inspection, deterministic repository
  checks, and local unit tests;
- neither the model runner nor the admission-refresh/live-preflight path was
  invoked;
- the model qualification/task-family run trees are byte-identical to baseline;
- the tracked run inventory remained 22 run instances and 871 files with
  manifest SHA-256
  `2263bb7c26b93f5dd4cfb46857c36628bcb29b57ad2c2343d490746c2334f6b5`.

## 13. Preservation proof

The following Git tree identities at baseline and after authored Batch 7 work
were identical:

| Preserved area | Git tree object |
| --- | --- |
| `sources/` | `10e28d83184c789fc468ca1edc3bebf42ba40b46` |
| `references/papers/` | `ed29ebcde3f01b00a0e49eb33eef1688566dcad3` |
| `irisx/core/` | `773856fec635535f28c5df37c19bc7914f3a3f64` |
| `experiments/configurations/` | `0233d57b11d0c2940a2d9b5c78f23171f1452b7c` |
| Model qualification definition | `f70469ea77b55dfee12dcd838a9d94d17cc78a22` |
| Model qualification admission | `c200f262241f8c16ac61beb4cff00479d99a8bf9` |
| Historical qualification runs | `088f939b85392f5df640b69133a913dcd00e1c9a` |
| Entire Batch 6 task-family tree | `15298fa5aac5dde2be093db4f9f748a473a75930` |
| Batch 6 task-family runs | `ddb49359a5bff21292f39604c9b298a35fc56cdb` |

The pre-Batch-7 `research/` tree identity was
`0d89db5ef0d4712e6068bd499c11a852570633da`; its only Batch 7 changes are the
two required additive research records. All earlier research files are
unchanged.

Additional preservation checks found:

- zero changes under `sources/`, `references/papers/`, `irisx/core/`,
  `experiments/configurations/`, or the model-execution qualification substrate;
- zero changes to historical Phase 5 Batch 1–6 plans;
- zero changes to historical handoffs;
- zero changes to historical run paths;
- zero changes to the preserved Phase 4 plan with the known hash mismatch;
- no deletions of sources, papers, research records, plans, handoffs, task
  definitions, admission records, or run evidence.

The only Batch 7 authored paths are:

- modified: `AGENTS.md`;
- added: `research/phase-5-architecture-consolidation.md`;
- added: `research/phase-5-capability-trigger-review.md`;
- added: `docs/phase-5-architecture-state.md`;
- added: `docs/phase-5-architecture-consolidation-handoff.md`;
- added, then retired in place: the Batch 7 controlling TEMP plan.

## 14. Root authority and future model-run governance

`AGENTS.md` now records Phase 5 as closed by Decision A and authorizes no next
experiment or model execution.

It also records the owner's future two-turn procedure:

1. A launch turn freezes and commits definition/code, passes deterministic
   admission/preflight, verifies a clean tree, launches a background model
   process with stdout/stderr outside the repository, records PID/timestamp/
   freeze SHA/log paths, performs exactly one immediate confirmation, and
   stops without polling or inspecting results—even if the process already
   exited.
2. Only a later explicit owner collection turn may inspect completion/output,
   preserve raw artifacts, adjudicate, and commit evidence.

This is explicitly an **owner-directed development procedure**. It is not
evidence for a reliability architecture, persistence mechanism, workflow
engine, recovery mechanism, or research result.

## 15. Handoff boundary

Phase 5 is closed within the evidence bounds above. Work must stop after the
controlling plan is retired, `main` is pushed normally, and clean synchronized
state is confirmed. No new task, experiment, model call, Batch 8, or Phase 6 is
authorized by this handoff.
