# Product Scope

Status: current product policy through P2 admission, grounded in
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

## P1 authorized scope

P0 established authority, policy, repository layout, archival recovery, and
offline validation. P1 adds versioned contracts, canonical JSON, a deterministic
synthetic qualification fixture, provider-neutral selection semantics, and a
reproducible Domain Package builder/verifier. The P1 qualification fixture is
explicitly not a real Engineering Trial and cannot support a product-effectiveness
claim.

P2 repository work has started at the admission layer, but the first real
domain and workload, data rights, provider/model, specialization backend,
budget, deployment form, external execution, and detailed production
architecture remain undecided. Decision 0003 therefore marks P2
admission-blocked. A later admitted trial must supply a separately authorized
Domain Specification and real workload through the contracts in
[`contracts.md`](contracts.md), changing a contract only through a reviewed
schema-version decision rather than by accidental fixture-specific drift.
