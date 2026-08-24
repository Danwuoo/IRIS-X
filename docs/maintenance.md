# Repository Maintenance

Status: Phase 2 operating workflow. Run all checks from the repository root.

## Baseline Command

```powershell
python tools\repository_check.py --self-test
python tools\repository_check.py
```

The second command validates registry syntax, coverage, relationships, evidence paths, semantic Git snapshot identities, current source trees, PDF fingerprints, generated indexes, authored links, and top-level boundaries. `--no-verify-hashes` disables only current PDF byte/hash verification; historical Git identity resolution remains active.

After a migration or preservation audit, run:

```powershell
python tools\migration_audit.py --help
python tools\migration_audit.py
```

## Add An External Source

1. Confirm the owner wants a new reference and identify its conservative research role.
2. Place the unchanged tree at `sources/external/<original-leaf-name>/`.
3. Record upstream URL/evidence, declared manifest version/evidence, acquisition method, license evidence, and unresolved facts in `corpus/sources.yaml`.
4. Append a snapshot entry whose `source_ref` resolves to the captured Git commit/path and record its tree OID.
5. Increase `expected_counts.sources` only after the new row is complete.
6. Update the recovery queue for every unresolved fact.
7. Run the baseline command.

## Refresh A Source

1. Copy or fetch the new content outside the existing tree first.
2. Replace `sources/<class>/<leaf-name>/` only after preserving the old snapshot identity in history.
3. Append a new snapshot ID and set `active_snapshot_id` to it; never overwrite or delete the prior entry.
4. Record acquisition method, commit/path reference, tree OID, changed facts, and continuing unknowns.
5. Run the baseline command.

## Add A Predecessor Snapshot

Follow the external-source flow, but place the tree under `sources/predecessors/` and classify it `predecessor`. If origin or license is unavailable, retain `Unknown` or `Not established` and add an owner decision to `corpus/RECOVERY_QUEUE.md`.

## Add Or Replace A Paper

1. Place the unchanged PDF under `references/papers/`.
2. Identify it from primary metadata/title, not filename alone.
3. Record publication URL, identity check method/date, related source ID when applicable, byte count, Git blob OID, and SHA-256.
4. For replacement, append a snapshot entry and move the old active entry's status through history rather than erasing it.
5. Run the baseline command.

## Deprecate Or Remove Material

Do not delete registry rows or rewrite history to hide provenance. Mark record status `deprecated`, remove the physical item from its classified corpus path only with an owner decision, retain the final snapshot entry and retirement reason, update indexes and expected counts where applicable, and explain the irreversible action in the change description. A deprecated row is a registry tombstone: its former classified path must be absent while its snapshot history remains resolvable.

## Research Notes

Start with [research/templates/research-note.md](../research/templates/research-note.md). Cite registry IDs and evidence paths, separate observations from interpretation, preserve uncertainty labels, and run link/inventory checks before finishing.
