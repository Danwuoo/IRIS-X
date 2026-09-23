# Pilot evidence and development readiness review — 2026-09-24

Reviewed main: `811bd4b`. Verdict: **the bounded 4B LoRA compatibility pilot
has credible retained success evidence; complete NVARC development and
end-to-end execution acceptance remain incomplete**.

The development task's latest final message claims completion of the authorized
004 execution and explicitly excludes full-method measurement. The trial README
also says partial. Those narrow statements match the evidence; interpreting
them as completion of the original full reproduction plan would be incorrect.

## Independent checks

This review made no Kaggle requests and started no new external model work.
It used the previously retrieved private outputs and current local code.

- `python tools/repository_check.py --all`: PASS, 198 tests, 4 optional skips
  under default Python 3.14.
- `.irisx/nvarc-ml-venv/Scripts/python.exe tools/nvarc_ml_profile.py`: PASS,
  3 tests, no skips. This runs tiny actual Qwen3.5 compact reload/gradient,
  PEFT attachment/reset, and two-rank CPU collective/resume/failure checks.
  Versions: Python 3.12, torch 2.12.1+cpu, Transformers 5.8.1,
  PEFT 0.21.0, Safetensors 0.8.0.
- Recomputed the hashes of all nine retained pilot 004 output files; all match
  the terminal verification report. Approved plan, wheel, base manifest,
  notebook and kernel metadata hashes also match the staged package.
- Independently recomputed the canonical plan identity and checked agreement
  between plan, result, ledger and verification. Step/token counts agree.
- Extracted the executed wheel and compared the pilot 004 runner, training
  module and representation module against current source bytes: all match.

Retained evidence supports: four visible L4s, device 0 used, pinned 4B base
loaded, two synthetic LoRA optimizer steps, 16 total training tokens, observed
attention/DeltaNet/embedding/head gradient groups, adapter reset, 9,419 MiB
peak allocated memory, losses 6.4069 and 4.0467, and zero generations.
The failed first request and successful retry are separate records in
`launch-ledger.json` and `auth-retry-ledger.json`; the latter records terminal
success and the one retrieval. The initial rejected ledger is retained history,
not a contradiction of the terminal result.

## What happened during the attempts

| Attempt | Observed outcome | Interpretation |
| --- | --- | --- |
| 001 | Provider COMPLETE, application hardware-gate failure before model load; actual device detail was not retained | The package omitted the official competition mount used in earlier successful cases. This was a known configuration difference; missing telemetry prevents proving it caused the hardware failure. No training happened. |
| 002 | HTTP 400 before a version receipt | Provider rejected submission; the exact bad field was not established. No model failure or result. |
| 003 | Accepted; official mount and four L4s verified; PEFT import failed against preinstalled torchao 0.10.0 | Actual dependency incompatibility before model load. A partial terminal retrieval retained non-log files, while Windows encoding left the log empty. |
| 004 first request | HTTP 401 before version creation | Expired local OAuth credential, not a model failure. |
| 004 exact-package retry | Accepted version 1; offline torchao removal, two 4B LoRA steps and full UTF-8 retrieval succeeded | The bounded compatibility check genuinely completed. |

The main delays were launch configuration, provider transport, dependency
preflight and retrieval handling. They are not evidence of NVARC learning
failure. Earlier successful notebook settings should have been reused sooner;
hardware diagnostics, dependency checks and UTF-8 retrieval belong in the
standard launch path. HTTP 400's cause must remain unknown rather than being
retroactively attributed to the shorter slug without provider evidence.

## Remaining concrete findings

### P1 — The supplied solver configuration is rejected by its binding builder

`configs/qwen-candidates.json` includes `method`, but
`src/irisx/arc_nvarc_runtime.py:36` omits it from `CONFIG_FIELDS` and lines
106–107 reject any unsupported field. `draft_outbound` passes the supplied
configuration to `make_binding` without removing metadata.

An offline synthetic one-test workload with the repository's unchanged config
fails with `candidate config has an unsupported field`. Removing only `method`
passes. Consequently the checked-in method config cannot directly prepare its
own outbound package. The passing fixture builds a separate inline config and
does not catch this integration mismatch.

Repair the config/schema boundary deliberately and add a regression through
the actual shipped configuration and outbound builder/verifier. Do not remove
the unknown-field protection globally. This is local engineering, independent
of GPU availability or experiment authorization.

### P2 — Gradient coverage does not establish finite gradients

At `src/irisx/arc_nvarc_4b_pilot_004.py:220–236`, finite loss is checked,
but coverage uses `torch.any(parameter.grad != 0)` without a finite-gradient
check. A NaN gradient satisfies that predicate, as independently confirmed
with a synthetic torch tensor. `optimizer.step()` can therefore proceed with
invalid gradients; adapter reset afterward cannot prove the update was finite.

This is a validation gap, **not evidence that pilot 004 actually produced NaNs**.
For future runners, check finite gradients and updated adapter tensors before
claiming numerical compatibility, reset group observations per step, and test
the failure path. Preserve executed pilot bytes and the historical result.

## Why this is not full-method readiness

The executed pilot loads the original full-vocabulary model and feeds compact
numeric IDs from `task_local_sequences`; it does not run the production 4B
16-token conversion or validate its source-token mapping. This is sufficient
for the narrow generic gradient/reset exercise, not grid-semantic learning.
The tiny CPU test exercises a separate small model's selected-row reload.

The pilot also uses LoRA rank 2 and two eight-token sequences. The method
configuration proposes rank 256, 16 steps and sequence limits up to 8,192.
Its 9,419 MiB measurement cannot establish that those workloads fit on an L4,
nor that full SFT fits; DDP does not shard model/optimizer memory.

Still unverified or absent:

- Real 4B compact conversion/export/reload and the corresponding derived model.
- Frozen full training data, ARC full SFT, trained export and real resume.
- Real complete-grid generation, bounded DFS, inverse transforms, likelihood
  reranking and task-local adaptation through one integrated solver run.
- Four-worker GPU dispatch or real Qwen distributed GPU training.
- Real upstream TRM checkpoint/inference/integration and SDG sandbox enforcement.
- ARC accuracy, final holdout or full-method quality/cost measurement.

The next useful milestone is a bounded vertical integration pilot: first fix
the shipped configuration and numerical guards locally, then specify the real
compact 4B conversion/reload, short adaptation and generation/reranking/result
path with representative shape and memory checks. Freeze exact materials and
resource limits before that external work. A large full-SFT launch should not
be inferred from this compatibility result. This review authorizes no new run.

## Evidence locations and documentation cleanup

New local review artifacts are under `.irisx/nvarc-acceptance-811bd4b/`:
`validation.log`, `ml-profile.log`, `evidence-check.json`, `config-probe.json`,
and `gradient-predicate-probe.json`. Pilot evidence remains untouched under
`.irisx/arc-agi-2/qwen35-nvarc/4b-pilot-launch-004/`.

`4b-pilot-004-draft.md:28` still says the dependency repair has not been tested
on Kaggle, despite its terminal section proving that it was. Treat that sentence
as an outdated draft description and label it historically in a future cleanup.
It does not undermine the verified output bytes or justify another pilot.
