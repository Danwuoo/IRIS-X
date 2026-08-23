---
document_id: Design_Theory
status: research_basis
layer: L1
role: conceptual_source_of_truth
depends_on: []
feeds_into:
  - Minimal_Closed_Loop_Runtime_Spec
  - Execution_IR_and_Episode_Semantics
  - Evidence_Packet_and_Verifier_Runtime
  - Commit_Abort_Replay_Semantics
  - Failure_Taxonomy_v0
  - Metrics_Definition
mvp_scope: partial
---

# Next-Generation Agents: Design Conception and Theory

---

## 0. Compressed Proposition

The next generation of agents should not be defined only as "models that can answer questions." They should be defined as:

> **Learnable intelligent systems that, under limited context, limited resources, and incomplete information, can form hypotheses, plan actions, execute operations, collect evidence, verify results, commit state, manage memory, localize failures, and recover paths.**

In other words, the core of an agent is not only **reasoning**, but:

```text
think -> plan -> act -> observe -> verify -> commit / rollback -> remember -> recover
```

This is not a fixed process. It is a closed loop driven by learned control, observable, auditable, trainable, and replayable.

---

## 1. Problem Restatement: Why "Better Reasoning" Is Still Not Enough

In recent years, the capability improvement of large language models has mainly developed along several routes:

1. **Chain-of-thought / reasoning trace**: Make the model explicitly generate intermediate reasoning.
2. **Reasoning + acting**: Let the model call tools or interact with the environment during reasoning, such as ReAct.
3. **Tool use**: Let the model learn when and how to call APIs, such as Toolformer.
4. **Test-time search**: Expand multiple paths during inference, such as Tree of Thoughts, Graph of Thoughts, and Language Agent Tree Search.
5. **Reflection / self-improvement**: Let the model improve from errors, feedback, or past episodes, such as Reflexion and Self-Refine.
6. **Memory / context management**: Let the model support long tasks through memory layers, working sets, and context management, such as MemGPT, Generative Agents, and Voyager.
7. **Agent safety / evaluation**: Extend agent risk from text output to the action layer, safety, robustness, and risk awareness.

All of these directions matter. But if they are only assembled as an external workflow, several fundamental problems appear:

- There is no formal semantic boundary between reasoning and action.
- Tool calls often become a hard-coded orchestration process rather than a learned policy.
- Search / planning is often an external algorithm, not an attributable internal agent capability.
- Memory may degrade into a retrieval cache rather than a governable long-term state.
- Verification often happens only at the final answer instead of as an action-level runtime service.
- Side effects lack transaction semantics, making replay, rollback, and audit difficult.
- Failure can only be observed as "wrong" and cannot be subdivided into representation, procedure, search, memory, abstraction, evaluation, or execution governance failures.

Therefore, the core question raised by this document is:

> **How can we design an agent runtime that is not tool-first, not workflow-first, not search-first, but instead centered on learned cognition while also having executable reasoning, verifiable actions, manageable context, auditable side effects, and recoverable failure paths?**

---

## 2. Research Context And Absorption Principles

This section is not a literature review. It transforms relevant research into design principles.

### 2.1 ReAct: Reasoning And Action Must Interleave, Not Be Separated Before And After

The core value of ReAct is that it interleaves reasoning traces with task-specific actions, allowing the model to query external information, update plans, and handle exceptions during reasoning, rather than thinking everything through once before acting.

**Absorption principles:**

- An agent should not treat reasoning and acting as two independent phases.
- Action results must flow back into reasoning state.
- Observation, action, and reasoning updates should form a continuous closed loop.
- Every action should have a traceable state transition and verifier evidence.

**Corresponding design in this document:**

```text
Hypothesis -> Action Proposal -> Observation -> State Update -> Verification
```

ReAct proves that interleaving reasoning/action is more flexible than pure reasoning or pure action. This design goes further by requiring actions to become transactionized, evidenced, and credit-addressable.

### 2.2 Toolformer: Tool Use Should Be A Decision Learned By The Model, Not An External Flowchart

Toolformer's core contribution is letting a language model learn "when to call an API, what to call, what parameters to pass, and how to incorporate the result into subsequent prediction."

**Absorption principles:**

- Tools are not intelligence itself; they are an external substrate.
- The timing, parameters, and result integration of tool use should be decided by learned control.
- Tool results must not bypass the core state representation and form a private side channel.
- Tools must not become oracles; their results still require verification and provenance tracking.

**Corresponding design in this document:**

Tool calls are placed into Execution IR / Episode Step and governed by the verifier and Evidence Packet, rather than controlled by handwritten if-else workflows.

### 2.3 Tree / Graph / Language Agent Tree Search: Reasoning Needs Searchable Structure, But Search Cannot Replace Intelligence

Tree of Thoughts expands the reasoning unit from token to "thought" and allows branching, evaluation, and backtracking. Graph of Thoughts further organizes thoughts into arbitrary graph structures. Language Agent Tree Search places reasoning, acting, planning, and environment feedback into a tree search / MCTS-style framework.

**Absorption principles:**

- Agents need branching, lookahead, rollback, and candidate evaluation.
- Search is an explicit form of cognitive control, but it cannot become the only problem-solving core.
- Search nodes must carry state, action, evidence, and credit metadata.
- Search expansion and stopping conditions should be controlled by learned budget / termination policy, not fixed depth or fixed beam.

**Corresponding design in this document:**

```text
Branch = State Summary + Candidate Action + Expected Effect + Evidence Slot + Credit Hints
```

Therefore, search is no longer only a prompting trick; it is incorporated into Execution IR and Episode Governance.

### 2.4 Reflexion / Self-Refine: Feedback Is A Semantic Gradient, But It Cannot Exist Only In The Prompt

Reflexion shows that an agent can transform environmental feedback into verbal reflection, write it into episodic memory, and improve later trials. Self-Refine shows that the same model can generate a draft, propose feedback, and iteratively revise it.

**Absorption principles:**

- Feedback should become a consumable internal signal, not merely be concatenated into a prompt.
- Reflection should align with Failure Taxonomy, Credit Routing, and recovery action.
- Self-correction cannot only be "try again"; it should specify which capability surface needs repair.
- Reflection memory needs a write gate to avoid polluting long-term memory.

**Corresponding design in this document:**

Reflection is redefined as:

```text
Failure Evidence -> Credit Routing -> Targeted Recovery -> Memory Write / Suppress
```

### 2.5 Voyager / Generative Agents: Long-Term Capability Comes From The Compound Structure Of Skill, Memory, And Reflection

Voyager shows the importance of automatic curriculum, skill libraries, environment feedback, self-verification, and composable executable skills for open-ended embodied agents. Generative Agents shows how observation, memory, reflection, and planning support long-term interactive behavior.

**Absorption principles:**

- Agents need skill accumulation, but a skill library must not become a second brain.
- Memory needs layers: episodic, semantic, procedural, and working set.
- Reflection and planning must be managed by memory governance, not appended without limit.
- Skill reuse must have applicability checks and verification; it must not be blindly applied.

**Corresponding design in this document:**

```text
Skill / Memory Item = Content + Applicability Conditions + Provenance + Validity History + Failure Profile
```

### 2.6 MemGPT: Context Is An Operating System Problem, Not Merely A Prompt Length Problem

MemGPT analogizes the limited context window to fast memory in an operating system and moves information across different memory layers through virtual context management.

**Absorption principles:**

- The context window is not memory itself; it is a working set.
- Agents need a Context OS / Working Set Compiler.
- Compression, swap-in, swap-out, pinning, and eviction are all core agent runtime problems.
- Context selection should consider provenance, task phase, branch, replayability, and verifier needs.

**Corresponding design in this document:**

```text
Working Set = Active Goal + Current State + Relevant Memory + Evidence + Constraints + Recovery Context
```

### 2.7 LLMCompiler: Multi-Tool Execution Needs A Dependency Graph, Not A Linear Call Chain

LLMCompiler shows that multiple function calls can be compiled into a task graph with dependencies, reducing latency / cost when parallelism is possible.

**Absorption principles:**

- Multiple actions / tool calls should not be only a linear sequence.
- An execution plan should explicitly represent dependencies, parallelizability, preconditions, and postconditions.
- The responsibilities of planner, dispatcher, and executor must be separated, but semantic decisions cannot be outsourced to a hard workflow.
- The execution graph should align with verification / evidence / rollback.

**Corresponding design in this document:**

Execution IR should support:

```text
node: action
edge: dependency / causal precondition / evidence dependency
commit group: atomic boundary
rollback group: recovery boundary
```

### 2.8 Agent Safety / Evaluation: Agent Risk Is Not Only In Text, But In Action

Research such as Agent-SafetyBench points out that after agents enter interactive environments and tool use, risk is no longer only harmful text. It includes unsafe action, lack of risk awareness, lack of robustness, incorrect tool use, and environmental side effects.

**Absorption principles:**

- Safety should not be only an output filter; it should enter action precheck / postcheck.
- Risk awareness should be part of the verifier / controller.
- Actions with external side effects must have commit / abort / rollback semantics.
- Evaluation should not only inspect task success; it should also inspect unsafe action, false accept, false reject, and recovery quality.

---

## 3. Core Design Theory

### 3.1 An Agent Is Not A Model, But A Runtimized Closed Loop

This document defines an agent as:

```text
Agent = Cognition Kernel
      + State Representation
      + Execution Substrate
      + Context OS
      + Verifier Runtime
      + Memory Governance
      + Failure Recovery
      + Episode Governance
```

The model is the main carrier of the cognition kernel, but intelligent behavior comes from the entire closed loop.

### 3.2 Capability Decomposition Of An Agent

| Capability Surface | Question | Main Mechanism |
| --- | --- | --- |
| Representation | How are the world, task, and goal internally represented? | Canonical State Representation |
| Reasoning | How are hypotheses formed, updated, and compared? | Recurrent Cognition Kernel |
| Planning | How are executable candidate actions produced? | Procedure / Plan Proposal |
| Action | How does the agent interact with tools or the environment? | Execution IR |
| Observation | How is external feedback absorbed? | Observation -> State Update |
| Verification | How is action or answer reliability judged? | Verifier Runtime + Evidence Packet |
| Memory | How are information and experience stored, read, compressed, and forgotten? | Context OS + Memory Hierarchy |
| Recovery | How are failures localized and corrected? | Credit Routing + Targeted Recovery |
| Governance | How are side effects committed, rolled back, and audited? | Episode Journal |

---

## 4. Three-Layer Architecture

### 4.1 Layer A: Core Cognition Kernel

The core cognition kernel is the agent's only high-capacity semantic subject. It is responsible for:

- state encoding / update
- hypothesis formation
- local / recurrent reasoning
- uncertainty estimation
- budget and halting signals
- failure credit hints
- verifier feature production
- memory / tool / execution request proposal

**Design principles:**

1. A second high-capacity semantic brain must not be introduced.
2. Tools, memory, retrieval, and planner must not replace the cognition kernel.
3. Control signals must be learnable, observable, and calibratable.
4. Every major state transition should be traceable by the attribution system.

### 4.2 Layer B: Action Execution Substrate

The action execution substrate is responsible for projecting the cognition kernel's hypothesis / plan into an executable structure.

It includes:

- Execution IR
- action schema
- branch graph
- tool / environment adapter
- precondition checker
- postcondition checker
- evidence attachment point
- commit / abort / rollback logic

**Design principles:**

1. Execution IR is not equal to reasoning state.
2. Tool output must not directly become core semantic state; it must pass through observation normalization.
3. Every action needs provenance.
4. Any action with external side effects must have commit discipline.

### 4.3 Layer C: Context And Runtime Governance

This layer is responsible for long-horizon stability.

It includes:

- working set compiler
- memory hierarchy
- retrieval provenance
- compression / summarization
- context pinning
- evidence retention
- episode journal
- runtime manifest
- replay / reconciliation

**Design principles:**

1. Context is a working set; more is not always better.
2. Memory is governed state, not an append-only log without limits.
3. Long tasks must be able to reconstruct critical decision paths.
4. Failure and recovery must be localizable to concrete episode steps.

---

## 5. First-Class System Primitives

### 5.1 Canonical State Representation

An agent needs a shared cross-module canonical state to represent:

- task intent
- global context
- objects / entities
- relations
- events / transitions
- abstractions / macros
- confidence / uncertainty summaries
- verifier-relevant state

The purpose of state representation is not human readability, but maintaining cross-module consistency and attributability.

**Boundary rules:**

- State representation is reasoning state.
- Execution plan, tool trace, and raw memory documents should not be directly mixed into reasoning state.
- External information must pass through normalized observation or summary projection.

### 5.2 Execution IR

Execution IR is action semantics, not reasoning semantics.

It represents:

```text
ExecutionStep {
  step_id
  parent_step_id
  action_type
  action_payload
  expected_effect
  preconditions
  postconditions
  dependency_edges
  verifier_requirements
  rollback_policy
  side_effect_class
}
```

**Core uses:**

- plan compilation
- tool dispatch
- branch management
- execution replay
- side-effect governance
- evidence alignment
- recovery diagnosis

### 5.3 Evidence Packet

Evidence Packet is the standard evidence unit for every important action / branch / verifier event.

```text
EvidencePacket {
  evidence_id
  episode_id
  step_id
  pre_state_summary
  action_ref
  observation
  post_state_summary
  verifier_result
  confidence
  disagreement
  violated_constraints
  failure_logits
  credit_hints
  provenance
  runtime_context
}
```

**Design principles:**

- Evidence Packet is not explanation.
- Evidence Packet is shared material for the verifier, credit router, recovery policy, and regression harness.
- Evidence Packet must support rollback diagnosis.

### 5.4 Context OS / Working Set Compiler

Context OS compiles long-term information into the working set required by current reasoning.

```text
WorkingSet {
  active_goal
  current_state
  pinned_constraints
  relevant_memory
  branch_context
  evidence_context
  recovery_context
  tool_context
  provenance_index
}
```

**Core operations:**

- retrieve
- rank
- compress
- pin
- evict
- summarize
- reconstruct
- branch-specific pack
- provenance-preserving pack

### 5.5 Episode Journal

Episode Journal is the transaction log of agent behavior.

```text
EpisodeStepStatus =
  PROPOSED
  PENDING
  APPLIED
  ABORTED
  ROLLED_BACK
  RECONCILED
```

It records:

- step identity
- state hash
- action identity
- evidence identity
- verifier result
- commit status
- rollback status
- runtime / tool provenance
- memory write effects

**Core purposes:**

- exactly-once semantics
- replay
- audit
- crash recovery
- failure localization
- safety review

---

## 6. Core Closed Loop

### 6.1 Basic Closed Loop

```text
1. Encode external input into canonical state
2. Form hypothesis
3. Propose candidate plan / action
4. Compile action into Execution IR
5. Pre-verify action safety and feasibility
6. Execute or simulate
7. Collect observation
8. Build Evidence Packet
9. Verify postcondition
10. Commit, abort, retry, or rollback
11. Update memory / context
12. Emit output, confidence, credit, audit artifact
```

### 6.2 Failure Closed Loop

```text
failure detected
  -> collect evidence
  -> assign failure credit
  -> choose recovery target
  -> apply targeted recovery
  -> re-verify
  -> update memory only if write gate accepts
```

**Forbidden patterns:**

- If it is wrong, rerun the entire pipeline.
- If it is wrong, increase search depth.
- If it is wrong, stuff everything into context.
- If it is wrong, lower the verifier threshold.
- If it is wrong, unconditionally write reflection memory.

---

## 7. Failure Taxonomy And Credit Routing

### 7.1 Failure Types

| Code | Type | Agent Semantics |
| --- | --- | --- |
| F_REP | Representation Failure | State representation is wrong, missing, fragmented, or inconsistent |
| F_PROC | Procedural Failure | procedure / plan / action schema is wrong |
| F_SEARCH | Search / Budget Failure | Branching, resources, stopping, or exploration strategy is wrong |
| F_MEM | Memory Failure | Wrong read, missed read, bad write, pollution, or stale memory |
| F_ABS | Abstraction Failure | Wrong abstraction granularity, wrong compression, or macro misuse |
| F_EVAL | Evaluation Failure | verifier, confidence, calibration, or risk judgment is wrong |
| F_EXEC | Execution Governance Failure | action side effect, commit, rollback, replay, or tool provenance is wrong |

> Note: `F_EXEC` is a research hypothesis added by this document for agent runtime. If it is to be included in a formal specification, it should be handled through a Change Proposal and should not directly modify any existing taxonomy.

### 7.2 Credit Vector

```text
failure.credit = {
  representation,
  procedure,
  search_control,
  memory_context,
  abstraction,
  evaluation,
  execution_governance
}
```

The purpose of Credit Routing is not to produce a human explanation, but to decide:

- which layer to redo
- what kind of evidence to add
- whether to expand search
- whether to recompile context
- whether to suppress memory write
- whether to rollback
- which capability surface the loss / feedback should be routed to during training

### 7.3 Targeted Recovery

| Failure | Recovery |
| --- | --- |
| F_REP | Re-normalize observation; rebuild object/relation/event state |
| F_PROC | Re-propose; adjust action schema; reorder procedure |
| F_SEARCH | Delay stopping; re-branch; adjust budget; increase verifier escalation |
| F_MEM | Re-retrieve; lower stale memory weight; prevent polluted writes |
| F_ABS | Adjust compression granularity; disable overly strong macro |
| F_EVAL | Use stricter verifier; calibrate confidence; require more evidence |
| F_EXEC | abort / rollback / reconcile; rebuild action provenance; check side effect |

---

## 8. Memory Theory: Memory Is Not A Database, But A Governed Behavioral Asset

### 8.1 Four Memory Layers

| Memory Layer | Content | Risk |
| --- | --- | --- |
| Working Memory | Information required for the current task | context overstuffing |
| Episodic Memory | Past episode, action, evidence | stale episode reuse |
| Semantic Memory | Abstract knowledge, rules, concepts | overgeneralization |
| Procedural Memory | skills, action schemas, routines | skill misapplication |

### 8.2 Memory Item Schema

```text
MemoryItem {
  id
  type
  content
  embedding
  provenance
  creation_episode
  applicability_conditions
  success_history
  failure_profile
  freshness
  compression_level
  write_gate_score
}
```

### 8.3 Memory Write Gate

Memory writes must have a gate. Write conditions should consider at least:

- evidence quality
- verifier confidence
- recurrence value
- novelty
- failure risk
- provenance completeness
- whether it comes from rollback / failed episode
- whether it may pollute future retrieval

---

## 9. Context OS Theory

### 9.1 Context Is Not A Buffer

Context should be viewed as:

```text
Context = compiled working set for current control state
```

not:

```text
Context = everything possibly useful
```

### 9.2 Working Set Compilation Criteria

| Question | Decision |
| --- | --- |
| Must it exist? | pin |
| Can it be compressed? | summarize |
| Can it be reconstructed? | store pointer |
| Does it need a verifier? | retain evidence |
| Is it branch-specific? | isolate by branch |
| Is it provenance-critical? | preserve source |
| stale risk? | decay or demote |

### 9.3 Context Failure

Common context failures:

- irrelevant context overload
- missing critical evidence
- stale memory reuse
- compressed away constraints
- branch contamination
- unverifiable summary
- lost provenance

These should not be treated only as prompt engineering problems. They should enter Failure Taxonomy and regression metrics.

---

## 10. Verification Theory: Verifier Is A Runtime Service

### 10.1 Verifier Is Not Only The Final Judge

Verifier should cover:

- pre-action feasibility
- pre-action safety
- post-action validity
- branch consistency
- evidence sufficiency
- memory write safety
- rollback legitimacy
- final answer correctness

### 10.2 Verifier Output

```text
VerifierOutput {
  validity_score
  confidence
  calibration_state
  disagreement
  risk_score
  violated_constraints
  required_extra_evidence
  failure_logits
  credit_hints
}
```

### 10.3 False Accept Is More Dangerous Than False Reject

In an agent runtime, false accept is not only a wrong answer. It may lead to:

- wrong tool action being committed
- wrong memory being written
- wrong side effect becoming unrecoverable
- wrong branch being treated as a successful path

Therefore, the main design goal of the verifier should not only be increasing task success, but reducing unsafe / invalid commit.

---

## 11. Execution Governance

### 11.1 Action Side Effect Classes

| Class | Description | Governance |
| --- | --- | --- |
| READ_ONLY | Query, observation | provenance required |
| SIMULATED | Simulated execution | evidence required |
| REVERSIBLE | Reversible change | rollback policy required |
| COMMITTABLE | Change that requires commit | pre/post verification required |
| IRREVERSIBLE | Irreversible external effect | explicit escalation required |
| MEMORY_WRITE | Internal memory update | write gate + provenance required |

### 11.2 Commit Protocol

```text
PROPOSED
  -> PRECHECKED
  -> PENDING
  -> EXECUTED
  -> EVIDENCED
  -> VERIFIED
  -> APPLIED
```

Failure path:

```text
PENDING / EXECUTED
  -> ABORTED
  -> ROLLED_BACK
  -> RECONCILED
```

### 11.3 Replay-Safe Principle

Any replayable episode must preserve:

- action input
- environment/tool version
- runtime manifest
- state hash
- evidence packet
- verifier result
- commit status
- memory write effects

---

## 12. Learning And Training Directions

### 12.1 Pretraining Is Not Only Learning Knowledge, But Learning Process

Agent training should avoid optimizing only the final answer. Core training signals should include:

- representation consistency
- plan/action proposal quality
- verifier calibration
- evidence sufficiency
- recovery correctness
- memory write discipline
- context compilation quality
- rollback / commit correctness
- failure credit stability

### 12.2 Synthetic Data Directions

Synthetic data can support the following capabilities:

| Synthetic Task | Goal |
| --- | --- |
| Delayed Credit Tasks | Make errors appear later and train Credit Routing |
| Recovery Tasks | Teach the model targeted retry rather than blind retry |
| Context Compilation Tasks | Select necessary evidence under limited context |
| Evidence Sufficiency Tasks | Judge when evidence is insufficient |
| Transaction Tasks | Train commit / abort / rollback |
| Memory Pollution Tasks | Judge when memory should not be written |
| Branch Consistency Tasks | Maintain isolation across multiple branch states |
| Tool Provenance Tasks | Identify reliability and version differences in tool output |

### 12.3 Runtime Feedback as Training Signal

Agent runtime can produce high-value training traces:

```text
(state, action, evidence, verifier, credit, recovery, outcome)
```

But it must filter:

- verifier unreliable traces
- tool failure traces
- context polluted traces
- ungrounded reflection traces
- unsafe action traces
- rollback-unresolved traces

---

## 13. Evaluation Theory

### 13.1 Outcome Is A Secondary Metric

The primary evaluation of an agent should not look only at task success, but should inspect process integrity.

### 13.2 Primary Metrics

| Metric | Purpose |
| --- | --- |
| reasoning_to_action_fidelity | Whether a hypothesis is correctly transformed into action |
| evidence_sufficiency_score | Whether evidence is sufficient to support commit |
| verifier_false_accept_rate | Whether an invalid action / answer is accepted |
| verifier_false_reject_rate | Whether a valid path is wrongly rejected |
| credit_routing_entropy | Whether failure attribution degrades |
| targeted_recovery_success | Whether recovery repairs the right layer |
| context_relevance_ratio | Whether the working set is effective |
| context_provenance_loss | Whether context loses its source |
| memory_pollution_rate | Rate of incorrect memory writes |
| rollback_success_rate | Whether rollback is reliable |
| replay_consistency | Whether replay reaches a consistent state |
| unsafe_action_rate | Proportion of unsafe actions |
| commit_integrity_score | Whether commit satisfies pre/post conditions |

### 13.3 Regression Philosophy

If task success rises but any of the following degrade, it should be treated as a regression:

- credit routing collapse
- verifier calibration degradation
- concept / context leakage increase
- memory pollution increase
- false accept increase
- unsafe action increase
- replay inconsistency
- rollback failure increase
- hard-coded control replacement of learned policy

---

## 14. Differences From Mainstream Agent Architectures

| Mainstream Direction | Common Problem | Correction In This Design |
| --- | --- | --- |
| Tool-first agent | Tools become the intelligence locus | Tools are only the execution substrate |
| Prompt workflow agent | The process is not learnable or attributable | learned control + Credit Routing |
| Search-heavy agent | Search hides representation failure | Search is constrained by budget policy and failure attribution |
| Memory-heavy agent | Retrieval replaces understanding | Memory read/write is gated and verified |
| Reflection agent | Reflection pollutes context | Reflection requires evidence + write gate |
| Planner-executor | Executor becomes an external semantic authority | execution effects must be verified and projected |
| Long-context agent | context stuffing | working set compiler |
| Benchmark-optimized agent | Shaped to the test set | benchmark only as probe |

---

## 15. Phased Roadmap

### Stage 0: Lock Conceptual Boundaries

Deliverables:

- State vs Execution boundary note
- Evidence Packet sketch
- Episode Journal sketch
- Failure taxonomy extension proposal
- Context OS design note

Completion criteria:

- No longer confuse reasoning state with execution trace.
- No longer treat tool log as state.
- No longer treat memory append as learning.

### Stage 1: Minimal Closed-Loop Prototype

Goal:

```text
state -> plan -> action -> evidence -> verify -> commit / abort
```

Limits:

- closed toy environment
- no irreversible side effect
- every action replayable
- verifier simple but explicit
- episode journal complete

### Stage 2: Targeted Recovery

Add:

- failure classification
- credit vector
- recovery action selection
- re-verification
- recovery trace logging

Completion criteria:

- The system can distinguish "representation error", "plan error", "verification error", and "memory error."
- Blind retry is no longer the primary recovery strategy.

### Stage 3: Context OS

Add:

- working set compiler
- memory tiers
- retrieval provenance
- compression policy
- context regression metrics

Completion criteria:

- Context relevance rises in long episodes.
- Provenance loss falls.
- Stale memory reuse falls.

### Stage 4: Execution Governance

Add:

- commit protocol
- rollback protocol
- replay tests
- runtime manifest
- side-effect classification

Completion criteria:

- Episode can replay.
- Action can be audited.
- Rollback can be verified.

### Stage 5: Single Vertical Scenario Stress Test

Select one high-value scenario, such as:

- code repair agent
- research assistant agent
- tool-using data analysis agent
- controlled robotics / simulation agent
- document operations agent

Evaluation:

- task success
- evidence quality
- recovery quality
- context scaling
- memory pollution
- replay consistency
- unsafe action rate

---

## 16. Major Risks

### 16.1 False Agentic Progress

The system looks more like an agent, but in reality is only:

- more prompt choreography
- more hard-coded retries
- more tool calls
- more context stuffing
- less learned control

**Prevention:**

- All control must be observable, trainable, and attributable.
- Tool use must be controlled by learned policy.
- Hard-coded policy can only be a technical debt guardrail.

### 16.2 Execution IR Becomes A Second Semantic State

If Execution IR starts carrying reasoning state, it causes state drift.

**Prevention:**

- Execution IR describes only action / dependency / commit / rollback.
- Reasoning state must return to canonical state representation.
- Execution results must flow back through observation / evidence projection.

### 16.3 Memory Pollution

Wrong reflection, wrong tool result, or failed episode is written into long-term memory.

**Prevention:**

- memory write gate
- verifier confidence threshold
- provenance requirement
- failed trace quarantine
- stale memory decay

### 16.4 Verifier Overconfidence

Verifier false accept causes wrong action commit.

**Prevention:**

- verifier disagreement
- calibration tracking
- evidence sufficiency score
- high-risk action escalation
- commit-time recheck

### 16.5 Governance Overhead

Too much journal / manifest / evidence overhead blocks research speed.

**Prevention:**

- phase-based activation
- toy environment first
- minimal schema first
- only govern side-effectful operations initially

---

## 17. Research Hypotheses

### H1: Reasoning-to-action fidelity is the core bottleneck of agent capability

If a model can reason but cannot stably translate actions, the agent remains unusable.

### H2: Evidence Packet can significantly improve verifier reliability

Turning the verifier from a final-answer judge into an evidence-consuming runtime service can reduce false accept.

### H3: Context OS is more important than simply increasing the context window

In long tasks, working set quality affects stability more directly than context length.

### H4: Failure credit routing can improve recovery efficiency

Targeted recovery is cheaper than blind retry, pollutes memory less, and is more interpretable.

### H5: Episode governance is the core foundation of agent safety

Agents without commit / rollback / replay semantics for side effects are difficult to deploy reliably.

---

## 18. Final Design Manifesto

This design argues:

> The core of next-generation agents is not "longer reasoning chains" or "more tool calls," but composing reasoning, action, evidence, verification, memory, commit, rollback, and recovery into a learnable, observable, auditable, replayable closed loop.

It should avoid the following degenerations:

- not a tool-first dispatcher
- not a symbolic executor wrapper
- not a prompt workflow
- not a search-only planner
- not a memory retrieval system
- not a benchmark-shaped system
- not engineering patchwork

It should become:

```text
Cognition-centered
Execution-aware
Evidence-grounded
Context-governed
Memory-disciplined
Failure-attributable
Replay-safe
Learnable-control-first
```

---

## 19. Reference Research

The following literature and research directions are the main external context absorbed by this document.

1. **ReAct: Synergizing Reasoning and Acting in Language Models**  
   https://arxiv.org/abs/2210.03629

2. **Toolformer: Language Models Can Teach Themselves to Use Tools**  
   https://arxiv.org/abs/2302.04761

3. **Tree of Thoughts: Deliberate Problem Solving with Large Language Models**  
   https://arxiv.org/abs/2305.10601

4. **Graph of Thoughts: Solving Elaborate Problems with Large Language Models**  
   https://arxiv.org/abs/2308.09687

5. **Language Agent Tree Search Unifies Reasoning Acting and Planning in Language Models**  
   https://arxiv.org/abs/2310.04406

6. **Reflexion: Language Agents with Verbal Reinforcement Learning**  
   https://arxiv.org/abs/2303.11366

7. **Self-Refine: Iterative Refinement with Self-Feedback**  
   https://arxiv.org/abs/2303.17651

8. **Voyager: An Open-Ended Embodied Agent with Large Language Models**  
   https://arxiv.org/abs/2305.16291

9. **Generative Agents: Interactive Simulacra of Human Behavior**  
   https://arxiv.org/abs/2304.03442

10. **MemGPT: Towards LLMs as Operating Systems**  
    https://arxiv.org/abs/2310.08560

11. **An LLM Compiler for Parallel Function Calling**  
    https://arxiv.org/abs/2312.04511

12. **Understanding the Planning of LLM Agents: A Survey**  
    https://arxiv.org/abs/2402.02716

13. **A Review of Prominent Paradigms for LLM-Based Agents: Tool Use, Planning, and Feedback Learning**  
    https://arxiv.org/abs/2406.05804

14. **A Survey on LLM Test-Time Compute via Search**  
    https://arxiv.org/abs/2501.10069

15. **Large Language Model Agent: A Survey on Methodology, Applications and Challenges**  
    https://arxiv.org/abs/2503.21460

16. **Agent-SafetyBench: Evaluating the Safety of LLM Agents**  
    https://arxiv.org/abs/2412.14470

---

## 20. Suggested Follow-Up Documents

After this document, it should be split into the following formal documents:

1. `Execution_IR_and_Episode_Semantics.md`
2. `Evidence_Packet_and_Verifier_Runtime.md`
3. `Context_OS_and_Working_Set_Compiler.md`
4. `Agent_Runtime_Governance.md`
5. `Failure_Credit_and_Targeted_Recovery_for_Agents.md`
6. `Agentic_Regression_and_Evaluation_Metrics.md`
7. `Minimal_Closed_Loop_Prototype_Plan.md`

---

## 21. Shortest Version

> An agent is not a model that is better at chatting, but a learnable runtime that can turn internal hypotheses into external actions, turn external actions into evidence, turn evidence into commit or rollback, turn failures into Credit Routing, and turn experience into governed memory.
