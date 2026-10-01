# Isolated original NVARC material preparation

Date: 2026-10-01 (Taipei). Scope: local CPU preparation under
[Decision 0050](../../docs/decisions/0050-separate-original-nvarc-reproduction.md).
The [distinct corpus contract](configs/original-corpus-contract-20261001.json)
preserves the six original training sources and the separate validation source.
The previous clean outputs, 20260930 method contract and executed identities
are unchanged. Full material freeze and independent verification are complete.

## Full material freeze

Local corpus: `.irisx/nvarc-original/materials/corpus-20261001-001`.
Its closed material tree is 12,347,686,344 bytes. Manifest SHA-256:
`63277d77d2af04e2aba487e5a69f64df5113d2d12bc66a449232e1ac70fa6eff`.
Contract SHA-256:
`9f093d463cac15e002256126ce678bdba4ca213b0d2dcbd2a472a0afc95eb576`.

| Split/source | Retained records | Compact input tokens | Compact supervised tokens | Maximum compact length |
| --- | ---: | ---: | ---: | ---: |
| train: arc2_training | 155,904 | 283,630,722 | 127,215,634 | 9,330 |
| train: mini | 37,632 | 11,252,736 | 5,114,880 | 594 |
| train: concept | 40,960 | 53,247,797 | 23,011,892 | 3,140 |
| train: rearc | 102,392 | 397,172,478 | 177,464,521 | 11,170 |
| train: nvarc_training | 1,132,633 | 3,584,972,780 | 1,545,483,054 | 11,196 |
| train: nvarc_full | 1,785,960 | 7,179,544,749 | 3,192,617,078 | 11,196 |
| **training total** | **3,255,481** | **11,509,821,262** | **5,070,907,059** | **11,196** |
| validation: arc2_evaluation6 | 720 | 2,418,486 | 1,072,701 | 9,702 |

All 1,785,960 `nvarc_full` records retain an ARC evaluation ancestor. Of them,
279,322 also have a protected development/holdout ancestor or visible duplicate
family; these simultaneous exposures remain explicit. Original validation is
therefore an exposed source-recipe validation set, not a fresh evaluation claim.
No old locked evaluator answers are opened to compute these ancestry tags.

Length accounting confirms 47,892 training records and 12 validation records
exceed 8192 compact tokens; all remain intact. Training length percentiles
(higher quantile) are p50 3,412, p90 5,826, p95 6,596, p99 9,020 and p99.9 11,196.
All 120 original validation parent IDs also occur among training ancestors.
Derived metadata is retained at
`.irisx/nvarc-original/manifests/length-accounting-20261001-001.json`, bound to
the corpus manifest and the local procedure SHA. These are ancestry/length
statistics; no prediction or expected-answer comparison is performed.

Preparation log: `.irisx/nvarc-data/original-preparation-001.log`.

## Independent verification and readiness

Report: `.irisx/nvarc-original/manifests/corpus-verification-20261001-001.json`.
SHA-256: `78a185d32e1372fde8cd7f73f6f07f45bb60a4537e1c4eaf5ca6480cf90aaa69`.
Every one of the 3,256,201 source rows was rechecked for role/grid grammar,
compact counts, original row order, both ancestors and additive exposure.
All copied HF files match the closed source inventory. Independent compact
encoding checks 34 samples per source (238 total), including each longest row.
The hash-gated upstream loader verifies all source concatenation boundaries
and separate validation; the complete seed-24 shuffle index matches a NumPy
permutation under the retained local libraries.

`material_preparation_ready=true`; `original_model_training_ready`,
`packing_backend_verified`, `original_tokenizer_parity_verified` and
`full_method_ready` remain false. The proof binds the corpus/contract, importer
and tool SHA-256 values. Loader/shuffle evidence uses local datasets/NumPy
versions, not a recovered exact original NeMo environment. The remaining
[backend/version/resource gaps](../../docs/plan/2026-10-01-nvarc-reproduction-gaps.md)
remain explicit.

Verification log: `.irisx/nvarc-data/original-verification-001.log`, SHA-256
`41524331a075aa8bfe7453ee3274dde74c3609eba44c69d7f46a0aa5d820753d`.

## Regression validation

New policy/real-HF tests: 5 passed without skips. They cover additive exposure
on both parents, oversize retention, independent token accounting, invalid
grammar, clean-purpose rejection and rehashed false-parent/extra-file tampering.
Log: `.irisx/nvarc-data/original-corpus-tests-001.log`, SHA-256
`0c7c1f8bc1889bc73e1c20e081918ac58ebb87cb94293079639cfc918966c6b4`.

Repository `--all`: 302 tests, 507.776 seconds, 4 existing optional skips; passed.
Log: `.irisx/nvarc-data/original-corpus-repository-001.log`, SHA-256
`09e249643ab2d96404e47ce9a248c36fd9f309ffdf5a54428533df6cf76ba43f`.

The strict ML profile's first run passed 37/38 checks; the installed-wheel tiny
model test exceeded its unchanged 60-second model-ready deadline while full
corpus processing also ran. Its failure is retained in
`.irisx/nvarc-data/original-corpus-strict-ml-001.log` (SHA-256
`eadd346250b08fe2f6a1733215d44ae9186fb4fb61681f6f84c6bd42e2640e3e`).
The failed check passed when rerun alone after corpus processing: 1 test,
73.441 seconds for the complete install/probe/tamper test, with its model-ready
deadline still 60 seconds. This is consistent with local resource contention;
the first full-profile failure remains retained rather than relabeled a pass.
Recheck log: `.irisx/nvarc-data/original-corpus-strict-deployment-recheck-001.log`,
SHA-256 `146b3083a391621773c941b742a1d847e1f50a9701c3d26645f85162f2eb994c`.
The final documentation/authority update also passed the repository invariants
and diff whitespace checks. No model backend or timeout implementation changed.

## Material and isolation

`tools/nvarc_original_corpus.py` binds the two already acquired version-1
archive inventories, retained ZIP hashes, parent catalog and pinned source
recipe hashes. It copies the closed HF inventory byte-for-byte, preserving
all original messages and row order. No parent/length filter or truncation
is applied. Invalid grammar or unknown ancestry fails preparation rather
than silently dropping an original record.

Every source has a row-aligned Arrow sidecar containing `source_row`,
`puzzle_name`, `parent_ids`, additive `exposure_tags`, compact input tokens
and assistant-only supervised tokens. Both synthetic filename parents and
the first-parent directory are joined against the closed synthetic inventory.
This is published filename ancestry; teacher semantic ancestry is not
independently reconstructed. Mini/Concept ancestry is namespaced and semantic
overlap across sources remains unknown.

Original material is under `.irisx/nvarc-original/materials/`, with verification
reports in `.irisx/nvarc-original/manifests/`. Contracts reserve distinct
`checkpoints/`, `runs/` and `results/` namespaces for later approved work.
The reader requires an exact manifest SHA and an explicit original-reproduction
or Qwen3.5-port purpose; clean-research/evaluation purpose is rejected. Models
using this corpus cannot claim unexposed evaluation on its ancestors.

## Source behavior and limits

The actual `run_sft.py` loader concatenates the six training paths in YAML order.
Its `main` shuffles training with effective seed 24 from `run_sft_4b.sh` and loads
`arc2_evaluation6` separately. `sft_preprocessor` passes `add_bos_token=False`,
`add_eos_token=False`, `add_generation_prompt=True` and loss multiplier 1.0.
Its `max_seq_length` argument is unused; this fact does not establish that the
downstream NeMo backend accepts every long sequence without its own processing.

Original packing is configured as `modified_first_fit_decreasing`, enabled,
256,000 microbatch tokens and sequence-length rounding 64 after shell overrides.
The actual NeMo packing implementation/attention isolation and original Qwen3
tokenizer are not present in the verified material. Their behavior remains a
training prerequisite; no replacement packing or invented truncation is applied.

Token accounting here is the Qwen3.5 compact-grid projection with source chat
newlines and assistant-grid/EOS supervision. Vectorized Arrow grammar/counts
are checked against independent `GridTokenizer` encoding samples, including
the longest record in each source. This establishes compact projection counts,
not numerical parity with the unavailable original Qwen3 tokenizer/backend.

No new acquisition, model/teacher call, real-data training, provider mutation,
scoring, old locked evaluator read, publication or paid work occurs. Both Kaggle
dataset license fields were previously reported as unknown; local preparation
is not redistribution clearance.
