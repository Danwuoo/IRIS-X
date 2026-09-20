# Product-Era Repository Layout

Status: active P1 plus Decision 0005/0006/0007 ARC-AGI-2 Kaggle handoff as of 2026-09-20.

| Path | Role | Current state |
| --- | --- | --- |
| `PRODUCT_THESIS.md` | Canonical product authority | Adopted and byte-verified |
| `docs/product/` | Product scope, contracts, package format, non-goals, and admission | P1 contracts, historical P2 admission, and current ARC-AGI-2 scope documented |
| `docs/development/` | Operating model and data/execution policy | Offline P1 and admitted P2 work governed |
| `docs/decisions/` | Current decisions | Product direction, P1 foundation, historical P2 block, ARC-AGI-2 admission, and Kaggle handoff recorded |
| `src/irisx/` | Product implementation | P1 contracts/reference flow, historical admission validator, ARC trial/scorer, closed-world transport, Kaggle import/preflight, and package verification |
| `tests/` | Active tests | Repository, contracts, selection, package, CLI, admission, and admitted-trial coverage |
| `trials/` | Admission and Engineering Trials | Historical admission plus static ARC-AGI-2 notebook/workspace tracked; Trial 001 not run |
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
Decision 0005 replaces only the venue with a manual private-Dataset Kaggle
handoff, selects the frozen Qwen revision, and keeps evaluator truth and all
scoring on the repository host. Decision 0006 makes the provenance-bound
unpacked model Dataset the active model representation. Decision 0007 binds
the Kaggle-extracted trial tree and its canonical manifest identity.

Historical payload is not deep-moved into `archive/`. Its original tree is
addressed by the annotated tag `archive/pre-product-transition-2026-09-17`;
the active `archive/` directory contains only recovery metadata.
