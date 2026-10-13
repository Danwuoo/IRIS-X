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
- [`0027-authorize-session-free-kernel-debugging.md`](0027-authorize-session-free-kernel-debugging.md)
  authorizes distinct free private kernels during the current session solely
  for program-error repairs to that bounded compact 4B flow.
- [`0028-authorize-nvarc-m2-m3-small-probes.md`](0028-authorize-nvarc-m2-m3-small-probes.md)
  authorizes one private free Kaggle FSDP feasibility probe and one independent
  bounded local Qwen teacher probe, each with one terminal retrieval and no retry.
- [`0029-authorize-nvarc-m2-fsdp-repair.md`](0029-authorize-nvarc-m2-fsdp-repair.md)
  authorizes one new private, free four-L4 FSDP feasibility replacement with
  phase diagnostics after the original probe's NCCL timeout.
- [`0030-authorize-nvarc-m2-result-repair.md`](0030-authorize-nvarc-m2-result-repair.md)
  authorizes one distinct, private four-L4 FSDP result-packaging repair after
  `002` completed a step but failed canonical JSON serialization.
- [`0031-authorize-nvarc-m2-m3-checkpoint-continuation.md`](0031-authorize-nvarc-m2-m3-checkpoint-continuation.md)
  authorizes one bounded private four-L4 full-parameter ARC-SFT checkpoint,
  export and source-solve run, and one independent four-call local Qwen teacher
  run, each with one terminal retrieval and no retry.
- [`0032-authorize-nvarc-m2-m3-terminal-repairs.md`](0032-authorize-nvarc-m2-m3-terminal-repairs.md)
  authorizes one distinct scratch-backed M2 full-parameter ARC-SFT kernel and
  one distinct tokenizer-repaired M3 local Qwen teacher kernel, each private,
  bounded, free, and limited to one terminal retrieval without retry.
- [`0033-authorize-nvarc-source-and-direct-teacher.md`](0033-authorize-nvarc-source-and-direct-teacher.md)
  authorizes the retained-export source continuation, a four-stage direct
  teacher, exact tokenizer preflight and local artifact verification.
- [`0034-restart-nvarc-without-monitoring.md`](0034-restart-nvarc-without-monitoring.md)
  authorizes two distinct private replacement submissions and stops at receipts.
- [`0035-submit-nvarc-combined-two-gpu-notebook.md`](0035-submit-nvarc-combined-two-gpu-notebook.md)
  authorizes one private combined M2/M3 notebook using two selected L4 GPUs,
  unchanged workloads and existing Datasets, with no monitoring or retrieval.
- [`0036-repair-combined-nvarc-notebook.md`](0036-repair-combined-nvarc-notebook.md)
  authorizes one diagnostic retrieval of failed combined 001 and one distinct
  combined 002 hardware-identity repair submission, stopping at its receipt.
- [`0037-save-nvarc-notebook-for-owner-editor.md`](0037-save-nvarc-notebook-for-owner-editor.md)
  authorizes one private quick save of the reviewed combined 003 notebook,
  without agent execution; the owner will run it in Editor and report.
- [`0038-save-paired-nvarc-analysis-notebook.md`](0038-save-paired-nvarc-analysis-notebook.md)
  authorizes one private QUICK_SAVE combining paired M2 thresholds and semantic
  M3, with a downloadable analysis ZIP and no agent execution or monitoring.
- [`0039-save-repaired-nvarc-combined-editor.md`](0039-save-repaired-nvarc-combined-editor.md)
  authorizes one private QUICK_SAVE of distinct combined 005, repairing both
  M2 full-grid candidate search and M3 public-demo rule guidance without an
  agent run or monitoring.
- [`0040-save-nvarc-public-witness-repairs.md`](0040-save-nvarc-public-witness-repairs.md)
  authorizes one private QUICK_SAVE of distinct combined 006 with a public
  palette witness for M2 and a trusted public-rule mix target for M3, without
  an agent run or monitoring.
- [`0041-save-nvarc-grammar-and-signature-repairs.md`](0041-save-nvarc-grammar-and-signature-repairs.md)
  authorizes one private QUICK_SAVE of distinct combined 007 with public
  grammar completion for M2 and an exact one-argument output prompt for M3,
  without an agent run or monitoring.
- [`0042-save-nvarc-startup-diagnostics.md`](0042-save-nvarc-startup-diagnostics.md)
  authorizes one private QUICK_SAVE of distinct combined 008 with finer
  startup events and interrupt-class terminal evidence, without changing
  M2/M3 workloads or starting an agent run.
- [`0043-save-nvarc-public-witness-and-safe-ast.md`](0043-save-nvarc-public-witness-and-safe-ast.md)
  authorizes one private QUICK_SAVE of distinct combined 009, separately
  reporting an M2 public positional witness and validating M3's narrow
  teacher programs by no-exec AST interpretation and 44 semantic probes.
- [`0044-save-compact-base-sft-ttt-comparison.md`](0044-save-compact-base-sft-ttt-comparison.md)
  authorizes one private owner-Editor QUICK_SAVE comparing a compact base,
  its retained eight-step SFT pilot export, and that export with task TTT on
  a fixed truth-free public workload.
- [`0045-repair-compact-abc-editor-mount.md`](0045-repair-compact-abc-editor-mount.md)
  authorizes one distinct material-mount repair and owner-Editor QUICK_SAVE
  for the compact A/B/C comparison.
- [`0046-save-compact-abc-adaptation-sensitivity.md`](0046-save-compact-abc-adaptation-sensitivity.md)
  authorizes one owner-Editor QUICK_SAVE comparing fixed A/B controls with
  task-local TTT step-count and learning-rate variations.
- [`0047-save-compact-abc-beam-comparison.md`](0047-save-compact-abc-beam-comparison.md)
  authorizes one owner-Editor QUICK_SAVE changing only the legal model
  candidate search to a bounded two-path beam.
- [`0048-save-compact-abc-base-ttt-pair.md`](0048-save-compact-abc-base-ttt-pair.md)
  authorizes one owner-Editor QUICK_SAVE comparing base and eight-step SFT
  pilot weights with and without the same one-step task TTT.
- [`0049-acquire-and-audit-nvarc-datasets.md`](0049-acquire-and-audit-nvarc-datasets.md)
  authorizes fixed-version acquisition and local lineage/exposure processing
  of the two published NVARC puzzle datasets, without model execution.
- [`0050-separate-original-nvarc-reproduction.md`](0050-separate-original-nvarc-reproduction.md)
  records the owner's original-recipe reproduction direction: preserve all
  published recipe inputs and isolate exposure from clean-data comparisons.
- [`0051-run-qwen35-kaggle-gpu-preflight.md`](0051-run-qwen35-kaggle-gpu-preflight.md)
  records the consumed private Qwen3.5 resource probe: one source-optimizer
  step and checkpoint restore gate passed; the long-sequence step failed.
- [`0052-repair-qwen35-kaggle-gpu-preflight.md`](0052-repair-qwen35-kaggle-gpu-preflight.md)
  records the consumed second-upload repair: both whole-sequence steps and
  checkpoint resume passed on four L4s with CPU FP32 state offload.
- [`0053-nvarc-overnight-development-goal.md`](0053-nvarc-overnight-development-goal.md)
  records the timed NVARC implementation Goal and autonomous free Kaggle GPU
  direction, preserving prior identities and explicit parity gaps.
- [`0058-save-native-multitask-export-repair.md`](0058-save-native-multitask-export-repair.md)
  authorizes exactly one private native multitask 010 QUICK_SAVE derived from
  frozen export-repair review 009, with resource/session facts unavailable,
  stopping at the receipt for manual owner Editor operation.
- [`0059-obtain-one-official-stage3-cli-score.md`](0059-obtain-one-official-stage3-cli-score.md)
  authorizes one distinct full-input Stage 3 official competition score through
  Kaggle CLI, preserving strict replay limitations and stopping at its terminal
  outcome without opening Stage 4.
- [`0060-save-two-public-evaluation-notebooks.md`](0060-save-two-public-evaluation-notebooks.md)
  records two owner-Editor public evaluation notebooks, one private QUICK_SAVE
  each after local debug, with separate BASE/full-TTT budgets and ZIP names.
- [`0061-transfer-stage4-development-to-dots.md`](0061-transfer-stage4-development-to-dots.md)
  records autonomous Astra ultra development with parallel subagents and free
  private Kaggle GPU experiments, ending at official-scoring readiness.
- [`0062-run-e12-with-explicit-free-quota-waiver.md`](0062-run-e12-with-explicit-free-quota-waiver.md)
  records the owner's one-run conservative-reservation waiver while preserving
  actual free-quota checks, USD 0, the unchanged E12 workload and terminal monitoring.
- [`0063-repair-e12-arm-telemetry-and-rerun.md`](0063-repair-e12-arm-telemetry-and-rerun.md)
  records the owner-authorized one-run telemetry repair replacement, same scope
  and free-only bounds, exact wire review, terminal analysis and preservation.
- [`0064-run-paired-search-budget-diagnostic.md`](0064-run-paired-search-budget-diagnostic.md)
  records one small paired 120/240-second search diagnostic sharing one native
  TTT128 state per task, with unchanged non-time caps, free-only resources,
  independent review, terminal monitoring and audited preservation.

- [`0069-evaluate-sealed-public-research-predictions.md`](0069-evaluate-sealed-public-research-predictions.md)
  permits only sealed, isolated public-development scoring and reviewed private
  research publication under the 2026-10-10 owner request.

- [`0070-publish-and-run-bounded-learning-agent.md`](0070-publish-and-run-bounded-learning-agent.md)
  authorizes the exact reviewed private learning-agent release and required
  Datasets, plus one 43,200-second session on the existing configured resource,
  with unchanged training/evaluator isolation and verified publication evidence.

- [`0071-complete-local-code17-publication-and-public120-run.md`](0071-complete-local-code17-publication-and-public120-run.md)
  transfers this round's sole publisher role locally, with reviewed repairs,
  private execution and terminal monitoring through a complete PUBLIC120 run,
  preserving each attempt and freezing a verified reproducible Git version.
