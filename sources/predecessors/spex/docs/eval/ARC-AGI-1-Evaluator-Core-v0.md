# ARC-AGI-1 Evaluator Core v0

- **Version:** v0.1
- **Date:** 2026-08-05
- **Status:** Accepted Stage 1 local-reference implementation
- **Scope:** Strict, model-independent ARC-AGI-1 task, prediction, scoring, diagnostic, and local submission contracts
- **Authoritative evaluation definition:** [ARC Evaluation Definition v0](./ARC-Eval-Definition-v0.md) sections 6, 7.1, and 9.2
- **Frozen local rules:** [`artifacts/arc-agi-1/rules.json`](../../artifacts/arc-agi-1/rules.json)

## 1. Boundary and status

This is a development-only local-reference implementation. The official ARC-AGI-1 parser, scorer, evaluator, and submission writer remain **Unavailable in checkout**. Its output uses `local-reference-non-official`, `official_status: Unavailable in checkout`, and `parity_status: not-established`; it must not be described as an official or parity-validated score.

The core accepts the recorded local task rules as loaded from the checkout: UTF-8 JSON task objects, non-empty rectangular grids up to 30×30, integer cells 0–9, exact all-test-output task success, and at most three native attempts. It strictly permits only `train`, `test`, and an optional string `name` metadata field; when present, `name` must equal the external task ID and is not exposed in `TaskView`. It does not implement a runner, model adapter, solver, baseline, run bundle, budget, cost ledger, sealed split, or official submission path.

A read-only parse over the current 800-file A1 checkout found 11 files with this optional `name` metadata (2 training and 9 public-evaluation); each equals its filename-derived task ID. All 800 tasks pass the strict parser. Unknown top-level fields remain invalid rather than being ignored.

During Stage 1 validation, `python scripts/arc_a1_substrate.py validate` directly observed a pre-existing `rules_snapshot_mismatch`: the manifest records `237b2565904d50aaa03eed91dec90781f0ab2162e51b0c510530498679c76e68`, while the unmodified checkout's rules file hashes to `7b3c804d57f9bdf4305c73ef31bcd922df22b87ec6a75c1b0e26986f17b8e2df`. Neither Stage 0 artifact was edited here. The evaluator records the hash of the actual rules file, but this mismatch blocks a combined Stage 0 integrity-validation pass and requires a separately scoped Stage 0 correction or adjudication.

## 2. Implemented contract

The code is under [`src/spex_arc`](../../src/spex_arc):

- `domain/arc_a1.py` defines `Grid`, `TrainPair`, `TestCase`, `Task`, `Prediction`, and `CandidateSet`, plus the solver-facing `TaskView`. `Task.solver_view()` retains train pairs and test inputs but creates `SolverTestCase` records with no test-output attribute.
- `evaluator/arc_a1.py` loads the frozen rules hash and snapshot ID; performs local-reference scoring; emits structured failures; and implements deterministic submission serialization and reading.
- [`arc-agi-1-task.schema.json`](../../schemas/arc-agi-1-task.schema.json), [`arc-agi-1-prediction.schema.json`](../../schemas/arc-agi-1-prediction.schema.json), and [`arc-agi-1-local-reference-submission.schema.json`](../../schemas/arc-agi-1-local-reference-submission.schema.json) are the machine-readable task, candidate, and submission contracts. The standard-library parser enforces their structural constraints and the task-bound semantic constraints that JSON Schema cannot express directly (rectangularity, output shape, test count, attempt allowance/order, and duplicate candidates).

Invalid input is returned as deterministic `ValidationFailure` records with a stable code, JSON-like path, and message. In particular, malformed JSON, empty/ragged grids, illegal cells, missing/extra outputs, wrong shapes, duplicate candidates, excessive candidates, and evaluator/rules identity mismatches do not escape as uncaught scoring exceptions.

## 3. Scoring and diagnostics

`Exact@1` is true only when the first candidate exactly matches every test output. `Exact@K_native` is true only when one of the ordered candidates 1–3 exactly matches every test output. The latter is the frozen local reference for the source-stated A1 native attempt allowance, not an official score.

The aggregate report derives only from task-level scores and includes:

- first-attempt pixel accuracy, counting absent cells as incorrect;
- first-attempt output-shape accuracy;
- invalid-output rate and stable failure-type counts;
- first-attempt solve rate; and
- additional-attempt salvage count/rate, kept separate from `Exact@1`.

Diagnostic metrics never replace exact task accuracy.

## 4. Local submission contract

The deterministic local envelope has artifact type `arc-agi-1-local-reference-submission`, schema version `1.0`, evaluator version, rules SHA-256, local-reference scorer status, and whole-task candidate sets. Writer output uses canonical JSON (UTF-8, sorted object keys, no whitespace variation, trailing newline) and sorts task records by task ID while preserving validated candidate order. The reader rejects evaluator-version and rules-hash mismatches before scoring.

This envelope is intentionally distinct from an official ARC submission format. No official writer has been reconstructed or inferred.

## 5. Validation and Stage 1 acceptance record

From repository root, run:

```powershell
python -m unittest discover -s tests -p 'test_*.py' -v
```

The Stage 1 suite has 11 passing tests, including the existing Stage 0 substrate regressions. The Stage 1 cases cover one and multiple test inputs; permitted source-name metadata; correct output, wrong cell, wrong shape, empty/ragged grid, illegal value, missing/extra output; first versus later-attempt success; duplicate and excessive candidates; deterministic serialization; malformed task/prediction JSON; and evaluator-version/rules-hash mismatch.

| Stage 1 acceptance condition | Result |
|---|---|
| Unit and regression suites pass in the repository's standard-library Python environment | Pass — 11 tests passed. |
| Invalid output becomes a structured failure rather than an uncaught evaluator exception | Pass — parser and scorer return `ValidationFailure` records. |
| Scorer output is deterministic | Pass — immutable types, fixed task ordering, canonical serialization, and regression coverage. |
| Local reference scoring remains non-official pending authoritative scorer parity | Pass — labels and identity checks are mandatory; official materials remain unavailable. |

## 6. Status impact

- **Empirical claim impact:** none.
- **Evidence adjudication impact:** none.
- **ARC stage-status impact:** none. Stage 1 is implementation infrastructure, not an `A1-Research-Qualified`, public-complete, or verified-complete result.
- **Winning-hypothesis impact:** none.
- **Remaining blockers:** authoritative official A1 parser, scorer, evaluator, and submission-writer material remains `Unavailable in checkout`; the pre-existing Stage 0 rules-manifest hash mismatch must be corrected or adjudicated separately.
