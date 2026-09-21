# Product-Era Repository Layout

Status: active P1 plus ARC-AGI-2 Trial 001 under the Decision 0010 lightweight
development workflow as of 2026-09-22.

| Path | Role | Current state |
| --- | --- | --- |
| `PRODUCT_THESIS.md` | Canonical product authority | Adopted and byte-verified |
| `docs/product/` | Product scope, contracts, package format, non-goals, and admission | P1 contracts, historical P2 admission, and current ARC-AGI-2 scope documented |
| `docs/development/` | Operating model and data/execution policy | Offline P1 and admitted P2 work governed |
| `docs/decisions/` | Current decisions | Product direction, P1 foundation, historical P2 block, ARC-AGI-2 admission, and Kaggle handoff recorded |
| `src/irisx/` | Product implementation | P1 contracts/reference flow, historical admission validator, ARC trial/scorer, closed-world transport, Kaggle import/preflight, and package verification |
| `tests/` | Active tests | Repository, contracts, selection, package, CLI, admission, and admitted-trial coverage |
| `trials/` | Admission and Engineering Trials | Historical admission plus static ARC-AGI-2 notebook/workspace tracked; no returned Trial 001 result has completed repository verification and import |
| `research/` | Product-driven research | Conditional; no question opened |
| `tools/` | Current utilities | Offline repository validator and read-only Trial 001 layout audit |
| `archive/` | Git-native historical catalog | Read-only |
| `.irisx/` | Generated local outputs | Ignored |

The [`Trial 001 status page`](../trials/first-real-domain/README.md) carries the
current state, next action, and fixed execution boundary. Decisions 0004–0009
retain the exact data, model, transport, runtime, and `run-001` identities.
Decision 0010 removes the need to repeat that chain across current guidance:
routine local work proceeds directly, while the real run requires a separate
explicit owner authorization and a passing technical preflight. Decision 0011
adds the distinct checkpoint-aware `run-002` v4 transport without changing the
frozen `run-001` bytes. Decision 0013 preserves both earlier identities and
authorizes only a four-invocation, unbounded-time `run-003` v5 completion
benchmark with checkpoint and `result.zip` evidence.

Historical payload is not deep-moved into `archive/`. Its original tree is
addressed by the annotated tag `archive/pre-product-transition-2026-09-17`;
the active `archive/` directory contains only recovery metadata.
