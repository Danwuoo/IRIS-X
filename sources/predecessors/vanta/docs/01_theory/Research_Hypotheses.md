# Research Hypotheses

## Purpose

This document extracts the research hypotheses from the source theory and validation report. It is derived synthesis, not a replacement for the source documents.

## Source Documents

- [Design Theory](Design_Theory.md)
- [Validation and Refutation Report](Validation_and_Refutation_Report.md)

## H1: Reasoning-to-action fidelity is the core bottleneck of agent capability

If a model can reason but cannot stably translate reasoning into actions, the agent remains unusable.

Initial validation priority:

- Compare baseline function calling against Execution IR and verifier-enabled variants.
- Measure task success, invalid action rate, state-transition consistency, and rationale-to-action alignment.

## H2: Evidence Packet can significantly improve verifier reliability

Turning the verifier from a final-answer judge into an evidence-consuming runtime service may reduce false accept.

Initial validation priority:

- Compare final-answer judging, raw-trace judging, and structured Evidence Packet judging.
- Measure false accept, false reject, calibration, and evidence sufficiency.

## H3: Context OS is more important than simply increasing the context window

In long tasks, working set quality may affect stability more directly than nominal context length.

Initial validation priority:

- Compare raw long context, retrieval, and provenance-preserving working set compilation under fixed budgets.
- Measure task success, provenance loss, middle-position robustness, latency, and token cost.

## H4: Failure credit routing can improve recovery efficiency

Targeted recovery may be cheaper, less memory-polluting, and more interpretable than blind retry.

Initial validation priority:

- Use controlled failure injection.
- Compare blind retry, deeper search, and targeted recovery under matched compute.

## H5: Episode governance is the core foundation of agent safety

Agents without commit, rollback, and replay semantics for side effects are difficult to deploy reliably.

Initial validation priority:

- Use sandboxed side-effect classes.
- Compare governed and ungoverned runtimes on unsafe action rate, replay consistency, audit completeness, and commit integrity.

## Open Questions

- Which hypothesis should be tested first in the selected vertical domain?
- What sample size is feasible for each ablation?
- Which hypotheses require human labels before automated metrics are meaningful?
