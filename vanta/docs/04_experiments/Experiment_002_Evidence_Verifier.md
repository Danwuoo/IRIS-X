# Experiment 002: Evidence Verifier

## Research question

Does structured Evidence Packet input improve verifier reliability compared with final-answer judging or raw trace judging?

## Hypothesis tested

H2: Evidence Packet can significantly improve verifier reliability.

## Baseline

Verifier sees only final answer or unstructured execution trace.

For the implemented local runner, the two baseline arms are:

- `final_answer`
- `raw_trace`

## Treatment

Verifier consumes structured Evidence Packet fields including pre-state, action reference, observation, post-state, constraints, and provenance.

For the implemented local runner, the treatment arm is:

- `structured_evidence_packet`

The current local runner applies a deterministic Verifier v0 gate before the
LLM verifier for the `structured_evidence_packet` arm only. The `final_answer`
and `raw_trace` arms remain LLM-only baselines. A deterministic `reject` or
`request_evidence` decision is non-overridable and prevents LLM invocation for
that structured item.

The LLM verifier path is OpenClaw local harness and must be labeled as
`openclaw_agent_local/<model>_verifier`. It is not a pure model-only result.

Action sequences are fixed from fixture `expected/acceptance.json` recipes so
planner variation is not mixed into the verifier comparison.

## Metrics

- `verifier_false_accept_rate`
- `verifier_false_reject_rate`
- `evidence_sufficiency_score`
- `verifier_brier_score`
- `request_evidence_rate`
- `abstain_rate`

For this local runner, `reject`, `abstain`, and `request_evidence` all count as
false reject when the fixture oracle label is valid.

## Required logs

- Evidence packets.
- Verifier decisions.
- Fixture oracle accept/reject labels.
- Provenance source records.

Human labels are deferred for this local smoke configuration.

## Success criteria

- Treatment reduces false accept rate under matched task distribution.
- Treatment does not create an unacceptable false reject increase.
- Evidence sufficiency labels correlate with verifier decisions.

## Failure criteria

- Evidence Packet increases false confidence.
- Verifier accepts invalid actions because model-generated explanations are treated as evidence.
- Provenance is missing or not externally grounded.

## Status

Runner implemented; latest OpenClaw measured run completed on 2026-05-04.

Latest measured result:

- Path: `docs/04_experiments/results/experiment_002/20260504_205316/`
- Model: `openai-codex/gpt-5.4`
- OpenClaw agent: `vanta-verifier`
- Status: `completed`
- Report: `docs/05_evaluation/Experiment_002_Local_Run_Report.md`

The completed run shows the rules-first structured verifier treatment reducing
structured-arm false accepts from the prior `0.6666666666666666` to `0.0`
without increasing structured-arm false rejects. This is an engineering
correction to verifier policy, not broad validation of H2.

A same-day rules-first run at
`docs/04_experiments/results/experiment_002/20260504_204537/` is retained but
superseded by the latest run because a policy-rule ordering cleanup landed
before the final rerun.

The previous completed `openai-codex/gpt-5.4` run using OpenClaw
`vanta-verifier` without the rules-first structured gate is retained at
`docs/04_experiments/results/experiment_002/20260504_104454/`. That run is
superseded because the structured arm accepted invalid disallowed-action and
path-escape fixtures.

The previous completed `openai-codex/gpt-5.4` run using OpenClaw `main` is
retained at `docs/04_experiments/results/experiment_002/20260503_235319/`.
That run is superseded because its structured arm produced all-abstain outputs
after OpenClaw returned context-overflow text for every structured item.

An earlier `openai-codex/gpt-5.4` attempt at
`docs/04_experiments/results/experiment_002/20260503_234357/` was `partial`
because OpenClaw agent `main` did not allow that model override. The OpenClaw
local allowlist was updated before the latest completed run.

Implemented entrypoint:

```powershell
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$out = "docs/04_experiments/results/experiment_002/$timestamp"
mix vanta.experiment002 --verifier openclaw --model openai-codex/gpt-5.4 --openclaw-agent vanta-verifier --out $out
```

Results must be written under
`docs/04_experiments/results/experiment_002/<timestamp>/` and reported as
`completed` only after the OpenClaw verifier run finishes. If OpenClaw preflight
fails, no completed result may be recorded.
