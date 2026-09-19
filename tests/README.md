# Tests

The active suite covers the P1 contracts, deterministic reference evaluation,
selection semantics, package build/verification, CLI behavior, offline-only
execution, the historical P2 admission snapshot and negative gates, current
Decision 0004/0005 authority synchronization, deterministic closed-world ZIP
safety, evaluator-truth isolation, model/trial/result bindings, quarantine
import, local scoring and acceptance, and the preserved P0 archive catalog.
Decision 0004 also requires the admitted ARC-AGI-2 trial implementation to add
its specified offline coverage without running a real model/solver merely to
pass tests. Archived tests remain only in the cold-archive tag and are excluded
from default discovery.

Run all tests from the repository root:

```powershell
python -m unittest discover -s tests -v
```
