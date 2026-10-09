# Trusted typed IR and synthetic F/G/P/R curriculum

This component implements N7/N12/N13 only. It never imports ARC tasks or labels,
trains a model, loads a GPU, publishes data, or executes generated Python through
host `exec`, `eval`, or compilation. Candidate source is interpreted by the same
reviewed `arc_program_v2.verify_program` / pinned `arc_bounded_v2.py` pair.

## Integration API

- `parse_plan(text) -> plan`: strict JSON, maximum 4,096 UTF-8 bytes, exact keys,
  one to three steps, duplicate-key rejection, no booleans-as-integers, floats,
  nonfinite numbers, unrecognized operations or parameters.
- `compile_plan(plan) -> source`: fixed templates only, at most 32,768 UTF-8
  bytes and 2,048 AST nodes. No caller text is interpolated except validated
  bounded integers. Returns raw `def transform(grid):` source.
- `grammar_candidates() -> list[dict]`: each entry contains `id`, `ordinal`,
  `plan`, `production_ids`, and `program`. The key is **id**, not candidate_id.
- `production_ids(plan) -> list[str]`: length, operation and typed parameter
  productions, including multiplicity.
- `order_candidates(proposals, mode='uniform'|'smoothed'|'hard_pruned', alpha=1)`:
  returns entries with `prior_weight`; at most four valid shared proposals.
  Alpha is bounded to 1e-6..1000 to retain numerical positive support.
  Malformed proposals must be explicitly accounted for/filtered by the caller.
  The parent owns CPU search, candidate execution, budgets and selection.
- `grammar_manifest()`: frozen inventory digest and the finite coverage ceiling.
- `plan_contract()`: model-facing strict typed-plan instructions.
- `fresh_verifier(agent_path, verifier_path=None)`: actual fresh, OS-limited
  subprocess adapter; both interpreter and wrapper bytes must match frozen
  SHA-256 pins. The wrapper defaults to the interpreter's sibling
  `arc_program_v2.py`. Captured source is loaded through a cache-bypassing loader,
  so matching-timestamp substituted pyc files cannot impersonate the wrapper.
- `make_curriculum(output, verify_fn, seed=1015, episodes=512,
  max_verifications=1024, wall_seconds=1200, family_split=None) -> manifest`:
  writes `episodes.jsonl` and `manifest.json` to a new directory, returns the
  JSON-serializable manifest dictionary. The verifier must accept
  `verify_fn(source, task, timeout_seconds=...)` and expose the truthful
  `provenance` dictionary supplied by `fresh_verifier` (or the suite's pinned
  equivalent). It must use fresh bounded workers; no direct interpreter adapter.
- `known_witness_coverage(verify_fn, output=None, wall_seconds=120)`: executes 171
  CPU witnesses, covering all 137 atomic parameterizations and 34 distinct
  two-operation classes. The reference formulas are independent trusted code.

## Operation semantics and finite search scope

Identity; horizontal column reversal; vertical row reversal; clockwise rotation
by 1/2/3 quarter turns; transpose; one-color recoloring with distinct colors
0..9; nonbackground bounding crop with specified background 0..9; nearest-
neighbor scale by 2 or 3; rectangular tiling with axis repeats 1..3 (not both 1);
largest same-color 4/8-connected component's bounding crop with background 0..9.

Crops retain every original pixel inside the selected rectangle. Empty
foreground returns a copy. Largest-component ties select the first row-major
component. Scale/tile are partial transformations: intermediate axes above 30
fail at the bounded `new_grid` primitive. All operations remain subject to the
shared 200,000-step verifier budget; valid IR is not a promise of execution on
every input shape or a promise of ARC semantic coverage.

The N7 interface accepts up to three steps. N12 intentionally searches a smaller
declared language: 137 atomic candidates and 1,140 two-step compositions, totaling
1,277. Compositions cover geometry/geometry, geometry/recolor in both orders, and
background-zero crops followed by geometry or scale. Behaviorally equivalent
programs remain separate syntactic candidates. IDs hash canonical plans. The
fixed breadth-first order interleaves atomic parameterizations by operation kind
so early budgets include every primitive family.

Uniform assigns equal candidate mass. Smoothed feature-prior ranking starts from
that uniform candidate base and multiplies smoothed production likelihood ratios
relative to the zero-observation production prior, then normalizes. An empty
proposal pool therefore recovers uniform weights and ordering exactly. Its mass
is positive for every candidate; observed repeated features can still affect
ranking. This is a feature-prior ranking heuristic, not a full PCFG probability.
Hard-pruned mode requires every production to occur in the proposal pool and can
have empty support. Fixed ordinal breaks score ties. No candidate is executed
when computing priors. Equal ceilings do not imply equal realized compute.

## Synthetic curriculum and objective separation

Exactly 64 augmentations of each of eight authored families yield 512 episodes.
Family assignment occurs before all seeded augmentation:

| Train (384 episodes) | Validation (128 episodes) |
| --- | --- |
| mirror_columns | transpose_then_replace |
| clockwise_quarter_turn | largest_object_box |
| replace_marker | |
| remove_background_border | |
| nearest_neighbor_double | |
| repeat_columns | |

Each episode has two independently generated demo grids and an independently
generated query grid, with distinct seed namespaces and checked distinct inputs.
The explicit family formulas author outputs separately from compilation.

- F: verbatim raw-source copying of a supplied program. Its target and target
  format exactly match P and R, making it a format-only control for raw-source
  program objectives. The entire solution program is supplied in F's input;
  semantic induction is neither required nor claimed.
- G: query-grid target from visible demos plus query input.
- P: bounded-program target inferred from the same visible task.
- R: repair target from the task, valid-but-wrong mutated program, and actual
  visible-demo mismatch feedback. No query target/error enters repair input.

Every record stores separate inputs/targets. Witness and repair sources are
byte-identical; one successful fresh-worker call certifies both against demos
and the independent query target. A second fresh-worker call must admit and
successfully execute the mutation, then report `demo_mismatch`. Syntax/runtime
failure is never labeled semantic failure. Thus the frozen export uses exactly
1,024 fresh calls, rather than claiming three verifications while budgeting two.

Exports have source/compiler/interpreter/verifier hashes, grammar and split
digests, witness hashes, seed provenance, objective fields, and actual gas/wall
accounting. A complete final directory appears only after every episode passes.
Every attempted verifier call first reserves 200,000 steps. Valid returned usage
replaces that reservation immediately, before deadline or semantic validation.
Exceptions, interruption and malformed usage retain conservative reservations.
Both success and failure outputs include a hashed per-call verification ledger;
failure summaries preserve attempted, returned and unknown-usage call counts,
including CPU work from rejected witnesses and mutations.
Existing exports cannot be overwritten. Failures leave clearly marked staging
diagnostics, not completed datasets. Source changes during generation fail
closed; elapsed wall limits include final export preparation. Operational timing
is excluded from deterministic JSONL payloads.

This is synthetic family holdout, not an ARC holdout or unseen-primitive split.
Primitive overlap is intentional. This work demonstrates executable authored
targets and known-witness grammar membership, not model learning or quality gain.

## Reproduce CPU checks

From the suite parent directory, put this component and suite `src` on PYTHONPATH:

```sh
PYTHONPATH=components/typed_ir:src python -m unittest -v test_typed_ir
```

The full-export test expects `evidence/curriculum-512-reviewed` and the separate
known-witness report. Use `fresh_verifier('src/arc_bounded_v2.py')` with
`known_witness_coverage` and `make_curriculum` to create new, nonexisting paths.
Modules perform no tests, installation, file writes or generation at import.

Earlier `evidence/curriculum-512` and `evidence/curriculum-512-frozen` are
superseded development evidence. The former has a stale inventory-order digest;
the latter predates the failure ledger, cache-safe adapter and matched raw-source
F objective. Their successful CPU execution remains historical evidence, but
neither is the final bound export. Use only `curriculum-512-reviewed` and
`known-witness-coverage-reviewed.json`. Payload changes from the earlier runs
are intentional because F now uses the same raw-source target format as P/R.
