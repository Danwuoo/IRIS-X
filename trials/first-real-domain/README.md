# ARC-AGI-2 Trial 001

This is the single current status page for Trial 001. Decisions 0004–0011 retain
the rationale and exact historical bindings; the detailed manual procedure is
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
- The current v4 notebook is deliberately a smoke gate: one session starts at
  most four model invocations, covering two attempts for the first baseline and
  candidate input. It exits successfully with a checkpoint and does not create
  a partial `result-package.zip`.
- The v4 repository implementation and offline verification exist. A final
  uploadable `run-002` package still needs a clean repository revision, exact
  binding, and passing technical preflight.
- The Decision 0009 layout audit remains the authoritative read-only check for
  frozen `run-001` bytes and disposable `.irisx/` aliases.
- A real model/solver run is not authorized by the tracked repository. It still
  requires a separate explicit owner instruction after a passing technical
  preflight.

Run the read-only status audit with:

```powershell
python tools\trial_001_layout.py
```

For the retained `run-001` evidence, the expected audit status is
`frozen-awaiting-result-closure`; physical path normalization remains blocked
until that audit reports `normalization_ready: true`. This historical gate does
not permit reusing the `run-001` identity for v4 bytes.

## Next action

Finish the clean-revision `run-002` binding, build and verify its outbound
package, and obtain a passing technical preflight. Do not execute it over the
real workload without a separate owner authorization for those final verified
identities. After authorization, use the v4 notebook and manually preserve its
`checkpoint-package.zip`. Treat four completed invocations as runtime-path
proof only, not Trial 001 measurement or promotion evidence.

## Fixed boundary

- Official ARC-AGI-2 source only; evaluator truth never leaves the local host.
- Frozen model:
  `Qwen/Qwen3.8-27B@1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`.
- Manual private-Dataset Kaggle transport, network disabled, no credentials in
  the notebook, and USD 0 external paid-execution budget.
- Exactly two predictions per test input; scoring, selection, and Domain Package
  construction remain local.
- `run-001` bytes and paths remain unchanged; v4 bytes use only `run-002`.
- The 43,200-second execution budget is cumulative across resumed sessions;
  resume cannot create additional model-compute budget.

## Tracked workspace

This directory contains only reviewed static material. Raw ARC source, model
weights, handoff packages, preflight reports, returned predictions, evaluation
evidence, and future Domain Packages remain under ignored `.irisx/` paths.

[`kaggle-notebook.ipynb`](kaggle-notebook.ipynb) is the frozen thin execution
adapter for `run-001`. [`kaggle-notebook-v4.ipynb`](kaggle-notebook-v4.ipynb)
is the checkpoint-aware `run-002` adapter. It reads immutable private Dataset
inputs from `/kaggle/input`, verifies them, invokes the digest-bound runner, and
creates only truth-free checkpoint/result packages. Neither notebook scores
outputs nor creates selection evidence.
