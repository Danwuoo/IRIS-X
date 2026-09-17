# Product-Era Repository Layout

Status: active P1 plus P2 admission-only layout as of 2026-09-17.

| Path | Role | Current state |
| --- | --- | --- |
| `PRODUCT_THESIS.md` | Canonical product authority | Adopted and byte-verified |
| `docs/product/` | Product scope, contracts, package format, non-goals, and admission | P1 contracts plus P2 admission documented |
| `docs/development/` | Operating model and data/execution policy | Offline P1 execution governed |
| `docs/decisions/` | Current decisions | Product direction, P1 foundation, and P2 admission block recorded |
| `src/irisx/` | Product implementation | P1 contracts/reference flow plus admission validator |
| `tests/` | Active tests | Repository, contracts, selection, package, CLI, and admission coverage |
| `trials/` | Admission and Engineering Trials | Admission package tracked; no real trial selected or run |
| `research/` | Product-driven research | Conditional; no question opened |
| `tools/` | Current utilities | Offline repository validator only |
| `archive/` | Git-native historical catalog | Read-only |
| `.irisx/` | Generated local outputs | Ignored |

The first domain, provider/model, backend, budget, deployment form, and detailed
architecture are undecided. The P2 admission package does not settle those
choices or authorize real execution.

Historical payload is not deep-moved into `archive/`. Its original tree is
addressed by the annotated tag `archive/pre-product-transition-2026-09-17`;
the active `archive/` directory contains only recovery metadata.
