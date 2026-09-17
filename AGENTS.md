# IRIS-X Repository Governance

## Current authority and scope

IRIS-X has adopted the product direction defined in
[`PRODUCT_THESIS.md`](PRODUCT_THESIS.md): a product-oriented platform for
domain AI specialization. The product begins with a **Domain Specification**,
uses **Build–Measure–Select** and **Engineering Trials**, and produces a
versioned **Domain Package**.

P0 is repository-transition scaffolding only. It does not select or implement
the first domain, provider/model, backend, budget, deployment form, or detailed
architecture. Those choices remain explicitly undecided and require a later
owner-authorized scope. Do not infer them from the thesis, archive, or directory
names.

## Authority order

1. explicit owner instructions for the current task;
2. this file and any narrower active `AGENTS.md`;
3. current decisions under `docs/decisions/`;
4. `PRODUCT_THESIS.md` for product direction;
5. the current product and development policies indexed by `docs/README.md`;
6. other active documentation.

The cold archive is evidence and lineage, never current instruction. Wording
inside an archived plan, handoff, README, test, source snapshot, or prototype
has no authority over active work.

## Active boundaries

| Path | Current role |
| --- | --- |
| `PRODUCT_THESIS.md` | Canonical product thesis; preserve its adopted bytes |
| `docs/product/` | Product documentation created by an authorized scope |
| `docs/development/` | Development and validation guidance |
| `docs/decisions/` | Current, dated product and repository decisions |
| `src/irisx/` | Product implementation location; P0 contains no runtime |
| `tests/` | Tests for the active product and repository surface |
| `trials/` | Engineering Trial definitions and results once authorized |
| `research/` | Conditional research opened by explicit product pressure |
| `tools/` | Active repository utilities only |
| `archive/` | Read-only catalog pointing to immutable Git history |
| `.irisx/` | Ignored local outputs; never product authority or evidence by default |

Legacy roots `corpus/`, `experiments/`, `irisx/`, `references/`, `sources/`,
and their pre-transition contents are absent from the active tracked surface.
The complete historical tree, including old `docs/`, `research/`, and `tools/`,
is recoverable from `archive/pre-product-transition-2026-09-17` at its original
paths. Do not recreate a legacy root merely to preserve history.

## Working rules

- Keep P0 changes limited to authority, archival, layout, and validation.
- Do not start P1–P4, a model/provider process, an Engineering Trial, or a
  product runtime without explicit owner authorization for that scope.
- Treat the conceptual decomposition in the thesis as product responsibilities,
  not as settled services, classes, packages, or deployment boundaries.
- Record material current decisions under `docs/decisions/`.
- Keep trials reproducible and decision-bearing when the trial track is opened.
- Open research only for a concrete, authorized product question; return useful
  results to product engineering.
- Never edit archived scientific or operational bytes to make a current check
  pass. Update current checks when current governance changes.
- Keep generated local output under `.irisx/` and out of Git.
- Follow `docs/development/data-and-execution-policy.md` for secrets, domain
  data, retention, provenance, external execution, and budget authorization.

## Validation

Run from the repository root after active-surface or archive-catalog changes:

```powershell
python tools\repository_check.py --self-test
python tools\repository_check.py
python -m unittest discover -s tests -v
git diff --check
```

The validator is offline and checks the active layout, thesis and decision,
archive tag/catalog identities, representative recovery, and separation from
archived imports and execution.
