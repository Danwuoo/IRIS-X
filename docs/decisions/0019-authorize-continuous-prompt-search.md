# Decision 0019: Authorize continuous prompt search

Status: Accepted

Date: 2026-09-22

## Context

`prompt-pilot-baseline-002` completed its exact 384-job workload and Decision
0018 recovered a verified truth-free result without another generation. The
owner then explicitly directed the trial to continue through scoring,
reflection, dependent prompt search, and final holdout evaluation without
stopping for per-round approval.

The recovered baseline is bound to result digest
`4764cd569f669f8736461ddf2b5d6ac3bf1c80ddf3f903d669f8d5a43aa054af`,
run identity digest
`15f6d00a764b3849664bdfafa80183f051bf2701c6bd64f01caf9b53168b4051`,
and split digest
`6176d88ce9a66dcc45584aa09c110898c0f782b1f97e42e1f268c3ef1f25bd2b`.

## Decision

Authorize the `arc-agi-2-prompt-pilot` controller to run the complete bounded
Build–Measure–Select sequence:

- deterministically score the 256 optimization-train and 128 selection-dev
  baseline records locally, retaining invalid outputs in the denominator;
- install and bind a local isolated release of DSPy and GEPA, use real
  `dspy.GEPA` Pareto/frontier selection, and invoke Codex CLI
  `gpt-5.6-sol` at `xhigh` through its custom instruction-proposer hook;
- make at most ten dependent proposal attempts. Each attempt counts even when
  the proposer fails or returns an invalid or duplicate instruction; invalid
  and duplicate instructions do not consume GPU generations;
- provide the proposer at most three complete optimization-train examples and
  at most 32 KiB of input. Selection-dev answers and case-level feedback and
  every locked-holdout answer remain outside the proposer context;
- evaluate each legal new candidate once on the unchanged 256 train plus 128
  dev workload using the exact Qwen3.5-4B revision, parser, demonstrations,
  greedy decoding, 512-token limit, no thinking, no retry, private Kaggle
  `NvidiaL4` x4, official competition mount, Internet disabled, and USD 0 paid
  cost;
- reuse the retained large model Dataset and update only a small
  runtime/outbound Dataset. Each new prompt and result has a distinct run and
  package identity; no prior identity or bytes are reused for changed content;
- poll running kernels at low frequency, retrieve terminal output once, verify
  it, score it, update the durable ledger, and continue automatically. A
  complete checkpoint may be packaged locally after a finalization-only
  failure instead of rerunning generation;
- after ten attempts, select `G*` only by frozen selection-dev exact match,
  then open the locked 128-case holdout and compare B1 with `G*`. If `G*` is
  B1, run only one 128-case holdout workload; otherwise run 256 interleaved
  B1/G* jobs; and
- cap the entire trial at 4,480 Qwen generation invocations, including the 384
  baseline invocations and final holdout. Do not add hidden warmups, retries,
  public-evaluation sweeps, or competition submissions.

Before every external mutation or retrieval, write an atomic local ledger with
the round, parent, candidate and configuration digests, kernel/version, status,
result digest when available, proposal and generation counters, timings, and
next action. One controller owns the ledger. Restarted work must resume it and
must not duplicate a proposal, Dataset update, kernel push, or retrieval.

The controller stops only for a missing required input, unavailable
authentication or platform quota, unverifiable evidence, or a repair that
would exceed these workload bounds. Routine reversible packaging and software
repairs inside this decision do not require another owner confirmation.

## Consequences

The earlier startup, retrieval, scoring, and per-round stop conditions in
Decisions 0016–0018 are consumed lineage and no longer govern this trial's
next action. Their identities and evidence remain frozen. This decision does
not reopen Trial 001 or Trial 002, authorize paid execution, publish results,
change product promotion criteria, or start P3/P4.
