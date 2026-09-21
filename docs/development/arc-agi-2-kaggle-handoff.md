# ARC-AGI-2 Trial 001 Kaggle handoff

Status: active under accepted Decisions 0004–0011 and 0013. `run-001` and the
executed v4 `run-002` remain frozen. The owner authorized the exact v5
four-invocation `run-003` completion benchmark; the remaining 664 invocations
remain unauthorized.

## Decision 0009 in-flight freeze

The retained `run-001` transport is frozen while its returned evidence has not
yet completed quarantine import and local evaluation. Do not rename, move,
repack, or delete its canonical outbound package, Trial bundle, model source,
runtime closure, upload staging bytes, bindings, or notebook during that
window. The read-only audit reports the current gate:

```powershell
python tools\trial_001_layout.py
```

The canonical outbound remains
`.irisx\arc-agi-2\trial-001\kaggle\outbound\run-001\trial-input.zip`.
Future outbound builds must use
`kaggle\outbound\<bundle-id>\trial-input.zip`, with the directory name equal to
the manifest package ID. Different bytes require a new bundle ID; suffixes such
as `run-001-v2` must not retain `package_id: run-001`.

Physical normalization and the tracked workspace rename to
`trials/arc-agi-2/trial-001/` occur only after the audit reports
`normalization_ready: true`. Normalized local run evidence uses the plural
`.irisx\arc-agi-2\trial-001\runs\<run-id>\` path.

## Decision 0011 run-002 checkpoint flow

The attempted v3 session did not return a complete result and has no partial
state that can be imported. Do not mutate or relabel it. The v4 adapter is
packaged only as `run-002` and adds:

- atomic `checkpoint-package.zip` writes before and after every invocation;
- flushed `progress.jsonl` events mirrored to the notebook output;
- exact resume binding to the outbound manifest, model provenance, repository,
  notebook, v4 runner, frozen runner core, configurations, envelope, and policy;
- fail-closed recovery of an in-flight invocation as a charged timeout;
- one cumulative 43,200-second budget across all sessions; and
- a 1,800-second finalization reserve so remaining invocations can be recorded
  as timeouts and a complete result can close before the venue limit.

The currently packaged notebook limits its checkpoint to four actual model
invocations total. Deterministic interleaving makes those first four calls the two
attempts for the first baseline input and the two attempts for the matching
candidate input. Reaching this smoke limit is a successful checkpoint-only
exit; rerunning the notebook cannot add a fifth invocation, and it never
fabricates a partial result package.

The checkpoint contains predictions and execution state, never evaluator truth.
Cross-session persistence is manual: download the latest checkpoint unchanged,
publish it as a new immutable version of the private
`danielwuu/run-002-checkpoint` Dataset, and attach that Dataset to the resumed
notebook. No credential or automated Kaggle transport is added.

## Decision 0013 run-003 completion benchmark

`run-003` replaces only the four-invocation benchmark transport. It does not
modify or resume `run-002`. The v5 runner:

- executes the same first four keys as v4;
- retains `max_new_tokens: 32768` but passes no `max_time` to
  `model.generate` and applies no cumulative runner wall-clock limit;
- checkpoints before and after every invocation;
- retries an interrupted pending invocation on resume; and
- writes `/kaggle/working/result.zip` after four terminal records.

Kaggle's provider-controlled session lifetime still applies. The result ZIP
contains each raw generation, parsing and error status, token counts, seeds,
EOS flags, UTC and elapsed timing, runtime and model identity, progress log,
final checkpoint, and run binding. It contains no evaluator truth or scores.

## Data flow

```text
verified local ARC source + verified unpacked Qwen model source
  -> trial-input.zip (contracts, provenance, offline runtime wheels, runner, notebook; no model bytes)
  -> two required private immutable Kaggle Datasets
     (+ one optional private checkpoint Dataset when resuming)
  -> Kaggle exposes the trial ZIP as an extracted tree
  -> network-disabled notebook verifies that tree and reads raw model files in place
  -> run-003 result.zip (four raw generations and execution observations only)
  -> local quarantine verification and inconclusive closure preparation
```

Evaluator truth never enters an outbound Dataset, notebook, or returned result.
Kaggle credentials and transport are manual and stay outside the repository.

## Fixed model binding

- repository: `Qwen/Qwen3.8-27B`
- revision: `1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`
- local source root:
  `.irisx\arc-agi-2\trial-001\model\qwen3.8-27b-1d4bf0f2`
- local provenance sidecar:
  `.irisx\arc-agi-2\trial-001\model\qwen3.8-27b-1d4bf0f2-provenance.json`
- Kaggle Dataset: private immutable `danielwuu/qwen38-27b`
- notebook path: `/kaggle/input/datasets/danielwuu/qwen38-27b`
- representation: unpacked model files at the Dataset root
- identity: exact path, byte size, and SHA-256 list in the local provenance
  sidecar and outbound binding
- effective runtime: Python 3.12.13, Torch 2.10.0+cu128, and the packaged
  offline Transformers 5.8.1 wheel closure

`model-package.zip` is not part of the active flow.

## Build the outbound input

Create a canonical binding JSON with exactly these top-level fields:
`bundle_id`, `model_dataset`, `repository`, `runtime_dependencies`, and
`retention`. The Dataset version and runtime versions must be the exact values
observed in Kaggle; all retention values must be non-empty.

```powershell
irisx arc-agi-2 model validate `
  .irisx\arc-agi-2\trial-001\model\qwen3.8-27b-1d4bf0f2

irisx arc-agi-2 trial outbound-build `
  --trial .irisx\arc-agi-2\trial-001\trial `
  --model-source .irisx\arc-agi-2\trial-001\model\qwen3.8-27b-1d4bf0f2 `
  --binding .irisx\arc-agi-2\trial-001\kaggle\run-003-binding.json `
  --runtime-wheels .irisx\arc-agi-2\trial-001\runtime\linux-cp312 `
  --output .irisx\arc-agi-2\trial-001\kaggle\outbound\run-003\trial-input.zip

irisx arc-agi-2 trial outbound-verify `
  .irisx\arc-agi-2\trial-001\kaggle\outbound\run-003\trial-input.zip
```

The binding uses `bundle_id: run-003`. The outbound builder validates every
local model file, embeds the canonical model provenance, binds every runtime
wheel by path, size, and digest, and packages `kaggle_runner_v5.py` as the
runner plus the frozen v3 runner as `runner_core.py`. It does not copy model
bytes into `trial-input.zip`.

## Preflight

The preflight binding must bind both private immutable Dataset versions, the
clean full repository revision, exact Python/Torch/Transformers runtime,
runtime source identity, notebook, runner, runner-core digests, the exact
checkpoint policy, one NVIDIA RTX PRO 6000 96 GB GPU, Internet disabled, no
credentials, provider calls disabled, USD 0 external paid cost, the four-call
unbounded-time adapter policy, benchmark result shape, `run-003` quarantine
path, and retention behavior.

```powershell
irisx arc-agi-2 trial preflight `
  --trial .irisx\arc-agi-2\trial-001\trial `
  --model-source .irisx\arc-agi-2\trial-001\model\qwen3.8-27b-1d4bf0f2 `
  --trial-package .irisx\arc-agi-2\trial-001\kaggle\outbound\run-003\trial-input.zip `
  --binding .irisx\arc-agi-2\trial-001\kaggle\run-003-preflight-binding.json `
  --output .irisx\arc-agi-2\trial-001\kaggle\run-003-preflight.json
```

A valid report says `technical_ready: true`. The owner's Decision-0013
authorization is separate from this technical evidence and applies only to the
exact verified `run-003` identities. The technical artifact deliberately keeps
`run_authorized: false`; it cannot self-authorize execution.

## Manual Kaggle procedure after authorization

1. Attach the private raw-model Dataset and private `trial-input.zip` Dataset.
2. Select exactly one NVIDIA RTX PRO 6000 96 GB accelerator.
3. Disable Internet and ensure no credentials are present.
4. Open the notebook carried in the verified trial package or use the tracked
   `trials/first-real-domain/kaggle-notebook-v5.ipynb` with the same digest.
5. The notebook reads the extracted trial tree directly from
   `/kaggle/input/datasets/danielwuu/trial-input`, verifies its manifest and
   complete closed-world membership, then copies only those small trial files
   to `/kaggle/working`.
6. The notebook safely expands the verified offline wheel closure into
   `/kaggle/working`, confirms Transformers 5.8.1 exposes Qwen3.5, and does not
   access the network.
7. The notebook verifies the complete raw model Dataset against provenance and loads
   it directly from `/kaggle/input`; it performs no 55 GB ZIP extraction or
   model copy.
8. Watch the flushed notebook progress. No runner timer stops a generation.
   The latest recoverable state is always
   `/kaggle/working/checkpoint-package.zip`; `result.zip` appears only after
   four terminal invocation records.
9. If the session must be resumed, download that checkpoint unchanged, publish
   it as a private immutable `danielwuu/run-003-checkpoint` Dataset version,
   attach it, and rerun the v5 notebook. A same-session rerun automatically
   finds the working checkpoint first.
10. After four terminal records, download `result.zip` unchanged for offline
    verification. Do not send it through the full-trial scoring/import path.

Verify the returned benchmark without evaluator truth:

```powershell
irisx arc-agi-2 result benchmark-verify `
  --package .irisx\arc-agi-2\trial-001\kaggle\inbound\quarantine\run-003\result.zip `
  --trial-package .irisx\arc-agi-2\trial-001\kaggle\outbound\run-003\trial-input.zip
```

## Quarantine, local scoring, and final package

Place the returned file at
`.irisx/arc-agi-2/trial-001/kaggle/inbound/quarantine/<run-id>/result-package.zip`,
then verify and import it before local evaluation. Only a promoted candidate
that passes the five-point P2 acceptance gate is package-eligible.

```powershell
irisx arc-agi-2 result import `
  --package .irisx\arc-agi-2\trial-001\kaggle\inbound\quarantine\run-002\result-package.zip `
  --trial-package .irisx\arc-agi-2\trial-001\kaggle\outbound\run-002\trial-input.zip `
  --trial .irisx\arc-agi-2\trial-001\trial `
  --run-root .irisx\arc-agi-2\trial-001\runs

irisx arc-agi-2 result evaluate `
  --trial .irisx\arc-agi-2\trial-001\trial `
  --run .irisx\arc-agi-2\trial-001\runs\run-002

irisx arc-agi-2 package build `
  --trial .irisx\arc-agi-2\trial-001\trial `
  --source .irisx\arc-agi-2\trial-001\source `
  --run .irisx\arc-agi-2\trial-001\runs\run-002 `
  --model-source .irisx\arc-agi-2\trial-001\model\qwen3.8-27b-1d4bf0f2 `
  --trial-package .irisx\arc-agi-2\trial-001\kaggle\outbound\run-002\trial-input.zip `
  --result-package .irisx\arc-agi-2\trial-001\kaggle\inbound\quarantine\run-002\result-package.zip `
  --output .irisx\arc-agi-2\trial-001\domain-package
```

The final Domain Package contains the complete verified model bytes under
`deployment/model-source/source/` and binds the same provenance digest used by
the Kaggle handoff.
