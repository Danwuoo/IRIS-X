# IRIS-X

IRIS-X is a product-oriented platform for turning domain material, real
workloads, explicit requirements, and operating constraints into measured,
deployable domain AI configurations.

The current product authority is [`PRODUCT_THESIS.md`](PRODUCT_THESIS.md).
IRIS-X treats domain specialization as an engineering configuration problem:
it starts from a **Domain Specification**, follows **Build–Measure–Select**,
uses **Engineering Trials** to decide which interventions earn promotion, and
produces a versioned **Domain Package**.

P1 supplies the minimal provider-neutral contracts and deterministic offline
qualification flow. The first P2 Engineering Trial used ARC-AGI-2 with one
static specialization intervention and a frozen offline Qwen3.8-27B execution
path. It is now closed as `inconclusive-no-promotion`: no complete measurement,
score, candidate selection, or Domain Package was produced. Its terminal state
is maintained in the
[`Trial 001 status page`](trials/first-real-domain/README.md).

[`Decision 0010`](docs/decisions/0010-adopt-lightweight-risk-based-development.md)
keeps the product goal and Build–Measure–Select method while simplifying daily
development: routine local, offline, reversible work proceeds directly;
decisions and owner gates are reserved for durable or risky boundary changes.
After the non-checkpointing `run-001` attempt returned no result, Decision 0011
adds the separately identified v4 `run-002` path with atomic per-invocation
checkpoints and cumulative-budget resume. It does not authorize execution.
Decision 0013 preserves that executed identity and adds v5 `run-003`, with no
runner time limit, exactly four invocations, resumable checkpoints, complete raw
generation evidence, and `result.zip`. Decision 0012 ends that execution
authority without accepting a returned result and records the terminal
inconclusive closure.

Decision 0014 opens a separate ARC-AGI-2 Trial 002 completable-baseline
question. It selects exact Qwen3.5-4B and NVARC source identities, fixes four
answer-blind public-training tasks, and authorizes one private bounded Kaggle
L4 x4 smoke. Decision 0015 preserves that failed first attempt and authorizes a
replacement identity with the real ARC competition mounted, runtime-verified
L4 x4, and exactly four inference-only generation calls. The replacement has
completed with four valid grids and a local exact-match result of 0/4; its
external execution authority is consumed. Its status lives in
[`trials/arc-agi-2-baseline/README.md`](trials/arc-agi-2-baseline/README.md);
it does not reopen Trial 001 or claim public-evaluation performance.

## Quickstart

IRIS-X requires Python 3.11 or later and has no third-party runtime dependencies.
Install the local CLI, then run the complete synthetic flow:

```powershell
python -m pip install --no-build-isolation -e .
irisx fixture prepare --output .irisx/quickstart/fixture
irisx spec validate .irisx/quickstart/fixture/specification.json
irisx trial validate .irisx/quickstart/fixture/trial.json
irisx trial run --trial .irisx/quickstart/fixture/trial.json --output .irisx/quickstart/run
irisx package build --run .irisx/quickstart/run --output .irisx/quickstart/package
irisx package verify .irisx/quickstart/package
irisx admission validate trials/p2-admission/admission.json
```

The retired Trial 001 operational flow and frozen lineage are documented in
[`docs/development/arc-agi-2-kaggle-handoff.md`](docs/development/arc-agi-2-kaggle-handoff.md).
No default validation command downloads weights, uploads to Kaggle, or executes
the real workload.

Every generated file remains under ignored `.irisx/`. Repeating the flow with
identical inputs produces identical canonical contracts and package bytes.

## Active repository

| Path | Purpose |
| --- | --- |
| [`PRODUCT_THESIS.md`](PRODUCT_THESIS.md) | Adopted product thesis |
| [`docs/product/`](docs/product/README.md) | Current product scope, contracts, package, and P2 trial admission |
| [`docs/development/`](docs/development/README.md) | Operating model and data/execution policy |
| [`docs/decisions/`](docs/decisions/README.md) | Current decisions |
| [`src/irisx/`](src/irisx/) | P1 contracts/reference flow/package verification, historical admission validation, retained Trial 001 implementation, and the bounded Trial 002 runner/evaluator |
| [`tests/`](tests/README.md) | Active P1, P2 admission, and closed-trial tests |
| [`trials/`](trials/README.md) | Historical P2 admission, closed ARC-AGI-2 Trial 001, and runtime-verified bounded Trial 002 workspace |
| [`research/`](research/README.md) | Conditional product-driven research |
| [`archive/`](archive/README.md) | Read-only catalog of the pre-product repository |
| [`tools/`](tools/README.md) | Active offline repository validation |

Start with [`AGENTS.md`](AGENTS.md), the
[`development operating model`](docs/development/operating-model.md), and the
closed Trial 001 status page. Use the
[`decisions index`](docs/decisions/README.md) when the rationale or an exact
binding is needed.
The current product, development, decision, contract, and P2 trial-admission
documentation is indexed from [`docs/README.md`](docs/README.md).

Validate the active repository from the repository root:

```powershell
python tools\repository_check.py --all
```
