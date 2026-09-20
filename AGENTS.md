# IRIS-X Repository Governance

## Current authority and scope

IRIS-X has adopted the product direction defined in
[`PRODUCT_THESIS.md`](PRODUCT_THESIS.md): a product-oriented platform for
domain AI specialization. The product begins with a **Domain Specification**,
uses **Build–Measure–Select** and **Engineering Trials**, and produces a
versioned **Domain Package**.

P0 repository-transition scaffolding is complete. P1 implements only the
provider-neutral product-contract layer and deterministic offline qualification
flow authorized on 2026-09-17. Decision 0003 and the P2 admission snapshot
remain historical evidence of the prior blocked state. Decision 0004 selects
the first real trial as ARC-AGI-2 on the local/offline path and authorizes its
repository implementation, official-source materialization, offline validation,
and preflight work. It does not authorize the real model/solver run, which still
requires a separate explicit owner authorization after all bindings and gates
are satisfied. Decision 0005 narrowly replaces the execution venue with a
manual, private-Dataset, network-disabled Kaggle handoff on one NVIDIA RTX PRO
6000 96 GB and binds the frozen Trial 001 model to
`Qwen/Qwen3.8-27B@1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`. It does not
authorize the real run. Decision 0006 supersedes only the model ZIP transport:
the active path uses the unpacked, provenance-bound model tree directly from
the private Kaggle Dataset. It also does not authorize the real run.

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
| `src/irisx/` | P1 contracts/reference flow/package verification, historical P2 admission validation, and authorized ARC-AGI-2 trial implementation |
| `tests/` | Tests for the active product and repository surface |
| `trials/` | Historical P2 admission package and the admitted ARC-AGI-2 trial workspace; real execution only after separate authorization |
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

- Keep current P2 work within Decision 0004 as narrowly amended by Decisions
  0005 and 0006: the minimum ARC-AGI-2 Trial 001 implementation, official
  source and raw-model materialization, manual Kaggle handoff, deterministic
  offline validation, quarantine import, local evaluation, preflight,
  documentation, and tests. Do not broaden it into a general framework or
  production runtime.
- Preserve Decision 0003 and `trials/p2-admission/admission.json` as immutable
  historical blocked-state evidence. Never reinterpret or mutate that v1.0
  snapshot into an authorization token.
- Do not execute the real ARC-AGI-2 model/solver trial without a later explicit
  owner execution authorization and all Decision 0004/0005/0006 preflight gates. Do
  not start P3/P4, call an external model provider, use third-party ARC data,
  enable notebook Internet during measured execution, automate Kaggle
  credentials or transport, spend external funds, fine-tune the selected model,
  or build a production runtime.
- A network fetch, if implemented for the approved `arcprize/ARC-AGI-2`
  upstream at commit `f3283f727488ad98fe575ea6a5ac981e4a188e49`, must be a
  deliberate source-materialization command separated from trial execution;
  default tests and validation remain offline.
- A model fetch, if invoked, may acquire only the Decision 0005 Qwen repository
  and revision. It must remain separate from tests, validation, packaging,
  preflight, Kaggle execution, and the real trial. Kaggle upload/download is
  manual; the private Dataset contains the unpacked model files bound by
  Decision 0006 provenance. Evaluator truth and answer-derived metadata never
  enter an outbound package or notebook.
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
