# IRIS-X Five-Stage Core Research Formulation Protocol

## 1. Status and purpose

- **ID:** `protocol-irisx-core-formulation-v0`
- **Status:** decision / accepted research-program protocol
- **Phase 1–6 evidence baseline:**
  `8f8f264b841369918f6bab21c3a749a27f51dc57`
- **Program-definition baseline:** the owner-accepted commit containing this
  protocol; it must be recorded as an exact commit before Stage 1 starts
- **Scope:** research formulation, theory formation, and later experimental
  program design only
- **Execution state:** all five research stages are `not_started`

This protocol governs a thesis-scale synthesis intended to discover the most
defensible core research problem for IRIS-X. It responds to a structural gap:
IRIS-X has a substantial corpus, Phase 1–6 research and experimental evidence,
a provisional problem definition, and a provisional architecture, but it does
not yet have a final problem formulation and theory capable of organizing that
material without inheriting its assumptions.

The program is discovery-oriented. It may retain, narrow, reorganize, or reject
the current success–reliability–lifecycle-cost formulation. That formulation is
an important candidate, not a required conclusion.

This protocol does not authorize Phase 7, a new batch, an experiment, a model
or provider invocation, implementation, architecture expansion, or a final
product boundary. Executing a Deep Research prompt is a separate owner action.

## 2. Program decisions

The owner has selected the following structure:

1. five large research stages rather than one monolithic task;
2. one independent conversational task per stage;
3. GPT-6 as the lead research model for every stage;
4. a cumulative authoritative state rather than reliance on conversational
   memory;
5. a separate state-consolidation step after each research stage;
6. owner acceptance before state promotion or progression;
7. one eventual primary research formulation, unless Stage 4 finds that no
   candidate satisfies the frozen criteria.

Independence between research and consolidation is procedural, not an
independent scientific replication when both use the same model family.

## 3. Common authority rules

Every stage must obey root `AGENTS.md`, `research/AGENTS.md`, and the following
rules.

### 3.1 Evidence classes

Every substantive claim must be classified as exactly one of:

- `source_stated` — a claim made by a source, paper, project, or prior IRIS-X
  record;
- `directly_observed` — an outcome recorded by an admissible IRIS-X artifact;
- `inferred` — a synthesis or interpretation supported by stated evidence;
- `unknown` — the available evidence does not justify a determination.

Implementation existence, adoption, popularity, repeated terminology, or a
source author's confidence is not evidence that a mechanism is necessary or
effective for IRIS-X.

### 3.2 Uncertainty vocabulary

Use `Unknown`, `Unclear`, `Not established`, `Not evaluated`, and `Conflicting
evidence` without silently converting them to false, unsupported, or resolved.
If cumulative state and an original authority disagree, report the conflict and
prefer the original authority for the claim it directly governs. Do not
silently rewrite either record.

### 3.3 Historical preservation

Phase classifications, invalid attempts, negative results, superseded records,
and authority defects remain historical facts. Later repair or stronger
evidence may supplement them but cannot retrospectively reclassify them.

### 3.4 No guessing

The researcher may use only the supplied cumulative state, the frozen stage
inputs, and sources actually inspected. Missing information that could change a
conclusion must be retrieved or labeled unknown. The researcher must not invent
history, definitions, evidence, repository state, citations, or owner intent in
order to complete a report.

### 3.5 Original-source requirement

Navigation documents and prior handoffs may locate evidence but do not replace
it. Important claims must be checked against the primary paper, imported source
snapshot, experiment artifact, or authoritative IRIS-X research record that
supports them. Stable repository paths, source IDs, artifact IDs, versions, and
external URLs must be recorded where available.

### 3.6 Research-contribution boundary

For every proposed IRIS-X contribution, distinguish:

- the research phenomenon or decision problem;
- the hypothesized mechanism;
- the evaluation or assurance method;
- commodity or reusable substrate;
- implementation-specific realization.

No imported framework type or repository boundary becomes an IRIS-X
requirement by default.

## 4. Model and task topology

Each research stage is a fresh GPT-6 Deep Research task. The task must receive:

1. the stage prompt;
2. this protocol;
3. the current cumulative authoritative state;
4. the latest accepted prior-stage handoff, when one exists;
5. the exact owner-accepted program-definition commit and the declared Phase
   1–6 evidence baseline as separate authorities;
6. only the stage-specific additional inputs.

The Phase evidence baseline governs pre-program research records and artifacts.
The program-definition commit governs this protocol, prompts, and cumulative
state. A task must never assume they are the same commit. Later accepted state
promotions must also be identified by an immutable artifact or exact commit.

The task must not depend on earlier chat history or personal memory. The stage
prompt must be sufficiently complete before research begins; unanswered
requirements are handled as open questions or blockers, not filled by guess.

After the stage report is frozen, a separate consolidation task receives only:

- this protocol;
- the pre-stage cumulative state;
- the frozen stage report;
- its evidence/source manifest;
- the stage acceptance criteria.

The consolidator may verify cited evidence narrowly. It may not conduct the
next research stage, add substantive findings absent from the report, repair
the report silently, or advance the program.

## 5. Cumulative authoritative state

`state/current-state.json` is the canonical compact state. Full stage reports
are immutable historical detail; the state holds only information that can
affect downstream reasoning.

Each canonical claim has one entry containing its statement, evidence class,
status, scope, support, contradiction, assumptions, uncertainty, stage of
origin, last review, and downstream authority. State changes are explicit
deltas; no entry is silently overwritten.

Retain:

- supported and rejected claims;
- competing interpretations;
- negative and conflicting evidence;
- terminology decisions;
- scope and generalization limits;
- unresolved questions;
- downstream permissions and prohibitions;
- precise evidence pointers.

Exclude:

- search narration;
- tool logs;
- redundant quotations;
- discarded outlines;
- stylistic discussion;
- temporary to-do items;
- prose already represented by a canonical entry.

Absence from the canonical state never implies false. It implies that the item
has no downstream authority and must be retrieved or treated as unknown.

## 6. Required stage-report contract

Every stage report must contain:

1. stage identity, task identity, dates, model, and repository baseline;
2. the exact question answered;
3. inclusion, exclusion, and search boundaries;
4. source and artifact coverage ledger;
5. findings classified by evidence class;
6. supporting and contradictory evidence;
7. rejected interpretations and reasons;
8. uncertainty and missing evidence;
9. permitted downstream claims;
10. prohibited downstream claims;
11. proposed cumulative-state delta;
12. acceptance self-audit;
13. explicit stop statement.

The proposed delta has no authority until a separate consolidation accepts it.

## 7. Cross-stage acceptance standard

A stage can pass only when all of the following are true:

- every substantive conclusion has a stable evidence pointer;
- source-stated claims are not presented as direct observations;
- inference is separated from evidence;
- negative, invalid, and conflicting evidence remains visible;
- material missing evidence is labeled and its effect explained;
- scope and generalization boundaries are explicit;
- required coverage is complete or every omission is justified;
- the report does not perform a prohibited downstream decision;
- the report provides a minimal, auditable proposed state delta;
- the consolidator returns `PASS_PENDING_OWNER_ACCEPTANCE` and the owner
  accepts promotion.

Failure produces `BLOCKED`, not partial advancement. The stage may be repaired
under a separately authorized task while preserving the failed report.

### 7.1 Consolidation and promotion gate

A consolidation can return `PASS_PENDING_OWNER_ACCEPTANCE` only when:

- the frozen report passes every common and stage-specific criterion;
- every promoted claim traces to the report and stable original evidence;
- the delta preserves contradictions, uncertainty, history, and scope;
- no substantive finding absent from the report is introduced;
- the proposed updated state is valid, complete, and internally consistent;
- when progression is permitted, the next-stage manifest contains exact inputs
  and explicit prohibitions;
- a valid Stage 4 `NO_CANDIDATE_PASSES` result or Stage 5 completion records a
  halt/completion transition instead of fabricating a next-stage manifest.

The owner may accept, reject, or request repair. Only explicit acceptance makes
the proposed state authoritative. Acceptance does not itself run the next
stage. A failed or unaccepted consolidation leaves the pre-stage state current.

## 8. Five stages and specific gates

### Stage 1 — Research Constitution and Scope Lock

**Question:** What frozen scope, method, units of analysis, evidence policy,
candidate-evaluation criteria, and search boundaries permit the program to
discover rather than presuppose the core IRIS-X problem?

**Gate:** Pass only if the report:

- treats the current problem definition as a revisable candidate;
- distinguishes project motivation from research conclusion;
- enumerates plausible units of analysis without selecting one prematurely;
- freezes inclusion/exclusion rules and an evidence hierarchy;
- defines a candidate-formulation rubric covering explanatory compression,
  discrimination, falsifiability, operationalizability, contribution novelty,
  evidence fit, boundary clarity, and research-program generativity;
- defines external-search and saturation rules;
- produces the authoritative Stage 2 input manifest;
- states no final thesis, architecture, or winning formulation.

### Stage 2 — Evidence and Corpus Reconstruction

**Question:** What do Phase 1–6 and the registered corpus actually establish,
contradict, leave unknown, and assume?

**Gate:** Pass only if the report:

- reconstructs the Phase 1–6 evidence and decision lineage without rewriting
  historical classifications;
- covers all 13 registered sources and 7 registered paper artifacts, or records
  a concrete, decision-safe reason for any omission;
- distinguishes predecessor hypotheses, external source claims, direct IRIS-X
  observations, inference, and reusable substrate;
- records terminology collisions, incompatible assumptions, failure models,
  negative evidence, provenance limits, and transfer risks;
- identifies which claims are task-local, horizon-bound, or not established;
- produces an auditable evidence atlas rather than a source-by-source summary;
- does not select or rank a final core problem.

### Stage 3 — Problem Discovery and External Challenge

**Question:** Which distinct scientific problem families best explain the
internal evidence, cross-source conflicts, and gaps after targeted external
challenge?

**Gate:** Pass only if the report:

- constructs mechanism–context–outcome and claim–evidence relationships across
  sources rather than clustering keywords;
- conducts targeted external research for counter-literature, alternative
  framings, prior art, and missing fields, with primary sources preferred;
- audits corpus selection bias and novelty risk;
- produces three to five genuinely competing candidate formulations;
- gives each candidate a phenomenon, unit of analysis, boundary conditions,
  explanatory structure, predicted discriminations, potential contribution,
  falsifiers, and unresolved evidence needs;
- applies compression, discrimination, and removal tests;
- preserves candidates that conflict with current IRIS-X preferences when they
  satisfy the evidence;
- does not select a winner.

### Stage 4 — Formulation Adjudication

**Question:** Which candidate, if any, should become the primary IRIS-X core
research formulation under the Stage 1 rubric and the complete evidence state?

**Gate:** Pass only if the report:

- uses the frozen rubric without changing weights or criteria to favor a
  candidate;
- steelmans and red-teams every candidate;
- checks explanatory coverage of Phase evidence, source conflicts, unknowns,
  novelty, operationalization, falsifiability, and tractable research scope;
- records sensitivity to reasonable rubric interpretations;
- selects one primary formulation and assigns subordinate roles, or returns a
  justified `NO_CANDIDATE_PASSES` result;
- records rejected candidates and reopening conditions;
- distinguishes a research problem from a mechanism, evaluation framework,
  product goal, and architecture;
- does not present a polished final thesis or authorize experiments.

### Stage 5 — Theory and Experimental Program Formation

**Question:** How should the accepted formulation become a defensible theory,
thesis, research questions, hypotheses, and discriminating experimental
program?

**Gate:** Pass only if the report:

- states one primary thesis with explicit scope and contribution;
- defines the central constructs and their relationships without collapsing
  distinct outcomes unjustifiably;
- derives a small coherent set of research questions and directional,
  falsifiable hypotheses;
- maps every thesis component and hypothesis to supporting, conflicting, and
  missing evidence;
- identifies boundary conditions, alternative explanations, failure cases,
  and claims that remain prohibited;
- designs experiment families that discriminate among explanations rather than
  demonstrate implementation;
- separates measurement development, mechanism tests, generalization tests,
  and lifecycle/long-horizon evaluation;
- supplies ordering, prerequisites, stopping rules, and decision gates;
- separates original contribution from commodity substrate;
- produces an integrated thesis-scale synthesis and auditable appendices;
- authorizes no experiment, implementation, Phase 7, or architecture expansion.

## 9. Program completion

The program is complete only after Stage 5 consolidation is owner-accepted.
Completion establishes a research formulation and proposed experimental
program within their stated evidence boundaries. It does not establish that
the thesis is true, that the architecture is correct, or that any proposed
experiment is authorized.

## 10. Prompt-design basis

The stage prompts are intentionally complete and explicit. Official OpenAI
Deep Research guidance states that research expects a fully formed prompt and
does not itself supply missing context or a clarification step. The protocol
therefore freezes inputs, source policy, output contracts, and acceptance
criteria before each task:

- <https://developers.openai.com/api/docs/guides/deep-research>
