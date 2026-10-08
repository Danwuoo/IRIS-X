# E20 bounded object/geometry branch

Status: CPU implementation and synthetic validation; the first frozen public
development screen produced zero candidate vectors and its configuration is
rejected. No complementary coverage, official readiness, or official-score claim.
This first configuration is frozen before the coordinator's development
evaluation. No evaluator solutions or confirmation inputs were used in design.

## Delta and ownership

The baseline had native NVARC candidate generation and neutral offline pools,
but no symbolic program search. New files provide the closed DSL, isolated CPU
runner, a small neutral provenance adapter, truth-free execution CLI, and a
separate evaluator-only CLI. Existing common schemas, native eight-view
verification semantics, historical fixtures and frozen run bytes are unchanged.
The DSL is newly written; no external ARC solutions/program library was copied.
No source/dependency download, model call, paid compute, GPU call, submission,
push, PR or publication is part of this implementation.

The companion `.irisx/` materials were absent in this worktree at the initial
inspection, including the three-file code-only native fixture and public source
provenance/answers. Tests below need none of them. The coordinator subsequently
provided only a frozen solver-visible development challenge (24 tasks/35
tests), digest
`sha256:b346c4958c9d4be369d62695ff0e8e490f6914922153f23f302b5698e4aaca25`.
Evaluation of its labels is assigned to an independent evaluator.

## Frozen grammar and semantics

One macro is extract -> select -> transform -> render, exactly four expanded
AST nodes. Maximum three macros means at most twelve AST nodes, not Python AST
height. There is one non-nested selector per macro. The full JSON grammar has
1,120 fixed macro choices; its canonical digest is retained with each run.

- Extractors: whole grid, all foreground as one object, same-color foreground
  connected components using four or eight neighbors
- Selectors: all, largest/smallest by occupied pixel count with first row-major
  tie break, or a fixed color 0..9. Whole-grid/foreground extractors allow all only
- Transform classes: identity, CCW rotation (90/180/270 degrees), horizontal or
  vertical reflection, transpose, single-foreground-color bounding-box fill,
  integer scale (2 or 3), and foreground recolor (fixed target 0..9)
- Renderers: original-size canvas or bounding-box crop of the selected union

Background is the most frequent color in the **current** macro input; ties
choose the lowest color. It is recomputed at every macro. A crop may therefore
make the former foreground the next macro's background; crop-then-recolor can
recolor holes. This is deliberate frozen semantics, not answer-derived logic.
Object geometry is local to its bounding rectangle and preserves its canvas
top-left anchor. Canvas bounds are strict, never clipped. Different-color
overlap fails; equal-color overlap is allowed. Empty crops fail. Empty canvas
selections yield the inferred background. Dimensions always remain 1..30.

## Search and resource contract

Deterministic breadth-first enumeration counts every attempted macro expansion,
including invalid and deduplicated attempts. Parameter inventories never come
from demo output labels. Every candidate must exactly fit every ordered demo.
Semantic dedup includes all demos and all ordered test inputs together, retaining
demo-equivalent programs when their test predictions differ. Equivalent joint
semantics retain the first-enumerated minimum-depth representative. This is not
guaranteed to be the globally smallest canonical program among equivalent
prefixes. Candidate ranking uses expanded AST complexity then canonical bytes
of the retained programs, not likelihood or truth.
At most 64 unique full-task candidate vectors survive; per-test pools dedup
those vectors without inventing independent test correctness.

Default caps: ten seconds for one isolated task solve including worker startup
and output transfer; 50,000 expansion attempts; 256 MiB serialized search-state
cache; three macro steps/twelve AST nodes; 64 candidate vectors. The worker
uses Linux RLIMIT_AS at 1 GiB, bounding virtual memory and therefore RSS. Peak
RSS is measured independently in Linux bytes. The limit is not an RSS reading.
Before enforcement, bootstrap virtual mappings and historical RSS are checked;
already-oversized bootstrap fails without starting search. Lowering RLIMIT_AS
does not reclaim preexisting mappings.
Unsupported platforms fail closed. Node/cache caps retain a deterministic
prefix; wall termination/fault/memory failure discard partial candidates.
Real wall-cutoff state counts can vary with host scheduling; no bitwise runtime
determinism is claimed. Fixed input/config plus a state cap determines ordering.
Forced worker kill adds measured cleanup overhead after the compute cutoff.
Parent provenance replay/finalization is bounded by record sizes but is outside
the worker cutoff; total run wall is measured separately, never inferred from
ten-second allowances or summed CPU intervals.

Optional LOO is disabled by default. With at least three demos, each fold removes
the held-out demo before a fresh search, then evaluates its top-ranked program
on that demo's input. Main search and every fold share the same wall/state caps.
Support is null if any fold cannot finish or fewer than three demos exist.
Main retained candidates are reserved against every fold's cache allowance,
previous fold results are released before the next search, and the aggregate
peak serialized cache is reported and checked against the shared cap.
The support describes the **search/selection procedure**, not every program's
individual generalization. Even 3/3 support does not guarantee a test answer.

Typed evaluation has no code execution or file/network operators. It imports no
task lookup, evaluator, model or native solution source. Process bootstrap loads
reviewed code; stdin/stdout carry only a strict truth-free task and result.

## Candidate interoperability

`arc_candidates_neutral` v2 replays programs on all demos and tests, binds full
task and ordered input identity, code/config/grammar/program/output digests,
costs and demo evidence. Explicit complete limits are digest-bound and all
candidate count/depth/AST and measured state/cache/wall/CPU/RSS caps are checked
at export and direct validation. Completed-search cutoff reason is retained.
`record_kind=symbolic-program` is distinct from native
generation. Its native verification field must be null. Eight native views and
native score provenance remain in their originating native artifacts; a ranked
pool reference or DSL fit cannot certify them.

The default development operation is standalone DSL. Two optional fixed policies
are exposed for later measurement: baseline-first preserves its first two unique
grids; one-each-v2 uses baseline's first grid and the first symbolic grid distinct
from that head. A shared symbolic head does not displace its later novel grid.
The unselected original one-each-v1 head-collision fallback is historical.
No learned router,
task-ID rule, source-score comparison or test-label feature is present. Combined
retained pools cap at 64 grids; the evaluator computes **full** branch union
oracle from separately scored branch rows, so this cap cannot silently reduce
the reported union. Oracle, actual fixed-two-slot results, tests and whole-task
success are distinct quantities. Tasks with any newly correct test and newly
all-tests-correct tasks have separately named fields. No selection policy is accepted on synthetic
success alone.

## Commands and truth boundary

Set `PYTHONPATH=src`, `PYTHONHASHSEED=0`, offline HF variables and empty
`CUDA_VISIBLE_DEVICES` for CPU checks. Full repository checks are serialized by
the coordinator. Focused checks:

```
python -m unittest tests.test_arc_symbolic_dsl tests.test_arc_symbolic_independent -v
```

The solver CLI accepts challenges with demonstrations and **test inputs only**:

```
python tools/run_arc_symbolic.py --challenges <solver-visible/dev-challenges.json> --expected-challenges-digest <frozen-canonical-digest> --run-id <fresh-id> --output <new-directory>
```

It freezes producer-file hashes, config, grammar and task denominators before
launch, reserves each task, writes neutral provenance, existing offline pools,
official-format submission and a closed file-hash manifest. Missing candidates
use the existing honest submission filler policy. Filler is not solver credit.
There is no solutions/scoring option and existing paths are never overwritten.
The producer-file inventory is not a closed dependency/runtime attestation;
final packaging and interpreter/dependency closure are coordinator-owned.

Only an independent evaluator should run the separate entrypoint:

```
python tools/evaluate_arc_symbolic.py --challenges <same-visible-challenges> --expected-challenges-digest <frozen-digest> --solutions <evaluator-only-source-bound-solutions> --expected-solutions-sha256 <byte-hash> --symbolic-pools <pools.json> --expected-symbolic-sha256 <byte-hash> --output <new-evaluator-directory>
```

Optional baseline pools also require their byte hash; fixed policy is declared
up front. No evaluated rows are written back to solver pools or runtime packages.
The local report contains evaluator-only labels; share only its aggregate brief.
Final public confirmation additionally requires `--purpose
final-public-confirmation --confirmation-lock <coordinator-predeclared-single-lock>`.
That immutable lock is created before opening solutions. The coordinator must
use the same global lock across all configurations and branches; choosing a new
path is not permission for another final comparison. Public exposure remains
explicit. No hidden/official score is calculated by this tool.

## Acceptance still pending

Synthetic operator/isolation coverage is engineering evidence only. E20's
frozen development screen must find correct tests in at least two distinct tasks
and at least one correct task absent from the same canonical neural pool. A
baseline pool with identical full demo/test identities is still required before
complementary coverage can be established. Zero useful standalone or additive
coverage rejects this operator/depth configuration; it does not justify automatic
answer-driven rule additions or extrapolation to official >85.
