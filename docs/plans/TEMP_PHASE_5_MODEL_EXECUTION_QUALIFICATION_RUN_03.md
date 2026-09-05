# TEMP Phase 5 — Model Execution Qualification Run 03

- **Status:** Temporary — active execution plan
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
