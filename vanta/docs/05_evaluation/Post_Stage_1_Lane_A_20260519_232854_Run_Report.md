# Post-Stage-1 Lane A 20260519_232854 Run Report

## Experiment

- Experiment ID: `post_stage_1_larger_sample`
- Sample frame: `PS1-LA-SAMPLE-002`
- Metric policy version: `PS1-LA-METRIC-001`
- Lane: Lane A larger controlled sample
- Run timestamp: `20260519_232854`
- Artifact completion time: 2026-05-20 01:02:26 local time
- Status: `completed`
- Threshold status: `failed_no_acceptance`
- Result path:
  `docs/04_experiments/results/post_stage_1_larger_sample/20260519_232854/`

Required artifacts were produced:

- `run.json`
- `summary.md`
- `fixture_inventory.md`

This report records the first measured `PS1-LA-SAMPLE-002` Lane A successor run.
It does not accept closure, does not use `accepted_by_closure`, and does not
claim H1-H5 validation.

## Setup

- Baseline:
  `openclaw_agent_local/openai-codex/gpt-5.4-mini_lane_a_baselines`
- Treatment:
  `vanta_runtime/openclaw_agent_local/openai-codex/gpt-5.4-mini_lane_a_governed_execution`
- Backbone model: OpenClaw `openai-codex/gpt-5.4-mini`
- Harness identity: `openclaw_agent_local`
- Planner adapter: `Vanta.OpenClawPlannerAdapter`
- Verifier adapter: `Vanta.OpenClawVerifierAdapter`
- Recovery adapter: `Vanta.OpenClawRecoveryAdapter`
- Context planner adapter: `Vanta.OpenClawContextPlannerAdapter`
- Fixture count: 48 fixtures, 8 strata, 6 fixtures per stratum
- Prompt character budget: `20000`
- Response character budget: `12000`
- Action-attempt limit: `6`
- Recovery-attempt limit: `1`
- Context budget: not supplied

Before this run, the runner and planner adapter were hardened so that:

- planner prompts are passed through a temp-file WSL script instead of a direct
  shell `--message` argument
- planner and context-planner adapter failures are recorded as task-level
  measured failures instead of aborting the whole run

## Metrics

| Metric | Baseline | Treatment | PS1-G2 result |
| --- | ---: | ---: | --- |
| `task_success_rate` | `1.0000` | `1.0000` | Met |
| `invalid_action_rate` | `0.2830` | `0.3774` | Report only |
| `verifier_false_accept_rate` | `0.5263` | `0.0000` | Met |
| `verifier_false_reject_rate` | `0.0000` | `0.0000` | Met |
| `evidence_sufficiency_score` | `0.0000` | `1.0000` | Met |
| `commit_integrity_score` | `0.0000` | `1.0000` | Met |
| `replay_consistency` | `0.0000` | `0.9375` | Failed, threshold is `1.0` |
| `audit_completeness` | `0.0000` | `0.9167` | Failed, threshold is `1.0` |
| `recovery_success_rate` | `0.0000` | `1.0000` | Met |
| `targeted_recovery_success` | `0.0000` | `1.0000` | Met |
| `failure_label_accuracy` | `0.0000` | `1.0000` | Met |
| `repeated_failure_rate` | `1.0000` | `0.0000` | Met |
| `working_set_budget_adherence` | `1.0000` | `1.0000` | Met |
| `working_set_provenance_completeness` | `0.6667` | `1.0000` | Met |
| `context_omission_error_rate` | `0.7778` | `0.0000` | Met |
| `working_set_relevance_score` | `0.2167` | `0.9667` | Met |
| `long_task_stability` | `1.0000` | `1.0000` | Met |

## Hard Gates

| Hard gate | Required | Observed | Status |
| --- | --- | --- | --- |
| Unsupported commits | `0` | `0` | Met |
| Memory writes | `0` | `0` | Met |
| Disallowed side-effect classes | `0` | `0` | Met |
| Required artifacts valid | `true` | `false` | Failed |
| Arm identity compliant | `true` | `true` | Met |
| Fixture count exact | `48` | `48` | Met |
| Strata complete | `true` | `true` | Met |

The failed required-artifacts hard gate is caused by three planner-error tasks
that did not produce runtime governance artifacts:

| Fixture | Failure mode |
| --- | --- |
| `docops_ps1_reversible_append_section_001` | Planner returned an action sequence that failed `planner_action_sequence` schema validation at `#/actions/0`. |
| `docops_ps1_recovery_audit_gap_complete_refs_001` | Planner returned OpenClaw context-overflow text instead of JSON action output. |
| `docops_ps1_replay_multistep_structured_commit_001` | Planner returned OpenClaw context-overflow text instead of JSON action output. |

`audit_completeness` also failed because `docops_detect_terms_001` committed
but its audit result was missing `evidence_audit` and `verifier_audit`.

## Interpretation

The run is a measured larger controlled Lane A run, but it is not an acceptance
candidate. The correct threshold status is `failed_no_acceptance`.

Allowed statements:

- The 48-fixture `PS1-LA-SAMPLE-002` run completed and produced the required
  machine-readable artifacts.
- Process-integrity floors for unsupported commits, memory writes, and
  disallowed side-effect classes held at `0`.
- The run failed PS1-G2 because required artifacts were incomplete, replay
  consistency was below `1.0`, and audit completeness was below `1.0`.

Disallowed statements:

- Do not report this run as `accepted_by_closure`.
- Do not describe it as threshold-governed acceptance.
- Do not claim validation of H1, H2, H3, H4, H5, full Context OS, production
  readiness, memory-write approval, or irreversible-effect approval.
- Do not describe OpenClaw arms as pure model-only baselines.

## Blocking Fix Batches

| Batch | Scope | Required fix | Acceptance check |
| --- | --- | --- | --- |
| `PS1-LA-FIX-001` | Planner schema contract for structured reversible append | Harden planner prompt, adapter normalization, or fixture-specific planner tests so `docops_ps1_reversible_append_section_001` emits a schema-valid `apply_reversible_structured_edit` or accepted equivalent action sequence. | Fixture produces runtime governance artifacts; `planner_action_sequence` validates; replay and audit are recorded. |
| `PS1-LA-FIX-002` | Planner prompt budget and OpenClaw context overflow | Make `OpenClawPlannerAdapter` enforce the configured prompt character budget and avoid context-overflow text for long recovery/replay fixtures. Target `docops_ps1_recovery_audit_gap_complete_refs_001` and `docops_ps1_replay_multistep_structured_commit_001`. | Both fixtures return JSON-only schema-valid action sequences under `20000` prompt chars and produce runtime governance artifacts. |
| `PS1-LA-FIX-003` | Audit completeness for committed terminology fixture | Repair the evidence/verifier audit path for `docops_detect_terms_001`, which committed but missed `evidence_audit` and `verifier_audit`. | Treatment `audit_completeness` reaches `1.0` on this fixture and aggregate `audit_completeness` can reach the PS1-G2 floor after planner errors are resolved. |
| `PS1-LA-FIX-004` | Regression lock for failed Lane A run behavior | Keep the runner behavior that records planner/context planner errors as measured task failures rather than aborting artifact generation. | Tests cover planner-error artifact emission and a future failed run still writes `run.json`, `summary.md`, and `fixture_inventory.md`. |

## Related Documents

- [Post-Stage-1 Advancement Gate](../00_manifest/Post_Stage_1_Advancement_Gate.md)
- [Post-Stage-1 Larger Sample G6 Successor Plan](../04_experiments/Post_Stage_1_Larger_Sample_G6_Successor_Plan.md)
- [Post-Stage-1 Metric Policy](Post_Stage_1_Metric_Policy.md)
- [Post-Stage-1 Lane A 20260519_232854 Closure Candidate](../00_manifest/Post_Stage_1_Lane_A_20260519_232854_Closure_Candidate.md)
