# Product-Era Repository Layout

Status: active P0 layout as of 2026-09-17.

| Path | Role | P0 state |
| --- | --- | --- |
| `PRODUCT_THESIS.md` | Canonical product authority | Adopted and byte-verified |
| `docs/product/` | Product scope, non-goals, and future requirements | P0 policy set; contracts reserved |
| `docs/development/` | Operating model and data/execution policy | P0 policy set; runtime reserved |
| `docs/decisions/` | Current decisions | Product direction recorded |
| `src/irisx/` | Product implementation | Reserved; no P1 contracts/runtime |
| `tests/` | Active tests | Repository-transition coverage only |
| `trials/` | Engineering Trials | Reserved; no trial selected or run |
| `research/` | Product-driven research | Conditional; no question opened |
| `tools/` | Current utilities | Offline repository validator only |
| `archive/` | Git-native historical catalog | Read-only |
| `.irisx/` | Generated local outputs | Ignored |

The first domain, provider/model, backend, budget, deployment form, and detailed
architecture are undecided. This layout reserves homes for future work without
settling those choices or implementing P1.

Historical payload is not deep-moved into `archive/`. Its original tree is
addressed by the annotated tag `archive/pre-product-transition-2026-09-17`;
the active `archive/` directory contains only recovery metadata.
