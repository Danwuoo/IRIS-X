# IRIS-X Research Problem Definition

- **ID:** `problem-2026-08-26-unified-research-proposition`
- **Status:** exploratory — provisional project-level research problem definition
- **Scope:** Defines what IRIS-X is trying to study, what progress means, and how the research program may evolve. It does **not** define a final architecture, framework stack, product boundary, or implementation plan.
- **Repository phase:** research preparation / architecture research
- **Authority:** IRIS-X-authored synthesis. This document may guide research prioritization, but its mechanisms and sub-hypotheses remain revisable through evidence and experiments.

## 1. Purpose

IRIS-X exists to study how agentic systems can complete clearly defined tasks with strong empirical performance while using no more capability and cost than is necessary, and while remaining reliable over repeated and long-running operation.

The project is not primarily about maximizing model capability, benchmark rank, agent autonomy, or framework complexity. It is also not committed in advance to specialist agents, generalist agents, single-agent systems, multi-agent systems, a specific runtime, or a specific optimization method.

The central research concern is the relationship among:

1. **task success rate**;
2. **cost sufficiency**;
3. **long-term reliability**; and
4. **lifecycle cost-effectiveness**.

IRIS-X treats architecture as a downstream research result. Candidate mechanisms from predecessor work and external systems are hypotheses, evidence, reusable substrates, or experimental tools—not inherited requirements.

## 2. Unified Research Proposition

> **IRIS-X studies how to construct, evaluate, and continuously improve agentic systems for clearly bounded tasks so that they achieve a target task success rate at the lowest sufficient lifecycle cost, while maintaining reliability across repeated execution, state accumulation, environmental change, system updates, and failure recovery. The primary optimization objective is overall cost-effectiveness rather than maximum one-shot capability.**

A shorter form is:

> **How can we achieve sufficient and durable task success at the best lifecycle cost-effectiveness?**

This proposition is intentionally architecture-neutral.

## 3. Primary Research Variables

### 3.1 Task Success Rate

Task success rate is the primary outcome variable.

A task should have a sufficiently explicit contract to determine whether the requested outcome was actually achieved. For agentic tasks, success may require more than a plausible final answer; it may require correct external state changes, satisfied constraints, valid evidence, or successful verification.

Research should distinguish, where relevant:

- actual task success;
- partial success;
- failed execution;
- false or incorrectly believed success;
- verified success;
- success achieved only after retry or escalation.

A benchmark score may be evidence about task success for a defined benchmark task distribution, but it is not automatically evidence of broad capability or long-term reliability.

### 3.2 Cost Sufficiency

IRIS-X is not a pure cost-minimization project.

The relevant question is the minimum cost sufficient to meet a required level of task success and reliability.

A provisional form is:

\[
\min C_{\text{lifecycle}}
\]

subject to:

\[
S \geq S_{\min}
\]

and:

\[
R_{\text{long-term}} \geq R_{\min}
\]

where:

- \(S\) is measured task success;
- \(R_{\text{long-term}}\) is long-term reliability under the defined operating conditions;
- \(C_{\text{lifecycle}}\) is the relevant lifecycle cost.

The exact measurement definitions are **Not established** and should be developed empirically rather than assumed here.

Lifecycle cost may eventually include, depending on the research question:

- model inference cost;
- token or compute usage;
- tool and environment cost;
- verifier and evaluation cost;
- retry and recovery cost;
- escalation to stronger models or systems;
- latency and throughput costs;
- design-time search and optimization;
- training, fine-tuning, or specialization;
- maintenance and regression management;
- failure and remediation overhead.

Low inference price alone is not sufficient evidence of low lifecycle cost.

### 3.3 Long-Term Reliability

Long-term reliability is separate from one-shot task success.

IRIS-X should study whether measured success remains stable across conditions such as:

- repeated execution;
- long-running or stateful sessions;
- accumulated memory or state;
- tool and API changes;
- distribution or environmental shift;
- prompt, workflow, model, or configuration updates;
- recovery after failures;
- repeated optimization;
- regression and drift.

The exact unit of long-term reliability is currently **Unclear**. It may need to distinguish among:

- reliability of an agent instance;
- reliability of an agent configuration across independent episodes;
- reliability of the process used to produce, update, or specialize agents.

These should not be silently treated as equivalent.

### 3.4 Lifecycle Cost-Effectiveness

Cost-effectiveness is the primary optimization principle.

IRIS-X should not initially collapse task success, reliability, and cost into a single scalar score unless evidence shows that such a reduction is valid for a specific research setting.

A more appropriate early research representation is a trade-off surface or Pareto frontier over:

\[
(\text{Task Success},\ \text{Long-Term Reliability},\ \text{Lifecycle Cost})
\]

This allows different system configurations to be compared without assuming in advance that one architecture family is correct.

## 4. Core Research Question

The current primary research question is:

> **For a clearly defined task distribution and operating environment, what is the minimum-sufficient agentic system configuration that can meet a target task success rate and long-term reliability requirement at the best lifecycle cost-effectiveness?**

This is a project-level research question, not a commitment to a specific mechanism.

Candidate system configurations may include, but are not limited to:

- strong general-purpose models;
- cheaper general-purpose models;
- task-specific or specialist models;
- prompt- or program-specialized agents;
- tool-augmented systems;
- verifier-augmented systems;
- model routers and cascades;
- workflow-optimized systems;
- stateful or persistent runtimes;
- hybrid systems;
- single-agent or multi-agent configurations.

No configuration class is privileged by definition.

## 5. Supporting Research Questions

The unified problem decomposes into several supporting questions.

### RQ1 — Sufficient capability

What capabilities are actually necessary for a given bounded task distribution, and which capabilities are expensive redundancy?

### RQ2 — Evidence of success

What evidence is sufficient to justify treating an agent outcome as successful, and how should false success, unverified success, and partially verified success be distinguished?

### RQ3 — Cost accounting

Which costs materially determine lifecycle cost-effectiveness, and how should design-time, runtime, verification, retry, escalation, maintenance, and failure costs be amortized and compared?

### RQ4 — Long-term reliability

Which failure modes emerge only under repeated, stateful, long-running, shifted, or updated operation, and how should long-term reliability be measured without reducing it to one-shot benchmark accuracy?

### RQ5 — Failure attribution and intervention

When performance is insufficient, how can we determine whether the appropriate response is to:

- retry;
- repair context or state;
- invoke stronger verification;
- escalate capability;
- change tools;
- reconfigure the workflow;
- re-specialize or re-optimize;
- retrain;
- redesign the system?

### RQ6 — Design-time specialization versus runtime capability

Under what conditions can design-time specialization, prompt/program optimization, workflow search, routing, or other structured mechanisms substitute for more expensive general-purpose runtime intelligence?

### RQ7 — Reliability of the specialization process

Can IRIS-X eventually develop a repeatable methodology that, given a new task, reliably produces and maintains a cost-effective agentic configuration rather than depending on ad hoc manual agent engineering?

This is a long-term research direction, not a current assumption.

## 6. Architecture-Neutrality and Predecessor Hypotheses

IRIS-X must not treat predecessor architecture decisions as inherited constraints.

In particular, concepts such as:

- single-trunk cognition;
- canonical State IR;
- learned routing or gating;
- explicit failure attribution;
- execution IR;
- transactional action semantics;
- typed epistemic records;
- particular verifier structures;

should be treated as **predecessor hypotheses or candidate mechanisms** unless independently supported by IRIS-X research.

A predecessor hypothesis may carry useful historical evidence, engineering experience, negative results, or rationale. It therefore should not be discarded merely because it is non-normative.

However:

> **historical authority is not evidence.**

A mechanism should survive in IRIS-X because comparison and experiments support it, not because a predecessor document called it an invariant, constitution, or non-negotiable principle.

Hypotheses that were coupled in predecessor systems should also be separable where possible. For example, single-trunk cognition, canonical state representation, learned control, and explicit failure attribution should not automatically be accepted or rejected as one indivisible package.

## 7. Specialist Agents as a Strategic Hypothesis

Low-cost, task-specific or specialist agents are an important strategic direction for IRIS-X, but they are not the project definition.

A specialist is valuable only if specialization improves the relevant success–reliability–cost trade-off.

IRIS-X should therefore allow evidence to show that, for some tasks:

- specialist systems are more cost-effective;
- routing or escalation is more cost-effective;
- generalist systems with tools are more cost-effective;
- hybrid systems are more cost-effective;
- specialization costs are not justified.

The research program succeeds by finding the better empirical frontier, not by proving that specialist agents must win.

## 8. Evaluation Principle

Comparisons should be made against explicit task contracts, operating conditions, and resource envelopes.

Where possible, research should distinguish:

- model-level capability;
- system-level capability;
- task scaffolding;
- tool access;
- verification;
- memory or persistence;
- routing or escalation;
- design-time optimization;
- runtime inference.

An observed gain should not be attributed to specialized model capability when it was produced by system-level mechanisms.

Similarly:

- evaluator reward is not automatically evidence of reliability;
- benchmark success is not automatically broad capability;
- successful tool execution is not automatically correct reasoning;
- verifier approval is not automatically empirical truth;
- lower per-call inference price is not automatically lower lifecycle cost.

## 9. Research Program Evolution

IRIS-X should evolve by reducing uncertainty rather than by prematurely filling an architecture roadmap.

### Phase 0 — Research Preparation

Current phase.

Goals:

- organize and preserve the corpus;
- establish provenance;
- make sources inspectable;
- identify high-value evidence paths;
- maintain clean boundaries between imported material and IRIS-X-authored research.

### Phase 1 — Comparative Problem Decomposition

Map overlapping concepts, incompatible assumptions, terminology collisions, failure models, and research gaps across the existing corpus.

Outputs should emphasize:

- comparative notes;
- contradiction maps;
- terminology maps;
- evidence-status maps;
- open questions.

### Phase 2 — IRIS-X Research Hypotheses

Form explicit, falsifiable IRIS-X hypotheses.

Examples may concern:

- sufficient capability;
- cost-aware escalation;
- verification;
- failure attribution;
- specialization;
- state and memory;
- optimization;
- controlled execution.

Candidate mechanisms remain hypotheses at this stage.

### Phase 3 — Discriminating Experiments

Design experiments that distinguish competing hypotheses rather than merely demonstrating that a prototype can run.

Experiments should measure relevant combinations of:

- task success;
- cost;
- reliability;
- failure distribution;
- recovery;
- generalization or shift where relevant.

### Phase 4 — Architectural Synthesis

Only after hypotheses survive meaningful comparison and experiments should IRIS-X begin converting supported constraints into architectural requirements.

Architecture is therefore a synthesis of research results, not the starting point of the project.

### Phase 5 — Reusable System and Substrate Decisions

Determine which mechanisms should be:

- reused as commodity substrate;
- adapted behind explicit boundaries;
- implemented as IRIS-X-specific research contributions;
- rejected or retained only as references.

IRIS-X does not need to become a monolithic framework.

### Phase 6 — Specialization and Optimization Science

A mature IRIS-X research program may investigate whether agent construction itself can become systematic:

> Given a new task distribution, can we identify, generate, evaluate, and maintain a minimum-sufficient agentic configuration with predictable cost-effectiveness and reliability?

This is a long-term direction and remains **Not established**.

## 10. Evidence Basis

This document is an IRIS-X-authored synthesis based on the current repository operating rules and the existing research corpus.

Relevant current repository evidence includes:

- root `AGENTS.md`: research-preparation status, minimum-sufficient capability direction, cost-aware execution, epistemic reliability, empirical evaluation, failure attribution, runtime instrumentation, optimization, and the distinction between research contribution and reusable substrate;
- `research/AGENTS.md`: requirement to distinguish source-stated, directly observed, inferred, and unknown claims;
- `docs/repository-layout.md`: separation of preserved imported material from IRIS-X-authored research;
- `research/templates/research-note.md`: current lightweight research-note discipline.

Predecessor and external materials motivate candidate research dimensions, but this document does not promote their architecture claims into IRIS-X requirements.

## 11. Current Uncertainties

The following are intentionally unresolved:

- **Not established:** the final mathematical definition of lifecycle cost-effectiveness.
- **Not established:** the minimum task-contract formalism required for valid comparisons.
- **Unclear:** the appropriate unit and horizon for long-term reliability.
- **Not established:** whether one reliability metric can apply across different task families.
- **Not evaluated:** whether specialist agents provide the best lifecycle cost-effectiveness across the task classes IRIS-X will study.
- **Not evaluated:** whether design-time optimization can systematically substitute for expensive runtime capability.
- **Not established:** which predecessor mechanisms will survive IRIS-X experiments.
- **Not established:** the final system architecture or runtime substrate.

These uncertainties are research targets, not gaps to be filled by assumption.

## 12. Decision Boundary

This document establishes a **provisional unified research problem**, not a final architecture or immutable thesis.

A future change should be justified when evidence shows that one or more of the following are wrong or insufficient:

- task success rate is not the appropriate primary outcome;
- lifecycle cost sufficiency is not a meaningful constraint;
- long-term reliability cannot be operationalized usefully;
- cost-effectiveness is not the correct top-level optimization principle;
- the bounded-task framing excludes an empirically important class of agentic intelligence research.

Until such evidence exists, this problem definition can serve as the common orientation for IRIS-X comparative research, hypotheses, experiments, and later architectural synthesis.
