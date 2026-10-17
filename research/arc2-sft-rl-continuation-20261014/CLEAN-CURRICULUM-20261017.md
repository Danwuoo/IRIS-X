# Clean synthetic curriculum: offline RE-ARC preparation

Status: next-iteration source only, 2026-10-17 UTC. This does not change the
immutable v50 AF3/SFT/TTT run, its training inputs, or its result interpretation.
No GPU run, remote Dataset, model download, publication, or score is introduced
by this implementation. Generated corpora and producer snapshots stay ignored
under `.irisx/`.

## Source investigation and choice

Read the official repositories and inspect source before executing any selected
code. Source-only sparse checkouts did not materialize the upstream generated
corpus or original ARC ZIPs. No package installation was needed.

- [Google ARC-GEN, pinned a15cbdb44c776610aeeb9f487a06af875d3d0878](https://github.com/google/ARC-GEN/tree/a15cbdb44c776610aeeb9f487a06af875d3d0878)
  is Apache-2.0. Its 900 task modules include 710 current training parents,
  181 development parents, and 9 parents outside this 1000-parent inventory.
  None shares a protected PUBLIC120 ID. The inspected CLI's `validate` operation
  checks reproduction of original examples; it is not an independent solver
  verification of every fresh generated pair. That validation path was not run.
- [Michael Hodel RE-ARC, pinned e5b7f1d06362a76f9d3b8c25154ff1fafca897ce](https://github.com/michaelhodel/re-arc/tree/e5b7f1d06362a76f9d3b8c25154ff1fafca897ce)
  is MIT, copyright 2024 Michael Hodel. Its 400 explicit generator/verifier
  pairs include 309 current training parents, 82 development parents, and 9
  parents outside the inventory. There is no protected PUBLIC120 ID overlap.
  RE-ARC is the first implementation because each sampled output can be checked
  by its corresponding real upstream `verify_<parent>` program. This sacrifices
  coverage relative to ARC-GEN rather than making unverifiable correctness claims.

RE-ARC execution pins these exact file SHA-256 values:

| File | SHA-256 |
| --- | --- |
| LICENSE | `60ea7c0edc4c765357257e31ad7c5f7d3ba7007329703d1fcfc3abbcbbd36efd` |
| generators.py | `1f598cb13c9c7b223181ab35485ca77d9079b600ee3baef1bce750db71248726` |
| verifiers.py | `e11c1ceed68ddb87fa544e3504f06d677c59698669a680e8124717f7703d80a1` |
| dsl.py | `c60faf5730a966fc1689c08bc96794cd97fd0311b8036e0f9b0c80e2d12f0f11` |
| utils.py | `48e11e45f804a37fcb0e62005c879ece7d5f0e1593d3fd53f5f978d31666540a` |

ARC-GEN inspection anchors: LICENSE SHA-256
`c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4`,
CLI `14550a131a0a7ffdf8e57df66a4c9ac4b126249ddeb4b2468553a58494935e30`,
task list `98aa515236a096bc75c013bd60cbe0a62d3b823b92c6bc754fdf3148d6748d0d`,
and common helpers `56f9be46fc563f2754c3d506ff0d4aa8fa97c181c1c6db209a21ffd4707b9bc9`.
ARC-GEN is not executed or packaged by this first curriculum.

## Strict lineage and truth separation

`tools/arc2_goal_sprint_20261017/curriculum.py` uses the existing `load_data`
production path. It binds training manifest SHA-256
`a4b9da04d8690c57a3d0855553989fa055c5b9283ffc1784fe99413c8d1cb9d5`, the
exact existing admitted 800/200 ID digests, and the exact solver-only
PUBLIC120/167 digest. The pinned protected IDs equal the solver-only PUBLIC IDs.
The current material yields 800 training parents, 200 development parents, and
no source-task exclusions from the existing load_data checks.

Every descendant retains its explicit original parent ID and inherits only the
admitted training split. All 200 development parents, all 120 protected PUBLIC
parents, and all unknown parents are refused before generator execution.
Changing grids or giving a descendant a new task ID never changes its lineage.
The consumer repeats these checks against current admission; generated records
are never randomly split into training and development.

Before hashing PUBLIC provenance, reject query records with anything other than
an input. No evaluator path is accepted. No PUBLIC query answer file is opened.
Existing `known_variant_group` checks D4/color-renaming/demo-shuffle invariants
against whole PUBLIC demonstration tasks and individual demonstration pairs.
Any matching generated pair rejects its entire bundle. Repeated generated
bundle invariants, repeated inputs within a bundle, and identity examples are
also excluded. These are conservative known-overlap checks, not semantic
independence or proof that an upstream verifier is mathematically correct.

Explicit synthetic-fixture admission exists only for offline unit tests. Its
mode is recorded in the artifact and the production loader refuses it by
default. Production CLI has no fixture switch. Direct library admission checks
its own ID-set and signature bindings, not just the dataclass's frozen flag.

## Generator execution and reproducibility

Five source files are hash-checked before use. Only the selected parent's exact
generator/verifier AST, exact DSL, and the original `unifint` and standard-library
random imports execute. There is no import of upstream plotting, `main.py`,
`demo_generator`, original-task loaders, or `fix_bugs`; no upstream training/test
example reconstruction path is used. No matplotlib installation is needed.

Each bundle has 3–6 examples, default four. Each grid must be rectangular,
1–30 by 1–30, integer colors 0–9, with no booleans. The upstream verifier must
return exactly the generated target. Default bounds are 40 attempts per bundle,
2 seconds per generator/verifier attempt using POSIX interval timers, and
30 seconds for the entire fresh worker subprocess. Timeouts/errors/duplicates
are retained as rejections. Incomplete bundles are not training examples.
The default curriculum is small; hard limits allow at most 5000 bundles and
128 MiB of final corpus bytes.

Seeds derive from the global seed, original parent ID, bundle index, and attempt
index using SHA-256. Each worker starts with `PYTHONHASHSEED=0`; caller RNG state
is not modified. Canonical JSON contains no elapsed-time fields. Python version,
source-file hashes, exact generator/verifier function-segment hashes, per-example
seeds, target hashes, and attempt outcomes are retained. Successful generation
is byte-reproducible with the same Python/source/configuration and no differing
timeout decisions; near-boundary wall-clock timeouts can differ between hosts.
These trusted-source worker deadlines are not claimed to be an OS sandbox.

## Artifact and consumer API

A corpus is a new non-overwritable directory containing:

- `manifest.json`: compact canonical config, source/producer provenance, exact
  current admission binding, parent lists, requested parents, bundle index and
  counts. The caller retains its external SHA-256 seal.
- `bundles/<task_id>.json`: explicit parent, train split, 3–6 demonstrations,
  generator/verifier identity, hashes and seeds. There is no test field.
- `provenance.jsonl`: exactly one ledger entry for every requested parent/bundle
  slot, including rejected slots and verified per-attempt example hashes.
- `LICENSE`: the exact upstream MIT text, hash-bound and verified on consumption.

Every file is size/hash checked. The loader refuses changed seals, stale
admission, unexpected files, symlinks, traversal, partial bundles, changed
lineage, broken seed/hash evidence, and PUBLIC known variants. It returns
parent-indexed bundles, not a flat synthetic dataset:

```python
from tools.arc2_goal_sprint_20261017.curriculum import (
    Admission, GenerationConfig, load_admission, prepare_curriculum,
    load_curriculum,
)

# In an existing run which already called load_data:
admission = Admission.from_load_data(training, dev, public, data_receipt)

# Offline preparation from already-materialized, exact pinned source:
seal = prepare_curriculum(
    source_root, new_output_root, admission=admission,
    config=GenerationConfig(bundles_per_parent=16, examples_per_bundle=4),
)

bundles_by_parent, receipt = load_curriculum(
    new_output_root, admission=admission,
    expected_manifest_sha256=seal["manifest_sha256"],
    expected_producer_hashes=package_pinned_producer_map,  # optional extra binding
)
```

The external manifest seal already binds the historical producer implementation
hash map. The optional explicit map lets the package independently enforce that
identity. The loader does not equate historical producer hashes to unrelated
current consumer encoding code, so adding an output-mask encoder cannot force
regeneration. Current admission, lineage, bytes and invariants are always
rechecked. Changed producer expectations or external seals fail closed.

For integration, choose uniformly among original training parents first. For a
parent with available generated bundles, choose original demonstrations versus
one generated bundle at 50/50, then select a bundle within that parent. Parents
without admitted generated bundles use their original demonstrations. Do not
sample uniformly from all original and generated task IDs, which would heavily
overweight the 309 RE-ARC-covered parents. Do not send generated descendants to
dev or use PUBLIC feedback to admit or select them. Packaging/sampling integration
is deliberately separate from this file and has not been applied to v50.

Production CLI is offline and actually re-runs load_data validation:

```sh
python -m tools.arc2_goal_sprint_20261017.curriculum prepare \
  --source-root /absolute/pinned/re-arc \
  --training-root /absolute/training/data/training \
  --training-manifest /absolute/training/manifest.json \
  --public-challenges /absolute/public/public-challenges.json \
  --output /absolute/new-corpus --bundles-per-parent 16 --examples-per-bundle 4

python -m tools.arc2_goal_sprint_20261017.curriculum validate \
  --training-root /absolute/training/data/training \
  --training-manifest /absolute/training/manifest.json \
  --public-challenges /absolute/public/public-challenges.json \
  --output /absolute/new-corpus --manifest-sha256 EXTERNAL_SEAL
```

## Validation and bounded production preparation

The focused suite has 31 tests, all passing with normal and optimized Python,
including real official-source generator/verifier execution when the separately
materialized source is explicitly provided by `IRISX_REARC_SOURCE`. Default
public tests do not download source; that one integration test is then an
explicit skip. Only the three real POSIX worker/timer tests carry Linux
capability metadata; portable schema, admission and integrity tests still run.
Independent parent review identified and corrected license retention,
self-consistent Admission validation, portable-test marking, and separation of
sealed producer identity from unrelated current consumer encoding.

The final frozen-producer 16-parent/64-example production-admission smoke
completed with all 16 bundles admitted in 13.02 seconds, with 112,867 artifact
bytes. Actual source admission took 9.87 seconds. Its external manifest SHA-256
is `9ce8101e3a6b1adb43d988c8eae6669f6ff395f14554730418e60ccac584071d`.
The retained ledger includes a real verifier mismatch which was rejected before
a later valid sample completed that bundle. These CPU results prove
preparation/verification, not training benefit or a PUBLIC score. Earlier smoke
identities remain separate and unchanged.

A frozen producer snapshot was prepared for the separately authorized local
309-parent × 16-bundle × 4-example preparation. It contains 126 inventoried files,
2,875,016 bytes, and its canonical inventory SHA-256 is
`177b4831675c67d82f6a902e754543dc415b9e1869926ae2f4d4f4ccabf4e763`.
Workers use that snapshot and a frozen copy of the five pinned RE-ARC files, not
the mutable shared worktree. The snapshot runner first completes a fresh bounded
smoke, then requests at most 4944 bundles / 19,776 examples. Durable progress
logs distinguish worker-verified candidates from final post-dedup admission.
Final artifact counts, byte seal, rejected/timeout ledger and measured duration
must be read from the completed receipt; starting preparation is not completion.
No remote upload or training is part of this local preparation.

## Completed local preparation r2

The first long preparation lost its executor session after 149 workers; it had
no terminal result or admitted corpus. Its partial bytes were preserved, not
relabelled as complete. A fresh r2 used the same frozen producer and independent
output identity. It completed generation plus the full production consumer
readback on 2026-10-17 UTC:

- 309 admitted training parents, 4,944 complete bundles, 19,776 examples.
- 31,725,378 total artifact bytes; manifest SHA-256
  `d67955f333369292a0ad523625fecbd96c108c04865944bd300dc5400370ada8`.
- 3,986.702 seconds for production generation and final readback, excluding
  the separate smoke. This was CPU preparation, not GPU training time.
- The complete attempt ledger records 19,776 verified examples and rejected
  attempts: 239 identity pairs, 584 generator/verifier mismatches, and 18
  generator/verifier errors. Those rejected attempts are not training examples;
  later valid attempts completed each of the 4,944 requested bundles.
- All 200 development parents, protected PUBLIC parents, unknown parents and
  known PUBLIC demonstration variants remain excluded by the same admission.
  The exact MIT license is retained. This is not a semantic-independence proof.

The generated corpus remains private and local. A source-package/transport
readback is a separate step; no Dataset upload, new notebook dispatch, model
training benefit or PUBLIC score follows merely from this successful preparation.

The separate local-only package smoke subsequently passed: 5,009 exact
source/material files, an 11,615,111-byte opaque transport, and a second complete
production consumer admission of the same 4,944 bundles. No adapter was resumed,
base model loaded, evaluator opened, Dataset uploaded, or notebook dispatched.
Its source receipt explicitly records a dirty development worktree; it is a
packaging proof, not an immutable release or a replacement for v50. Rebuild from
the final committed source and reconcile fresh remote identities before any
future dispatch. The curriculum manifest pin above is independently reusable.
