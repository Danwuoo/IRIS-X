# IRIS-X: A Product-Oriented Platform for Domain AI Specialization

## Abstract

IRIS-X is conceived as a product-oriented platform for transforming general-purpose artificial intelligence capabilities into domain-specialized systems that satisfy explicit task, quality, operational, and economic requirements. Its central premise is that domain specialization should not be equated with a single training method such as supervised fine-tuning, parameter-efficient adaptation, retrieval augmentation, prompt optimization, or reinforcement learning. For a given domain, the most effective solution may instead be a configuration composed of several mechanisms at different layers, including model selection, prompting, retrieval, tools, workflows, fine-tuning, routing, verification, and runtime controls.

Accordingly, IRIS-X treats domain AI construction as a configuration search and engineering selection problem rather than as a fixed model-training pipeline. The user supplies a **Domain Specification** describing domain material, real workloads, success criteria, deployment constraints, and available resources. IRIS-X establishes a baseline, constructs an evaluation surface, identifies capability gaps, applies candidate specialization interventions, measures their effects, and iteratively searches for configurations that satisfy the declared requirements. The output is not merely a model checkpoint but a versioned and deployable **Domain Package** containing the selected model and specialization artifacts together with evaluation results, operational configuration, known limitations, and deployment metadata.

The platform follows a product-engineering methodology summarized as **Build–Measure–Select**. External frameworks, models, algorithms, and prior systems are treated as candidate technical backends that must demonstrate measurable value on actual domain workloads before being promoted into the platform. Research remains an auxiliary activity initiated when repeated engineering failures expose unresolved technical questions; it is not the primary production process. In this formulation, IRIS-X aims to become an engineering system for systematically producing domain AI rather than a theoretical framework for prescribing how domain AI should be constructed.

---

## 1. Introduction

The availability of increasingly capable general-purpose language and multimodal models does not eliminate the need for domain-specific systems. In practical deployment, a general model is rarely evaluated solely by its abstract capability. It is evaluated against concrete work: whether it can process a particular class of documents, operate under an organization's rules, satisfy latency or cost constraints, interact with specific tools, avoid critical failure modes, and maintain acceptable behavior under the target workload.

A common response to this problem is to frame domain adaptation primarily as model training. Under this view, users provide a dataset, select a base model, perform fine-tuning, and receive a new checkpoint or adapter. This framing is useful for a subset of applications but is too restrictive for a general domain-AI production system. Many practical capability gaps can be resolved without modifying model weights. Conversely, some tasks cannot be solved adequately through prompting or retrieval alone and require model-level adaptation. The appropriate intervention depends on the workload, the current failure profile, the deployment environment, and the requirements imposed on the resulting system.

IRIS-X therefore begins from a different abstraction. The primary problem is not:

> How should a model be trained for a domain?

It is:

> **Given a domain, a workload, explicit requirements, and operational constraints, what AI configuration should be constructed so that the resulting system can perform the required work adequately and economically?**

This change in formulation has important consequences. First, the optimization target becomes a complete deployable configuration rather than an isolated model. Second, techniques such as retrieval, workflow design, fine-tuning, routing, and reinforcement learning become alternative or composable interventions instead of mandatory stages. Third, system evaluation must occur against real task distributions and operational requirements rather than only against generic benchmarks. Finally, the platform itself must be capable of comparing, selecting, and composing technical mechanisms instead of merely exposing them as unrelated tools.

IRIS-X is intended to implement this engineering process.

---

## 2. Problem Definition

Let a domain application be represented by a specification

\[
D = (K, T, R, O),
\]

where:

- \(K\) denotes domain material and available knowledge;
- \(T\) denotes the target task distribution or workload;
- \(R\) denotes the requirements defining acceptable system behavior;
- \(O\) denotes operational constraints and deployment conditions.

Let a candidate AI system configuration be represented as

\[
\theta = (M, P, C, G, A, V),
\]

where, depending on the application:

- \(M\) is the base model or model set;
- \(P\) represents prompts, programs, or learned instruction artifacts;
- \(C\) represents contextual mechanisms such as retrieval and domain knowledge access;
- \(G\) represents workflow, control, routing, or orchestration logic;
- \(A\) represents model adaptation, including fine-tuning or other training procedures;
- \(V\) represents evaluation, validation, or task-specific checking mechanisms.

Not every configuration requires all components. A valid configuration may be as simple as a base model with a prompt, or as complex as a fine-tuned model combined with retrieval, tools, routing, and structured validation.

For a domain specification \(D\), IRIS-X seeks configurations whose measured behavior satisfies the application's requirements:

\[
\theta \models R.
\]

Among configurations that satisfy \(R\), selection should consider operational objectives such as runtime cost, latency, implementation complexity, maintainability, training expense, hardware requirements, and deployment risk.

A conceptual selection objective can therefore be written as:

\[
\theta^* =
\arg\min_{\theta \in \Theta_D}
C(\theta)
\quad
\text{subject to}
\quad
Q(\theta, T) \models R,
\]

where \(Q\) represents measured behavior over the relevant task distribution and \(C\) represents the applicable engineering cost profile.

This formulation does not require all criteria to be reducible to a single scalar objective. In practice, IRIS-X may maintain a Pareto set over quality, latency, monetary cost, complexity, and other operational dimensions. The essential principle is simpler:

> additional capability or architectural complexity should be introduced only when it contributes materially to satisfying the domain requirements.

This is the engineering meaning of **minimum-sufficient specialization**.

---

## 3. Domain Specification as the Primary Input

IRIS-X is intentionally designed so that its primary input is not a training dataset. A training dataset is one possible artifact within a broader domain specification, but many organizations begin with less structured material.

A user may possess documents, operating procedures, historical cases, databases, support conversations, manually completed examples, APIs, schemas, policy documents, or domain experts. The platform must therefore accept heterogeneous evidence about the intended domain and progressively transform it into a usable engineering specification.

The Domain Specification is divided conceptually into four parts.

### 3.1 Domain Material

Domain material defines the information environment within which the system is expected to operate. It may include documentation, regulations, manuals, terminology, historical records, structured databases, schemas, APIs, and existing knowledge bases.

This material may later support several different mechanisms: evaluation construction, retrieval systems, synthetic example generation, continued pretraining, supervised fine-tuning, tool integration, or simply prompt context. IRIS-X should not decide the role of a piece of domain material before evaluating the application requirements.

### 3.2 Task Distribution

The task distribution specifies what the system must actually do.

Examples include:

\[
\text{contract} \rightarrow \text{risk assessment}
\]

\[
\text{invoice} \rightarrow \text{audit decision}
\]

\[
\text{technical question} \rightarrow \text{domain answer}
\]

\[
\text{support request} \rightarrow \text{classification and action}
\]

The task distribution is more important than an abstract domain label. Two systems operating in the same legal or financial domain may require radically different configurations if one performs retrieval while the other performs consequential decision support.

The platform should therefore optimize against representative work, not merely against domain vocabulary.

### 3.3 Requirements

Requirements determine what constitutes an acceptable system.

They may include conventional quality metrics such as accuracy, recall, precision, ranking quality, or task-completion rate, but may also include operational constraints such as:

- maximum critical-error rate;
- schema-conformance requirements;
- latency targets;
- throughput requirements;
- monetary cost limits;
- human-review policies;
- privacy constraints;
- deterministic behavior requirements;
- minimum support for specific task families.

A central product principle follows:

> IRIS-X should optimize toward declared requirements rather than toward maximum benchmark performance.

A system with lower absolute benchmark performance may be the superior product if it satisfies all required constraints at substantially lower cost or operational complexity.

### 3.4 Operating Constraints

Operating constraints describe the environment within which the final system must function. Examples include deployment hardware, cloud restrictions, on-premise requirements, network access, allowed model providers, language requirements, inference budgets, request volumes, security policies, and integration constraints.

These conditions are first-class inputs because an otherwise strong specialization strategy may be unusable when placed within the actual deployment environment.

---

## 4. Domain Specialization as Configuration Search

The technical core of IRIS-X is the search over a **specialization space**.

Given a domain specification \(D\), the platform considers a family of candidate configurations:

\[
\Theta_D =
\{\theta_1, \theta_2, \ldots, \theta_n\}.
\]

These candidates may differ in base model, prompting strategy, context construction, retrieval architecture, tool use, workflow topology, training method, routing policy, or combinations thereof.

An illustrative search space might include:

\[
\theta_1 = M_A + P
\]

\[
\theta_2 = M_A + P + RAG
\]

\[
\theta_3 = M_A + LoRA
\]

\[
\theta_4 = M_B + P_{optimized}
\]

\[
\theta_5 = M_B + workflow
\]

\[
\theta_6 = M_S^{fine-tuned} + tools
\]

\[
\theta_7 = M_S + router(M_L)
\]

The purpose of IRIS-X is not to exhaustively enumerate every possible combination. It is to progressively narrow this space through measurement and engineering evidence.

This produces a fundamentally different platform behavior from conventional training systems. A conventional system may assume that the user has already selected fine-tuning as the correct intervention. IRIS-X instead treats the intervention itself as a decision variable.

---

## 5. The Specialization Loop

The principal execution model of IRIS-X is an iterative specialization loop.

\[
Domain\ Specification
\rightarrow
Evaluation
\rightarrow
Baseline
\rightarrow
Gap\ Analysis
\rightarrow
Intervention
\rightarrow
Evaluation
\rightarrow
Selection
\]

The process continues until requirements are met or the search reaches a declared resource or feasibility boundary.

### 5.1 Evaluation Construction

Before optimization, the platform must establish a workload on which candidate systems can be compared. Depending on available data, this may involve selecting held-out historical examples, manually authoring representative cases, extracting task instances from domain material, or generating candidate examples for human review.

Evaluation is not an afterthought. Without a stable workload, optimization degenerates into qualitative prompt tweaking.

### 5.2 Baseline Establishment

A baseline determines the performance of an initial configuration under the same evaluation conditions that will later be used to measure interventions.

The baseline may be a strong general model, a smaller economical model, an existing production system, or several reference configurations.

The baseline provides both a performance reference and an indication of where specialization effort is necessary.

### 5.3 Gap Analysis

IRIS-X should analyze not only aggregate performance but also the structure of failure.

Different failure patterns suggest different interventions.

For example:

- missing domain knowledge may motivate retrieval or continued pretraining;
- output-format instability may motivate structured generation or validation;
- repeated task-pattern errors may motivate supervised fine-tuning;
- complex multi-step failures may motivate workflow decomposition;
- low-confidence edge cases may motivate routing or escalation;
- rewardable behavioral errors may motivate preference optimization or RL.

Gap analysis does not need to be perfectly automated in the initial versions of IRIS-X. However, the platform should preserve enough structured information for intervention decisions to become progressively more systematic.

### 5.4 Intervention

An intervention modifies one or more parts of the candidate configuration.

Candidate interventions can be organized into several classes.

**Context-level interventions** include prompt optimization, few-shot selection, context restructuring, retrieval, and domain knowledge injection.

**System-level interventions** include tools, workflows, structured outputs, validators, memory, and multi-stage execution.

**Model-level interventions** include supervised fine-tuning, parameter-efficient fine-tuning, continued pretraining, preference optimization, and reinforcement learning.

**Composition-level interventions** include routing, cascades, fallback models, ensembles, and capability escalation.

IRIS-X must remain technique-agnostic. These mechanisms compete on their measured engineering value.

### 5.5 Evaluation and Selection

After intervention, the candidate configuration is evaluated under the same workload and requirement surface.

The result is compared against:

1. the baseline;
2. previous configurations;
3. the explicit domain requirements;
4. operational costs and constraints.

Candidates may then be promoted, retained as experimental alternatives, modified, or rejected.

---

## 6. The Domain Package

The primary output of IRIS-X is a **Domain Package**.

A Domain Package is the deployable unit representing a specific version of domain-specialized AI capability. It is intentionally broader than a checkpoint or adapter.

A conceptual package structure is:

```text
domain-package/
├── manifest
├── model/
├── specialization/
├── domain/
├── evaluation/
└── deployment/
```

The `model/` component identifies the base model and any learned model artifacts such as adapters or checkpoints.

The `specialization/` component contains configuration artifacts such as prompts, retrieval definitions, tool interfaces, workflows, routing rules, or validation logic.

The `domain/` component records schemas, terminology, knowledge references, and relevant domain assets.

The `evaluation/` component records benchmark definitions, measured metrics, regression tests, and known failure cases.

The `deployment/` component describes runtime requirements and operational configuration.

The exact structure should remain extensible because many Domain Packages will not require every mechanism.

Conceptually, a Domain Package should answer six basic questions:

1. What tasks does this system support?
2. Under what workload was it evaluated?
3. What configuration produced the measured behavior?
4. Does it satisfy the declared requirements?
5. What are its known limitations?
6. What is required to reproduce and deploy it?

This makes the Domain Package both an engineering artifact and a product boundary.

---

## 7. Product-Level Optimization Criteria

IRIS-X should not optimize only model accuracy. A production configuration exists within a multi-dimensional engineering space.

Relevant dimensions include:

\[
(Quality,\ Cost,\ Latency,\ Complexity,\ Maintainability,\ Resource\ Demand)
\]

A configuration that improves quality marginally while multiplying deployment cost or operational complexity may not be preferable.

Consider two candidate systems:

\[
\theta_A:
95.4\%\ success,\ \$0.002/task
\]

\[
\theta_B:
97.1\%\ success,\ \$0.035/task
\]

If the domain requirement is \(94\%\), configuration \(\theta_A\) may be the preferred system despite its lower maximum performance.

This illustrates an important principle:

> IRIS-X is not intended to maximize intelligence. It is intended to produce sufficient domain capability under real constraints.

This principle also discourages unnecessary architecture. Additional layers, models, verifiers, routers, or training processes incur engineering and maintenance cost and should therefore justify their existence through measurable improvement.

---

## 8. External Sources as Engineering Candidates

IRIS-X may maintain external frameworks, algorithms, and systems as source snapshots or references, but their principal value is operational rather than conceptual.

An external project enters the IRIS-X engineering process as a **candidate backend**.

For example:

- DSPy may serve as a candidate program/prompt optimization backend;
- GEPA may serve as a candidate reflective optimization mechanism;
- AFlow may serve as a candidate workflow-search backend;
- Agent Lightning may serve as a candidate reinforcement-training backend;
- RouteLLM and FrugalGPT may serve as candidate routing or cascade mechanisms;
- verifier frameworks may provide evaluation or reward mechanisms;
- observability frameworks may provide profiling and execution instrumentation.

The relevant question is not whether a project's conceptual framework is attractive. The relevant question is:

> Does this mechanism improve a Domain Package under representative workload and cost conditions?

The promotion path can therefore be expressed as:

\[
Source
\rightarrow
Adapter
\rightarrow
Engineering\ Trial
\rightarrow
Measurement
\rightarrow
Adopt / Experimental / Reject
\]

This approach prevents IRIS-X from becoming a passive collection of frameworks or a repository of conceptual comparisons.

---

## 9. Backend Isolation and Integration

External systems should not automatically define the internal architecture of IRIS-X.

A preferable implementation strategy is to preserve upstream systems separately and create explicit IRIS-X adapters:

```text
sources/
    upstream projects

irisx/
    backends/
        dspy/
        gepa/
        aflow/
        ...
```

This separation serves several purposes.

First, it preserves upstream identity and makes upgrading or replacing dependencies easier. Second, it prevents framework-specific abstractions from becoming implicit IRIS-X core concepts. Third, it enables controlled comparison of multiple backends implementing similar capabilities. Finally, it permits the removal of a backend without destabilizing the conceptual product model.

The core IRIS-X interface should therefore be defined around required capabilities rather than external framework APIs.

---

## 10. Capability Registry

As the system matures, tested mechanisms can be represented through a capability registry.

A capability describes an engineering function, while a backend describes one implementation of that function.

For example:

```yaml
prompt_optimization:
  backends:
    - dspy
    - gepa

workflow_search:
  backends:
    - aflow

reinforcement_training:
  backends:
    - agent_lightning

model_routing:
  backends:
    - routellm
    - frugalgpt
```

However, registration alone must not imply endorsement.

Each backend should accumulate empirical engineering metadata such as:

- domains tested;
- task families tested;
- performance delta;
- optimization cost;
- runtime overhead;
- hardware requirements;
- stability;
- known incompatibilities;
- promotion status.

A mature registry therefore becomes not simply a list of integrations but an evidence-bearing catalog of specialization capabilities.

---

## 11. Build–Measure–Select as the Default Development Method

IRIS-X adopts a product-engineering rather than theory-first development method.

The default cycle is:

\[
Build
\rightarrow
Measure
\rightarrow
Select
\]

A feature, framework, or architectural component should not be incorporated solely because it is theoretically attractive, frequently cited, widely adopted, or historically present in predecessor systems.

It earns a place in IRIS-X when it improves one or more practical dimensions of an end-to-end Domain Package without imposing unjustified costs elsewhere.

This principle applies equally to sophisticated mechanisms. Fine-tuning, reinforcement learning, multi-agent coordination, learned routing, or complex verification layers receive no privileged status. They must compete against simpler alternatives.

This creates an architecture that grows from observed product pressure rather than from speculative completeness.

---

## 12. Engineering Trials

The primary empirical unit of day-to-day IRIS-X development should be the **Engineering Trial**.

An Engineering Trial answers a concrete product question:

> Does intervention \(X\) improve configuration \(Y\) sufficiently to justify promotion?

A trial records at least:

- the goal;
- the baseline;
- the candidate intervention;
- the workload;
- the measured result;
- the relevant costs;
- the resulting engineering decision.

For example:

```text
Goal:
Invoice extraction success >= 96%.

Baseline:
Model A + prompt = 88.2%.

Candidate:
Program optimization backend.

Result:
94.9%.

Optimization cost:
$14.20.

Runtime overhead:
0.

Decision:
Do not promote.

Reason:
Material improvement, but requirement remains unmet.
```

A subsequent trial may evaluate LoRA and produce 97.0%, resulting in promotion.

The engineering decision is as important as the metric. IRIS-X should accumulate a history not merely of what was tested, but of why specific configurations were adopted or rejected.

---

## 13. Role of Research

IRIS-X does not eliminate research. It changes when and why research occurs.

Research should be initiated when product engineering repeatedly encounters an unresolved question for which existing mechanisms and empirical comparisons are insufficient.

For example, repeated trials may reveal that prompt-level optimization consistently reaches a performance plateau, but there is no reliable criterion for deciding whether retrieval, fine-tuning, or a stronger model is the appropriate next intervention.

Such a pattern can be promoted from an engineering problem to a research question.

The intended flow is:

\[
Engineering\ Failure
\rightarrow
Research\ Question
\rightarrow
Controlled\ Investigation
\rightarrow
Engineering\ Rule
\]

Research therefore produces reusable decision knowledge for the platform.

The undesirable alternative is an open-ended process in which each research result primarily generates additional research programs without returning to product behavior.

IRIS-X should prefer research that can eventually modify the specialization process, evaluation system, backend registry, or selection policy.

---

## 14. Product and Research Tracks

The project can therefore be divided into two operational tracks.

### 14.1 Product / Engineering Track

This is the default track.

Its activities include:

- backend integration;
- workload construction;
- benchmarking;
- prompt and program optimization;
- retrieval configuration;
- tool integration;
- workflow construction;
- fine-tuning;
- reinforcement training;
- profiling;
- routing;
- packaging;
- deployment;
- regression evaluation.

Its primary success criterion is:

> Does this work produce a better Domain Package?

### 14.2 Research Track

This track is opened selectively.

Its activities include:

- investigating repeated unexplained failures;
- developing new specialization criteria;
- studying intervention-selection rules;
- evaluating previously unresolved mechanisms;
- producing knowledge required for better engineering decisions.

Its success criterion is not publication quantity or conceptual novelty alone.

It is:

> Does the resulting knowledge improve the domain-specialization process?

---

## 15. Conceptual Product Decomposition

Without committing to a final software architecture, the IRIS-X product can be decomposed into five conceptual layers.

### 15.1 Domain Interface

The Domain Interface ingests domain material, tasks, examples, requirements, and operating constraints.

Its purpose is to translate user intent into a structured Domain Specification.

### 15.2 Evaluation Harness

The Evaluation Harness creates and executes workload evaluations, establishes baselines, tracks metrics, and supports regression comparison between candidate configurations.

### 15.3 Specialization Engine

The Specialization Engine invokes candidate specialization capabilities, including prompting, retrieval, tools, workflows, model adaptation, reinforcement learning, routing, and related mechanisms.

It should not assume one fixed specialization sequence.

### 15.4 Selection and Optimization Layer

This layer compares candidate configurations against requirements and operational criteria.

It determines whether to retain, modify, reject, or promote a configuration and selects subsequent interventions when requirements remain unmet.

### 15.5 Domain Package Layer

The Domain Package layer serializes the selected system into a versioned, reproducible, and deployable artifact.

These five layers describe product responsibilities. They should not yet be interpreted as mandatory process boundaries, services, classes, or repositories.

---

## 16. Non-Goals

Clarifying what IRIS-X is not is necessary to prevent scope drift.

IRIS-X is not primarily a general-purpose agent framework. Existing runtimes and agent frameworks can be integrated where useful.

IRIS-X is not merely a fine-tuning platform. Weight adaptation is one specialization mechanism among many.

IRIS-X is not conventional AutoML for language models. The search space includes model choice, prompts, contextual systems, tools, workflows, routing, validation, and training.

IRIS-X is not a benchmark leaderboard. Maximum benchmark performance does not define product success.

IRIS-X is not an AI research laboratory whose primary output is theory. Research exists in support of unresolved engineering needs.

IRIS-X is not a framework aggregation project. Integrating additional libraries has no intrinsic value unless those integrations improve practical specialization outcomes.

---

## 17. Product Principles

The concept can be summarized through seven product principles.

**Domain-first.**  
The domain and workload are the starting point; the model is not.

**Requirement-driven.**  
The objective is requirement satisfaction, not unrestricted capability maximization.

**Technique-agnostic.**  
No specialization method is privileged in advance.

**Empirical.**  
Technical components must demonstrate value on measured workloads.

**Minimum-sufficient.**  
Unnecessary capability and complexity should not be purchased merely because they are available.

**Package-oriented.**  
The deliverable is a complete domain capability rather than an isolated model artifact.

**Lifecycle-aware.**  
A deployed domain system must support reevaluation, regression testing, respecialization, and version evolution as its data and requirements change.

---

## 18. Product Narrative

The intended user interaction can be expressed simply.

A user provides:

> These are my domain materials. These are the tasks my organization actually performs. These outcomes are acceptable. These failures are unacceptable. These are my cost, hardware, privacy, and deployment constraints.

IRIS-X responds:

> I will establish a baseline, evaluate candidate models and specialization mechanisms, measure them against your workload, select a configuration that satisfies your requirements, and produce a versioned Domain Package that can be evaluated, reproduced, and deployed.

The value of IRIS-X lies in the middle of these two statements: the systematic engineering process that converts an underspecified collection of domain assets into a measured and deployable system.

---

## 19. Central Product Thesis

The product thesis of IRIS-X can be stated as follows:

> **Domain AI should be treated as an engineering configuration problem rather than a predetermined training procedure. Given domain knowledge, real workloads, explicit requirements, and operating constraints, a platform should be able to evaluate alternative models and specialization techniques, iteratively construct candidate configurations, and produce the simplest deployable system that satisfies the domain's requirements.**

This thesis is a design proposition for the product, not an established scientific law.

Its validity must ultimately be demonstrated through implementation.

---

## 20. Near-Term Validation Objective

The first meaningful validation of IRIS-X should therefore not be another abstract architecture exercise.

It should be an end-to-end vertical slice demonstrating:

\[
Domain\ Specification
\rightarrow
Baseline
\rightarrow
Specialization
\rightarrow
Evaluation
\rightarrow
Selection
\rightarrow
Domain\ Package
\]

for one sufficiently bounded real domain.

The purpose of this initial implementation is not to prove that every specialization method can be automated. It is to determine whether the proposed product abstraction is coherent enough to support a real domain from initial requirements through a deployable package.

Only after this loop exists should broader architectural abstractions be stabilized.

---

## Conclusion

IRIS-X is proposed as a domain-AI production platform whose core responsibility is not model training in isolation, but the systematic transformation of domain requirements into deployable specialized AI configurations.

Its central abstraction is the Domain Specification. Its principal engineering process is iterative specialization. Its decision rule is empirical requirement satisfaction under operational constraints. Its primary deliverable is the Domain Package. Its development methodology is Build–Measure–Select. External systems are treated as candidate backends subject to practical testing, while research is invoked only when product engineering exposes unresolved technical questions.

The intended result is a platform capable of answering a question that individual optimization, training, retrieval, or agent frameworks do not answer by themselves:

> **Given this domain and this real workload, what AI system should actually be built?**

IRIS-X exists to turn that question into a repeatable engineering process.