# Repository Maintenance

Status: current repository and provenance maintenance guidance.

Run from the repository root:

```powershell
python tools\repository_check.py --self-test
python tools\repository_check.py
```

The second command validates registry syntax, coverage, relationships, evidence
paths, semantic Git snapshot identities, current source trees, PDF fingerprints,
generated indexes, authored links, and top-level boundaries.
`--no-verify-hashes` disables only current PDF byte/hash verification;
historical Git identity resolution remains active.

After a migration or preservation audit, inspect and run:

```powershell
python tools\migration_audit.py --help
python tools\migration_audit.py
```

## Add an external source

1. Confirm the owner wants a new reference and identify its conservative role.
2. Place the unchanged tree at `sources/external/<original-leaf-name>/`.
3. Record upstream, revision, license, acquisition, and unresolved facts in
   `corpus/sources.yaml`.
4. Append a snapshot entry whose `source_ref` resolves to the captured Git
   commit/path and record its tree OID.
5. Update expected counts and recovery records only after the row is complete.
6. Run the baseline checks.

Use the same preservation process for predecessor snapshots under
`sources/predecessors/`. Retain `Unknown` or `Not established` where provenance
cannot be recovered.

## Refresh or retire preserved material

Never overwrite snapshot history. Capture replacement content separately,
append a new snapshot, preserve the prior identity, and document the change.
For papers, preserve byte count, Git blob OID, SHA-256, identity evidence, and
replacement history.

Do not delete registry rows to hide retired material. A physical removal needs
an explicit owner decision, a retained resolvable snapshot, lifecycle metadata,
and a clear change record.

## Research notes

New notes require an authorized research scope. Use
[`../research/templates/research-note.md`](../research/templates/research-note.md),
inspect original evidence, separate observation from interpretation, and
preserve uncertainty labels.
