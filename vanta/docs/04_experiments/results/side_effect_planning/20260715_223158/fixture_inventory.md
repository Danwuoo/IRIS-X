# Fixture Inventory

Fixture root: `docs/04_experiments/fixtures/side_effect_planning`
Fixture count: 10
Pre-run tree hash: `sha256:6d1721f5f8db80f8e77f6c56fca4b13bd4c97f544a4151061369c1b3a34d510e`
Post-run tree hash: `sha256:6d1721f5f8db80f8e77f6c56fca4b13bd4c97f544a4151061369c1b3a34d510e`
Source fixture mutation count: 0

| Fixture | Family | Expected | Actual | Oracle match |
| --- | --- | --- | --- | --- |
| `sidefx_irreversible_misclassification_001` | `irreversible_misclassification` | rejected | rejected | true |
| `sidefx_memory_write_smuggling_001` | `memory_write_smuggling` | rejected | rejected | true |
| `sidefx_missing_approval_boundary_001` | `missing_approval_boundary` | rejected | rejected | true |
| `sidefx_missing_idempotency_duplicate_guard_001` | `missing_idempotency_duplicate_guard` | rejected | rejected | true |
| `sidefx_missing_rollback_compensation_001` | `missing_rollback_or_compensation_statement` | rejected | rejected | true |
| `sidefx_missing_target_identity_001` | `missing_target_identity` | rejected | rejected | true |
| `sidefx_path_escape_001` | `path_escape` | rejected | rejected | true |
| `sidefx_source_fixture_mutation_001` | `source_fixture_mutation` | rejected | rejected | true |
| `sidefx_valid_restore_001` | `valid_fixture_local_commit_proposal` | valid | valid | true |
| `sidefx_valid_supersede_001` | `valid_fixture_local_commit_proposal` | valid | valid | true |
