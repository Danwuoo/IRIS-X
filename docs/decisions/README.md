# Decisions

These records preserve durable product, safety, contract, and evidence-boundary
choices. Start with Decision 0010 for the current development workflow and the
active trial README for operational status. Read older decisions when their
rationale or exact binding is relevant; current README files do not repeat the
entire chain.

Pre-product decisions remain available only from the cold-archive tag and have
no current authority unless a new decision explicitly re-adopts them.

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
- [`0008-bind-offline-qwen3-5-transformers-runtime.md`](0008-bind-offline-qwen3-5-transformers-runtime.md)
  binds a closed offline Transformers 5.8.1 wheel set so the frozen Qwen3.5
  architecture can load without Kaggle Internet. It does not authorize the
  real run.
- [`0009-normalize-arc-agi-2-trial-001-layout.md`](0009-normalize-arc-agi-2-trial-001-layout.md)
  freezes the retained `run-001` identities, requires bundle IDs to match
  outbound directories, and gates physical layout normalization on verified
  result import and local evaluation. It does not authorize or ratify a run.
- [`0010-adopt-lightweight-risk-based-development.md`](0010-adopt-lightweight-risk-based-development.md)
  keeps Build–Measure–Select while allowing routine local, offline, reversible
  work to proceed without a new decision record; durable and risky boundary
  changes remain explicitly gated.
- [`0011-create-checkpointing-run-002.md`](0011-create-checkpointing-run-002.md)
  preserves the frozen `run-001` bytes and creates a separately identified v4
  `run-002` adapter with atomic per-attempt checkpoints, exact resume identity,
  progress output, and cumulative cross-session time accounting.
- [`0012-close-arc-agi-2-trial-001-inconclusive.md`](0012-close-arc-agi-2-trial-001-inconclusive.md)
  closes Trial 001 as `inconclusive-no-promotion`, retains the owner-reported
  four-timeout `run-002` observation, records that no `run-003` result was
  locally accepted, and ends the remaining execution authority.
- [`0013-create-unbounded-four-invocation-run-003.md`](0013-create-unbounded-four-invocation-run-003.md)
  preserves the executed `run-002` identity and authorizes a new `run-003` v5
  completion benchmark: exactly four invocations, no runner time limit,
  resumable checkpoints, and a fully recorded `result.zip`.
- [`0014-authorize-arc-agi-2-trial-002-baseline-smoke.md`](0014-authorize-arc-agi-2-trial-002-baseline-smoke.md)
  opens the distinct Trial 002 completable-baseline question, selects the exact
  Qwen3.5-4B and NVARC-derived path, and authorizes one private bounded Kaggle
  L4 x4 smoke with automated CLI transport and truth-free evidence.
- [`0015-authorize-trial-002-repair-smoke.md`](0015-authorize-trial-002-repair-smoke.md)
  preserves the failed first smoke and authorizes one replacement identity
  with the ARC competition mounted, exact L4 x4 runtime checks, and exactly
  four inference-only generation invocations.
- [`0016-authorize-arc-agi-2-prompt-pilot-baseline.md`](0016-authorize-arc-agi-2-prompt-pilot-baseline.md)
  opens a distinct prompt-pilot trial and authorizes one private 384-job
  baseline launch, with work stopping once four exact-model workers are ready
  and the dynamic scheduler has started.
- [`0017-authorize-prompt-pilot-mount-repair.md`](0017-authorize-prompt-pilot-mount-repair.md)
  preserves the failed first baseline and authorizes one transport-only
  replacement identity with exact current Kaggle Dataset mounts and the same
  four-worker startup stopping condition.
- [`0018-authorize-prompt-pilot-result-recovery.md`](0018-authorize-prompt-pilot-result-recovery.md)
  authorizes one output retrieval from the compute-complete baseline-002
  failure and local reconstruction of its missing result package, without
  rerunning or scoring the workload.
- [`0019-authorize-continuous-prompt-search.md`](0019-authorize-continuous-prompt-search.md)
  authorizes the bounded continuous scoring, real DSPy/GEPA plus Codex prompt
  search, private candidate evaluations, and one final locked-holdout
  comparison under a 4,480-generation ceiling.
- [`0020-authorize-arc-budget-ablation.md`](0020-authorize-arc-budget-ablation.md)
  authorizes the separate output-budget/thinking diagnostic and conditional
  validation under a 576-generation ceiling, with GPT-6 Sol xhigh development
  and future reflection configuration.
- [`0021-authorize-nvarc-4b-compatibility-pilot.md`](0021-authorize-nvarc-4b-compatibility-pilot.md)
  authorizes one private Kaggle L4 Qwen3.5-4B LoRA compatibility kernel and one
  terminal retrieval under a two-step, 128-token, zero-generation ceiling.
- [`0022-authorize-competition-mounted-4b-pilot-repair.md`](0022-authorize-competition-mounted-4b-pilot-repair.md)
  preserves the failed pilot 001 and authorizes one distinct pilot 002 kernel
  with the official competition mounted and early GPU diagnostics.
- [`0023-authorize-pre-version-4b-pilot-retry.md`](0023-authorize-pre-version-4b-pilot-retry.md)
  preserves the provider-rejected pilot 002 and authorizes one corrected,
  shorter-slug pilot 003 submission before any accepted run.
- [`0024-authorize-4b-pilot-dependency-repair.md`](0024-authorize-4b-pilot-dependency-repair.md)
  preserves pilot 003's dependency failure and authorizes one distinct pilot
  004 submission with an offline removal of incompatible optional `torchao`.
- [`0025-retry-auth-rejected-4b-pilot-004.md`](0025-retry-auth-rejected-4b-pilot-004.md)
  records pilot 004's expired-OAuth HTTP 401 and authorizes one exact-package
  transport retry after credential refresh, before any notebook version.
- [`0026-authorize-nvarc-4b-compact-complete-pilot.md`](0026-authorize-nvarc-4b-compact-complete-pilot.md)
  binds one private compact 4B conversion, short adaptation, generation and
  result-verification run under fixed synthetic and USD 0 ceilings.
