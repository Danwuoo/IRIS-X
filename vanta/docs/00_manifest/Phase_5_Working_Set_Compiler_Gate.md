# Phase 5 Working Set Compiler Gate

## Purpose

Define the Phase 5 entry and local smoke gate for `Working Set Compiler v0`
without expanding into full Context OS implementation or empirical validation of
H3.

## Phase 5 Scope

Phase 5 implements only a reference-backed `Working Set Compiler v0`.

Allowed:

- Compile schema-valid `WorkingSet` artifacts from canonical state refs,
  Evidence Packet refs, constraint refs, and recovery context refs.
- Record selection policy, rationale, token budget metadata, provenance, and
  omitted-context notes.
- Compare working-set treatment against a bounded raw-trace baseline on
  controlled Document Ops long-context fixtures.

Disallowed:

- Full Context OS optimization.
- Learned retrieval, ranking, or compression.
- Raw tool log dumps as working sets.
- Full memory dumps.
- Memory writes or memory governance.
- Claims that H3 or full Context OS is validated.

## Baseline

`raw_trace_bounded_openclaw_agent_local/<model>_matched_budget`

The baseline builds a bounded raw trace context under the same prompt-character
budget as treatment. It preserves the trace-like fixture order and truncates
when the budget is exhausted. It records included and dropped refs for omission
and provenance scoring.

## Treatment

`working_set_compiler_v0_reference_backed_openclaw_agent_local/<model>_matched_budget`

The treatment uses deterministic reference-backed selection to produce a
schema-valid `WorkingSet`. Required refs are selected first, then optional refs
are selected by fixture metadata and stable kind priority. Omitted optional refs
must be recorded in `omitted_context_notes`.

## Fixed Local Smoke Controls

- Model: default `openai-codex/gpt-5.4-mini`, unless explicitly overridden in
  the run command.
- Tool interface: OpenClaw local harness through WSL.
- Tool use inside OpenClaw prompt: disallowed; embedded context only.
- Prompt budget: fixed by `--max-prompt-chars`.
- Response budget: fixed by `--max-response-chars`.
- Token accounting: character-derived estimates using `ceil(chars / 4)` until
  the OpenClaw contract exposes exact usage.
- Runtime integration: Experiment 005 wrapper only; the existing
  `Vanta.Runtime.run_task/3` commit path is unchanged.

## Local Smoke Pass Conditions

The Phase 5 local smoke gate passes only when all conditions hold:

- OpenClaw is configured and the run status is `completed`.
- Exactly five Phase 5 Document Ops fixtures are run.
- Every treatment `WorkingSet` artifact validates against
  `working_set.schema.json`.
- Treatment `working_set_budget_adherence == 1.0`.
- Treatment `working_set_provenance_completeness == 1.0`.
- Treatment `context_omission_error_rate` is lower than baseline.
- Treatment `working_set_relevance_score` is higher than baseline.
- Treatment `long_task_stability >= baseline`.
- Unsupported commits equal `0`.
- Memory writes equal `0`.
- Existing closed-loop tests still pass.

Failing this gate may be recorded as a failed local smoke run, but it must not
be described as validation of Context OS or H3.

## Related Documents

- [Context OS and Working Set Compiler Note](../02_specs/Context_OS_and_Working_Set_Compiler_Note.md)
- [Experiment 005 Working Set Compiler](../04_experiments/Experiment_005_Working_Set_Compiler.md)
- [Metrics Definition](../05_evaluation/Metrics_Definition.md)
- [Implementation Timeline](../06_engineering/Implementation_Timeline.md)
