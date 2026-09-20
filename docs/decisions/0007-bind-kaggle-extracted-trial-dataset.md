# Decision 0007: bind the Kaggle-extracted Trial 001 Dataset

Date: 2026-09-20  
Status: Accepted

## Decision

Kaggle expands an uploaded `trial-input.zip` into the private Dataset mount.
The active Trial 001 notebook therefore reads the closed-world trial tree from
`/kaggle/input/datasets/danielwuu/trial-input` instead of searching for the
original ZIP file.

The notebook requires `manifest.json`, verifies canonical serialization and
the exact declared membership, rejects symbolic links and undeclared files,
checks every declared byte size and SHA-256 digest, and copies only those small
verified trial files into `/kaggle/working/irisx-trial`. The unpacked model
continues to be read directly from its read-only input mount and is not copied.

Because Kaggle does not expose the original ZIP container bytes, returned
result identity binds `trial_manifest_digest`, the SHA-256 of the canonical
outbound `manifest.json`. Local preflight continues to record the transport
ZIP digest separately. Quarantine verification recomputes the manifest digest
from the retained local `trial-input.zip` before accepting a result.

The Dataset owner and slug are `danielwuu/trial-input`. Its immutable version
must be rebound after every uploaded revision. The notebook change made by
this decision requires a new Dataset version; version 1 is evidence of the
prior ZIP-looking notebook and is not eligible for execution.

This decision authorizes only transport adaptation, validation, packaging,
and preflight. It does not authorize the real model/solver run, which still
requires a later separate explicit owner authorization after every gate passes.
