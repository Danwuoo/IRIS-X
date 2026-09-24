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
inference-only Qwen3.5-4B generation calls with no TTT or retry. That replacement
is now `runtime-verified`: all four calls returned valid grids on four L4 GPUs,
while local exact-match scoring was 0/4. Its one kernel push and one retrieval
are consumed; no further Trial 002 external execution is authorized.
Decision 0016 opens the separate `arc-agi-2-prompt-pilot` trial and authorizes
one `prompt-pilot-baseline-001` private 384-job Kaggle launch. The active task
must stop development and monitoring once four distinct L4 workers report the
exact pinned model ready and initial dynamic dispatch is observed; it does not
authorize result retrieval, scoring, reflection, or another kernel.
That authorized version 1 ended `ERROR` before the hardware gate and model
runner because the exact outbound was not present at the assumed Dataset mount
path. It produced zero model-ready events and zero generations. The launch is
consumed; Decision 0016 authorizes no repair submission or further external
status, log, source, or output request.
The owner's repair direction is retained in Decision 0017. It preserves the
failed identity and authorizes exactly one transport-only replacement,
`prompt-pilot-baseline-002`: update the existing small private runtime Dataset
as version 2, resolve only exact owner-qualified or explicit legacy mounts, and
push one new private kernel. The original 384-job, L4 x4, pinned-model, no-retry,
truth-free, Internet-disabled, USD 0 boundaries remain. Stop development and
monitoring immediately after four distinct model-ready events plus initial
scheduler dispatch, or retain a replacement failure without another retry.
That replacement reached `startup-verified`: four exact-model workers reported
ready on four distinct L4 UUIDs and the first four jobs were dispatched across
ranks 0–3. It then completed all 384 jobs (380 valid, 4 invalid) but failed
before writing `result.zip` because integer `model_ready` rank keys violated
canonical JSON. The Dataset update, kernel push, and monitoring authority are
consumed. No result retrieval, checkpoint recovery, packaging, scoring, or
resubmission is authorized without new owner direction.
The owner has now explicitly authorized Decision 0018: retrieve the exact
baseline-002 version 1 output once and locally package its completed checkpoint.
This recovery may apply only the verified integer-to-string rank-key fix. It
does not authorize another generation, Dataset/kernel mutation, scoring,
reflection, publication, competition submission, or repeat retrieval.
That recovery is complete. The exact version 1 checkpoint and progress stream
were retained locally, and deterministic local packaging produced verified
truth-free result digest
`4764cd569f669f8736461ddf2b5d6ac3bf1c80ddf3f903d669f8d5a43aa054af`
with zero new generations. The one retrieval is consumed and the result remains
frozen. Decision 0019 supersedes the earlier prompt-pilot stop points and
authorizes continuous local scoring, up to ten dependent DSPy/GEPA plus Codex
proposal attempts, private candidate evaluation, and one final locked-holdout
comparison under the fixed 4,480-generation ceiling.
That search is now terminal: no candidate beat B1 and the final holdout failed
before inference on visible-source incompatibility. Decision 0019 is consumed.
Decision 0020 opens `arc-agi-2-budget-ablation`: development and future reflection
use `gpt-6-sol / xhigh`, while the solver remains pinned Qwen3.5-4B. It authorizes
192 diagnostic generations and at most 384 conditional validation generations,
with source acquisition, private four-L4 CLI execution, retrieval and scoring
as one continuous workflow. No GEPA calls or holdout execution are part of it.
The status page is `trials/arc-agi-2-budget-ablation/README.md`.
That diagnostic completed all 192 calls with no qualifying arm; conditional
validation was not launched. Decision 0020 is terminal, and its unused ceiling
does not authorize further calls. Control review confirms all 512 visible
sources match: the prior holdout failure compared a single-test projection
against a full multi-test case. Holdout remains unscored.
Decision 0021's one private Kaggle kernel push and one terminal retrieval for
the distinct `nvarc-4b-compat-pilot-001` 4B LoRA compatibility pilot are
consumed. The kernel completed, but the pilot failed its L4 hardware gate
before model loading or training: zero steps, tokens and generations. No
retry, replacement, full SFT or ARC scoring is authorized. The terminal
evidence and exact material bindings are in
`trials/arc-agi-2-qwen35-nvarc/4b-pilot.md`.
Decision 0022's one distinct `nvarc-4b-compat-pilot-002` private Kaggle
kernel push was attempted and rejected by the API with HTTP 400 before a
version receipt. The intended kernel was inaccessible at the status check
and absent from the recent own-kernel list. No terminal retrieval was made;
the push authority is consumed and the unused retrieval is not permission to
retry. The official competition mount and early hardware diagnostics remain
locally staged only. Decision 0023 records the owner's explicit direction to
retry a provider rejection before any kernel version or model run. It
authorized exactly one separate `nvarc-4b-compat-pilot-003` submission with a
shorter title/slug and the same synthetic-only, private, offline, USD 0,
two-step, 128-token, zero-generation bounds. That version was accepted,
verified four distinct L4s and the official competition mount, then failed
before model loading on Kaggle's preinstalled `torchao 0.10.0`, which PEFT
0.21.0 rejects. Zero steps/tokens/generations were reserved. The one output
retrieval attempt retained all seven non-log files; Windows console encoding
left the log empty. Decision 0023 is consumed. No model retry or reuse of
pilot 001/002/003 identities is authorized.
Decision 0024 accepts the owner's explicit authorization of one distinct pilot
004 dependency repair, bound to the unchanged local draft plan. It removes the
optional incompatible `torchao` package offline before pinned wheel install
and checks its absence before PEFT import. Exactly one private kernel push,
bounded terminal status checks and one output retrieval are authorized under
the unchanged two-step, 128-token, zero-generation, USD 0 limits. No Dataset
mutation, retry, resume or other pilot identity is authorized.
The first pilot 004 `SaveKernel` request received HTTP 401 because the local
OAuth access token had expired. A refreshed credential and successful own-kernel
listing show no pilot 004 version. Decision 0025 applies the owner's standing
pre-runtime rejection retry direction to authorize one exact-package transport
retry under the same pilot 004 identity. If it is accepted, monitor to terminal
and retrieve once; if rejected, stop without a third request.
That exact retry was accepted as version 1 and completed. The official
competition mount, four distinct L4s and offline removal of `torchao 0.10.0`
were verified. Qwen3.5-4B completed two synthetic LoRA optimizer steps with
16 total training tokens, all four expected gradient groups, adapter reset,
and zero generations. One terminal retrieval returned a full log and verified
truth-free result. Decisions 0024–0025 are consumed; no additional pilot
submission, retrieval, ARC scoring, full SFT or method promotion is authorized.
Decision 0026 authorized the distinct `nvarc-4b-compact-complete-001` small
complete flow. Kaggle accepted one private version under a title-derived slug
different from the specified metadata ID. The terminal version failed at the
Dataset v2 root inventory gate before model load, conversion, training or
generation. One terminal retrieval preserved 11 files and confirmed that no
compact artifact, checkpoint or result exists. The one push and retrieval are
consumed; no repair submission or further external execution is authorized.
Its status is `trials/arc-agi-2-qwen35-nvarc/compact-complete-001.md`.
The owner now authorizes Decision 0027's session-local, free Kaggle kernel
debugging for program errors in that same bounded synthetic compact flow.
Every new attempt uses a distinct immutable run identity and private kernel;
the original 001 version remains consumed. No scientific scope, paid cost,
Dataset mutation, ARC scoring or competition submission is authorized.

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
- Keep the prompt-pilot identity and evidence separate from Trial 002. Its
  current status page is `trials/arc-agi-2-prompt-pilot/README.md`.
- Preserve the failed `prompt-pilot-baseline-001` identity and submitted bytes.
  Do not reuse that identity for a mount-path repair or claim its 384 jobs ran.
- Decision 0017 authorizes only `prompt-pilot-baseline-002` as the replacement.
  Do not broaden its mount repair into another Dataset, solver, workload,
  generation policy, result retrieval, scoring, reflection, or retry.
- Preserve the compute-complete but result-packaging-failed baseline-002
  identity and evidence. The local string-key fix is routine engineering only;
  Decision 0018 now authorizes one exact output retrieval and local result
  reconstruction. Both are complete and consumed. Decision 0019 separately
  authorizes the bounded continuous search; never mutate or reuse the baseline
  identity for a candidate.
- For Decision 0019 work, maintain one atomic local ledger before external
  mutation or retrieval. Preserve train/dev/holdout isolation, use real
  `dspy.GEPA` with the fixed Codex proposer, count failed/duplicate proposals,
  and never exceed ten proposal attempts or 4,480 total Qwen generations.
- Preserve Decision 0003 and `trials/p2-admission/admission.json` as immutable
  historical blocked-state evidence. Never reinterpret or mutate that v1.0
  snapshot into an authorization token.
- For Decision 0020, preserve all previous trial identities. Audit all 512
  visible cases and require parity for every one of the 384 executable
  train/dev cases. Isolated unused-holdout differences remain documented and
  unscored. Use an atomic ledger, at most 576 new generations, 300 seconds per
  job, no retries, and the fixed qualification rule before the second kernel.
  Keep outcome-derived diagnostic strata evaluator-side. New Codex development
  and reflection profiles use `gpt-6-sol / xhigh`; historical profiles remain
  valid. This ablation configures reflection but makes no proposer calls.
- Do not execute or resume any part of closed Trial 001. The Decisions 0014 and
  0015 exception for Trial 002 was consumed by `trial-002-smoke-002`; do not
  start another kernel, retrieval, retry, fifth invocation, TTT, LoRA, notebook
  Internet session, external model call, paid run, publication, competition
  submission, large SFT, RL, prompt search, second solver, or public-evaluation
  sweep under that authority. Do not start P3/P4 or build a production runtime.
- A network fetch, if implemented for the approved `arcprize/ARC-AGI-2`
  upstream at commit `f3283f727488ad98fe575ea6a5ac981e4a188e49`, must be a
  deliberate source-materialization command separated from trial execution;
  default tests and validation remain offline.
- Trial 001 model and manual-transport rules remain frozen lineage. Decisions
  0014 and 0015 authorized the now-completed Trial 002 acquisition, private
  Dataset/kernel upload, execution, and output download; they do not authorize
  repeating them. Evaluator truth and answer-derived metadata never enter an
  outbound package, checkpoint, result, or notebook.
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
