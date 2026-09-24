# NVARC source integration, 2026-09-24

This is the local M0/M1 engineering record for the owner-authorized phases
1–3. It does not promote a method, score ARC, or authorize an external run.
The subsequent [M2/M3 bounded development record](m2-m3.md) describes the
actual public ARC-SFT/tiny TRM/SDG sandbox chain and its separate unapproved
4B feasibility and teacher packages; it leaves these M0/M1 source bindings
unchanged.

## Rebuild and boundaries

For a first network acquisition, install `git` and Kaggle CLI/API access in
Python 3.12 and run `python tools/nvarc_source.py materialize`. It clones NVARC at
`846d0198efa752534594e321fc3289fc0a06c657`, initializes its seven direct
submodules and the nested ConceptARC editor, checks nine exact commits, pulls
the pinned public Kaggle notebooks only when their verified local copies are
absent, and checks all pinned bytes. A newer remote current version fails closed.
The
cache lives at `.irisx/arc-agi-2/qwen35-nvarc/source/`, independent of the old
51fa worktree. `python tools/nvarc_source.py verify` is strictly offline.
Default repository tests never download source or install packages.

After a verified acquisition, export a local directory bundle with
`python tools/nvarc_source.py export-bundle --bundle .irisx/nvarc-source-bundle`.
Rebuild into a fresh directory without Kaggle or network access with
`python tools/nvarc_source.py materialize --bundle .irisx/nvarc-source-bundle
--source .irisx/nvarc-source-rebuilt`. The bundle contains the checked source
tree, Git object stores and both exact notebooks; it is ignored local material,
not a redistributable artifact. Every member is size/hash checked before import,
then the reconstructed nine Git checkouts, recursive submodules, notices,
notebooks and bound source files are verified. The actual pinned source was
exported and rebuilt this way on 2026-09-24, returning `source_ready: true`.

The verifier checks each repository's HEAD, index and tracked worktree, rejects
Git assume-unchanged/skip-worktree bypass flags, and inspects untracked and
ignored files. Its only permitted additions are bytecode caches
for the three hash-gated modules that the integration compiles directly from
checked source; untracked Python source, other caches and staged changes fail.
Those bytecode files cannot replace the loaded source. A partial Git clone
cannot always produce a self-contained `git bundle` because historical blobs
may be absent, so the local bundle preserves the verified working tree and Git
metadata instead. The four offline
`tests.test_nvarc_source_materialization` cases cover dirty root/nested
repositories, cache reuse, current-version drift, interrupted and mismatched
notebook writes, clean rebuild and tampered bundle members. This closes F1/F2
from the [independent review](control-review-9198fd4.md) at the tool level.

The [source manifest](source-manifest.json) binds commits, URLs, notebook
versions/hashes, integration source files, and available root license notices.
NVARC itself has no root license at this commit. The notebook pulls do not
state a license; keep those bytes in the ignored local cache. The
[dependency manifest](dependency-manifest.json) distinguishes explicit TRM
requirements from the tested Windows CPU environment. Original NeMo-RL,
Unsloth and Kaggle package versions are not all supplied by upstream.

The Qwen notebook is `sorokin/arc2-qwen3-unsloth-flash-lora-batch4-queue`
version 10, SHA-256 `506b85db66f9949022e87935ccb06a73fd78cb690883bd600bfb5c7d36c2b3af`.
Kaggle's current TRM notebook is `cpmpml/arc2-trm-v31` version 21, SHA-256
`9000b90f61346c1872c0e31056d6beeeb3d19201899dca4f7cd8f3b4e0c8d56dc`.
NVARC's README specifically cites its competition version 18,
`scriptVersionId=278223801`; the Kaggle API returned HTTP 403 for the
historical versioned pull. Version 21 is therefore pinned as available source,
but no version-18 notebook parity claim is made. The pinned TRM Git source
itself is available and executes in the CPU fixture.

The [asset inventory](asset-inventory.json) records six public Kaggle Dataset
versions, purpose, reported size, metadata license and evaluation exposure.
Only metadata/file listings were fetched. The 42 GB reported SDG artifacts,
published augmented data, approximately 2.2 GB reported TRM training Dataset
(its large array members list roughly 39 GB), published TRM checkpoints and
original Qwen3 ARC-SFT model were not downloaded. The pinned 9.34 GB Qwen3.5
base manifest and prior independently verified compact 003 artifact remain
separate. `arc2_evaluation6` and labelled TRM evaluation arrays are excluded
from clean training and outbound material.

## Source to adapter map

| Source entry | Direct use | Qwen3.5/IRIS-X boundary and evidence |
| --- | --- | --- |
| `SDG/scripts/build_datasets.py:fix_settings`, `apply_augmentation`, `get_messages` | `source_sdg_messages` invokes the hash-gated upstream functions, retaining Python RNG state around them | The prior one-pass color map differs from upstream's in-place map for color cycles. The source profile uses the upstream function; differential test records the difference. Teacher calls and generated-program sandbox remain unrun. |
| `ARChitects/run_sft.py:load_datasets` | `source_sft_sequences` executes the original HF loader and consumes original alternating `messages`; a source-derived two-record fixture completes a real tiny Qwen3.5 optimizer step and checkpoint | Grid parsing, 16-row Qwen3.5 mapping and assistant-only mask are adapter work. NeMo's `sft_preprocessor`, packed loss backend and full-SFT execution still require backend compatibility and real data. |
| Qwen notebook v10 `arc_loader.py:ArcDataset.augment`, `forward_mod`, `invert_mod` | `source_qwen_training_views` and `source_qwen_views` call the original adaptation and 8/16-view inference augmentors; candidate source profile uses their transformed demos and grids | Original `hash(task_id)` verification seed is process-dependent; the integrated profile pins an explicit seed. Its long-context `cut_to_len` remains a known difference. |
| Qwen notebook v10 `arc_solver.py:QwenDataCollatorForCompletionOnlyLM`, `turbo_dfs`, `calc_scores` | Hash-gated AST extraction executes the original mask, DFS and NLL functions in differential tests; install/upload/Unsloth notebook cells never execute | A differential failure showed that the original TTT mask includes **every demonstration assistant response**, not only the last held-out answer. The source profile now matches it token for token. Bounded DFS is retained for Qwen3.5 because the original batch KV traversal shares mutable state across branches of a hybrid attention/DeltaNet model. Deterministic logits prove traversal/pruning/completion on the common bounded domain. The adapter uses `use_cache=False` full prefixes; tiny real model tests branch isolation. Source scores use **sum** NLL including EOS, and the source profile now does the same. |
| Qwen notebook v10 `arc_decoder.py:getter_kgmon`, `score_kgmon` | `source-kgmon` ranking invokes the original getter; differential test invokes original top-two selection | IRIS-X retains explicit duplicate vote counts, missing attempts and deterministic tie order. Original code does not report bounded stop reasons. |
| `TinyRecursiveModels/dataset/build_arc_dataset.py:convert_dataset`, `np_grid_to_seq_translational_augment` | `preprocess_source_training_fixture` runs the real pinned builder on locally staged, labelled synthetic training tasks and checks its NumPy output | Solver-visible input remains separate from labelled training arrays. TRM model train/reload/TTT and version-18 notebook inference are not verified. |
| Qwen3.5 `Qwen3_5ForConditionalGeneration` and PEFT | `arc_nvarc_qwen35_adapter.py` owns LoRA target discovery, full-prefix forward and answer NLL; `GridTokenizer(source_chat_newlines=True)` maps original role/newline/EOS grammar | Qwen3 source rows cannot be loaded as Qwen3.5 weights. Compact 003 remains byte-frozen and uses the previous default grammar. Source-compatible training/solve profile is distinct. |
| Existing IRIS-X transport/ledger/checkpoint/evaluator | Reused without a new pilot runner; `resume_digest_member` and `run_utf8_logged_command` add local digest-bound continuation and raw UTF-8 logs | The interrupted-transfer and non-ASCII Windows log regressions pass on synthetic bytes. No external retrieval was attempted, so provider range behavior and a large real artifact remain unverified. Historical run identities, compact conversion and prior result remain unchanged. |

## Local differential results and limits

The checked-in [stage config](configs/source-integration-stage.json) selects
fixture, tiny real CPU, or the already verified 4B compact material through
one `tools/nvarc_source_stage.py` entry and one truth-free result schema. It
calls the existing solver, training, checkpoint and material verifiers. Fixture
and actual tiny-model profiles passed; the 4B profile was not run in this task.

Run `.irisx/nvarc-ml-venv/Scripts/python.exe tools/nvarc_ml_profile.py`.
The strict profile fails on missing source or dependencies and runs the source
suite without skips. On 2026-09-24 it passed 19 tests with zero skips. Its
shared fixtures cover rectangular D4/color and
inverse transforms, demonstration order, two-test tasks, source SFT messages,
role/newline/EOS and assistant-only masks, actual TRM array generation,
source DFS traversal/pruning/EOS with deterministic logits, eight verification
views, source NLL, duplicate votes/top-two, empty candidates, a 1,101-token
path and each explicit bounded stop reason. Tiny real Qwen3.5 CPU forward
checks full-prefix sibling isolation with and without the immutable logit cache.

Existing repository tests cover exact Dataset mount inventory, the `torchao`
removal order, tuple-to-list canonical JSON repair, nonfinite gradient/adapter
reset and task-boundary ledger/resume. `python -m unittest
tests.test_arc_nvarc_transport_io -v` verifies a simulated interrupted
digest-bound member continuation and raw UTF-8 log retention. The source
materializer writes notebooks through a hash-checked pending file and atomic
replacement, so a failed fetch cannot replace verified bytes. Provider range
transport and **large real artifact** retrieval remain unverified M4 work; no
new retrieval was attempted here.

After the F1/F2 repair, `python tools/repository_check.py --all` passed the
offline repository check and 212 unit tests (four existing optional PyTorch
tests skipped under default Python 3.14). The new source-materialization suite
passed all four tests. The strict ML profile again passed 19 tests with zero
skips. `python tools/nvarc_source.py verify` reports nine Git repositories,
two notebooks and nine bound code files; running `materialize` on that valid
cache also passed without Kaggle access. The two transport I/O regressions
passed under default Python.

The original DFS has neither IRIS-X's shape-aware pruning nor its expansion,
sequence and deadline semantics. Differential equivalence is asserted only
where both algorithms accept the same candidate domain and bounds; longer
paths and stop accounting are IRIS-X safety extensions, not upstream parity.
The source's full augmentation schedule and score sum are available through
the source profile; the older default candidate profile is retained for prior
material compatibility. No hybrid KV optimization, packed recurrent masking,
full ARC-SFT checkpoint, real SDG teacher, or TRM GPU model artifact was
produced in these phases.
