# ARC-AGI-2 Trial 001 — closed

This is the single current status page for Trial 001. Decision 0012 is accepted
and closes the trial with disposition `inconclusive-no-promotion`. Decisions
0004–0011 and 0013 retain the detailed rationale, execution boundaries, and
frozen identities.

## Goal

The trial sought to measure whether one static `prompts_programs`
specialization improves official ARC-AGI-2 public-evaluation pass@2 accuracy
over the otherwise identical baseline by at least five percentage points,
using the frozen `Qwen/Qwen3.8-27B` model and offline Kaggle envelope.

## Current state

- Status: `closed-inconclusive` as of 2026-09-22.
- The measurement did not complete, no accuracy was computed, the candidate was
  not selected, and no Domain Package was created.
- Frozen `run-001` returned no result after approximately twelve hours and has
  no recoverable partial state.
- Executed `run-002` is frozen at repository revision
  `ea9cf7ddb014fd39eb7d969323e372ed09a2d8c2` and outbound ZIP SHA-256
  `7ab7d06e6cdb6f5a41f6ad72b89b74a1ac55797c37fd83ba595e2bcd8d5af2f8`.
  The owner-provided Kaggle log reports four 600-second timeouts and
  2,400.337651402 seconds of model-invocation wall time. The checkpoint was not
  imported, so this is owner-reported runtime evidence, not verified prediction
  or accuracy evidence.
- Prepared `run-003` used the v5 adapter and removed runner-level time limits
  for exactly four invocations. No `result.zip` was accepted through local
  quarantine verification before the owner chose closure without waiting.
- The owner's 2026-09-22 closure instruction ends the Decision-0013 execution
  authorization. The remaining 664 invocations and any continuation of
  `run-003` are not authorized.
- [`closure.json`](closure.json) is the machine-readable terminal record. Its
  empty `result_digests` list is deliberate.

## Next action

Do not execute, resume, score, or promote Trial 001. Preserve the frozen run
identities and retained local bytes. The read-only layout audit now recognizes
the accepted inconclusive closure as an alternative terminal gate and may
report `normalization_ready: true`; any physical byte-preserving normalization
is a separate maintenance change.

```powershell
python tools\trial_001_layout.py
```

Any new model experiment must begin with a new trial question, explicit scope,
new trial/run identities, and any required execution authorization.

## Fixed boundary

- Official ARC-AGI-2 source only; evaluator truth never left the local host.
- Frozen model:
  `Qwen/Qwen3.8-27B@1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`.
- Manual private-Dataset Kaggle transport, network disabled, no notebook
  credentials, and USD 0 external paid-execution budget.
- `run-001`, `run-002`, and `run-003` identities remain distinct and frozen.
- The `run-002` `checkpoint-package.zip` and `run-003` `result.zip` were not
  imported as closure evidence.
- Disposition `inconclusive-no-promotion` is not a score and does not evaluate
  the five-percentage-point acceptance threshold.

## Tracked workspace

The notebooks and runners remain as reproducibility and lineage material:

- `kaggle-notebook.ipynb`: frozen `run-001` adapter;
- `kaggle-notebook-v4.ipynb`: checkpoint-aware `run-002` adapter; and
- `kaggle-notebook-v5.ipynb`: four-invocation `run-003` adapter.

They are not active execution instructions after closure. Raw ARC source, model
weights, handoff packages, and retained local execution material remain under
ignored `.irisx/` paths.
