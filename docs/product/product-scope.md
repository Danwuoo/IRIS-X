# Product Scope

Status: current product policy through the Decision 0005 Kaggle handoff, grounded in
[`PRODUCT_THESIS.md`](../../PRODUCT_THESIS.md) and
[`Decision 0001`](../decisions/0001-adopt-product-oriented-domain-ai-specialization.md),
with the bounded trial scope selected by
[`Decision 0004`](../decisions/0004-admit-first-p2-arc-agi-2-engineering-trial.md).

Decision 0005 changes only the Trial 001 execution venue, manual transport, and
frozen model binding.

## Product boundary

IRIS-X is a product-oriented platform for transforming a **Domain
Specification** into a measured, reproducible, and deployable **Domain Package**.
The Domain Specification describes domain material, representative
workloads, explicit success requirements, and operating constraints. The Domain
Package records the selected configuration, its evaluation basis, operational
metadata, known limitations, and the artifacts needed to reproduce and deploy
it.

IRIS-X treats specialization as an engineering configuration problem. Models,
prompts, retrieval, tools, workflows, training, routing, verification, and
runtime controls are possible interventions, not mandatory stages. They earn a
place through **Build–Measure–Select** and an authorized **Engineering Trial**
that demonstrates useful improvement against the relevant workload and costs.

## Product responsibilities

The thesis identifies five conceptual responsibilities: domain intake,
evaluation, specialization, selection, and packaging. These are product
responsibilities, not settled services, modules, APIs, repositories, or
deployment boundaries.

Product success means satisfying declared domain requirements under real
quality, cost, latency, complexity, maintainability, privacy, and resource
constraints. Minimum-sufficient configurations are preferred over unnecessary
capability or architecture.

## P1 authorized scope

P0 established authority, policy, repository layout, archival recovery, and
offline validation. P1 adds versioned contracts, canonical JSON, a deterministic
synthetic qualification fixture, provider-neutral selection semantics, and a
reproducible Domain Package builder/verifier. The P1 qualification fixture is
explicitly not a real Engineering Trial and cannot support a product-effectiveness
claim.

Decision 0003 and its blocked admission snapshot remain historical evidence.
Decision 0004 now selects ARC-AGI-2 as the first real domain, the complete
official public evaluation split as the frozen workload, the official public
training split as the only specialization material, a local/offline path with
zero external paid-execution budget, one static `prompts_programs`
intervention, a five-percentage-point acceptance threshold, and a
self-contained single-machine offline research-solver package as the deployment
target.

The admitted scope covers the minimum repository implementation, exact official
source materialization, deterministic offline validation, and preflight work.
Decision 0005 selects the exact Qwen3.8-27B revision and a manual,
network-disabled Kaggle notebook using one NVIDIA RTX PRO 6000 96 GB. Exact
model-package bytes, private Dataset versions, runtime dependencies, resource
and retention bindings, and owner execution authorization remain unresolved
until preflight. Detailed production architecture remains undecided, and the real run
requires a separate explicit owner execution authorization. Trial artifacts
must use the contracts in [`contracts.md`](contracts.md), changing a contract
only through a reviewed schema-version decision rather than accidental
fixture-specific drift.

Other deployment forms and all product architecture beyond this bounded trial
remain undecided.
