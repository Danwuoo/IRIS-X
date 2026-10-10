# Consolidated offline ARC research

IR v2, native path guard, with the 2026-10-10 tokenizer/output repair.

Current repair: **287 Linux tests and 1,152 actual-notebook CPU SMOKE checks pass**.
See [repair diagnosis and safe rerun instructions](REPAIR-20261010.zh-TW.md).
The G4 tokenizer return type and oversized stdout defects are corrected; actual
Granite tokenizer/weights/GPU execution remains unverified. Historical v4 and v2
scientific receipts retain their original identities.

This additive successor combines independent controls, exposed-demo coverage,
ordering diagnostics, and gated model studies in one notebook. It accepts only
`task_id` and `demos` containing `input`/`output`; it has no test/query evaluator.
The scientific/model path never semantically reads queries, gold or solutions.
An isolated integrity child streams all runtime bytes, including evaluator
members, solely for hashes and returns aggregate proof. Evaluator paths,
per-file gold hashes and evaluator content never go to the model.
Historical N5-N14 scientific programs and the
original N14 gate remain unchanged. Demo-fit is engineering evidence about
expressibility on exposed demonstrations, not generalization or promotion.

This release is validated on Linux CPU with independent controls and exposed-demo
coverage. The G4 model path is implemented but requires later real-asset and GPU
acceptance. The owner approved Git and private, inactive Kaggle publication after
review. That approval does not start a GPU run, training, paid VM or competition
submission. Publication receipts are recorded separately after acceptance.
See [VALIDATION.md](VALIDATION.md) for version-specific results and limits.

## Notebook configuration

The default switches are `MANUAL_START=False`, `ENABLE_MODEL=False`,
`PROFILE='SMOKE'`, and `RESUME=False`. Running all cells with those defaults
performs no source writes, installs, Dataset scans, model/tokenizer imports,
torch import, loading or GPU work. Manual CPU activation extracts only the
embedded trusted package after closed-inventory and byte-hash verification.
Changed files, symlinks/junctions and conflicting imported `tools` modules fail
closed. Embedded candidate programs remain AST data for the bounded VM.

Use a new `OUTPUT_ROOT` for a new run or profile. A SMOKE identity cannot become
a FULL run, and its model gate never opens. Model configuration is only:

```python
MODEL_CONFIG = {'input_root': '/kaggle/input', 'explicit_roots': {}}
```

`explicit_roots` can optionally identify existing absolute Linux mount roots
for `runtime`, `model`, `wheels`, `interpreter`, and `adapter`. It cannot replace
their version/manifest pins. There are no manual model, environment-lock or
runtime-manifest path/hash fields. Configuration validation is pure: it does
not inspect the filesystem or import model/runtime helpers. Before any extraction
or output write, a shared guard rejects equality or either ancestry direction
between every declared input root and source/cache/output/derived-environment
paths. Traversal, ambiguous aliases and write-side symlinks/junctions fail closed.
CPU planning does not stat or scan declared Dataset roots. Therefore input-side
symlink aliases and bind-mount equivalence cannot be discovered by that lexical
check; post-gate asset checks remain required, and declared mounts must be
accurate.

## Fixed scope and budgets

| Phase | Fixed work | Ceiling |
| --- | --- | --- |
| CPU SMOKE | 128 candidates x 8 demo sets, plus 128 controls | 1,152 checks; 300 seconds; model gate always closed |
| CPU FULL | 5,965 candidates x 8 demo sets, plus 128 controls | 47,848 checks; 1,800 seconds |
| FULL model study | One seed block: 16 shared roots, 32 true/redacted feedback calls, 32 frozen-parent memory-off/on calls | 80 physical calls and up to 80 response-verifier checks |
| Fresh search | 3 arms x 3 seeded tie orders x 8 tasks x 64 expansions | 4,608 verifier checks; no added model calls |

The controller allows at most four isolated verifier workers. Each check has
200,000 gas shared across its demos, 2 CPU seconds, 3 parent wall seconds and
256 MiB address space. FULL's total reservation is 52,536 physical verifier
checks and 10,507,200,000 gas. Each model call allows at most 6,144 prompt
tokens, 2,048 new tokens and 8,192 context tokens, with a cooperative 120-second
call limit. Shared physical generation cost is charged once; arm attribution
is reported separately. Memory pairs retain the same frozen parent/history
and change only memory content.

The v2 core has 5,965 unique canonical plans: 1,277 legacy, 1,820 object unary,
280 crop/D4 compositions, 1,300 anchored recolor, 1,280 Boolean equal-panel, and
8 panel-copy plans. The dead `same_normalized_mask` anchor relation was removed
from both enumeration and the legal proposal language. Anchor and focus
selectors see the complete original partition; the anchor is then excluded
from selected focus objects. This does not add a next-smallest/largest rule.
Literal backgrounds outside the core remain legal proposal parameters.

The 64 positive controls use an independent trusted Python reference. Their
64 semantic negatives keep the exact same task inputs and expected outputs
but use legal wrong programs with recorded mutations and mismatching demo
indices. The earlier 64 target-mutant checks are separately available through
`detector_controls()` and do not count toward the required 128 gate controls.

Only complete FULL base coverage can open the testability gate: all 64 positive
and 64 semantic negative controls must meet expectations, the physical ledger
must be complete, and at least two of the eight engineering tasks must have a
base-inventory demo-fit. Root proposals cannot repair this gate retrospectively.
SMOKE, unknown checks or unvisited candidates cannot establish no-witness.
Reports retain the full eight-task denominator and witness-feasibility strata.
Cached ordering diagnostics are separate from fresh physical search checks.

After the gate, each task may add at most two legal root plans, admitted by the
full compiler. The pool cap is 5,967. All three ranking arms use the same
pool/hash and fixed seeded tie order, with receipts for duplicates,
out-of-domain plans and overflow. This finite inventory is not the complete
IR or Python language.

## Automatic offline model preparation

Automatic preparation occurs only after `PROFILE='FULL'`, a passed complete
base gate, and explicit `ENABLE_MODEL=True`. CPU/inert and pre-gate paths do
not scan model Datasets, install packages, import model dependencies, or load
tokenizers/weights. The post-gate bootstrap resolves these exact assets:

| Role | Pinned private Dataset version |
| --- | --- |
| Runtime | `danielwuu/iris-arc-next-runtime/8` |
| Model | `danielwuu/iris-arc-granite42-8b-offline/2` |
| Wheels | `danielwuu/iris-arc-next-cu128-cp312-wheels/1` |
| CPython | `danielwuu/iris-arc-next-cpython312-offline/2` |
| Adapter | `danielwuu/iris-arc-granite42-run003-adapter-20261009/1` |

The bootstrap checks pinned manifests and actual member bytes, prepares the
offline CP312 environment in supervised children, and then starts one persistent
model-owner process in that pinned environment. The owner is shared across
study arms; the old suite launcher is not called repeatedly. Runtime integrity
checks stream evaluator members only as opaque bytes for hashes and return
aggregate proof; they send no evaluator paths, per-file gold hashes or content
to the model. A mock
manifest or synthetic matching fixture cannot certify mounted runtime8 bytes,
the actual environment, or GPU startup. Independent Linux review verified the
actual retained runtime8 bundle (34 payload files) by opaque byte hashes only.
The other four real mounts, installation, tokenizer, weights and G4 execution
remain unverified. Four-L4 deployment is a separate unvalidated profile.

## CPU execution and evidence

Use an existing Linux environment with the required `resource` limits:

```python
from tools.arc_consolidated_20261010.runner import run

result = run(
    './.irisx/consolidated-runs/smoke-001',
    manual_start=True,
    enable_model=False,
    profile='SMOKE',
)
print(result['status'], result['archive'])
```

This does not load a model or claim runtime8 mount acceptance. Windows can run
portable schema/compiler/reference/ledger/mock tests, but its real verifier
fails closed without Linux resource enforcement. No fallback removes those
limits. FULL may not finish within 1,800 seconds; its remaining checks must
stay partial/inconclusive rather than silently extending the budget.

The ledger fsyncs a reservation before dispatch, uses an OS controller lock,
and retains immutable responses and a hash-chained journal. Resume requires
the same source/task/model/prompt/sampling/budget/config bindings and explicit
`RESUME=True`. A missing response is unknown, consumes the full reservation,
and is not resent. An available response can receive separately charged CPU
verification. Truncated journals and orphan responses fail closed.

Each session has a fresh monotonic deadline and persistent consumed wall.
`SESSION_SECONDS=None` defaults to 600 seconds for SMOKE or 7,200 for FULL,
separate from the CPU-phase limits. The whole workflow allows 14,400 seconds,
including source setup, installation, model loading, verification, export and
archive work. Deadlines govern admission/cooperative stopping; cleanup can
overrun. Stage snapshots preserve completed work and failures. Global sealing
requires stop evidence for owned verifier children and the model owner.
Program return or archive completion does not stop VM billing.

## Source assembly and checks

Run portable tests from the repository or extracted portable-package root.
Use an existing real, non-symlink Python 3.12 executable. Strict remote-owner
fixtures reject symlink interpreters; resolving an existing executable is an
invocation precondition, not permission to weaken path checks:

```sh
"$(python3 -c 'import os,sys; print(os.path.realpath(sys.executable))')" -m unittest discover -s tools/arc_consolidated_20261010/tests -t . -p 'test_*.py' -v
```

Only after reviewed sources are stable, assemble the final notebook:

```sh
python3 -m tools.arc_consolidated_20261010.build_notebook
```

The builder embeds package Python, frozen demos/provenance, the pinned legacy
VM/compiler/bootstrap helpers and pinned optional model helpers. It excludes
tests, outputs and its own source. Record the resulting notebook and source
hashes and rerun inert checks before distributing it. The final native guard
revision has a rebuilt notebook and independently checked inert defaults; see
VALIDATION.md and validation/release-validation.json for exact identities.
