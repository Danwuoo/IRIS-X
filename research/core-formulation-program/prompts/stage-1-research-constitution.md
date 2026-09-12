# GPT-5.6 Sol Research Prompt — Stage 1: Research Constitution and Scope Lock

## Intended use

Run this as the first independent Codex research task using exact model
`gpt-5.6-sol` with reasoning setting `max`. Do not use the `gpt-5.6` alias or
substitute another model. Record the immutable launch-record identity and keep
requested configuration separate from model metadata exposed by the task
environment; unavailable runtime metadata is `Unknown`.

## Prompt

You are conducting Stage 1 of the IRIS-X Core Research Formulation Program.
Your task is to establish the research constitution that later stages must
obey. You are not being asked to discover or select the final research problem.

Repository: `Danwuoo/IRIS-X`

Owner-accepted program-definition commit:
`<OWNER_ACCEPTED_PROGRAM_DEFINITION_COMMIT>`

Owner-accepted current-state pin commit:
`<OWNER_ACCEPTED_CURRENT_STATE_COMMIT>`

Owner-authorized immutable launch record:
`<OWNER_AUTHORIZED_LAUNCH_RECORD>`

Phase 1–6 evidence baseline:
`8f8f264b841369918f6bab21c3a749a27f51dc57`

Read these authorities before doing any analysis:

1. `AGENTS.md`
2. `research/AGENTS.md`
3. `research/core-formulation-program/protocol.md`
4. `research/core-formulation-program/state/current-state.json`
5. `research/problem-definition.md`
6. `research/phase-4-closure.md`
7. `docs/phase-5-architecture-state.md`
8. `docs/phase-6-research-state.md`
9. `research/phase-6-formal-closure-and-research-state.md`
10. `corpus/README.md`, `corpus/sources.yaml`, and
    `corpus/artifacts.yaml`

Read items 1–3 from the owner-accepted program-definition commit. Read item 4
from the owner-accepted current-state pin commit and confirm that its
`program_definition.accepted_commit` equals the exact program-definition
commit. Read the pre-program authorities and artifacts from the Phase evidence
baseline unless the protocol explicitly says otherwise. Never conflate these
refs. If either commit or the launch-record placeholder has not been replaced,
or the launch record does not specify exact model `gpt-5.6-sol` and reasoning
`max`, stop as `BLOCKED`.

Verify the program-definition commit, current-state pin commit, Phase evidence
baseline, frozen task configuration, and record inaccessible or changed
authorities.
Do not rely on earlier chat history. Treat the cumulative state as the only
compact downstream-authoritative memory, and verify important statements
against original authorities.

### Exact question

What frozen scope, method, units of analysis, evidence policy,
candidate-evaluation criteria, and search boundaries will allow the five-stage
program to discover rather than presuppose the core IRIS-X research problem?

### Required work

1. Separate owner motivation, current project framing, prior research finding,
   implementation substrate, and prospective scientific contribution.
2. Enumerate plausible units of analysis and explain the consequences of each.
   Do not choose one merely because it matches the current architecture.
3. Define explicit program inclusion and exclusion rules across:
   - Phase 1–6 records and experiment artifacts;
   - registered sources and papers;
   - external literature and neighboring fields;
   - implementation repositories, documentation, and community claims.
4. Define an evidence hierarchy and admissibility rules for source-stated,
   directly observed, inferred, and unknown claims. Cover negative results,
   invalid attempts, absence of evidence, source independence, replication,
   horizon limits, and provenance defects.
5. Operationally define the candidate-formulation rubric required by the
   common protocol: explanatory compression, discrimination, falsifiability,
   operationalizability, contribution novelty, evidence fit, boundary clarity,
   and research-program generativity. Specify scoring anchors, veto conditions,
   and how sensitivity will be tested. Do not score a candidate in Stage 1.
6. Define rules for targeted external search, primary-source preference,
   counterevidence, citation chaining, selection-bias auditing, source
   saturation, and justified stopping.
7. Define the exact analytical products Stage 2 and Stage 3 must construct,
   including claim–evidence and mechanism–context–outcome relationships.
8. Identify ambiguities that would materially alter the program. Resolve only
   those supported by authority; preserve the rest as explicit open questions
   or blockers.
9. Produce an exact Stage 2 input manifest, including repository paths and
   coverage obligations.

Methodological literature may be consulted only where it is necessary to
justify the constitution. Do not perform the substantive external problem
search assigned to Stage 3.

### Required deliverable

Produce one complete report intended for:

`research/core-formulation-program/results/stage-1-research-constitution.md`

Follow all 13 sections in the common stage-report contract. In addition, the
report must include:

- a scope matrix;
- alternative units-of-analysis table;
- evidence hierarchy and admissibility decision tree;
- fully operational candidate rubric with anchors and vetoes;
- external-search and saturation protocol;
- Stage 2 coverage and input manifest;
- proposed cumulative-state delta containing only constitution-level entries.

For every substantive claim, label its evidence class and provide a stable
repository path or primary external URL. Distinguish methodological choices
from empirical conclusions.

### Acceptance gate and stop rule

Self-audit every Stage 1 criterion in section 8 of the common protocol and
every cross-stage criterion. If any criterion is unmet, label the result
`BLOCKED` and explain the minimal repair. Do not paper over a missing authority
or owner decision.

Do not state a final thesis, select a winning problem formulation, freeze the
architecture, design or run an experiment, invoke an experimental model or
provider, modify the repository, create Phase 7, or promote state.

Finish with exactly:

`STAGE_RESULT: <CANDIDATE_FOR_CONSOLIDATION|BLOCKED>`

Then stop.
