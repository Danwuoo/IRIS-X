# Experiment 001 Local Run Report

## Experiment

- Experiment ID: `experiment_001_minimal_loop`
- Date: 2026-05-03
- Runtime version: local `vanta` workspace, Mix project version `0.1.0`
- Evaluator: automated Experiment 001 runner
- Dataset or benchmark: current seven Document Ops fixtures
- Status: `Completed local smoke run`
- Result path:
  `docs/04_experiments/results/experiment_001/20260503_130927/`

## Setup

- Baseline: OpenClaw local agent harness planner with direct action execution
  and no governance artifacts
- Baseline designation: candidate canonical local LLM baseline for Stage 1
  Experiment 001 smoke runs
- Treatment: Stage 1 closed-loop runtime with Execution IR, Evidence Packet,
  deterministic Verifier v0, commit/abort handling, and Episode Journal
- Backbone model: `openai-codex/gpt-5.4-mini`
- Tool interface: OpenClaw `agent --local --json` action-sequence prompt through
  WSL, then local Document Ops action executor
- Compute budget: one pass over seven local fixtures
- Side-effect classes: `READ_ONLY`, `SIMULATED`, and `REVERSIBLE`; `COMMITTABLE`,
  `IRREVERSIBLE`, and `MEMORY_WRITE` remain outside Stage 1 scope
- OpenClaw harness note: this is not a pure model-only baseline. The call path
  includes OpenClaw agent context and tool availability, although the planner
  prompt instructs the model to return JSON only and not use OpenClaw tools.

## Run Attempt

Command run on 2026-05-03:

```powershell
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$out = "docs/04_experiments/results/experiment_001/$timestamp"
mix vanta.experiment001 --baseline llm --planner openclaw --model openai-codex/gpt-5.4-mini --out $out
```

Observed result path:

```text
docs/04_experiments/results/experiment_001/20260503_130927/
```

`run.json` and `summary.md` were produced.

## Metrics

| Metric | Baseline | Treatment | Notes |
| --- | --- | --- | --- |
| `task_success_rate` | `0.5714285714285714` | `1.0` | Treatment meets the current local smoke gate. |
| `invalid_action_rate` | `0.375` | `0.375` | Negative fixtures intentionally produce rejected invalid paths. |
| `verifier_false_accept_rate` | Not measured | Not measured | Not part of compact Experiment 001 runner output yet. |
| `verifier_false_reject_rate` | Not measured | Not measured | Not part of compact Experiment 001 runner output yet. |
| `evidence_sufficiency_score` | `0.0` | `1.0` | Baseline does not produce Evidence Packets by design. |
| `commit_integrity_score` | `0.5714285714285714` | `0.5714285714285714` | Compact metric counts committed tasks over all fixtures, including expected rejections. |
| `replay_consistency` | `0.0` | `1.0` | Baseline has no Episode Journal replay path by design. |
| `audit_completeness` | Not measured | Not measured | Not part of compact Experiment 001 runner output yet. |

## Findings

- The OpenClaw adapter produced schema-valid planner action sequences for all
  seven fixtures in the final run.
- The treatment arm met the current compact local smoke gate:
  `task_success_rate == 1.0`, `evidence_sufficiency_score == 1.0`,
  `replay_consistency == 1.0`, and no committed treatment task had
  `invalid_actions > 0`.
- The treatment rejected the expected negative paths for disallowed simulated
  patch, path escape, and wrong diff fixtures.
- This run does not validate H1 statistically. It is one local smoke run over
  seven fixtures with a prompt-tuned OpenClaw harness planner.

## Failures And Risks

- The measured run remains a smoke result over seven fixtures only. It must not
  be interpreted as broad validation of H1 or the full architecture.
- OpenClaw agent harness context is part of the baseline call path, so the
  baseline is not directly comparable to a pure Responses API model-only run.
- The compact runner still does not compute `verifier_false_accept_rate`,
  `verifier_false_reject_rate`, or `audit_completeness`.
- Prompt guidance was tightened for fixture-local negative paths and exact patch
  payloads before the final passing smoke run; this should be reported when
  comparing against future less-constrained baselines.

## Deferred / Post-Stage-1 Work

- Add stricter fixture-intent checks so negative fixtures cannot pass by any
  rejection path when they are meant to test a specific failure mode.
- Decide whether a broader canonical Experiment 001 baseline requires a direct
  OpenAI Responses run, a larger benchmark, or both OpenClaw and Responses as
  separately labeled baselines.
- Measure `verifier_false_accept_rate`, `verifier_false_reject_rate`, and
  `audit_completeness` in later evaluation work.
- Treat this report as closed local smoke evidence, not as broad support for H1.
