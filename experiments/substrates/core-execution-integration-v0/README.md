# Core Execution Integration v0

Status: deterministic read-only integration path for the provisional Phase 5 core

This substrate is the existing second execution path: a lookup of one record in a small in-memory map. It binds immutable task-contract and program bytes, including the contract-declared evidence requirements, uses `irisx.core.execute`, invokes a fixture-local `ReadOnlyLookupAdapter` exactly once, independently verifies supplied evidence against the bound context, and records identical before/after state hashes.

The request is explicitly read-only, so mutation prevention is not required and no policy gate is invoked. The path performs zero model, network, API, retry, route, escalation, recovery, persistence, or workflow-search actions. It writes no run directory and makes no claim beyond local deterministic interface reuse.

Run from repository root:

```powershell
python experiments\substrates\core-execution-integration-v0\scripts\run_lookup.py
python -m unittest discover -s experiments\substrates\core-execution-integration-v0\tests -v
```
