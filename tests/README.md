# Tests

The active suite covers the P1 contracts, deterministic reference evaluation,
selection semantics, package build/verification, CLI behavior, offline-only
execution, the P2 admission snapshot and negative gates, and the preserved P0
archive catalog. Archived tests remain only in the cold-archive tag and are
excluded from default discovery.

Run all tests from the repository root:

```powershell
python -m unittest discover -s tests -v
```
