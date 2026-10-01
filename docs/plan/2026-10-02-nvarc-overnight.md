# NVARC overnight implementation

The owner opened a development Goal, with autonomous free Kaggle GPUs,
until substantial completion or 2026-10-02 07:00 Taipei. Authority is
[Decision 0053](../decisions/0053-nvarc-overnight-development-goal.md).
The native one-shot timer `nvarc-07-00` is armed; no wall-clock polling is needed.
Starting main commit is `01f43cd`. GPU preflight 002 is verified and consumed.

## Completion evidence

1. Source packing configuration and deterministic binning are explicit.
   Independent sequence attention, positions, DeltaNet state and labels cannot
   leak across boundaries. Real hybrid tiny-model logits/loss/gradient checks
   compare the adapter against independent original sequences.
2. A reusable SFT path consumes the isolated original-corpus order, applies
   source optimizer/schedule and global supervised-token normalization across
   ranks/microsteps, and binds all parent/exposure lineage. Checkpoint resume
   restores optimizer, scheduler, RNG and cursor; export/reload is verified.
3. Source-profile TTT, candidate search, eight-view verification and task reset
   run from a verified export with a complete ledger, never evaluator answers.
   Port implementation choices and resource limits remain explicit.
4. SDG and TRM interfaces integrate with their existing source implementations
   and retain exact materials, stages, preprocessing, training/inference and
   acceptance evidence. Limited interpreters/tiny models cannot stand in for
   full original generation or original-scale training.
5. Necessary CPU differential and Kaggle runtime probes pass on exact saved
   packages; repository validation passes; source code and durable reports are
   committed on main. Remaining exact-version/material/scale gaps are visible.

## Progress

- Timer and Goal: active.
- Packing / hybrid attention-state isolation: reference implemented; 503 exact
  NeMo MFFD comparisons and real tiny hybrid logits/loss/gradients pass.
  Segmented execution is explicit; fused NeMo throughput remains unverified.
- Reusable distributed source SFT / accumulation / export: CPU verified. Two
  actual FSDP ranks with unequal sample counts match the independent global
  token-mean optimizer; uninterrupted/resumed model and optimizer tensors,
  scheduler, RNG and cursor match exactly. Every export tensor reloads exactly.
  Complete source shuffle, lazy Arrow lineage and whole long records pass.
  Four-L4 run 002 completed two accumulated steps, 94,156 input tokens,
  process restart and a 724-tensor HF export/reload. Sole terminal retrieval
  verified the closed diagnostics; local weight transfer/independent tensor
  verification is pending. Run 003 is accepted and measures global batch 256
  over the exact first 512 full-shuffle rows (1,770,662 input tokens).
- Complete task-local adaptation / inference integration: full 128-view tiny
  epoch checkpoint differential and trained-export/search/reset integration
  pass. Four-L4 run `nvarc-overnight-ttt-001` is accepted with a single model
  worker, 128 rank-256 TTT steps and sixteen source DFS calls. Its sole terminal
  retrieval verified a missing notebook mount-path variant before model work.
  Distinct TTT 002 repairs that transport path and is accepted/running.
  It uses SFT run 002's
  immutable output mount and must verify all weight bytes onsite before model
  work. No terminal TTT observation is claimed yet.
- SDG / TRM integration and remaining material parity: current strict profile
  passed 45 tests in 329.491 s, including ten-stage source saved replay under
  actual WSL namespaces and real tiny source TRM train/reload/TTT/joint ranking.
  Published raw SDG artifacts version 1 are downloading; source-linked TRM
  checkpoint Dataset 031 version 1 was inventoried separately and its exact
  source-named `step_220708` checkpoint is downloading. The exact TRM
  v18 source API request returned 404, preserving the v21/v18 gap.
  Full original teacher generation, raw artifact verification, TRM scale and v18 parity
  remain unverified and cannot be replaced by these engineering observations.
- Repository validation: 314 tests passed in 267.771 s for milestone 002.
  Final runtime observations, durable handoff and substantive completion remain
  pending. Required validation will be repeated only after further changes.

The bounded two-step GPU probe is not a full SFT checkpoint or quality result.
An interface, fixture or inert plan alone does not satisfy a runtime requirement.
