# Experiment 001: Minimal Loop

## Research question

Does a minimal closed loop improve task success and reduce invalid actions compared with a baseline function-calling agent?

## Hypothesis tested

H1: Reasoning-to-action fidelity is the core bottleneck of agent capability.

## Baseline

ReAct or traditional function-calling agent with no explicit Execution IR, Evidence Packet, or Episode Journal.

For the Stage 1 local prototype, the executable baseline is an LLM planner that
emits a JSON action sequence. The baseline runner executes that same sequence
directly through the action executor and records evaluation labels, but it does
not produce Execution IR, Evidence Packets, Verifier Outputs, commits, or an
Episode Journal.

Two planner adapters are implemented:

- `Vanta.OpenAIPlannerAdapter`: OpenAI Responses API, env-gated by
  `OPENAI_API_KEY` and `OPENAI_MODEL`.
- `Vanta.OpenClawPlannerAdapter`: OpenClaw local agent harness through WSL,
  defaulting to `openai-codex/gpt-5.4-mini`.

OpenClaw runs must be labeled as OpenClaw agent harness baselines because the
call path injects OpenClaw agent context and may expose OpenClaw tools even when
the planner prompt instructs the model to return JSON only.

## Treatment

Runtime with canonical state, Execution IR, Evidence Packet, Verifier Runtime, and commit/abort logging for reversible or simulated actions.

The treatment arm uses the same LLM action sequence as the baseline and routes it
through `Vanta.Runtime.run_task/3`.

## Candidate Canonical Local LLM Baseline

For Stage 1 local smoke runs, OpenClaw `openai-codex/gpt-5.4-mini` is the
candidate canonical local LLM baseline. This designation is limited to local
Experiment 001 smoke comparisons and does not make the OpenClaw harness result a
pure model-only baseline or a statistically validated canonical benchmark.

Post-Stage-1 baseline identity is governed by
[Baseline Identity Plan](Baseline_Identity_Plan.md). That plan keeps OpenClaw as
a local harness baseline and supplements it with separately named direct API
arms when available.

## Local smoke configuration

- Backbone model: `gpt-5.4-mini`. For OpenAI Responses runs this is provided
  through `OPENAI_MODEL`; for OpenClaw runs this is
  `openai-codex/gpt-5.4-mini`.
- Sample: the current seven Document Ops fixtures, run once.
- Result location: `docs/04_experiments/results/experiment_001/<timestamp>/`.
- Exit gate: treatment `task_success_rate`, `evidence_sufficiency_score`, and
  `replay_consistency` must all equal `1.0`, and treatment must have zero
  unsupported commits.

This configuration defines only a local Document Ops smoke run. It is not a
statistical validation of the architecture and must not be described as broad
empirical support for H1.

## Metrics

- `task_success_rate`
- `invalid_action_rate`
- `evidence_sufficiency_score`
- `commit_integrity_score`

## Required logs

- Canonical state snapshots.
- Execution steps.
- Evidence packets.
- Verifier outputs.
- Episode journal.

## Success criteria

- Treatment improves task success or reduces invalid action rate without increasing unsupported commits.
- Treatment produces complete logs for audit.

## Failure criteria

- Treatment only improves task success by hiding invalid actions.
- Required logs are missing.
- Source or environment state changes cannot be explained from the journal.

## Readiness Checklist

- [x] Stage 1 MVP Entry Gate exists.
- [x] Document Ops selected as first controlled environment.
- [x] Stage 1 schema contracts define required runtime fields.
- [x] Initial Document Ops fixture set exists.
- [x] Phase 1 runtime skeleton exists.
- [x] Runtime orchestrator, baseline runner, replay runner, and experiment runner exist.
- [x] Positive and negative Document Ops fixtures exist.
- [x] Candidate canonical local LLM baseline, sample size, and exit gate are locked.
- [x] Baseline and treatment runs have been executed with a configured LLM baseline.
- [x] Evaluation report contains measured results.

## Status

`Closed: local smoke completed`.

Measured locally with the OpenClaw local agent harness on 2026-05-03. The closed
candidate canonical local baseline run is:

```text
docs/04_experiments/results/experiment_001/20260503_130927/
```

That run uses `openai-codex/gpt-5.4-mini` through OpenClaw and meets the current
compact treatment smoke gate. It is still a seven-fixture local smoke result,
not statistical support for H1 or broad empirical support for the full
architecture. Closure is recorded in
[Stage 1 Experiment 001 Closure](../00_manifest/Stage_1_Experiment_001_Closure.md).

A prior local attempt on 2026-05-02 with `OPENAI_MODEL=gpt-5.4-mini` and the
direct OpenAI adapter was blocked because the execution environment did not
provide `OPENAI_API_KEY`.

## Deferred Work

- Direct OpenAI Responses comparison with `gpt-5.4-mini`.
- Larger benchmark size beyond the current seven Document Ops fixtures.
- `verifier_false_accept_rate`, `verifier_false_reject_rate`, and
  `audit_completeness` measurement in later experiments.
- Post-Stage-1 direct Responses comparison under the separately named arm rules
  in [Baseline Identity Plan](Baseline_Identity_Plan.md).

## Future Rerun Reference

Direct OpenAI command once the OpenAI environment is configured:

```powershell
$env:OPENAI_API_KEY = "<local-secret>"
$env:OPENAI_MODEL = "gpt-5.4-mini"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$out = "docs/04_experiments/results/experiment_001/$timestamp"
mix vanta.experiment001 --baseline llm --out $out
```

OpenClaw command for a local agent harness rerun:

```powershell
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$out = "docs/04_experiments/results/experiment_001/$timestamp"
mix vanta.experiment001 --baseline llm --planner openclaw --model openai-codex/gpt-5.4-mini --out $out
```
