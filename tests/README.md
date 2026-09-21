# Tests

The active suite covers the P1 contracts, deterministic reference evaluation,
selection semantics, package build/verification, CLI behavior, offline-only
execution, the historical P2 admission snapshot and negative gates, current
Decision 0004/0005/0006/0007 authority synchronization, deterministic closed-world ZIP
safety, evaluator-truth isolation, model/trial/result bindings, quarantine
import, local scoring and acceptance, and the preserved P0 archive catalog.
The suite also covers Decision 0011 `run-002` outbound separation, atomic
identity-bound checkpoint round trips, tamper rejection, contiguous-prefix
resume state, cumulative-budget evidence, and checkpoint-aware preflight.
Decision 0013 coverage verifies `run-003` identity separation, absence of a
runner time limit, retry of provider-interrupted pending work, raw-generation
recording, exact four-invocation `result.zip` closure, and offline result
verification against the outbound package.
Decision 0004 also requires the admitted ARC-AGI-2 trial implementation to add
its specified offline coverage without running a real model/solver merely to
pass tests. Archived tests remain only in the cold-archive tag and are excluded
from default discovery.

Run all tests from the repository root:

```powershell
python -m unittest discover -s tests -v
```
