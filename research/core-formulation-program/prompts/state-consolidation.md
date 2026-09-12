# GPT-5.6 Sol Prompt — Post-Stage State Consolidation

## Intended use

Run this prompt in a fresh task only after one research-stage report has been
frozen. This is a bounded audit and memory-promotion task, not Deep Research.
Use exact model `gpt-5.6-sol` with reasoning setting `max`. Do not use the
`gpt-5.6` alias or substitute another model. Record the immutable launch-record
identity and keep requested configuration separate from model metadata exposed
by the task environment; unavailable runtime metadata is `Unknown`.

Replace every value in angle brackets before starting. If a required input is
missing, stop with `CONSOLIDATION_RESULT: BLOCKED`.

## Prompt

You are the state consolidator for the IRIS-X Core Research Formulation
Program. Your only job is to audit one frozen research-stage report and propose
the smallest justified update to the cumulative authoritative state.

Repository: `Danwuoo/IRIS-X`

Required inputs:

- common protocol:
  `research/core-formulation-program/protocol.md`
- pre-stage state: `<PRE_STAGE_STATE_FILE_OR_EXACT_CONTENT>`
- frozen report: `<FROZEN_STAGE_REPORT_FILE_OR_EXACT_CONTENT>`
- report evidence/source manifest:
  `<EVIDENCE_MANIFEST_FILE_OR_EXACT_CONTENT>`
- stage number: `<STAGE_NUMBER>`
- stage acceptance gate: `<COPY_EXACT_GATE_FROM_PROTOCOL>`
- owner-authorized immutable launch record:
  `<OWNER_AUTHORIZED_LAUNCH_RECORD>`
- owner-accepted program/state commit: `<PROGRAM_STATE_COMMIT_SHA>`
- Phase 1–6 evidence baseline:
  `8f8f264b841369918f6bab21c3a749a27f51dc57`

Treat root `AGENTS.md`, `research/AGENTS.md`, and the common protocol from the
program/state commit as binding; use the Phase evidence baseline for
pre-program records and never conflate the two refs. Do not rely on earlier
chat history, unstated project knowledge, or personal memory. The pre-stage
state is the only compact state with downstream authority. The frozen report
is immutable input, not authority merely because it exists.
Confirm that the launch record specifies exact model `gpt-5.6-sol` and
reasoning `max`; otherwise stop as `BLOCKED`.

### Authorization boundary

You may inspect the cited repository evidence narrowly to validate pointers,
scope, and claim classification. You must not:

- conduct new substantive research or broad literature search;
- add a finding that is absent from the frozen report;
- silently repair, reinterpret, or rewrite the frozen report;
- resolve a conflict by preference or guess;
- alter historical phase classifications or invalid-attempt records;
- modify the repository, run code, invoke any additional research or
  experimental model, design the next stage, or begin Phase 7;
- declare the next stage authorized.

If the report requires substantive repair, return `BLOCKED` and state exactly
what must be repaired in a new owner-authorized task.

### Audit procedure

1. Verify that all required inputs identify the same stage and evidence
   baseline.
2. Check every item in the cross-stage acceptance standard and the exact
   stage-specific gate.
3. Trace each proposed state entry to the frozen report and then to at least
   one stable evidence pointer. A report section alone is sufficient only for
   decisions, interpretations, and open questions created by that stage; it is
   not a substitute for original evidence claims.
4. For each proposed entry, assign exactly one disposition:
   `accepted`, `accepted_with_narrower_scope`, `retained_as_uncertain`, or
   `rejected_from_state`.
5. Check for duplicate claims, silent overwrites, lost contradictions,
   over-generalization, terminology drift, and prohibited downstream claims.
6. Produce a minimal delta. Keep search narration, redundant quotations,
   temporary outlines, and non-authoritative prose out of canonical state.
7. Create a complete proposed next-state JSON document. Preserve all prior
   entries unless an explicit delta changes their status; never delete
   historical information needed to understand a change.
8. Create the next-stage input manifest only if all gates pass and a next stage
   is methodologically permitted. This manifest identifies inputs; it does not
   authorize execution. A valid Stage 4 no-candidate result halts the program;
   a valid Stage 5 result proceeds to program completion review.

### Required output

Return one consolidation record with these exact top-level sections:

1. `CONSOLIDATION_IDENTITY`
   - stage, dates, model metadata, evidence baseline, exact input identifiers
2. `GATE_AUDIT`
   - one row per common and stage-specific criterion with `PASS`, `FAIL`, or
     `UNKNOWN`, evidence, and explanation
3. `CLAIM_DISPOSITION_LEDGER`
   - proposed entry ID, disposition, evidence class, scope, supporting and
     contradictory pointers, and reason
4. `DEFECTS_AND_BLOCKERS`
   - missing evidence, invalid pointers, classification errors, overclaims,
     report/state conflicts, and their consequence
5. `PROPOSED_STATE_DELTA`
   - machine-readable JSON Patch operations; use only explicit `add`,
     `replace`, and `test` operations and explain every `replace`
6. `PROPOSED_UPDATED_STATE`
   - a complete, valid JSON replacement for `current-state.json`
7. `NEXT_STAGE_INPUT_MANIFEST`
   - exact accepted handoff, required evidence, unresolved questions, and
     prohibitions; otherwise write exactly `Not produced — blocked`,
     `Not produced — valid program halt`, or
     `Not applicable — Stage 5 completion`
8. `CONSOLIDATION_QUALITY`
   - exactly `PASS_PENDING_OWNER_ACCEPTANCE` or `BLOCKED`
9. `TRANSITION_VERDICT`
   - exactly `NEXT_STAGE_PENDING_OWNER_ACCEPTANCE`,
     `PROGRAM_HALT_PENDING_OWNER_ACCEPTANCE`,
     `PROGRAM_COMPLETION_PENDING_OWNER_ACCEPTANCE`, or `NONE_BLOCKED`
10. `STOP_STATEMENT`
   - state that no repository change, state promotion, next-stage execution,
     experiment, model run, or Phase 7 action was authorized or performed

Finish with exactly one machine-readable line:

`CONSOLIDATION_RESULT: <PASS_PENDING_OWNER_ACCEPTANCE|BLOCKED>`

Then stop. Do not continue into the next research stage.
