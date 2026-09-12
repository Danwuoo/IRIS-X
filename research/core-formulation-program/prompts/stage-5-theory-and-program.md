# GPT-5.6 Sol Research Prompt — Stage 5: Theory and Experimental Program Formation

## Intended use

Run only after Stage 4 selected a primary formulation and its consolidation was
accepted by the owner. Use a fresh Codex research task with exact model
`gpt-5.6-sol` and Codex app-native reasoning setting `ultra`. Do not use the
`gpt-5.6` alias, substitute another model, or silently downgrade to `max`.
Record the immutable launch-record identity and keep requested configuration
separate from model metadata exposed by the task environment; unavailable
runtime metadata is `Unknown`.

Replace every angle-bracket field before starting.

## Prompt

You are conducting Stage 5 of the IRIS-X Core Research Formulation Program.
Your task is to transform the accepted primary formulation into a defensible,
thesis-scale theory and a proposed discriminating experimental program. You are
designing research; you are not authorizing or executing it.

Repository: `Danwuoo/IRIS-X`

Required accepted inputs:

- common protocol:
  `research/core-formulation-program/protocol.md`
- current owner-accepted cumulative state:
  `<ACCEPTED_CURRENT_STATE_FILE_OR_EXACT_CONTENT>`
- accepted Stage 4 consolidation and handoff:
  `<ACCEPTED_STAGE_4_HANDOFF_FILE_OR_EXACT_CONTENT>`
- accepted primary formulation, subordinate-role map, rejection ledger, and
  evidence matrices: `<STAGE_4_REPORT_AND_MANIFESTS>`
- owner-authorized immutable launch record:
  `<OWNER_AUTHORIZED_LAUNCH_RECORD>`
- owner-accepted program/state commit: `<PROGRAM_STATE_COMMIT_SHA>`
- Phase 1–6 evidence baseline:
  `8f8f264b841369918f6bab21c3a749a27f51dc57`

Read root `AGENTS.md`, `research/AGENTS.md`, the common protocol, current state,
accepted handoff, Stage 4 decision, and all original authorities needed for
decisive evidence. Read pre-program records from the Phase evidence baseline
and program records from the program/state commit; never conflate them. Confirm
that Stage 4 selected a primary formulation and the owner accepted
consolidation. If not, stop as `BLOCKED`. Confirm that the launch record
specifies exact model `gpt-5.6-sol` and Codex reasoning `ultra`; otherwise stop
as `BLOCKED`. Do not rely on earlier chat history.

### Exact question

How should the accepted formulation become a defensible theory, thesis,
research questions, hypotheses, and discriminating experimental program?

### Required theory work

1. State one primary thesis that answers the accepted problem formulation and
   makes a bounded original contribution. Do not claim the thesis is already
   established by evidence used to formulate it.
2. Define every central construct operationally. Separate success,
   reliability, lifecycle cost, assurance, coordination, attribution, recovery,
   and other constructs unless accepted evidence justifies a relationship or
   unification.
3. Specify units and levels of analysis, actors, mechanisms, contexts,
   outcomes, time horizons, scope, and boundary conditions.
4. Present the explanatory or causal structure. Classify every claim using the
   common evidence classes, and separately mark each proposed link's relation
   status as supported, contradicted, assumed, or unknown. Identify plausible
   rival structures.
5. Derive a small coherent set of research questions. Each must be necessary
   to assess the thesis and not merely request implementation description.
6. Derive directional, falsifiable hypotheses with units, treatments or
   contrasts where applicable, outcomes, predicted direction, conditions, and
   explicit falsifiers. Do not convert unknowns into hypotheses without a
   theoretical reason.
7. Map each thesis component, question, and hypothesis to supporting,
   conflicting, and missing evidence plus prohibited generalizations.
8. State the original IRIS-X contribution separately from commodity substrate,
   implementation choices, evaluation infrastructure, and prior art.

### Required experimental-program work

Design experiment families that discriminate among the accepted theory and
its strongest alternatives. Separate:

- construct and measurement validation;
- mechanism and causal-discrimination tests;
- task/model/provider/context generalization tests;
- lifecycle, long-horizon, drift, intervention-cost, and recovery evaluation;
- negative controls, ablations, adversarial cases, and provenance checks.

For each proposed family specify the decision it informs, hypotheses and
rivals, minimum admissible evidence, unit/sample/scenario logic, independent
variables or contrasts, outcomes and measurement validity, confounds,
baselines, controls, falsifiers, stopping rules, failure interpretation,
generalization limits, prerequisites, and evidence/compute dependencies.

Order the program by information value and dependency, not implementation
convenience. Define gates for continue, revise, abandon, or reopen formulation.
Do not invent power values, sample sizes, costs, model access, or feasibility;
state what must be estimated later. Treat the existing architecture as one
possible apparatus unless the accepted theory requires otherwise.

Limited external verification is allowed to close a source or method gap
identified in the accepted Stage 4 manifest. Do not silently reopen or replace
the accepted formulation. If decisive evidence invalidates it, return
`BLOCKED` with a formulation-reopening recommendation.

### Required deliverable

Produce one complete integrated report intended for:

`research/core-formulation-program/results/stage-5-theory-and-program.md`

Follow all 13 common report sections. Also include:

- primary thesis and contribution statement;
- construct glossary and theory diagram/table;
- research-question and hypothesis hierarchy;
- thesis/RQ/hypothesis evidence-traceability matrix;
- alternative-explanation and falsification ledger;
- boundary-condition and prohibited-claim register;
- ordered experimental-program families and dependency map;
- measurement, decision-gate, stopping, and reopening rules;
- explicit reusable-substrate versus original-contribution boundary;
- thesis-scale synthesis plus auditable evidence and method appendices;
- minimal proposed final cumulative-state delta.

Every statement must preserve the common evidence classes. The report must say
what is proposed, what prior evidence supports, what remains unknown, and what
future evidence could falsify the thesis.

### Acceptance gate and stop rule

Self-audit every Stage 5 criterion in section 8 of the common protocol and all
cross-stage criteria. Return `BLOCKED` if any central construct lacks an
operational path, hypotheses cannot discriminate rivals, or the proposed
program is merely an implementation roadmap.

Do not execute the proposed experimental program, conduct additional empirical
research, run code or experiments, invoke experimental models/providers,
modify the repository, declare the thesis empirically true, create Phase 7, or
promote state. Even a passing report remains a candidate for separate
consolidation and owner acceptance.

Finish with exactly:

`STAGE_RESULT: <CANDIDATE_FOR_CONSOLIDATION|BLOCKED>`

Then stop.
