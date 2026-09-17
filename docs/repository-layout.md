# Product-Era Repository Layout

Status: active P1 layout as of 2026-09-17.

| Path | Role | P1 state |
| --- | --- | --- |
| `PRODUCT_THESIS.md` | Canonical product authority | Adopted and byte-verified |
| `docs/product/` | Product scope, contracts, package format, and non-goals | P1 contracts documented |
| `docs/development/` | Operating model and data/execution policy | Offline P1 execution governed |
| `docs/decisions/` | Current decisions | Product direction and P1 foundation recorded |
| `src/irisx/` | Product implementation | P1 contracts and offline reference flow |
| `tests/` | Active tests | Repository, contracts, selection, CLI, and package coverage |
| `trials/` | Real Engineering Trials | Reserved; no real trial selected or run |
| `research/` | Product-driven research | Conditional; no question opened |
| `tools/` | Current utilities | Offline repository validator only |
| `archive/` | Git-native historical catalog | Read-only |
| `.irisx/` | Generated local outputs | Ignored |

The first domain, provider/model, backend, budget, deployment form, and detailed
architecture are undecided. The P1 implementation does not settle those choices
or authorize P2.

Historical payload is not deep-moved into `archive/`. Its original tree is
addressed by the annotated tag `archive/pre-product-transition-2026-09-17`;
the active `archive/` directory contains only recovery metadata.
