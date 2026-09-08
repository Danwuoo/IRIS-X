# Phase 6 Batch 2 — Direct Pressure Sampling

Status: frozen-definition experiment surface for owner-authorized TURN A.

This experiment samples six bounded, local-input, read-only, tool-free tasks
under the exact admitted `codex-cli-0.147.0-run-03-admission-v0` allocation.
It keeps task observation, failure attribution, intervention hypotheses, and
capability-trigger status separate. It implements no deferred mechanism.

The authoritative lifecycle is controlled by
`docs/plans/TEMP_PHASE_6_MECHANISM_FREE_DIRECT_PRESSURE_SAMPLING.md`.
TURN A writes temporary provider and model artifacts only to the external
staging root recorded in `runs/batch-2/launch-manifest.json`. Repository
collection, verification, predicate derivation, interpretation, and handoff
are reserved for a later explicit owner-requested TURN B.

Deterministic definition validation:

```powershell
python experiments\phase-6-pressure-sampling-v0\scripts\validate_definitions.py
python -m unittest discover -s experiments\phase-6-pressure-sampling-v0\tests -v
```

The fixed allocation is Luna/medium, ChatGPT authentication, read-only
sandbox, approval never, tools disabled, zero HTTP/stream retries, WebSockets
disabled, and zero routes/fallbacks/escalations/recovery actions.

