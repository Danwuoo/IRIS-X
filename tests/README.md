# Tests

The active suite covers the P1 contracts, deterministic reference evaluation,
selection semantics, package build/verification, CLI behavior, offline-only
execution, the historical P2 admission snapshot and negative gates, current
Decision 0004 authority synchronization, and the preserved P0 archive catalog.
Decision 0004 also requires the admitted ARC-AGI-2 trial implementation to add
its specified offline coverage without running a real model/solver merely to
pass tests. Archived tests remain only in the cold-archive tag and are excluded
from default discovery.

`test_arc_agi_2.py` generates ARC-shaped data locally and covers pinned source
identity, byte provenance, 120-case isolation, training-only specialization,
pass@2, exact six-task acceptance boundaries, preflight stop conditions,
structural result recomputation, rejection of trial-local self-authorization,
the separate P2 gate, and package ineligibility before a later owner-authorized
runtime exists. It performs no network or solver calls.

Run all tests from the repository root:

```powershell
python -m unittest discover -s tests -v
```
