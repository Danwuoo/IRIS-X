# TEMP — Pre-Synthesis Readiness for a Single GPT-5.6 Sol Ultra Research Session

Status: **Proposed / not started**
Date: **2026-09-12 Asia/Taipei**
Repository: **Danwuoo/IRIS-X**
Planning baseline observed while authoring: **`dabda8a2fbe3adb820535043161fd27c7787608e`**
Execution model for this plan: **GPT-5.6 Sol / High reasoning**
Target downstream research mode: **one separately authorized GPT-5.6 Sol / Ultra session**
Model/provider calls authorized by this plan: **none**
Research status: **readiness preparation only; foundational synthesis is not started or authorized**
Architecture authority: **none**
Phase authority: **this is not Phase 7 and does not create or select a next phase**

## 1. Purpose

IRIS-X has completed Phase 6 and now contains a substantial heterogeneous corpus:
predecessor systems, external repositories, preserved papers, Phase 1–6 research
notes, direct experiment evidence, architecture syntheses, closure records, and
provisional project-level formulations. The next substantive research may be a
paper-scale foundational synthesis intended to discover and defend the core
IRIS-X research formulation.

The owner intends that substantive synthesis to be completed in **one GPT-5.6
Sol Ultra session**, not through a multi-stage research program. Therefore the
work authorized by this plan is only the preparation required to make that one
session research-efficient, provenance-safe, and resistant to premature
formulation lock-in.

The readiness work must convert the repository from a corpus that is primarily
preserved and navigable into a corpus that is **synthesis-ready**, while avoiding
substantive conclusions that belong to the later Ultra session.

The core design rule is:

> **Precompute navigation, evidence boundaries, terminology exposure, and
> validation — not the final interpretation.**

The Sol High task governed by this plan must reduce retrieval and bookkeeping
burden without replacing primary sources with lossy summaries or deciding the
research thesis in advance.

## 2. Current repository facts that constrain this plan

The Sol High task must verify these directly rather than relying on this plan
alone.

### 2.1 Phase 6 is closed

Current root authority states that Phase 6 is complete, the architecture remains
provisional, zero of eight deferred capability gates are triggered by current
direct evidence, and no next experiment or phase is authorized.

The readiness task must preserve that state. It must not convert unresolved
`unknown` or `insufficient_or_ambiguous` predicates into mechanism requirements.

### 2.2 A provisional project-level problem already exists

`research/problem-definition.md` is an important IRIS-X-authored prior
formulation, not a blank slate and not final authority. It must be represented
as a candidate/prior formulation that the later Ultra synthesis may retain,
revise, split, or reject.

The readiness task must not silently promote its success–reliability–cost
formulation into the final thesis.

### 2.3 The corpus already has preservation infrastructure

`corpus/sources.yaml`, `corpus/artifacts.yaml`, `corpus/PROVENANCE.md`, and
repository tooling already provide source identity, paper identity, provenance,
snapshots, and integrity checks. The readiness work should reuse these stable
IDs and authorities instead of creating a second source registry.

### 2.4 Research claim discipline already exists

`research/AGENTS.md` requires substantive claims to distinguish source-stated,
directly observed, inferred, and unknown material and to preserve uncertainty
labels. The readiness package must retain that discipline at machine-readable
and human-readable levels.

### 2.5 The former core-formulation program was intentionally removed

The latest planning baseline commit is `research: remove core formulation
program`. The removed design used a five-stage Sol research program with
cumulative state and independent stage prompts. This plan must **not recreate
that topology under a new name**.

The target architecture here is deliberately different:

```text
one bounded Sol High readiness task
        -> owner review
        -> one separately authorized Sol Ultra foundational-synthesis session
```

No intermediate formulation stages, model-led state promotions, or hidden
multi-session research program should be introduced.

## 3. Exact readiness question

> **What minimum deterministic research infrastructure, source/evidence
> interfaces, analytical scaffolds, validation rules, and downstream session
> contract are required so that one later GPT-5.6 Sol Ultra session can perform
> a defensible foundational IRIS-X synthesis from primary evidence without
> spending most of its context on repository archaeology or inheriting a
> preselected thesis?**

This is a readiness question, not the substantive IRIS-X research question.

## 4. Non-goals and hard prohibitions

The Sol High task must not:

- state or select the final IRIS-X research thesis;
- decide the final core research problem;
- freeze final Research Questions or hypotheses;
- run a new experiment;
- launch any model/provider execution from the repository;
- create Phase 7 or a Phase 7 plan;
- modify `sources/` or `references/papers/`;
- modify historical Phase 1–6 evidence to make it easier to synthesize;
- reinterpret a historical failure as success or vice versa;
- choose a final architecture, framework, provider, runtime, router, workflow,
  optimizer, persistence layer, or recovery mechanism;
- build a literature review that substitutes for primary-source access;
- create a giant prose summary intended to be the later Ultra session's main
  evidence;
- score or select a winning candidate formulation;
- conduct substantive new external literature research beyond narrowly checking
  readiness-method facts that are genuinely necessary;
- recreate the removed five-stage `core-formulation-program` or any equivalent
  staged model-research pipeline.

If any proposed readiness artifact would require substantive adjudication of the
core thesis, leave the field neutral, expose alternatives, or mark it `Unknown`
/ `Not established`.

## 5. Design principles

### 5.1 Primary-source retrievability over summary compression

The readiness layer is an index and analytical interface, not an epistemic
replacement for original sources. Every material entry must point back to stable
repository paths, stable source IDs, artifact IDs, or exact Phase records.

### 5.2 Claim-space over file-space

The later Ultra session should be able to navigate by constructs, assumptions,
claims, mechanisms, evidence type, tensions, and boundary conditions rather than
only by repository chronology.

### 5.3 Evidence class must remain visible

At minimum distinguish:

- `source_stated`;
- `directly_observed`;
- `inferred`;
- `unknown` / unavailable;
- historical governance/decision authority where relevant.

Do not flatten an IRIS-X synthesis into direct evidence.

### 5.4 Preserve contradictions and negative evidence

A readiness package that only records agreement is defective. It must expose
incompatible assumptions, failed attempts, invalid runs, historical defects,
negative evidence, and generalization limits when they are decision-relevant.

### 5.5 No false source independence

A paper and its implementation, a result and its later closure summary, or a
predecessor idea and an IRIS-X synthesis derived from it must not be counted as
independent evidence without justification.

### 5.6 Minimal duplication

Reuse `corpus/` stable identities. Do not create parallel source manifests that
can drift. New readiness records should reference existing registries and add
synthesis-specific metadata only.

### 5.7 Context-budget awareness

The readiness package should make selective retrieval possible. It must not
assume the entire repository will be injected into the later Ultra context at
once.

## 6. Required repository review before design

Before creating readiness artifacts, the Sol High task must inspect enough of
the repository to justify the schema and coverage rules.

At minimum inspect directly:

### Governance and current state

- `AGENTS.md`
- `research/AGENTS.md`
- `experiments/AGENTS.md`
- `README.md`
- `research/README.md`
- `corpus/README.md`
- `corpus/PROVENANCE.md`
- `corpus/sources.yaml`
- `corpus/artifacts.yaml`
- `docs/phase-6-research-state.md`
- `research/phase-6-formal-closure-and-research-state.md`
- `docs/phase-6-formal-closure-handoff.md`

### Current formulation and architecture syntheses

- `research/problem-definition.md`
- `research/candidate-mechanism-hypotheses.md`
- `research/phase-4-closure.md`
- `research/post-phase-4-architecture-synthesis.md`
- `research/phase-5-architecture-consolidation.md`
- `research/phase-5-capability-trigger-review.md`
- `docs/phase-5-architecture-state.md`

### Phase 6 evidence chain

Inspect the controlling/result/handoff records and direct evidence authorities
needed to reconstruct the Phase 6 Batch 1, Batch 2, Batch 3, and post-Batch-3
authority-repair chain. Do not rely only on the closure note.

### Earlier direct evidence

Identify and inspect the direct experiment/result authorities necessary to
support the Phase 4 and Phase 5 claims that the readiness ledger will expose.
Where an exact claim depends on a terminal record or experiment artifact, record
that direct path rather than citing only a later synthesis.

### Registered predecessors and external references

For every stable source in `corpus/sources.yaml`, inspect at least the registered
high-value entry points sufficient to determine:

- intended research role;
- unit(s) of analysis;
- primary objective(s);
- key mechanism classes;
- major assumptions;
- relevant failure/evaluation model;
- what IRIS-X must not infer merely from the source's existence.

Do not attempt exhaustive code summarization.

### Preserved papers

For every artifact in `corpus/artifacts.yaml`, identify its relationship to a
registered source or research theme and provide retrieval metadata. Do not
pretend a paper has been deeply interpreted if the task environment cannot
reliably inspect its contents. Mark access limitations explicitly.

## 7. Required readiness package

Create a compact directory:

```text
research/pre-synthesis-readiness/
```

This directory has an immediate operational purpose and therefore does not
create a new general research hierarchy.

### 7.1 `README.md` — readiness entry point

Must explain:

- purpose and non-goals;
- frozen execution baseline;
- exact artifact set;
- how the later Ultra session should retrieve primary evidence;
- authority order;
- what has and has not been interpreted;
- readiness validation command;
- explicit statement that the foundational synthesis is not started.

### 7.2 `baseline-manifest.json`

Machine-readable snapshot of the exact readiness baseline and critical
identities. At minimum include:

- repository and branch;
- execution-start commit;
- plan path and plan blob/hash if available;
- root/research/experiments AGENTS identities;
- `corpus/sources.yaml` identity;
- `corpus/artifacts.yaml` identity;
- current problem-definition identity;
- authoritative Phase 4/5/6 closure/current-state identities;
- registered source/artifact counts;
- generation timestamp;
- schema version.

Do not claim immutable upstream model behavior or external web content.

### 7.3 `source-interface.yaml`

This is **not** a new source registry. Each row references a stable source or
artifact already registered in `corpus/` and adds only synthesis-facing fields,
for example:

- stable ID;
- source class (`predecessor`, `external_reference`, `paper`, `irisx_record`);
- primary retrieval paths;
- research role;
- plausible unit(s) of analysis;
- objective/optimization target;
- mechanism family tags;
- evaluation/ground-truth style;
- time horizon;
- cost boundary if explicit;
- high-value assumptions;
- known relation to other sources;
- independence caveat;
- non-authority warning;
- access/coverage status.

Entries must distinguish `source_stated` metadata from readiness inference.

### 7.4 `phase-evidence-ledger.yaml`

Create claim-level entries for the durable Phase 1–6 evidence needed by the
later synthesis. Each entry should contain, where applicable:

- stable local claim ID;
- phase/batch;
- evidence class;
- concise bounded claim;
- direct primary authority paths;
- later synthesis paths, separately labeled;
- tested task/configuration/horizon;
- supported scope;
- explicit non-conclusions;
- counterevidence or historical invalid attempts;
- uncertainty labels;
- falsifier or next discriminating evidence if already established by authority;
- relationship to provisional architecture or deferred gates.

The ledger must not turn inferred candidate constraints into direct observations.

### 7.5 `construct-map.yaml`

Expose terminology without prematurely normalizing it. Include concepts such as
capability, sufficient capability, task success, reliability, evidence,
verification, provenance, authority, failure, attribution, state, recovery,
specialization, routing/allocation, workflow, optimization, cost, lifecycle
cost, and any additional constructs discovered during inspection.

For each construct record:

- source-specific meanings;
- unit of analysis;
- measurement/operationalization when stated;
- related but non-equivalent terms;
- collisions or overloaded usage;
- unresolved normalization question;
- primary references.

A canonical definition is optional and must remain absent where not justified.

### 7.6 `assumption-tension-matrix.md`

Human-readable cross-source matrix organized by analytical tension rather than
project name. At minimum examine:

- unit of analysis;
- one-shot vs repeated/lifecycle horizon;
- deterministic oracle vs learned/model/human judgment;
- model capability vs system/configuration capability;
- design-time optimization vs runtime adaptation/escalation;
- task-specific specialization vs general capability;
- inference cost vs lifecycle cost;
- stateful vs stateless execution;
- successful execution vs justified belief in success;
- reward/benchmark performance vs reliability;
- prevention vs detection/recovery;
- local immutable evidence vs remote/mutable provenance.

Each row must state whether the tension is a true contradiction, a scope
difference, a terminology collision, or `Unclear`.

### 7.7 `claim-evidence-index.jsonl`

A retrieval-oriented index, not a completed theory. Each line should map one
important claim or candidate proposition to:

- claim ID;
- normalized short proposition;
- claim status (`supported_bounded`, `inferred`, `contested`, `unknown`,
  `not_evaluated`, or another explicitly defined status);
- supporting authority paths;
- challenging/counterevidence paths;
- dependent claims;
- scope/boundary tags;
- source-independence notes;
- retrieval priority.

Do not include a `winner` field or final thesis score.

### 7.8 `candidate-formulation-template.md`

Provide a neutral structure the later Ultra session must use for each competing
formulation. Require at least:

- explanandum;
- unit of analysis;
- core constructs;
- causal/mechanistic structure;
- why the problem is scientifically nontrivial;
- relationship to success/reliability/cost;
- relationship to Phase 1–6 evidence;
- source support;
- conflicting evidence;
- explanatory compression;
- discriminating predictions;
- falsifiers;
- operationalization path;
- generalization boundary;
- novelty/contribution claim;
- unresolved assumptions;
- strongest alternative explanation.

The readiness task must not populate this template with a preferred formulation.

### 7.9 `ultra-session-contract.md`

Define the downstream one-session research protocol. It should require a single
continuous Ultra session to perform sequential analytical passes while retaining
one context, rather than separate model runs.

Recommended passes:

1. authority and baseline verification;
2. evidence reconstruction using the readiness indexes plus primary-source
   spot checks;
3. construct and tension reconstruction;
4. candidate explanandum discovery;
5. generation of multiple genuinely competing formulations;
6. adversarial comparison and counterevidence search;
7. selection, synthesis, or justified no-single-formulation result;
8. derivation of thesis/RQs/hypotheses only after adjudication;
9. derivation of experimental program from discriminating hypotheses;
10. final provenance, uncertainty, scope, and anti-literature-review audit.

The contract must specify that important claims be rechecked against primary
source paths and that readiness metadata is not itself treated as scientific
authority.

### 7.10 `ultra-session-prompt.md`

Create the complete copy-paste prompt for the later separately authorized
GPT-5.6 Sol Ultra session. It must reference the readiness package and instruct
the model to perform the actual foundational synthesis in one session.

The prompt must **not be executed** under this plan.

It must explicitly permit the Ultra session to challenge
`research/problem-definition.md`, permit a justified plural/no-unified-thesis
outcome, and require competing formulations before final selection.

### 7.11 `readiness-report.md`

Record what was actually reviewed and built, including:

- exact execution baseline;
- coverage summary;
- sources/artifacts/Phase records represented;
- known access limitations;
- deliberate information not pre-synthesized;
- validation results;
- remaining readiness blockers;
- whether the package is `READY_FOR_OWNER_REVIEW` or `BLOCKED`.

`READY_FOR_OWNER_REVIEW` does not authorize the Ultra session.

## 8. Validation tooling

Add one narrow deterministic validator under:

```text
tools/validate_pre_synthesis_readiness.py
```

It should validate structure and referential integrity, not scientific truth.
At minimum check:

- required readiness files exist;
- JSON/YAML/JSONL parse successfully using dependencies already acceptable in
  the repository, or use standard-library formats where practical;
- stable source IDs resolve against `corpus/sources.yaml`;
- artifact IDs resolve against `corpus/artifacts.yaml`;
- referenced repository paths exist at the validated tree;
- required evidence-class/status fields use declared vocabularies;
- no final-thesis/winner field appears in readiness schemas where prohibited;
- baseline manifest identities match actual files/tree where deterministically
  checkable;
- source-interface coverage is complete for registered sources and papers;
- the Ultra prompt references the required readiness authorities;
- the package explicitly states synthesis is not started/authorized.

Do not build a new general database, embedding pipeline, RAG service, vector
store, or framework. The validator should remain small and inspectable.

## 9. Context and retrieval policy for the later Ultra session

The readiness package should encode retrieval tiers rather than flattening all
material into one prompt.

Suggested tiers:

```text
Tier 0 — governance and current-state authority
Tier 1 — direct IRIS-X Phase evidence and terminal/result authorities
Tier 2 — IRIS-X syntheses and provisional formulations
Tier 3 — predecessor conceptual material
Tier 4 — external papers/projects and implementation references
Tier 5 — low-level implementation details, loaded only when a claim depends on them
```

Tier number is retrieval priority, not epistemic truth rank. Direct evidence may
still be highly local; external primary literature may be stronger for a general
scientific claim than an IRIS-X inference.

The later Ultra session must selectively expand primary material when a claim is
important, disputed, or formulation-defining.

## 10. Coverage standard

Readiness is not complete merely because every source ID appears once.

Coverage is sufficient when:

1. all registered sources and papers have retrieval/interface entries;
2. all material Phase 1–6 claims expected to affect foundational formulation
   have bounded claim-level ledger entries;
3. known negative/invalid evidence relevant to those claims is not omitted;
4. major construct collisions are represented;
5. major cross-source tensions are represented;
6. source-dependence relationships prevent obvious double-counting;
7. the later Ultra session can trace every high-priority readiness claim back to
   primary paths without repository archaeology;
8. uninspected or inaccessible material is visibly marked rather than silently
   summarized.

Do not maximize row count. Prefer high-value, traceable entries.

## 11. Anti-bias requirements

The Sol High readiness task must actively guard against these failure modes:

### 11.1 Confirmation bias toward the current problem definition

Treat `research/problem-definition.md` as a prior candidate, not the objective.
Do not organize every artifact only around success–reliability–cost if the
corpus exposes other plausible explananda.

### 11.2 Architecture hindsight bias

Do not infer that Phase 5's provisional architecture identifies the research
problem merely because it operationalizes evidence-backed constraints.

### 11.3 Source-count voting

Multiple frameworks implementing routing, optimization, persistence, or
verification do not make those mechanisms IRIS-X requirements.

### 11.4 Summary authority inflation

A closure note that summarizes direct evidence does not become independent
support for the same claim.

### 11.5 Positive-result bias

Preserve failed provider/configuration attempts, historical authority defects,
false accepts, unverified-success distinctions, and other negative evidence when
relevant to a claim.

### 11.6 Premature unification

The downstream Ultra session must remain allowed to conclude that two or more
research programs should stay distinct if a single formulation would erase
important causal or evaluative distinctions.

## 12. Validation and repository hygiene

The Sol High task must run only local deterministic validation appropriate to
repository editing. At minimum:

1. validate the readiness package with the new validator;
2. run `python tools/repository_check.py`;
3. run targeted existing tests if modifications to shared tooling require them;
4. inspect the final diff for accidental changes to preserved source/evidence;
5. confirm `sources/` and `references/papers/` are unchanged;
6. confirm no experiment/model-run artifact was created;
7. report any pre-existing historical failure separately from new failures.

No model/provider call is needed or authorized for this readiness task.

## 13. Commit and lifecycle discipline

The readiness implementation should use normal semantic commits and preserve
history. A reasonable lifecycle is:

```text
verify execution baseline and instructions
-> create readiness skeleton and schemas
-> populate source/evidence/construct/tension indexes from direct inspection
-> create downstream Ultra contract and prompt
-> add deterministic validator
-> run validation and repository checks
-> record readiness report
-> finalize owner-facing handoff
```

Do not amend, rebase, squash historical commits, reset shared history, or
force-push.

This TEMP plan remains proposed until the owner executes the Sol High prompt.
If the implementation later uses normal IRIS-X plan retirement practice, retire
it only after readiness artifacts, validation, and handoff are complete.

## 14. Acceptance criteria

The readiness task may report `READY_FOR_OWNER_REVIEW` only if all of the
following hold:

- one exact execution baseline is recorded;
- the package references all registered sources and papers;
- Phase 1–6 formulation-relevant evidence is represented at bounded claim level;
- direct evidence and later synthesis are distinguishable;
- major terminology collisions and assumption tensions are exposed;
- negative evidence and uncertainty are visible;
- source-dependence/double-counting risks are recorded;
- no final thesis or winning formulation has been selected;
- a neutral competing-formulation template exists;
- a single-session Ultra research contract exists;
- a complete Ultra prompt exists but was not executed;
- deterministic validation passes or every failure is explicitly blocking;
- preserved source/evidence trees remain unchanged;
- no Phase 7, experiment, or model run has been started.

If a material primary authority cannot be located, an important ledger claim
cannot be traced, or the package would require invented interpretation to appear
complete, report `BLOCKED` rather than filling the gap.

## 15. Stop boundary

Stop after the readiness package, validator, validation results, readiness
report, and owner-facing handoff are complete.

Do not start the Ultra synthesis.

Do not produce a final IRIS-X thesis.

Do not select Phase 7.

Do not launch any model/provider run.

The owner must separately authorize use of `ultra-session-prompt.md` in a later
GPT-5.6 Sol Ultra session.

---

# Appendix A — Copy-paste GPT-5.6 Sol High prompt

Use this prompt in one GPT-5.6 Sol session with **High** reasoning to implement
the readiness plan above. The task is repository research preparation, not the
foundational synthesis itself.

```text
You are preparing the IRIS-X repository for one later, separately authorized,
single-session foundational research synthesis using GPT-5.6 Sol Ultra.

Repository:
Danwuoo/IRIS-X

Controlling plan:
docs/plans/TEMP_PRE_SYNTHESIS_READINESS_FOR_SINGLE_ULTRA_SESSION.md

Use GPT-5.6 Sol with High reasoning for this task.

This task is PRE-SYNTHESIS READINESS ONLY.
It is not Phase 7, not the foundational synthesis, not an experiment, and not
authorization for any model/provider run from the repository.

Your objective is to perform the complete repository review and implementation
specified by the controlling plan so that a later single Ultra session can
spend its reasoning budget on theory formation and evidence adjudication rather
than repository archaeology.

Hard boundaries:

- Do not state or select the final IRIS-X research thesis.
- Do not decide the final core research problem.
- Do not freeze final RQs or hypotheses.
- Do not run an experiment.
- Do not launch a model/provider execution.
- Do not create Phase 7.
- Do not modify sources/ or references/papers/.
- Do not rewrite historical Phase 1–6 evidence.
- Do not select a final architecture or framework.
- Do not recreate the removed multi-stage core-formulation program.
- Do not replace primary sources with a giant prose summary.

First:

1. Fetch/pull current main normally and record the exact clean execution-start
   commit. The planning baseline written in the plan is historical context, not
   a requirement that main still equal that SHA.
2. Reload and obey AGENTS.md plus scoped research/ and experiments/
   instructions.
3. Inspect the latest commit history around
   `research: remove core formulation program` so you understand what was
   intentionally removed and do not recreate it.
4. Read the complete controlling plan before making changes.
5. Review the required governance, corpus, current-state, Phase 4–6 synthesis,
   direct evidence, registered sources, and paper registries specified by the
   plan. Use original authorities rather than summaries alone whenever a
   readiness entry makes a substantive claim.

Then implement exactly one compact readiness package at:

research/pre-synthesis-readiness/

Required files:

- README.md
- baseline-manifest.json
- source-interface.yaml
- phase-evidence-ledger.yaml
- construct-map.yaml
- assumption-tension-matrix.md
- claim-evidence-index.jsonl
- candidate-formulation-template.md
- ultra-session-contract.md
- ultra-session-prompt.md
- readiness-report.md

Also add:

tools/validate_pre_synthesis_readiness.py

Important methodological rule:

Precompute navigation, provenance, evidence boundaries, construct collisions,
tensions, and retrieval structure — NOT the final interpretation.

Treat research/problem-definition.md as a provisional prior formulation. The
later Ultra session must remain free to retain, revise, split, or reject it.
Treat Phase 5 architecture as provisional evidence-backed operationalization,
not proof of the underlying research thesis. Preserve Phase 6's bounded result
and its unknown intervention predicates exactly.

For readiness metadata and ledgers:

- distinguish source-stated, directly observed, inferred, and unknown claims;
- point important claims to direct primary repository authorities;
- separately identify later synthesis/closure paths;
- preserve explicit non-conclusions and uncertainty;
- include relevant negative evidence and invalid historical attempts;
- record source-dependence and double-counting risks;
- expose unit-of-analysis, horizon, ground-truth/evaluation, cost-boundary, and
  intervention-point differences across sources;
- do not force canonical definitions where evidence does not justify them;
- do not create a winner/final-thesis field.

For the later Ultra session design:

- it must be one continuous Ultra session, not a staged multi-run program;
- require multiple genuinely competing formulations before selection;
- require adversarial comparison and counterevidence;
- allow a justified plural/no-single-unified-thesis outcome;
- require important formulation-defining claims to be checked against primary
  sources;
- derive thesis/RQs/hypotheses only after candidate adjudication;
- derive the experimental program from discriminating hypotheses, not from a
  feature roadmap;
- finish with an anti-literature-review audit and explicit scope/uncertainty
  boundaries.

The readiness validator must check structural and referential integrity only,
not scientific truth. Reuse corpus stable IDs; do not create a parallel source
registry or a RAG/vector-store system.

Validate at minimum:

- python tools/validate_pre_synthesis_readiness.py
- python tools/repository_check.py
- any targeted existing tests required by shared-tool changes
- final diff/preservation checks confirming sources/ and references/papers/
  remain unchanged and no experiment/model-run artifact was created

Use normal semantic commits. Do not rewrite history or force-push.

Final deliverable:

1. completed readiness package;
2. deterministic validator;
3. readiness-report.md with exact coverage, limitations, validation results,
   and execution baseline;
4. complete but UNEXECUTED research/pre-synthesis-readiness/ultra-session-prompt.md;
5. concise owner-facing report listing changed files, commits, validation, any
   blockers, and whether the package is READY_FOR_OWNER_REVIEW or BLOCKED.

READY_FOR_OWNER_REVIEW does not authorize the later Ultra session.

Stop immediately after readiness completion and reporting. Do not execute the
Ultra prompt and do not begin foundational synthesis.
```
