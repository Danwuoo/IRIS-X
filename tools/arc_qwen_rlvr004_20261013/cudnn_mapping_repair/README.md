# Local run007 cuDNN mapping reconstruction

This directory contains new local source, not recovered original bytes. It
overlays only `owned_runtime/environment_v2.py` and the independently assembled
terminal consumer's `consumer/release_checks.py`; earlier run source remains
unchanged.

The retrieved run006/v37 worker log and inner closure identify the actual
failure as `ValueError: loaded cuDNN backend outside pinned library directory`.
Model loading and native calibration occurred before the failed environment
admission. Their original physical charges and closure must be retained. The
old error contains no mapped pathname or library digest. A system directory
copy or pathname alias is a possible cause, not an observed v37 fact.

The replacement retains the exact environment lock, complete pinned wheel,
installed vendor library inventory, header ABI, current API/version equality,
native identity, hardware and prior environment gates. Every cuDNN mapping must
identify a regular, canonical, no-link file with the kernel's device/inode and
exact bytes of its corresponding pinned wheel member. Copies outside the owned
installed directory are accepted only in the already fixed child driver library
directories, resolved to their canonical image locations. An alternative major
version, unknown backend, foreign bytes, arbitrary directory, deleted mapping,
changed inode, link or mixed unmatched backend fails admission. No loader
environment or directory search is expanded.

Observation v2 records every mapped path, pinned member, digest, byte count,
device/inode, location and verification result. The independent consumer repeats
the complete receipt contract and keeps strict historical observation v1
validation. A bounded JSON diagnostic goes to the already preserved worker
stderr on success or failure. Earlier wheel/API failures also capture the
actual map set and best-effort hashes within the original deadline; unavailable
hashes remain explicit and never become admission evidence.

CPU regression command (run again with `python3 -O -B`):

```text
python3 -B tools/arc_qwen_rlvr004_20261013/cudnn_mapping_repair/test_cudnn_mapping.py -v
```

Use Linux with `/proc`, GCC and a regular ext4 temporary directory. The 21 tests
compile real synthetic ELF shared libraries and load them in fresh subprocesses,
then inspect real kernel mappings, including vendor backend names with multiple
underscore-delimited components. The miniature wheel/torch/distribution are
explicit test fixtures. These tests verify byte and mapping admission and the
independent consumer; they do not load actual cuDNN, perform GPU work, admit a
production model, generate predictions or demonstrate scientific efficacy.
The actual image's library mappings still require verification by the new run.

`run_legacy_environment_tests.py` also replays the 15 unchanged original
environment tests against this overlay, in normal and optimized mode. The
historical suite's named fixture is absent from the frozen checkout. The runner
copies its unchanged test source into temporary storage and supplies the exact,
hash-pinned code18 environment document as that fixture. This preserves the
original prior-field, policy, header, version, path and deadline assertions.
