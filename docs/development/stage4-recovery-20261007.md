# Stage 4 recovery checkpoint — 2026-10-07

This is a recovery tree, not the complete pre-rollback development history.
The execution filesystem reverted to the surviving local checkpoint
`cb5ea25336a196bec3571aa3adea437d991c3dcb` before E12 transport preparation.
The newer E12 source `f0e449f4d2df567da659a4a9d5c8c6a83a2e8320` and integrated
checkpoint `d99165241d848525c55f461ef852cca834098451` are recorded identities;
their original Git objects are unavailable. No E12 SaveKernel request or
GitHub publication had been sent before the rollback.

## Recovered bytes and provenance

The authorized original v9 result ZIP retained its embedded runtime sources.
Those bytes plus literal authoring records reproduce the entire frozen E12
package exactly, with 80 runtime payload members and 55 project source files:

- Plan SHA-256: `f8000ab7db2a40795e93ff7482ad17ffa7fc817057207da7a9aadd6266739349`
- Package manifest SHA-256: `07e0bd80b7a4cc8bbaca6ebaad020a56ed404d77c1e0c5b489a8423650187a3c`
- Notebook SHA-256: `9617f40cbf9364d675a226687f761d65733bf2326dd96cffa52a240c86ee71f1`
- Notebook size: 881,562 bytes

All 55 project production files in that manifest were restored to this tree.
The E11 delivery utility also matches its independently retained historical
hash. Eight tests, four documents, an E12 fixture and inert plan were recovered
from literal authoring records; package equality does not authenticate their
historical full-tree identity. Exact per-file provenance is recorded in
`research/stage4-recovery-20261007/source-provenance.json`.

The complete preserved package is in the delivered Library artifact
`IRIS-X-E12-Exact-Package-Recovery-20261007-001.zip` (6,170,213 bytes), SHA-256
`57656c3a17a1dd64ec5ff6ddd8ffcee75ba04dc872a3b7ee6c5abad00f278460`.
It includes the unchanged original v9 result, reconstruction proof and literal
recovery records. Production source equality was checked without native model
imports, network calls or subprocesses in the reconstruction process.

## Execution state and resource boundary

E12 has not run. Kaggle version 10 has not been saved. The known CLI and OAuth
files were lost; no new login grant or credential search was attempted.
The last actual quota observation was 2026-10-07 15:56:57 UTC: approximately
3.195315 free GPU hours, zero reserved, paid scaling off. This is historical
and must be refreshed after authorized login recovery. It is below the
conservative four-GPU-hour reservation for this unchanged experiment.

The prepared inert notebook uses the same pinned model and dependency bytes,
private offline four-L4 execution, USD 0, independent 64-step and 128-step
training arms on four development tasks (768 updates, 12 test executions),
DFS floor 0.2 and 120 seconds generation within 150 seconds per test. Its
3,600-second watchdog is an internal cap, not evidence of provider enforcement
or stopped Editor billing. Owner confirmation defaults to false. No automatic
publication, launch, paid computation or competition submission is enabled by
this recovery tree.

## What remains unavailable

The original recent Git object history, the original full integrated tree,
several independent acceptance reports and test logs, publisher transport code,
and the separate bounded verification-queue prototype are not recovered here.
Earlier pass/failure counts are historical assertions until their original
artifacts are retrieved; new recovery tests are reported separately. A new
local commit and an exact-tree remote snapshot cannot recreate the missing
historical commits. The final handoff records their distinct SHAs explicitly.

The retained v9 analysis found both DFS floors at 1/6 public development test
accuracy and no union improvement; this is a prior result, not an E12 outcome
or official score. Confirmation remains unopened. Stage 4 and E90 are not
complete, and no claim of official ARC-AGI-2 >85 is supported.

## Resume and preservation

Use the byte-verified Library package to recover the prepared notebook; do not
regenerate it from a different source commit while claiming the old identity.
A future changed package requires a new identity and source/package review.
Restore authorized Kaggle login and check fresh free quota before choosing
Quick Save versus execution. Keep the original experiment scope and preserve
its explicit owner gate. If a run is admitted under the owner's current
workflow, wait for its terminal output and independently validate it.

The user authorized saving work to a dedicated private GitHub branch. A
connector-created snapshot may have different commit metadata from the local
recovery commit; exact full-tree equality and the mapping belong in the
separate publication receipt. The surviving history and new recovery commit
are preserved in a bundle, with missing newer history disclosed. Publication
uses `[skip ci]` to avoid unbudgeted CI; workflow files remain unchanged.
