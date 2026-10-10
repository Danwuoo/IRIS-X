# Final Linux validation and scientific lineage

Development base: `e946fb89a1deb155bb52f5c5b34e703491272853`.
This is an additive package. Old N5–N14 programs, source lock and N14 gate are unchanged.

## Accepted final native guard revision

- Runtime source identity: `96b56860be587607a8cd86ef73e83d89008b274874e3429989d889de4aab3c69`.
- Notebook SHA-256: `0e0da400f207995ed884635857ea6caa6cf23c6db3ee7375036ea8e28c652a8f`.
- Full Linux package suite: **272 passed, zero failures/errors/skips**, 42.154 seconds.
- Final fresh SMOKE: **1,152/1,152 checks**, 34.093 seconds CPU phase, 34.928 seconds total. All 64 independent-reference positives fit and all 64 legal wrong-program negatives mismatch. No unknowns, missing responses, model calls or GPU work.
- All 1,152 v2/v3 SMOKE semantic receipts are identical after excluding only four timing fields; candidate/source/task bindings, gas and feedback match.
- Real notebook default cells remain inert. Source extraction and direct-run preflights reject declared-input overlap before filesystem inspection or writes.
- Path guard review covers equality, both ancestry directions, five explicit Dataset roles, traversal/lexical aliases, write-side links and derived environment. Input-side symlink/bind-mount equivalence remains undiscoverable under the scan-free CPU contract.

Tests used an existing resolved regular Python 3.12 executable. Earlier invocations through a symlink interpreter failed strict remote-owner fixture admission; these were retained as invocation-precondition failures. No path guard was weakened. Production preparation uses a regular copied venv interpreter.

## Complete FULL scientific diagnostic, immutable v2

This run used source `758c58ac1dced5797b37dae73572386551c5274a6dfa657429102d131a153e87`, before the narrow path-guard revision. It is **v2 FULL evidence**, not a v3 FULL run. Independent review proves scientific compiler/verifier/controls/data/stages/legacy bytes, ordered candidates, budgets and dispatch logic unchanged. Fresh v3 regression and SMOKE provide the orchestration bridge. Never relabel or resume the source-bound v2 ledger under v3.

- **47,848/47,848 physical checks**: 128 controls and 5,965 candidates × 8 exposed engineering tasks.
- CPU phase **1,207.331 seconds**, below the unchanged 1,800-second ceiling; total **1,243.320 seconds**. Four isolated verifier workers.
- Task-candidate results: **3 fits, 45,813 mismatches, 1,904 out-of-domain; zero missing/unknown**.
- **2/8 tasks have a witness**: `fafffa47` has two panel-Boolean programs fitting all four demonstrations; `c444b776` has one panel-copy program fitting its sole demonstration. The two Boolean programs differ only in literal-zero versus most-frequent background on the observed data.
- The object/anchor additions produce no all-demo witness on these eight tasks. This does not show those abstractions are generally ineffective.
- Out-of-domain records retain resource/runtime exclusions. At demo level there are 1,866 program-step-limit reports, 362 subsequent shared-gas-exhausted reports, and 84 grid-bound reports; multiple demo reports can belong to one candidate. They are not 1,904 proven semantic negatives.
- The research-testability gate passes. **No model installation, weights/tokenizer load, GPU execution, training, query scoring or N14 promotion follows from this diagnostic.**

The full task-level counts, exact witness programs, gas and complete journal/response hash verification are in `validation/full-v2-audit.json`. The original evidence archive SHA-256 is `e488501891553ab23c04a3b408030d86488642ee13a87e96623efdee3fb0e8e2` (94,667,097 bytes). The downloadable technical evidence package retains this archive separately from the final source.

## Independent checks

The final release includes compact, hash-bound evidence in `validation/`:

- `linux-tests-v3.txt`, `smoke-v3-audit.json`, `v2-v3-smoke-parity.json`
- `science-invariance-v3.json`, `guard-review-v3.json`, `guard-bindings-v3.json`
- `security-review-v2.json`, covering failed-call elapsed accounting and descendant cleanup
- `runtime8-bootstrap-review-v2.json`: actual retained runtime8 bundle, all 34 payload files verified by opaque hashes only; no evaluator answers parsed
- `publication-contract-review.json`, exact notebook defaults, five pins and inactive publication settings
- `existing-helper-compatibility.json`: portable helper copies match existing repository bytes and must not overwrite them
- `release-validation.json`, provenance, commands and final scientific/orchestration status

`audit_cpu_result.py SOURCE_ROOT RESULT_JSON OUTPUT_JSON` independently recounts a completed result, verifies the full journal chain and every immutable response hash, and tests archive CRC without rerunning candidates. Raw result JSON and archives are in the technical evidence bundle.

## Reproduction

From the portable source or repository root, using an existing Linux Python 3.12:

```sh
PYTHON_REAL="$(python3 -c 'import os,sys; print(os.path.realpath(sys.executable))')"
PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_DATASETS_OFFLINE=1 CUDA_VISIBLE_DEVICES= "$PYTHON_REAL" -m unittest discover -s tools/arc_consolidated_20261010/tests -t . -p 'test_*.py' -v
```

Use a writable workspace-backed `TMPDIR` for tests and fresh output roots for actual checks. See `RUN_GUIDE.zh-TW.md` for the notebook and resume contract. Generating or changing source requires a fresh notebook build and inert checks. Documentation edits do not alter the executable source identity.

## Remaining acceptance and historical failures

The actual model/wheel/interpreter/adapter mounts, installation, tokenizer/native-vocabulary accounting, weights, G4 inference and four-L4 deployment remain unverified. CPU/mock tests do not certify them. No paid provisioning or GPU run was performed. VM billing shutdown is not claimed.

Package tests are not whole-repository CI. The separately authorized Git integrator must run the repository's prescribed aggregate checks and report exact-commit remote CI. Historical Windows aggregate failures and earlier v1/v2 validation attempts are retained in `validation/history-v2-validation.md`; none are converted into passes. Publication receipts belong to the publishers and are distinct from execution/score receipts.
