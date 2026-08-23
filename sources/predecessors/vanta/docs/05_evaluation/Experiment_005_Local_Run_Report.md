# Experiment 005 Local Run Report

## Experiment

- Experiment ID: `experiment_005_working_set_compiler`
- Date: 2026-05-07
- Runtime version: local `vanta` workspace, Mix project version `0.1.0`
- Evaluator: fixture oracle plus working-set acceptance metadata
- Dataset or benchmark: five controlled Document Ops long-context fixtures
- Status: `Completed OpenClaw local harness run`
- Result path:
  `docs/04_experiments/results/experiment_005/20260507_105950/`

## Setup

- Baseline:
  `raw_trace_bounded_openclaw_agent_local/openai-codex/gpt-5.4-mini_matched_budget`
- Treatment:
  `working_set_compiler_v0_reference_backed_openclaw_agent_local/openai-codex/gpt-5.4-mini_matched_budget`
- Backbone model: OpenClaw `openai-codex/gpt-5.4-mini`
- OpenClaw agent: `vanta-verifier`
- Tool interface: OpenClaw local harness through WSL
- Fixture set:
  `docops_ws_evidence_packet_001`, `docops_ws_irrelevant_context_001`,
  `docops_ws_omission_trap_001`, `docops_ws_recovery_context_001`, and
  `docops_ws_traceability_long_001`
- Side-effect scope: fixture-local read-only Document Ops actions only; no
  irreversible external action or memory write is executed

The baseline serializes fixture refs in bounded raw-trace order. The treatment
compiles a schema-valid, reference-backed `WorkingSet` using
`Working Set Compiler v0`. Both arms use embedded context only and the same
OpenClaw model, tool interface, prompt ceiling, and response ceiling.

## Metrics

| Metric | Raw Trace Baseline | Working Set Treatment | Notes |
| --- | --- | --- | --- |
| `working_set_budget_adherence` | `1.0` | `1.0` | Both arms stayed within the fixed local budget ceiling. |
| `working_set_provenance_completeness` | `0.6` | `1.0` | Treatment preserved complete provenance for selected refs. |
| `context_omission_error_rate` | `0.9333333333333332` | `0.0` | Treatment included all fixture-required refs. |
| `working_set_relevance_score` | `0.1` | `1.0` | Treatment selected only fixture-relevant refs. |
| `long_task_stability` | `1.0` | `1.0` | Both arms completed the current smoke fixtures. |
| `task_success_rate` | `1.0` | `1.0` | Both arms produced accepted read-only validation actions. |
| `unsupported_commits` | `0` | `0` | No committed invalid action paths. |
| `memory_writes` | `0` | `0` | Phase 5 memory-write boundary held. |

## Labeling Status

No human or secondary labels were collected for this local smoke run. The
omission and relevance values are deterministic fixture-oracle scores from
`expected/working_set_acceptance.json`, and provenance completeness is a
structural selected-ref metadata check. Under
[Human Labeling Guide](Human_Labeling_Guide.md), the `run.json` context
artifacts, fixture packets, and source refs can be used as inputs to a later
working-set labeling pilot, but this report itself contains no human
working-set labels.

These measurements may be cited only as local smoke evidence for
`Working Set Compiler v0` and as artifact inputs for later broader evaluation.
They must not be described as human-labeled relevance or omission results,
statistical support for H3, broad H3 validation, or full Context OS validation.

Compute matching was preserved fixture by fixture for the configured budget
ceilings:

| Compute field | Raw Trace Baseline | Working Set Treatment |
| --- | --- | --- |
| `max_prompt_chars` | `20000` | `20000` |
| `max_response_chars` | `12000` | `12000` |
| `matched_fixture_count` | `5` | `5` |

Prompt and response character counts vary by context artifact, but both arms
remain within the same configured ceilings. Token counts in the run are
character-derived estimates using `ceil(chars / 4)`.

## Run Command

Command recorded for Experiment 005 runs:

```powershell
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$out = "docs/04_experiments/results/experiment_005/$timestamp"
mix vanta.experiment005 --out $out --model openai-codex/gpt-5.4-mini --openclaw_agent vanta-verifier --max-prompt-chars 20000 --max-response-chars 12000
```

Observed result path:

```text
docs/04_experiments/results/experiment_005/20260507_105950/
```

`run.json` and `summary.md` were produced. The result status is `completed`,
and the local smoke gate reports `local_smoke_pass: true`.

## Findings

- The run status is `completed`.
- All five treatment `WorkingSet` artifacts validate against
  `working_set.schema.json`.
- The treatment arm included every fixture-required ref and preserved complete
  selected-ref provenance.
- The bounded raw-trace baseline omitted required refs in the controlled
  omission-trap conditions, as intended by the fixture metadata.
- Existing closed-loop commit boundaries held for this smoke run: no unsupported
  commits and no memory writes.
- The run provides a measured local smoke result for `Working Set Compiler v0`.
  It is not broad validation of H3 or full Context OS.

## Failures And Risks

- The fixture count is five, so this is smoke-scale coverage, not a statistically
  powered long-context benchmark.
- OpenClaw results include local harness and `vanta-verifier` agent effects;
  they must not be described as pure model-only results.
- Fixture relevance and omission labels are deterministic scoring references,
  not substitutes for human labels in broader evaluation.
- The current compiler is deterministic reference-backed selection only; it does
  not implement learned retrieval, compression, memory governance, or full
  Context OS.

## Next Steps

- Keep Phase 5 claims scoped to the five-fixture local smoke result.
- Add larger Document Ops long-context samples before treating H3 as empirically
  supported.
- Add human or secondary labels before using relevance and omission scores as
  broader evaluation evidence.
