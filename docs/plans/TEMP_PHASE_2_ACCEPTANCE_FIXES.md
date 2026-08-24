# Temporary Phase 2 Acceptance Fixes

Status: **Required before Phase 2 acceptance**

Continue from commit `9c19c90`. Do not rewrite that commit and do not merge `main`.

## Proven Failing Cases

The following cases were executed against `tools/repository_check.py` and incorrectly returned no errors:

1. Delete a registered source directory.
2. Add an unregistered directory under `sources/predecessors/` or `sources/external/`.
3. Add an unregistered PDF under `references/papers/`.
4. Append a superseded source snapshot whose `source_ref` cannot resolve and whose `tree_oid` is wrong.
5. Append a superseded artifact snapshot whose `source_ref`, `blob_oid`, SHA-256, and byte count are wrong.
6. Make `active_snapshot_id` point to a snapshot whose status is `retired`.

These are acceptance blockers because the repository currently claims exact bidirectional inventory coverage and append-only, semantically verifiable snapshot history.

## Required Validator Corrections

### Exact physical inventory

Enumerate the immediate imported leaves beneath:

- `sources/predecessors/`
- `sources/external/`
- `references/papers/*.pdf`

Validate bidirectionally:

- every active registered current path exists with the expected file type;
- every physical source leaf and paper PDF has exactly one registry record;
- duplicate registered current paths fail;
- unregistered source directories and PDFs fail;
- classification agrees with the physical predecessor/external boundary;
- `sources/AGENTS.md` and `sources/README.md` are authored boundary files, not corpus items;
- define and document physical presence rules for deprecated records.

### Complete snapshot-history validation

Validate every snapshot, not only the active source snapshot:

- each source `source_ref` must resolve to a Git tree equal to its recorded `tree_oid`;
- each artifact `source_ref` must resolve to a Git blob equal to its recorded `blob_oid`;
- read historical artifact blob bytes from Git and validate recorded byte count and SHA-256;
- current source tree and current artifact fingerprint must still equal their active snapshot;
- semantic history validation must remain enabled when `--no-verify-hashes` skips current PDF reads.

### Lifecycle invariants

For every record:

- exactly one snapshot has `status: active`;
- `active_snapshot_id` identifies that exact active snapshot;
- every other snapshot is `superseded` or `retired`;
- snapshot IDs remain globally unique;
- `record_status: active` requires physical presence;
- deprecated record behavior is explicit and tested.

## Required Regression Tests

Add executed self-tests for:

- missing registered source;
- missing registered artifact independent of evidence-path failure;
- unregistered predecessor/external source;
- unregistered paper PDF;
- duplicate current paths;
- classification/path mismatch;
- invalid historical source snapshot;
- invalid historical artifact snapshot;
- multiple active snapshots;
- no active snapshot;
- active ID pointing to retired/superseded snapshot;
- deprecated physical-presence rules.

Remove the dead `if False` missing-inventory test path.

## Documentation Corrections

- Update `corpus/RECOVERY_QUEUE.md` from Phase 1 to Phase 2.
- Replace pre-migration path labels such as `iris/` and `frugalgpt/` with stable IDs or current classified paths.
- Add conservative entries for Agent Lightning, FrugalGPT, and RouteLLM to root `AGENTS.md` under Current Research Corpus, so the authoritative agent instructions cover all 13 sources.
- Normalize generated source-index punctuation so roles that already end with punctuation do not produce `..`.
- Make `python tools/migration_audit.py --help` print usage instead of running the audit, and document its invocation briefly.

## Verification And Commit

Run:

```powershell
python tools\repository_check.py --self-test
python tools\repository_check.py
python tools\repository_check.py --no-verify-hashes
python tools\migration_audit.py
python tools\migration_audit.py --help
python -m py_compile tools\repository_check.py tools\migration_audit.py
```

Repeat the six proven failing cases above and report their expected failures. Confirm imported content remains unchanged.

Create a new commit on top of `9c19c90`; do not amend. Report the new commit hash and leave integration to the parent task.
