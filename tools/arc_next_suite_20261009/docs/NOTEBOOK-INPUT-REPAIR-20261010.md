# Notebook-only prerequisite and retry repair

Revision: `evidence-inputs-fix1-20261010`.

## Scope and unchanged contracts

N9–N14 notebook orchestration now handles Kaggle's automatic extraction. Scientific `src/` files, their lock, tasks, prompts, seeds, fixed denominators, model pins, admission thresholds, N14 ranking and execution budgets are byte-identical to v2. N5–N8 notebook bytes are preserved. No GPU/model/training execution, paid spend or competition-data read was performed for this repair.

The separate input helper is embedded as verified source bytes, hash-bound in notebook and publication metadata, and imported through a source-only loader. It never modifies the scientific evidence or executes any prior artifact's source. Its discovery/retry journal lives outside each closed scientific run.

## Discovery and ambiguity

- Default scope is `/kaggle/input`; explicit search roots are available for owner-selected cloud paths.
- Maximum depth 7, directories 1,024, enumerated entries 12,000 and candidates 128. Known five asset slugs/explicit asset roots are pruned. Evidence trees are not recursively searched after recognizing their closed final inventory.
- An unrelated wrapper manifest does not hide nested evidence. Directory and ZIP candidates are bounded before complete verification (20,000 entries, 250 MiB, bounded metadata, no symlinks/special members/path traversal).
- The unchanged runner verifies manifests, lock, scientific contract, final inventory, seal, complete ledger and process stop. The helper additionally requires complete search accounting.
- Equivalent ZIP/extracted copies share one complete evidence identity. Differing valid identities fail closed; there is no latest/first selection. Explicit overrides remain fully validated and are labeled separately.
- Automatically selected N6/N7 must match their known final-inventory hashes. Wrapper manifest/version pins are publication provenance only; the journal explicitly states that the wrapper manifest was not runtime-verified.
- N14 only accepts the original admission-threshold blocked chain after independently checking N6. Missing/invalid-source BLOCKED receipts never waive evidence.

## Retry behavior

The initial output path is unchanged. A new attempt namespace is allocated only after every prior attempt has a closed two-file inventory (blocked receipt plus final inventory), exact run/revision/source lock and strict integer zero generate/training counters. All previous evidence and archives remain unchanged. Partial/complete/malformed/orphaned histories stop. Missing prerequisite or asset mounts produce a terminal zero-call BLOCKED receipt before installation/model access. Source and helper files are append-only and verified on reuse.

## Dataset and publication

The reviewed private prerequisite Dataset contains exact extracted N6/N7 evidence (435 files each) plus `dataset-manifest.json`, 871 files total. No query gold, credentials or weights are included. The original ZIPs remain preserved. The publication manifest binds `danielwuu/iris-arc-next-prerequisites-20261010/1`; complete payload anchors are in `PREREQUISITE-DATASET-PIN.json`.

Only existing N9–N14 notebook IDs receive inactive successor versions. N9's owner-created ARC-AGI-3 metadata association is preserved; N10–N14 retain empty associations. GPU, TPU, Internet and manual start remain off. N13 adds no prerequisite Dataset and remains CPU-only. N14 remains blocked until future prerequisite evidence and a qualifying policy exist.

## CPU acceptance

Run the full suite with `IRISX_RUNTIME8_TEST_ROOT` pointing to the verified canonical runtime8 mount and `IRISX_ACTUAL_PRIOR_ROOT` pointing to the reviewed prerequisite payload. The latter adds actual owner-evidence acceptance tests; absent evidence is an explicit skip and does not satisfy release acceptance. Generated notebook tests stop at a mocked backend boundary after real input verification; they do not claim a live model/Kaggle session.

The new regression cases cover extracted multi-wrapper layouts, ZIPs, duplicate equivalent copies, wrong-run/report-only inputs, ambiguity, tampering, old locks, partial/non-stopped evidence, symlinks/traversal, size/count limits, model-tree pruning, exact pins, explicit override, preserved blocked retries, malformed/attempted histories, missing assets, N13 no scan and N14's missing-source rejection.

To regenerate, run `python3 build_notebooks.py`; it creates the scientific-source notebooks and then applies `build_input_repair.py`. For notebook-only input changes, do not regenerate the scientific source lock.
