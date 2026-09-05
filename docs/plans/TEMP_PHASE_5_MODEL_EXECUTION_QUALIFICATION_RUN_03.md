# TEMP Phase 5 — Model Execution Qualification Run 03

- **Status:** Retired — qualification accepted and handed off
- **Authorization:** Owner-authorized formal Batch 4 qualification execution
- **Date:** 2026-09-05 Asia/Taipei
- **Repository:** Danwuoo/IRIS-X
- **Required starting SHA:** `43d2d2936ad41cfb3ea21e8d6a7db7aae995df6a`
- **Run ID:** `qualification-20260905-03`
- **Scope:** one frozen model-backed read-only qualification attempt
- **Monitoring instruction:** confirm background launch once, then do not monitor

## Purpose

Execute the repaired Codex CLI 0.147.0-compatible qualification tool once
through the existing IRIS-X identity, evidence, deterministic verification,
canonical adjudication, terminal-record, and resource-accounting boundaries.

The two earlier failed runs remain immutable evidence. This run receives a new
identity and directory and must not overwrite or reinterpret them.

## Frozen execution

- provider: `openai` through custom Codex slot `irisx_openai_no_retry`;
- execution surface: `codex-cli 0.147.0`;
- model: accepted cheaper role `gpt-5.6-luna`;
- reasoning effort: `medium`;
- authentication: ChatGPT only;
- billing: ChatGPT subscription;
- API-key fallback: prohibited;
- HTTP retries: 0;
- stream reconnect retries: 0;
- WebSocket transport: disabled;
- sandbox: read-only;
- model/tool envelope: frozen tool-free catalog;
- verifier: fixture-local deterministic oracle; no model judge.

The exact definition, identity, preflight observation, command code, and tests
must be committed and pushed from a clean `main` before launch.

## Execution and handoff boundary

Launch the qualification runner as a hidden background process with stdout and
stderr redirected outside the repository. Record the process ID, launch time,
freeze SHA, and external launcher-log paths. Confirm only that the process was
created and had not already exited at the immediate launch check.

After that one confirmation, do not poll, wait for, inspect, or report the run
result in this task. Do not read its output or newly created run artifacts.
Leave this plan active for a future explicitly requested collection turn.

## Preservation and exclusions

Preserve all prior runs, evidence, plans, handoffs, sources, papers, research,
and deterministic Phase 5 inputs. No second launch, retry, comparison, routing,
cascade, fallback, escalation, recovery, persistence framework, workflow
engine/search, optimizer, training, fine-tuning, multi-agent work, architecture
search, model judge, external action, production server/UI/API, or
H-G1/H-W1/H-C1/H-R1 evaluation is authorized. Do not start Batch 5.

## Retirement record

Run 03 was launched exactly once from the frozen definition/code commit and was
not monitored after the required immediate launch confirmation. A later
owner-authorized collection turn found the process complete and preserved the
raw run directory without retry or overwrite.

- definition/code freeze:
  `47d9173fa929119377fdf01034c399792bdde8ba`;
- immutable run-evidence commit:
  `ccfa44fc255357ba42c8f4ebbd22deda475055e6`;
- durable handoff commit:
  `7c6b93e20593a506b4eb211a425aa31dc06b04da`;
- raw result: `{"selected_id":"alpha"}`;
- deterministic verification: correct with sufficient bound evidence;
- canonical adjudication: `accept / verified_success / completed`;
- run-03 provider attempts/model calls: `1/1`;
- retries, routes, fallbacks, escalations, recovery actions, and tool calls:
  all `0`;
- observed token usage: 4,141 input and 16 output tokens;
- focused validation: 70/70 PASS;
- full inventory: 141 total, 140 passed, the same one historical Phase 4
  frozen-plan hash failure, 0 errors, 0 skips, and 0 new failures.

The durable result is
`docs/phase-5-model-execution-qualification-run-03-handoff.md`. This temporary
plan is retired separately after that handoff. Phase 5 Batch 4 is closed for
the frozen run-03 configuration. Batch 5 was not started.
