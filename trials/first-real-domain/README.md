# ARC-AGI-2 Trial 001

This tracked workspace contains only reviewed static material for the first
real-domain Engineering Trial admitted by Decisions 0004 and 0005. Raw ARC
source, model weights, ZIP handoff packages, preflight reports, returned
predictions, local evaluation evidence, and future Domain Packages remain under
ignored `.irisx/` paths.

[`kaggle-notebook.ipynb`](kaggle-notebook.ipynb) is the thin, network-disabled
execution adapter. It reads immutable private Dataset inputs from
`/kaggle/input`, verifies and extracts them beneath `/kaggle/working`, invokes
the digest-bound runner, and creates one complete `result-package.zip`. It does
not score ARC outputs or create selection or Domain Package evidence.

The notebook must not be run over the real frozen workload until a later
explicit owner authorization binds the exact model and trial Dataset versions,
package digests, repository/notebook/runner revisions, runtime dependencies,
resource limits, retention behavior, and a passing technical preflight.
