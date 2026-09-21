# ARC-AGI-2 Trial 001

This is the single current status page for Trial 001. Accepted Decisions
0004–0011 and 0013 retain the rationale and exact historical bindings;
Decision 0012 is the pending closure proposal. The detailed manual procedure is
in the
[`Kaggle handoff guide`](../../docs/development/arc-agi-2-kaggle-handoff.md).

## Goal

Measure whether one static `prompts_programs` specialization improves official
ARC-AGI-2 public-evaluation pass@2 accuracy over the otherwise identical
baseline by at least five percentage points, using the frozen Qwen3.8-27B model
and the offline Kaggle execution envelope.

## Current state

- The repository implementation, offline validators, manual handoff adapter,
  result quarantine/import path, local scorer, and package checks exist.
- The canonical `run-001` outbound, notebook, runner, manifest, and repository
  identities are frozen by Decision 0009.
- The attempted non-checkpointing `run-001` session did not return a result after
  approximately twelve hours. It has no recoverable partial state and remains
  without a verified imported result or completed local evaluation.
- Decision 0011 introduces the separately identified `run-002` v4 adapter. It
  writes an atomic checkpoint before and after every invocation, emits live
  canonical progress, resumes only an identity-matched contiguous prefix, and
  reserves 1,800 seconds to close the checkpoint and result before the bound
  wall-clock limit.
- The current v4 notebook is deliberately a smoke gate: the checkpoint may
  contain at most four model invocations total, covering two attempts for the
  first baseline and candidate input. It exits successfully with a checkpoint
  and does not create a partial `result-package.zip`; rerunning it cannot add a
  fifth invocation.
- The executed `run-002` outbound is now frozen at repository revision
  `ea9cf7ddb014fd39eb7d969323e372ed09a2d8c2` and ZIP SHA-256
  `7ab7d06e6cdb6f5a41f6ad72b89b74a1ac55797c37fd83ba595e2bcd8d5af2f8`.
  Its notebook, runner, runner core, run binding, and checkpoint policy must not
  be rebuilt under the same identity.
- The owner-authorized smoke execution reached its four-invocation limit. The
  owner-provided Kaggle log reports four 600-second timeouts and
  2,400.337651402 seconds of cumulative model-invocation wall time. Model
  weights loaded, the optimized optional kernels were unavailable, and the
  runtime used its PyTorch fallback. This is a runtime and failure-mode
  benchmark only; it contains no successful prediction or accuracy evidence.
- Kaggle reported `/kaggle/working/checkpoint-package.zip`, but that file has
  not yet been imported and verified locally. The tracked observation is
  therefore `owner-reported`, not closure evidence.
- The owner clarified that the desired benchmark must let four generations
  finish naturally rather than count four timeout records. Decision 0013
  therefore creates a new `run-003` v5 adapter; `run-002` remains frozen.
- `run-003` executes exactly the same first four invocation keys, passes no
  `max_time` to `model.generate`, applies no cumulative runner time limit,
  checkpoints each invocation, retries an unfinished interrupted invocation on
  resume, and writes a closed-world `/kaggle/working/result.zip` after four
  terminal records. The frozen 32,768-token generation cap still applies, and
  Kaggle retains its provider-controlled session lifetime.
- Decision 0012 prepares an `inconclusive-no-promotion` closure. It now remains
  proposed until the unchanged `run-003/result.zip` is locally verified and its
  digest is recorded.
- The Decision 0009 layout audit remains the authoritative read-only check for
  frozen `run-001` bytes and disposable `.irisx/` aliases.
- The owner's 2026-09-22 instruction authorizes only the exact four-invocation
  `run-003` completion benchmark after a passing technical preflight. The other
  664 invocations and the complete Trial 001 measurement remain unauthorized.

Run the read-only status audit with:

```powershell
python tools\trial_001_layout.py
```

For the retained `run-001` evidence, the expected audit status is
`frozen-awaiting-result-closure`; physical path normalization remains blocked
until that audit reports `normalization_ready: true`. This historical gate does
not permit reusing the `run-001` identity for v4 bytes.

## Next action

Bind a clean repository revision to `run-003`, build and verify
`outbound/run-003/trial-input.zip`, and pass its technical preflight. Execute
the v5 notebook once on the bound offline Kaggle environment, resuming from its
checkpoint if the provider ends a session. Download the unchanged
`/kaggle/working/result.zip` to
`.irisx/arc-agi-2/trial-001/kaggle/inbound/quarantine/run-003/result.zip` and
verify it with `irisx arc-agi-2 result benchmark-verify`. Then finalize Decision
0012 without scoring or promoting the four-record benchmark.

## Fixed boundary

- Official ARC-AGI-2 source only; evaluator truth never leaves the local host.
- Frozen model:
  `Qwen/Qwen3.8-27B@1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`.
- Manual private-Dataset Kaggle transport, network disabled, no credentials in
  the notebook, and USD 0 external paid-execution budget.
- Exactly two predictions per test input; scoring, selection, and Domain Package
  construction remain local.
- `run-001` bytes and paths remain unchanged; v4 bytes use only `run-002`.
- Executed `run-002` bytes are frozen; different execution bytes require a new
  run identity.
- The `run-002` 43,200-second execution budget remains cumulative across its
  sessions. The separately identified `run-003` benchmark has no runner time
  limit; its four-invocation and 32,768-token-per-invocation limits remain
  binding.

## Tracked workspace

This directory contains only reviewed static material. Raw ARC source, model
weights, handoff packages, preflight reports, returned predictions, evaluation
evidence, and future Domain Packages remain under ignored `.irisx/` paths.

[`kaggle-notebook.ipynb`](kaggle-notebook.ipynb) is the frozen thin execution
adapter for `run-001`. [`kaggle-notebook-v4.ipynb`](kaggle-notebook-v4.ipynb)
is the checkpoint-aware `run-002` adapter.
[`kaggle-notebook-v5.ipynb`](kaggle-notebook-v5.ipynb) is the unbounded-time
four-invocation `run-003` benchmark adapter. They read immutable private Dataset
inputs from `/kaggle/input`, verify them, invoke digest-bound runners, and
create only truth-free checkpoint/result packages. None scores outputs or
creates selection evidence.
