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
  The distinct four-L4 accumulation/export package is being prepared.
- Complete task-local adaptation / inference integration: pending.
- SDG / TRM integration and remaining material parity: pending.
- Final validation, runtime observations and handoff: pending.

The bounded two-step GPU probe is not a full SFT checkpoint or quality result.
An interface, fixture or inert plan alone does not satisfy a runtime requirement.
