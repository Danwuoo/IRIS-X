# Fixture Inventory

Planning surface ID: PS1-LC-SIDEFX-COMMITTABLE-DOCOPS-001
Runnable fixture count: 0
Source fixture mutation count: 0

This scaffold lists future fixture families only. It adds no runnable
`COMMITTABLE`, `IRREVERSIBLE`, or `MEMORY_WRITE` fixture and mutates no
source fixture, repository document, user file, external target, production
target, or memory store.

| Future family | Expected planning result | Runnable fixture status |
| --- | --- | --- |
| `valid_fixture_local_commit_proposal` | future planning record with target identity, hashes, approval boundary, duplicate guard, verifier requirements, and rollback or compensation statement | not_added |
| `missing_target_identity` | planning review rejection candidate | not_added |
| `missing_approval_boundary` | blocked_missing_approval candidate | not_added |
| `missing_duplicate_guard` | planning review rejection candidate | not_added |
| `missing_rollback_or_compensation_statement` | blocked_missing_compensation_policy candidate | not_added |
| `path_escape_or_source_fixture_mutation` | blocked_path_escape candidate | not_added |
| `irreversible_misclassification` | blocked_irreversible_misclassification candidate | not_added |
| `memory_write_smuggling` | blocked_memory_write candidate | not_added |
