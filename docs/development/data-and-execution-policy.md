# Data and Execution Policy

Status: current under Decision 0010. This policy defines the boundary between
routine development and work that needs explicit owner direction. Local,
offline, reversible implementation and validation inside the current scope do
not require a separate approval. Provider/model execution, paid resources,
sensitive-data disclosure, and irreversible actions retain their stated gates.
Execution work also follows the
[`Development Operating Model`](operating-model.md).

## Secrets and credentials

- Never commit API keys, tokens, passwords, private keys, session material, or
  other secrets.
- Supply secrets only through an approved environment or secret-management
  mechanism for an explicitly authorized task.
- Do not print secrets into logs, prompts, trial records, screenshots, or
  Domain Packages. Stop and report suspected exposure before continuing.

## Domain and sensitive data

- Treat non-public domain data as sensitive until its owner, permitted uses,
  access boundary, and retention requirements are established.
- Use the minimum data necessary for the authorized question. Do not upload or
  disclose domain data to an external provider/model without explicit approval
  covering that provider/model, data class, purpose, and retention behavior.
- Record applicable consent, licensing, privacy, security, residency, and
  human-review constraints rather than assuming them.

## Local outputs, retention, and provenance

- Put generated local working output under `.irisx/`. It is ignored, local,
  disposable by default, and is not authoritative evidence merely because it
  exists.
- Promote an output into Git only after review confirms that it is authorized,
  necessary, appropriately redacted, and suitable for the intended retention.
- Retained trial or product evidence must identify its source, procedure or
  command, relevant configuration, time, costs, transformations, and known
  limitations. Preserve provenance and failures; do not rewrite observations
  to support a preferred decision.
- Follow any stricter source-specific deletion or retention requirement. Git
  history is not an appropriate store for secrets or data that must be erasable.

## External execution and budgets

Ordinary P0/P1 validation and the P1 qualification fixture are deterministic and
offline. Historical P2 admission validation and default Decision 0004 tests,
validation, and preflight are likewise deterministic and offline. They may
inspect local files and Git objects but must not call a provider/model, access
an external service, start paid compute, or transmit domain data.

Decision 0004 permits an implementation to expose one deliberate source-
materialization command for the approved official `arcprize/ARC-AGI-2`
upstream at commit `f3283f727488ad98fe575ea6a5ac981e4a188e49`. Any network
fetch through that command is source acquisition, not trial execution; it must
remain structurally separate, accept no third-party ARC source, verify the
pinned identity and per-file digests, and keep raw material local and
disposable. It does not authorize network access during tests, validation,
preflight, specialization construction, or the Engineering Trial.

Any external or paid execution requires explicit owner authorization that
identifies the purpose and scope, provider/model or service, permitted data,
maximum budget or resource limit, stop conditions, and expected output and
retention. Budget approval must precede paid execution; absent an approved
limit, the permitted spend is zero. Approval of product direction or repository
work is not approval to spend money or execute a model.

External execution must use a deliberate command or authorized Engineering
Trial path separate from default tests and repository validation. Unexpected
network activity, cost, credential use, or data disclosure is a stop condition
and must be reported.

For ARC-AGI-2 Trial 001, external provider use, networked trial execution, and
external paid execution are prohibited, and the maximum external paid-execution
budget is USD 0. The current fixed boundary is summarized on the
[`Trial 001 status page`](../../trials/first-real-domain/README.md); the Kaggle
handoff guide contains the procedure. Measured notebook execution remains
network-disabled and credential-free. Evaluator truth, expected-output digests,
scores, feedback, and third-party ARC material may not cross the outbound
boundary. Trial 001 is closed by Decision 0012 as
`inconclusive-no-promotion`. The Decision-0013 authorization for the exact
four-invocation `run-003` benchmark has ended; no Trial 001 execution, resume,
scoring, or promotion is currently authorized.

Decision 0011 checkpoints are truth-free execution outputs under the same
retention boundary as returned predictions. Cross-session transport is manual:
the checkpoint may be downloaded unchanged and attached only as a private,
immutable Kaggle Dataset version. It must remain identity-bound to `run-002`;
resume neither changes the model/configuration nor grants extra cumulative
wall-clock budget.

Decision 0013 checkpoints and `result.zip` use the same truth-free retention
boundary but remain identity-bound to `run-003`. The v5 runner enforces four
completed invocation records and the frozen token/response limits without a
per-invocation or cumulative runner time limit. A provider-interrupted pending
invocation is retried on resume and is not mislabeled as a completed timeout.
These rules are retained as lineage only after closure; they do not authorize
continued execution or acceptance of a late result.

Decision 0014 creates a separate Trial 002 exception to the closed Trial 001
rules. For run `trial-002-smoke-001`, the owner authorizes acquisition of the
pinned Qwen3.5-4B and NVARC public materials, necessary private Dataset upload,
one private Kaggle L4 x4 kernel execution through the installed CLI, and one
bounded output retrieval. Notebook Internet stays disabled; evaluator truth,
scores, feedback, and answer-derived metadata stay local; existing CLI secrets
must not be printed or copied; external model APIs, paid execution above USD 0,
public publication, and competition submission remain prohibited. The run has
four fixed public-training tasks, 300 seconds of task-local adaptation plus
inference per task, a 3,600-second whole-session bound, and a 180-second
finalization reserve. It is not polled or live-streamed, and failure does not
authorize an automatic resubmission.

Decision 0015 records that `trial-002-smoke-001` failed before model work with
no competition source and only two visible GPUs. It authorizes one replacement,
`trial-002-smoke-002`, that mounts `arc-prize-2026-arc-agi-2` and opens only
`arc-agi_training_challenges.json`. The runtime must verify exactly four L4
GPUs before loading the model and then perform exactly four inference-only
generation invocations: one fixed task/test pair per GPU, one returned sequence,
no warm-up generation, retry, TTT, LoRA, SFT, or RL. The existing model and
wheel bytes may be reused in a new immutable private Dataset version. The one
kernel push and one bounded later retrieval inherit the Internet-disabled,
truth-free, USD 0, private, non-submission, no-polling boundary. Failure or a
queued state does not authorize another submission.

The replacement and its one retrieval are complete. Returned evidence verifies
four L4 GPUs, exactly four completed inference invocations, and four valid grids;
local exact-match scoring was 0/4. Decisions 0014 and 0015 now retain provenance
and boundary lineage only: they authorize no additional status/log/output call,
kernel execution, retry, or submission.
