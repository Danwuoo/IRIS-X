# F1 Research Charter and Adversarial Specification

- **ID:** `note-2026-09-13-f1-research-charter`
- **Status:** hypothesis
- **Question/scope:** Whether claim–evidence–authority relations are an independently discriminating theory of reliable agentic commitment within a declared task/configuration/verifier/action/horizon boundary. This note does not prove F1, create Phase 7, authorize an experiment, or make F1 a final architecture.
- **Corpus records:** `exp-2026-08-30-source-snapshot-assertion`; `exp-2026-08-30-docops-acceptance-verification`; `exp-2026-08-30-docops-evidence-binding`; `exp-2026-08-30-preexecution-write-interception`; `phase-6-pressure-sampling-v0/batch-3`; `phase-6-predicate-authority-repair-v0`; preserved Eidos, SPEX, and VANTA sources.

## Status and decision boundary

F1 remains the provisional bounded foundational center: **evidence-governed warranted agency**. The strongest defensible current result is narrower:

1. F1-A separability is supported in deterministic, locally authored development fixtures.
2. F1-B incremental decision value is inferred from rule-conformance and research-adjudication effects, but independent value beyond the rules that define warrant is not established.
3. F1-C cross-construction generalization, F1-D agency relevance, and F1-E practical non-dominance are not established.

This result leaves F1 free to be retained, narrowed, split, or rejected. It does not alter historical Phase 6 classifications. In particular, Batch 3 P4 remains one sampled task/configuration-level pressure observation; it does not establish intrinsic model incapability or the benefit of routing, retry, escalation, or a stronger allocation. The post-Batch-3 authority repair remains separate from historical Result D, and zero of eight deferred capability gates are directly triggered.

The declared boundary for this charter is the tuple:

`(task contract, producer configuration, verifier configuration, acceptance policy, authority policy, permitted action, initial state, decision horizon)`.

No claim below generalizes outside its stated tuple without new evidence.

## Evidence language

- `directly_observed`: present in a preserved run artifact or deterministically reproducible code path inspected in this session.
- `source_stated`: asserted by an imported source or external primary publication; it is not direct IRIS-X evidence.
- `inferred`: a reasoned bridge from observed or source-stated material; the bridge is defeasible.
- `unknown`, `Not established`, `Not evaluated`, or `Conflicting evidence`: the required observation is absent, inadequate, or incompatible.

A result, its later closure note, and the foundational synthesis form one authority chain. They are not counted as independent replications.

## Primary-evidence reconstruction

| Evidence chain | Direct artifact and implementation paths | Observation | Evidence class | Boundary and adverse reading |
|---|---|---|---|---|
| H-M1a snapshot/content identity | `experiments/exp-2026-08-30-source-snapshot-assertion/inputs/challenges.json`; `.../runs/hm1a-20260830-local-01/results.json`; `.../scripts/run_experiment.py` | Across 30 records, registry assertion detected all 12 predefined identity mismatches with no false rejection; record-only accepted all 12 mismatches. | `directly_observed` | Establishes task-local identity separability. The mismatch set and expected relation were authored together, so it does not establish general provenance verification or cross-author validity. |
| H-V1a semantic verification | `experiments/exp-2026-08-30-docops-acceptance-verification/inputs/challenges.json`; `.../scripts/build_challenges.py`; `.../scripts/run_experiment.py`; `.../runs/hv1a-20260830-local-01/results.json` | Claim-only produced 108 false accepts among 180 decisions; the verifier produced zero false accepts and retained 72 true accepts. | `directly_observed` | The challenge generator, actual-outcome adjudicator, and verifier were separately implemented but share the same fixture oracle. Independence from producer claims is supported; independently grounded verifier correctness is not. |
| H-V1b evidence binding | `experiments/exp-2026-08-30-docops-evidence-binding/inputs/challenges.json`; `.../scripts/build_challenges.py`; `.../scripts/run_experiment.py`; `.../runs/hv1b-20260830-local-01/results.json` | All 288 paired outcomes were successful and semantically accepted. Evidence-bound policy made 36 complete/correct cases eligible and denied 252 missing, invalid, crossed, stale, or non-binding cases; semantic-only made all 288 eligible. | `directly_observed` | Strong evidence for relation separability. However, `verified_success_eligibility` and `false_verified_success_acceptance` incorporate evidence sufficiency in the frozen rule. The policy therefore demonstrates enforcement of a warrant definition, not by itself incremental decision value against an independent consequential oracle. |
| Batch 3 P4 pressure | `experiments/phase-6-pressure-sampling-v0/runs/batch-3/p4-dependency/raw-output.txt`; `.../verification-record.json`; `.../terminal-record.json`; `.../predicate-source-map.json` | The provider returned a usable result, the deterministic semantic verifier found a dependency-order miss, and the terminal record attributes the locus to `execution_producer` with `task_level_pressure_observed=true`. | `directly_observed` | Only one sampled frozen task/configuration miss. `model_intrinsic_capability_failure`, retry benefit, routing benefit, and stronger-allocation benefit remain `Not established`. |
| Direct-predicate authority repair | `experiments/phase-6-predicate-authority-repair-v0/definition/predicate-derivation-rules.json`; `.../runs/authority-repair-20260910/direct-predicates.json`; `.../gate-adjudication.json`; `.../validation-record.json`; `.../scripts/derive_repair.py` | Hash-bound terminal sources yield `[false, false, false, true, false, false]` for Batch 3 task pressure, while absent comparison evidence remains `unknown`. The repaired adjudication has zero direct-evidence gate triggers. | `directly_observed` | Shows that provenance-bound predicate authority changes a research decision and prevents unsupported closure. It is a research-adjudication action, not an independently evaluated external agent action. Historical Result D is unchanged. |
| H-I1a commitment timing | `experiments/exp-2026-08-30-preexecution-write-interception/inputs/experiment-definition.json`; `.../scripts/run_experiment.py`; `.../runs/hi1a-20260830-local-01/results.json` | Pre-execution interception prevented 18/18 prohibited mutations while permitting six controls; post-hoc checking observed all 18 prohibited mutations before detection. | `directly_observed` | Establishes that decision timing can change bounded filesystem outcomes. It does not compare F1 policies or show that claim–evidence–authority relations caused the benefit. |

The foundational synthesis and Phase 6 closure are authoritative summaries of these records, not additional observations. Eidos, SPEX, and VANTA supply concepts and design constraints. Their claims are `source_stated` unless backed by a separately preserved IRIS-X result.

## Operational constructs

The following definitions are deliberately non-circular.

| Construct | Operational definition | Excluded shortcut |
|---|---|---|
| `actual_outcome` | A task-state result assigned by an oracle constructed independently of the evidence/authority perturbation generator and evaluated from permitted observations after the episode. | The producer claim, evaluator verdict, or perturbation label cannot be copied into the outcome. |
| `producer_claim` | The producer's frozen-schema assertion about result, status, evidence, or proposed action. It is preserved even when false or malformed. | It is not treated as outcome merely because the process exited successfully. |
| `evidence_item` | An addressable observation or artifact with identity, content, creation context, and claimed relation to one episode or claim. | More bytes or more items do not imply relevance. |
| `evidence_validity` | Whether the item satisfies predeclared intrinsic checks, such as existence, parseability, digest, time range, or observation procedure. | Validity does not establish that the item supports this claim. |
| `evidence_binding` | A predeclared, testable relation connecting an evidence item to the exact task instance, producer episode, claim, state, and horizon for which it is offered. | Path proximity, a plausible filename, or content volume is insufficient. |
| `authority` | An ex ante policy stating which principal, source, role, or procedure may assert a specified proposition or authorize a specified action under stated conditions. | Authority never means “whoever turned out to be correct.” |
| `authority_mapping` | The frozen mapping from proposition/action classes and contexts to authorized principals or procedures, plus a deterministic or independently adjudicated conformance result. | The map cannot be retrofitted after observing task outcomes. |
| `verifier_independence` | A vector over authoring, oracle/data access, execution, incentives, and correlated failure modes. The design must declare each dimension and demonstrate at least authoring and oracle independence for D1. | A different function, process name, prompt, or model label alone is not independence. |
| `semantic_verification` | An independently specified test of whether the produced content satisfies the task semantics. Its interface excludes producer self-claims, perturbation labels, and authority decisions. Its intended competence and failure conditions are empirical. | “Semantic” cannot silently absorb provenance or authorization whenever convenient. |
| `acceptance` | A policy decision to treat a claim as usable for a declared downstream purpose. It may be informational and reversible. | Acceptance is not actual outcome. |
| `commitment` | A recorded state transition that reserves resources, updates an authoritative state, exposes a result to a dependent decision, or permits/executes a consequential action. | Merely writing an offline evaluation row is not consequential commitment unless the row controls a later decision. |
| `verified_success_eligibility` | Eligibility under a frozen policy, represented as separately observable conditions rather than used as ground truth. | It cannot be the sole oracle used to prove that the same policy is valuable. |
| `abstention` | A policy decision to make no accept/reject commitment within the decision horizon and to emit its reason. | Abstention is not silently counted as success or failure. |
| `unverified_success` | `actual_outcome=success` while the evaluated policy does not accept/commit it as verified success within the horizon. | It remains separate from false rejection and from failure. |
| boundary | The exact task, producer, verifier, authority, action, state, and horizon tuple declared above. | Results do not silently transfer across configurations or actions. |

### Construct audit

| Audit | Present finding |
|---|---|
| Authority is exogenous rather than retrospective correctness | Satisfied as a definition; **not established as a D1 dataset property** because no independently supplied authority policy and consequential oracle exist yet. |
| Verifier independence is substantive | **Not established** for H-V1a/H-V1b beyond separation from producer claims; the verifier and outcome adjudicator share the authored fixture oracle. |
| Ground truth is independent of perturbation generation | **Not established for a future D1 instrument**. Existing H-V1b variants are valid development tests, but their evidence labels and eligibility rule were built together. |
| Adjudication does not define the evaluated outcome | Satisfied for actual semantic outcomes in H-V1a/H-V1b; **not satisfied as an independent value criterion** for H-V1b `verified_success_eligibility`. |
| Verifier correctness is empirical | Required by this charter; not assumed. Existing deterministic fixture performance is bounded evidence only. |
| Evidence volume is not binding or authority | Satisfied by definition and by H-V1b crossed/unrelated/conflicting variants within its fixture boundary. |

## Separately falsifiable F1 layers

### F1-A — separability

- **Exact claim:** Within the declared boundary, actual outcome, producer claim, evidence validity, evidence binding, authority mapping, semantic verification, acceptance/commitment, and derived predicates are non-equivalent variables and can diverge.
- **Unit and horizon:** One claim/decision episode from frozen input through terminal decision and any declared post-state observation.
- **Primary evidence:** H-M1a, H-V1a, H-V1b, Batch 3 P4, and the predicate-authority repair paths listed above.
- **Evidence class:** `directly_observed`, task-local.
- **Strongest counterexample:** The existing variants were locally and jointly authored; separability could be an artifact of schema decomposition rather than a naturally recurring agent phenomenon.
- **Strongest rival explanation:** R3 measurement substrate: separate fields are good instrumentation but not a central theory of agency.
- **Discriminating prediction:** Holding task outcome fixed, crossed or non-binding evidence and an ex ante authority-map perturbation change only the policy components that consume those relations, while all raw outcome observations remain invariant.
- **Falsifier/narrowing condition:** If the variables cannot be varied independently in independently authored tasks, or their separation never changes a reproducible decision, narrow F1-A to a recordkeeping convention.
- **Present status:** `supported_within_scope`.

### F1-B — incremental decision value

- **Exact claim:** Given the same producer output and semantic-verification result, evidence binding and ex ante authority provide decision information that improves a separately defined decision vector over assertion/raw-outcome policies.
- **Unit and horizon:** A policy decision and its declared commitment/post-state result within one episode.
- **Primary evidence:** H-V1b and the post-Batch-3 direct-predicate repair.
- **Evidence class:** `inferred`; direct rule-conformance effects exist, but independent consequential value is absent.
- **Strongest counterexample:** H-V1b defines verified-success eligibility using evidence sufficiency, so evidence-bound policy necessarily wins that label; the repair enforces a research authority rule rather than a separately observed task consequence.
- **Strongest rival explanation:** R2 absorbs evidence checks into semantic correctness, or R5 treats authority as ordinary access-control conformance with no special unified theory.
- **Discriminating prediction:** Under an outcome-fixed factorial design with an independently supplied authority policy, F1-aware decisions reduce false consequential commitments beyond a competent semantic verifier without an unacceptable offset in false rejection, abstention, or resources.
- **Falsifier/narrowing condition:** If semantic verification captures essentially all benefit, or authority/binding only rename policy-defined eligibility, narrow F1 to verification plus authorization substrate.
- **Present status:** `inferred`; independent incremental value is `Not established`.

### F1-C — cross-construction generalization

- **Exact claim:** F1-B effects survive independently authored tasks, oracles, evaluators, and nontrivial verifier disagreement rather than depending on one construction's shared labels.
- **Unit and horizon:** Held-out task families and authoring strata across their complete decision horizons.
- **Primary evidence:** None. Existing local experiments and their syntheses are one development lineage.
- **Evidence class:** `Not evaluated`.
- **Strongest counterexample:** A competent independently authored verifier may eliminate the observed benefit, or a new authority map may not be identifiable independently of task correctness.
- **Strongest rival explanation:** R1 or R2 generalizes while F1's locally encoded relations do not.
- **Discriminating prediction:** Pre-frozen F1 policies retain incremental effects on held-out constructions, including disagreement cases, with no access to perturbation labels.
- **Falsifier/narrowing condition:** Effects vanish, reverse, or require relabeling on held-out constructions.
- **Present status:** `not_established`.

### F1-D — agency relevance

- **Exact claim:** Warrant relations change consequential agent commitment or action, not only the quality of research records or offline evaluation.
- **Unit and horizon:** One accept/abstain/reject decision coupled to a reversible but consequential state transition, observed through its post-state horizon.
- **Primary evidence:** H-I1a shows that pre-action control can matter; the authority repair shows research-decision effects. No experiment connects the full F1 relation to an independently valued agent action.
- **Evidence class:** `inferred` bridge only; the F1 claim itself is `Not evaluated`.
- **Strongest counterexample:** Better records coexist with identical downstream actions and utility.
- **Strongest rival explanation:** R3 measurement substrate.
- **Discriminating prediction:** Outcome-fixed authority/binding perturbations change only warranted commitments, and those choices change independent action-success or policy-compliance outcomes.
- **Falsifier/narrowing condition:** F1 improves trace quality but never alters a consequential decision, or altered decisions have no independent benefit.
- **Present status:** `not_established`.

### F1-E — practical non-dominance

- **Exact claim:** Within the declared boundary and base rates, F1's reduction in false commitment is not systematically dominated by false rejection, abstention, verification/adjudication resources, or credible latency.
- **Unit and horizon:** A predeclared batch-level outcome vector, stratified by task family and policy, through completion of verification and commitment.
- **Primary evidence:** Existing H-M1a/H-V1a/H-V1b/H-I1a resource fields are bounded feasibility observations, not a common comparative decision study.
- **Evidence class:** `Not evaluated`.
- **Strongest counterexample:** An always-abstain policy can eliminate false commitment while being useless; an expensive verifier can do the same while exceeding the decision budget.
- **Strongest rival explanation:** R1 supplies better coverage/cost at the same false-commitment rate, or R2 matches benefit with lower overhead.
- **Discriminating prediction:** F1 occupies a non-dominated point in the full outcome/resource vector under frozen thresholds and declared costs.
- **Falsifier/narrowing condition:** Every F1 operating point is weakly worse on all relevant outcomes and strictly worse on at least one, or the result depends on hiding an unmeasured cost.
- **Present status:** `not_established`.

Evidence for F1-A is not counted as evidence for F1-C, F1-D, or F1-E. Any future upgrade requires its own inferential bridge and observations.

## Steelmanned rival accounts

| Rival | Strong form | Observation that would make it preferable to full F1 |
|---|---|---|
| R1 — calibrated outcome-only | Reliable commitment is primarily a selective-prediction problem. A calibrated probability of actual success plus a frozen risk/coverage threshold is sufficient; provenance and authority are metadata unless they predict outcome. | On held-out consequential tasks, a genuinely calibrated outcome policy matches or beats F1 on false commitment and action outcomes while achieving better coverage, abstention, and resources. Authority perturbations change records but add no independent decision value. |
| R2 — semantic-verification-only | The core problem is verifier competence. A sufficiently independent semantic verifier can determine whether the result is acceptable; evidence binding and authority are either inputs to semantics or redundant policy plumbing. | An independently authored verifier absorbs essentially all false-commitment reduction. Adding binding/authority yields no reproducible action benefit and only adds rejection, abstention, or cost. |
| R3 — measurement-substrate | Claim/evidence/provenance/authority separation is excellent scientific and operational hygiene, but the central agent phenomenon is elsewhere: task competence, control, or outcome selection. | F1 improves auditability, adjudication reproducibility, and error localization while consequential commitments, task success, and post-state utility remain unchanged. |
| R4 — full F1 | Reliable agentic commitment requires explicit relations among claim, evidence, authority, verification, and action. These relations provide incremental, generalizing, practically useful decision information. | R4 is preferred only if it adds held-out consequential decision value beyond R1 and R2, survives independent construction and verifier disagreement, and is not dominated on the full outcome/resource vector. |
| R5 — authorization-logic decomposition | Provenance, evidence checking, semantic verification, and authorization are useful but already separable mechanisms. Their conjunction need not be a distinctive unified theory of agent reliability. | A factorized calibration + verification + standard authorization model predicts every D1 effect without an F1-specific interaction, construct, or transfer advantage. |

Each rival can win. A D1 design that labels any R1, R2, R3, or R5 victory as instrument failure is invalid.

## Bounded novelty differentiation audit

The audit used preserved IRIS-X sources first and targeted primary literature second. It is not an exhaustive novelty search.

| Antecedent | Explanandum and unit | Relevant distinctions and manipulation | Consequential connection | Differentiation result |
|---|---|---|---|---|
| Eidos preserved source (`sources/predecessors/eidos/eidos.yaml`, `docs/index.json`) | Epistemic governance and typed authority records; repository/document unit | Source-stated distinctions among authority, provenance, and governed records; no completed governed corpus in the inspected bootstrap state | Intended research governance | Conceptual antecedent, not empirical F1 support. |
| SPEX preserved source (`sources/predecessors/spex/docs/current/PROJECT-STATE.md`) | Measurement validity, evidence, adjudication, and uncertainty; experiment/result unit | Separates observed evidence from inference and authority | Research decisions, not evaluated agent action | Strong R3 antecedent. F1 must show more than scientific hygiene. |
| VANTA preserved specs (`sources/predecessors/vanta/docs/02_specs/Evidence_Packet_and_Verifier_Runtime.md`; `Commit_Abort_Replay_Semantics.md`) | Verified execution and controlled commit; execution/action unit | Source-stated evidence packets, provenance, verifier outcomes, authorization, commit/abort/replay | Explicit action authorization and side effects | Close architectural antecedent. Its own reports leave schema adequacy, verifier disagreement, and empirical sufficiency open. |
| Calibration and selective prediction ([Guo et al. 2017](https://proceedings.mlr.press/v70/guo17a.html); [Geifman & El-Yaniv 2017](https://arxiv.org/abs/1705.08500)) | Confidence/correctness and risk–coverage at prediction level | Does not generally separate claim, evidence binding, or authority; varies confidence threshold/coverage | Abstain/accept prediction decisions | Strong R1. F1 must beat a real calibrated selective baseline, not self-reported confidence. |
| W3C PROV-O ([Recommendation](https://www.w3.org/TR/prov-o/)) | Provenance of entities, activities, agents, derivation, and attribution | Rich provenance relations; not an experiment holding outcome fixed | Supports trust/quality assessment, usually not a specific agent commitment policy | Binding/lineage are mature substrate concepts. |
| in-toto and SLSA ([in-toto paper](https://www.usenix.org/conference/usenixsecurity19/presentation/torres-arias); [SLSA provenance](https://github.com/slsa-framework/slsa/blob/main/spec/build-provenance.md)) | Software-supply-chain step/material/product identity and builder provenance | Signed metadata, expected steps/actors, and artifact digests; can hold artifact content fixed while provenance differs | Verification gates artifact consumption | Strong antecedent for binding plus authority. D1 must identify an agent-level empirical contribution beyond applying attestation. |
| Access-control logics, PolicyMaker, and proof-carrying authorization ([Abadi et al.](https://homepages.inf.ed.ac.uk/gdp/publications/Calculus_for_Access_Control.pdf); [PolicyMaker](https://www.mattblaze.org/papers/pmcomply.pdf); [proof-carrying authentication](https://www.cs.princeton.edu/~appel/fpcc.html)) | Whether a principal/request is authorized under policy and credentials | Explicitly separates who says a statement from whether that principal is trusted to say it | Direct authorization decision | Strong R5. Authority-aware action is not novel merely because it is added to an agent record. |
| Assurance cases ([SEI report](https://www.sei.cmu.edu/documents/1222/2012_005_001_28161.pdf)) | Confidence in a claim supported by evidence through argument | Claim–evidence relations and defeaters are central; experimental manipulation is not generally the focus | Safety/assurance decisions | Strong conceptual overlap with F1's warrant language. |
| Runtime assurance / Simplex ([Neural Simplex Architecture](https://arxiv.org/abs/2102.12981)) | Safe control under an unverified advanced controller; control-cycle unit | Switches authority to a verified backup based on a monitor, with outcome/safety consequences | Consequential runtime action | Establishes mature action-assurance framing; does not by itself unify producer claims, binding, and epistemic authority. |
| Agent evaluation and safety ([ToolEmu](https://arxiv.org/abs/2309.15817); [AgentDojo](https://arxiv.org/abs/2406.13352); [MT-Bench](https://arxiv.org/abs/2306.05685)) | Agent trajectory/task utility, security failures, and evaluator reliability | Evaluates outputs or trajectories and exposes evaluator/judge failure; authority/binding factorials are not the central manipulation | Tool use and security outcomes can be consequential | Strong antecedent for verifier unreliability and action-level outcomes. D1 needs independent oracles and disagreement cases. |
| Preserved RouteLLM and FrugalGPT papers (`references/papers/ROUTELLM_paper.pdf`; `references/papers/FrugalGPT_paper.pdf`) | Cost/performance allocation over queries | RouteLLM learns a strong/weak model choice from preferences; FrugalGPT optimizes prompt/model cascades under budget | Changes provider/model allocation | Adjacent to F2/F3, not evidence for F1. Their outcome/cost framing strengthens R1 and the need to keep configuration sufficiency separate. |

Across these antecedents, the components of F1 are not individually new. Claim–evidence arguments, provenance binding, authority, authorization, abstention, verification, and runtime assurance all have mature lineages. **`novelty_not_established`** is therefore the only justified novelty verdict.

What remains plausibly differentiating—but unproven—is a controlled agent study that jointly and independently manipulates these relations while holding actual outcome fixed, preserves evaluator disagreement, and measures consequential commitment plus the complete resource/coverage tradeoff. That is a candidate empirical contribution, not a novelty claim.

## Retain, narrow, split, or reject rules

- **Retain F1-A** only within demonstrated task families while separability and reproducibility remain observed.
- **Retain F1-B as central** only after an independent consequential oracle shows incremental value beyond R1/R2 and standard authorization.
- **Narrow F1 to measurement substrate** if R3 wins: preserve its records and adjudication discipline, but stop calling it the central agent phenomenon.
- **Split F1** into epistemic verification and authorization/commit control if R5 predicts the data without an interaction or transfer advantage.
- **Reject full F1 as the foundational center** if calibrated outcome-only or semantic-verification-only policies dominate across independently constructed tasks, or if authority cannot be operationalized exogenously.
- **Do not promote F1-C/D/E** from one favorable batch. Each needs an independent result and boundary statement.

## Uncertainty and exclusions

- Whether natural agent failures exhibit enough outcome-fixed claim/evidence/authority disagreement for useful estimation is `Unknown`.
- Whether semantic verification can be bounded independently of authorization semantics is `Unclear` and task-dependent.
- F1's cross-model, cross-task, and cross-author generalization is `Not evaluated`.
- Human/manual cost is `Unknown` unless directly measured.
- Temporal and state-transition reliability remains deferred until a continuity-dependent task supplies direct pressure.
- Minimum-sufficient configuration and failure-directed intervention remain distinct downstream constructs. Batch 3 P4 does not collapse them into F1.

## Follow-ups

The smallest warranted follow-up is model-free: obtain an independently authored, sealed task/oracle package; an ex ante authority policy supplied by a legitimate policy owner; an independently authored semantic verifier with declared failure cases; and a held-out calibration split for the exact future producer configuration. Only then should deterministic D1a qualification test whether R1–R5 can each win a coherent region. No provider call is needed for that step.
