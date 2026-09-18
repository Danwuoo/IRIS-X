# IRIS-X

IRIS-X is a product-oriented platform for turning domain material, real
workloads, explicit requirements, and operating constraints into measured,
deployable domain AI configurations.

The current product authority is [`PRODUCT_THESIS.md`](PRODUCT_THESIS.md).
IRIS-X treats domain specialization as an engineering configuration problem:
it starts from a **Domain Specification**, follows **Build–Measure–Select**,
uses **Engineering Trials** to decide which interventions earn promotion, and
produces a versioned **Domain Package**.

P1 now supplies the minimal provider-neutral product contracts and a bounded,
deterministic offline reference flow. The included synthetic fixture qualifies
validation, evaluation, selection, packaging, and corruption detection; it is
not a real domain Engineering Trial or evidence of product effectiveness.
Decision 0004 admits the first real P2 trial as ARC-AGI-2 on a local/offline,
official-public-data-only path with one minimal specialization intervention.
Its repository implementation, source materialization, offline validation, and
preflight work are authorized; the real model/solver run still requires a
separate explicit owner authorization.

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

Every generated file remains under ignored `.irisx/`. Repeating the flow with
identical inputs produces identical canonical contracts and package bytes.

The admitted ARC-AGI-2 path is documented separately because its deliberate
official-source acquisition is the only networked step. See
[`docs/development/arc-agi-2-trial-001.md`](docs/development/arc-agi-2-trial-001.md)
for source materialization, offline preparation, fail-closed preflight, future
result validation, P2 acceptance, and package verification commands. No real
run command is exposed while the local solver and separate owner execution
authorization remain unbound.

## Active repository

| Path | Purpose |
| --- | --- |
| [`PRODUCT_THESIS.md`](PRODUCT_THESIS.md) | Adopted product thesis |
| [`docs/product/`](docs/product/README.md) | Current product scope, contracts, package, and P2 trial admission |
| [`docs/development/`](docs/development/README.md) | Operating model and data/execution policy |
| [`docs/decisions/`](docs/decisions/README.md) | Current decisions |
| [`src/irisx/`](src/irisx/) | P1 contracts/reference flow/package verification, historical admission validation, and admitted P2 trial implementation |
| [`tests/`](tests/README.md) | Active P1, P2 admission, and admitted-trial tests |
| [`trials/`](trials/README.md) | Historical P2 admission package and admitted ARC-AGI-2 trial workspace |
| [`research/`](research/README.md) | Conditional product-driven research |
| [`archive/`](archive/README.md) | Read-only catalog of the pre-product repository |
| [`tools/`](tools/README.md) | Active offline repository validation |

Start with [`AGENTS.md`](AGENTS.md) and the
[`current decisions index`](docs/decisions/README.md).
The current product, development, decision, contract, and P2 trial-admission
documentation is indexed from [`docs/README.md`](docs/README.md).

Validate the active repository from the repository root:

```powershell
python tools\repository_check.py --self-test
python tools\repository_check.py
python -m unittest discover -s tests -v
git diff --check
```
