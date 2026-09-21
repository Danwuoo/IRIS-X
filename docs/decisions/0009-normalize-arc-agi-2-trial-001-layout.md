# Decision 0009: normalize the ARC-AGI-2 Trial 001 layout without invalidating run evidence

Date: 2026-09-20
Status: Accepted

## Context

Trial 001 preparation produced several local aliases while the Kaggle handoff
was being repaired across Decisions 0006, 0007, and 0008. In particular,
multiple different outbound packages used the logical package identifier
`run-001`, while the final Decision-0008 package was also copied under several
different filenames. Binding files and notebook copies acquired similar
version suffixes.

Those aliases are understandable development evidence, but they make a path
name look like an identity. Trial identity is instead established by the
closed-world manifest and its SHA-256 bindings. Reorganizing the local tree
must not alter, rewrite, or strand a result produced by the currently retained
`run-001` outbound package.

The owner authorized this layout cleanup on 2026-09-20. This decision governs
organization and compatibility only. It does not authorize or ratify a real
model/solver execution and does not weaken any execution, data-isolation,
budget, or acceptance gate in Decisions 0004 through 0008.

## Frozen run-001 identity

Until the returned result is verified, imported, and evaluated locally, these
identities and paths are frozen:

```text
package_id: run-001
repository_revision: 3191c3e9d126570567d09651b80d0dd778e2c6f3
trial ZIP SHA-256: a179ee8b80b5b7886b756561f74be80d425312faf2d1ecea0b5d81262cef6b44
trial manifest SHA-256: 1eede07b480301cebe66b56af76846178dda5ff4b5630b75d4304364bb04dfb0
notebook SHA-256: e12a187dd59ef0978930b2c78cded09f8187e39e08b079bab0a9f1f3547bb40a
runner SHA-256: ffde7dda2dd9b035ffa654b9e0914c7d2ce5f004d55467d86c2a44a7c43502a2
```

The canonical retained outbound path is:

```text
.irisx/arc-agi-2/trial-001/kaggle/outbound/run-001/trial-input.zip
```

The returned package must remain unchanged at:

```text
.irisx/arc-agi-2/trial-001/kaggle/inbound/quarantine/run-001/result-package.zip
```

The existing `trial/`, raw model source, model provenance sidecar, offline
runtime closure, binding observations, upload staging bytes, tracked notebook,
and canonical outbound package must not be moved or deleted before the local
result closure gate passes.

## Result closure gate

Layout movement is permitted only after all of the following are true:

1. the canonical outbound package still matches every frozen identity above;
2. the unchanged returned package passes offline result verification against
   that outbound package and the frozen local Trial 001 bundle;
3. quarantine import has atomically produced
   `.irisx/arc-agi-2/trial-001/runs/run-001/import-evidence.json`;
4. local evaluation has produced the complete `local-evaluation/` evidence;
   and
5. a layout audit reports `normalization_ready: true`.

The plural `runs/<run-id>/` path is the active normalized-evidence location and
narrowly supersedes the singular `run/<run-id>/` example in Decision 0005.
This naming clarification changes no artifact bytes or validation semantics.

## Canonical layout after the gate

The local generated tree is normalized to:

```text
.irisx/arc-agi-2/trial-001/
|-- source/
|-- model/
|-- runtime/linux-cp312/
|-- trial/
|-- kaggle/
|   |-- bindings/<run-id>/
|   |-- outbound/<run-id>/trial-input.zip
|   |-- inbound/quarantine/<run-id>/result-package.zip
|   |-- upload/<run-id>/
|   `-- superseded/
|-- runs/<run-id>/
`-- domain-package/
```

The tracked workspace will move from the generic
`trials/first-real-domain/` name to the explicit
`trials/arc-agi-2/trial-001/` name only after the result closure gate. The
notebook bytes need not change merely because their tracked path changes.
Outbound packages already built from the old repository revision remain
verified against their embedded bytes and retained revision; they are never
rewritten to claim the new path.

## Identity and retention rules

- A new outbound build must be written as
  `outbound/<bundle-id>/trial-input.zip`; the directory name and manifest
  `package_id` must match.
- Rebuilding different bytes requires a new bundle identifier such as
  `run-002`. Version suffixes such as `run-001-v2` must not carry
  `package_id: run-001`.
- `run-001-v1` and `run-001-v2` are superseded development transport evidence,
  not eligible Trial 001 inputs.
- Exact aliases of the frozen Decision-0008 bytes may be classified and moved
  under `kaggle/superseded/` after the result closure gate. They are not
  silently treated as independent runs.
- Retained packages are moved byte-for-byte and checked before and after any
  move. They are not repacked, edited, or assigned a new identity.
- Deletion remains subject to the existing retention text and a later explicit
  owner action after Domain Package verification and owner review.

## Consequences

- The in-flight or returned `run-001` result remains usable through the exact
  Decision-0008 outbound package and manifest identity.
- Future outbound construction fails closed when the output directory does not
  match the chosen bundle identifier.
- A repository-local, read-only layout audit reports frozen identity status,
  aliases, superseded packages, and result-closure readiness without moving
  files.
- Physical normalization is intentionally deferred while any result-closure
  condition is absent.
