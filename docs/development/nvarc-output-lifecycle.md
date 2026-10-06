# NVARC committed output lifecycle (E01)

This local change concerns publication and recovery only. It does not diagnose
official submission 56840442 (Notebook Threw Exception, score null), change
solver qualification, or authorize another runtime. Historical stagers bind
pre-E01 producer bytes; new bytes require a distinct inert package identity.

## Contract declared before implementation

A public generation contains exactly `submission.json`, `submission-audit.json`,
`candidate-pools.json`, `coverage.json`, and `task-timings.json`. A native strict
generation contains exactly `native-evidence.json`, `submission-audit.json`,
`submission.json`, and `export-process.json`. An official working-root generation
contains those native files plus `official-summary.json`. Terminal diagnostics
are independent, mutable observations and never part of candidate qualification.

Each generation is a fresh directory under `.output-generations/`. Exclusive
file creation, file flush/fsync and exact byte SHA-256/length verification precede
an exclusive `manifest.json`. The manifest binds the kind, full run/plan/source/
code/model identity, actual task IDs and ordered full multi-test challenges, and
the retained records or native evidence (including reset and transcript data).
Native strict replay and existing source/reset/transcript gates run before
publication; a digest alone never substitutes for those gates. Public lightweight
evidence remains explicitly short of native qualification.
Native bindings include the exact qualification input file inventory, with
missing reset/terminal evidence recorded as null. Snapshots bracket evidence
reads and strict replay; a changed file rejects publication. Missing reset is
still handled by the existing strict contract, never inferred as successful.

The commit point is a same-directory single-path replacement of
`output-commit.json`, referencing the verified manifest digest. Before that
point an interrupted generation is an orphan, never recovered by scanning for a
newest file. After it, every member is available through that marker even if
exporter finalization or root projection fails. Older generations are retained.
One writer owns a store; concurrent writers are rejected by an exclusive lock.
A killed writer leaves its lock: recovery must follow independently confirmed
producer termination and explicit lock removal, never age-based lock stealing.

Root compatibility files are projections, not a multi-file OS transaction.
Sidecars are replaced from verified generation bytes first, `submission.json`
last, then `output-projection.json` last of all. A reader loads the commit marker
once and reads only its immutable generation, or validates every root member
against that same manifest and the matching projection marker. A crash between
marker and projection may leave stale/mixed root files: reject that projection
and rebuild all members from the committed generation. Never pair sidecars by
filename alone. Working-root submission replacement occurs only after strict
qualification. Generic `arc_kaggle_submission.write_new` and its exclusive-create
CLI remain unchanged; lifecycle replacement is a separate explicit API.
For a stopped producer, rerun the zero-model native exporter first, then use
`recover_working_output` with that caller-bound native store and the original
summary. It verifies exact contents before rebuilding root projections. Public
archives acquire the same exclusive writer lock and retain the selected committed
generation as well as its validated projections.

Recovery requires exact caller bindings and closed file inventory, strict JSON,
digests and semantic revalidation. Public recovery repeats record qualification,
rebuilds all five files and compares them. Native recovery repeats the strict
export gates and compares the four files (except process-only observations).
Foreign/stale run, changed source/code/model/reset/transcript evidence or corrupt
committed members fail closed, without selecting an older/filler generation to
claim qualification. Recovery never invokes a model. Initial unwritable storage
can produce no artifact; it must report failure. No new early fallback policy is
introduced; existing full-denominator, model/duplicate-first/constant audit stays.

Failures after commit retain candidates; failures before commit retain the
previous committed generation. A caller can explicitly repair projection after
the failed producer is stopped. No automatic task retry or qualification bypass
is introduced. Timeout/kill can leave temps/orphans/locks for diagnosis.
Terminal logging records primary and secondary exceptions separately and makes
a bounded stderr attempt if disk logging fails. No storage means diagnostics may
exist only in the returned exception/stderr. A logger error cannot replace the
primary exception. Cleanup failures are also secondary.

Four outcomes remain independent: `output_valid` (schema/full denominator),
`notebook_exit` (success/failure/unknown), `evidence_qualified` (strict native
gates; false for lightweight public evidence), and `promotion` (false here).
Legal output with failed notebook is not official-ready. No recovery grants
promotion or changes source/reset/transcript/hash thresholds.

## Durability limits

On Windows and Linux, same-filesystem rename/replace publishes one pathname,
not a transaction across multiple files. Files are fsynced before replacement.
POSIX directory fsync is attempted and its observed success reported; Windows
directory fsync is unavailable through this API. Unsupported directory fsync
is recorded, other IO errors propagate. These observations establish local
process-crash recovery on the tested filesystem, not power-loss durability,
network filesystem guarantees, GPU timing, or provider runtime qualification.
Blocking kernel IO is not forcibly preempted by an application deadline.

The finite F01–F24 mapping and actual test/replay/process receipts are retained
under `.irisx/stage4-e01-001/`; failure and never-run evidence stays explicit.
