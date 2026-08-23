# Experiment 005: Working Set Compiler

## Research Question

Can reference-backed `WorkingSet` artifacts reduce omission and provenance
failures versus bounded raw trace context under fixed local OpenClaw budget,
without breaking the existing closed loop?

## Hypothesis Pressure Tested

H3: Working set quality can matter more than simply increasing nominal context
when budget, provenance, and replay constraints are fixed.

Experiment 005 is a local smoke pressure test only. It is not validation of H3
or full Context OS.

## Baseline

`raw_trace_bounded_openclaw_agent_local/<model>_matched_budget`

The baseline serializes fixture-provided refs in raw trace order and truncates
under the same prompt-character budget used by treatment.

## Treatment

`working_set_compiler_v0_reference_backed_openclaw_agent_local/<model>_matched_budget`

The treatment compiles a schema-valid `WorkingSet` with deterministic
reference-backed selection. Required refs are selected first, optional refs are
selected by fixture metadata and kind priority, and omitted optional refs are
recorded.

## Fixed Budget Rule

Each arm must use the same:

- OpenClaw model.
- OpenClaw local harness interface through WSL.
- Prompt character ceiling.
- Response character ceiling.
- Fixture-local runtime action set.

Exact token usage is not available from the current OpenClaw harness contract.
The run records estimated token counts from character counts and must label
those counts as estimates.

## Phase 5 Fixture Set

Experiment 005 uses only fixtures with `expected/working_set_acceptance.json`:

- `docops_ws_traceability_long_001`
- `docops_ws_evidence_packet_001`
- `docops_ws_irrelevant_context_001`
- `docops_ws_omission_trap_001`
- `docops_ws_recovery_context_001`

These are controlled Document Ops long-context fixtures. No irreversible
external action is executed.

## Metrics

- `working_set_budget_adherence`
- `working_set_provenance_completeness`
- `context_omission_error_rate`
- `working_set_relevance_score`
- `long_task_stability`
- `task_success_rate`
- unsupported commits
- memory writes

## Status

Protocol, implementation, mock-run support, and one measured OpenClaw local
harness run are implemented. The measured run at
`docs/04_experiments/results/experiment_005/20260507_105950/` closes Phase 5 as
`Closed: local smoke completed` for the controlled five-fixture Document Ops
working-set set.

Implemented entrypoint:

```powershell
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$out = "docs/04_experiments/results/experiment_005/$timestamp"
mix vanta.experiment005 --out $out --model openai-codex/gpt-5.4-mini --openclaw_agent vanta-verifier --max-prompt-chars 20000 --max-response-chars 12000
```

Mock tests and fixture execution must not be described as validation of H3. A
measured OpenClaw run must also remain local-smoke scoped.

## Related Documents

- [Phase 5 Working Set Compiler Gate](../00_manifest/Phase_5_Working_Set_Compiler_Gate.md)
- [Context OS and Working Set Compiler Note](../02_specs/Context_OS_and_Working_Set_Compiler_Note.md)
- [Ablation Plan](Ablation_Plan.md)
- [Document Ops Benchmark](Document_Ops_Benchmark.md)
- [Metrics Definition](../05_evaluation/Metrics_Definition.md)
