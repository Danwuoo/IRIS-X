# Product Scope

Status: current P0 policy, grounded in
[`PRODUCT_THESIS.md`](../../PRODUCT_THESIS.md) and
[`Decision 0001`](../decisions/0001-adopt-product-oriented-domain-ai-specialization.md).

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

## P0 boundary

P0 establishes authority, policy, repository layout, archival recovery, and
offline validation. It does not implement product contracts or runtime code.
The first domain and workload, provider/model, backend, budget, deployment form,
schemas, APIs, and detailed architecture remain undecided. Each requires a
later owner-authorized scope and, where material, a current decision record.
