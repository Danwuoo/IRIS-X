# Product Scope

Status: current product policy under Decision 0010, grounded in
[`PRODUCT_THESIS.md`](../../PRODUCT_THESIS.md) and
[`Decision 0001`](../decisions/0001-adopt-product-oriented-domain-ai-specialization.md),
with the bounded trial scope selected by
[`Decision 0004`](../decisions/0004-admit-first-p2-arc-agi-2-engineering-trial.md).

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
ARC-AGI-2 is the first real domain and uses the complete official public
evaluation split, the official public training split as the only specialization
material, one static `prompts_programs` intervention, and a five-percentage-point
acceptance threshold. The execution path is offline, zero-paid-spend, and bound
to a frozen Qwen3.8-27B model.

The [`Trial 001 status page`](../../trials/first-real-domain/README.md) is the
current source for its state, next action, and exact operational boundary.
Decisions 0004–0009 retain detailed rationale and immutable evidence bindings.
Detailed production architecture and other deployment forms remain undecided,
and the real run requires separate explicit owner authorization. Trial
artifacts must use the contracts in [`contracts.md`](contracts.md); a public
contract changes only through an explicit schema-version boundary decision.

Other deployment forms and all product architecture beyond this bounded trial
remain undecided.
