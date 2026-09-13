# IRIS-X Foundational Research Synthesis

- **ID:** note-2026-09-13-foundational-research-synthesis
- **Status:** adjudicated foundational synthesis; provisional and falsifiable; no execution authority
- **Date:** 2026-09-13
- **Scope:** reconstruct the preserved Phase 1–6 research chain, compare materially distinct scientific formulations, and state the narrowest defensible IRIS-X research center
- **Non-scope:** no Phase 7, repository-launched or follow-on model/provider execution, authorized experiment, runtime mechanism, framework selection, productionization, or follow-on task
- **Controlling synthesis contract:** [single Ultra session contract](pre-synthesis-readiness/ultra-session-contract.md)
- **Evidence cutoff:** repository state at commit d4e95e2a7b6f7ab8f08f4c5b76a02cbc8eb1f3b3
- **Authoring topology:** one owner-authorized GPT-5.6 Sol Ultra synthesis session; repository-launched or follow-on model/provider executions: 0

## Executive adjudication

The evidence does **not** justify one monolithic thesis in which task success, reliability, capability, cost, attribution, optimization, and long-running state are treated as a single phenomenon. It supports a plural but ordered research structure.

1. **Supported foundational center — evidence-governed warranted agency.** For a declared task, configuration, verifier, action boundary, and horizon, actual outcome, producer claim, evidence validity and binding, authority, acceptance, verified-success eligibility, and state transition must remain separately observable and correctly related. A successful outcome alone does not justify belief in success, and an observed failure alone does not justify a model-level or intervention-level explanation. This center has the strongest direct support because Phase 4 experimentally separated outcome from acceptance and evidence, while Phase 6 showed that even correct terminal observations can yield the wrong research predicate when provenance and authority are misbound.

2. **Emerging decision program — minimum-sufficient configuration followed by failure-directed intervention.** Minimum-sufficient capability is best treated as a property of a frozen task/configuration/distribution/horizon, not as an intrinsic model label. A single miss can establish bounded configuration pressure, but cannot establish repeatability, intrinsic model incapability, or the benefit of retry, recovery, routing, escalation, workflow search, or a stronger model. Configuration sufficiency and intervention choice are therefore adjacent but distinct questions; they may share an evidence program without being collapsed into one construct.

3. **Deferred alternative — temporal and state-transition reliability.** Process lifetime, restoration, and targeted recovery have bounded deterministic support. Persistent agent state, crash/restart continuity, remote mutable state, and days-or-weeks reliability remain scientifically open. Current direct evidence triggers no persistence capability gate, so long-running state is not justified as the present foundational center.

The prior success–reliability–lifecycle-cost proposition remains useful as a **decision envelope**, not as a unified explanandum. Success is an outcome; reliability is presently a vector of claim-specific and mechanism-specific properties; cost is a boundary-dependent decision criterion whose monetary lifecycle form is not yet measured.

## 1. Authority, baseline, and method

### 1.1 Baseline reconciliation before interpretation

The [pre-synthesis baseline manifest](pre-synthesis-readiness/baseline-manifest.json) records execution-start commit db053dcc9c614965bcaeeb96d28ebd6a57c967fa. The present repository is at d4e95e2a7b6f7ab8f08f4c5b76a02cbc8eb1f3b3. The sole intervening commit is the pre-synthesis readiness package. All 15 critical file hashes and Git blob identities match the manifest, and the protected trees for sources, references/papers, and experiments match their recorded tree identities. Both the readiness validator and repository checker passed before synthesis.

This is expected commit-level drift, not scientific-authority drift. No preserved source, paper, experiment, terminal record, or Phase 4–6 decision artifact changed between the frozen baseline and this interpretation.

### 1.2 Evidence classes used here

| Evidence class | Meaning in this synthesis | Permitted inferential force |
|---|---|---|
| directly_observed | A preserved IRIS-X run, terminal record, deterministic comparison, validation record, or repository identity observation | Supports only the recorded task, configuration, environment, comparison, and horizon |
| source_stated | A predecessor or external primary repository/paper states a design, result, interpretation, or limitation | Supports faithful description of that source; not an IRIS-X empirical result |
| inferred | A relationship reconstructed across authorities in this document | Must expose premises, scope, counterevidence, and falsifiers |
| unknown / Not established / Not evaluated | Evidence is unavailable, insufficient, inapplicable, or absent | Must not be converted to false, zero, or a negative result |

### 1.3 Independence and double-counting policy

- A direct result, its result note, its closure note, and the later state summary are one evidence chain, not four replications.
- A paper and its preserved implementation are normally one research lineage unless an independent reproduction is present.
- A predecessor design assertion and an IRIS-X synthesis that cites it are not independent empirical supports.
- Multiple deterministic fixtures can share generators, validators, acceptance predicates, and failure modes; episode count is not an independence count.
- Batch 2 Result C, historical Batch 3 Result D, and the separate post-Batch-3 Result A authority repair retain their original identities. The repair does not retrospectively reclassify Batch 3.

### 1.4 Research method

The synthesis used the readiness [source interface](pre-synthesis-readiness/source-interface.yaml), [evidence ledger](pre-synthesis-readiness/phase-evidence-ledger.yaml), [construct map](pre-synthesis-readiness/construct-map.yaml), [tension matrix](pre-synthesis-readiness/assumption-tension-matrix.md), [claim index](pre-synthesis-readiness/claim-evidence-index.jsonl), and [candidate template](pre-synthesis-readiness/candidate-formulation-template.md) as navigation aids, then checked formulation-defining claims against direct experiment artifacts and primary repository or paper authorities. It first reconstructed what the evidence can and cannot support, then generated four candidates, subjected each to the same adversarial template, compared them without scalar scoring, and only then formulated a thesis, research questions, hypotheses, and an unexecuted discriminating evidence program.

## 2. Claim-level reconstruction of the evidence chain

### 2.1 Phases 1 and 2: research boundaries and preserved identity

Phase 1 made a governance decision to separate imported predecessors, external references, papers, and IRIS-X-authored work. [Repository-separation decision](../docs/decisions/0001-separate-imported-corpus.md) This established an editable/preserved boundary, not an architecture, ontology, runtime, or research thesis.

Phase 2 directly established that the local registries identify 13 source trees and seven paper artifacts with stable IDs, paths, snapshot or fingerprint data, and explicit provenance limits. [Source registry](../corpus/sources.yaml), [artifact registry](../corpus/artifacts.yaml), [provenance policy](../corpus/PROVENANCE.md) This supports local retrieval and byte identity only. Most exact upstream revisions and acquisition histories remain Unknown, and fingerprints do not establish completeness, license clearance, upstream equivalence, or scientific validity.

The success–reliability–lifecycle-cost [problem definition](problem-definition.md) originated as a revisable Phase 2–6 prior. Its own scope withholds final thresholds, a unified reliability measure, a final cost boundary, and final research authority. This synthesis therefore treats it as a candidate decision envelope rather than evidence for itself.

### 2.2 Phase 3 and Phase 4: what was directly learned

| Evidence item | Direct observation | Defensible implication | Boundary or counterevidence |
|---|---|---|---|
| Corrected read-only pilot | The structured control completed 36/36 deterministic cases; the literal control completed 21/36 across 72 valid episodes. The original attempt remains failed because manifest serialization raised a NameError even though result generation completed. [Corrected results](../experiments/exp-2026-08-28-docops-readonly-baseline/runs/pilot-20260828-local-rerun-01/results.json) | Configuration structure can materially change bounded task success; terminal research status must not be inferred from partial result presence | Same local deterministic environment; most lifecycle-cost components unknown; no general model claim |
| H-M1a snapshot identity | Treatment detected all 12 content-identity mismatches with zero false decisions; record-only comparison missed all 12. [Results](../experiments/exp-2026-08-30-source-snapshot-assertion/runs/hm1a-20260830-local-01/results.json) | A claimed or recorded identity is not equivalent to recomputing source identity | Twelve frozen local cases; no distributed or mutable-upstream identity result |
| H-V1a independent semantic verification | Claim-only acceptance falsely accepted 108 invalid outputs. Independent deterministic verification reduced false accepts to 0 while retaining all 72 valid accepts across 360 records. [Results](../experiments/exp-2026-08-30-docops-acceptance-verification/runs/hv1a-20260830-local-01/results.json) | Producer assertion and independently justified acceptance are non-equivalent | Oracle was deterministic and fixture-specific; learned, human, adversarial, and ambiguous evaluation remain open |
| H-V1b evidence binding | All 576 actual outcomes were successful and passed semantic verification. Evidence-bound adjudication denied verified-success status to all 252 missing, stale, crossed, unrelated, or conflicting evidence cases; semantic-only adjudication falsely treated those 252 as verified success. [Results](../experiments/exp-2026-08-30-docops-evidence-binding/runs/hv1b-20260830-local-01/results.json) | Outcome success and justified belief in that success can diverge while the underlying outcome is held fixed | Does not establish universal evidence sufficiency or the correctness of every verifier |
| H-I1a pre-execution interception | Pre-execution policy prevented all 18 prohibited mutations; post-hoc detection allowed all 18 mutations before detecting them. Six permitted controls passed. [Results](../experiments/exp-2026-08-30-preexecution-write-interception/runs/hi1a-20260830-local-01/results.json) | Prevention, post-hoc detection, and outcome observation are distinct intervention points | Local copied workspace; no remote, irreversible, or externally visible effects |
| H-O1a observability profile | Declared-field coverage increased from 0/612 to 612/612 with paired outcome invariance. Timing effects were mixed: 21 positive and 15 negative deltas. [Results](../experiments/exp-2026-08-30-docops-profile-instrumentation/runs/ho1a-20260830-local-01/results.json) | Instrumentation can improve reconstructability without changing these outcomes | No directional overhead benefit; the 17-field profile is not universal |
| H-OR1a process lifetime | All 480 deterministic cases succeeded with no sequence drift across fresh and long-lived local processes. [Results](../experiments/exp-2026-08-31-process-lifetime-stability/runs/hor1a-20260901-local-01/results.json) | This bounded substrate did not degrade over its tested process horizon | Not crash/restart, model/provider drift, stochastic execution, or days/weeks reliability |
| H-SR1a reversible cycles | All 120 copied-workspace cycles restored exact baseline state. [Results](../experiments/exp-2026-08-31-reversible-cycle-state-stability/runs/hsr1a-20260901-local-01/results.json) | Exact restoration is attainable for the tested reversible state class | Not general persistence, remote state, compensation, or concurrent mutation |
| H-RCV1a targeted recovery | Targeted recovery produced valid final state in 15/15 injected failures; detect-only produced valid final state in 0/15 across five frozen failure states. [Results](../experiments/exp-2026-08-31-targeted-recovery-valid-state/runs/hrcv1a-20260901-local-01/results.json) | Detection alone is not recovery; a failure-specific intervention can change final-state validity | Does not show that recovery improves arbitrary tasks or that the taxonomy selects treatments correctly outside fixtures |
| H-P1a structured specialization | The frozen optimized Luna program completed 32/32 blind items, versus 18/32 for the Luna seed and 23/32 for the Terra seed. C1 had no false successes; C0 had 14 and C2 had 9. [Results](../experiments/exp-2026-09-01-luna-structured-program-specialization/runs/blind-20260902-chatgpt-03/results.json) | A task-specific configuration can outperform weaker and stronger-reference seed configurations on a finite deterministic corpus | This is configuration-level evidence, not model equivalence. Monetary provider cost is Unknown; 382 design-plus-runtime calls, 6.23 million input tokens, 61,334 output tokens, and substantial wall time preclude a lifecycle-cost conclusion |
| H-P1a invalid attempts | One attempt produced 26 provider schema errors and no candidate; another failed pre-invocation path normalization with zero model calls. [Phase 4 closure](phase-4-closure.md) | Optimization success must include invalid attempts and admission failures in its research record | The successful attempt cannot erase process fragility or establish repeatable optimization |

Phase 4 therefore validates several separate trust, control, recovery, identity, observability, and bounded-specialization properties. It does not validate a general or scalar reliability construct, a final architecture, long-term reliability, complete lifecycle cost, or a universal specialization law.

### 2.3 Phase 5: operationalized boundaries, not a thesis result

Phase 5 translated the Phase 4 distinctions into a provisional execution slice: immutable identity, contract-bound evidence, producer/verifier separation, canonical adjudication, conditional pre-mutation policy, and separate resource records. These are operational hypotheses about preserving evidential distinctions, not proof that a particular runtime architecture is scientifically necessary.

Qualification runs 01 and 02 ended in configuration/adapter failures; run 03 was a verified success. Three task-family runs—filtering, aggregation, and ranking—were all verified successes under the same admitted Luna/tool-free configuration, with zero retries, routes, escalations, recoveries, or tool calls. [Qualification run 03](../experiments/substrates/model-execution-qualification-v0/runs/qualification-20260905-03/terminal-record.json), [filter terminal](../experiments/substrates/model-execution-qualification-v0/task-family/runs/task-family-20260906-a-filter/terminal-record.json), [aggregation terminal](../experiments/substrates/model-execution-qualification-v0/task-family/runs/task-family-20260906-b-aggregation/terminal-record.json), [ranking terminal](../experiments/substrates/model-execution-qualification-v0/task-family/runs/task-family-20260906-c-ranking/terminal-record.json)

The direct terminals support a limited lineage of successful task/configuration observations. They do not establish general capability, repeatability under provider change, lifecycle cost, or a need for any of the eight deferred capability mechanisms.

### 2.4 Phase 6: pressure, attribution, and authority

**Batch 1 instrument.** The deterministic capability-pressure and failure-attribution instrument produced all 34 expected assessments, preserved two designed ambiguity collisions, and recognized eight synthetic positive fixtures while leaving the direct-evidence gate ledger empty. Synthetic positives validate instrument behavior; they are not real-task capability evidence. [Phase 6 instrument report](phase-6-capability-pressure-and-failure-attribution.md)

**Batch 2 Result C.** P1–P3 were verified successes. P4 was a systemic failure with no usable provider result, so task-semantic pressure was Not established and P5–P6 remained unattempted. The batch is an uninterpretable sampling-path negative result, not a capability miss. [Batch 2 summary](../experiments/phase-6-pressure-sampling-v0/runs/batch-2/summary.json), [P4 terminal](../experiments/phase-6-pressure-sampling-v0/runs/batch-2/p4-dependency/terminal-record.json)

**Batch 3 historical Result D.** All six provider executions were accepted and usable. P1, P2, P3, P5, and P6 were verified successes. P4 was a semantic miss located at execution_producer/task_success, directly supporting a frozen-configuration shortfall and task-level pressure. Intrinsic model incapability, stronger-model benefit, retry benefit, routing benefit, and recovery benefit remained Not established. Model-inference execution detail and provider monetary cost remained Unknown. [Batch 3 summary](../experiments/phase-6-pressure-sampling-v0/runs/batch-3/summary.json), [P4 terminal](../experiments/phase-6-pressure-sampling-v0/runs/batch-3/p4-dependency/terminal-record.json)

**Separate post-Batch-3 Result A authority repair.** The historical derivation bound H-C1 to Batch 2 sources and used the wrong predicate operator. The repair bound six exact Batch 3 terminal paths, hashes, and pointers, producing the task-pressure vector false, false, false, true, false, false. It correctly derived cheaper_admitted_configuration_misses_requirement as true while keeping stronger resolution, decision-relevant trade-off, and retry/recovery comparison unknown. [Direct predicates](../experiments/phase-6-predicate-authority-repair-v0/runs/authority-repair-20260910/direct-predicates.json), [gate adjudication](../experiments/phase-6-predicate-authority-repair-v0/runs/authority-repair-20260910/gate-adjudication.json), [validation](../experiments/phase-6-predicate-authority-repair-v0/runs/authority-repair-20260910/validation-record.json)

The exact comparison predicates stronger_candidate_resolves_miss, decision_relevant_tradeoff_established, and bounded_retry_or_recovery_benefit_compared remain **unknown**. Their absence is neither negative evidence nor permission to fill them from intuition.

The repair's 10 focused tests and its Phase 6/Phase 5 focused suites passed. The full discovered inventory remained 281/282 because HPIaContractTests.test_frozen_artifact_hashes_match_exact_bytes still records the pre-existing hash mismatch for docs/plans/TEMP_PHASE_4_FINAL_MODEL_SPECIALIZATION_AND_CLOSURE.md. The validation record marks that sole failure unchanged from baseline, with zero new errors and zero new failures; it is preserved rather than normalized away.

The final all-eight-gate state is preserved exactly:

| Gate family | Status | Reason |
|---|---|---|
| H-C1 cascade/escalation | insufficient_or_ambiguous | One bounded cheap-configuration miss exists; stronger-resolution benefit and decision-relevant trade-off remain unknown |
| Retry/recovery comparison | insufficient_or_ambiguous | No direct paired intervention comparison for the Batch 3 pressure case |
| H-G1 optimization method | not_triggered | No direct need or comparative benefit established |
| H-W1 workflow search | not_triggered | No evidence that fixed/simple control flow caused the miss |
| H-R1 routing/allocation | not_triggered | No direct allocation comparison or heterogeneous-benefit result |
| Persistent/long-running state | not_triggered | No task requirement or direct pressure supporting persistence |
| Nondeterministic verifier | not_triggered | Direct evidence did not establish that the deterministic oracle was insufficient for the sampled tasks |
| Remote/external action control | not_triggered | Current direct tasks did not require such actions |

Zero of eight gates are triggered. Unknown and insufficient_or_ambiguous are not false and are not authorization to implement a mechanism.

## 3. Construct reconstruction and deliberate non-equivalences

The readiness [construct map](pre-synthesis-readiness/construct-map.yaml) exposes 19 overloaded constructs. This synthesis adopts the following working stipulations only for the present claim set; it does not impose a final ontology.

| Construct | Working use after adjudication | Deliberate non-equivalences |
|---|---|---|
| Task success | Satisfaction of a frozen task-specific outcome predicate | Not producer claim, verifier acceptance, evidence validity, verified success, reward, or reliability |
| Verified-success eligibility | An adjudicated relation among successful outcome, valid/bound evidence, and correct authority | Not proof of general correctness or future success |
| Reliability | A vector of explicitly named properties with separate units and horizons | Not a scalar synonym for accuracy, pass rate, safety, availability, or repeatability |
| Capability | Ability of a declared configuration to meet a declared requirement under a stated verifier | Not automatically intrinsic to a model, stable across prompts/tools, or general intelligence |
| Sufficient capability | Distribution- and horizon-level adequacy justified by repeated evidence and a decision boundary | Not one successful episode, one miss, a small model, or an admitted configuration |
| Evidence | A claim-relevant, provenance-bearing observation or artifact whose authority and independence are explicit | Not any existing file, trace, citation, or model explanation |
| Verification | A claim-specific check against an independently grounded criterion where independence is itself recorded | Not all evaluation, validation, reward, or judge output |
| Provenance | Identity and lineage of the evidence used for a claim | Not authority, truth, scientific validity, or source independence |
| Authority | The rule determining which observation may set a predicate | Not recency, polish, consensus, or provenance alone |
| Failure | A typed shortfall at a declared lifecycle locus | Not one generic negative status and not necessarily model incapability |
| Attribution | A supported relation between a shortfall and its locus or cause | Stage localization is weaker than causal attribution and weaker than intervention benefit |
| Specialization | A change to model, prompt, program, tools, workflow, or configuration for a bounded objective | These mechanisms are not interchangeable and their costs differ |
| State | Must be qualified as internal cognitive state, session/context state, external mutable state, or research-governance state | These scopes have different persistence, recovery, and evidence obligations |
| Recovery | A post-failure transition toward a declared valid state | Not retry, prevention, detection, replanning, or task success |
| Cost | A named resource or consequence under a declared accounting boundary | Provider price, tokens, latency, engineering effort, failure risk, and lifecycle cost are not fungible without a rule |
| Intervention point | The lifecycle stage at which a mechanism can alter an outcome or state | Design-time optimization, pre-action prevention, runtime allocation, retry, and recovery are not equivalent |

### 3.1 Adjudication of the twelve readiness tensions

| Tension | Adjudication |
|---|---|
| Unit of analysis | Preserve request, claim, task execution, configuration, workflow candidate, trajectory, and maintenance process as separate units. Any aggregation needs an explicit bridge. |
| One-shot vs lifecycle horizon | One-shot results establish observations; repeated or durable claims require their own horizons and change processes. |
| Deterministic vs learned/model/human judgment | Evaluator class is a first-class variable. Deterministic fixture results do not transfer evaluator validity to learned or human judges. |
| Model vs system/configuration capability | Current direct pressure is configuration-level. Intrinsic model incapability remains Not established. |
| Design-time vs runtime intervention | Keep separate. Offline search evidence cannot justify online escalation, and runtime allocation evidence cannot justify a design-time optimizer. |
| Specialization vs general capability | No general law is established. Specialization claims remain task/distribution/configuration bound. |
| Inference vs lifecycle cost | Inference price is one cost component. Complete lifecycle cost remains Not established. |
| Stateful vs stateless execution | Treat state as conditional on a task requirement; do not make persistence core without evidence of necessity. |
| Successful execution vs justified belief | This is a demonstrated contradiction on the Phase 4 fixtures and is central to the supported formulation. |
| Reward/benchmark performance vs reliability | Keep reward as an outcome measure. It does not subsume evidence, action control, recovery, or temporal validity. |
| Prevention vs detection/recovery | Preserve all three intervention points; Phase 4 directly shows they produce non-equivalent states. |
| Local immutable vs remote/mutable provenance | Local byte identity is established; upstream origin, current upstream behavior, and remote mutability are often Unknown. |

## 4. Materially distinct candidate formulations

The candidates below use the complete readiness template. Their initial status is intentionally symmetric; their dispositions were filled only after all four were compared.

### Candidate F1 — Evidence-governed warranted agency

- **Candidate ID:** F1
- **Status:** proposed for adversarial comparison; not selected at formulation time
- **Formulation family:** epistemic control and authority-correct adjudication
- **Materially distinct from candidates:** F2 explains bounded configuration adequacy, F3 explains treatment choice after failure, and F4 explains reliability over state transitions and time. F1 explains when an observed result or derived decision is warranted.

#### Explanandum

Why can the same actual task outcome be correctly or incorrectly accepted, and why can correct terminal observations still support a wrong research predicate? Without F1, the 108 claim-only false accepts, 252 semantically successful but evidence-invalid cases, and the Phase 6 provenance/authority defect are isolated data-cleaning bugs rather than instances of a common scientific phenomenon: breakdown of the relation between world state, evidence, authority, and justified system commitment.

#### Unit of Analysis and Horizon

The primary unit is a claim–evidence–authority–adjudication tuple for one terminal task execution or one derived research predicate. The immediate horizon extends from frozen identity through outcome observation to acceptance or intervention decision. Aggregation is permitted only over tuples governed by the same task contract, verifier class, authority rule, and change horizon.

#### Core Constructs

Outcome is the independently observed task state. Producer claim is the executor's assertion. Evidence validity concerns whether an artifact satisfies its own requirements; evidence binding concerns whether it belongs to the claimed task/execution. Authority determines which observation may set a predicate. Acceptance is the adjudicator's decision. Verified-success eligibility is a relation among successful outcome, valid/bound evidence, and authority-correct acceptance. Reliability remains a vector. This deliberately narrows Eidos-style authority and VANTA-style evidence packets to claim-specific relations rather than importing their broader governance or runtime ontologies. [Eidos README](../sources/predecessors/eidos/README.md), [VANTA verifier specification](../sources/predecessors/vanta/docs/02_specs/Evidence_Packet_and_Verifier_Runtime.md)

#### Causal or Mechanistic Structure

A producer acts and emits a claim plus candidate evidence. An authority-independent verifier measures task semantics and evidence binding. An adjudicator applies a frozen rule. Identity corruption, verifier dependence, evidence misbinding, or wrong authority can each change acceptance while leaving actual outcome unchanged. Conversely, outcome can change while evidence or acceptance remains stale. Model-intrinsic capability is neither required nor inferred by this structure.

#### Scientific Nontriviality

The problem is not merely how to serialize traces. It asks which relations are necessary and sufficient for an agent system to transform observations into justified commitments under fallible producers, mutable artifacts, and competing authorities. The phenomenon admits counterexamples, interventions, false-positive and false-negative measures, and cross-evaluator generalization tests.

#### Relationship to Success, Reliability, and Cost

Task success is an outcome, not the explanandum. Warranted acceptance is one reliability dimension, alongside identity integrity and action control. Verification, evidence capture, abstention, and false commitment carry costs; these are constraints and decision criteria. No unified cost or reliability scalar is assumed.

#### Relationship to Phase 1–6 Evidence

Direct support comes from H-M1a, H-V1a, H-V1b, and the Phase 6 authority repair. H-I1a indirectly supports the importance of decision timing. Phase 5 operationalizes the relation but is not independent validation. H-P1a and the Batch 3 P4 miss are neutral about F1's sufficiency, while their correct interpretation depends on it. The principal challenge is that the strongest experiments are deterministic local fixtures.

#### Primary Source Support

The direct authorities are the H-M1a, H-V1a, H-V1b result artifacts and the post-Batch-3 direct-predicate and gate-adjudication artifacts cited above. Eidos supplies source-stated typed authority concepts; VANTA supplies source-stated evidence/verifier boundaries; SPEX supplies source-stated distinctions among direct observation, inference, and unknown. [SPEX project state](../sources/predecessors/spex/docs/current/PROJECT-STATE.md) These lineages are conceptual antecedents, not additional replications of IRIS-X results.

#### Conflicting and Negative Evidence

The deterministic verifier may encode the same assumptions as the task generator, so zero fixture errors do not establish open-world verifier validity. The Phase 6 derivation defect shows that an evidence system can preserve all terminals yet still fail at the authority layer. Batch 2 shows that no usable outcome can exist despite a complete surrounding record. Eidos currently contains typed bootstrap structure but no populated document corpus, so it contributes design rationale rather than outcome evidence.

#### Explanatory Compression

F1 jointly explains false accepts, unverified successes, snapshot mismatch detection, research-predicate corruption, and the need to separate producer, verifier, and adjudicator. It would distort the evidence if expanded to subsume action prevention, recovery, capability sufficiency, or temporal persistence; those retain separate units and causal questions.

#### Discriminating Predictions

1. Holding actual outcome fixed, crossing or staling evidence will selectively reduce verified-success eligibility under an evidence-bound adjudicator but not under semantic-only acceptance.
2. Holding all direct terminals fixed, perturbing the predicate authority map will change derived gate status without changing task outcomes.
3. Across independently constructed bounded tasks, producer-coupled acceptance will exhibit more correlated false acceptance than an authority-independent verifier when producers can emit plausible but wrong claims.
4. If a verifier is itself unreliable, additional evidence volume without authority and binding quality will not monotonically improve calibrated acceptance.

#### Falsifiers

F1 would be rejected or materially narrowed if, across independently authored representative tasks, producer claims and independent observations never diverged; evidence binding and authority rules added no information to acceptance; or the added separation increased false rejection and cost without reducing false commitment. A result showing that downstream decisions depend only on outcome rate and are invariant to evidence/authority quality would favor F2's outcome-frontier account.

#### Operationalization Path

The smallest discriminating study is a preregistered held-out warrant factorial: keep a balanced set of valid and invalid producer outputs, independently construct semantic oracles, vary verifier independence and evidence binding, and measure false accept, false reject, unverified success, abstention, and verification resources. It must include authority-map perturbations and evaluator-disagreement cases. No such study is authorized by this synthesis.

#### Generalization Boundary

Direct support is local, deterministic, file/task oriented, and short horizon. Learned judges, human judgment, stochastic model outputs, adversarial collusion, remote mutable evidence, multi-party authority, privacy constraints, and production base rates are Not established. Provider monetary and human-review costs are Unknown.

#### Novelty and Contribution Claim

Potential IRIS-X contribution: an empirically falsifiable account of reliable agentic commitment as an authority-correct relation among outcome, claim, evidence, acceptance, and intervention—not a new trace schema. Eidos, SPEX, and VANTA contain important antecedent ideas, so conceptual novelty is not claimed. Novelty relative to the wider literature is Not established from the preserved corpus alone.

#### Unresolved Assumptions

- Independent ground truth can be obtained for at least some consequential claims.
- Authority and evidence binding can be operationalized without circular dependence on the producer.
- Abstention or unverified success is an admissible system outcome.
- Claim-level benefits survive beyond synthetic deterministic corruptions.

#### Strongest Alternative Explanation

F2 argues that the real problem is simply selecting a configuration with adequate outcome performance; evidence machinery matters only as measurement infrastructure. F2 becomes preferable if verified-outcome rates and lifecycle decisions are unchanged by evidence/authority quality once task accuracy is known.

#### Adversarial Disposition

**Retain as the supported foundational core.** It has direct intervention evidence, explains otherwise disconnected Phase 4 and Phase 6 observations, and makes predictions distinct from pure performance optimization. Its open-world and longitudinal reach must remain explicitly limited.

### Candidate F2 — Minimum-sufficient configuration frontier

- **Candidate ID:** F2
- **Status:** proposed for adversarial comparison; not selected at formulation time
- **Formulation family:** task-relative capability and constrained configuration choice
- **Materially distinct from candidates:** F1 concerns warranted belief, F3 concerns causal treatment of failures, and F4 concerns state/time. F2 concerns which frozen configuration is adequate for a bounded distribution and decision boundary.

#### Explanandum

Why can a cheaper or nominally weaker configuration equal or exceed other configurations on a bounded task family, yet miss a particular admitted task? Without F2, H-P1a's 32/32 structured Luna result and Batch 3 P4's bounded shortfall appear contradictory or invite unsupported intrinsic-model explanations.

#### Unit of Analysis and Horizon

The unit is a complete configuration—model, program/prompt, tools, adapter, policy, verifier contract, and relevant state—evaluated over a declared task distribution and repetition/change horizon. A single task instance can establish pressure but not distribution-level sufficiency. Aggregates require frozen sampling rules and explicit handling of shift.

#### Core Constructs

Capability means requirement satisfaction by the whole configuration. Sufficient capability means stable adequacy for a declared distribution and horizon. Specialization is any task-directed change to model, prompt, program, tools, or workflow and must be typed. Frontier means non-dominance under separately reported verified outcome, reliability properties, and named cost components. This departs from RouteLLM's strong/weak model labels and the NVIDIA SLM paper's size-centered position by making configuration and evidence boundary primary. [RouteLLM paper](../references/papers/ROUTELLM_paper.pdf), [NVIDIA SLM position paper](../references/papers/NVIDIA_SLM_paper.pdf)

#### Causal or Mechanistic Structure

Task distribution and configuration jointly determine output behavior; verification maps outputs to claim-specific outcomes; sampling and shift mediate observed adequacy; design and runtime resources determine costs. Model identity is a component and potential cause, but prompt, program, tools, provider behavior, and admission are confounders unless varied independently. A configuration miss creates pressure; it does not choose the remedy.

#### Scientific Nontriviality

The scientific question is not how to tune a prompt for a benchmark. It asks what evidence warrants a sufficiency decision, how adequacy transfers across a bounded distribution and change horizon, and whether a lower-capability or lower-cost configuration remains non-dominated after reliability and lifecycle burdens are included.

#### Relationship to Success, Reliability, and Cost

Verified task success is the primary outcome. Reliability is a vector of constraints and secondary outcomes, not a single score. Cost is a vector and later decision criterion; inference price is only one component. A frontier cannot be claimed while provider monetary cost, development amortization, verification, failure, recovery, maintenance, or oversight relevant to the decision remains unmeasured.

#### Relationship to Phase 1–6 Evidence

H-P1a directly supports one finite configuration advantage. Phase 5 contributes three successful observations under one admitted lineage. Batch 3 P4 directly supports one frozen-configuration shortfall. The evidence does not establish repeatability of specialization, intervention benefit, lifecycle advantage, or a general SLM/generalist law. Historical Result D and the separate authority repair must remain separate.

#### Primary Source Support

The main direct authority is H-P1a's blind result; Phase 5 task terminals and Batch 3 P4 are bounded additional observations, not replications of the same comparison. RouteLLM reports learned per-request routing with more than twofold cost reduction on public benchmarks but acknowledges distribution and router variability. FrugalGPT reports up to 98% inference-price reduction with similar-distribution labeled data and upfront training cost. [FrugalGPT paper](../references/papers/FrugalGPT_paper.pdf) The NVIDIA SLM paper is explicitly a position and conversion proposal, not direct IRIS-X evidence.

#### Conflicting and Negative Evidence

H-P1a included two invalid optimization attempts and did not establish monetary lifecycle benefit. The Terra seed was neither a universal upper bound nor an optimized comparator. Batch 3 produced a real miss after five successes. Batch 2 demonstrated that system/provider failure can mimic an unusable task observation. RouteLLM reports that router performance can vary widely without a clear explanation and that real distributions may differ from benchmarks. FrugalGPT requires labeled, similar-distribution examples and omits latency, fairness, privacy, uncertainty, and environmental effects from its optimization.

#### Explanatory Compression

F2 unifies bounded specialization gains, task-relative pressure, configuration identity, distribution shift, and cost-performance frontiers. It would erase crucial distinctions if it treated justified acceptance as mere accuracy, collapsed failure locus into model capability, or assumed every miss demands escalation.

#### Discriminating Predictions

1. A structured task-specific configuration advantage will repeat on independently sampled held-out items from the same declared distribution more often than on shifted families.
2. Configuration identity will explain outcome changes not captured by model label alone when prompt/program/tool factors are varied factorially.
3. A nominally stronger model will sometimes be dominated on bounded verified outcomes, while the dominance relation may reverse after development, verification, or shift costs are included.
4. One configuration-level miss will not reliably predict benefit from a stronger model unless pressure repeats and the stronger comparator directly resolves it.

#### Falsifiers

F2 would be rejected as a useful center if task-specific advantages disappear under independent held-out sampling, model label alone accounts for performance across controlled configurations, or every specialist is dominated after a complete declared lifecycle boundary. Evidence that outcome distributions are stable but acceptance errors dominate consequential decisions would favor F1.

#### Operationalization Path

The smallest program freezes multiple complete configurations, independently samples same-distribution and shifted tasks, uses an authority-independent verifier, repeats enough to estimate stability without a post hoc threshold, and reports every resource component separately. It should first test whether the Batch 3 pressure pattern repeats; only then should it compare candidate configurations. No run is authorized here.

#### Generalization Boundary

Current direct evidence covers small deterministic task families, Luna/Terra configurations, a specific Codex/provider envelope, short horizons, and mostly non-mutating tasks. Population transfer, stochasticity, model updates, tool use, adversarial inputs, deployment load, monetary provider cost, maintenance, and human oversight are Unknown or Not established.

#### Novelty and Contribution Claim

Potential IRIS-X contribution: an evidence-bound notion of minimum-sufficient **configuration** whose sufficiency decision is conditioned on verifier, distribution, horizon, and lifecycle boundary. Routers, cascades, prompt optimizers, workflow search, and fine-tuning are commodity or reusable intervention mechanisms. Novelty beyond the preserved routing, cascade, optimization, and SLM literature is Not established.

#### Unresolved Assumptions

- A bounded task distribution can be specified without hiding consequential tail cases.
- Configuration identity is stable enough to compare across repetitions.
- A scientifically tractable lifecycle-cost boundary can be declared.
- Held-out verification is sufficiently independent of optimization and task construction.

#### Strongest Alternative Explanation

F1 argues that apparent configuration adequacy is secondary because reliable acceptance, not raw success, is the foundational phenomenon. F1 is preferable when configuration comparisons do not change decisions after evidence quality is accounted for, or when false commitment dominates outcome variance.

#### Adversarial Disposition

**Revise and retain as an emerging research program, not the present core thesis.** Direct evidence makes the configuration-relative question real, but repeatability, transfer, intervention benefit, and lifecycle non-dominance are missing.

### Candidate F3 — Failure-directed intervention selection

- **Candidate ID:** F3
- **Status:** proposed for adversarial comparison; not selected at formulation time
- **Formulation family:** conservative attribution and causal treatment choice
- **Materially distinct from candidates:** F1 concerns whether a claim is warranted, F2 concerns whether a configuration is adequate, and F4 concerns temporal/state transitions. F3 concerns which intervention, if any, causally improves an observed shortfall.

#### Explanandum

Why do superficially similar failed or unusable results require different responses, and when does a failure classification justify a retry, recovery, reconfiguration, stronger model, route, cascade, or no action? Without F3, Batch 2's provider/system failure and Batch 3's producer-semantic miss can be collapsed into the same negative label, inviting blind retry or escalation and unsupported blame assignment.

#### Unit of Analysis and Horizon

The unit is a failure episode embedded in a frozen task/configuration, followed by one explicitly identified intervention and a comparable outcome observation. The minimal horizon includes recurrence assessment, intervention, state effects, verification, and immediate resource consequences. Maintenance or distribution-level claims require repeated episodes and a declared drift horizon.

#### Core Constructs

Observation records what happened. Failure locus records the stage at which a shortfall is directly supported. Causal attribution asserts that changing a factor would change the outcome and therefore requires counterfactual evidence. Capability pressure records that a frozen configuration missed a declared requirement. Intervention benefit is a comparative treatment effect. Retry repeats; recovery repairs state; reconfiguration changes the configuration; escalation changes capability allocation. These constructs deliberately depart from the historical IRIS predecessor's prescriptive learned-credit architecture and from Agent Lightning's trajectory-to-reward credit assignment by withholding causal force until a comparison exists. [IRIS credit and recovery](../sources/predecessors/iris/docs/04_Credit_Assignment_and_Recovery.md), [Agent Lightning paper](../references/papers/Agent_Lightning_paper.pdf)

#### Causal or Mechanistic Structure

Task, configuration, provider/system state, producer behavior, verifier, and external environment may each cause an observed shortfall. A conservative classifier localizes only what direct evidence supports. Recurrence testing separates a one-off event from stable pressure. A controlled intervention changes one candidate cause while holding other identities fixed; independently verified outcome and state changes estimate benefit and harm. Selection effects, nonstationarity, and shared evaluator errors are confounders.

#### Scientific Nontriviality

The question is not which error handler to implement. It asks whether typed observations carry predictive causal information about treatment effects, whether generic escalation is wasteful or harmful, and what evidence threshold justifies changing a bounded agent system. The account can fail if classifications do not replicate or do not discriminate interventions.

#### Relationship to Success, Reliability, and Cost

Verified success and valid final state are outcomes. Failure-attribution accuracy and treatment discrimination are reliability properties. Intervention calls, latency, repeated failure, residual state, verification, and maintenance are separate cost components. Cost enters only after effects are established; low call price cannot substitute for treatment benefit.

#### Relationship to Phase 1–6 Evidence

Phase 6 directly supports conservative separation of observation, failure locus, intrinsic incapability, intervention benefit, and gate status. Batch 2 and Batch 3 provide contrasting systemic-failure and semantic-miss observations. H-I1a and H-RCV1a directly demonstrate that intervention timing and targeted recovery can change final state in deterministic fixtures. They do not establish which treatment benefits the Batch 3 pressure case. All relevant Phase 6 mechanism gates remain insufficient_or_ambiguous or not_triggered.

#### Primary Source Support

Direct authorities are the Batch 2 and Batch 3 P4 terminals, the Batch 1 assessments, H-I1a, H-RCV1a, and the repaired gate adjudication. VANTA supplies a source-stated multi-label failure taxonomy and commit/replay/recovery distinctions but says the taxonomy is not final and credit routing is not empirically validated. [VANTA failure taxonomy](../sources/predecessors/vanta/docs/02_specs/Failure_Taxonomy_v0.md), [VANTA commit/replay semantics](../sources/predecessors/vanta/docs/02_specs/Commit_Abort_Replay_Semantics.md) GEPA's trace reflection and Agent Lightning's credit assignment are source-stated alternative treatment-generation mechanisms, not support for IRIS-X treatment effects. [GEPA paper](../references/papers/GEPA_paper.pdf)

#### Conflicting and Negative Evidence

Batch 1's eight positives are synthetic instrument tests. Batch 2 supports no semantic pressure because no usable result existed. Batch 3 contains only one directly supported pressure observation. H-O1a found no consistent timing benefit from instrumentation. The predicate-authority bug shows that a correct failure observation can be misrouted before treatment selection. No retry, stronger-model, routing, cascade, workflow-search, or optimization comparison exists for the observed pressure case.

#### Explanatory Compression

F3 jointly explains why provider failure, task miss, policy denial, evidence invalidity, and residual-state failure must not share a default remedy; why prevention differs from recovery; and why a gate requires intervention evidence rather than architectural enthusiasm. It would distort F1 if it equated a warranted failure classification with a cause, and distort F2 if it treated one treatment success as distribution-level sufficiency.

#### Discriminating Predictions

1. Provider/system failures will respond more reliably to admission or adapter repair than to stronger-model allocation when no usable provider result exists.
2. Repeated producer-semantic misses under an otherwise usable frozen execution will be more sensitive to program/configuration or model changes than to evidence-binding changes, while acceptance errors show the reverse pattern.
3. A stage-matched treatment will improve independently verified outcome or valid final state more consistently than blind retry across a heterogeneous failure set.
4. Conservative abstention from treatment when attribution is ambiguous will sometimes have lower failure-plus-intervention cost than automatic escalation.

#### Falsifiers

F3 would be rejected or reduced to descriptive taxonomy if failure-locus classifications do not reproduce, do not predict differential treatment effects, or generic retry/escalation performs as well as stage-matched intervention across representative failures at no greater harm or cost. Stable configuration-level performance without meaningful intervention heterogeneity would favor F2 alone.

#### Operationalization Path

First establish recurrence of one direct pressure class under a frozen configuration. If it recurs, preregister a matched comparison in which no action, exact retry, one configuration change, and one capability-allocation change are independently applied with order randomization, common verification, state checks, and separate resources. Do not introduce multiple mechanisms in one arm. If pressure does not recur, stop; there is no treatment question. This is an unexecuted proposal only.

#### Generalization Boundary

Direct treatment results are deterministic, local, and fixture-specific. The one real-task pressure case has no treatment comparison. Stochastic failures, provider drift, tool failures, human intervention, adversarial behavior, remote side effects, delayed harm, and long-horizon maintenance are Not evaluated. Monetary treatment cost is Unknown.

#### Novelty and Contribution Claim

Potential IRIS-X contribution: an evidence gate that separates observed pressure, recurrence, causal attribution, treatment benefit, and architecture adoption. Failure taxonomies, tracing, retries, routing, recovery engines, optimizer implementations, and RL credit-assignment systems are reusable substrates or treatment families. Wider-literature novelty is Not established.

#### Unresolved Assumptions

- Failure strata can be defined without post-treatment leakage.
- At least one factor can be varied while preserving comparable task and verifier conditions.
- Short-horizon treatment effects predict the decision-relevant horizon.
- Withholding intervention is safe enough to serve as a comparator where needed.

#### Strongest Alternative Explanation

F2 says explicit causal diagnosis may be unnecessary: compare complete configurations on a frontier and select the best, regardless of why they differ. F2 becomes preferable when black-box configuration comparison is stable, cheap, and as effective as locus-specific treatment selection.

#### Adversarial Disposition

**Combine with F2 as an ordered evidence program without erasing distinctions.** F2 asks whether a configuration is sufficient; F3 asks what to change after stable pressure. F3 is scientifically promising but presently lacks the counterfactual comparison needed for a substantive treatment claim.

### Candidate F4 — Temporal and state-transition reliability

- **Candidate ID:** F4
- **Status:** proposed for adversarial comparison; not selected at formulation time
- **Formulation family:** long-running, stateful, and recoverable agency
- **Materially distinct from candidates:** F1's horizon ends at warranted commitment, F2 aggregates configuration adequacy over a declared distribution, and F3 studies treatment effects. F4 makes continuity, state transitions, drift, and restoration over time the explanandum.

#### Explanandum

Why can an agent that succeeds on isolated tasks degrade, lose authority, accumulate state error, or fail to reconstruct valid work over longer execution and maintenance horizons? Without F4, process-lifetime invariance, reversible restoration, targeted recovery, persistent session designs, and seven-day autonomous optimization are treated as incidental runtime features rather than hypotheses about temporal reliability.

#### Unit of Analysis and Horizon

The unit is a state-bearing agent process or controlled external resource observed across a sequence of tasks, interruptions, restarts, recoveries, configuration/provider changes, or maintenance events. Horizons must be named—within-process repetitions, restart cycles, days/weeks, or version changes—and cannot be pooled without a transition model.

#### Core Constructs

Internal cognitive state, session/context state, external mutable state, and research-governance state remain distinct. Continuity is preservation of required information and authority across transitions. Replay re-executes an action under declared semantics; restoration returns a resource to a required state; recovery produces a valid state after failure; temporal reliability is a vector of validity, drift, reconstructability, and bounded resource properties across a declared transition sequence. This deliberately avoids inheriting the historical IRIS mandate for one canonical learned State IR. [IRIS architecture constitution](../sources/predecessors/iris/docs/01_Architecture_Constitution.md)

#### Causal or Mechanistic Structure

Repeated actions, context accumulation, external mutation, process failure, model/provider updates, and maintenance changes can mediate temporal degradation. Persistence may prevent information loss but may also preserve corruption; stateless reconstruction may reduce contamination but add cost or lose tacit context. Checkpoints, typed identities, replay rules, and recovery mechanisms intervene at different transitions. Task ordering and nonstationary environments confound simple before/after comparisons.

#### Scientific Nontriviality

The problem is not whether to add a database. It asks when persistent or reconstructable state is causally necessary for verified outcomes, how drift propagates through agent decisions, and which continuity strategy minimizes false commitment and residual state under change.

#### Relationship to Success, Reliability, and Cost

Per-task verified success is an outcome within a sequence. Temporal reliability comprises transition-specific validity, drift, recovery, and continuity properties. Storage, replay, checkpointing, context growth, recovery, stale-state failures, and maintenance are cost components. Long-term cost cannot be inferred from one process run.

#### Relationship to Phase 1–6 Evidence

H-OR1a directly supports no drift across 480 deterministic within-process cases. H-SR1a supports 120 exact local restorations. H-RCV1a supports 15 targeted deterministic recoveries. These validate bounded mechanisms, not long-running model agents. Phase 5 and Phase 6 tasks do not establish a persistence requirement, and the corresponding Phase 6 gate is not_triggered.

#### Primary Source Support

Prime Agent describes daemon-backed sessions, persistent kernels, compaction, schedules, goals, and recoverable children, while explicitly stating that process isolation is not a security sandbox. [Prime Agent architecture](../sources/external/prime_agent/packages/coding-agent/docs/architecture.md), [long-running agents](../sources/external/prime_agent/packages/coding-agent/docs/long-running-agents.md) VANTA provides source-stated commit, abort, replay, and recovery obligations. AVO reports seven days of autonomous kernel evolution on B200 hardware and 30 minutes of transfer adaptation, a narrow but relevant source-stated long-running example. [AVO paper](../references/papers/NVIDIA_AVO_paper.pdf) These sources are not IRIS-X replications.

#### Conflicting and Negative Evidence

The direct IRIS-X process test excludes crash/restart, stochastic models, provider change, and days/weeks horizons. Exact restoration uses copied local workspaces. Persistence may amplify stale or poisoned state, and no direct comparison shows that stateful execution beats stateless reconstruction for current tasks. The Phase 6 persistence gate is not_triggered. AVO's success is confined to one expert kernel domain and one GPU family; it does not establish general agent durability.

#### Explanatory Compression

F4 explains drift, restoration, replay, context continuity, and recovery as transition properties. It would erase important distinctions if it treated every research record as runtime state, assumed persistence is always beneficial, or used long duration as evidence of correct outcomes or justified acceptance.

#### Discriminating Predictions

1. For tasks requiring information across interruptions, an authority-preserving checkpoint/reconstruction strategy will yield fewer invalid continuations than either unverified persistence or stateless restart.
2. On tasks without cross-step dependencies, stateful persistence will add resource and contamination risk without a verified-outcome advantage.
3. Injected stale or corrupted state will propagate into later decisions unless identity and authority are revalidated at transition boundaries.
4. Recovery success measured immediately will overestimate durability if residual drift appears after subsequent dependent actions.

#### Falsifiers

F4 would be rejected as a central research program if representative long-horizon tasks can always be reconstructed statelessly with equal verified outcomes and lower total cost, persistence adds no predictive failure mode, or transition-specific measures do not forecast later validity. If most consequential errors occur within one claim/adjudication step independent of continuity, F1 is the stronger center.

#### Operationalization Path

Only after a task requires continuity, compare verified persistence, stateless reconstruction, and deliberately corrupted-state controls across a frozen interruption/restart schedule. Measure task outcomes, authority continuity, residual drift, recovery, and named resources beyond the first post-restart action. No present task establishes this prerequisite and no study is authorized.

#### Generalization Boundary

IRIS-X direct evidence is local, deterministic, short, and largely non-model. Prime Agent and VANTA contribute source-stated mechanisms; AVO contributes one narrow long-duration result. Multi-host execution, security isolation, remote services, concurrent writers, provider/model updates, privacy, human handoff, and maintenance over weeks remain Unknown or Not evaluated.

#### Novelty and Contribution Claim

Potential IRIS-X contribution would be a claim- and authority-aware account of state-transition reliability, not another session store or workflow daemon. Persistence engines, checkpointing, messaging, scheduling, storage, and replay transports are commodity substrate. No current evidence establishes either necessity or wider novelty.

#### Unresolved Assumptions

- Some target tasks genuinely require durable state rather than reconstructable evidence.
- Transition boundaries can be observed and authority revalidated.
- A tractable horizon represents the downstream maintenance risk.
- Persistence benefits can be separated from increased context or compute.

#### Strongest Alternative Explanation

F1 says temporal failures are instances of stale evidence, identity, or authority and need no separate foundational theory. F1 is preferable if transition effects disappear once every claim is re-bound and reverified; F4 is preferable if sequence-dependent degradation remains after claim-level controls.

#### Adversarial Disposition

**Revise and defer as an unresolved alternative; reject present centrality.** The phenomenon is plausible and some substrate properties are directly demonstrated, but no current task requires persistence and no long-horizon agent-level comparison exists.

## 5. Symmetric adversarial comparison

No scalar score is used because the dimensions are not commensurable and the evidence classes differ.

| Criterion | F1 warranted agency | F2 sufficient configuration | F3 failure-directed intervention | F4 temporal/state reliability |
|---|---|---|---|---|
| Phenomenon explained | Divergence among outcome, claim, evidence, authority, and acceptance | Adequacy and non-dominance of complete configurations on bounded distributions | Differential effects of retry, recovery, reconfiguration, routing, escalation, or no action | Drift, continuity, restoration, and recovery across transitions and time |
| Direct empirical support | Strongest: controlled false-accept, evidence-binding, identity, and authority results | Bounded: one 32-item configuration comparison, limited task successes, one pressure miss | Partial: clear failure-locus separation and deterministic prevention/recovery effects; no treatment comparison for real pressure | Partial: deterministic process, restoration, and recovery fixtures; no long-horizon model-agent result |
| Primary challenge | Fixture/oracle dependence and unclear open-world verifier validity | Repeatability, distribution transfer, incomplete comparators, and unknown lifecycle cost | Descriptive localization may not predict causal treatment benefit | Feature-first risk; persistence may be unnecessary or harmful |
| Discrimination from alternatives | Changes acceptance while holding outcome fixed | Changes outcomes and frontier while holding warrant rules fixed | Changes outcome conditional on failure class and intervention | Produces sequence/transition effects absent in isolated claims |
| Operationalizability | High for bounded held-out factorials | Moderate; requires frozen comparable configurations and samples | Moderate after recurrence; needs safe counterfactual interventions | Low until a continuity-dependent task and meaningful horizon exist |
| Scientific reach if supported | Claim-specific reliable commitment across agents and research adjudication | Task-specific capability and resource allocation decisions | Evidence-grounded mechanism selection and escalation restraint | Long-running agents, maintenance, replay, and persistent state |
| Main unsupported assumptions | Independent authority is obtainable and useful beyond deterministic fixtures | Bounded distributions represent use, and lifecycle boundaries are measurable | Failure strata are causal enough to guide treatments | State continuity is required and tractable at the chosen horizon |
| Novelty status | Antecedents exist; wider novelty Not established | Routing/cascade/specialization antecedents exist; narrower configuration framing may contribute; novelty Not established | Taxonomy and optimization antecedents exist; evidence-gated causal sequence may contribute; novelty Not established | Persistence/recovery antecedents are extensive; novelty Not established |
| Adversarial disposition | Retain as supported core | Revise and retain as emerging program | Combine with F2 without collapsing the questions | Revise and defer; not current center |

### 5.1 Primary counterevidence against the selected center

The strongest objection to F1 is that its best results may be engineered consequences of deterministic fixtures: when invalid outputs and evidence corruptions are defined by the same task family that defines the oracle, an independent verifier can appear perfect by construction. Moreover, separating many statuses can increase operational complexity, latency, and false rejection. If future representative tasks show that evidence/authority distinctions add little beyond calibrated outcome sampling, F1 should be narrowed to research hygiene rather than a theory of reliable agency.

The synthesis does not dismiss this objection. F1 is selected because it currently explains the strongest controlled contradictions, not because its generality or novelty is settled.

### 5.2 Strong external alternatives and what they do not establish for IRIS-X

| Alternative lineage | Source-stated contribution | Relevance and limiting evidence |
|---|---|---|
| RouteLLM | Learns a query-level strong/weak choice from preference data; reports more than twofold cost reduction with limited quality loss and cross-pair generalization | It assumes a binary model allocation and one model call per query. The paper warns that real distributions may differ, in-domain data helps, and routers vary widely without a clear explanation. The preserved controller routes on the last message although current routers were trained on first-turn data. This is a candidate F3 treatment, not evidence that IRIS-X needs routing. [Controller](../sources/external/routellm/routellm/controller.py) |
| FrugalGPT | Learns prompt/model cascades under an average inference-budget constraint; reports up to 98% price reduction or a 4% accuracy gain on evaluated tasks | Requires labeled, similar-distribution examples and upfront learning resources; the paper excludes several decision-relevant dimensions. It supports the plausibility of F2 frontiers, not an IRIS-X lifecycle-cost result. |
| DSPy | Separates signatures, adapters, modules, evaluation, and optimization; recommends held-out evaluation and warns prompt optimizers can overfit small training sets | Supplies modular design-time substrate and evaluation practice. It does not establish which IRIS-X construct should be central or whether optimization is currently needed. [Programming](../sources/external/dspy/docs/docs/learn/programming/overview.md), [optimization](../sources/external/dspy/docs/docs/learn/optimization/overview.md) |
| GEPA | Uses trace reflection and Pareto-aware prompt evolution; reports better average performance than GRPO across six tasks with up to 35 times fewer rollouts | Rich traces can guide candidate generation, but evaluator quality, task scope, and lifecycle resources still bound the claim. It is an F3/F2 intervention family, not direct attribution evidence. |
| AFlow | Searches code-represented workflows with an MCTS variant; reports improvements across six benchmarks and weaker-model cost/performance advantages | Benchmark reward is not the full reliability vector. The repository itself warns that some migrated operators may contain bugs. Workflow search remains not_triggered for IRIS-X. [AFlow README](../sources/external/aflow/README.md) |
| Agent Lightning | Decouples agent execution from RL training and maps traces to transitions with credit assignment; reports improvement curves on text-to-SQL, RAG, and calculator tasks | The broad ANY-agent framing is a source claim, while long-horizon credit assignment and more efficient RL remain future work in the paper. RL is neither authorized nor indicated by current IRIS-X evidence. |
| Prime verifiers | Makes taskset, harness, model, runtime policy, trace, reward, metric, and error explicit; supports isolated rollout runtimes and resumable evaluation | Strong reusable evaluation substrate. Task-specific reward does not automatically provide authority-independent verification or a reliability thesis. [Architecture](../sources/external/prime_intellect_verifiers_v1/docs/v1/architecture.md) |
| NeMo Agent Toolkit | Provides framework-agnostic tracing, profiling, evaluation, and parameter/prompt optimization | Useful commodity instrumentation and optimization substrate. Its judge-dependent evaluators, forecasting, and multi-objective scalarization require their own validity evidence and do not settle IRIS-X's claim relations. [Evaluation](../sources/external/NeMo-Agent-Toolkit-develop/docs/source/improve-workflows/evaluate.md) |
| Prime Agent and AVO | Prime Agent supplies persistent sessions and long-running orchestration; AVO reports seven-day autonomous kernel optimization that beats selected expert baselines on B200 | These make F4 plausible and show a real long-running domain result, but they do not establish general reliability, security isolation, or persistence benefit for the current task distribution. |
| Historical IRIS predecessor | Mandates a single trunk, canonical State IR, learned control, and learned recovery | This is a strong architecture hypothesis, not direct evidence. Its prohibitions against hard-coded routing or symbolic authority conflict with the current evidence-first deterministic substrate and would prematurely erase viable alternatives. [IRIS-X predecessor](../sources/predecessors/iris/IRIS-X.md) |

## 6. Post-adjudication research formulation

### 6.1 Foundational thesis and adjacent hypothesis

**T1 — supported within the current evidence boundary.** Within a declared task, configuration, verifier, action boundary, and horizon, reliable agentic intelligence requires preserving a reconstructable and authority-correct relation among actual outcome, producer claim, evidence validity and binding, acceptance, and any derived decision. On the tested fixtures, breaking these relations produces false acceptance, unverified success, missed identity corruption, or wrong predicate authority even when other parts of the execution remain unchanged.

T1 does not assert universal verifier correctness, general long-term reliability, or a final architecture. It defines a falsifiable scientific center: the conditions under which an agent system is warranted in committing to a result or changing itself in response to evidence.

**T2 — emerging, not established.** Minimum-sufficient capability is a property of a complete configuration relative to a task distribution, verifier, horizon, and cost boundary. A configuration becomes a candidate for revision or escalation only after its pressure is repeatable; a particular mechanism becomes justified only after a comparative intervention shows decision-relevant benefit.

T2 is kept separate from T1. An outcome can be warranted but insufficient, or successful but unwarranted. Likewise, a correct failure classification does not identify a beneficial treatment.

### 6.2 Revised research problem

The defensible foundational problem is:

> For bounded agentic tasks, what evidence, authority, verification, and state-transition relations are sufficient to justify accepting a result and, when stable configuration pressure exists, to justify a particular intervention under an explicit resource and horizon boundary?

This revises the prior [problem definition](problem-definition.md) in three ways:

1. it makes justified commitment—not a fused success/reliability/cost objective—the central explanandum;
2. it treats minimum-sufficient configuration and intervention benefit as conditional downstream questions;
3. it preserves reliability and cost as typed vectors until an explicit decision rule and complete enough measurement boundary exist.

### 6.3 Research questions and hypotheses

| ID | Research question | Hypothesis | Current status and falsifier |
|---|---|---|---|
| RQ-EW1 / H-EW1 | Which claim–evidence–authority relations prevent false commitment without unacceptable false rejection? | Authority-independent semantic verification plus evidence binding will reduce false acceptance and distinguish unverified success from verified success across independently constructed bounded tasks | Directly supported only on deterministic fixtures. Falsified or narrowed if independent held-out tasks show no decision improvement or disproportionate false rejection/cost |
| RQ-MS1 / H-MS1 | When does an observed task/configuration shortfall constitute stable capability pressure? | Pressure will be configuration- and distribution-dependent; it will require recurrence under frozen identity and will weaken under changes that reveal sampling or system causes | One direct pressure observation; repeatability Not evaluated. Falsified if pressure is not reproducible or model label alone explains controlled variation |
| RQ-FD1 / H-FD1 | Does conservative failure locus predict which intervention improves verified outcomes? | Stage-matched interventions will outperform blind retry/escalation on heterogeneous, recurrent failures while ambiguous cases will often favor abstention | Intervention benefit Not established. Falsified if locus does not predict differential treatment effect or generic escalation dominates without added harm/cost |
| RQ-LC1 / H-LC1 | When is a lower-resource configuration non-dominated after verification, failure, optimization, and maintenance are counted? | Some task-specific configurations will remain non-dominated on a declared verified-outcome/reliability/resource vector, but inference-price advantages will sometimes disappear under lifecycle accounting | H-P1a supports bounded outcome advantage; monetary lifecycle advantage Unknown. Falsified if every specialist is dominated under a complete declared boundary |
| RQ-TS1 / H-TS1 | When does state continuity improve reliability beyond stateless reconstruction? | Persistence will help only for tasks with genuine cross-transition dependencies and authority-preserving state; otherwise it will add cost or contamination risk | Deferred; persistence gate not_triggered. Falsified as a central question if stateless reconstruction matches outcomes at lower cost across relevant long-horizon tasks |

## 7. Smallest discriminating evidence program — unexecuted

This is a hypothesis-derived decision sequence, not a phase plan, experiment authorization, feature roadmap, or instruction to run models. Every study would require separate owner authorization. Any future model execution remains subject to the repository's two-turn freeze/launch and later collection procedure.

### Study D1 — held-out warrant generalization

- **Purpose:** discriminate F1 from an outcome-only F2 explanation.
- **Unit/intervention:** independently authored bounded task results; vary producer dependence, semantic-verifier independence, evidence validity/binding, and authority mapping while holding actual outcome classes balanced.
- **Observables:** false accept, false reject, unverified success, abstention, authority error, adjudication reproducibility, verification latency/resources.
- **Decision:** retain F1 beyond fixture hygiene only if the relations predict calibrated commitment on held-out tasks. Narrow or reject it if they add no information or impose unacceptable error/cost.
- **Stop condition:** do not add runtime mechanisms; this study concerns claim relations only.

### Study D2 — configuration-pressure repeatability

- **Prerequisite:** D1 need not succeed, but task outcomes must have an independent verifier and exact frozen configuration identity.
- **Purpose:** distinguish stable F2 pressure from a one-off Batch 3 observation or a system-path artifact.
- **Unit/intervention:** repeated same-distribution and deliberately shifted task instances under the exact admitted configuration; no retry, route, escalation, or configuration change during the pressure-estimation arm.
- **Observables:** task-level outcome vector, failure locus, evidence status, distribution stratum, repetition/time identity, separate resource fields.
- **Decision:** proceed only if a preregistered recurrence rule is met. If not, preserve the original miss and stop without an intervention claim.

### Study D3 — single-factor intervention discrimination

- **Prerequisite:** recurrent, interpretable pressure from D2.
- **Purpose:** discriminate F3 from black-box configuration comparison and generic escalation.
- **Unit/intervention:** matched tasks randomized across no action, exact retry, one program/configuration change, and one stronger-capability allocation. Add a recovery arm only if invalid external state exists. Never bundle routing, workflow search, prompt optimization, and retry in one arm.
- **Observables:** independently verified outcome, residual state, recurrence, false commitment, intervention-specific resources, and delayed dependent-task effects where applicable.
- **Decision:** a mechanism gate may change only if a direct comparative benefit and its trade-off are established. An improvement does not automatically make the mechanism core.
- **Stop condition:** if no arm meaningfully distinguishes itself or attribution does not predict effects, retain ambiguity and stop.

### Study D4 — continuity necessity test

- **Prerequisite:** an owner-selected task with a genuine cross-interruption dependency; current evidence supplies none.
- **Purpose:** discriminate F4 from claim-level reconstruction alone.
- **Unit/intervention:** verified persistence versus stateless evidence reconstruction versus injected stale/corrupted state across a frozen interruption/restart schedule.
- **Observables:** verified task outcome, authority continuity, residual drift, recovery success beyond the first subsequent action, context/storage/replay resources.
- **Decision:** treat persistence as a research mechanism only if it changes decision-relevant outcomes beyond what re-binding and re-verification explain.

This ordering is intentionally conservative: D1 tests the selected core; D2 establishes whether a downstream pressure phenomenon is stable; D3 is permitted conceptually only after stable pressure; D4 exists only when a task requires continuity. None is launched or selected by this document.

## 8. Research contribution versus reusable substrate

| Possible IRIS-X research contribution | Commodity or reusable substrate |
|---|---|
| Claim-specific warranted commitment across outcome, evidence, authority, and acceptance | JSON/JSONL serialization, hashing, trace transport, file registries |
| Evidence conditions for moving from one shortfall to stable configuration pressure | Task runners, provider adapters, harnesses, benchmark loaders |
| Counterfactual standard for moving from pressure/attribution to intervention adoption | Retry loops, recovery libraries, router/cascade implementations |
| Minimum-sufficient configuration under explicit verifier, horizon, and lifecycle boundaries | DSPy/GEPA/AFlow optimization machinery, fine-tuning and RL infrastructure |
| Vector-valued reliability and cost decisions that preserve unknowns and incompatible units | Observability backends, profilers, dashboards, storage, session management |
| Authority-aware state-transition reliability, if future evidence establishes necessity | Persistent kernels, daemons, queues, checkpoints, workflow engines, MCP/tool dispatch |

The research contribution is therefore not a larger agent framework. It is a set of falsifiable relations and decision standards that can be tested using replaceable infrastructure.

## 9. Scope, falsifiers, and unresolved alternatives

### 9.1 Claims that are currently supported

- Actual success and justified acceptance can diverge under frozen deterministic conditions.
- Evidence validity/binding and authority can change verified-success or research-predicate decisions while direct outcomes remain fixed.
- Pre-action prevention, post-hoc detection, and targeted recovery are non-equivalent on the tested fixtures.
- A task-specific configuration can outperform seed comparators on a finite deterministic corpus.
- One admitted frozen configuration directly missed one Batch 3 requirement.
- That miss does not establish intrinsic model incapability or the benefit of any deferred mechanism.
- The repaired authoritative ledger triggers zero of eight gates.

### 9.2 Claims that remain Unknown, Not established, or Not evaluated

- universal verifier reliability, evaluator independence in open-ended tasks, and human/judge agreement;
- repeatability and transfer of H-P1a optimization or Batch 3 pressure;
- provider/model implementation immutability and stochastic behavior across time;
- retry, recovery, stronger-model, routing, cascade, workflow-search, or optimization benefit for the direct pressure case;
- a complete monetary or non-monetary lifecycle-cost boundary;
- production, adversarial, multi-host, concurrent, remote-action, privacy, and safety validity;
- crash/restart, days/weeks, or maintenance-drift reliability;
- a final system architecture, product boundary, canonical ontology, or unified reliability scalar;
- novelty of T1 or T2 relative to the full external literature.

### 9.3 Global revision conditions

The plural formulation should be revised if any of the following occur:

1. independently constructed evidence shows that outcome-only measurement predicts consequential decisions as well as authority/evidence-aware adjudication;
2. configuration pressure does not repeat under frozen identity or vanishes under sampling-path repair;
3. failure locus fails to predict differential intervention benefit;
4. lifecycle accounting consistently reverses bounded specialist advantages;
5. long-horizon sequence effects dominate claim-level failures even after re-binding and re-verification;
6. a single alternative formulation explains these observations without erasing their units, horizons, and negative evidence.

Unresolved alternatives—model-intrinsic specialization, runtime routing, cascades, workflow search, prompt/program optimization, RL/fine-tuning, learned control, persistent state, and broad architecture search—remain candidates, not implied requirements.

## 10. Required audits

### 10.1 Provenance audit — pass within local limits

- The baseline was reconciled before interpretation; critical files and protected trees match the manifest.
- The [source registry](../corpus/sources.yaml), [artifact registry](../corpus/artifacts.yaml), and [provenance policy](../corpus/PROVENANCE.md) establish local byte identity and known acquisition notes.
- Exact upstream revision, acquisition chain, and pre-import modification are often Unknown; local hashes do not establish scientific validity or equality to a current upstream source.
- Direct predicates cite exact producing terminal records. Historical summaries are not substituted for direct authority.
- No protected source, paper, or experiment artifact was modified.

### 10.2 Uncertainty audit — pass

- Unknown, Not established, Not evaluated, insufficient_or_ambiguous, systemic failure, semantic miss, and historical result classes remain distinct.
- Provider monetary cost, complete lifecycle cost, intrinsic model incapability, intervention benefit, repeatability, production transfer, and long-horizon reliability are not inferred.
- No absent value is converted to zero or false.
- Candidate generalization boundaries and falsifiers are explicit.

### 10.3 Source-dependence audit — pass

- Papers and their repositories are treated as one lineage unless explicitly separated.
- Phase result, synthesis, closure, and state documents are treated as one evidence chain.
- External framework claims are labeled source-stated and do not become IRIS-X empirical support.
- Shared deterministic fixtures are not counted as independent population replications.
- Predecessor prescriptions are treated as hypotheses or mechanisms, not inherited authority.

### 10.4 Anti-literature-review audit — pass

| Required check | Answer | Evidence in this synthesis |
|---|---|---|
| Does it explain a scientific problem rather than merely catalogue projects? | Yes | F1–F4 each state a distinct explanandum, causal structure, unit, prediction, and falsifier; Section 6 adjudicates the scientific center. |
| Are source summaries subordinated to claims, tensions, mechanisms, and discriminating evidence? | Yes | External projects appear chiefly in each candidate's primary support/counterevidence and in Section 5.2 as alternative mechanisms with limiting evidence. |
| Are direct observations distinguished from source claims and IRIS-X inference? | Yes | Section 1.2 fixes directly_observed, source_stated, inferred, and unknown classes; Sections 2, 4, and 5 apply those distinctions and source-dependence rules. |
| Are negative evidence and invalid attempts causally relevant rather than footnotes? | Yes | The failed original pilot, two invalid H-P1a attempts, 108 false accepts, 252 unverified-success cases, mixed timing deltas, Batch 2 systemic failure, Batch 3 miss, and authority defect change candidate support and study ordering. |
| Does the proposed research program distinguish hypotheses rather than build a preferred architecture? | Yes | D1–D4 are conditional comparisons with stop rules tied to F1–F4 predictions; no runtime mechanism is selected or implemented. |
| Could the synthesis justifiably conclude plural programs or no unified thesis? | Yes | It explicitly retains F1 as a bounded core, combines F2/F3 only as an ordered but non-collapsed program, defers F4, and revises the prior unified objective into a decision envelope. |

### 10.5 Scope audit — pass

- Every direct claim names or inherits its task, configuration, evaluator, environment, comparison, and horizon from Section 2.
- Deterministic local evidence is not generalized to learned judges, production, remote actions, adversarial settings, or long horizons.
- Source-stated external results establish candidate plausibility and counterexamples only; they are not promoted to IRIS-X findings.
- T1 is explicitly bounded, T2 is emerging, and F4 is deferred rather than silently absorbed into the core.
- Section 9 records the unsupported generalizations and global revision conditions.

### 10.6 Authorization audit — pass

- Repository-launched or follow-on model/provider executions: 0. The synthesis itself was authored in one owner-authorized GPT-5.6 Sol Ultra session.
- Experiments authorized or launched for execution: 0. Studies D1–D4 are unexecuted discriminating proposals, not selected executions.
- New runtime mechanisms: 0.
- Phase 7 or next phase declared: no.
- All eight Phase 6 gate statuses preserved; zero triggers.
- Future studies are unexecuted hypotheses requiring new owner authorization.

## 11. Primary source and authority index

### IRIS-X direct and adjudicative authorities

- [Phase 4 closure](phase-4-closure.md)
- [Phase 4 mechanism results](phase-4-mechanism-experiment-results.md)
- [Phase 4 evidence/interception results](phase-4-evidence-interception-results.md)
- [Phase 5 architecture consolidation](phase-5-architecture-consolidation.md)
- [Phase 5 capability trigger review](phase-5-capability-trigger-review.md)
- [Phase 6 capability pressure and attribution](phase-6-capability-pressure-and-failure-attribution.md)
- [Phase 6 direct pressure sampling](phase-6-direct-pressure-sampling.md)
- [Phase 6 sampling-path repair](phase-6-sampling-path-repair-and-requalification.md)
- [Phase 6 predicate/provenance authority repair](phase-6-predicate-provenance-authority-repair.md)
- [Phase 6 formal closure and research state](phase-6-formal-closure-and-research-state.md)
- [Durable Phase 6 state](../docs/phase-6-research-state.md)

### Predecessor primary authorities

- src.eidos — [Eidos README](../sources/predecessors/eidos/README.md)
- src.spex — [SPEX project state](../sources/predecessors/spex/docs/current/PROJECT-STATE.md)
- src.vanta — [VANTA evidence/verifier specification](../sources/predecessors/vanta/docs/02_specs/Evidence_Packet_and_Verifier_Runtime.md)
- [VANTA commit/abort/replay semantics](../sources/predecessors/vanta/docs/02_specs/Commit_Abort_Replay_Semantics.md)
- [VANTA failure taxonomy](../sources/predecessors/vanta/docs/02_specs/Failure_Taxonomy_v0.md)
- src.iris — [IRIS-X predecessor design](../sources/predecessors/iris/IRIS-X.md)

### External primary repositories and papers

- src.routellm / art.routellm-paper — [RouteLLM repository](../sources/external/routellm/README.md) and [paper](../references/papers/ROUTELLM_paper.pdf)
- src.frugalgpt / art.frugalgpt-paper — [FrugalGPT repository](../sources/external/frugalgpt/README.md) and [paper](../references/papers/FrugalGPT_paper.pdf)
- src.dspy — [DSPy repository](../sources/external/dspy/README.md)
- src.gepa / art.gepa-paper — [GEPA repository](../sources/external/gepa/README.md) and [paper](../references/papers/GEPA_paper.pdf)
- src.aflow / art.aflow-paper — [AFlow repository](../sources/external/aflow/README.md) and [paper](../references/papers/AFLOW_paper.pdf)
- src.agent-lightning / art.agent-lightning-paper — [Agent Lightning repository](../sources/external/agent_lightning/README.md) and [paper](../references/papers/Agent_Lightning_paper.pdf)
- src.prime-agent — [Prime Agent repository](../sources/external/prime_agent/README.md)
- src.prime-intellect-verifiers-v1 — [Prime verifiers repository](../sources/external/prime_intellect_verifiers_v1/README.md)
- src.nemo-agent-toolkit-develop — [NeMo Agent Toolkit repository](../sources/external/NeMo-Agent-Toolkit-develop/README.md)
- art.nvidia-slm-paper — [NVIDIA SLM position paper](../references/papers/NVIDIA_SLM_paper.pdf)
- art.nvidia-avo-paper — [NVIDIA AVO paper](../references/papers/NVIDIA_AVO_paper.pdf)

## Decision record

This synthesis retains F1 as the presently supported scientific center, retains F2 and F3 as a conditional downstream program with separate constructs and evidence requirements, and defers F4 until a continuity-dependent task supplies pressure. It revises the prior success–reliability–cost proposition into a decision envelope. It does not select a runtime, optimizer, router, cascade, workflow, model, next experiment, or next phase.
