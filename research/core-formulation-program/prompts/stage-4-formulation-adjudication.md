# GPT-6 Deep Research Prompt — Stage 4: Formulation Adjudication

## Intended use

Run only after Stage 3 consolidation is owner-accepted. Use a fresh GPT-6 Deep
Research task with the highest owner-approved research and reasoning settings.
Do not substitute another model silently. Record model metadata only when
exposed by the task environment; otherwise write `Unknown`.

Replace every angle-bracket field before starting.

## Prompt

You are conducting Stage 4 of the IRIS-X Core Research Formulation Program.
Your task is to adjudicate the accepted candidate set under the frozen Stage 1
rubric and complete evidence state. You may select one primary formulation or
conclude that none passes. You are not writing the final thesis.

Repository: `Danwuoo/IRIS-X`

Required accepted inputs:

- common protocol:
  `research/core-formulation-program/protocol.md`
- current owner-accepted cumulative state:
  `<ACCEPTED_CURRENT_STATE_FILE_OR_EXACT_CONTENT>`
- accepted Stage 3 consolidation and handoff:
  `<ACCEPTED_STAGE_3_HANDOFF_FILE_OR_EXACT_CONTENT>`
- frozen Stage 1 rubric and veto conditions:
  `<ACCEPTED_STAGE_1_RUBRIC>`
- frozen Stage 3 candidate dossiers and evidence matrices:
  `<STAGE_3_REPORT_AND_MANIFESTS>`
- owner-accepted program/state commit: `<PROGRAM_STATE_COMMIT_SHA>`
- Phase 1–6 evidence baseline:
  `8f8f264b841369918f6bab21c3a749a27f51dc57`

Read root `AGENTS.md`, `research/AGENTS.md`, the common protocol, current state,
accepted handoff, rubric, candidate dossiers, and decisive original evidence.
Read pre-program records from the Phase evidence baseline and program records
from the program/state commit; never conflate them. Confirm owner acceptance
through Stage 3 and baseline consistency. If a required input is missing, stop
as `BLOCKED`. Do not rely on chat history.

### Exact question

Which candidate, if any, should become the primary IRIS-X core research
formulation under the Stage 1 rubric and the complete accepted evidence state?

### Adjudication constraints

1. Use the Stage 1 criteria, anchors, vetoes, and sensitivity method exactly as
   accepted. Do not add, remove, redefine, or reweight a criterion because it
   benefits a candidate. If the rubric is internally invalid or cannot
   adjudicate the accepted set, return `BLOCKED` and identify the required
   governance repair.
2. Reconstruct the strongest version of every candidate before critique. Apply
   equivalent evidentiary burden and analytical depth to each.
3. Red-team each candidate for circularity, construct collapse, unfalsifiability,
   triviality, novelty absorption, architecture leakage, measurement
   confounding, implementation dependence, scope creep, and conflict with
   negative evidence.
4. Assess explanatory coverage of Phase 1–6, corpus relationships, conflicts,
   unknowns, and failed/invalid attempts. Do not reward a candidate for merely
   restating all topics.
5. Test operationalizability and research tractability without designing the
   Stage 5 experimental program.
6. Perform rubric sensitivity and dominance analysis. Identify whether the
   outcome changes under every reasonable interpretation already permitted by
   the frozen anchors.
7. Compare one-primary-plus-subordinate structure against plural or null
   alternatives. A mechanism, assurance framework, architecture, or product
   objective cannot be selected in place of a research problem.
8. Use limited new source verification only to resolve a directly
   decision-relevant factual uncertainty. Do not reopen broad Stage 3 search or
   introduce a new candidate silently. If new evidence would materially change
   the candidate set, return `BLOCKED` for Stage 3 repair.

### Decision rule

Return exactly one of:

- `PRIMARY_FORMULATION_SELECTED` — one candidate clears all vetoes and has a
  defensible advantage under the frozen rubric. Assign other concepts only
  explicit subordinate, contextual, measurement, mechanism, or rejected roles.
- `NO_CANDIDATE_PASSES` — no candidate clears the frozen standard. State the
  evidence or reformulation needed before adjudication can resume.

Do not force selection to preserve project continuity. Record rejected
candidates, exact rejection reasons, and evidence-based reopening conditions.

### Required deliverable

Produce one complete report intended for:

`research/core-formulation-program/results/stage-4-formulation-adjudication.md`

Follow all 13 common report sections. Also include:

- rubric-integrity audit;
- equal-depth steelman and red-team dossiers;
- criterion-by-candidate matrix with evidence and uncertainty, not scores alone;
- veto, sensitivity, and dominance analyses;
- explicit selection or no-selection decision;
- role assignment for all non-primary concepts;
- rejection and reopening ledger;
- if selected, exact Stage 5 theory-formation manifest;
- minimal proposed cumulative-state delta.

Trace every judgment to the frozen rubric and accepted evidence. Explicitly
separate evidence, inference, methodological judgment, and owner decision.

### Acceptance gate and stop rule

Self-audit every Stage 4 criterion in section 8 of the common protocol and all
cross-stage criteria. `NO_CANDIDATE_PASSES` is a valid stage result eligible
for consolidation, but its consolidation must propose a program halt rather
than a Stage 5 manifest. Any later repair or reformulation requires separate
owner direction.

Do not produce a polished final thesis, research questions, hypotheses, or
experimental program. Do not run experiments, invoke experimental
models/providers, modify the repository, create Phase 7, or promote state.

Finish with exactly:

`FORMULATION_RESULT: <PRIMARY_FORMULATION_SELECTED|NO_CANDIDATE_PASSES|BLOCKED>`

`STAGE_RESULT: <CANDIDATE_FOR_CONSOLIDATION|BLOCKED>`

Then stop.
