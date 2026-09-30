# Documentation

This directory contains only current product-era guidance.

- [`plan/2026-09-30-nvarc-method-completeness.md`](plan/2026-09-30-nvarc-method-completeness.md)
  records the source/method boundaries, six-source lineage importer, complete
  task epoch, SFT training semantics and data-gated inert development comparison.

- [`plan/2026-09-26-nvarc-combined-two-gpu-notebook.md`](plan/2026-09-26-nvarc-combined-two-gpu-notebook.md)
  scopes owner-authorized local development of one notebook with isolated M2
  and M3 GPU workers, offline validation and an inert execution proposal.

- [`plan/2026-09-24-nvarc-source-integration.md`](plan/2026-09-24-nvarc-source-integration.md)
  records owner-authorized source acquisition, direct integration and
  differential validation for the Qwen3.5 NVARC port; its later GPU and teacher
  execution envelope remains a proposal.

- [`plan/2026-09-23-qwen35-nvarc-acceptance-continuation.md`](plan/2026-09-23-qwen35-nvarc-acceptance-continuation.md)
  records the incomplete acceptance review and concrete repairs and remaining
  development for the original Qwen3.5 NVARC task on main.

- [`plan/2026-09-23-qwen35-nvarc-reproduction.md`](plan/2026-09-23-qwen35-nvarc-reproduction.md)
  defines the owner-requested Qwen3.5-4B NVARC development plan, including
  data, SFT, task-local adaptation, candidate ranking, integration, offline
  validation and a separate proposal for future real execution.

- [`plan/2026-09-23-research-control-handoff.md`](plan/2026-09-23-research-control-handoff.md)
  hands verified experimental results, local evidence locations and open
  research choices to the next GPT-6 Astra high control task.

- [`plan/2026-09-23-arc-reasoning-budget-ablation.md`](plan/2026-09-23-arc-reasoning-budget-ablation.md)
  defines the Decision 0020 authorized output-budget and thinking-mode
  diagnostic after the negative prompt search, with conditional validation.
- [`plan/2026-09-22-dspy-gepa-prompt-pilot.md`](plan/2026-09-22-dspy-gepa-prompt-pilot.md)
  retains the completed prompt experiment plan, with Qwen3.5-4B solving,
  Codex CLI reflection, grouped data splits, and bounded DSPy/GEPA integration.
- [`decisions/0017-authorize-prompt-pilot-mount-repair.md`](decisions/0017-authorize-prompt-pilot-mount-repair.md)
  authorizes one transport-only replacement after the first prompt-pilot
  baseline failed before model load on Kaggle's current Dataset mount topology.
- [`plan/2026-09-22-trial-002-kaggle-smoke-repair.md`](plan/2026-09-22-trial-002-kaggle-smoke-repair.md)
  scopes the fresh-task repair of competition mounting, actual L4 x4 execution,
  and exactly four Qwen3.5-4B inference invocations.
- [`plan/2026-09-22-arc-agi-2-completable-baseline.md`](plan/2026-09-22-arc-agi-2-completable-baseline.md)
  records the owner-directed Trial 002 baseline development scope, source and
  model strategy, bounded Kaggle CLI smoke, and implementation handoff.
- [`product/product-scope.md`](product/product-scope.md) defines the adopted
  product boundary, P1 foundation, and admitted P2 ARC-AGI-2 scope.
- [`product/non-goals.md`](product/non-goals.md) records durable exclusions and
  guards against technique- or framework-led scope drift.
- [`product/contracts.md`](product/contracts.md) defines the eight P1 contract
  families, common envelope, evidence states, and identity bindings.
- [`product/domain-package.md`](product/domain-package.md) defines the minimal
  package layout and closed-world verification rules.
- [`product/p2-admission.md`](product/p2-admission.md) defines the current
  relationship between the historical blocked P2 snapshot and current Decision
  0004 trial admission.
- [`development/operating-model.md`](development/operating-model.md) defines
  the lightweight Build–Measure–Select loop and the routine-versus-gated
  boundary adopted by Decision 0010.
- [`development/data-and-execution-policy.md`](development/data-and-execution-policy.md)
  governs secrets, domain data, local outputs, retention, provenance, budgets,
  and external/provider execution.
- [`development/arc-agi-2-kaggle-handoff.md`](development/arc-agi-2-kaggle-handoff.md)
  retains the detailed manual Trial 001 package, notebook, quarantine, local
  evaluation, and preflight procedure as closed-trial lineage.
- [`development/arc-agi-2-trial-002-kaggle-smoke.md`](development/arc-agi-2-trial-002-kaggle-smoke.md)
  records the bounded private Dataset/kernel procedure and verified local
  quarantine outcome for the completed Decision 0015 Trial 002 repair smoke.
- [`../trials/first-real-domain/README.md`](../trials/first-real-domain/README.md)
  is the single current status page for Trial 001.
- [`../trials/arc-agi-2-baseline/README.md`](../trials/arc-agi-2-baseline/README.md)
  is the single current status page for Trial 002.
- [`../trials/arc-agi-2-qwen35-nvarc/README.md`](../trials/arc-agi-2-qwen35-nvarc/README.md)
  is the distinct development status page for the owner-requested Qwen3.5
  NVARC port; Decisions 0021–0025 retain the bounded 4B Kaggle pilot lineage.
- [`plan/2026-09-26-nvarc-source-teacher-continuation.md`](plan/2026-09-26-nvarc-source-teacher-continuation.md)
  records the local source-bundle/export continuation, teacher completeness
  gates and inert packages after Decision 0032's consumed terminal runs.
- [`decisions/`](decisions/README.md) contains accepted boundary decisions and
  historical rationale.
- [`repository-layout.md`](repository-layout.md) defines the active P1 plus
  closed Trial 001 and runtime-verified Trial 002 layout.

Pre-product documentation remains at its original paths in the cold-archive
tag and is cataloged under [`../archive/`](../archive/README.md). It is not
active guidance.
