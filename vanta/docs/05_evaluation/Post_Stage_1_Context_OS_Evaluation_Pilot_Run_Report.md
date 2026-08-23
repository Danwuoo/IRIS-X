# Post-Stage-1 Context OS Evaluation Pilot Run Report

## Status

Report label: `context_evaluation_pilot`.

Plan ID: `PS1-LC-CTX-PLAN-001`.

Gate policy version: `PS1-LC-CTX-GATE-001`.

Metric policy version: `PS1-LA-METRIC-001`.

Label policy version: `PS1-LB-LABEL-001`.

Evaluation mode: `artifact_backed_post_freeze_evaluation`.

Result path:
`docs/04_experiments/results/context_os_planning/20260719_224209/`.

Completion status: `complete`.

Final pilot status: `pass_artifact_backed_evaluation_pilot`.

Evaluation fingerprint:
`sha256:97bc3d8b263e998de460fae8d063c2d3d629b48cfee9daf4b6f4e14091516680`.

This is an evaluation-tooling result, not a new closure decision. No closure
candidate or `accepted_by_closure` status was created for this pilot.

## Source, Execution, And Implementation Boundary

The pilot reads the accepted `20260601_113121` Lane A run, its closure and
report, the active frozen `20260601_113121` Lane B packet, and the
coordinator-only post-freeze arm memo. It issued zero model calls, zero
OpenClaw measured runs, zero Context OS runtime actions, zero memory writes,
zero external target accesses, and zero irreversible effects.

`Vanta.PostStage1ContextOSEvaluation` and
`mix vanta.post_stage1_context_os_evaluation` are deterministic evaluation-only
tooling. The evaluator reconstructs the existing bounded raw-trace and
unchanged `Working Set Compiler v0` selection artifacts only. It does not
modify the core runtime execution path or add a schema or action enum.

## Fixed Controls

| Control | Frozen value |
| --- | --- |
| Model | `openai-codex/gpt-5.4-mini` |
| Harness | `openclaw_agent_local` |
| Context planner adapter | `Vanta.OpenClawContextPlannerAdapter` |
| OpenClaw agent | `vanta-verifier` |
| Prompt / response budgets | `20000` / `12000` characters |
| Response format | `json_only` |
| Action / recovery attempt limits | `6` / `1` |
| Tool policy | `embedded_context_only` |
| Baseline arm | `raw_trace_bounded_openclaw_agent_local/openai-codex/gpt-5.4-mini_matched_budget` |
| Treatment arm | `working_set_compiler_v0_reference_backed_openclaw_agent_local/openai-codex/gpt-5.4-mini_matched_budget` |

The OpenClaw agent and tool policy were absent from the source-run
serialization. Their source is the user-authorized, evaluation-only post-hoc
coordinator attestation `PS1-LC-CTX-CONTROL-ATTEST-001`, whose adapter source
hash and required no-tool/embedded-context fragments were validated. They are
not source-run-native metadata and create no runtime authority. The OpenClaw
arms are not pure model-only arms.

The source global context budget remains `null` with the explicit meaning
`uses_frozen_per_fixture_budgets`. The validated budgets were `260`, `240`,
`250`, `270`, `280`, and `320` characters for the six named long-context
fixtures recorded in `fixture_inventory.md`.

## Lane A Structural And Fixture-Oracle Evidence

| Metric | Baseline | Treatment | Evidence source |
| --- | ---: | ---: | --- |
| `working_set_budget_adherence` | `1.0000` | `1.0000` | automated structural |
| `working_set_provenance_completeness` | `0.6667` | `1.0000` | automated structural |
| `context_omission_error_rate` | `0.7778` | `0.0000` | fixture oracle |
| `working_set_relevance_score` | `0.2167` | `0.9667` | fixture oracle |
| `long_task_stability` | `1.0000` | `1.0000` | structural and task outcome |

All six context artifacts per arm were traced to current fixture trees and
compared with source-run artifacts. The accepted source artifacts carry the
historical `stage1-mvp-v0` marker; the current compiler emits `stage1-mvp-v1`.
The equivalence check retains the historical marker while requiring exact
selection, ordering, budget, provenance, omitted refs, and content hashes.
These Lane A results are not human-labeled evidence.

Unsupported commits, memory writes, and disallowed side-effect classes were
all `0` at aggregate and task-level validated process floors.

## Lane B Human-Label Evidence

The active packet remained blinded in every reviewer-visible artifact. True arm
interpretation was read only from the coordinator-only memo after the primary
label freeze.

| Interpreted arm | Blinded arm | Omission | Relevance |
| --- | --- | ---: | ---: |
| Baseline | `context_arm_A` | `0.7368` (`14 / 19`) | `0.4545` (`5 / 11`) |
| Treatment | `context_arm_B` | `0.0000` (`0 / 19`) | `0.9500` (`19 / 20`) |
| Combined packet | both | `0.3684` (`14 / 38`) | `0.7742` (`24 / 31`) |

Raw counts are retained because the packet is small. Relevance must be read
together with omission so an empty or sparse context cannot create a misleading
quality interpretation. Human labels remain evaluation evidence and are not
runtime approval.

## Artifact Completeness And Reproducibility

The result directory contains `run.json`, `summary.md`,
`fixture_inventory.md`, `context_artifact_inventory.md`, and
`label_packet_ref.md`. `run.json` contains 31 hashed source file/tree refs and
an empty `validation_errors` list. The fingerprint excludes `generated_at` and
the output root; an independent rerun against the final frozen source documents
used a different temporary output directory and retained the same fingerprint.

## Test Record

The implementation was compiled with `mix compile --warnings-as-errors`.
The targeted evaluator test command was:

```text
mix test test/vanta/post_stage1/post_stage1_context_os_evaluation_test.exs --seed 0
```

It completed with `17 tests, 0 failures`. The related Lane B, evaluator, and
documentation consistency command completed with `39 tests, 0 failures`.

The repository-wide command was:

```text
mix test --seed 0
```

It completed in 87.8 seconds with `158 tests, 0 failures`. No unexecuted test
is claimed by this report.

## Interpretation Boundary

This pilot validates artifact completeness, frozen controls, source
traceability, metric recomputation, Lane B label/memo consistency, packet
blindness, process floors, and deterministic evaluation output for the named
artifacts only. It does not implement or validate full Context OS, validate H3,
authorize learned retrieval/ranking/compression, authorize memory governance,
create runtime approval or side-effect authority, expand G10, establish
production readiness, or create a new closure authority.
