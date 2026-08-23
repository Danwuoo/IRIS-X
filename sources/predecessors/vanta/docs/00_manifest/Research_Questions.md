# Research Questions

## Purpose

This document converts the theory and validation review into research questions that can be tested through specifications, schemas, benchmarks, and experiments.

## Primary Questions

1. Does explicit reasoning-to-action structure improve task success and reduce invalid action rates compared with a baseline function-calling agent?
2. Does an Evidence Packet improve verifier reliability compared with final-answer or raw-trace judging?
3. Does a Context OS / working set compiler improve long-task stability under fixed token and latency budgets?
4. Does Failure Taxonomy plus Credit Routing improve recovery efficiency compared with blind retry or deeper search under matched compute?
5. Does Episode Journal governance reduce unsafe commits and improve replay, audit, and rollback quality?

## Secondary Questions

- Which parts of the runtime produce value independently, and which require the full loop?
- Which metrics can be computed automatically, and which require human labels?
- Which side-effect classes can be safely handled in the MVP?
- What data is required before runtime feedback can be used as a training signal?

## Gate Tracking

- First vertical benchmark domain: answered by
  [Stage 1 MVP Entry Gate](Stage_1_MVP_Entry_Gate.md) as Document Ops.
- First MVP verifier architecture: answered by
  [Stage 1 MVP Entry Gate](Stage_1_MVP_Entry_Gate.md) as deterministic
  rule-based Verifier v0.
- Thresholds for acceptable false accept, false reject, and unsafe action
  rates: answered by
  [Post-Stage-1 Metric Policy](../05_evaluation/Post_Stage_1_Metric_Policy.md)
  as the accepted `PS1-G2` artifact.
- Larger controlled Document Ops sample frame: answered by
  [Post-Stage-1 Larger Sample Plan](../04_experiments/Post_Stage_1_Larger_Sample_Plan.md)
  as the accepted `PS1-G1` artifact.
- Post-Stage-1 baseline identity: answered by
  [Baseline Identity Plan](../04_experiments/Baseline_Identity_Plan.md) as the
  accepted `PS1-G5` artifact.

## Related Documents

- [Design Theory](../01_theory/Design_Theory.md)
- [Validation and Refutation Report](../01_theory/Validation_and_Refutation_Report.md)
- [Ablation Plan](../04_experiments/Ablation_Plan.md)
- [Metrics Definition](../05_evaluation/Metrics_Definition.md)
- [Post-Stage-1 Metric Policy](../05_evaluation/Post_Stage_1_Metric_Policy.md)
- [Post-Stage-1 Larger Sample Plan](../04_experiments/Post_Stage_1_Larger_Sample_Plan.md)
- [Baseline Identity Plan](../04_experiments/Baseline_Identity_Plan.md)
