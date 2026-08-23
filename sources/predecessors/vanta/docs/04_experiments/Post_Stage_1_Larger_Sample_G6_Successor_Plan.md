# Post-Stage-1 Larger Sample G6 Successor Plan

## Purpose

Define the execution-ready successor sample frame for the first Lane A
post-Stage-1 larger controlled Document Ops run after `PS1-G6` structured edit
implementation.

This document keeps the accepted 48-fixture, 8-stratum shape from
[Post-Stage-1 Larger Sample Plan](Post_Stage_1_Larger_Sample_Plan.md), but
explicitly routes G6 structured-edit fixtures into the behavioral strata used by
the Lane A runner.

It does not report measured results, accept a closure, validate H1 through H5,
authorize full Context OS, authorize memory writes, authorize irreversible
effects, or promote OpenClaw local harness runs to pure model-only baselines.

## Status

Plan ID: `PS1-LA-SAMPLE-002`.

Status: `Execution successor to PS1-LA-SAMPLE-001 for G6-aware Lane A runs`.

Run status: Measured runs exist. The latest documented full selector-repair run
is `20260601_113121` with runner threshold status
`pass_acceptance_candidate`. The corresponding manifest closure accepts that
run as `accepted_by_closure` for the named Lane A Document Ops sample. It does
not validate H1-H5 or broaden runtime scope.

Runner: `Vanta.PostStage1LargerSample`.

Default command:

```text
mix vanta.post_stage_1_larger_sample
```

Required output path:

```text
docs/04_experiments/results/post_stage_1_larger_sample/<timestamp>/
```

Required artifacts:

- `run.json`
- `summary.md`
- `fixture_inventory.md`

## Sample Frame

The execution frame contains exactly 48 fixture-local Document Ops fixtures:
8 strata with 6 fixtures each.

| Stratum | Fixture IDs |
| --- | --- |
| Traceability extraction | `docops_read_traceability_001`, `docops_struct_inspect_001`, `docops_ps1_traceability_multisource_001`, `docops_ps1_traceability_cross_doc_refs_001`, `docops_ps1_traceability_missing_target_001`, `docops_ps1_traceability_structured_outline_001` |
| Terminology consistency | `docops_detect_terms_001`, `docops_struct_contract_pass_001`, `docops_struct_contract_fail_001`, `docops_ps1_terms_alias_conflict_001`, `docops_ps1_terms_clean_canonical_001`, `docops_ps1_terms_contract_inline_001` |
| Simulated patch and diff | `docops_simulate_patch_001`, `docops_multistep_commit_001`, `docops_struct_simulate_md_001`, `docops_struct_simulate_json_001`, `docops_struct_insert_before_001`, `docops_struct_insert_after_001` |
| Reversible edit and commit | `docops_reversible_edit_001`, `docops_struct_apply_reversible_001`, `docops_ps1_reversible_append_section_001`, `docops_ps1_reversible_replace_heading_001`, `docops_ps1_reversible_json_path_replace_001`, `docops_ps1_reversible_patch_multiline_001` |
| Invalid action and path guard | `docops_action_not_allowed_001`, `docops_path_escape_001`, `docops_struct_path_escape_001`, `docops_struct_selector_missing_001`, `docops_struct_selector_ambiguous_001`, `docops_ps1_invalid_reversible_in_readonly_001` |
| Evidence and verifier challenge | `docops_wrong_diff_001`, `docops_struct_wrong_diff_001`, `docops_struct_simulation_mutation_001`, `docops_struct_missing_backup_metadata_001`, `docops_ps1_wrong_diff_multiline_001`, `docops_ps1_struct_backup_files_dropped_001` |
| Journal, replay, and recovery | `docops_rollback_failure_001`, `docops_audit_gap_001`, `docops_compensable_action_001`, `docops_ps1_recovery_structured_rollback_001`, `docops_ps1_recovery_audit_gap_complete_refs_001`, `docops_ps1_replay_multistep_structured_commit_001` |
| Working-set long context | `docops_ws_evidence_packet_001`, `docops_ws_irrelevant_context_001`, `docops_ws_omission_trap_001`, `docops_ws_recovery_context_001`, `docops_ws_traceability_long_001`, `docops_ps1_ws_structured_edit_context_001` |

## Inclusion Policy

Each included fixture must have:

- schema-valid `task.json` under docs and test fixture roots
- complete `expected/acceptance.json`
- deterministic success and failure criteria
- byte-for-byte synchronized docs and test mirrors
- no external side effect, memory write, irreversible effect, production effect,
  or full Context OS dependency

Structured-edit fixtures are assigned to the behavioral stratum they exercise.
They do not create a ninth stratum.

## Fixed Controls

The runner records these controls in `run.json` and `summary.md` before
interpreting metrics:

- model identity
- OpenClaw local harness identity
- planner, verifier, recovery, and context-planner adapter identities
- allowed action set
- prompt and response character budgets
- action-attempt limit
- recovery-attempt limit
- context budget when supplied
- compute matching rule
- baseline and treatment arm labels

OpenClaw arms remain harness-labeled. This successor plan intentionally does not
add a direct Responses API arm.

## Metric Policy

Threshold decisions are governed by
[Post-Stage-1 Metric Policy](../05_evaluation/Post_Stage_1_Metric_Policy.md)
with `Metric policy version: PS1-LA-METRIC-001`.

Allowed runner threshold statuses:

- `blocked_missing_metric`
- `failed_no_acceptance`
- `pass_acceptance_candidate`

The runner must not emit `accepted_by_closure`; only a later manifest closure
may accept a measured result.

## Non-goals

- No measured result is claimed by this plan.
- No `accepted_by_closure` status is created here.
- No H1-H5 validation claim is allowed.
- No production-readiness claim is allowed.
- No full Context OS claim is allowed.
- No `MEMORY_WRITE`, `COMMITTABLE`, or `IRREVERSIBLE` runtime execution is
  authorized.
- No OpenClaw result may be described as pure model-only.

## Related Documents

- [Post-Stage-1 Larger Sample Plan](Post_Stage_1_Larger_Sample_Plan.md)
- [Post-Stage-1 Metric Policy](../05_evaluation/Post_Stage_1_Metric_Policy.md)
- [Baseline Identity Plan](Baseline_Identity_Plan.md)
- [Post-Stage-1 Runtime Scope Proposal](../00_manifest/Post_Stage_1_Runtime_Scope_Proposal.md)
- [Post-Stage-1 Advancement Gate](../00_manifest/Post_Stage_1_Advancement_Gate.md)
- [Post-Stage-1 Lane A 20260525_223239 Run Report](../05_evaluation/Post_Stage_1_Lane_A_20260525_223239_Run_Report.md)
- [Post-Stage-1 Lane A 20260525_223239 Closure Candidate](../00_manifest/Post_Stage_1_Lane_A_20260525_223239_Closure_Candidate.md)
- [Post-Stage-1 Lane A 20260530_141649 Run Report](../05_evaluation/Post_Stage_1_Lane_A_20260530_141649_Run_Report.md)
- [Post-Stage-1 Lane A 20260530_141649 Closure Candidate](../00_manifest/Post_Stage_1_Lane_A_20260530_141649_Closure_Candidate.md)
- [Post-Stage-1 Lane A 20260601_113121 Run Report](../05_evaluation/Post_Stage_1_Lane_A_20260601_113121_Run_Report.md)
- [Post-Stage-1 Lane A 20260601_113121 Closure](../00_manifest/Post_Stage_1_Lane_A_20260601_113121_Closure.md)
