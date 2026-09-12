# GPT-5.6 Sol Research Prompt — Stage 2: Evidence and Corpus Reconstruction

## Intended use

Run only after Stage 1 consolidation has been accepted by the owner. Use a
fresh Codex research task with exact model `gpt-5.6-sol` and Codex app-native
reasoning setting `ultra`. Do not use the `gpt-5.6` alias, substitute another
model, or silently downgrade to `max`. Record the immutable launch-record
identity and keep requested configuration separate from model metadata exposed
by the task environment; unavailable runtime metadata is `Unknown`.

Replace every angle-bracket field with the accepted artifact before starting.

## Prompt

You are conducting Stage 2 of the IRIS-X Core Research Formulation Program.
Your task is to reconstruct what the existing IRIS-X evidence and registered
corpus actually establish. You are not being asked to choose a core problem.

Repository: `Danwuoo/IRIS-X`

Required accepted inputs:

- common protocol:
  `research/core-formulation-program/protocol.md`
- current owner-accepted cumulative state:
  `<ACCEPTED_CURRENT_STATE_FILE_OR_EXACT_CONTENT>`
- accepted Stage 1 consolidation and handoff:
  `<ACCEPTED_STAGE_1_HANDOFF_FILE_OR_EXACT_CONTENT>`
- owner-authorized immutable launch record:
  `<OWNER_AUTHORIZED_LAUNCH_RECORD>`
- owner-accepted program/state commit: `<PROGRAM_STATE_COMMIT_SHA>`
- Phase 1–6 evidence baseline:
  `8f8f264b841369918f6bab21c3a749a27f51dc57`

First read root `AGENTS.md`, `research/AGENTS.md`, the common protocol, the
accepted current state, and the accepted Stage 1 handoff from the program/state
commit. Read pre-program records from the Phase evidence baseline. Confirm that
Stage 1 is owner-accepted and that the handoff defines the Stage 2 input
manifest. If not, stop as `BLOCKED`. Never conflate the two refs and do not rely
on earlier chat history. Confirm that the launch record specifies exact model
`gpt-5.6-sol` and Codex reasoning `ultra`; otherwise stop as `BLOCKED`.

### Exact question

What do Phase 1–6 and the registered corpus actually establish, contradict,
leave unknown, and assume?

### Required coverage

Inspect the original authorities named by the Stage 1 manifest, including:

- all Phase 1–6 research, closure, handoff, architecture, and experiment
  records required by that manifest;
- all experiment artifacts required to verify direct observations;
- all 13 entries in `corpus/sources.yaml`, their available source records, and
  the original files needed to evaluate material claims without requiring an
  indiscriminate line-by-line audit of every imported repository;
- all 7 registered paper artifacts in `corpus/artifacts.yaml` and their
  available paper records;
- the provisional `research/problem-definition.md` as a historical candidate,
  not a conclusion.

If registry counts differ at the accepted baseline, report the discrepancy and
use the accepted manifest; do not silently broaden or shrink the corpus. A
missing item may be omitted only with an exact reason and an analysis showing
why the omission cannot distort downstream formulation.

### Required work

1. Reconstruct the Phase 1–6 evidence and decision lineage. Preserve original
   verdicts, invalid attempts, negative results, authority defects, horizon
   limits, and reopening conditions.
2. Build a canonical claim–evidence atlas. For each material claim record:
   claimant, evidence class, phenomenon, unit/context, mechanism if claimed,
   outcome, scope, support, contradiction, assumptions, uncertainty, provenance,
   and downstream authority.
3. Build cross-source relationship maps based on claims, mechanisms, contexts,
   outcomes, and failure models—not keyword similarity or source order.
4. Identify agreement, apparent agreement caused by terminology collision,
   direct conflict, compatible complementarity, incompatible assumptions, and
   untested transfer from external systems to IRIS-X.
5. Separate predecessor hypotheses, external claims, direct IRIS-X
   observations, IRIS-X inferences, evaluation methods, and commodity substrate.
6. Test every broad interpretation against task-locality, scenario bounds,
   evaluation horizon, model/provider dependence, sample limitations,
   provenance, and alternative explanations.
7. Record underdetermination: where the same evidence supports multiple
   interpretations, preserve all material alternatives.
8. Produce a terminology and construct-collision ledger plus an unresolved
   evidence-gap ledger for Stage 3.

This is corpus-first reconstruction. Do not conduct broad new external
literature discovery. Narrow external access is allowed only to verify identity,
version, provenance, or an original primary-source claim already registered;
record every such use.

### Required deliverable

Produce one complete report intended for:

`research/core-formulation-program/results/stage-2-evidence-reconstruction.md`

Follow all 13 sections in the common stage-report contract. Also include:

- Phase 1–6 evidence and decision lineage;
- complete source/artifact coverage ledger;
- canonical claim–evidence atlas;
- cross-source conflict and compatibility matrix;
- mechanism–context–outcome map;
- terminology/construct-collision ledger;
- evidence limits, transfer-risk, and underdetermination ledger;
- exact Stage 3 challenge questions and input manifest;
- minimal proposed cumulative-state delta.

For every substantive entry, label the evidence class and cite stable source
IDs, artifact IDs, repository paths, versions, or primary URLs. A navigation
document may locate evidence but cannot replace the original authority.

### Acceptance gate and stop rule

Self-audit every Stage 2 criterion in section 8 of the common protocol and all
cross-stage criteria. If full required coverage is not achieved and omissions
are not decision-safe, return `BLOCKED`.

Do not rank or select a core problem, conduct Stage 3, state a final thesis,
design or run experiments, invoke experimental models/providers, modify the
repository, create Phase 7, or promote state.

Finish with exactly:

`STAGE_RESULT: <CANDIDATE_FOR_CONSOLIDATION|BLOCKED>`

Then stop.
