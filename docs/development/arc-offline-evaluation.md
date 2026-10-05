# Shared offline ARC evaluation

`tools/arc_offline_evaluation.py` supplies evaluator-only content identity,
metrics, pairing and runtime summaries. `tools/report_arc_offline.py` is its
local CLI. It reuses `arc_kaggle_submission` grid/challenge validation and the
existing canonical digest convention. Its NVARC adapter uses the existing
`score_nvarc_public_eval` scorer and saved-package/archive binding checks;
frozen producer files and package inventories are unchanged. No model is loaded,
archive code executed, provider queried, or output uploaded.

## Commands

From the repository root, using an environment with the existing project on
`PYTHONPATH` for direct API use (the CLI sets its own import path):

```powershell
python tools\report_arc_offline.py --config <recipe.json> --output <new-output-directory>
python tools\report_arc_offline.py --synthetic-fixture --output .irisx\offline-fixture-example
python -m unittest tests.test_arc_offline_evaluation -v
```

Output directories must be new. All generated files belong under `.irisx/`.
The synthetic command uses two invented tasks/three tests, an empty pool, a
ranking miss and a top-one hit. It makes zero model calls and claims no ARC
benchmark or official score.

## Content identity and source labels

Challenge input schema is the existing exact mapping:
`{task_id: {train: [{input, output}], test: [{input}]}}`. Test outputs and extra
test fields are rejected. Digests are SHA-256 of the existing sorted,
compact UTF-8 canonical JSON, prefixed `sha256:`. Byte-file hashes are
unprefixed lowercase SHA-256. Identity includes the ordered demonstrations,
ordered full multi-test task, and each test input. Test ID/index alone is
insufficient.

The CLI verifies all 120 evaluation files against the retained digest-bound
source-provenance artifact for `arcprize/ARC-AGI-2` commit
`f3283f727488ad98fe575ea6a5ac981e4a188e49` (167 tests). It strips test outputs
before source comparison; reference answers remain evaluator-only. The
`compare_sources` API distinguishes exact reference content from pinned
provenance: its `exact_pinned_input_content` is null until a caller verifies
the pinned source. The CLI performs that verification. A supplied fixture
cannot acquire a pinned benchmark label just by matching itself.

Cross-source joins use unique input content within a task, preserving source
and destination indices. Ambiguous duplicate matches fail closed. A reordered
or enlarged test set, or changed demonstrations, cannot be labeled an exact
pinned input execution. The report records source repository/commit/locator,
challenge byte hash, reference file-inventory digest and provenance hash,
task/demo/input digests, separate task/test denominators and aggregation.

`input_content_match` and `input_and_demonstration_match` are explicitly
**filtered retrospective projections of the existing execution**. They are
not new canonical runs. The evaluator checks matched public reference answers
locally; no answer digest, equality label, score, diagnostic stratum or truth
is written back to a solver pool, notebook or outbound package.

## Recipe schema: `irisx/arc-offline-recipe-v1`

The recipe is a JSON object with exactly these fields. Relative file paths
resolve against the recipe directory; every input file is verified before use.

| Field | Required structure |
| --- | --- |
| `format` | `irisx/arc-offline-recipe-v1` |
| `source` | `path`, `sha256`, `repository`, `commit`, `locator` |
| `solutions` | `path`, `sha256`, `challenges_digest`; exact source-bound evaluator-only mapping `{task_id: [grid for every test in order]}` |
| `reference` | `root` (preserved upstream checkout), `path` (source provenance artifact), `sha256` |
| `runs` | Nonempty array of `path`, `sha256`, `adapter`, `package` |
| `official` | Null, or `path`, `sha256` for an offline normalized official observation |
| `retained_evidence` | Array of `path`, `sha256` for already retained supporting evidence |

Adapter `nvarc-public-archive` requires `package` to identify its exact saved
package; it verifies the closed ZIP, package inventory, payload bindings, plan,
records and existing scorer result. Adapter `offline-pools` requires `package`
null and the interchange below. Distinct run IDs are required. A recipe does
not authorize new acquisition, solver work or provider execution.

## Solver pool schema: `irisx/arc-offline-pools-v1`

The top level has exactly `format`, `run_id`, `method`, `challenges_digest`,
`records`, and `parent_wall_seconds` (nonnegative finite seconds or null).
`records` is a sparse array; omitted tasks/tests remain in the challenge
denominator. A record has exactly:

```text
task_id: known unique ID
task_digest: digest of the entire original task, including all ordered tests
timings: {allowed observed timing field: finite nonnegative seconds or null}
tests: [
  {test_index: unique zero-based integer,
   input_digest: digest of this exact test input,
   ranked_grids: [0..64 unique legal model candidate grids in rank order],
   status: complete | partial | failed | not_executed}
]
```

Failed/unexecuted test records cannot contain candidates. Unknown fields are
rejected at the envelope, task and test boundaries, including truth and
answer-derived metadata. The interchange contains model candidates only,
before submission filler duplication. Top-two means the first two actual
ranked candidates. A single candidate is a partial pool; an empty pool earns
no model credit even if a legal submission filler would match `[[0]]`.

Allowed timings are `training_seconds`, `search_seconds`,
`verification_seconds`, `other_seconds`, `solve_seconds`, `reset_seconds`,
`total_seconds`. These are caller-declared measured task intervals, not budget
allocations. `solve_seconds` is an overlapping combined test-solve interval,
and reset is a measured subinterval of other work. Missing clocks stay unknown.
If some task clocks are absent, the phase is partial with a known subtotal
and observed-task count; its complete `seconds` remains null.

## Output schema: `irisx/arc-offline-evaluation-v1`

The report separates `source`, `reference`, `source_comparison`,
`evaluations`, `paired`, `official_submission`, and `provenance`.
Each evaluation has local per-test `rows`, `development_metrics`, `runtime`,
and separately labeled `retrospective_projections`. Rows contain identities,
booleans, counts and statuses, never candidate or answer grids. Rows and
diagnostic labels are still evaluator-only.

Each metric has `numerator`, `denominator`, `value`, `unit`. Empty denominators
produce null values. The primary test-micro quantities are:

- `pass_at_1`: first ranked model candidate exactly matches.
- `pass_at_2`: either of the first two model candidates exactly matches.
- `candidate_oracle`: an answer exists anywhere in the retained candidate pool.
- `candidate_coverage`: pool is nonempty.
- `empty_pool`: pool is empty, including unobserved test records.
- `pool_miss`: pool is nonempty but contains no correct candidate.
- `ranking_miss`: correct candidate exists beyond the first two slots.
- `partial_pool`: exactly one actual model candidate.
- `unobserved_test_record`: no retained entry for this test.

`pass_at_2 + empty_pool + pool_miss + ranking_miss` exhausts the exact test
denominator. `task_average_pass_at_2` averages each task's solved-test fraction;
its numerator is the sum of fractions and denominator is tasks.
`tasks_all_tests_pass_at_2` counts whole-task success. Neither is test-micro
accuracy. Pairing requires equal full source and task/demo/test identities,
then reports both/gain/loss/neither for pass@1, pass@2, oracle and coverage.

Runtime reports measured parent elapsed time separately from overlapping
worker sums. Training/search/verification/other have observed/partial/unknown
states and task denominators. Existing NVARC archives measure training, reset,
total task and combined solve intervals. They do not measure separate search,
verification or complete other time. BASE training zero is grounded in its
validated no-TTT record. No residual, allowance or forward-count division is
presented as an observed phase.

## Official observation schema: `irisx/arc-official-observation-v1`

Exactly these fields are recorded: `format`, `provider`, `competition`,
`reference`, `kernel`, `kernel_version`, `status`, `outcome`, `error`,
`public_score`, `private_score`, `score_units`, `observed_at`, `receipt_sha256`.
References/kernel/outcome/error/receipt may be null; version may be null or a
positive integer. Scores must be finite numbers or null. Normalize provider
empty strings to null explicitly while preserving the original receipt.
Numeric zero remains a scored observation. `COMPLETE` plus notebook exception
and null scores is `failed_without_score`, never zero. No provider query is
performed. Score units are retained rather than inferred from local accuracy.

## Research handoff

The CLI writes `local/evaluation.json`, `evidence-brief.json`,
`evidence-brief.md`, and `manifest.json`. The manifest's closed handoff list
contains only the two brief files, with sizes/hashes. The local report hash is
an integrity reference, not a request to transfer that evaluator file.
The brief selects aggregate methods/metrics, source links/commits/hashes,
runtime summaries, official status/score fields, limitations and questions.
It contains no per-test labels, raw answer/test grids, full notebook payload,
credentials or weights. Do not ZIP the entire output directory for research.

Return research through the controller as a proposal with primary sources,
mechanism, expected observable benefit, smallest local test, failure criteria,
compute/data/exposure assumptions and required instrumentation. Source-bound
measurement alone selects neither a new model nor method and grants no GPU
or provider quota.
