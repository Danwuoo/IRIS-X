# Public SFT141 submission-format endpoint

This independent standard-library package closes the **serialization endpoint**
for the public diagnostic line. It is not a solver, accuracy evaluator, scientific
run, competition submission, or reproduction of the private IRIS pipeline. It
imports neither that pipeline nor the public diagnostic evaluator/model worker.
No private artifacts, model execution, network request, API call, notebook,
credential, or evaluation answer file is needed.

## Contract and primary sources

The output is one `submission.json` object:

```json
{"Original-task-ID":[{"attempt_1":[[1,2]],"attempt_2":[[3,4]]}]}
```

Each task maps to a list in its original test-input order, not a single pair of
grids. Each query has exactly `attempt_1` and `attempt_2`. Task IDs remain
unchanged; mapping keys are sorted only for deterministic JSON bytes. Output
shape may differ from input shape. Grids must be rectangular, 1..30 by 1..30,
with integer colors 0..9; booleans and numeric floats are rejected.

Primary sources checked on 2026-10-21:

- The [official ARC Prize 2026 ARC-AGI-2 competition page](https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-2)
  specifies exact-match success when either of two attempts matches, averaged
  over **all test outputs**: query-micro pass@2. Its submission section requires
  every challenge task ID, original test-input order, and both attempt keys in
  `submission.json`. The [2025 competition page](https://www.kaggle.com/competitions/arc-prize-2025/)
  has the same submission shape. This primary text was retrieved through public
  search indexing; direct dynamic-page extraction was empty. This verifies the
  published contract, not live authenticated scorer execution or acceptance.
- [Official ARC-AGI-2 task contract](https://github.com/arcprize/ARC-AGI-2/blob/main/readme.md#task-success-criterion)
  specifies two trials per test input and the all-test-inputs task-success
  criterion. Its grid specification is under
  [Task file format](https://github.com/arcprize/ARC-AGI-2/blob/main/readme.md#task-file-format).
  The latter section also retains an inconsistent older three-trials sentence;
  this exporter follows the explicit two-trial criterion and two-attempt wire
  contract, not that sentence.
- The [ARC Prize-maintained reference exporter](https://github.com/arcprize/hierarchical-reasoning-model-analysis/blob/main/evaluators/arc.py)
  constructs the task-to-list mapping, names attempts, and duplicates a singleton
  when padding. This implementation does not copy/import or execute that code.
- The [ARC Prize benchmarking scorer](https://github.com/arcprize/arc-agi-benchmarking/blob/main/src/arc_agi_benchmarking/scoring/scoring.py)
  computes each task's fraction of solved test queries and averages across tasks.
  This is a different aggregation from the published competition metric; do not
  silently substitute it for query-micro. No login or legal agreement was
  accepted. Reverify applicable rules and eligibility before any separately
  authorized formal submission.

### Metrics are different quantities

For a task with `m` test queries, let `s` be the number exactly solved within the
two attempts. Task-macro pass@2 is the mean of `s/m` over tasks. Query-micro
pass@2 is the sum of `s` divided by the sum of `m`; tasks with more queries get
more weight. The all-queries-solved task rate instead counts a task only when
`s == m`, matching the dataset's categorical “task solved” criterion. These are
not interchangeable. The published current Kaggle competition rule is
query-micro, not task-macro or the all-queries task rate. This serializer computes
**none** of them. Candidate,
duplicate, and fallback counts are coverage/format counts, never accuracy.
Public diagnostic results do not establish hidden generalization or gains.

## Gold-free inputs and frozen selection

The challenge must be a nonempty official-style JSON object:

```json
{
  "example": {
    "train": [{"input": [[0]], "output": [[1]]}],
    "test": [{"input": [[2]]}, {"input": [[3]]}]
  }
}
```

Only demonstration records may contain `output`. Test entries must contain only
`input`. Extra challenge/task/pair fields are rejected rather than stripped.
The exporter cannot itself remove answers from a raw public evaluation file.
Provide an already separated, gold-free challenge. Preserve every test input.

The separate candidate file has this exact schema:

```json
{
  "schema": "iris-public-sft141-frozen-candidates-v1",
  "challenge_sha256": "SHA256_OF_EXACT_CHALLENGE_FILE_BYTES",
  "strategy": "frozen",
  "strategy_chosen_before_gold": true,
  "queries": {
    "example": {
      "0": [[[4]], [[5]]],
      "1": [[[6]]]
    }
  }
}
```

Use `frozen`, `vote`, or `rescored` as the declared strategy, matching the CLI.
The export does not select a winner using evaluation results. Choose the strategy
before inspecting gold. The required declaration records that assertion; it is
**not independent evidence of when or how selection happened**.

Every expected task and every zero-based, canonical decimal test index must be
present. Query-map ordering is irrelevant; original challenge test order governs
output. Unknown IDs, omitted IDs, index gaps, `01` aliases, negative indices,
duplicate JSON keys at any depth, more than two candidates, and duplicated source
candidate grids are rejected. Provide one copy of a singleton rather than
pretending it is two distinct selections. JSON NaN/Infinity are rejected.

An explicit empty candidate list `[]` means no candidate for that query. Missing
identity records are errors even with fallback enabled; fallback cannot repair
an untrustworthy or incomplete identity inventory. There is no fixed 12-parent,
120-parent, 167-query, or other dataset-size assumption.

## CLI

From the repository root, with the parent output directory already existing:

```sh
python -m tools.public_sft141_submission export \
  --challenge .irisx/challenge.json --candidates .irisx/candidates.json \
  --strategy frozen --strategy-chosen-before-gold \
  --output-dir .irisx/submission-export-001

python -m tools.public_sft141_submission verify \
  --challenge .irisx/challenge.json --candidates .irisx/candidates.json \
  --strategy frozen --strategy-chosen-before-gold \
  --output-dir .irisx/submission-export-001
```

`export` requires a nonexistent output directory, even if an existing directory
is empty. It writes only `closure.json` and `submission.json`. `verify` rereads
sources, rebuilds the entire output and closure, and requires exact canonical
byte equivalence. It catches changed source bytes even if predictions are
unchanged. Exit status is 0 on successful format export/verification and 2 on
rejection. Successful exit never asserts model quality or a formal submission.

Default empty-candidate behavior is fail-closed with no output directory. Only
explicit `--fallback copy-input` copies that query's input into **both** attempts.
Use the same policy when verifying. This may be useful for format smoke checks;
it is not a prediction-quality claim. The closure separately records:

- two-distinct-selected queries and their genuinely selected attempts;
- singleton queries and the one duplicate-padding attempt per query;
- fallback queries and their two fallback attempts;
- the full task/query counts and each query's original identity and mode.

These attempt categories sum to exactly twice the full query count. Singleton
padding adds no second independent piece of evidence. `format_complete` may be
true while `candidate_coverage_complete` is false. All-empty selections may
produce a format-complete file only under explicit fallback.

## Existing diagnostic results

A sealed result from the existing public diagnostic can be adapted directly:

```sh
python -m tools.public_sft141_submission export \
  --challenge .irisx/diagnostic-challenge.json \
  --candidates .irisx/public-sft141-run-001/worker/result.json \
  --source-format diagnostic --strategy vote --strategy-chosen-before-gold \
  --plan .irisx/public-sft141-materials/plan.json \
  --seal .irisx/public-sft141-run-001/prediction_seal.json \
  --output-dir .irisx/diagnostic-submission-001
```

Use `--strategy rescored` only when that strategy was chosen before gold. There
is no automatic preference, winner selection, or backfill from another strategy.
The supplied official-style challenge must exactly match the gold-free plan's
full task identities, demonstrations, inputs, and query order. The seal must
bind the exact result bytes and state `worker_exited: true`.

The adapter checks all query identities, unique candidate pool entries,
canonical grid identities, occurrence-count bounds, selected-grid membership,
and vote/declared-score ordering. Both selection lists are validated, including
the unused list. Missing queries and index gaps fail, regardless of `complete`
flags. An empty selected list remains missing even if completion is claimed.
Full pool counts/scores are checked for internal ordering, **not** reconstructed
from raw token or NLL evidence. Result/row completion flags are never evidence
of actual candidate coverage, successful inference, or scientific completion.

The adapter does not read `evaluation.json` or gold and does not repeat the
independent full-token, prompt-conditioning, EOS, D4, or NLL scientific audit.
No external audit receipt is accepted as a scientific pass in this version.
Source verification is explicitly marked
`sealed-result-and-plan-inventory-checked-scientifically-unaudited`.
The hash seal is an integrity declaration, not a trusted signature or proof of
real inference; plan equivalence is not cryptographic proof that the worker used
that plan. `scientific_complete` and `accuracy_evaluated` remain false.

## Filesystem and closure guarantees

All semantic inventory validation and output serialization happen before output
creation. Input reads are bounded to 128 MiB per regular file. Parent traversal,
symlink inputs/ancestors/destinations, and Windows reparse-point paths are
rejected. Task IDs are data, never output filenames. POSIX traversal pins
no-follow directory descriptors; Windows uses explicit component checks because
its standard library lacks equivalent openat support. The Windows branch is not
an adversarial concurrent-filesystem sandbox and was not exercised on Windows in
this CPU validation.

Each file is fsynced to an exclusive temporary file and published by an atomic,
no-replacement hard link. Filesystems without hard-link support fail closed;
there is no unsafe overwrite fallback. Closure is published first, submission
last. Two-file atomic transactions are not claimed: interruption may leave an
incomplete fresh directory, which must not be used unless `verify` succeeds.
Existing evidence is never replaced or removed automatically.

The closure binds exact challenge, candidate source, optional plan/seal, and
submission SHA-256 values; strategy declaration; fallback policy; coverage;
and per-query categories. It contains no accuracy result, source grids, or
source paths. Hash consistency alone cannot establish trusted provenance or
prevent an actor who can rewrite both sources and closure from forging claims.
This tool does not run models, submit files, or accept legal terms.

## Verification and scope

```sh
PYTHONHASHSEED=0 python -m unittest discover -s tests -p 'test_public_sft141_submission.py' -v
```

The synthetic suite exercises actual CLI subprocesses and filesystem output,
round-trip verification, multi-query order, dynamic 137-task/273-query inventory,
missing/unknown/gapped/duplicate identities, complete and partial candidate
coverage, all-missing fallback, byte mutations, gold fields, shape/color bounds,
boolean rejection, explicit strategy, diagnostic pool mutations, symlinks,
parent traversal, no-overwrite and concurrent-exclusive publication, and failure
when atomic hard-link publication is unavailable. Import checks enforce stdlib
and own-package dependencies. These are engineering gates, not model results.

On 2026-10-21, 32 scoped tests passed. The combined `test_public_sft141*.py`
suite ran 88 tests: 85 passed and 3 expected optional-dependency skips. An additional
in-memory format check projected the existing pinned public source to gold-free
inputs and preserved all 120 tasks / 167 queries. All 167 queries deliberately
used input-copy fallback: zero selected predictions, no accuracy evaluation,
no model execution, and no persisted source or submission grids. These counts
are not scientific evidence. The repository-wide gate has unrelated existing
layout/fixture issues; scoped passes are not a whole-repository green claim.

The original public diagnostic remains a separate 12-parent experiment. Format
support for a larger inventory neither executes it nor expands its inference
plan. No new notebook, full-model run, Kaggle interaction, private artifact,
formal submission, or hidden-gain claim is included.
