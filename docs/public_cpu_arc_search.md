# Public-only, demonstration-verified CPU program candidates

## Scope and scientific status

`tools/public_cpu_arc_search` is a new, independently implemented, seed-free CPU
candidate source for the complete IRIS solver goal. It is not an agent harness,
not a learned-model result, and not a reconstruction of an original author's
method. No model weights, training API, GPU, downloads, Kaggle calls, or evaluator
imports are involved. No public evaluation inference or scoring is performed by
the tests below. Real benchmark execution is a separate, reviewed step.

The intended public source is official ARC-AGI-2 commit
`f3283f727488ad98fe575ea6a5ac981e4a188e49`, whose existing public file pins are in
`tools/public_sft141_diagnostic/public_pins.json`. A separate preparation owner
must verify those source bytes and strip each `task.test` to input-only before
handing the challenge to this package. This package deliberately does not read
raw public task files, because they contain query answers. The plan binds the
exact supplied gold-free challenge, but does not itself establish its official
upstream provenance. The separate materializer/source receipt establishes that.

For the pinned panel the external inventory is all 120 tasks / 167 true queries.
The search supports arbitrary task IDs and multiple ordered queries rather than
hard-coding that denominator. Nothing here silently changes `task.test` into a
held-out training example. Public-development score qualifications still apply;
no hidden generalization, threshold attainment, or scientific effectiveness is
claimed by successful execution.

## Frozen grammar and fitting rule

Exactly 137 attempted templates per fully searched task:

1. Seventeen spatial bases: identity; bounding-box crop of cells unequal to
   background `b`, for each `b=0..9`; uniform-block downsample factor 2 or 3;
   nearest-neighbor upscale factor 2 or 3; and full-grid tile factor 2 or 3.
2. Each spatial base followed by each of the eight D4 views from the unchanged
   public codec `tools/public_sft141_diagnostic/contract.py`. View
   `4*transpose_flag+rotations_ccw` means transpose first, then that many CCW
   quarter turns. Rectangular grids are supported.
3. One constant-output-grid family, applicable only if every support output is
   exactly identical. Its output is that entire grid, not a constant color.

A crop with no non-background cells is inapplicable. Downsampling requires both
input dimensions divisible by the factor and every factor-by-factor block
uniform. Upscale/tile outputs exceeding 30 rows or columns are inapplicable.
All final grids have dimensions 1..30 and integer colors 0..9. There is no further
chaining, object library, translations, search depth, parameter sweep, or adaptive
grammar expansion.

For each geometry, fit one deterministic color-to-color table jointly from every
visible training pair. A generated/output shape mismatch or conflicting output
for the same generated input color rejects the whole template. The full observed
table is retained in the compact program spec in sorted input-color order.

If all observed color pairs are identities, represent the palette as an explicit
parameter-free identity primitive, applicable to all ten colors including query
colors not observed in demonstrations. Otherwise it is a learned partial table:
every query cell must have an observed table entry; there is no guessed default,
copy-through, completion, or inference for unseen colors. This identity exception
was fixed before any public run. A learned full-support palette may become the
parameter-free identity primitive when refitted on a subset, using the exact same
deterministic fitting rule.

Every fitted program must explicitly replay every full support exactly. Exact
program representations are deduplicated; different valid programs remain even
when support predictions coincide. Program identities hash canonical specs.

## Genuine leave-one-demonstration-out ranking

For each accepted full-support program and each held demonstration, independently
refit the SAME geometry or constant family on the other `n-1` pairs, then predict
the held input. Record whether a prediction is defined and whether it equals the
held output, as well as the refit-program and prediction hashes. All held outputs
are already visible demonstrations, never public test answers. With one support,
LOO is explicitly unavailable and both counts are zero, not synthetic successes.

The single task-level order is frozen as:

1. Highest number of exact LOO predictions.
2. Highest number of defined LOO predictions.
3. Lowest fixed complexity.
4. Lexicographically smallest canonical program JSON string.

Complexity is spatial-operation count (identity base 0, each other base 1,
nonidentity D4 view +1), plus `1 + changed_observed_color_count` for a learned
nonidentity palette. Identity palette adds zero. A constant grid costs
`1 + output_cell_count`. There are no task/result-dependent weights or tuning.

Each query walks this shared order until it has two distinct legal predictions
or exhausts all programs. Inapplicable predictions and duplicate grids are
counted. Fewer than two candidates is valid; zero is explicitly missing. Query
inputs affect applicability, not task-level program rank. No fallback is applied
by this package. If a task is interrupted before exhaustive template/LOO search
and query selection, all of its candidate lists remain empty rather than exposing
a biased prefix as a completed search. Completed earlier tasks remain recorded.

## Why demonstration consistency is not proof

A concrete synthetic counterexample is included in the tests. Both supports are
symmetric matrices, `[[1,0],[0,2]]` and `[[2,1],[1,0]]`, each mapped to itself.
Identity and transpose both fit every support and pass both LOO folds. Complexity
ranks identity first. The unseen input `[[1,2],[0,1]]` has transpose output
`[[1,0],[2,1]]`, so the top identity program is wrong under this perfectly
support-consistent rule. This is not benchmark gold and illustrates why exact
support and LOO verification cannot establish actual query correctness.

Another test has identity-geometry supports `1→1` and `2→3`. The joint learned
palette replays both exactly, but LOO gives one undefined prediction and one
defined-but-wrong identity prediction: exact count 0, defined count 1. LOO is not
a disguised count of full-support successes.

## Input and source binding

Input is one JSON object keyed by task IDs. Every task has exactly `train` and
`test`; every nonempty training list item has exactly `input` and `output`; every
nonempty test list item has exactly `input`. Extra keys, test outputs, metadata,
labels, duplicate JSON keys, invalid grids, booleans as colors, and nonfinite
numbers are rejected before dispatch. IDs remain JSON keys, never paths.

`plan` reads only this challenge and the explicit source manifest. It freezes the
challenge SHA-256, all task/query identities, fixed grammar/ranking, budget, and
SHA-256s of the four new Python files plus imported public codec/format/filesystem
helpers and package initializers. `run` requires the same exact source/challenge
bytes before dispatch, the worker verifies them again, and the supervisor checks
them after worker exit. Plans must use canonical JSON bytes, as produced by the
CLI, avoiding alternative-serialization identity ambiguity. Source modifications
require a new plan and new reviewed identity before a real run, never a result-
driven change to the consumed run.

Source hashes bind application code, not the whole operating system or Python
installation. These local integrity receipts are not signed attestation and do
not establish a hostile-filesystem sandbox or absence of prior human exposure.

## Operational clock, process ownership, and immutable outputs

Execution is explicitly Linux-only. Its owned-process and directory-fsync tests
carry the repository's `requires_linux` eligibility annotation. They still run
in ordinary discovery and the complete Linux lane; only the named portable lane
skips them. Pure grammar/geometry/palette tests remain portable. This annotation
does not provide or claim a Windows execution backend.

The CLI takes a finite original pre-dispatch
`--started-epoch`, with its whole-process deadline equal to that epoch plus the
planned budget in `(0,600]` seconds. A future start or already-consumed budget is
rejected. No task, retry, worker restart, or result collection resets this clock.
Plans can be prepared before review; the original epoch is supplied immediately
before the one separately authorized run and recorded in immutable admission.

The supervisor creates one new output directory, writes admission and plan before
inference, and launches one worker in a new session/process group. Cooperative
checks use monotonic time. Work ends before the original deadline with at most
two seconds (or 25% of remaining time) reserved for closure. The supervisor's
watchdog kills and reaps only its own known worker group. It accepts no external
PID/group and has no `pkill`, user-computer route, Windows fallback, or GPU work.
A supervisor hard alarm remains active through final publication and fails closed
with code 124 if the original bound is exhausted. Such a directory lacks a valid
closure and is not a completed scientific result.

Atomic hard-link publication never overwrites an existing file or output
directory. A partial directory is preserved, not resumed or repaired in place.
After confirmed worker exit, the supervisor collects the entire expected
inventory, including tasks that never started and explicit missing queries.
The worker never reads an evaluator or query-answer file. Scoring must be done
separately, after exit and seal verification. No complete seal is issued for a
timeout, error, incomplete task, source/challenge mutation, or missing worker
summary. A detected mid-run challenge mutation suppresses all frozen candidates.

Artifacts:

- `plan.json` and `admission.json`: source/challenge/inventory and original clock.
- `task-NNNNNN.json`: every attempted template, failure cause, verified program
  specs, full-support replay counts, LOO folds, fixed order, selected-query
  provenance, cells/template counters, and task wall time.
- `worker.json`: source-bound worker PID, completion inventory, aggregate counters,
  worker CPU and wall timing. Required for a complete seal.
- `worker.log`: immutable-after-exit process output.
- `frozen_candidates.json`: generic source-bound frozen-candidate format understood
  by the existing `tools.public_sft141_submission` exporter. Every expected
  task/query is present, including empty candidate lists.
- `closure.json`: complete or partial status, original clock, confirmed exit,
  full inventory, artifact hashes, costs, and explicit no-accuracy qualification.

`verify` checks current source/challenge bindings, file hashes, original admission
clock and inventory, worker summary/PID/counters, receipt-derived candidates and
completion coherence. Removing `worker.json` and editing its closure entry cannot
retain a complete seal. This is integrity validation, not evaluation or signing.

Costs are seconds, attempted templates, geometry input/output cells, palette-fit
and palette-prediction cells, exact replay count, LOO refits, and query program
attempts/failures/duplicates. They are not tokens, training steps, model FLOPs, or
GPU charges. Cell counts denote named algorithmic visits, not every Python/codec
memory access. With `n` supports and `q` queries, the worst-case fit/replay effort
is proportional to `137*(n*n + q)*900` bounded grid-cell visits plus codec copying,
with early rejection commonly reducing it. No wall-time improvement or model
comparison is inferred from that complexity expression.

`worker_cpu_seconds` starts AFTER worker plan/challenge loading and admission. It
measures worker search-loop/bookkeeping CPU, including receipt publication and
final source/challenge checks, not interpreter startup or supervisor CPU.
`whole_run_wall_seconds` starts at the original pre-dispatch epoch and includes
admission/startup, inference, worker exit and closure preparation, measured just
before immutable closure publication. It excludes that last write and CLI exit;
an external caller should also record process start-to-exit wall time for a strict
end-to-end comparison. The hard deadline itself still covers final publication.

## Commands and review gate

From the repository root, create an output parent first. The following are
interface examples, not permission to execute a public benchmark:

```bash
python -m tools.public_cpu_arc_search plan \
  --challenge /absolute/gold-free-challenge.json --seconds 120 \
  --output-plan /absolute/new-plan.json

# Only after frozen-source review and the separately scoped execution approval:
python -m tools.public_cpu_arc_search run \
  --plan /absolute/new-plan.json --output-dir /absolute/new-run \
  --started-epoch ORIGINAL_PRE_DISPATCH_UNIX_SECONDS

python -m tools.public_cpu_arc_search verify --output-dir /absolute/new-run
```

Exit 0 means exhaustive source-bound execution/verification, not accuracy. Exit 3
means a closed partial run; exit 2 means rejected admission/contract/error, and
exit 124 means hard deadline with no valid final seal. A process error can leave
an incomplete output directory; do not treat file existence as completion.

The separate existing exporter can use `--source-format frozen --strategy frozen`
and `--strategy-chosen-before-gold`. Its default `--fallback fail` will fail when
queries are missing. Explicit `--fallback copy-input` is a separate format-only
choice and must retain its own fallback counts; never count those copies as
program predictions or mistake a format-complete submission for solver quality.
No official submission is performed.

## Offline validation

```bash
PYTHONHASHSEED=0 python -m unittest tests.test_public_cpu_arc_search -v
python tools/repository_check.py --all
```

Tests are hand-constructible CPU inference, not a miniature neural proxy: D4 with
joint palette, actual crop/downsample/upscale/tile, constant shortcut, crop
ambiguity, multiquery order/shared ranks, duplicate grids, false support-program
rejection, real LOO failure, singleton LOO unavailable, unseen-color rules,
support-consistent counterexample, gold-free schema, source/challenge mutation,
immutable outputs, all-inventory deadlines, exited-worker seals, and verifier
regressions. The real public benchmark is not a unit test and is not run here.
