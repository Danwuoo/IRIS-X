# Temporary Phase 3 Research Operationalization Plan

Status: **Temporary implementation plan**  
Scope: Research operationalization, comparative research, and first baseline experiment definition  
Architecture authority: None  
Research authority: `research/problem-definition.md` remains the provisional project-level research problem  
Removal condition: Replace or retire this plan after the Phase 3 exit criteria are met and durable research/experiment artifacts describe the resulting operating baseline

## Why Phase 3 Exists

Phase 2 made the repository inspectable, provenance-aware, and operationally maintainable. The current research problem is now explicit enough to guide work, but the repository still lacks the intermediate layer between the project-level proposition and architecture decisions: a concrete bounded task distribution, operational research variables, corpus-backed candidate hypotheses, and a reproducible baseline experiment.

Phase 3 must turn the provisional research problem into an executable research program without prematurely selecting an IRIS-X architecture.

The required progression is:

```text
problem definition
    -> bounded task distribution
    -> task/evaluation contract
    -> operational research variables
    -> candidate mechanisms and competing hypotheses
    -> baseline experiment
    -> empirical evidence
    -> later architecture synthesis
```

Phase 3 must not skip directly from `research/problem-definition.md` to an agent runtime, framework stack, canonical state model, router, verifier architecture, or other final system design.

## Required Outcomes

1. IRIS-X has one explicitly selected initial bounded task distribution suitable for the first research cycle, with alternatives and selection rationale preserved.
2. The selected task distribution has a concrete task/evaluation contract that states what constitutes success, partial success, failure, and sufficient evidence of outcome.
3. The first research cycle declares its operating environment, resource envelope, evaluation horizon, and lifecycle-cost accounting boundary.
4. Task success, evidence status, relevant reliability dimensions, and lifecycle cost are operationalized sufficiently to support a baseline comparison without claiming universal metrics.
5. Candidate mechanisms from predecessor and external sources are compared at the level of problems solved, assumptions, expected effects, failure modes, and falsifiable hypotheses.
6. At least one minimal baseline experiment is fully defined and reproducible. It must compare system configurations without assuming which architecture family should win.
7. The repository clearly distinguishes research observations, hypotheses, experiment definitions, raw results, and interpretation.
8. No Phase 3 artifact is allowed to become a de facto final architecture specification.

## Work Package 1: Select the Initial Bounded Task Distribution

Create an IRIS-X-authored research note for initial task-distribution selection. Prefer a flat `research/` artifact unless implementation evidence shows that a deeper hierarchy has immediate operational value.

The note must inspect plausible task sources or task families already available in the corpus before selecting one. Do not choose a benchmark merely because it is convenient or popular.

Evaluate candidate task distributions against explicit eligibility considerations derived from `research/problem-definition.md`:

- outcome can be judged against a reasonably explicit task contract;
- repeated independent executions are possible;
- the environment can be stated and controlled sufficiently for comparison;
- at least two meaningfully different system configurations can attempt the same tasks;
- resource usage and lifecycle-cost components can be observed or bounded;
- failure, verification, retry, escalation, or recovery phenomena can be exposed where relevant;
- the distribution is bounded enough that success claims do not silently generalize to broad intelligence;
- execution does not require adopting one imported framework as IRIS-X architecture.

Use eligibility gates and evidence-backed qualitative comparison by default. Do not invent a weighted aggregate score unless the weighting itself is justified.

The note must preserve:

- candidate task distributions considered;
- corpus/source IDs and concrete inspected paths;
- source-stated versus directly observed versus inferred claims;
- reasons for rejecting or deferring alternatives;
- known limitations of the selected distribution;
- unresolved questions.

The selected task distribution is a first research vehicle, not the definition of IRIS-X.

## Work Package 2: Define the Task and Evaluation Contract

Create a durable research artifact for the selected task distribution that states the first-cycle comparison boundary.

It must define, at minimum:

### Task instance and distribution

- what constitutes one task instance;
- how instances are sampled or enumerated;
- what distribution or subset is in scope;
- what is explicitly out of scope;
- whether tasks are independent or stateful.

### Outcome status

Define how the task contract distinguishes:

- success;
- partial success, if applicable;
- failure.

Do not use evaluator approval as the definition of empirical truth when independent outcome evidence is available.

### Evidence status

Define what evidence is available to support or reject a claimed outcome, including how the first cycle can distinguish where applicable:

- verified or correctly recognized success;
- unverified success;
- false success;
- false failure;
- correctly recognized failure.

### Execution-path attributes

Record retry, repair, escalation, recovery, and comparable intervention paths separately from outcome and evidence status.

### Operating boundary

Declare:

- operating environment;
- resource envelope;
- evaluation horizon;
- lifecycle-cost accounting boundary;
- workload/deployment assumption used for amortization, if any.

A resource envelope constrains what a system may use. A lifecycle-cost accounting boundary determines which costs are included in a comparison. Keep them distinct.

## Work Package 3: Operationalize the First-Cycle Research Variables

Create a research note that maps the project-level variables to first-cycle observables without claiming universal definitions.

### Task success

State how per-instance outcomes aggregate into task success rate for the selected evaluation sample. Preserve sample size, sampling procedure, exclusions, and uncertainty.

### Evidence/epistemic status

State how evidence judgments are produced and audited. If a verifier is used, treat verifier output as evidence, not automatic truth.

### Long-term reliability

Select only the reliability dimensions that the first task distribution can meaningfully test. Consider the existing umbrella dimensions:

- operational reliability;
- stateful reliability;
- robustness;
- change reliability / maintainability;
- recovery reliability.

For dimensions that cannot yet be tested, mark them `Not evaluated` rather than inventing proxy metrics.

Do not force the selected reliability dimensions into one scalar unless the research evidence justifies aggregation.

### Lifecycle cost

Declare the concrete first-cycle accounting fields. Depending on what is observable, these may include:

- model/token/compute usage;
- tool/environment cost;
- verifier/evaluation cost;
- retry/recovery cost;
- escalation cost;
- latency/throughput fields;
- design-time optimization or specialization cost;
- maintenance/remediation cost.

Unknown or unavailable cost components must remain explicit. Do not equate per-call inference price with lifecycle cost.

## Work Package 4: Build the Candidate-Mechanism Comparison

Create a comparative research note grounded in the original corpus.

Inspect relevant predecessor and external sources before summarizing them. At minimum, consider the systems that materially overlap with the selected task and first-cycle variables. Potentially relevant source families include, without making them mandatory dependencies:

- IRIS: state representation, learned control, attribution, recovery;
- EIDOS: epistemic governance, provenance, authority, typed research records;
- SPEX: measurement, evidence, comparison, adjudication;
- VANTA: controlled execution, verification, commit/rollback/replay/recovery;
- Prime Agent: stateful and long-running execution;
- Prime Intellect Verifiers: tasksets, harnesses, traces, rollouts, verification/evaluation interfaces;
- NeMo Agent Toolkit: instrumentation, profiling, observability, evaluation, optimization;
- DSPy: declarative LM programs and program optimization;
- GEPA: trace-informed reflective optimization and Pareto-efficient search;
- AFlow: automatic workflow generation and evaluation-guided search;
- Agent Lightning: agent training interfaces;
- FrugalGPT and RouteLLM: budget-aware model selection, cascades, and routing.

For each mechanism actually included in the comparison, record:

```text
research problem addressed
source-stated mechanism
required assumptions
expected effect on success / evidence / reliability / cost
likely failure modes or trade-offs
what is reusable substrate vs potential IRIS-X research contribution
falsifiable hypothesis for the selected task distribution
minimum experiment needed to distinguish the hypothesis
```

Do not collapse coupled predecessor mechanisms into one indivisible architecture. Separate hypotheses where comparison allows it.

The output is a hypothesis/comparison map, not an architecture recommendation.

## Work Package 5: Define the First Baseline Experiment

Create the first experiment under `experiments/` using the scoped experiment rules. Introduce only the directory structure immediately needed by the experiment.

The baseline must answer a narrow question before testing sophisticated mechanisms. Prefer the smallest comparison that establishes an empirical reference frontier for the selected task distribution.

The definition should normally compare at least two system configurations that differ in an interpretable capability/cost dimension. Examples include a cheaper and a stronger general-purpose model, or another pair justified by the available environment. Do not assume these exact configurations if the selected task or available infrastructure makes a different minimal baseline more defensible.

The experiment definition must specify:

- experiment ID and status;
- research question and hypothesis/null comparison where appropriate;
- selected task distribution and task-contract artifact;
- exact configurations being compared;
- fixed versus variable system components;
- operating environment and resource envelope;
- sampling/repetition procedure;
- success and evidence recording procedure;
- relevant reliability observations;
- lifecycle-cost fields and accounting boundary;
- failure recording;
- commands or procedures required to execute;
- expected raw-output location or handling policy;
- interpretation boundary;
- stop conditions and invalid-run conditions.

The experiment must be designed so later mechanism experiments can add one meaningful intervention at a time, for example verification, retry/recovery, routing/escalation, prompt/program optimization, workflow optimization, or specialization.

### Execution policy

If the baseline can be executed reproducibly with available local resources and without new paid services, credentials, destructive actions, or unapproved external side effects, execute a small smoke/pilot run and record it according to `experiments/AGENTS.md`.

If execution requires unavailable credentials, paid model/API usage, external service mutation, or owner approval, do not fabricate results and do not silently incur cost. Leave the experiment in a clearly marked `defined / not run` state and record the exact blocker and execution command/procedure.

A successful smoke run is evidence that the harness executes, not evidence that any architecture hypothesis is established.

## Work Package 6: Navigation and Research Traceability

Update only the durable navigation needed to make the new research artifacts discoverable.

At minimum, review whether the following need concise links or status updates:

- `research/README.md`;
- `experiments/README.md`;
- root `README.md` only if the repository-level starting workflow materially changes.

Do not turn navigation files into duplicated research content.

Each research artifact must follow `research/AGENTS.md` and distinguish source-stated, directly observed, inferred, and unknown claims. Use stable corpus IDs plus concrete evidence paths.

Each experiment artifact must follow `experiments/AGENTS.md` and keep definitions, inputs, raw outputs, reviewed results, and interpretation distinguishable.

## Non-Goals

- No final IRIS-X architecture, runtime, framework stack, product boundary, or ontology.
- No implementation of a new general agent runtime merely to make Phase 3 look complete.
- No adoption of Prime Agent, DSPy, GEPA, AFlow, NeMo Agent Toolkit, or another imported system as the default IRIS-X architecture.
- No refactoring or stylistic cleanup inside imported source trees.
- No claim that the first task distribution represents general agentic intelligence.
- No claim that a benchmark score proves long-term reliability.
- No universal scalar success-reliability-cost score unless justified by evidence.
- No invented task thresholds, reliability thresholds, upstream behavior, costs, or experiment results.
- No paid API/model execution or external side effects without explicit owner approval.
- No large placeholder hierarchy or speculative implementation scaffolding.

## Execution Order

1. Read root `AGENTS.md`, `research/AGENTS.md`, `experiments/AGENTS.md`, `research/problem-definition.md`, corpus navigation/provenance documentation, and this plan.
2. Inspect candidate task sources and write the initial task-distribution selection note.
3. Define the selected task/evaluation contract and comparison boundary.
4. Operationalize first-cycle success, evidence, applicable reliability dimensions, and lifecycle-cost fields.
5. Inspect relevant original corpus sources and produce the candidate-mechanism comparison with falsifiable hypotheses.
6. Define the minimal baseline experiment and any immediately necessary experiment inputs/scaffolding.
7. Execute only a safe, reproducible no-new-cost smoke/pilot run when possible; otherwise record the exact execution blocker without fabricating results.
8. Update minimal research/experiment navigation.
9. Run repository validation and review the complete diff for accidental imported-source edits or premature architecture commitments.

## Exit Criteria

Phase 3 is complete only when all of the following are true:

- one initial bounded task distribution is selected with evidence-backed rationale and documented alternatives;
- one task/evaluation contract defines the first-cycle outcome, evidence, operating, resource, horizon, and cost boundaries;
- first-cycle research variables are operationalized without pretending unresolved universal metrics are established;
- at least one comparative note maps relevant corpus mechanisms to assumptions, trade-offs, failure modes, and falsifiable hypotheses;
- at least one baseline experiment is fully defined and reproducible from repository artifacts;
- any executed pilot has reproducible procedures and clearly separated raw result/interpretation, or the experiment explicitly records why it was not run;
- research and experiment navigation points to the new artifacts;
- imported source and paper content remains unchanged;
- `python tools\repository_check.py` passes from repository root;
- repository diff contains no final architecture specification disguised as a research artifact;
- unresolved questions remain explicitly labeled rather than filled with assumptions.

Meeting these criteria makes IRIS-X ready for evidence-producing mechanism experiments. It does not authorize final architecture synthesis by itself.

## Post-Phase Decision Gate

After Phase 3, review the evidence and experiment readiness before choosing the next phase.

The normal next step should be mechanism experiments that test whether individual interventions move the empirical success-reliability-cost frontier. Architecture synthesis should begin only when enough supported constraints exist to justify architecture requirements.

Possible later progression:

```text
Phase 3: research operationalization + baseline
Phase 4: mechanism experiments and comparative results
Phase 5: supported constraints and architecture synthesis
```

These later phase labels are provisional and are not commitments to a fixed roadmap.

## Verification

Run at minimum:

```powershell
python tools\repository_check.py
```

If Phase 3 adds or changes Python code, also run targeted tests and:

```powershell
python -m py_compile <changed-python-files>
```

If existing repository tooling provides additional relevant self-tests, run them as appropriate. Report executed commands and their outcomes; do not claim checks that were not run.

## Implementation Judgment

The implementing task may adjust exact authored filenames, task candidates, or minimal experiment layout when repository evidence makes a different choice materially clearer. It must preserve the research progression, evidence discipline, non-goals, and exit criteria above.

When evidence is incomplete, prefer `Unknown`, `Unclear`, `Not established`, `Not evaluated`, or `Conflicting evidence` over a guessed answer.

Do not ask the owner to choose among implementation details that can be resolved by inspecting the repository. Ask only when execution requires unavailable secrets, paid-resource approval, destructive action, or a genuinely owner-only research decision.
