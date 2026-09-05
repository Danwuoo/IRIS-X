# TEMP Phase 5 — Model Execution Qualification Repair

- **Status:** Temporary — controlling execution plan
- **Authorization:** Owner-authorized corrective continuation of Phase 5 Batch 4
- **Date:** 2026-09-05 Asia/Taipei
- **Repository:** Danwuoo/IRIS-X
- **Required original baseline:** `0d738fec43bafc72b5f6ca0f1ca39a6426b0b751`
- **Required repair starting `main`:** `000cc1c3c9affbbf84c434803389bfd427e12dee`
- **Batch:** Batch 4 repair only; this is not Batch 5
- **Hard stop:** stop after one corrective qualification attempt, evidence, validation,
  handoff, plan retirement, and normal push

## Purpose

Repair the local Codex provider configuration defect recorded by the immutable
Batch 4 run `qualification-20260905-01`, then make at most one new frozen live
qualification attempt through the same model-backed `ExecutorAdapter` boundary.

The original run, its raw artifacts, adjudication, resource record, handoff,
and commits remain historical evidence. They must not be edited, replaced, or
reclassified.

## Authorized change

Codex CLI 0.147.0 rejects attempts to override the reserved built-in provider
ID `openai`. The repair may define one custom Codex configuration slot:

```text
codex model-provider config id: irisx_openai_no_retry
provider name: OpenAI
upstream provider identity: openai
wire API: responses
requires OpenAI authentication: true
HTTP request retries: 0
SSE reconnect retries: 0
WebSocket support: false
standalone web search support: false
```

The custom slot is client configuration, not a new provider identity. It must
not declare `env_key`, `experimental_bearer_token`, command-backed auth, or an
API-key/base-URL fallback. With the observed ChatGPT auth mode, Codex must
resolve its compiled ChatGPT Codex endpoint. Preflight must fail closed unless
the active authentication remains `Logged in using ChatGPT` after API-key
environment variables are removed.

The repair may add new definition/code/tests and minimally update the existing
qualification script and README. It must not add provider-specific types to
`irisx.core`; no further core change is currently justified.

## Frozen identity and run

Reuse without modification:

- task input `inputs/task-input.json`;
- model program `inputs/model-program.txt`;
- output schema `definition/output-schema.json`;
- deterministic oracle `{"selected_id":"alpha"}`;
- accepted provider/model baseline
  `experiments/configurations/provider-model-baseline-v0.json`;
- provider/model role `openai` / `gpt-5.6-luna` / `medium`;
- deterministic verifier and canonical core adjudication boundaries.

Create a new repair identity/contract and freeze:

```text
run ID: qualification-20260905-02
configuration ID: openai-codex-luna-medium-readonly-zero-retry-repair-v0
Codex provider config ID: irisx_openai_no_retry
```

The repair definition and all executable code must be committed at one clean
Git `HEAD` before the live attempt. The run record must bind that full commit
SHA as both definition and code freeze.

## Call ceiling

The prior Batch 4 run consumed one logical invocation attempt. This corrective
authorization adds, and is limited to:

```text
new live qualification attempts: 1
automatic HTTP retries: 0
automatic stream reconnect retries: 0
manual retries: 0
routes: 0
escalations: 0
recovery actions: 0
```

The Batch 4 lineage ceiling is therefore two logical attempts total: the
preserved failed attempt plus at most one repair attempt. A malformed, wrong,
interrupted, or failed repair result must be preserved and adjudicated; it does
not authorize another call.

Tests, fixture replay, definition validation, catalog inspection, auth status,
CLI version checks, and configuration parsing checks must make zero model
calls. The already-observed `codex doctor` repair diagnostic is a zero-model
preflight reachability check and must not be represented as model usage.

## Execution envelope

The repair remains a simple local-input, read-only record-selection task. The
model receives no shell, web, apps, browser, computer-use, image, skill, goal,
multi-agent, or mutation capability. Approval is `never`; sandbox is
`read-only`; execution occurs in an isolated temporary directory; user config,
rules, and session persistence are disabled. WebSocket transport is disabled
to eliminate WebSocket-to-HTTPS fallback behavior.

Any observed tool use, retry/reconnect, route/reroute, fallback, escalation,
recovery, state mutation, output/event mismatch, malformed event stream, or
provider configuration drift invalidates the result and must fail closed.

## Required lifecycle

1. verify clean repair baseline and original run hashes;
2. commit this TEMP plan separately;
3. add/freeze the repair identity, contract, code, and zero-call tests;
4. pass repository, provider-baseline, catalog, auth, config-load, focused, and
   original-run validation with zero model calls;
5. commit the complete definition/code freeze;
6. verify clean `HEAD` and record its full SHA;
7. execute at most one live repair qualification attempt;
8. preserve new raw artifacts in
   `runs/qualification-20260905-02/` without overwriting any prior run;
9. run fixture-local deterministic verification and canonical adjudication;
10. commit run evidence and factual interpretation;
11. run focused and full regression validation with zero new failures/errors;
12. create `docs/phase-5-model-execution-qualification-repair-handoff.md`;
13. retire this TEMP plan in a separate commit;
14. push `main` normally and confirm ahead/behind `0/0`;
15. STOP without starting Batch 5.

## Evidence and accounting

The new run must preserve command metadata, stdout JSONL events, stderr, raw
last message, terminal record, resource record, manifest, and interpretation.
It must record the actual Codex path/version, catalog observation, ChatGPT auth,
ChatGPT subscription billing, provider/config identities, full freeze SHA,
prompt/definition hashes, token usage if exposed, elapsed time, and exact
observed event counts.

`model_calls` records the adapter-controlled logical invocation attempt and
must be `1` once the process is launched. Transport/network request count and
provider cost remain `Unknown` unless directly exposed. Never infer zero
transport requests from missing CLI events. Retry, route, escalation, recovery,
and tool counts must reflect observed evidence and the frozen envelope.

## Validation and preservation

Required focused checks include repository validation, baseline/catalog
validation, core tests, both deterministic Phase 5 substrates, qualification
tests, original run validation, new run validation after execution, compilation,
and unchanged CLI semantics for the two deterministic paths.

Run the established full experiment/substrate suite. The sole known Phase 4
retired-plan hash failure may remain unchanged. Do not modify or suppress it;
the final condition is zero new failures and zero errors.

Preserve `sources/`, `references/papers/`, `research/`, all prior run files,
all prior plans and handoffs, and the four frozen deterministic Phase 5 inputs.
No history rewrite, force push, model comparison, routing, cascade, fallback,
retry, escalation, recovery, persistence, workflow engine/search, optimizer,
fine-tuning, training, multi-agent work, architecture search, model judge,
non-deterministic verifier, external action, production server/UI/API, or
H-G1/H-W1/H-C1/H-R1 evaluation is authorized.

