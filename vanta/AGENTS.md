# Vanta Agent Instructions

This repository is a research and engineering program for an agent runtime. Treat the
documentation system as the source of routing truth. Do not treat theory prose as an
implementation order until it has passed through specs, schemas, experiments, and
evaluation documents.

## Default Interaction

- Respond to the user in Traditional Chinese unless they ask otherwise.
- Be direct and concrete. Distinguish clearly between what is already documented,
  what is only a draft, and what is still an open question.
- When asked for status, inspect the relevant files before answering.
- When asked to write or change files, make the change directly and keep the edit
  scoped to the requested documentation or implementation layer.
- Do not claim that a hypothesis, architecture, or experiment is validated unless
  an experiment document contains measured results.

## Repository Reading Order

Always start with these when orienting:

1. `docs/00_manifest/Project_Manifest.md`
2. `docs/00_manifest/Document_Map.md`
3. `docs/00_manifest/Traceability_Matrix.md`
4. `docs/00_manifest/Glossary.md`

The two substantive theory inputs are:

- `docs/01_theory/Design_Theory.md`
- `docs/01_theory/Validation_and_Refutation_Report.md`

Current specs, schemas, experiments, evaluation, and engineering documents may be
drafts. Check their contents and open questions before treating them as locked.

## Layer Responsibilities

- `docs/00_manifest/`: scope, terminology, routing, decisions, traceability.
- `docs/01_theory/`: source theory, validation review, hypotheses, alternatives.
- `docs/02_specs/`: implementable MVP behavior and semantic contracts.
- `docs/03_schemas/`: JSON/data contracts shared by runtime, benchmark, evaluation.
- `docs/04_experiments/`: benchmarks, ablations, experiment protocols.
- `docs/05_evaluation/`: metrics, labels, guides, report templates.
- `docs/06_engineering/`: architecture, module plan, timeline, testing strategy.

Use this precedence for engineering decisions:

1. Manifest governance and explicit decisions.
2. Specs and schemas.
3. Experiment/evaluation requirements.
4. Engineering plans.
5. Theory documents as background only.

## Task Routing

For conceptual boundary or Stage 0 questions, read:

- `docs/01_theory/Design_Theory.md`
- `docs/00_manifest/Project_Manifest.md`
- `docs/00_manifest/Glossary.md`
- `docs/02_specs/Execution_IR_and_Episode_Semantics.md`
- `docs/02_specs/Evidence_Packet_and_Verifier_Runtime.md`
- `docs/02_specs/Commit_Abort_Replay_Semantics.md`
- `docs/02_specs/Failure_Taxonomy_v0.md`

For MVP runtime/spec work, read:

- `docs/02_specs/Minimal_Closed_Loop_Runtime_Spec.md`
- `docs/02_specs/Execution_IR_and_Episode_Semantics.md`
- `docs/02_specs/Evidence_Packet_and_Verifier_Runtime.md`
- `docs/02_specs/Commit_Abort_Replay_Semantics.md`
- `docs/03_schemas/*.schema.json`

For schema work, read the upstream spec first, then the target schema:

- Execution steps: `Execution_IR_and_Episode_Semantics.md`,
  `execution_step.schema.json`, `episode_journal.schema.json`
- Evidence/verifier: `Evidence_Packet_and_Verifier_Runtime.md`,
  `evidence_packet.schema.json`, `verifier_output.schema.json`
- Benchmarks/evaluation: `Benchmark_Task_Format.md`, `Metrics_Definition.md`,
  `benchmark_task.schema.json`, `eval_result.schema.json`

For experiment or benchmark work, read:

- `docs/01_theory/Research_Hypotheses.md`
- `docs/01_theory/Alternative_Theories.md`
- `docs/04_experiments/Ablation_Plan.md`
- `docs/04_experiments/Document_Ops_Benchmark.md`
- `docs/05_evaluation/Metrics_Definition.md`

For evaluation and labeling work, read:

- `docs/05_evaluation/Metrics_Definition.md`
- `docs/05_evaluation/Human_Labeling_Guide.md`
- `docs/05_evaluation/Verifier_Labeling_Guide.md`
- `docs/05_evaluation/Failure_Labeling_Guide.md`
- `docs/05_evaluation/Evaluation_Report_Template.md`

For engineering implementation work, read:

- `docs/02_specs/Minimal_Closed_Loop_Runtime_Spec.md`
- `docs/03_schemas/Schemas_Index.md`
- `docs/06_engineering/MVP_Architecture.md`
- `docs/06_engineering/Runtime_Module_Plan.md`
- `docs/06_engineering/Repository_Structure.md`
- `docs/06_engineering/Testing_Strategy.md`

## Current Research Direction

Prioritize the Stage 1 spine unless the user redirects:

```text
state -> plan -> action -> evidence -> verify -> commit / abort
```

The preferred first vertical domain is Document Ops because it has reversible
changes, inspectable diffs, clear provenance, and natural verifier targets.

Do not expand into full Context OS, long-term memory governance, irreversible
external actions, or broad agent safety claims before the minimal loop is
specified, schematized, benchmarked, and evaluated.

## Stage 0 Completion Gate

Stage 0 is complete only when the repository has locked these boundaries:

- canonical state is not execution trace
- tool log is not canonical state
- Evidence Packet is not explanation
- Episode Journal is not memory
- memory append is not learning
- Context OS is not long-context stuffing
- Verifier Runtime is not only final-answer judging
- rollback is not always possible

If asked whether Stage 0 is done, check for a concrete boundary-lock document and
a Context OS / Working Set Compiler note. If either is missing, answer that Stage
0 is not fully locked.

## Documentation Editing Rules

- Keep conceptual claims traceable to `Design_Theory.md` or
  `Validation_and_Refutation_Report.md`.
- When adding a new document, update the relevant index and traceability documents
  if the new document changes navigation or source-of-truth relationships.
- Keep `chatgpt_docs/` synchronized as the ChatGPT Project Knowledge export. When
  development or documentation changes affect current progress, governance,
  research direction, active gates, or any source file already mirrored there,
  update the corresponding copied file in `chatgpt_docs/` in the same turn. Keep
  the export at 25 files or fewer unless the user explicitly changes the limit.
- Preserve the difference between `Open Questions`, `Non-goals`, `Scope`, and
  normative requirements.
- Do not fill every document evenly. Advance the research spine:
  `02_specs -> 03_schemas -> 04_experiments -> 05_evaluation -> 06_engineering`.
- Mark unrun experiments as `Not yet run` or equivalent. Do not invent results.
- Prefer precise tables, schemas, and acceptance criteria over broad manifesto
  language in downstream layers.

## Boundary Rules To Enforce

- Theory can motivate specs, but cannot directly dictate code.
- Specs define behavior; schemas define data contracts.
- Experiment documents define tests of hypotheses, not proof.
- Evaluation documents define measurement, not subjective success.
- Engineering documents must cite specs/schemas/tests, not only theory.
- Side-effectful actions require evidence and verifier treatment before commit.
- Irreversible or external actions require escalation, compensation, or explicit
  non-goal treatment.
