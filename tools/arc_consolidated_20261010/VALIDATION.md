# Linux validation and scientific lineage

## Current 2026-10-10 tokenizer/output repair

Base main is `4dac3596ed776c482decaa50cd46d23fe50af73f`. The current source is
`635a43b546bae298754f136897f539ac002d0e8d40a8f36065295f609858551c`; notebook SHA is
`eac5ca3e70443e30a6049645256296d06bb9f5d377053dad701fc1aa2b525b36`.

287 Linux tests pass (43.140 seconds; zero failures/errors/skips). Actual frozen-notebook SMOKE completes 1,152 checks, 128 expected controls, zero unknowns/model calls/imports, in 32.928 seconds total with 1,661 stdout bytes. All 1,152 response hashes and archive CRC verify; v4/repair semantic receipts match after excluding four timing fields. The original compiler/inventory/controls/budgets/dispatch and immutable v2 FULL attribution remain unchanged.

See `REPAIR-20261010.zh-TW.md` and `validation/release-validation.json` for failure diagnosis, exact contracts, safe fresh-output rerun and verification limits. The following v4/v2 sections are historical; they do not describe a new repaired-source FULL/GPU run.

Development base: `e946fb89a1deb155bb52f5c5b34e703491272853`.
This is an additive package. Old N5–N14 programs, source lock and N14 gate are unchanged.

## Accepted final packaging revision v4

- Runtime source identity: `5958e67ddedfe10e4a19e33bde9d4ab98d70ae33569b225f0b94fe3953280f01`.
- Notebook SHA-256: `635b085a43cb56fbe7ff42dc8590218557e6ac988ccae69ee10bfd4b2a5e5707`.
- Full Linux package suite: **272 passed, zero failures/errors/skips**, 42.425 seconds.
- Final fresh SMOKE: **1,152/1,152 checks**, 31.211 seconds CPU phase, 31.995 seconds total. All 64 independent-reference positives fit and all 64 legal wrong-program negatives mismatch. No unknowns, missing responses, model calls or GPU work.
- All 1,152 v2/v4 SMOKE semantic receipts are identical after excluding only four timing fields; candidate/source/task bindings, gas and feedback match.
- Real notebook default cells remain inert. Source extraction and direct-run preflights reject declared-input overlap before filesystem inspection or writes.
- Path guard review covers equality, both ancestry directions, five explicit Dataset roles, traversal/lexical aliases, write-side links and derived environment. Input-side symlink/bind-mount equivalence remains undiscoverable under the scan-free CPU contract.

Tests used an existing resolved regular Python 3.12 executable. Earlier invocations through a symlink interpreter failed strict remote-owner fixture admission; these were retained as invocation-precondition failures. No path guard was weakened. Production preparation uses a regular copied venv interpreter.

## Complete FULL scientific diagnostic, immutable v2

This run used source `758c58ac1dced5797b37dae73572386551c5274a6dfa657429102d131a153e87`, before the narrow path-guard revision. It is **v2 FULL evidence**, not a v4 FULL run. Independent review proves scientific compiler/verifier/controls/data/stages/legacy bytes, ordered candidates, budgets and dispatch logic unchanged. Fresh v4 regression and SMOKE provide the orchestration bridge. Never relabel or resume the source-bound v2 ledger under v4.

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

- `science-invariance-v4.json`, `packaging-delta-v4.json`, `git-format-acceptance-v4.json`: v4 removes only one excess trailing LF from each initializer and rebuilds the notebook. Initializer ASTs are unchanged. Three precise new-directory attributes (`-text whitespace=cr-at-eol`) preserve the frozen CRLF bytes of the builder, controls and provenance; existing root attributes are untouched. Actual Git index hashes match and `git diff --cached --check` passes. Historical v3 acceptance remains in `history-v3-validation.md`.

- `linux-tests-v4.txt`, `smoke-v4-audit.json`, `v2-v4-smoke-parity.json`
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
