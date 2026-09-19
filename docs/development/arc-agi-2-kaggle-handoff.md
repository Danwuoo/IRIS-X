# ARC-AGI-2 Trial 001 Kaggle Offline Handoff

Status: current implementation procedure for Decision 0005. This procedure
does not authorize the real Trial 001 run.

## Boundary

The supported execution path is deliberately manual:

```text
local official source + local verified model source
  -> immutable model-package.zip
  -> truth-free trial-input.zip
  -> two private immutable Kaggle Dataset versions
  -> Internet-disabled notebook on one NVIDIA RTX PRO 6000 96 GB
  -> predictions-and-observations-only result-package.zip
  -> untrusted local quarantine
  -> validated normalized run evidence
  -> local scoring, generic selection, P2 acceptance, Domain Package
```

The repository does not manage Kaggle credentials, publish Datasets, start a
notebook, or download notebook output. Evaluator truth, expected-output digests,
scores, correctness feedback, `EvaluationResult`, `SelectionDecision`, and
Domain Package bytes never enter an outbound Dataset or Kaggle notebook.

## 1. Materialize and validate the official ARC source

This is the only ARC network-acquisition command. It accepts no repository or
revision argument and checks the fixed Decision 0004 identity.

```powershell
python -m irisx arc-agi-2 source materialize `
  --output .irisx\arc-agi-2\trial-001\source

python -m irisx arc-agi-2 source validate `
  .irisx\arc-agi-2\trial-001\source
```

Validation checks the official remote, commit
`f3283f727488ad98fe575ea6a5ac981e4a188e49`, preserved bytes, per-file SHA-256
digests, 1,000 public training tasks, 120 public evaluation tasks, and ARC grid
shape. Default tests never invoke materialization.

## 2. Materialize, package, and verify the frozen model

Model acquisition is separately invoked and may be very large. It accepts no
arbitrary model identity. Git LFS objects must be fully present; pointer files
fail validation.

```powershell
python -m irisx arc-agi-2 model materialize `
  --output .irisx\arc-agi-2\trial-001\model-source

python -m irisx arc-agi-2 model validate `
  .irisx\arc-agi-2\trial-001\model-source

python -m irisx arc-agi-2 model package-build `
  --source .irisx\arc-agi-2\trial-001\model-source `
  --output .irisx\arc-agi-2\trial-001\model\qwen3.8-27b-1d4bf0f2\model-package.zip

python -m irisx arc-agi-2 model package-verify `
  .irisx\arc-agi-2\trial-001\model\qwen3.8-27b-1d4bf0f2\model-package.zip
```

The package binds `Qwen/Qwen3.8-27B`, revision
`1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`, Apache-2.0 metadata, frozen
weights, every file size, and every file SHA-256 digest. Validation and
preflight never download weights.

## 3. Prepare and validate Trial 001 locally

```powershell
python -m irisx arc-agi-2 trial prepare `
  --source .irisx\arc-agi-2\trial-001\source `
  --output .irisx\arc-agi-2\trial-001\trial

python -m irisx arc-agi-2 trial validate `
  .irisx\arc-agi-2\trial-001\trial
```

Preparation creates the existing P1 contracts plus supporting evidence. The
solver view contains demonstrations and test inputs only. Evaluator truth is a
separate local artifact. Baseline and candidate bind the same model descriptor,
evaluator, runtime, and execution controls; only `prompts_programs` differs.

The pinned upstream README contains an internal wording inconsistency: its
formal task-success criterion permits two trials per test input, while a later
task-format paragraph says three. Decision 0004 explicitly fixes Trial 001 at
pass@2, matching the formal criterion, so the implementation requires exactly
two attempts and rejects hidden extras. This discrepancy is recorded rather
than silently interpreted as pass@3.

## 4. Bind the model Dataset and build `trial-input.zip`

Manually upload `model-package.zip` as a private Kaggle Dataset. Do not publish
it. Record its owner, slug, immutable version, exact runtime versions, clean
repository revision, and retention choices in a local outbound binding file.
The file has this exact shape:

```json
{
  "bundle_id": "run-001",
  "model_dataset": {
    "owner": "OWNER",
    "slug": "SLUG",
    "version": 1,
    "private": true,
    "immutable": true
  },
  "repository": {
    "revision": "FULL_40_HEX_COMMIT",
    "clean": true
  },
  "runtime_dependencies": {
    "python": "EXACT_VERSION",
    "torch": "EXACT_VERSION",
    "transformers": "EXACT_VERSION",
    "source": "EXACT_KAGGLE_IMAGE_OR_PRIVATE_RUNTIME_ID"
  },
  "retention": {
    "model_dataset": "OWNER-APPROVED_BEHAVIOR",
    "trial_dataset": "OWNER-APPROVED_BEHAVIOR",
    "notebook_output": "OWNER-APPROVED_BEHAVIOR",
    "local_evidence": "through Domain Package verification and owner review"
  }
}
```

Build the per-run package at the Decision 0005 path:

```powershell
python -m irisx arc-agi-2 trial outbound-build `
  --trial .irisx\arc-agi-2\trial-001\trial `
  --model-package .irisx\arc-agi-2\trial-001\model\qwen3.8-27b-1d4bf0f2\model-package.zip `
  --binding .irisx\arc-agi-2\trial-001\kaggle\outbound\run-001\binding.json `
  --output .irisx\arc-agi-2\trial-001\kaggle\outbound\run-001\trial-input.zip

python -m irisx arc-agi-2 trial outbound-verify `
  .irisx\arc-agi-2\trial-001\kaggle\outbound\run-001\trial-input.zip
```

The verifier is closed-world and rejects traversal, absolute or backslash
paths, symlinks, duplicates, undeclared files, stale identities, digest
mismatches, unsafe expansion, answer-derived metadata, credentials, third-party
ARC material, and an incomplete solver-facing workload.

## 5. Manual Trial Dataset upload and technical preflight

Upload `trial-input.zip` unchanged as a second private Kaggle Dataset. Record
its immutable owner/slug/version and the exact returned-package, hardware,
limits, quarantine, runtime, and retention bindings in a local preflight JSON
file. The `execution_limits` object must exactly copy the common execution
envelope; `result_shape` must be:

```json
[
  "logs/runner.json",
  "observations/execution.json",
  "predictions/baseline.json",
  "predictions/candidate.json"
]
```

Run static preflight offline:

```powershell
python -m irisx arc-agi-2 trial preflight `
  --trial .irisx\arc-agi-2\trial-001\trial `
  --model-package .irisx\arc-agi-2\trial-001\model\qwen3.8-27b-1d4bf0f2\model-package.zip `
  --trial-package .irisx\arc-agi-2\trial-001\kaggle\outbound\run-001\trial-input.zip `
  --binding .irisx\arc-agi-2\trial-001\preflight\run-001-bindings.json `
  --output .irisx\arc-agi-2\trial-001\preflight\run-001.json
```

A technically ready report still states `run_authorized: false`. A later,
separate owner decision must authorize the exact real run. Do not open or run
the notebook merely because static preflight passes.

## 6. Notebook procedure after later authorization

Only after that later authorization:

1. Create a private Kaggle notebook with Internet disabled.
2. Select exactly one NVIDIA RTX PRO 6000 96 GB.
3. Attach exactly the bound private model Dataset version and bound private
   trial Dataset version.
4. Import the tracked
   [`kaggle-notebook.ipynb`](../../trials/first-real-domain/kaggle-notebook.ipynb)
   without editing its source.
5. When prompted, enter the exact `trial-input.zip` SHA-256 digest recorded by
   the passed preflight. Do not copy it from the uploaded Dataset itself.
6. Run all cells. The notebook reads only `/kaggle/input`, verifies both ZIPs,
   writes only under `/kaggle/working`, blocks socket connections and address
   resolution, uses local-only model loading, and creates
   `/kaggle/working/result-package.zip`.
7. Download the complete notebook output unchanged. Do not select, edit, or
   reconstruct individual result files.

The runner records predictions, structured invocation logs, hardware, software,
seed, timeout, resource, stop-condition, and zero-cost evidence. It does not
receive evaluator truth and does not compute ARC scores.

## 7. Quarantine, import, and local evaluation

Place the unchanged result at:

```text
.irisx/arc-agi-2/trial-001/kaggle/inbound/quarantine/run-001/result-package.zip
```

Verify it without promotion, then import it:

```powershell
python -m irisx arc-agi-2 result verify `
  --package .irisx\arc-agi-2\trial-001\kaggle\inbound\quarantine\run-001\result-package.zip `
  --trial-package .irisx\arc-agi-2\trial-001\kaggle\outbound\run-001\trial-input.zip `
  --trial .irisx\arc-agi-2\trial-001\trial

python -m irisx arc-agi-2 result import `
  --package .irisx\arc-agi-2\trial-001\kaggle\inbound\quarantine\run-001\result-package.zip `
  --trial-package .irisx\arc-agi-2\trial-001\kaggle\outbound\run-001\trial-input.zip `
  --trial .irisx\arc-agi-2\trial-001\trial `
  --run-root .irisx\arc-agi-2\trial-001\run

python -m irisx arc-agi-2 result evaluate `
  --trial .irisx\arc-agi-2\trial-001\trial `
  --run .irisx\arc-agi-2\trial-001\run\run-001
```

Quarantine remains untrusted until every archive, identity, completeness,
hardware, Internet, credential, provider, cost, runtime, seed, timeout, and
envelope check passes. Only then are bytes normalized under `run/run-001/`.
Pass@2 scoring, `EvaluationResult`, generic selection, and the five-point P2
acceptance artifact are produced locally.

## 8. Eligible Domain Package

Build only when local evaluation reports both generic promotion and P2
acceptance:

```powershell
python -m irisx arc-agi-2 package build `
  --trial .irisx\arc-agi-2\trial-001\trial `
  --source .irisx\arc-agi-2\trial-001\source `
  --run .irisx\arc-agi-2\trial-001\run\run-001 `
  --model-package .irisx\arc-agi-2\trial-001\model\qwen3.8-27b-1d4bf0f2\model-package.zip `
  --trial-package .irisx\arc-agi-2\trial-001\kaggle\outbound\run-001\trial-input.zip `
  --result-package .irisx\arc-agi-2\trial-001\kaggle\inbound\quarantine\run-001\result-package.zip `
  --output .irisx\arc-agi-2\trial-001\package\run-001

python -m irisx arc-agi-2 package verify `
  .irisx\arc-agi-2\trial-001\package\run-001
```

Verification recomputes source, model, trial, result, selection, acceptance,
deployment-closure, digest, and closed-world evidence. A positive improvement
below `0.05`, any hard-requirement failure, or any stale reference remains valid
negative evidence but is package-ineligible.

## Remaining gates before any real run

A repository implementation or passing fixture does not resolve the real
bindings. Before owner authorization, report and close every unresolved item:

- complete verified model bytes and model-package digest;
- private immutable model and trial Dataset owner/slug/version bindings;
- clean repository revision and exact notebook/runner digests;
- exact Kaggle Python, PyTorch, Transformers, and image/private-runtime identity;
- actual availability of one NVIDIA RTX PRO 6000 96 GB;
- Internet-disabled and credential-free notebook state;
- invocation, pass@2, timeout, seed, decoding, output, wall-clock, and resource
  limits;
- complete-output download procedure and quarantine path;
- Dataset, notebook-output, and local-evidence retention/deletion behavior; and
- separate explicit owner authorization for that exact real run.
