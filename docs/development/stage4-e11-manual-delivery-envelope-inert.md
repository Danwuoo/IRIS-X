# E11 manual delivery envelope: future integration only

The returned v9 runtime ZIP established archive closure and CRC integrity but did
not include the separate after-close finalization receipt. The original
`nvarc_e11_paired_floor.finalize` deliberately writes an immutable sidecar with
`finalization_qualified=false` and `receipt_written=false`, then reports its
observed post-write state in the returned result/cell stdout. The sidecar alone
cannot prove the write completed or the complete finalizer finished before the
2,700-second deadline.

`tools/nvarc_e11_delivery_envelope.py` is a standalone, standard-library-only
delivery utility for a future, separately reviewed manual execution stage. Its
direct entrypoint rejects before imports. Nothing in the current renderer,
run003 package, runtime inventory, admission, download cell, or frozen source is
changed. This implementation grants no provider, GPU, QUICK_SAVE, execution,
retrieval, scoring or publication authority. It cannot repair missing v9 timing
evidence retrospectively.

## One return artifact

The future execution caller can invoke `create_envelope` once after observing
all producers stopped and after the existing finalizer returns. It receives an
absolute directory, the independently expected run ID and raw plan SHA-256, and
bounded JSON bytes already held by the caller. It reads only the fixed original
`<run_id>.zip` path and publishes `<run_id>-delivery.zip` exclusively.

The fixed outer ZIP members are:

- `runtime.zip`: the complete original ZIP, unchanged byte for byte
- `stop-evidence.json`: caller-observed stop evidence, unchanged
- `sidecar.json`: optional original immutable sidecar bytes, unchanged
- `finalizer-result.json`: optional complete observed finalizer return value,
  serialized without inventing or changing any field
- `manifest.json`: exact run/plan identity, size/SHA-256 for each other member,
  and conservative completion classification

The download cell would only expose the existing delivery ZIP. It must not
collect files, run the finalizer again, or create an envelope. The future caller
must retain the finalizer return value directly; parsing old stdout or changing
the sidecar's flags is not a substitute. A new integration must preserve its
own exact package identity and include the additional delivery time in its
budget review.

## Caller stop-evidence contract

`stop_evidence` is a JSON object with exactly these fields:

- `format`: `irisx/e11-delivery-stop-evidence-v1`
- `run_id` and `plan_sha256`: the independently expected exact identity
- `observation`: the already observed outer E11 supervision object
- `terminal`: the already retained coordinator terminal object, or null only
  for a proven coordinator launch failure
- `launches`: rank-string keys `0` through `3`, containing the caller's actual
  worker launch receipts, or null for each registered but unlaunched worker

These are supplied observations from the trusted execution caller, not a new
process supervisor or a cryptographic attestation. The utility does not infer
process absence from the existence of a ZIP or from a coordinator exit alone.
Before opening even the input directory, it checks exact deadlines, outer
stop/capture, collective worker cleanup, matching PIDs/groups, unique complete
registration, and ordered finite timestamps. Unconfirmed cleanup fails without
reading any producer file. The utility never reads a producer directory.

After admission, it checks the archived canonical plan's raw hash, run identity, terminal
plan digest, supervision observation, worker inventory and launch bindings.
The ancestor finalizer's explicitly diagnostic fallback may omit worker files;
its full caller-supplied stop proof is still required, and it remains diagnostic.
A proven prelaunch failure must contain its bootstrap failure and no admission,
terminal or worker evidence. Every archived member is streamed through CRC
verification, never extracted, imported, executed or rewritten.

## Evidence interpretation

The manifest distinguishes `unknown`, `sidecar_only`, `incomplete_result`, and
`post_write_result`. A supplied receipt with an archive hash must match the
unchanged runtime bytes. A missing hash is explicitly `archive_binding=unknown`
and cannot qualify finalization. A sidecar must retain its original false flags;
its observed final qualification is null. Conflicting sidecar/result fields
are rejected.

A true observed finalization flag requires the complete ordered finalizer
entry/validation/write/close/publication/return stages, a matching archive hash
and size, a post-write timestamp before the original hard deadline, and the
consistent complete finalizer result. Failed and incomplete results are retained
with their false/unknown state. Diagnostic archives cannot claim successful
finalization. None of this qualifies native execution, ARC correctness, method
improvement, resource availability, GPU preemption, or provider billing. Runtime
qualification is `not_assessed` or `diagnostic_only`; promotion and scoring
remain false.

Hashes provide integrity and exact supplied-identity binding, not authenticated
provenance against someone who rewrites an entire artifact and all observations.
The caller must retain trusted package identity and obtain observations from
the actual execution. Offline consumers should call `verify_envelope` with the
independently known run/plan identity before interpreting the manifest; it
rechecks member hashes, CRC, bindings and completion semantics without replaying
historical monotonic clocks as current time.

## Bounds and publication

The fixed ceilings are 256 MiB original archive, 512 MiB expanded runtime data,
4,096 runtime members, 4 MiB central directory, and 1 MiB per evidence JSON.
Streaming uses 64 KiB chunks. ZIP64, multi-disk ZIPs, archive prefixes/suffixes,
encrypted or unsupported compression, directory entries, symlinks, special
files, traversal names, case-fold duplicate names, file/directory prefix
collisions and duplicate keys in parsed plan/stop/receipt/manifest JSON are
rejected. Other runtime members receive bounded CRC verification; this helper
does not replace the full runtime schema, truth-isolation or scientific verifier.
Archived receipt comparisons
use canonical bytes so an integer cannot stand in for an equal-valued boolean. Runtime
members may use stored/deflate compression; outer envelope members are stored.
The central directory is bounded before `zipfile` allocates member objects.

Creation has at most 30 seconds and cannot extend the original hard deadline.
Supplied stop and receipt observations must already have happened at its creation
start; future timestamps are rejected even when they precede the hard deadline.
Read-only verification has its own 30-second budget. Every streamed read/write
checks the deadline. OS filesystem calls cannot be forcibly time-bounded by this
stdlib helper: a slow syscall can prevent timely return, and no worst-case
deadline or provider stop guarantee is claimed. The additional delivery budget
has only CPU-fixture coverage, not a native runtime benchmark.

POSIX `O_NOFOLLOW`, directory file descriptors and regular-file checks reject
symlinks at every input-path component and nonregular inputs before streaming.
Use a caller-owned local directory without concurrent unrelated writers. The
source is checked for concurrent mutation. Creation requires Linux `O_TMPFILE`
and procfs descriptor linking; unsupported filesystems/platforms fail closed.
An anonymous local temporary inode is fully closed as a ZIP, flushed, fsynced,
CRC/hash/semantic verified, and made read-only before exclusive atomic hard-link
publication directly from its still-open descriptor. It has no temporary pathname
that can be substituted after verification. The only intentional symlink follow
is the helper's own `/proc/self/fd/<fd>` source, never a caller-supplied path. Existing
destinations, including symlinks, are never replaced. Read-only mode and exclusive
publication are write-once behavior for this utility, not tamper-proof storage.

Without a closed, bounded original archive and confirmed producer-stop evidence,
creation rejects; it does not reconstruct missing runtime data or observations.
Closing an unpublished anonymous inode discards it and leaves the original ZIP alone.
An I/O/deadline failure after atomic publication may leave a complete delivery
file without returning success. Inspect that fixed file read-only; never retry
by overwriting it. The envelope does not attempt to put proof of its own
after-close publication inside itself. Its purpose is to retain the original
runtime finalizer's already observed after-close evidence in one return item.

## Focused CPU validation

Run `python -m unittest tests.test_nvarc_e11_delivery_envelope -v`.
Fixtures cover exact byte retention and offline re-verification, full/sidecar/
unknown/incomplete states, diagnostic and prelaunch failures, wrong run/plan/
archive binding, missing stop proof before I/O, stage order/deadline mutations,
conflicting sidecar evidence, duplicate JSON and archive names, path/symlink/FIFO
rejection, CRC corruption, bounded metadata/data, mid-copy timeout, source
mutation, tampered manifests, false promotion and immutable destination handling.
No native/model imports, provider calls or GPU operations occur.

Independent adversarial review also exercised contradictory diagnostic success,
missing diagnostic launch bindings, named-temporary substitution, case-fold/
prefix collisions and boolean/integer substitutions. These counterexamples
drove the anonymous-inode publication and type-sensitive comparison checks;
none expands the future-only integration or execution scope.
