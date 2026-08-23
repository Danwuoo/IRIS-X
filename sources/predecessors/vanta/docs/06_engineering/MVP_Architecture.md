# MVP Architecture

## Purpose

Translate the research documentation into a minimal implementation architecture without claiming the theory is validated.

## Architecture Overview

```text
Task Input
  -> Canonical State Manager
  -> Planner / Action Proposer
  -> Execution IR Compiler
  -> Action Executor
  -> Evidence Packet Builder
  -> Verifier Runtime
  -> Commit / Abort Controller
  -> Episode Journal
  -> Evaluation Harness
```

## Current Status And Boundaries

- Closure status: `Closed: local smoke completed`.
- Controlled environment: local Document Ops fixtures.
- Runtime language: Elixir/Mix.
- Verifier v0: deterministic rule-based verifier using schema validation,
  side-effect-class checks, required evidence checks, provenance checks, and
  fixture-specific acceptance checks.
- Current executable side-effect classes: `READ_ONLY`, `SIMULATED`, and
  `REVERSIBLE` fixture-local Document Ops actions.
- `PS1-G6` is locally implemented as `Document Ops Structured Edit Action
  Surface v0` without expanding side-effect classes or making H1-H5 validation
  claims.
- The `20260601_113121` Lane A run is accepted by closure for the named
  threshold-governed Document Ops sample only.
- `PS1-G9` has a complete `Fixture-Local SQLite Persistence v0`
  implementation and a 20-case measured `pass_acceptance_candidate` run at
  `20260715_114209`; the named manifest closure accepts it as fixture-local
  Persistence v0 authority.
- `PS1-G10` implements one task-specific `COMMITTABLE` action for candidate
  promotion inside marked ephemeral copied fixtures. Experiment 007 run
  `20260716_020716` passes 28/28 cases and all hard gates and is accepted by the
  named G10 closure.
- `PS1-G7` Context OS work remains specification, schema-impact, evaluation,
  and implementation planning only. `PS1-G8` now has a complete 10-fixture
  planning validator/runner pilot, but remains planning-only runtime scope.
- Disallowed in the current runtime: general or external `COMMITTABLE`
  authority, full Context OS, memory writes, irreversible actions, production
  deployment, and H1-H5 validation claims.

## MVP Modules

- Canonical State Manager: stores task intent, state summaries, and state hashes.
- Execution IR Compiler: turns action proposals into executable steps.
- Verifier Runtime: checks feasibility, safety, postconditions, and evidence sufficiency.
- Evidence Packet Builder: collects state, action, observation, verifier, and provenance data.
- Commit / Abort Controller: applies or rejects verified changes.
- Episode Journal: records runtime actions for audit and replay.
- Evaluation Harness: computes initial metrics from logged episodes.
- Runtime Orchestrator: wires the Stage 1 loop as `Vanta.Runtime.run_task/3`.
- Baseline Runner: executes LLM action sequences directly without governance
  artifacts for Experiment 001 comparison.
- Replay Runner: replays journal steps in clean fixture workspaces.
- Document Ops Structured Edit Surface: inspects document structure, validates
  document contracts, simulates structured edits, and applies reversible
  fixture-local structured edits under `PS1-G6`.
- Working Set Compiler v0: produces schema-valid, reference-backed working sets
  for controlled long-context fixtures without implementing full Context OS.
- Post-Stage-1 tooling: generates larger-sample artifacts, Lane B packet and
  label-result artifacts, and `PS1-G8` side-effect planning validation artifacts
  without changing the commit path.
- Persistence Adapter: keeps runtime orchestration independent of backend
  details through Memory and SQLite adapters.
- SQLite Persistence v0: stores typed artifacts, accepted state/journal
  pointers, recovery records, and idempotency keys with explicit transactions.
- Persistence Recovery: prepares fixture-local reversible effects before
  mutation and resolves restart windows to commit, abort, rollback, or
  `recovery_required`.
- Fixture Commit Runtime: validates the copied-workspace marker, target and
  hashes, standalone approval, two-phase evidence/verifiers, durable prepare,
  atomic promotion, logical commit, restart recovery, audit, and strict replay.
- Fixture Commit Experiment: validates 28 immutable failure-injection cases and
  emits the Experiment 007 artifact contract.

## Deferred Modules

- Full Context OS.
- Long-term memory write gate.
- Training on runtime feedback.
- Runtime execution of any `COMMITTABLE` action except the named G10 copied-
  fixture promotion, and all `IRREVERSIBLE` or `MEMORY_WRITE` side effects.
- Packaged runtime schema assets; current schemas remain under
  `docs/03_schemas/*.schema.json`.
- High-risk external action governance beyond fixture-local tasks.

## Post-Stage-1 Decisions And Open Questions

- Resolved by `PS1-G9`: SQLite behind `Vanta.Persistence` replaces the named
  fixture-local persistence prototype; MemoryAdapter remains for tests and
  compatibility.
- Resolved by `PS1-G10`: the first executable commit domain is one explicitly
  allowlisted candidate promotion inside a marked ephemeral copied workspace;
  it creates no external, irreversible, memory, or multi-process authority.
- What successor measured-comparison scope is required beyond the accepted
  `20260601_113121` Lane A Document Ops sample?
- What benchmark size and direct Responses comparison are required before the
  OpenClaw `openai-codex/gpt-5.4-mini` candidate canonical local baseline can be
  promoted beyond Stage 1 smoke status?
