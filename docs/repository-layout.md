# Product-Era Repository Layout

Status: active P1, closed ARC-AGI-2 Trial 001, and runtime-verified bounded
Trial 002 smoke under the Decision 0010 lightweight development workflow as of
2026-09-22.

| Path | Role | Current state |
| --- | --- | --- |
| `PRODUCT_THESIS.md` | Canonical product authority | Adopted and byte-verified |
| `docs/product/` | Product scope, contracts, package format, non-goals, and admission | P1 contracts, historical P2 admission, and current ARC-AGI-2 scope documented |
| `docs/development/` | Operating model and data/execution policy | Offline P1 and admitted P2 work governed |
| `docs/decisions/` | Current decisions | Product direction, P1 foundation, historical P2 block, ARC-AGI-2 admission, and Kaggle handoff recorded |
| `src/irisx/` | Product implementation | P1 contracts/reference flow, historical admission validator, retained Trial 001 implementation, Trial 002 bounded runner/evaluator, closed-world transport, quarantine, and package verification |
| `tests/` | Active tests | Repository, contracts, selection, package, CLI, admission, and admitted-trial coverage |
| `trials/` | Admission and Engineering Trials | Historical admission, closed Trial 001 status and lineage, plus the runtime-verified Trial 002 status, audit, and notebook |
| `research/` | Product-driven research | Conditional; no question opened |
| `tools/` | Current utilities | Offline repository validator and read-only Trial 001 layout audit |
| `archive/` | Git-native historical catalog | Read-only |
| `.irisx/` | Generated local outputs | Ignored |

The [`Trial 001 status page`](../trials/first-real-domain/README.md) carries the
terminal state and retained boundary. Decisions 0004–0009
retain the exact data, model, transport, runtime, and `run-001` identities.
Decision 0010 removes the need to repeat that chain across current guidance:
routine local work proceeds directly, while any future external run requires a
new scoped question, explicit owner authorization, and a passing technical
preflight. Decision 0011
adds the distinct checkpoint-aware `run-002` v4 transport without changing the
frozen `run-001` bytes. Decision 0013 preserves both earlier identities and
authorized only a four-invocation, unbounded-time `run-003` v5 completion
benchmark with checkpoint and `result.zip` evidence. Decision 0012 closes the
trial without a locally accepted result, score, promotion, or Domain Package.
Decision 0014 opens the separate Trial 002 question. Decision 0015 preserves
the failed first smoke and authorizes one competition-mounted replacement with
runtime-verified L4 x4 and exactly four Qwen3.5-4B inference invocations. That
replacement completed with four valid grids and 0/4 local exact match; its
external execution and retrieval authority is consumed.

Historical payload is not deep-moved into `archive/`. Its original tree is
addressed by the annotated tag `archive/pre-product-transition-2026-09-17`;
the active `archive/` directory contains only recovery metadata.
