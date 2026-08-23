# Fixtures Catalog

Catalog version: 5.0.

This catalog lists the 48 fixture-local Document Ops fixtures used by
`PS1-LA-SAMPLE-002`. It is a navigation and inventory document only. It does
not move fixtures, report measured results, create `accepted_by_closure`, or
validate H1 through H5.

Fixture roots remain:

```text
docs/04_experiments/fixtures/document_ops/
test/fixtures/document_ops/
```

The docs and test roots are expected to remain byte-for-byte synchronized.
Fixture order follows
[Post-Stage-1 Larger Sample G6 Successor Plan](../Post_Stage_1_Larger_Sample_G6_Successor_Plan.md).
The latest accepted Lane A run inventory records the same 48 fixtures under
`docs/04_experiments/results/post_stage_1_larger_sample/20260601_113121/`.

## Strata

| Stratum | Count | Primary purpose |
| --- | ---: | --- |
| Traceability extraction | 6 | Read fixture-local sources and extract explicit traceability references without mutation. |
| Terminology consistency | 6 | Detect or confirm canonical terminology and document-contract consistency. |
| Simulated patch and diff | 6 | Produce candidate patches, diffs, or structured-edit simulations without mutating source artifacts. |
| Reversible edit and commit | 6 | Exercise reversible fixture-local edits with commit, diff, and rollback metadata expectations. |
| Invalid action and path guard | 6 | Reject unsupported actions, path escapes, selector failures, or disallowed side-effect use. |
| Evidence and verifier challenge | 6 | Pressure evidence sufficiency, verifier rejection, diff correctness, and backup metadata checks. |
| Journal, replay, and recovery | 6 | Exercise rollback failure, audit gaps, compensation records, replay, and targeted recovery paths. |
| Working-set long context | 6 | Exercise `Working Set Compiler v0` selection under bounded context with required, relevant, and irrelevant refs. |

Total: 48 fixtures.

## Separate PS1-G8 Planning Fixtures

The evaluation-only planning fixtures for the named
`committable_docops_planning_pilot` live under
`docs/04_experiments/fixtures/side_effect_planning/`. They are not part of the
48-fixture Lane A sample, are not runtime `benchmark_task` fixtures, and do not
have an executable `test/fixtures/` mirror. The planning runner treats that root
as immutable and records pre-run and post-run tree hashes.

## Fixture Catalog

| Stratum | Phase / Gate | Fixture ID | Purpose |
| --- | --- | --- | --- |
| Traceability extraction | Phase 1 minimal loop | `docops_read_traceability_001` | Extract explicit markdown links from one source document without modifying source files. |
| Traceability extraction | Post-Stage-1 G6 structured edit surface | `docops_struct_inspect_001` | Inspect markdown headings and selector targets without mutation. |
| Traceability extraction | Phase 1 minimal loop | `docops_ps1_traceability_multisource_001` | Extract explicit links from a primary source while preserving multi-source read-only behavior. |
| Traceability extraction | Phase 1 minimal loop | `docops_ps1_traceability_cross_doc_refs_001` | Extract ordered cross-document markdown references from a routing note. |
| Traceability extraction | Phase 1 minimal loop | `docops_ps1_traceability_missing_target_001` | Extract a missing-target link without fabricating replacement traceability. |
| Traceability extraction | Post-Stage-1 G6 structured edit surface | `docops_ps1_traceability_structured_outline_001` | Inspect a structured outline and resolve the requested Specs selector without mutation. |
| Terminology consistency | Phase 1 minimal loop | `docops_detect_terms_001` | Detect inconsistent Evidence Packet terminology across two markdown documents. |
| Terminology consistency | Post-Stage-1 G6 structured edit surface | `docops_struct_contract_pass_001` | Validate a markdown source against a fixture-local contract that should pass. |
| Terminology consistency | Post-Stage-1 G6 structured edit surface | `docops_struct_contract_fail_001` | Record expected document-contract failures without treating the observation as verifier failure. |
| Terminology consistency | Phase 1 minimal loop | `docops_ps1_terms_alias_conflict_001` | Detect a terminology alias conflict across two source documents. |
| Terminology consistency | Phase 1 minimal loop | `docops_ps1_terms_clean_canonical_001` | Confirm canonical Evidence Packet terminology is consistent across clean notes. |
| Terminology consistency | Post-Stage-1 G6 structured edit surface | `docops_ps1_terms_contract_inline_001` | Validate an inline terminology contract for required canonical terms. |
| Simulated patch and diff | Phase 1 minimal loop | `docops_simulate_patch_001` | Simulate a controlled markdown wording edit and expected diff without writing source files. |
| Simulated patch and diff | Phase 3 commit/journal/replay | `docops_multistep_commit_001` | Exercise a multi-step simulated commit path with file listing, hashing, patch simulation, and diff computation. |
| Simulated patch and diff | Post-Stage-1 G6 structured edit surface | `docops_struct_simulate_md_001` | Simulate a selector-based markdown structured edit and produce candidate content and diff. |
| Simulated patch and diff | Post-Stage-1 G6 structured edit surface | `docops_struct_simulate_json_001` | Simulate a JSON-path structured replacement without modifying the source file. |
| Simulated patch and diff | Post-Stage-1 G6 structured edit surface | `docops_struct_insert_before_001` | Simulate inserting a structured line before the selected source line. |
| Simulated patch and diff | Post-Stage-1 G6 structured edit surface | `docops_struct_insert_after_001` | Simulate inserting a structured line after the selected source line. |
| Reversible edit and commit | Phase 3 commit/journal/replay | `docops_reversible_edit_001` | Apply and audit a reversible local document edit with backup metadata. |
| Reversible edit and commit | Post-Stage-1 G6 structured edit surface | `docops_struct_apply_reversible_001` | Apply a selector-based reversible markdown edit with fixture backup metadata. |
| Reversible edit and commit | Post-Stage-1 G6 structured edit surface | `docops_ps1_reversible_append_section_001` | Apply a reversible structured insert after the Scope heading. |
| Reversible edit and commit | Post-Stage-1 G6 structured edit surface | `docops_ps1_reversible_replace_heading_001` | Apply a reversible structured heading replacement. |
| Reversible edit and commit | Post-Stage-1 G6 structured edit surface | `docops_ps1_reversible_json_path_replace_001` | Apply a reversible JSON-path structured edit for the controlled domain field. |
| Reversible edit and commit | Phase 3 commit/journal/replay | `docops_ps1_reversible_patch_multiline_001` | Apply a reversible multiline patch with backup metadata and expected diff. |
| Invalid action and path guard | Phase 1 minimal loop | `docops_action_not_allowed_001` | Reject a simulated patch proposal in a read-only fixture before commit. |
| Invalid action and path guard | Phase 1 minimal loop | `docops_path_escape_001` | Reject a read action whose path escapes the fixture workspace. |
| Invalid action and path guard | Post-Stage-1 G6 structured edit surface | `docops_struct_path_escape_001` | Reject a structured inspection action that attempts fixture path escape. |
| Invalid action and path guard | Post-Stage-1 G6 structured edit surface | `docops_struct_selector_missing_001` | Reject a structured edit whose selector does not resolve. |
| Invalid action and path guard | Post-Stage-1 G6 structured edit surface | `docops_struct_selector_ambiguous_001` | Reject a structured edit whose selector resolves to multiple targets. |
| Invalid action and path guard | Phase 3 commit/journal/replay | `docops_ps1_invalid_reversible_in_readonly_001` | Reject a reversible edit proposal because the fixture permits only read-only actions. |
| Evidence and verifier challenge | Phase 2 evidence/verifier | `docops_wrong_diff_001` | Reject a simulated patch whose diff does not match fixture acceptance criteria. |
| Evidence and verifier challenge | Phase 2 evidence/verifier; Post-Stage-1 G6 structured edit surface | `docops_struct_wrong_diff_001` | Reject a simulated structured edit whose diff does not match the fixture oracle. |
| Evidence and verifier challenge | Phase 2 evidence/verifier; Post-Stage-1 G6 structured edit surface | `docops_struct_simulation_mutation_001` | Reject a simulated structured edit that mutates source during simulation. |
| Evidence and verifier challenge | Phase 2 evidence/verifier; Post-Stage-1 G6 structured edit surface | `docops_struct_missing_backup_metadata_001` | Reject a reversible structured edit whose observation omits required backup metadata. |
| Evidence and verifier challenge | Phase 2 evidence/verifier | `docops_ps1_wrong_diff_multiline_001` | Reject a multiline simulated patch whose diff does not match the fixture oracle. |
| Evidence and verifier challenge | Phase 2 evidence/verifier; Post-Stage-1 G6 structured edit surface | `docops_ps1_struct_backup_files_dropped_001` | Reject a reversible structured edit when backup files are dropped after write. |
| Journal, replay, and recovery | Phase 4 targeted recovery | `docops_rollback_failure_001` | Detect missing backup metadata and recover a fixture-local source file from diff data. |
| Journal, replay, and recovery | Phase 4 targeted recovery | `docops_audit_gap_001` | Detect an audit gap and repair evidence and verifier references from supplied artifacts. |
| Journal, replay, and recovery | Phase 4 targeted recovery | `docops_compensable_action_001` | Record a fixture-local compensable action and require explicit compensation instead of rollback. |
| Journal, replay, and recovery | Phase 4 targeted recovery | `docops_ps1_recovery_structured_rollback_001` | Recover a dropped-backup rollback failure by reconstructing rollback from the diff payload. |
| Journal, replay, and recovery | Phase 4 targeted recovery | `docops_ps1_recovery_audit_gap_complete_refs_001` | Repair audit references from supplied artifacts. |
| Journal, replay, and recovery | Phase 3 commit/journal/replay; Post-Stage-1 G6 structured edit surface | `docops_ps1_replay_multistep_structured_commit_001` | Replay a multi-step structured simulated commit with read-only validation and audit coverage. |
| Working-set long context | Phase 5 Working Set Compiler v0 | `docops_ws_evidence_packet_001` | Validate that the selected Evidence Packet artifact exists and remains read-only. |
| Working-set long context | Phase 5 Working Set Compiler v0 | `docops_ws_irrelevant_context_001` | Validate the relevant source artifact while ignoring irrelevant context refs. |
| Working-set long context | Phase 5 Working Set Compiler v0 | `docops_ws_omission_trap_001` | Expose omission when required context appears late in raw trace order. |
| Working-set long context | Phase 5 Working Set Compiler v0 | `docops_ws_recovery_context_001` | Include recovery context when compiling the working set. |
| Working-set long context | Phase 5 Working Set Compiler v0 | `docops_ws_traceability_long_001` | Extract traceability links from a selected document in a multi-document context. |
| Working-set long context | Phase 5 Working Set Compiler v0; Post-Stage-1 G6 structured edit surface | `docops_ps1_ws_structured_edit_context_001` | Select working-set refs needed to validate a structured-edit context note under budget. |

## Boundaries

Experiment 007 uses a separate immutable fixture family under
`fixture_local_committable_execution/`: 28 JSON case records and a workspace
template. The runner copies the template to a temporary workspace before every
effect; the catalog source is never a commit target.

- This catalog does not change fixture inclusion rules, schemas, sample-frame
  requirements, metric policy, or closure status.
- This catalog does not authorize full Context OS, memory writes,
  `IRREVERSIBLE` execution, external effects, production deployment, or any
  `COMMITTABLE` execution beyond the separately accepted G10 copied-fixture
  action.
- Measured results remain in result directories and reports, not in this
  catalog.
