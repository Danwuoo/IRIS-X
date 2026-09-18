# Product-Era Repository Layout

Status: active P1 plus admitted P2 ARC-AGI-2 trial layout as of 2026-09-18.

| Path | Role | Current state |
| --- | --- | --- |
| `PRODUCT_THESIS.md` | Canonical product authority | Adopted and byte-verified |
| `docs/product/` | Product scope, contracts, package format, non-goals, and admission | P1 contracts, historical P2 admission, and current ARC-AGI-2 scope documented |
| `docs/development/` | Operating model and data/execution policy | Offline P1 and admitted P2 work governed |
| `docs/decisions/` | Current decisions | Product direction, P1 foundation, historical P2 block, and ARC-AGI-2 admission recorded |
| `src/irisx/` | Product implementation | P1 contracts/reference flow, historical admission validator, and ARC-AGI-2 materialization, isolation, pass@2, preflight, acceptance, and package-profile validation |
| `tests/` | Active tests | Repository, contracts, selection, package, CLI, admission, and admitted-trial coverage |
| `trials/` | Admission and Engineering Trials | Historical admission package plus tracked ARC-AGI-2 Trial 001 profile; real trial not run |
| `research/` | Product-driven research | Conditional; no question opened |
| `tools/` | Current utilities | Offline repository validator only |
| `archive/` | Git-native historical catalog | Read-only |
| `.irisx/` | Generated local outputs | Ignored |

Decision 0004 selects the first domain, official data boundary, local/offline
path, one intervention, zero external paid-execution budget, acceptance gate,
and research-package deployment target. The historical P2 admission package
does not authorize execution. The concrete local model/solver and execution
envelope remain unbound, detailed production architecture remains undecided,
and the real run requires a separate explicit owner authorization.

Historical payload is not deep-moved into `archive/`. Its original tree is
addressed by the annotated tag `archive/pre-product-transition-2026-09-17`;
the active `archive/` directory contains only recovery metadata.
