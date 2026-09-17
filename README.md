# IRIS-X

IRIS-X is a product-oriented platform for turning domain material, real
workloads, explicit requirements, and operating constraints into measured,
deployable domain AI configurations.

The current product authority is [`PRODUCT_THESIS.md`](PRODUCT_THESIS.md).
IRIS-X treats domain specialization as an engineering configuration problem:
it starts from a **Domain Specification**, follows **Build–Measure–Select**,
uses **Engineering Trials** to decide which interventions earn promotion, and
produces a versioned **Domain Package**.

P0 establishes product authority, repository boundaries, and a Git-native cold
archive. It does not implement product contracts or runtime behavior. The first
domain, provider/model, backend, budget, deployment form, and detailed
architecture remain undecided.

## Active repository

| Path | Purpose |
| --- | --- |
| [`PRODUCT_THESIS.md`](PRODUCT_THESIS.md) | Adopted product thesis |
| [`docs/product/`](docs/product/README.md) | Future product requirements and concepts |
| [`docs/development/`](docs/development/README.md) | Current development guidance |
| [`docs/decisions/`](docs/decisions/README.md) | Current decisions |
| [`src/irisx/`](src/irisx/README.md) | Reserved product source location |
| [`tests/`](tests/README.md) | Active validation and future product tests |
| [`trials/`](trials/README.md) | Future Engineering Trials |
| [`research/`](research/README.md) | Conditional product-driven research |
| [`archive/`](archive/README.md) | Read-only catalog of the pre-product repository |
| [`tools/`](tools/README.md) | Active offline repository validation |

Start with [`AGENTS.md`](AGENTS.md) and
[`docs/decisions/0001-adopt-product-oriented-domain-ai-specialization.md`](docs/decisions/0001-adopt-product-oriented-domain-ai-specialization.md).

Validate P0 from the repository root:

```powershell
python tools\repository_check.py --self-test
python tools\repository_check.py
python -m unittest discover -s tests -v
```
