# Experiment 002 Local Run Report

## Experiment

- Experiment ID: `experiment_002_evidence_verifier`
- Date: 2026-05-04
- Runtime version: local `vanta` workspace, Mix project version `0.1.0`
- Evaluator: fixture oracle
- Dataset or benchmark: seven Document Ops fixtures
- Status: `Completed OpenClaw local harness run`
- Result path:
  `docs/04_experiments/results/experiment_002/20260504_205316/`

## Setup

- Baseline: `final_answer` and `raw_trace` LLM verifier arms.
- Treatment: rules-first `structured_evidence_packet` verifier arm.
- Backbone model: OpenClaw `openai-codex/gpt-5.4`.
- OpenClaw agent: dedicated `vanta-verifier` local verifier agent.
- Tool interface: OpenClaw local harness through WSL.
- Action source: fixture `expected/acceptance.json` action sequences.
- Side-effect classes: `READ_ONLY`, `SIMULATED`, and `REVERSIBLE`.

The treatment arm applies deterministic Verifier v0 before LLM review. A
deterministic `reject` or `request_evidence` is non-overridable and records
`llm_invoked: false`. The `final_answer` and `raw_trace` arms remain LLM-only
baselines.

The dedicated verifier agent uses a fixed verifier system prompt, empty skills,
and no callable tool entries in the OpenClaw run report. This is still an
OpenClaw local harness result, not a pure model-only verifier result.

## Metrics

| Metric | Final Answer | Raw Trace | Structured Evidence Packet | Notes |
| --- | --- | --- | --- | --- |
| `verifier_false_accept_rate` | `1.0` | `0.6666666666666666` | `0.0` | Invalid oracle item accepted by the verifier path. |
| `verifier_false_reject_rate` | `1.0` | `0.0` | `0.0` | Valid oracle item not accepted by the verifier path. |
| `evidence_sufficiency_score` | `0.0` | `0.0` | `1.0` | Structured packet complete and provenance-grounded. |
| `verifier_brier_score` | `0.8186571428571428` | `0.2722428571428571` | `0.001014285714285716` | Mean squared error between confidence and strict correctness. |
| `request_evidence_rate` | `0.5714285714285714` | `0.0` | `0.0` | Reported separately from false reject. |
| `abstain_rate` | `0.0` | `0.0` | `0.0` | Reported separately from false reject. |

## Run Command

Command run on 2026-05-04:

```powershell
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$out = "docs/04_experiments/results/experiment_002/$timestamp"
mix vanta.experiment002 --verifier openclaw --model openai-codex/gpt-5.4 --openclaw-agent vanta-verifier --out $out
```

Observed result path:

```text
docs/04_experiments/results/experiment_002/20260504_205316/
```

`run.json` and `summary.md` were produced.

## Findings

- The run status is `completed`; `run.json` validates against
  `experiment_run.schema.json`.
- The run contains no `verifier_error` entries and no adapter-normalized
  `adapter_error` outputs.
- The OpenClaw verifier path was changed from `main` to the dedicated
  `vanta-verifier` agent. This removed the prior context-overflow/all-abstain
  structured-arm failure mode.
- The adapter now generates short automatic session ids to stay below the
  OpenAI Codex provider `prompt_cache_key` 64-character limit.
- The final-answer arm produced decisions `accept=3` and `request_evidence=4`.
- The raw-trace arm produced decisions `accept=6` and `reject=1`.
- The structured Evidence Packet arm produced decisions `accept=4` and
  `reject=3`.
- All three invalid structured items were stopped by deterministic gate with
  `llm_invoked: false`: disallowed action, path escape, and wrong diff.
- All four valid structured items proceeded to OpenClaw LLM review and were
  accepted with `llm_invoked: true`.
- The structured-arm `verifier_false_accept_rate` fell from the previous
  `0.6666666666666666` run to `0.0`, while structured-arm
  `verifier_false_reject_rate` stayed `0.0`.
- This completed local harness run records a verifier-policy correction. It
  should not be reported as broad validation of H2.

## Additional Runs

- A same-day rules-first run is retained at
  `docs/04_experiments/results/experiment_002/20260504_204537/`. It is
  superseded by the latest run because a policy-rule ordering cleanup landed
  before the final rerun.
- The previous completed `openai-codex/gpt-5.4` run using OpenClaw
  `vanta-verifier` without the rules-first structured gate is retained at
  `docs/04_experiments/results/experiment_002/20260504_104454/`. That run is
  superseded because the structured arm accepted invalid disallowed-action and
  path-escape fixtures.
- The previous completed `openai-codex/gpt-5.4` run using OpenClaw `main` is
  retained at
  `docs/04_experiments/results/experiment_002/20260503_235319/`.
- That earlier completed run is superseded for current reporting because its
  structured arm produced `abstain=7` after OpenClaw returned context-overflow
  text for every structured item.
- The previous completed `openai-codex/gpt-5.4-mini` run is retained at
  `docs/04_experiments/results/experiment_002/20260503_231430/`.
- An earlier `openai-codex/gpt-5.4` attempt before the allowlist change is
  retained at
  `docs/04_experiments/results/experiment_002/20260503_234357/`; its status was
  `partial` because OpenClaw `main` rejected the model override.

## Failures And Risks

- OpenClaw results include local harness effects and must not be described as
  pure model-only verifier results.
- The structured-arm improvement depends on deterministic Stage 1 rules for the
  current seven fixtures; it is not evidence that LLM review alone detects these
  violations.
- The seven-fixture local comparison is a smoke-scale experiment, not a
  statistical validation of H2.
- Fixture oracle labels are deterministic but are not a substitute for human
  labels in broader verifier evaluation.

## Next Steps

- Add a direct Responses verifier arm if a pure model-only comparison is needed.
- Expand deterministic-gate regression coverage as new invalid fixture classes
  are added.
- Expand beyond the seven-fixture smoke set before making broader verifier
  reliability claims.
