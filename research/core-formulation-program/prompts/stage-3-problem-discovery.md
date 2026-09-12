# GPT-5.6 Sol Research Prompt — Stage 3: Problem Discovery and External Challenge

## Intended use

Run only after Stage 2 consolidation is owner-accepted. Use a fresh Codex
research task with exact model `gpt-5.6-sol` and Codex app-native reasoning
setting `ultra`. This is the program's main external-research stage; allocate
depth to opposing literature and primary-source verification, not repetitive
summaries. Do not use the `gpt-5.6` alias, substitute another model, or silently
downgrade to `max`. Record the immutable launch-record identity and keep
requested configuration separate from model metadata exposed by the task
environment; unavailable runtime metadata is `Unknown`.

Replace every angle-bracket field before starting.

## Prompt

You are conducting Stage 3 of the IRIS-X Core Research Formulation Program.
Your task is to discover genuinely competing scientific problem formulations
that can explain the reconstructed evidence and survive targeted external
challenge. You must not select a winner.

Repository: `Danwuoo/IRIS-X`

Required accepted inputs:

- common protocol:
  `research/core-formulation-program/protocol.md`
- current owner-accepted cumulative state:
  `<ACCEPTED_CURRENT_STATE_FILE_OR_EXACT_CONTENT>`
- accepted Stage 2 consolidation and handoff:
  `<ACCEPTED_STAGE_2_HANDOFF_FILE_OR_EXACT_CONTENT>`
- frozen Stage 2 evidence atlas and manifests:
  `<STAGE_2_REPORT_AND_MANIFESTS>`
- owner-authorized immutable launch record:
  `<OWNER_AUTHORIZED_LAUNCH_RECORD>`
- owner-accepted program/state commit: `<PROGRAM_STATE_COMMIT_SHA>`
- Phase 1–6 evidence baseline:
  `8f8f264b841369918f6bab21c3a749a27f51dc57`

Read root `AGENTS.md`, `research/AGENTS.md`, the common protocol, current state,
accepted handoff, and original evidence authorities needed to verify Stage 2
claims. Read pre-program records from the Phase evidence baseline and program
records from the program/state commit; never conflate them. Confirm Stage 2
owner acceptance and baseline consistency. If either is absent, stop as
`BLOCKED`. Confirm that the launch record specifies exact model
`gpt-5.6-sol` and Codex reasoning `ultra`; otherwise stop as `BLOCKED`. Do not
rely on earlier chat history.

### Exact question

Which distinct scientific problem families best explain the internal evidence,
cross-source conflicts, and gaps after targeted external challenge?

### Required research strategy

1. Start from the Stage 2 claim–evidence and mechanism–context–outcome maps,
   not from the current architecture or preferred terminology.
2. Identify the deepest recurring tensions and anomalies. Distinguish a
   scientific problem from a product goal, architecture, mechanism,
   measurement method, assurance process, or general aspiration.
3. Search adjacent and competing research fields for:
   - alternative explanations and problem decompositions;
   - negative results and boundary conditions;
   - prior art that may absorb the apparent IRIS-X contribution;
   - measurement and construct-validity critiques;
   - evidence that the observed tension is contingent, already solved, or
     ill-posed.
4. Prefer primary papers, standards, official technical reports, and original
   project documentation. Use reviews to orient search, then trace decisive
   claims to primary sources. Record query families, databases/sites, dates,
   inclusion/exclusion decisions, and citation chains.
5. Deliberately seek disconfirming sources for every emerging candidate.
   Include fields and terminology that disagree with IRIS-X's present framing.
6. Audit selection bias in the registered corpus, including source genealogy,
   shared assumptions, duplicated evidence, ecosystem concentration, recency,
   missing communities, and publication/benchmark bias.
7. Stop external search only under the Stage 1 saturation rule. If saturation
   is not reached within the task boundary, state the uncovered regions and
   return `BLOCKED` when they could change the candidate set.

### Candidate construction

Produce three to five genuinely competing problem formulations. Do not create
cosmetic variants of one thesis. For each candidate specify:

- the phenomenon requiring explanation or intervention;
- the unit of analysis and relevant actors;
- scope and boundary conditions;
- causal or explanatory structure, including mechanism only where supported;
- how it organizes Phase 1–6 evidence and cross-source conflict;
- predicted discriminations against rival candidates;
- possible original contribution and existing prior art;
- operationalization path without committing to an experiment;
- falsifiers and observations that would make it unproductive;
- supporting, conflicting, and missing evidence;
- strongest steelman and strongest objection.

Apply these tests without selecting a winner:

- **compression test:** what otherwise disconnected evidence does it explain?
- **discrimination test:** what observation would distinguish it from rivals?
- **removal test:** what part of IRIS-X becomes unnecessary if it is false?
- **novelty test:** is the claimed gap already covered by prior work?
- **boundary test:** when should the formulation not apply?

Retain a candidate that conflicts with current IRIS-X preferences if it meets
the evidence and method. Include a serious null or deflationary formulation
when evidence supports the possibility that no unified IRIS-X-specific problem
is needed.

### Required deliverable

Produce one complete report intended for:

`research/core-formulation-program/results/stage-3-problem-discovery.md`

Follow all 13 common report sections. Also include:

- external-search ledger and saturation audit;
- corpus selection-bias and novelty audit;
- updated cross-source relationship synthesis;
- three to five candidate formulation dossiers;
- candidate-to-evidence and candidate-to-rival matrices;
- unresolved discriminating evidence needs;
- exact Stage 4 adjudication manifest;
- minimal proposed cumulative-state delta.

Every claim about external work must cite a primary URL, persistent identifier,
or exact official record when available. Separate source claims from your
inferences. Do not use citation count, popularity, or repeated vocabulary as a
proxy for truth or necessity.

### Acceptance gate and stop rule

Self-audit every Stage 3 criterion in section 8 of the common protocol and all
cross-stage criteria. Return `BLOCKED` if the external challenge is materially
one-sided, the candidates are not genuinely distinct, or a search gap could
change the candidate set.

Do not select or rank a winner, conduct Stage 4, write the final thesis, design
or run experiments, invoke experimental models/providers, modify the
repository, create Phase 7, or promote state.

Finish with exactly:

`STAGE_RESULT: <CANDIDATE_FOR_CONSOLIDATION|BLOCKED>`

Then stop.
