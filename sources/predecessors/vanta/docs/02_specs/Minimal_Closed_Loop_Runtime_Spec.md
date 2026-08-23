# Minimal Closed Loop Runtime Spec

## Purpose

Define the MVP runtime loop that turns state into action, action into evidence, evidence into verification, and verification into commit or abort.

## Scope

- Canonical state intake and update.
- Candidate plan/action proposal.
- Compilation into Execution IR.
- Evidence Packet construction.
- Verifier Runtime invocation.
- Commit or abort decision.
- Episode Journal logging.

## Non-goals

- Full Context OS optimization.
- Long-term memory training.
- Irreversible external side effects.
- Production deployment.
- Claims that the architecture is empirically validated.

## Inputs

- User task or environment event.
- Current canonical state.
- Runtime constraints.
- Available action schemas.
- Prior episode context, if any.

## Outputs

- Updated canonical state.
- Execution steps.
- Evidence packets.
- Verifier outputs.
- Commit or abort status.
- Episode journal entry.

## Key Concepts

- The minimal loop is `state -> plan -> action -> evidence -> verify -> commit / abort`.
- Every non-trivial action must produce evidence before commit.
- The verifier may abstain or request additional evidence.
- Failed steps should preserve enough journal data for later recovery analysis.
- Stage 0 boundary locks constrain this loop: state, execution trace, evidence, verifier output, journal, memory, and rollback semantics remain separate artifacts.

## Stage 1 Locked Answers

- Stage 1 local smoke status: `Closed: local smoke completed`.
- First controlled environment: local Document Ops fixtures.
- Verifier implementation: deterministic Verifier v0 using JSON Schema validation,
  side-effect-class rules, fixture-specific acceptance checks, required evidence
  checks, and provenance completeness checks.
- Minimum commit evidence: `pre_state_hash`, `post_state_hash`, `step_id`,
  `action_ref`, normalized `observation`, `post_state_summary`, `provenance`,
  and `runtime_context`. Simulated or reversible edits must include a diff or
  result summary inside the normalized observation.
- Allowed side-effect classes: `READ_ONLY`, `SIMULATED`, and `REVERSIBLE`.
- Disallowed side-effect classes: `COMMITTABLE`, `IRREVERSIBLE`, and
  `MEMORY_WRITE` for the first Stage 1 runtime.

## Post-Stage-1 Locked Answers

- Broader MVP acceptance thresholds for the first Lane A larger controlled
  sample are governed by
  [Post-Stage-1 Metric Policy](../05_evaluation/Post_Stage_1_Metric_Policy.md).
- The first larger controlled Document Ops sample is 48 fixtures as defined by
  [Post-Stage-1 Larger Sample Plan](../04_experiments/Post_Stage_1_Larger_Sample_Plan.md).
- The OpenClaw harness baseline remains local-harness labeled and may be
  supplemented by separately named direct Responses arms according to
  [Baseline Identity Plan](../04_experiments/Baseline_Identity_Plan.md).
- `PS1-G9` accepts SQLite behind `Vanta.Persistence` for the named
  `Fixture-Local SQLite Persistence v0` surface. Runtime artifacts remain typed
  and separate; accepted Canonical State and Episode Journal pointers commit in
  one database transaction. The filesystem uses the prepared-effect recovery
  protocol in
  [Persistence and Recovery Semantics](Persistence_and_Recovery_Semantics.md).

## Related Documents

- [Stage 0 Boundary Lock](../00_manifest/Stage_0_Boundary_Lock.md)
- [Stage 1 MVP Entry Gate](../00_manifest/Stage_1_MVP_Entry_Gate.md)
- [Stage 1 Experiment 001 Closure](../00_manifest/Stage_1_Experiment_001_Closure.md)
- [Design Theory](../01_theory/Design_Theory.md)
- [Validation and Refutation Report](../01_theory/Validation_and_Refutation_Report.md)
