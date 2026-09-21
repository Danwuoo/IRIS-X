# IRIS-X Repository Governance

## Current authority and scope

IRIS-X has adopted the product direction defined in
[`PRODUCT_THESIS.md`](PRODUCT_THESIS.md): a product-oriented platform for
domain AI specialization. The product begins with a **Domain Specification**,
uses **Build–Measure–Select** and **Engineering Trials**, and produces a
versioned **Domain Package**.

P0 and P1 established the repository and provider-neutral contract foundation.
ARC-AGI-2 Trial 001 is the active P2 slice. Its goal, current state, next action,
and blockers live in [`trials/first-real-domain/README.md`](trials/first-real-domain/README.md);
Decisions 0004–0009 retain the detailed rationale and frozen evidence bindings.

[`Decision 0010`](docs/decisions/0010-adopt-lightweight-risk-based-development.md)
adopts a lightweight, risk-based workflow. Routine local, offline, reversible
work inside the current boundaries does not need another decision record.
Boundary-crossing work remains gated. In particular, the real ARC-AGI-2 run
still requires a separate explicit owner authorization, and Decision 0009's
`run-001` identities remain frozen until result closure.
Decision 0011 creates a distinct checkpointing `run-002` v4 transport after the
non-checkpointing run-001 attempt failed to finish. It authorizes implementation,
offline packaging, verification, and preflight only, not real execution.
Decision 0013 preserves the executed `run-002` identity and authorizes the exact
four-invocation `run-003` v5 completion benchmark with no runner time limit,
checkpoint resume, and a truth-free `result.zip`. It does not authorize the
remaining 664 invocations or Trial 001 scoring and promotion.

## Authority order

1. explicit owner instructions for the current task;
2. this file and any narrower active `AGENTS.md`;
3. Decision 0010, the active trial status page, and applicable accepted
   decisions under `docs/decisions/`;
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
| `docs/decisions/` | Accepted boundary decisions and historical rationale |
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

- Use the routine lane for local, offline, reversible implementation, tests,
  documentation, refactoring, fixtures, and validation inside the current
  product and trial boundaries. Do not create a decision record for ordinary
  engineering choices.
- Pause for explicit owner direction before changing product scope, a public
  contract, an acceptance threshold, a promotion claim, a frozen identity, or
  before external/provider/paid/sensitive-data or irreversible work. Record a
  decision only when the choice must govern future work.
- Use the Trial 001 README as current status. Consult Decisions 0004–0009 for
  provenance and exact bindings instead of duplicating their full text in new
  documents.
- Preserve the Decision 0009 frozen `run-001` outbound, notebook, runner, and
  manifest identities. Do not move Trial 001 execution bytes until its result
  closure gate passes; never reuse one bundle ID for different outbound bytes.
- Preserve executed `run-002` bytes under Decision 0011. Build the unbounded-time
  four-invocation completion benchmark only as `run-003` with the Decision 0013
  v5 adapter. Both checkpoint formats must be identity-bound, atomic, truth-free,
  and resumable only as a contiguous invocation prefix.
- Preserve Decision 0003 and `trials/p2-admission/admission.json` as immutable
  historical blocked-state evidence. Never reinterpret or mutate that v1.0
  snapshot into an authorization token.
- Do not execute the full ARC-AGI-2 model/solver trial without a later explicit
  owner execution authorization and a passing technical preflight. The current
  authorization covers only the exact four-invocation `run-003` benchmark. Do
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
- Record durable boundary decisions under `docs/decisions/`; keep transient
  implementation status in the active trial README or task report.
- Keep trials reproducible and decision-bearing when the trial track is opened.
- Open research only for a concrete, authorized product question; return useful
  results to product engineering.
- Never edit archived scientific or operational bytes to make a current check
  pass. Update current checks when current governance changes.
- Keep generated local output under `.irisx/` and out of Git.
- Follow `docs/development/data-and-execution-policy.md` for secrets, domain
  data, retention, provenance, external execution, and budget authorization.

## Validation

Run from the repository root before handoff:

```powershell
python tools\repository_check.py --all
```

The validator is offline and checks the active layout, thesis and decision,
archive tag/catalog identities, representative recovery, and separation from
archived imports and execution.
