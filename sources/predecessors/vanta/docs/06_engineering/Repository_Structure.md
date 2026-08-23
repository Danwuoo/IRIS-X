# Repository Structure

## Purpose

Document the current Post-Stage-1 repository organization and navigation rules.
This file records the tree as it exists today; it is not an instruction to move
historical artifacts, result directories, fixtures, label packets, or runtime
source files.

## Current Root Layout

```text
.
  docs/             Documentation source, schemas, protocols, results, reports
  lib/              Elixir runtime, adapters, runners, and Mix tasks
  test/             ExUnit tests and executable fixture mirror
  .github/          GitHub Actions CI configuration
  chatgpt_docs/     ChatGPT Project Knowledge export mirror, capped at 25 files
  deps/             Mix dependency checkout, generated/local artifact
  _build/           Mix build output, generated/local artifact
  .elixir_ls/       Local editor/language-server artifact
  mix.exs
  mix.lock
  AGENTS.md
```

`docs/`, `lib/`, `test/`, `.github/`, and `chatgpt_docs/` are the relevant
authored or curated trees. `deps/`, `_build/`, and `.elixir_ls/` are local
generated artifacts and are not documentation, schema, experiment, evaluation,
runtime, or CI source-of-truth paths.

## Artifact Classes

| Class | Current path | Navigation rule |
| --- | --- | --- |
| Documentation source | `docs/00_manifest/`, `docs/01_theory/`, `docs/02_specs/`, `docs/04_experiments/*.md`, `docs/05_evaluation/*.md`, `docs/06_engineering/` | Follow [Document Map](../00_manifest/Document_Map.md) and manifest precedence before treating downstream material as authoritative. |
| Schemas | `docs/03_schemas/*.schema.json` | Use [Schemas Index](../03_schemas/Schemas_Index.md) as the L3 navigation entry. Schema files define data contracts and remain the current runtime validation source. |
| Schema impact reviews | `docs/03_schemas/Post_Stage_1_Context_OS_Schema_Impact_Review.md`, `docs/03_schemas/Post_Stage_1_Side_Effect_Schema_Impact_Review.md` | Review documents only. They record no-change decisions and do not add schema enum behavior. |
| Persistence schema impact review | `docs/03_schemas/Post_Stage_1_Persistence_Schema_Impact_Review.md` | `PS1-G9` review that adds envelope/lifecycle/recovery schemas without changing existing core enum authority. |
| G10 schema impact review | `docs/03_schemas/Fixture_Local_Committable_Schema_Impact_Review.md` | Adds only the standalone approval contract, explicit fixture-commit payload, two-phase evidence fields, and typed journal/artifact refs authorized by G10. |
| Experiment protocols | `docs/04_experiments/*.md` outside `fixtures/` and `results/` | Protocols, plans, and benchmark definitions. They do not report results unless a measured run artifact or evaluation report is linked. |
| Side-effect planning fixtures | `docs/04_experiments/fixtures/side_effect_planning/` | Immutable proposal templates and evaluation-only fixture oracles for the named PS1-G8 planning pilot. They are not executable runtime fixtures or approvals. |
| Fixture-commit experiment fixtures | `docs/04_experiments/fixtures/fixture_local_committable_execution/` | Twenty-eight immutable G10 case records plus a workspace template; every run copies the template before any effect. |
| Experiment results | `docs/04_experiments/results/<experiment>/<timestamp>/` | Use [Experiment Results README](../04_experiments/results/README.md) as the L4 result navigation entry. Preserve historical, failed, superseded, timeout, partial, measured, and planning-only result directories as provenance. |
| Evaluation reports | `docs/05_evaluation/*.md` | Metrics, labeling policies, run reports, report templates, and reported evaluation summaries. |
| Label packets | `docs/05_evaluation/label_packets/<packet>/` | Use [Label Packets README](../05_evaluation/label_packets/README.md) as the L5 packet navigation entry. Lane B packet artifacts, blinded items, packet-local templates, filled labels, and import summaries are evaluation artifacts, not runtime schemas or approvals. |
| Runtime code | `lib/vanta/**/*.ex`, `lib/mix/tasks/vanta/*.ex` | Current Elixir implementation and CLI entry points. Runtime modules and Mix task modules are grouped by engineering responsibility while preserving existing module names and CLI task names. |
| Persistence code | `lib/vanta/persistence/*.ex` | Adapter contract, Memory/SQLite adapters, and fixture-local recovery protocol. Concrete SQLite code stays behind the adapter boundary. |
| Fixture-commit code | `lib/vanta/runtime/fixture_commit.ex`, `lib/vanta/experiments/fixture_commit_experiment*.ex`, `lib/mix/tasks/vanta/fixture_commit_experiment.ex` | The isolated G10 runtime path, validator/runner, and Mix entry point. |
| Executable fixtures | `test/fixtures/document_ops/` | ExUnit-consumed fixture mirror. Must stay byte-for-byte synchronized with `docs/04_experiments/fixtures/document_ops/`. |
| CI configuration | `.github/workflows/ci.yml` | GitHub Actions entry point for test layering. It runs the fast smoke alias before the full test alias and does not replace local `mix test` as the complete suite. |
| ChatGPT Project Knowledge export | `chatgpt_docs/docs/` | Curated mirror of selected source docs. It is not the source of truth and must remain at 25 files or fewer unless the cap changes. |

## Documentation Tree

```text
docs/
  00_manifest/      Governance, routing, decisions, gates, traceability
  01_theory/        Theory source, hypotheses, alternatives, validation review
  02_specs/         Implementable behavior and semantic contracts
  03_schemas/       JSON schemas plus schema impact review documents
  04_experiments/   Benchmark definitions, protocols, fixtures, results
  05_evaluation/    Metrics, labels, reports, label packets
  06_engineering/   Architecture, module plan, repo structure, test strategy
```

The documentation source tree intentionally keeps result provenance in place:

```text
docs/04_experiments/
  fixtures/document_ops/                   Documentation-side fixture source
  fixtures/side_effect_planning/            Immutable planning proposal fixtures
  results/
    experiment_001/<timestamp>/
    experiment_002/<timestamp>/
    experiment_003/<timestamp>/
    experiment_004/<timestamp>/
    experiment_005/<timestamp>/
    post_stage_1_larger_sample/<timestamp>/
    side_effect_planning/<timestamp>/      Scaffold or measured planning-pilot artifacts
    persistence_and_recovery/<timestamp>/  Experiment 006 measured persistence artifacts
    fixture_local_committable_execution/<timestamp>/  Experiment 007 measured G10 artifacts

docs/05_evaluation/
  label_packets/
    post_stage_1_lane_b_20260601_113121/   Active reported Lane B packet
    post_stage_1_lane_b_20260530_141649/   Superseded historical packet
```

The `20260601_113121` Lane A larger controlled sample is the accepted closure
for the named threshold-governed Document Ops Lane A sample only. Historical
Lane A result directories remain provenance records. Label packet directories
remain evaluation artifacts and do not authorize runtime approval, schema
changes, memory writes, irreversible effects, or H1-H5 validation.

The navigation entries for these artifact trees are:

- [Experiment Results README](../04_experiments/results/README.md)
- [Label Packets README](../05_evaluation/label_packets/README.md)

## Artifact Retention Policy

This artifact retention policy documents current tracking and ignore
boundaries. It does not move existing result, fixture, label packet, or runtime
paths.

| Artifact class | Retention rule | Tracking boundary |
| --- | --- | --- |
| Tracked source docs | Keep authored governance, theory, spec, experiment, evaluation, and engineering Markdown under `docs/`. Source docs remain the source of truth over ChatGPT export mirrors. | Tracked unless explicitly generated/local. |
| Tracked schemas | Keep `docs/03_schemas/*.schema.json` and schema navigation documents under L3. Schemas define data contracts; schema impact reviews are review documents only. The current runtime loads schemas from this docs-local path. | Tracked. Do not add enum behavior, duplicate schema authority, or packaged runtime assets through retention changes. |
| Tracked summary, closure, and report Markdown | Keep run `summary.md`, `fixture_inventory.md`, evaluation reports, label reports, closure documents, and closure candidates in place, including failed or superseded records. | Tracked when part of result/report provenance. Do not rewrite historical results to create new claims. |
| Tracked required compact run artifacts | Keep compact machine-readable artifacts that are already tracked or explicitly required by a report or closure, such as selected `run.json` files and label packet JSON/JSONL records. | Tracked only when intentionally included. Existing tracked files remain tracked even when a broad ignore pattern would ignore new untracked peers. |
| Ignored raw logs and scratch artifacts | Keep bulky raw traces, scratch JSON, and one-off local run byproducts out of source control unless a later report explicitly elevates a compact artifact. Historical tracked `_logs/` remain provenance and should not be deleted or moved during cleanup. | Ignored/local by default where `.gitignore` applies; do not broaden tracking accidentally. |
| Generated local build artifacts | Keep Mix dependencies, build output, and editor/language-server state local. | Ignored: `/deps/`, `/_build/`, and `/.elixir_ls/`. |
| ChatGPT Project Knowledge export | Keep `chatgpt_docs/` as a local curated mirror capped at 25 files or fewer unless the cap changes. When a source file already mirrored there changes, update the corresponding mirror in the same turn. Do not automatically add new README or policy files unless routing, progress, gate, or source-of-truth needs require it. | Ignored by `/chatgpt_docs`; source remains under `docs/`. |

Current `.gitignore` mapping:

| `.gitignore` entry | Policy interpretation |
| --- | --- |
| `/deps/` | Generated Mix dependencies; local only. |
| `/_build/` | Generated Mix build output; local only. |
| `/.elixir_ls/` | Local editor/language-server artifact; local only. |
| `docs/04_experiments/results/experiment_001/*/raw/` | Experiment 001 raw scratch logs; ignored while compact `run.json` and `summary.md` provenance remains reviewable. |
| `docs/04_experiments/results/*/*/*.json` | Broad guard against accidentally adding unreviewed result JSON. Required compact JSON should be explicitly tracked or explicitly unignored only when a report or closure needs it. |
| `!docs/04_experiments/results/experiment_004/20260506_231941/run.json` | Explicit tracked compact run JSON exception for the Experiment 004 local smoke closure. |
| `!docs/04_experiments/results/experiment_005/20260507_105950/run.json` | Explicit tracked compact run JSON exception for the Experiment 005 local smoke closure. |
| `!docs/04_experiments/results/side_effect_planning/*/{run.json,fixture_results.json,environment_manifest.json}` | Compact machine-readable planning-pilot evidence; these files measure proposal validation only and do not authorize runtime execution. |
| `!docs/04_experiments/results/persistence_and_recovery/*/{run.json,failure_injection_results.json,environment_manifest.json,schema_hash_policy_versions.json}` | Compact Experiment 006 machine-readable evidence required by the measured report and closure review; Markdown summaries and matrices remain tracked normally. |
| `/chatgpt_docs` | Local ChatGPT Project Knowledge export mirror; synchronize mirrored files when their source changes, but keep source-of-truth status in `docs/`. |

Retention boundaries:

- Historical, failed, superseded, timeout, and partial run directories are
  provenance. Do not delete, rename, or move them during source-tree cleanup.
- Schemas remain documentation-local under `docs/03_schemas/*.schema.json` for
  the current Post-Stage-1 runtime. Future runtime asset packaging requires a
  separate accepted migration gate with loader, package, and test changes.
- Side-effect planning results remain planning-only artifacts. Retention does
  not authorize runtime execution of `COMMITTABLE`, `IRREVERSIBLE`, or
  `MEMORY_WRITE` actions.
- Label packets remain evaluation artifacts. Filled labels, import summaries,
  coordinator-only notes, and redacted packets do not create runtime approval,
  schema expansion, H1-H5 validation, or full Context OS validation.
- New validation claims require measured experiment artifacts plus evaluation
  and manifest closure treatment. Retention alone never validates a hypothesis.

## Runtime Code Layout

The runtime source under `lib/vanta/` is grouped by engineering responsibility
while preserving existing `Vanta.*` module names. The directory split is a
source-layout cleanup only; it does not rename modules, change runtime behavior,
move documentation provenance paths, or authorize new side-effect classes.

```text
lib/
  vanta/
    runtime/
      state_manager.ex
      execution_ir_compiler.ex
      action_executor.ex
      evidence_builder.ex
      verifier_runtime.ex
      commit_controller.ex
      episode_journal.ex
      runtime.ex
      replay_runner.ex
    persistence/
      persistence.ex
      memory_adapter.ex
      sqlite_adapter.ex
      recovery.ex
    adapters/
      planner_adapter.ex
      open_ai_planner_adapter.ex
      open_claw_harness.ex
      open_claw_planner_adapter.ex
      open_claw_verifier_adapter.ex
      open_claw_recovery_adapter.ex
      open_claw_context_planner_adapter.ex
    document_ops/
      structured_edit.ex
      fixture_acceptance.ex
    experiments/
      experiment001.ex ... experiment005.ex
      baseline_runner.ex
      blind_retry_runner.ex
      recovery_runner.ex
      recovery_policy.ex
      evaluation_harness.ex
      working_set_compiler.ex
      raw_trace_context_builder.ex
      persistence_experiment.ex
    post_stage1/
      post_stage1_larger_sample.ex
      post_stage1_lane_b_packet.ex
      post_stage1_lane_b_label_results.ex
      post_stage1_side_effect_planning.ex
      post_stage1_side_effect_planning/
        path_helpers.ex
        validator.ex
    support/
      hash.ex
      path_guard.ex
      schema.ex
  mix/tasks/
    vanta/
      experiment001.ex ... experiment005.ex
      post_stage_1_larger_sample.ex
      post_stage_1_lane_b_packet.ex
      post_stage1_lane_b_label_results.ex
      post_stage_1_side_effect_planning.ex
      persistence_experiment.ex
```

`lib/mix/tasks/vanta/` groups the Vanta Mix task source files by CLI namespace.
This is a source-layout cleanup only; existing `Mix.Tasks.Vanta.*` module names,
public `mix vanta.*` task names, and compatibility aliases in `mix.exs` remain
unchanged.

## Fixture Mirror Rule

Document Ops fixtures have two required locations:

```text
docs/04_experiments/fixtures/document_ops/
test/fixtures/document_ops/
```

The docs tree is the documentation-side fixture and provenance mirror. The test
tree is the executable fixture mirror used by ExUnit and Mix tasks. The two
trees must remain byte-for-byte synchronized. `Vanta.FixtureSyncTest` enforces
this by comparing relative file lists and file contents.

The PS1-G8 planning fixtures under
`docs/04_experiments/fixtures/side_effect_planning/` are a separate
evaluation-only fixture class. The planning runner reads them directly,
verifies pre/post tree hashes, and does not create an executable
`test/fixtures/` mirror.

## Follow-Up Source Layout

No remaining source-layout follow-up should move
`docs/04_experiments/results/`, `docs/04_experiments/fixtures/`,
`test/fixtures/`, or `docs/05_evaluation/label_packets/` unless a later
accepted repository migration plan explicitly changes provenance path policy.

## Schema Packaging Decision

The accepted 2026-07-06 schema packaging decision keeps schema files under
`docs/03_schemas/*.schema.json` for the current Post-Stage-1 runtime.
`Vanta.Schema` continues to load validation contracts from this docs-local path.
This batch does not copy schemas into a runtime asset directory, change Mix
packaging, or introduce a second schema authority.

Runtime asset packaging is a future migration, not an implicit source-layout
cleanup. It requires a later accepted decision plus coordinated loader, package,
schema-distribution, and test updates.

## Rules

- Theory changes should not directly mutate implementation behavior.
- Schemas define data contracts; specs define behavior.
- Schema impact reviews document schema decisions but do not add enum behavior.
- Experiment results must stay separate from protocols and design docs.
- Historical, superseded, and failed result directories remain provenance.
- Label packets are evaluation artifacts, not runtime schemas or runtime
  approvals.
- Generated artifacts should remain clearly separated from authored source.
- ChatGPT Project Knowledge export files must be synchronized byte-for-byte when
  their source file is included in `chatgpt_docs/`.
