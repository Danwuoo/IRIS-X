# AGENTS.md

## Project

**IRIS-X — Reliable Agentic Intelligence Research Workspace**

IRIS-X is a clean research workspace for rethinking reliable, low-cost, task-specific agent systems.

The project is not intended to combine several existing repositories into a larger framework. The repositories collected here are research predecessors, external references, implementation examples, and experimental substrates. Their useful ideas, constraints, failure cases, and engineering patterns may inform IRIS-X, but IRIS-X should develop its own coherent architecture rather than inherit the structure of any one source project.

The repository has completed its initial research-preparation work, the Phase 4
evidence program, and the first post-Phase-4 synthesis. Current work is
owner-authorized Phase 5 provisional architecture development. Any architecture
produced in this stage remains provisional, revisable, and not production-stable.

## Current Objective

Extract the already-supported execution trust boundaries into the smallest
provisional IRIS-X-authored core, preserve the existing deterministic mutation
slice, and test interface reuse through one additional deterministic read-only
path under the current owner-authorized batch.

At this stage, the main goals are to:

- preserve the completed Phase 4 closure and its task-local evidence boundaries;
- map observed evidence to candidate constraints and minimal interfaces;
- separate IRIS-X research contribution from reusable commodity substrate;
- preserve uncertainty and define falsifiers for provisional choices;
- implement and validate only the minimum executable path needed to exercise
  the supported trust boundaries across exactly the authorized paths;
- keep unresolved mechanisms as extension points rather than silently making
  them core features.

Do **not** expand this stage into broad architecture implementation,
productionization, routing, cascades, workflow search, fine-tuning, or
architecture search without a new owner-authorized scope.

Do **not** prematurely define a final research question, final system architecture, or final product boundary.

## Working Direction

The broad direction is **Reliable Agentic Intelligence**, with particular interest in agent systems that can achieve strong performance on bounded or specific tasks without requiring unnecessarily expensive general-purpose intelligence.

Useful themes currently include:

- task-specific or specialist agents;
- minimum-sufficient capability rather than maximum capability;
- cost-aware execution and escalation;
- epistemic reliability and provenance;
- empirical measurement and evaluation;
- controlled actions and verifiable state changes;
- failure attribution and recovery;
- runtime instrumentation;
- agent, prompt, workflow, and configuration optimization;
- design-time specialization versus runtime escalation;
- long-running and stateful agent execution.

These are research directions, not yet normative architecture requirements.

## Research Philosophy

IRIS-X should distinguish between three kinds of material:

1. **Ideas worth absorbing**
   - conceptual principles;
   - useful abstractions;
   - experimental findings;
   - failure modes;
   - evaluation methods;
   - architectural constraints.

2. **Mechanisms worth reusing or adapting**
   - runtimes;
   - evaluators;
   - tracing systems;
   - optimization methods;
   - workflow engines;
   - tool interfaces;
   - persistence mechanisms.

3. **Assumptions that should not be inherited automatically**
   - repository boundaries;
   - framework-specific object models;
   - product-oriented abstractions;
   - benchmark-specific assumptions;
   - implementation choices that only exist for historical reasons.

An imported project is evidence and reference material, not authority over IRIS-X.

## Current Research Corpus

The repository currently includes material from several predecessor and external projects. Their approximate research roles are:

### Predecessor work

- `sources/predecessors/iris/`
  - internal-state reasoning;
  - cognitive architecture;
  - state representation;
  - learned control;
  - attribution and recovery.

- `sources/predecessors/eidos/`
  - epistemic governance;
  - provenance;
  - authority;
  - typed research records;
  - conflict and knowledge-state discipline.

- `sources/predecessors/spex/`
  - measurement;
  - evidence;
  - evaluation;
  - comparison boundaries;
  - adjudication;
  - empirical claim discipline.

- `sources/predecessors/vanta/`
  - controlled execution;
  - execution IR;
  - side-effect classification;
  - verification;
  - commit, rollback, replay, and recovery.

### External references

- `sources/external/prime_agent/`
  - stateful agent runtime;
  - tool and session lifecycle;
  - context handling;
  - recursive or long-running agent execution.

- `sources/external/prime_intellect_verifiers_v1/`
  - tasksets;
  - harnesses;
  - traces;
  - rollouts;
  - evaluation and reinforcement-learning interfaces.

- `sources/external/NeMo-Agent-Toolkit-develop/`
  - framework-agnostic instrumentation;
  - profiling;
  - observability;
  - evaluation;
  - optimization;
  - runtime performance mechanisms.

- `sources/external/dspy/`
  - declarative LM programs;
  - signatures;
  - modules;
  - optimizers;
  - program-level abstraction.

- `sources/external/gepa/`
  - reflective optimization;
  - trace-informed mutation;
  - Pareto-efficient search;
  - prompt, code, configuration, and agent-architecture optimization.

- `sources/external/aflow/`
  - automatic agentic workflow generation;
  - code-represented workflow search;
  - operator-based composition;
  - evaluation-guided optimization.

- `sources/external/agent_lightning/`
  - stated framework for reinforcement-learning training of agents;
  - retains real agent harnesses in its documented design.

- `sources/external/frugalgpt/`
  - stated techniques for budget-constrained LLM applications;
  - model-selection and cascade concepts relevant to cost/performance tradeoffs.

- `sources/external/routellm/`
  - stated serving and evaluation framework for LLM routers;
  - routes requests between stronger and cheaper models.

This list describes why the material is present. It does not imply that all of these systems will become dependencies of IRIS-X.

## Repository Preparation Rules

When organizing the repository or corpus, prefer research enablement over
feature development. During the current Phase 5 provisional architecture stage,
retain the same restraint: evidence-backed boundaries and minimal reversible
implementation are more valuable than framework breadth.

Good work includes:

- adding source manifests or provenance records;
- documenting where imported material came from;
- recording upstream repository and commit information;
- separating imported source from IRIS-X-authored research;
- creating indexes and navigation documents;
- identifying duplicate or overlapping concepts;
- writing comparative notes;
- creating terminology maps;
- cataloging schemas, interfaces, evaluators, runtimes, and optimization mechanisms;
- identifying obvious licensing or provenance concerns;
- documenting unresolved questions;
- creating small scripts that help inspect or index the corpus.

Avoid:

- implementing a new agent runtime;
- merging imported projects into one codebase;
- rewriting predecessor projects under a common abstraction;
- choosing a final framework stack;
- creating a final IRIS-X ontology too early;
- declaring a final research thesis without supporting analysis;
- turning exploratory notes into normative architecture;
- treating benchmark success as proof of general capability;
- treating an imported framework as the default architecture.

## Source Preservation

Material under `sources/` and `references/papers/` is preserved source material. Scoped rules are in `sources/AGENTS.md`.

Unless a task explicitly requires modifying an imported project:

- preserve imported files as faithfully as practical;
- avoid stylistic cleanup inside imported trees;
- avoid refactoring imported implementations;
- do not silently rewrite upstream documentation;
- keep IRIS-X-specific analysis outside imported source trees where possible.

If an imported source must be modified for repository hygiene, clearly distinguish the modification from upstream content.

## IRIS-X Authored Material

New IRIS-X material belongs in these editable zones:

```text
research/
experiments/
docs/
tools/
corpus/
irisx/
```

Use `research/AGENTS.md` for analysis rules and `experiments/AGENTS.md` for experiment discipline. `irisx/` is reserved for provisional IRIS-X-authored architecture code and is not a production-stable SDK or framework. Do not introduce another broad hierarchy without an immediate operational purpose.

Research documents should make their status clear when useful, for example:

- exploratory;
- comparative;
- hypothesis;
- experiment;
- result;
- decision;
- deprecated.

Do not introduce a heavy governance system merely because predecessor projects used one. Governance should be added only when the research workflow requires it.

## Research Method

When studying the corpus:

1. inspect the original source before summarizing it;
2. distinguish stated behavior from inferred intent;
3. preserve provenance;
4. record uncertainty explicitly;
5. compare mechanisms at the level of problems solved, not only API shape;
6. separate research contribution from commodity infrastructure;
7. look for incompatible assumptions, not only similarities;
8. identify failure cases and negative evidence;
9. avoid concluding that a concept belongs in IRIS-X merely because multiple frameworks implement it;
10. prefer falsifiable observations over architectural enthusiasm.

When evidence is incomplete, use labels such as:

- `Unknown`
- `Unclear`
- `Not established`
- `Not evaluated`
- `Conflicting evidence`

Do not fill gaps with confident guesses.

## Working Mental Model

A useful provisional distinction is:

```text
IRIS-X research contribution
        vs.
commodity / reusable substrate
```

Examples of likely substrate include:

- model-provider adapters;
- basic tool dispatch;
- session management;
- tracing transport;
- generic workflow execution;
- persistence infrastructure.

Examples of areas that may require original IRIS-X research include:

- what constitutes sufficient capability for a bounded task;
- what evidence justifies trusting an agent result;
- when a cheap specialist should stop, retry, escalate, or be redesigned;
- how failures should be attributed;
- how cost, reliability, and capability should be evaluated together;
- how observations, claims, evaluations, and actions should interact.

These orientation points are not independently normative research questions or architecture requirements. The current provisional project-level research problem is documented in `research/problem-definition.md` and remains revisable through evidence.

## Development Restraint

Do not optimize for visible code volume.

At the current stage, a well-structured comparison, source map, or research note can be more valuable than an implementation.

Before adding a new abstraction, ask:

- What concrete problem does it solve?
- Which existing source already addresses that problem?
- Is the proposed abstraction a research contribution or only integration glue?
- What evidence would show that the abstraction is necessary?
- Can the question be answered through a smaller experiment first?

Prefer small, reversible research steps.

## External Frameworks

Do not assume IRIS-X must directly depend on any imported external framework.

Prime Agent, NeMo Agent Toolkit, verifiers, DSPy, GEPA, AFlow, and similar projects should initially be treated as reference implementations or candidate substrates.

If later experimentation uses one of them, keep the boundary explicit enough that IRIS-X concepts do not become indistinguishable from framework-specific types.

## Near-Term Work

During the current Phase 5 batch, prioritize:

- evidence-to-constraint traceability;
- candidate interfaces with explicit trust and failure boundaries;
- separation of outcome, claims, evidence, acceptance, and execution state;
- local deterministic validation of the core boundary across the preserved
  mutation slice and exactly one read-only integration path;
- preservation checks and a durable unresolved-decision backlog.

Validate repository organization from the root:

```powershell
python tools\repository_check.py
```

Do not begin large implementation work merely because the source material is available.

## Decision Standard

Architecture decisions should emerge from research, comparison, and experiments.

A useful implementation in a predecessor repository is not automatically a requirement.

A popular external framework is not automatically the correct substrate.

A high benchmark score is not automatically evidence of reliability.

A low inference price is not automatically low lifecycle cost.

A successful tool execution is not automatically evidence that the underlying reasoning was correct.

IRIS-X should preserve these distinctions while the project is still forming.

## Status

**Current status: Phase 5 — provisional architecture development.**

The repository is not a stable architecture, framework, production runtime, or
product. Candidate architecture produced in this stage is provisional.

The current authorized batch extracts and validates core execution boundaries
only. It does not authorize broad implementation or productionization, and it
must not prematurely constrain what IRIS-X may become.
