# Corpus Provenance Rules

Status: Phase 2 operating baseline for corpus organization. This document defines the current lightweight vocabulary; it is not governance over research claims or a final IRIS-X ontology.

## Field Semantics

- **Upstream revision**: the exact upstream Git commit, release, tag, or other independently identifiable upstream snapshot. Record it only when that identity is directly recoverable. Otherwise use `Unknown`; do not substitute a package version or local fingerprint.
- **Declared version**: a version literally declared by a source manifest, such as `pyproject.toml`, `package.json`, `setup.py`, or `mix.exs`. It always requires an evidence path and never implies the upstream revision.
- **Original import path**: the path at the initial IRIS-X import commit. It remains fixed after physical relocation so historical Git objects can be resolved.
- **Current path**: the classified working-tree location. Source paths must be under `sources/predecessors/` or `sources/external/`; artifacts must be under `references/papers/`.
- **Snapshot history**: append-only records of local capture events. A directory entry resolves `commit:path-at-capture` to a Git tree OID; an artifact entry resolves it to a Git blob OID. The active snapshot points to the latest retained capture. Future refreshes must add entries, not overwrite prior identities.
- **Acquisition evidence**: currently limited to the IRIS-X import commit and its subject. The concrete acquisition command, source URL selection, archive/tool process, and pre-import transformations remain `Unknown`.
- **Local fingerprint**: current bytes and their Git representation. For directories, validation computes a temporary-index tree from the working tree without changing the real index. For PDFs, it checks byte count, blob OID, and SHA-256 unless hash verification is explicitly disabled. Fingerprints prove what is locally recorded; they do not identify upstream origin.
- **Local modifications**: differences between the captured tree and upstream. Because upstream revisions are unknown, every current source uses `unknown`. A clean working-tree fingerprint does not establish absence of historical modification.
- **Verification status**: describes only the operation performed. `local-snapshot-fingerprinted` means the current directory was represented by a Git tree OID; `local-fingerprinted` means artifact hashes were checked. Neither means upstream correctness, completeness, license clearance, or scientific validity.

The registries intentionally use JSON-compatible YAML. This keeps one syntax for humans and coding agents while allowing the validator to depend only on Python's standard library.

## Uncertainty Labels

Use exactly these labels where applicable:

- `Unknown`
- `Unclear`
- `Not established`
- `Not evaluated`
- `Conflicting evidence`

Do not replace a gap with inference. If evidence points in more than one direction, keep the conflict visible instead of selecting a convenient answer.

Evidence paths must point inside this repository and must resolve when validation runs. External checks may be described in `identity_check_method` or URL status, but local evidence paths remain separate.

## Update Flow

1. Inspect the original imported file or directory before changing its row.
2. Distinguish source-stated facts, directly observed local facts, inferred interpretation, and unknowns.
3. Update the appropriate stable-ID row in `sources.yaml` or `artifacts.yaml`.
4. Add or resolve an item in `RECOVERY_QUEUE.md` when the change affects upstream revision, origin, acquisition method, omitted assets, or licensing.
5. Run the validator and include failures or intentional skips in the change description.
6. Do not edit imported trees merely to attach provenance; IRIS-X-authored records belong under `corpus/`.

Never infer an upstream revision from a declared package version. Never replace an old acquisition or snapshot entry with new facts.

If a future import adds a nested `.git` checkout or a durable external-evidence bundle, extend the schema deliberately and increment `schema_version`. Do not repurpose existing fields.
