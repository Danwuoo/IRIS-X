# Implementation Timeline

## Purpose

Define the staged engineering path and current Post-Stage-1 status while
avoiding architecture, validation, or production-readiness claims that have not
passed through measured results and closure documents.

## Phase 0: Documentation And Contracts

- Complete source translations.
- Freeze schema skeletons, then promote Stage 1 runtime schemas to required-field
  contracts before execution.
- Define metric and label guides.
- Select first benchmark domain.

## Phase 1: Minimal Closed Loop

- Implement state manager, Execution IR compiler, evidence builder, verifier stub, commit/abort controller, and episode journal.
- Run Experiment 001 on controlled tasks.
- Status: `Closed: local smoke completed` on 2026-05-03.

## Phase 2: Evidence And Verifier

- Implement structured verifier inputs.
- Run Experiment 002 local smoke.
- Status: `Closed: local smoke completed` on 2026-05-04.
- Remaining work: human labels, larger samples, and broader false accept / false
  reject analysis.

## Phase 3: Commit Journal And Replay

- Add replay checks and audit completeness checks.
- Run Experiment 003 local smoke.
- Status: `Closed: local smoke completed` on 2026-05-04.
- Remaining work: expanded fixture coverage, secondary audit labels, and
  multi-step / compensable action cases.

## Phase 4: Targeted Recovery

- Add Failure Taxonomy labels and basic recovery policies.
- Run compute-matched ablation against blind retry.
- Status: `Closed: local smoke completed` on 2026-05-06.
- Entry need satisfied for controlled Document Ops recovery fixtures:
  multi-step commit, rollback failure, audit gap, and compensable action cases.
- Remaining work: expand beyond the three controlled recovery fixtures, add
  ambiguous or multi-label failures, add human or secondary labels, and avoid
  broad H4 validation claims until larger measured ablations exist.

## Phase 5: Context OS Candidate

- Implement `Working Set Compiler v0` only, not full Context OS.
- Compare bounded raw trace against schema-valid, reference-backed
  `WorkingSet` artifacts on five Document Ops long-context fixtures.
- Keep model, prompt budget, response budget, latency controls, and OpenClaw
  local harness interface fixed for Experiment 005 local smoke.
- Do not add memory writes, full memory dumps, learned retrieval, or raw tool
  log dumps.
- Status: `Closed: local smoke completed` on 2026-05-07.
- Remaining work: expand beyond five controlled Document Ops long-context
  fixtures, add human or secondary omission/relevance labels, and avoid broad H3
  or full Context OS validation claims until larger measured ablations exist.

## Post-Stage-1 Gate Tracking

Post-Stage-1 advancement is governed by
[Post-Stage-1 Advancement Gate](../00_manifest/Post_Stage_1_Advancement_Gate.md).

- Milestone gates before advancing phases are tracked by `PS1-G1` through
  `PS1-G8`.
- Broader experiment sample size is accepted by `PS1-G1` in
  [Post-Stage-1 Larger Sample Plan](../04_experiments/Post_Stage_1_Larger_Sample_Plan.md).
- Baseline identity is accepted by `PS1-G5` in
  [Baseline Identity Plan](../04_experiments/Baseline_Identity_Plan.md).
- Larger-sample acceptance thresholds are accepted by `PS1-G2` in
  [Post-Stage-1 Metric Policy](../05_evaluation/Post_Stage_1_Metric_Policy.md).
  Acceptance still requires a measured run, threshold pass, and manifest or
  closure acceptance.
- The `20260601_113121` Lane A larger controlled sample is
  `accepted_by_closure` for the named threshold-governed Document Ops sample
  only. It does not validate H1-H5, approve production readiness, authorize full
  Context OS, authorize memory writes, or authorize irreversible effects.

## Current Engineering Position

- `PS1-G6` is locally implemented as `Document Ops Structured Edit Action
  Surface v0` with fixture-local `READ_ONLY`, `SIMULATED`, and `REVERSIBLE`
  actions, schemas, fixtures, runtime code, and tests.
- `PS1-G7` Context OS work is planning-only: draft spec, schema impact review,
  and evaluation plan. It does not implement full Context OS, learned retrieval,
  compression, memory governance, memory writes, or H3 validation.
- `PS1-G8` side-effect work is planning-only for fixture-local Document Ops
  `COMMITTABLE` commit proposals. The proposal validator, 10 immutable planning
  fixtures, rerunnable runner/Mix task, and complete `20260715_223158` measured
  pilot now exist. It does not execute `COMMITTABLE`, `IRREVERSIBLE`, or
  `MEMORY_WRITE` effects and does not create runtime approval or H5 validation.
- The 2026-07-06 schema packaging decision keeps schema files under
  `docs/03_schemas/*.schema.json` for the current runtime. Packaged runtime
  schema assets require a later accepted migration gate with loader, package,
  and test changes.
- `PS1-G9` gate/spec, three persistence schemas, adapter abstraction,
  MemoryAdapter, SQLiteAdapter, runtime integration, idempotency, restart
  recovery, strict replay, and Experiment 006 runner are implemented. The
  `20260715_114209` complete run is `pass_acceptance_candidate`, and the
  manifest closure accepts its named fixture-local scope as
  `accepted_by_closure` after all required test commands passed.

## Phase 6: Fixture-Local Persistence v0

- Backend: SQLite through direct `exqlite`, behind `Vanta.Persistence`.
- Migration path: Memory authority plus SQLite shadow parity, SQLite
  restart/replay candidate, then named persistence authority only by closure.
- Failure injection: 20 deterministic protocol-boundary cases; no OS-level
  process-kill claim.
- Measured candidate: `20260715_114209`, 20/20 cases and every `PS1-G9` hard
  metric passing; accepted by the named Persistence v0 closure.
- Predecessor: `20260715_114052`, retained as `failed_no_acceptance` provenance.
- Claim boundary: fixture-local single-machine persistence only; not production,
  distributed persistence, durable memory, external effects, or H1-H5.

## Next Implementation Gates

- Successor persistence gates may address migration beyond v0, concurrent
  multi-process authority, retention operations, or packaged schema assets;
  none are implied by `PS1-G9`.
- Define any executable `COMMITTABLE` behavior beyond the G10 copied-fixture
  promotion through a later accepted schema, implementation, fixture, test,
  and evaluation batch.
- Define any full Context OS implementation through later accepted specs,
  schemas, evaluation plans, labels, and measured runs.

## Phase 7: Fixture-Local COMMITTABLE Promotion v0

- Gate: accepted `PS1-G10`, scoped to one explicit action inside marked
  ephemeral copied fixture workspaces.
- Implementation: standalone approval schema, task-specific runtime dispatch,
  two-phase evidence/verifier, Persistence v0 prepared intent and transaction,
  restart recovery, strict restore, audit, and replay.
- Failure injection: 28 deterministic cases across authorization, hashes,
  paths, evidence, verifier, idempotency, crash windows, refs, rollback, replay,
  irreversible classification, and memory-write smuggling.
- Measured candidate: `20260716_020716`, 28/28 cases and all 15 hard gates
  passing; accepted by the named G10 closure after the required command set.
- Claim boundary: no external/production target, irreversible effect, memory
  write, durable memory, full Context OS, distributed authority, or H1-H5 claim.
