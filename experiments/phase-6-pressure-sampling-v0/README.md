# Phase 6 Batch 3 — Sampling Path Repair and Requalification

Status: active repair and requalification surface for owner-authorized TURN A.

This experiment samples six bounded, local-input, read-only, tool-free tasks
under the exact admitted `codex-cli-0.147.0-run-03-admission-v0` allocation.
It keeps task observation, failure attribution, intervention hypotheses, and
capability-trigger status separate. It implements no deferred mechanism.

The authoritative Batch 3 lifecycle is controlled by
`docs/plans/TEMP_PHASE_6_SAMPLING_PATH_REPAIR_AND_REQUALIFICATION.md`.
TURN A writes temporary provider and model artifacts only to the external
staging root recorded in `runs/batch-3/launch-manifest.json`. Repository
collection, verification, predicate derivation, interpretation, and handoff
are reserved for a later explicit owner-requested TURN B.

Batch 2 evidence and its Result C conclusion remain immutable under
`runs/batch-2/` and the retired Batch 2 plan/handoff/result documents.

Deterministic definition validation:

```powershell
python experiments\phase-6-pressure-sampling-v0\scripts\validate_definitions.py
python -m unittest discover -s experiments\phase-6-pressure-sampling-v0\tests -v
```

The fixed allocation is Luna/medium, ChatGPT authentication, read-only
sandbox, approval never, tools disabled, zero HTTP/stream retries, WebSockets
disabled, and zero routes/fallbacks/escalations/recovery actions.
