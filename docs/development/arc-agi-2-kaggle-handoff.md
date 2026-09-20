# ARC-AGI-2 Trial 001 Kaggle handoff

Status: active under Decisions 0004, 0005, 0006, 0007, and 0008. The real run remains
unauthorized until a separate explicit owner instruction.

## Data flow

```text
verified local ARC source + verified unpacked Qwen model source
  -> trial-input.zip (contracts, provenance, offline runtime wheels, runner, notebook; no model bytes)
  -> two manually uploaded private immutable Kaggle Datasets
  -> Kaggle exposes the trial ZIP as an extracted tree
  -> network-disabled notebook verifies that tree and reads raw model files in place
  -> result-package.zip (predictions and execution observations only)
  -> local quarantine verification, scoring, selection, and packaging
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
  --binding .irisx\arc-agi-2\trial-001\kaggle\outbound-binding.json `
  --runtime-wheels .irisx\arc-agi-2\trial-001\runtime\linux-cp312 `
  --output .irisx\arc-agi-2\trial-001\kaggle\outbound\run-001\trial-input.zip

irisx arc-agi-2 trial outbound-verify `
  .irisx\arc-agi-2\trial-001\kaggle\outbound\run-001\trial-input.zip
```

The outbound builder validates every local model file, embeds the canonical
model provenance, and binds every runtime wheel by path, size, and digest. It
does not copy model bytes into `trial-input.zip`.

## Preflight

The preflight binding must bind both private immutable Dataset versions, the
clean full repository revision, exact Python/Torch/Transformers runtime,
runtime source identity, notebook and runner digests, one NVIDIA RTX PRO 6000
96 GB GPU, Internet disabled, no credentials, provider calls disabled, USD 0
external paid cost, the execution envelope, complete result shape, quarantine
path, and retention behavior.

```powershell
irisx arc-agi-2 trial preflight `
  --trial .irisx\arc-agi-2\trial-001\trial `
  --model-source .irisx\arc-agi-2\trial-001\model\qwen3.8-27b-1d4bf0f2 `
  --trial-package .irisx\arc-agi-2\trial-001\kaggle\outbound\run-001\trial-input.zip `
  --binding .irisx\arc-agi-2\trial-001\kaggle\preflight-binding.json `
  --output .irisx\arc-agi-2\trial-001\kaggle\preflight.json
```

A valid report says `technical_ready: true` and `run_authorized: false`. That
is readiness evidence, not execution authorization.

## Manual Kaggle procedure after authorization

1. Attach the private raw-model Dataset and private `trial-input.zip` Dataset.
2. Select exactly one NVIDIA RTX PRO 6000 96 GB accelerator.
3. Disable Internet and ensure no credentials are present.
4. Open the notebook carried in the verified trial package or use the tracked
   `trials/first-real-domain/kaggle-notebook.ipynb` with the same digest.
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
8. Download `/kaggle/working/result-package.zip` unchanged.

## Quarantine, local scoring, and final package

Place the returned file at
`.irisx/arc-agi-2/trial-001/kaggle/inbound/quarantine/<run-id>/result-package.zip`,
then verify and import it before local evaluation. Only a promoted candidate
that passes the five-point P2 acceptance gate is package-eligible.

```powershell
irisx arc-agi-2 result import `
  --package .irisx\arc-agi-2\trial-001\kaggle\inbound\quarantine\run-001\result-package.zip `
  --trial-package .irisx\arc-agi-2\trial-001\kaggle\outbound\run-001\trial-input.zip `
  --trial .irisx\arc-agi-2\trial-001\trial `
  --run-root .irisx\arc-agi-2\trial-001\runs

irisx arc-agi-2 result evaluate `
  --trial .irisx\arc-agi-2\trial-001\trial `
  --run .irisx\arc-agi-2\trial-001\runs\run-001

irisx arc-agi-2 package build `
  --trial .irisx\arc-agi-2\trial-001\trial `
  --source .irisx\arc-agi-2\trial-001\source `
  --run .irisx\arc-agi-2\trial-001\runs\run-001 `
  --model-source .irisx\arc-agi-2\trial-001\model\qwen3.8-27b-1d4bf0f2 `
  --trial-package .irisx\arc-agi-2\trial-001\kaggle\outbound\run-001\trial-input.zip `
  --result-package .irisx\arc-agi-2\trial-001\kaggle\inbound\quarantine\run-001\result-package.zip `
  --output .irisx\arc-agi-2\trial-001\domain-package
```

The final Domain Package contains the complete verified model bytes under
`deployment/model-source/source/` and binds the same provenance digest used by
the Kaggle handoff.
