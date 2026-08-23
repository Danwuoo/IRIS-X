# Baseline Identity Plan

## Purpose

Define baseline arm identity for post-Stage-1 larger controlled samples.

This document is the required artifact for `PS1-G5`. It decides whether the
OpenClaw candidate local baseline is promoted, replaced, or supplemented, and it
sets naming and reporting rules for separately named baseline arms.

It does not run a baseline, validate a model, set acceptance thresholds, or
authorize broader runtime scope.

## Status

Plan ID: `PS1-LA-BASELINE-001`.

Status: `Accepted as PS1-G5 baseline-identity artifact` on 2026-05-10.

Run status: `Not yet run`.

Decision: the OpenClaw candidate local baseline is supplemented, not promoted
and not replaced.

OpenClaw remains a local agent harness baseline. A direct OpenAI Responses API
baseline, or any other pure model-only baseline, must be emitted as a separately
named arm.

## Baseline Decision

| Question | Decision |
| --- | --- |
| Promote OpenClaw local harness result to pure model-only baseline? | No. OpenClaw results include the local agent harness and must remain labeled as harness runs. |
| Replace OpenClaw with direct Responses baseline? | No. Direct Responses may be added as a separately named arm when the environment is configured. |
| Supplement OpenClaw with separately named arms? | Yes. Larger controlled samples should preserve OpenClaw local harness continuity and add direct API or other pure model-only arms when available. |
| Can a harness-only scaled run proceed without pure model-only comparison? | Only as a harness-labeled scaled local run or exploratory run, not as a pure model baseline claim. |

## Arm Families

| Arm family | Allowed label pattern | Use | Claim boundary |
| --- | --- | --- | --- |
| OpenClaw direct execution baseline | `openclaw_agent_local/<model>_direct_execution` | Continuity with Experiment 001 local smoke and larger Document Ops harness runs. | Not pure model-only; includes OpenClaw local harness behavior. |
| Direct Responses baseline | `responses_api/<model>_direct_execution` | Pure API comparison when `OPENAI_API_KEY` and fixed model configuration are available. | Must not be compared to OpenClaw without reporting harness difference. |
| Vanta governed execution treatment | `vanta_runtime/<planner_family>/<model>_governed_execution` | Runtime treatment for minimal loop, evidence, verifier, commit, journal, and replay comparisons. | Treatment identity must include planner family and model. |
| Blind retry recovery baseline | `blind_retry_openclaw_agent_local/<model>_matched_budget` | Phase 4 style recovery comparison under matched local compute. | Recovery-specific baseline, not a general direct-execution baseline. |
| Targeted recovery treatment | `targeted_recovery_openclaw_agent_local/<model>_matched_budget` | Failure taxonomy and recovery policy treatment. | Must report failure-label source and recovery policy constraints. |
| Bounded raw-trace context baseline | `raw_trace_bounded_openclaw_agent_local/<model>_matched_budget` | Phase 5 style context comparison. | Context baseline only; not full Context OS. |
| Working Set Compiler treatment | `working_set_compiler_v0_reference_backed_openclaw_agent_local/<model>_matched_budget` | Reference-backed working-set treatment. | `Working Set Compiler v0` only; no full Context OS claim. |

Labels may include a run-specific suffix only when the suffix records a fixed
control, such as prompt version or budget. Labels must not hide harness identity.

## Prohibited Labels

The following labels or interpretations are not allowed:

- `pure_model_only` for any OpenClaw local harness result
- `canonical_baseline` without naming the harness and model
- `openai/<model>` when the call path is OpenClaw local harness
- `context_os` for `Working Set Compiler v0`
- `validated_baseline` for any local smoke or unthresholded larger sample
- `human_approved` for human labels collected as evaluation artifacts

## Required Arm Metadata

Every arm reported under this plan must record:

- arm label
- arm family
- model identifier
- harness identifier
- adapter module or execution path
- prompt template version or hash
- response format requirement
- allowed tool policy
- prompt character budget
- response character budget
- action-attempt limit
- recovery-attempt limit when applicable
- context budget when applicable
- run command or invocation description
- result path
- timestamp

For OpenClaw arms, the report must state that the call path uses the OpenClaw
local agent harness and is not a direct model-only API result.

For direct Responses arms, the report must state the API adapter, configured
model, and whether the environment was available before execution.

## Comparison Rules

- Minimal-loop governance comparisons should use the same action proposal for
  baseline direct execution and Vanta governed execution when the question is
  runtime governance rather than planner quality.
- Recovery comparisons must use matched model-call count, prompt character
  ceiling, response character ceiling, and recovery action-attempt limit.
- Working-set comparisons must use matched model, prompt character ceiling,
  response character ceiling, and embedded-context-only tool policy.
- Cross-harness comparisons must be reported as harness comparisons unless both
  arms use the same direct API path.
- Missing direct Responses data must be reported explicitly rather than inferred
  from OpenClaw local harness data.

## Promotion Rules

An arm may be reported as a pure model-only baseline only when all conditions
below are met:

- the call path is a direct model API adapter or another documented pure
  model-only interface
- no local agent harness injects additional execution context
- no hidden tool use is available to the model
- prompt template, response format, budgets, and model ID are fixed before
  execution
- the run summary names the arm separately from OpenClaw harness arms

OpenClaw local harness results can remain useful local baselines, but they
cannot be promoted into pure model-only evidence by renaming.

## Non-goals

- This plan does not select the final production baseline.
- This plan does not remove historical Experiment 001 OpenClaw results.
- This plan does not set `PS1-G2` metric thresholds.
- This plan does not authorize a larger sample run by itself.
- This plan does not validate OpenClaw, Responses API, or any model.

## Related Documents

- [Post-Stage-1 Advancement Gate](../00_manifest/Post_Stage_1_Advancement_Gate.md)
- [Post-Stage-1 Gate Inventory](../00_manifest/Post_Stage_1_Gate_Inventory.md)
- [Post-Stage-1 Larger Sample Plan](Post_Stage_1_Larger_Sample_Plan.md)
- [Experiment 001 Minimal Loop](Experiment_001_Minimal_Loop.md)
- [Ablation Plan](Ablation_Plan.md)
- [Metrics Definition](../05_evaluation/Metrics_Definition.md)
