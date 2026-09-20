# Current Decisions

Decisions here govern the active product-era repository. Historical decisions
are available only from the cold-archive tag and have no current authority
unless a new decision explicitly re-adopts them.

- [`0001-adopt-product-oriented-domain-ai-specialization.md`](0001-adopt-product-oriented-domain-ai-specialization.md)
  adopts the IRIS-X product direction and records the choices still open.
- [`0002-adopt-p1-contract-and-serialization-foundation.md`](0002-adopt-p1-contract-and-serialization-foundation.md)
  adopts the zero-runtime-dependency Python foundation, canonical JSON
  contracts, offline qualification adapter, and closed-world package format.
- [`0003-record-p2-admission-block.md`](0003-record-p2-admission-block.md)
  records the historical P2 admission block, defines its admission-only scope,
  and identifies the owner decisions that were required.
- [`0004-admit-first-p2-arc-agi-2-engineering-trial.md`](0004-admit-first-p2-arc-agi-2-engineering-trial.md)
  selects the local/offline ARC-AGI-2 trial, authorizes its bounded repository
  implementation and preflight work, and keeps the real run behind a separate
  explicit execution authorization.
- [`0005-authorize-kaggle-offline-handoff-for-arc-agi-2-trial-001.md`](0005-authorize-kaggle-offline-handoff-for-arc-agi-2-trial-001.md)
  replaces only the Trial 001 execution venue and transport boundary with a
  private, manual, ZIP-based Kaggle handoff while preserving local evaluation,
  frozen weights, zero paid spend, and the separate real-run authorization.
- [`0006-use-unpacked-model-source-for-arc-agi-2-trial-001.md`](0006-use-unpacked-model-source-for-arc-agi-2-trial-001.md)
  supersedes the model ZIP transport with a provenance-bound unpacked model
  Dataset used directly from Kaggle's read-only input mount. It does not
  authorize the real run.
- [`0007-bind-kaggle-extracted-trial-dataset.md`](0007-bind-kaggle-extracted-trial-dataset.md)
  adapts the notebook to Kaggle's extracted Trial Dataset mount and binds
  returned results to the verified trial manifest rather than unavailable ZIP
  container bytes. It does not authorize the real run.
