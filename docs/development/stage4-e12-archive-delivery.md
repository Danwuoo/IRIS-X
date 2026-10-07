# E12 runtime and delivery closure

E12 uses new `nvarc_e12_archive.py` and `nvarc_e12_delivery_envelope.py` modules.
Historical E11 code and its 2,700-second policy remain unchanged. The E12 profile
has TERM at start + 3,290 seconds, KILL at + 3,299.8, a confirmed stop and capture
cutoff at + 3,300, and an absolute finalization cutoff at + 3,600. These are host
observations, not provider billing or escaped-process/GPU preemption attestations.

`finalize(root, observation, expected_plan_sha256)` preserves the original result
fields and adds `delivery_bundle_created`, `delivery_bundle_path`,
`delivery_bundle_sha256`, and `delivery_error`. A complete archive can preserve a
failed native outcome. `finalization_qualified` concerns raw evidence closure;
`runtime_qualification: not_assessed` explicitly does not qualify the native
training, answer quality, or promotion. The native runtime verifier remains the
separate authority for training and inference evidence.

The execution cell creates `<run>-delivery.zip` once. The download cell only
checks and links that delivery. It never rebuilds, finalizes, or recovers output.
The envelope contains the unchanged `<run>.zip` as `runtime.zip`, exact supplied
stop evidence, an immutable pre-write-completion sidecar, the observed post-write
raw finalizer result, and a manifest binding each member's size and SHA-256.
The manifest never includes its own hash; the returned outer bundle hash is not
inserted into the bundle. `finalizer_returned` means the internal raw ZIP phase
returned, not that the outer delivery function has already returned.

The immutable sidecar deliberately retains `receipt_written: false` and
`finalization_qualified: false`. Only a separate actual after-write observation
can establish receipt completion. Sidecar-only, missing, failed, and incomplete
evidence are retained as such. A data-only verifier cannot manufacture success
from false or unknown evidence. Historical monotonic stamps are compared to each
other, not to the independent review machine's current monotonic clock.

The verifier uses only the Python standard library, reads all members for CRC,
and never extracts, imports, or executes returned code. It checks exact plan and
run identity, the fixed four-task/768-update/12-test E12 profile, owned coordinator
and worker PIDs/groups, ordered raw stop/capture/finalizer stamps, and matching
archive and receipt hashes. The runtime member inventory is tied to the plan's
payload hashes and explicit root/worker/ttt64/ttt128 evidence names. A complete
coordinator requires all four worker results; each complete worker requires both
full arm inventories. Failed or incomplete scientific evidence is not upgraded.

Filesystem reads reject symlinks, special files, replaced inodes, duplicate or
case-aliased paths, unsafe components, oversized files, and oversized/deep trees.
Known generated caches are excluded only beneath the declared worker's exact
`triton-cache` or `unsloth_compiled_cache` location, or a CPython cache file for a
pinned source. Excluded files still consume the traversal and byte budgets.
Unknown `.py` and `.json` files remain forbidden. Committed malformed/duplicate
JSON and truth markers are rejected; recognized uncommitted temporary JSON and
last ledger tails can be retained without native qualification.

Publication requires Linux `O_TMPFILE` and procfs hard-linking. The archive and
receipt are created in anonymous inodes, checked, fsynced, made read-only, then
linked exclusively to their destinations. There is no temporary pathname for a
racing writer to replace. Missing platform support fails closed. Existing
runtime/delivery evidence is preserved. Deadline checks after potentially slow
writes and publication prevent reporting an in-budget completion after a late
syscall; published late bytes may exist and the returned diagnostic remains
unqualified. Full inventory failure can produce a bounded diagnostic-only ZIP
when all producer stops are established and time remains.

Unattempted dependency preflight failures are recorded with
`prelaunch_failed: true`, `launch_attempted: false`, and `launch_failed: false`;
they do not fabricate a subprocess launch rejection. An actually launched
coordinator that exits unsuccessfully before admission can also produce a
diagnostic delivery, but only when both the admitted marker and the entire
workers directory are absent. Its observed absence has a separate receipt, so
an existing bootstrap failure and captured output remain unchanged. Missing
worker cleanup after admission never receives this exception. Uncommitted
generation tails are indexed as unqualified; malformed selected generations
remain rejected.

Focused CPU validation:

```
python -m unittest tests.test_nvarc_e12_archive tests.test_nvarc_e12_delivery_envelope -q
```

Fixtures are synthetic and make no provider, model, original-gold, or owner
confirmation calls. They cover full/failed/prelaunch/diagnostic closure, exact
after-write evidence, immutable sidecars, deadline exhaustion, traversal/caches,
source hashes, CRC, path and JSON duplicates, symlinks/FIFOs, cross-run bindings,
source mutation, and exclusive anonymous-inode publication.
