# IRIS-X Repository Governance

## Current authority and scope

IRIS-X has adopted the product direction defined in
[`PRODUCT_THESIS.md`](PRODUCT_THESIS.md): a product-oriented platform for
domain AI specialization. The product begins with a **Domain Specification**,
uses **Build–Measure–Select** and **Engineering Trials**, and produces a
versioned **Domain Package**.

P0 and P1 established the repository and provider-neutral contract foundation.
ARC-AGI-2 Trial 001 is the completed first P2 slice. Its terminal state and
retained evidence live in
[`trials/first-real-domain/README.md`](trials/first-real-domain/README.md);
Decisions 0004–0009 retain the detailed rationale and frozen evidence bindings.

[`Decision 0010`](docs/decisions/0010-adopt-lightweight-risk-based-development.md)
adopts a lightweight, risk-based workflow. Routine local, offline, reversible
work inside the current boundaries does not need another decision record.
Boundary-crossing work remains gated. Decision 0009's `run-001` identities
remain frozen.
Decision 0011 creates a distinct checkpointing `run-002` v4 transport after the
non-checkpointing run-001 attempt failed to finish. It authorizes implementation,
offline packaging, verification, and preflight only, not real execution.
Decision 0013 preserves the executed `run-002` identity and authorizes the exact
four-invocation `run-003` v5 completion benchmark with no runner time limit,
checkpoint resume, and a truth-free `result.zip`. Accepted Decision 0012 now
closes Trial 001 as `inconclusive-no-promotion` without a verified `run-003`
result and ends all remaining Trial 001 execution authority.
Decision 0014 opens the distinct `arc-agi-2-trial-002` completable-baseline
question and authorizes exactly one bounded private Kaggle L4 x4 smoke under
`trial-002-smoke-001`, with Qwen3.5-4B, NVARC-derived task-local adaptation,
automated CLI transport, truth-free checkpoints/results, and USD 0 paid cost.
That attempt failed before model execution because the submitted kernel omitted
the competition source and observed only two GPUs. Decision 0015 preserves the
failed identity and authorizes one replacement `trial-002-smoke-002`: mount
`arc-prize-2026-arc-agi-2`, verify exactly four L4 GPUs, and make exactly four
inference-only Qwen3.5-4B generation calls with no TTT or retry.

## Authority order

1. explicit owner instructions for the current task;
2. this file and any narrower active `AGENTS.md`;
3. Decision 0010, the closed trial status page, and applicable accepted
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
| `src/irisx/` | P1 contracts/reference flow/package verification, historical P2 admission validation, and retained ARC-AGI-2 trial implementation |
| `tests/` | Tests for the active product and repository surface |
| `trials/` | Historical P2 admission package and the closed ARC-AGI-2 Trial 001 workspace |
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
- Use the Trial 001 README as terminal status. Consult Decisions 0004–0009 for
  provenance and exact bindings instead of duplicating their full text in new
  documents.
- Preserve the Decision 0009 frozen `run-001` outbound, notebook, runner, and
  manifest identities. Decision 0012 supplies the accepted alternative closure
  gate; physical normalization may proceed only after the layout audit reports
  `normalization_ready: true`. Never reuse one bundle ID for different bytes.
- Preserve executed `run-002` and prepared `run-003` bytes and identities. The
  v4/v5 checkpoint and result formats remain lineage material, not active
  execution instructions.
- Keep Trial 002 identities, bytes, results, and status separate from Trial
  001. The Trial 002 status page is `trials/arc-agi-2-baseline/README.md`.
- Preserve Decision 0003 and `trials/p2-admission/admission.json` as immutable
  historical blocked-state evidence. Never reinterpret or mutate that v1.0
  snapshot into an authorization token.
- Do not execute or resume any part of closed Trial 001. Decisions 0014 and
  0015 are the narrow exception for the separate Trial 002 question. The
  authorized repair reuses the pinned Qwen3.5-4B bytes, mounts the real ARC
  competition challenges, verifies exactly four L4 GPUs, and performs exactly
  four inference-only generation calls under `trial-002-smoke-002`. It does not
  permit TTT, LoRA, a retry or fifth invocation, notebook Internet, external
  model APIs, paid resources, public publication, competition submission,
  large SFT, RL, prompt search, a second solver, or a public-evaluation sweep.
  Do not start P3/P4 or build a production runtime.
- A network fetch, if implemented for the approved `arcprize/ARC-AGI-2`
  upstream at commit `f3283f727488ad98fe575ea6a5ac981e4a188e49`, must be a
  deliberate source-materialization command separated from trial execution;
  default tests and validation remain offline.
- Trial 001 model and manual-transport rules remain frozen lineage. For Trial
  002 only, Decisions 0014 and 0015 permit acquisition or reuse of
  `Qwen/Qwen3.5-4B@851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a` and private
  Dataset/kernel upload and output download through the installed Kaggle CLI.
  Acquisition remains separate from tests, validation, packaging, preflight,
  and measured execution. Evaluator truth and answer-derived metadata never
  enter an outbound package, checkpoint, result, or notebook.
- Treat the conceptual decomposition in the thesis as product responsibilities,
  not as settled services, classes, packages, or deployment boundaries.
- Record durable boundary decisions under `docs/decisions/`; keep transient
  implementation status in an open trial README or task report.
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
