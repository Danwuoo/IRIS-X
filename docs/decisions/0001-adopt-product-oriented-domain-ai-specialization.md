# Decision 0001: Adopt Product-Oriented Domain AI Specialization

- Status: Accepted
- Date: 2026-09-17
- Scope: P0 product transition

## Decision

IRIS-X adopts `PRODUCT_THESIS.md` as its canonical product thesis and adopts the
following product direction:

- domain AI specialization is an engineering configuration and selection
  problem, not a predetermined training procedure;
- the primary input is a **Domain Specification** covering domain material,
  real workloads, explicit requirements, and operating constraints;
- **Build–Measure–Select** is the default development method;
- an **Engineering Trial** is the primary empirical unit for deciding whether
  an intervention earns promotion;
- the principal deliverable is a versioned, reproducible, deployable
  **Domain Package**;
- product engineering is the default track, while research is opened
  selectively by unresolved product pressure.

The source thesis was verified at SHA-256
`373105e33a500c821ea7ca1f5d45a077ec2d6f381250cf79859cbfa6a83d7a63`
before being placed at its canonical path. Its content is preserved exactly.

## Consequences

Active governance and navigation now describe this adopted direction. The
pre-product repository is a read-only cold archive referenced by the annotated
tag `archive/pre-product-transition-2026-09-17`; historical documents and code
do not govern current work.

## Explicitly undecided

This decision does not select:

- the first domain or workload;
- any provider or model;
- any specialization or infrastructure backend;
- an engineering or inference budget;
- a deployment form;
- the detailed product architecture.

It also does not authorize P1–P4 implementation, model/provider execution, or
an Engineering Trial. Each requires a later owner-authorized scope.
