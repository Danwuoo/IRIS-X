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
not a real domain Engineering Trial or evidence of product effectiveness. The
first real domain, provider/model, backend, budget, deployment form, and
detailed production architecture remain undecided. P2 has started at the
admission layer, but Decision 0003 marks it admission-blocked and authorizes no
real trial execution.

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

## Active repository

| Path | Purpose |
| --- | --- |
| [`PRODUCT_THESIS.md`](PRODUCT_THESIS.md) | Adopted product thesis |
| [`docs/product/`](docs/product/README.md) | Current product scope, contracts, package, and P2 admission |
| [`docs/development/`](docs/development/README.md) | Operating model and data/execution policy |
| [`docs/decisions/`](docs/decisions/README.md) | Current decisions |
| [`src/irisx/`](src/irisx/) | P1 contracts/reference flow/package verification and P2 admission validation |
| [`tests/`](tests/README.md) | Active P1 and P2 admission tests |
| [`trials/`](trials/README.md) | P2 admission package and reserved real Engineering Trials |
| [`research/`](research/README.md) | Conditional product-driven research |
| [`archive/`](archive/README.md) | Read-only catalog of the pre-product repository |
| [`tools/`](tools/README.md) | Active offline repository validation |

Start with [`AGENTS.md`](AGENTS.md) and the
[`current decisions index`](docs/decisions/README.md).
The current product, development, decision, contract, and P2 admission
documentation is indexed from [`docs/README.md`](docs/README.md).

Validate the active repository from the repository root:

```powershell
python tools\repository_check.py --self-test
python tools\repository_check.py
python -m unittest discover -s tests -v
git diff --check
```
