# IRIS-X Research Problem Definition

## 1. Document Status and Scope

- **ID:** `problem-2026-08-26-unified-research-proposition`
- **Status:** exploratory — provisional project-level research problem definition
- **Scope:** Defines what IRIS-X is trying to study and what progress means. It does **not** define a final architecture, framework stack, product boundary, implementation plan, or fixed research roadmap.
- **Repository phase:** research preparation / architecture research
- **Authority:** IRIS-X-authored synthesis. This document may guide research prioritization, but its mechanisms and sub-hypotheses remain revisable through evidence and experiments.

## 2. Purpose

IRIS-X exists to study how agentic systems can complete clearly defined tasks with strong empirical performance while using no more capability and cost than is necessary, and while remaining reliable over repeated and long-running operation.

The project is not primarily about maximizing model capability, benchmark rank, agent autonomy, or framework complexity. It is also not committed in advance to specialist agents, generalist agents, single-agent systems, multi-agent systems, a specific runtime, or a specific optimization method.

The central research concern is the relationship among:

1. **task success rate**;
2. **long-term reliability**; and
3. **lifecycle cost**.

**Cost sufficiency is a decision criterion, not a fourth outcome dimension:** subject to defined task-success and reliability requirements, IRIS-X seeks configurations that do not purchase unnecessary capability or incur unnecessary lifecycle cost. Where those requirements are not yet specified or justified, research should characterize the empirical success–reliability–cost trade-off rather than assume a single scalar objective.

IRIS-X treats architecture as a downstream research result. Candidate mechanisms from predecessor work and external systems are hypotheses, evidence, reusable substrates, or experimental tools—not inherited requirements.

## 3. Unified Research Proposition

> **IRIS-X studies how to construct, evaluate, and improve agentic systems for clearly bounded task distributions so that they meet defined task-success and long-term-reliability requirements while minimizing lifecycle cost under explicit operating conditions and resource boundaries. The objective is not maximum one-shot capability, but the empirical success–reliability–cost trade-off and, where requirements are specified, the minimum lifecycle cost at which they can be satisfied.**

A shorter form is:

> **Which agentic system configurations can satisfy defined task-success and long-term-reliability requirements, and at what lifecycle cost?**

This proposition is intentionally architecture-neutral.

## 4. Primary Research Dimensions

### 4.1 Task Success Rate

Task success rate is a primary outcome variable.

A task should have a sufficiently explicit contract to determine whether the requested outcome was actually achieved. For agentic tasks, success may require more than a plausible final answer; it may require correct external state changes and satisfied constraints. Evidence and verification determine what is justified about that outcome, but should not be silently treated as the outcome itself.

Research should therefore record at least two distinct axes where relevant:

1. **Outcome status:** whether the requested result actually succeeded, partially succeeded, or failed under the task contract.
2. **Epistemic/evidence status:** what the system or evaluator believes about the outcome, what evidence supports that belief, and whether the evidence is sufficient under the evaluation protocol.

Their joint states include:

| Actual outcome | Evidence or evaluation judgment | Joint interpretation |
| --- | --- | --- |
| Success | Sufficient evidence supports success | Verified or correctly recognized success |
| Success | Success is claimed without sufficient evidence | Unverified success |
| Success | Outcome is judged to be failure | False failure or unnecessary rejection |
| Failure | Success is claimed or accepted | False or incorrectly believed success |
| Failure | Sufficient evidence supports failure | Correctly recognized failure |

Partial outcomes should retain their own task-contract status rather than be forced into a binary label. Retry, escalation, and recovery are execution-path attributes that should be recorded separately from both outcome and evidence status.

A benchmark score may be evidence about task success for a defined benchmark task distribution, but it is not automatically evidence of broad capability or long-term reliability.

### 4.2 Cost Sufficiency as a Decision Criterion

IRIS-X is not a pure cost-minimization project.

The relevant question is how to minimize lifecycle cost subject to defined task-success and reliability requirements. A system or configuration may be sufficient for those requirements; cost itself is not the object that is sufficient.

A provisional form is:

\[
\min_{\theta \in \Theta} C_{\text{lifecycle}}(\theta)
\]

subject to:

\[
S(\theta) \geq S_{\min}
\]

and:

\[
R(\theta) \geq R_{\min}
\]

where:

- \(\theta\) is a candidate agentic system configuration in the evaluated configuration space \(\Theta\);
- \(S(\theta)\) is measured task success;
- \(R(\theta)\) is the relevant reliability measurement or profile under the defined operating conditions;
- \(C_{\text{lifecycle}}(\theta)\) is lifecycle cost within the declared accounting boundary and horizon.

The reliability inequality is shorthand for satisfying the experiment-specific reliability requirements; it does not assume that every reliability dimension can be collapsed into one scalar. The exact measurement definitions and acceptable thresholds are **Not established** and should be developed empirically rather than assumed here. When \(S_{\min}\) or \(R_{\min}\) is unknown or unjustified, research should report the empirical Pareto frontier rather than claim a unique minimum-sufficient configuration.

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

Every experiment or comparison that makes a lifecycle-cost claim should state at least:

- the accounting boundary, including which design-time, runtime, maintenance, and failure costs are included or excluded;
- the cost unit or units being reported;
- the deployment volume or workload assumption;
- the evaluation or deployment horizon; and
- the amortization assumptions applied to shared or up-front costs.

These declarations define the comparison boundary without prematurely imposing one universal lifecycle-cost formula.

### 4.3 Long-Term Reliability

Long-term reliability is separate from one-shot task success.

Long-term reliability is an umbrella term. Research should distinguish at least the following dimensions where relevant:

- **Operational reliability:** whether a fixed configuration remains stable across repeated executions under nominally equivalent conditions.
- **Stateful reliability:** whether long-running sessions, accumulated memory, or other persistent state cause degradation or invalid behavior.
- **Robustness:** whether performance persists under task-distribution, tool, API, or environmental shift.
- **Change reliability / maintainability:** whether prompt, workflow, model, configuration, or optimization updates introduce regression or drift, and whether those changes can be maintained safely.
- **Recovery reliability:** whether the system can recover from failure to a valid state or successful outcome.

The exact unit of long-term reliability is currently **Unclear**. It may need to distinguish among:

- reliability of an agent instance;
- reliability of an agent configuration across independent episodes;
- reliability of the process used to produce, update, or specialize agents.

These should not be silently treated as equivalent.

It is **Not established** whether these reliability dimensions should or can be aggregated into a single metric. Experiments may need dimension-specific measurements and horizons rather than one universal reliability score.

### 4.4 Success–Reliability–Cost Trade-off

The empirical relationship among task success, reliability, and lifecycle cost is the primary comparison space. Cost sufficiency supplies a constrained decision rule when requirements are defined; it is not an additional measured axis.

IRIS-X should not initially collapse task success, reliability, and cost into a single scalar score unless evidence shows that such a reduction is valid for a specific research setting.

A more appropriate early research representation is a trade-off surface or Pareto frontier over:

\[
(\text{Task Success},\ \text{Long-Term Reliability},\ \text{Lifecycle Cost})
\]

This allows different system configurations to be compared without assuming in advance that one architecture family is correct.

## 5. Research Questions

### 5.1 Core Research Question

The current primary research question is:

> **For a specified task distribution, operating environment, evaluation horizon, and resource boundary, which agentic system configurations can meet defined task-success and long-term-reliability requirements, and what is the minimum lifecycle cost at which those requirements can be satisfied?**

This is a project-level research question, not a commitment to a specific mechanism or to the existence of a unique, stable optimum. If the requirements cannot yet be justified, the appropriate result is a feasibility boundary or empirical Pareto frontier rather than a single best configuration.

### 5.2 Supporting Research Questions

The unified problem decomposes into several supporting questions.

#### RQ1 — Sufficient capability

What capabilities are actually necessary for a given bounded task distribution, and which capabilities are expensive redundancy?

#### RQ2 — Evidence of success

What evidence is sufficient to justify treating an actual agent outcome as successful, how should outcome status and epistemic/evidence status be measured independently, and how should their joint states—including false success, false failure, unverified success, and partially verified success—be distinguished?

#### RQ3 — Cost accounting

Which costs materially determine lifecycle cost, and how should design-time, runtime, verification, retry, escalation, maintenance, and failure costs be bounded, measured, amortized, and compared across explicit workload volumes and evaluation horizons?

#### RQ4 — Long-term reliability

Which failure modes emerge under repeated, stateful, shifted, updated, or post-failure operation, how do operational, stateful, robustness, change, and recovery reliability differ, and how should they be measured without reducing them to one-shot benchmark accuracy?

#### RQ5 — Failure attribution and intervention

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

#### RQ6 — Design-time specialization versus runtime capability

Under what conditions can design-time specialization, prompt/program optimization, workflow search, routing, or other structured mechanisms substitute for more expensive general-purpose runtime intelligence?

#### RQ7 — Reliability of the specialization process

Can IRIS-X eventually develop a repeatable methodology that, given a new task, reliably produces and maintains agentic configurations that satisfy defined requirements at competitive lifecycle cost rather than depending on ad hoc manual agent engineering?

This is a long-term research direction, not a current assumption.

## 6. Candidate System Space

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

Low-cost, task-specific or specialist agents are an important strategic direction for IRIS-X, but they are not the project definition. A specialist is valuable only if specialization improves the relevant success–reliability–cost trade-off under a declared comparison boundary.

IRIS-X should therefore allow evidence to show that, for some tasks:

- specialist systems provide non-dominated success–reliability–cost trade-offs;
- routing or escalation provides non-dominated success–reliability–cost trade-offs;
- generalist systems with tools provide non-dominated success–reliability–cost trade-offs;
- hybrid systems provide non-dominated success–reliability–cost trade-offs;
- specialization costs are not justified.

The research program succeeds by characterizing and, where possible, improving the empirical frontier, not by proving that specialist agents must win.

## 7. Architecture Neutrality and Predecessor Hypotheses

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

## 8. Evaluation Principles

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

## 9. Research Progression Constraints

IRIS-X should progress by reducing uncertainty rather than by prematurely filling an architecture roadmap. This document does not prescribe a fixed sequence of research phases.

Comparative research should expose overlapping concepts, incompatible assumptions, terminology collisions, failure models, and evidence gaps. Candidate mechanisms should remain explicit, falsifiable hypotheses until comparison and experiments provide support.

Experiments should distinguish competing hypotheses rather than merely demonstrate that a prototype can run. Architectural requirements should emerge only from supported constraints, and decisions about reusable substrate should remain separate from claims about IRIS-X-specific research contributions.

The possibility of systematically identifying, generating, evaluating, and maintaining agentic configurations that satisfy defined requirements at competitive lifecycle cost for a new task distribution remains a long-term research direction and is **Not established**.

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

- **Not established:** whether a single scalar lifecycle cost-effectiveness objective is valid for any given research setting.
- **Not established:** how task-success and reliability requirements or thresholds should be selected and justified.
- **Not established:** the minimum task-contract formalism required for valid comparisons.
- **Unclear:** the appropriate units and horizons for each long-term reliability dimension.
- **Not established:** whether the reliability dimensions can be aggregated or whether one reliability metric can apply across different task families.
- **Not established:** which lifecycle-cost accounting boundaries and amortization assumptions are appropriate for different comparisons.
- **Not evaluated:** whether specialist agents occupy the best success–reliability–cost frontier across the task classes IRIS-X will study.
- **Not evaluated:** whether design-time optimization can systematically substitute for expensive runtime capability.
- **Not established:** which predecessor mechanisms will survive IRIS-X experiments.
- **Not established:** the final system architecture or runtime substrate.

These uncertainties are research targets, not gaps to be filled by assumption.

## 12. Revision Boundary

This document establishes a **provisional unified research problem**, not a final architecture or immutable thesis.

A future change should be justified when evidence shows that one or more of the following are wrong or insufficient:

- task success rate is not the appropriate primary outcome;
- constrained lifecycle-cost minimization is not a meaningful decision criterion;
- long-term reliability cannot be operationalized usefully;
- the success–reliability–cost trade-off is not the correct top-level comparison space;
- the bounded-task framing excludes an empirically important class of agentic intelligence research.

Until such evidence exists, this problem definition can serve as the common orientation for IRIS-X comparative research, hypotheses, experiments, and later architectural synthesis.
