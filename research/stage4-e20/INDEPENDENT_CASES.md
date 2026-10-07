# E20 independent synthetic witnesses

2026-10-06, Python 3.12.14, focused offline CPU validation.

## Result and independence

`tests/test_arc_symbolic_independent.py`: **36 tests PASS**, 0 errors/skips,
0.233 seconds in the final focused run. No implementation edits or commits were
made by this validation worker. Expected outputs are literal grids or elementary
synthetic constructions fixed before solver calls. No candidate-derived gold,
evaluator datasets, pretrained model, GPU, or network was used.

The two full-grammar search witnesses use independent demonstration and test
shapes: rectangular quarter-turn geometry, and largest-component cropping with
an unseen position/color/shape and distractor. The tests require the prewritten
target to occur in the candidate pool and replay candidates against every
demonstration. They establish finite synthetic behavior, not benchmark quality,
candidate ranking accuracy, or official-scoring readiness.

## High-signal coverage

- Literal asymmetric D4 targets, including rectangular `rot90` as CCW.
- Local object anchors, nonzero/tied backgrounds, scale replication, pixel-count
  selection versus bounding-area selection, row-major ties, same-color 4/8
  connectivity, selected-object union crops, recoloring, and monochrome fills.
- Equal-color overlap acceptance; different-color collision, clipping,
  overlarge crop union, empty crop, malformed grid/AST, and test-truth rejection.
- All-demo fit honesty with contradictory outputs for the same input.
- Distinct demo-fitting programs disagree on asymmetric test inputs. Perfect
  3/3 leave-one-demo-out support likewise retains test ambiguity; scoring and
  native verification remain explicitly absent.
- LOO excludes the held demonstration, creates fresh folds, and reports null
  support when the shared task budget prevents completing all folds.
- State/cache prefix limits and wall-cutoff clearing of an already-found pool.

The crucial two-step dedup witness has a reflection-symmetric demonstration
with two identical singleton objects. Asymmetric tests instead have two colors.
Reflection changes the first row-major component, then smallest-component crop
selects it. This composition does not commute with selection, so demo-only
state dedup loses a genuine test-distinct candidate even though one-step fits
are checked before dedup. Tiny production-macro subsets isolate this invariant.

Background is intentionally recomputed at each macro: after cropping
`[[2,2],[2,0]]`, 2 is the new background, and `recolor:4` yields
`[[2,2],[2,4]]`. This potentially surprising composition is explicitly tested.

## Negative mutation controls

Three separate in-memory mutations each caused exactly one assertion failure
and zero test errors in its targeted independent witness:

1. Change semantic signatures to serialize only the first grid: the two-step
   test-distinction witness fails.
2. Change fit comparison from all demonstration outputs to the first output
   only: the contradictory-demonstrations witness fails.
3. Change component-size ranking from pixel count to bounding-rectangle area:
   the independent largest-component witness fails.

The source file was never mutated for these controls.

## Reproduction and bindings

Run from the solver checkout:

```sh
PYTHONPATH=src PYTHONHASHSEED=0 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
HF_DATASETS_OFFLINE=1 CUDA_VISIBLE_DEVICES= \
python -m unittest discover -s tests -p test_arc_symbolic_independent.py
```

Validated SHA-256 bindings:

- DSL source: `20ca0051466e71dbd7aceb099312828db996aaf4b2031139856e0ff3ffffd8f3`
- Independent test file: `6a860b51bdc2f1d0181a198cdf45600e7f85b4e1ee36289fa424c26f5df32101`

Search semantics use a deterministic fake clock to avoid host-load-dependent
cutoffs. This is not physical process-wall, CPU/memory attestation, full-suite,
GPU, evaluator-isolation integration, or real ARC generalization evidence.

### Parent regression after the independent source snapshot

The source hash above binds the independent worker's original snapshot, before
parent extraction-cache reuse and serialized candidate-cache accounting repairs.
The same 36 independent tests were rerun with 19 implementation/interface and 29
existing interoperability tests against the final pre-screen source: 84 PASS,
zero failures/errors/skips, with ResourceWarning promoted to errors.
`CPU_VALIDATION_001.json` binds that final source, command and actual 1.061-second
unittest interval. These measurements do not establish public quality.
