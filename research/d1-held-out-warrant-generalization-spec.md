# D1 Held-Out Warrant Generalization Specification

- **ID:** `note-2026-09-13-d1-held-out-warrant-generalization`
- **Status:** hypothesis
- **Question/scope:** A model-free D1a qualification design that can make outcome-only, semantic-verification-only, measurement-substrate, authorization-decomposition, or full F1 explanations win. D1b model production is intentionally not frozen because D1a is not yet implementation-ready or admitted.
- **Corpus records:** the F1 evidence chains catalogued in `research/f1-research-charter-and-adversarial-specification.md`; the admitted execution substrate under `experiments/substrates/model-execution-qualification-v0`; the accepted provider baseline at `experiments/configurations/provider-model-baseline-v0.json`.

## Verdict

`needs_revision`

D1 is promising and its identification requirements can be stated, but the repository does not yet contain the independent task/oracle, exogenous authority policy, independently authored verifier, or exact-configuration calibration material needed to implement D1a without circularity. D1b is therefore not authorized, specified as a live run, frozen, or launched.

This is a successful no-launch boundary. A first live producer batch would add outputs before the rival explanations are identifiable and would turn a six-call safety ceiling into a scientifically underpowered convenience sample.

## Research question and non-claims

D1 asks:

> Do evidence binding and ex ante authority supply held-out, consequential commitment information beyond a genuinely calibrated outcome estimate and an independently authored semantic verifier?

D1 does not ask whether structured records are useful, whether semantic verification beats accepting producer assertions, or whether authorization policies can be enforced. Those are already weaker or adjacent questions. D1 also does not evaluate F2 minimum-sufficient configuration, F3 failure-directed intervention, routing, retry, escalation, or temporal continuity.

A positive D1 batch cannot prove universal F1-C, F1-D, or F1-E. It can at most create one bounded result at the exact task/configuration/verifier/action/horizon boundary.

## Identification requirements

### Required separation of roles

The following roles may be implemented by people, independently frozen code, or separately authorized sessions, but their information boundaries must be preserved and recorded:

| Role | May know | Must not define or observe before freeze |
|---|---|---|
| Task/oracle custodian | Task contract, permitted state, actual-outcome rule, consequential post-state oracle | Evidence/authority perturbation assignment; policy decisions; producer outputs used for evaluation |
| Authority-policy owner | Legitimate roles/principals and which propositions/actions they may authorize ex ante | Which principal happens to be correct in realized cases; policy scores |
| Semantic-verifier author | Task semantics and a development set disjoint from held-out cases | Held-out outcome labels, authority map, evidence perturbation labels, policy outputs |
| Perturbation implementer | Frozen evidence and authority factor definitions | Outcome construction or labels; verifier internals beyond its public interface |
| Producer | Task inputs and output schema | Held-out oracle, perturbation labels, comparator policy decisions |
| Analysis custodian | Frozen records after all components are sealed | Ability to revise oracles, factors, thresholds, or policies after observing results |

The task/oracle custodian and semantic-verifier author must be independently authored for F1-C. Code-process separation alone is inadequate. The authority-policy owner must establish authority from institutional/task rules, not from realized correctness.

### Required independent targets

D1 must preserve three targets rather than deriving them from one another:

1. `actual_outcome`: whether the task output is semantically successful under the independent task oracle.
2. `action_outcome`: whether the policy's commitment leads to the predeclared post-state/utility result.
3. `authorization_conformance`: whether the commitment was permitted by the ex ante authority policy.

Authorization conformance can be normatively defined by policy. It cannot also be the only evidence that F1 improved actual or action outcome. Conversely, an unauthorized but factually correct claim remains correct on `actual_outcome` and erroneous on `authorization_conformance`; this divergence is essential.

## D1a — model-free instrument and theory discrimination

### Qualification purpose

D1a is a deterministic, zero-provider-call instrument qualification. It must use sealed candidate outputs or fixture outputs that were authored independently of the perturbation assignments. Its purpose is not to estimate a model effect. It must demonstrate that:

- R1, R2, R3, R4, and R5 make distinct predictions;
- each rival can be preferred in at least one scientifically coherent simulated or frozen case region;
- the analysis does not define F1's advantage into the oracle;
- all outcome-vector components remain separately inspectable;
- rerunning the analysis from frozen records is deterministic.

### Episode schema

Each episode must include, at minimum:

```text
episode_id
task_family_id
task_instance_id
task_contract_digest
producer_configuration_id
producer_output_digest
producer_claim
producer_score_or_calibrated_probability
actual_outcome
actual_outcome_oracle_id
evidence_items[]
evidence_validity[]
evidence_binding[]
authority_policy_id
authority_mapping
authority_conformance
semantic_verifier_id
semantic_verifier_decision
semantic_verifier_confidence_or_not_measured
independent_disagreement_record
policy_decisions{}
commitment_record{}
action_outcome
resource_record{}
provenance{}
```

The schema must preserve `unknown` rather than coerce absent values to false.

### Factor structure

D1a must contain or deterministically generate a predeclared balanced subset of these factors while respecting logical constraints:

| Factor | Required levels | Independence requirement |
|---|---|---|
| Actual outcome | success, failure | Assigned by the task oracle, never by perturbation code. |
| Producer claim agreement | agrees with outcome, diverges from outcome | Uses frozen candidate outputs/claims; no policy relabeling. |
| Evidence validity/binding | valid-and-binding, invalid, valid-but-non-binding, absent | Perturbation changes evidence relations while task output/outcome digest remains fixed. |
| Authority mapping | canonical, unauthorized-principal, missing/ambiguous where policy permits | Mapping changes while task output and actual outcome remain fixed. Canonical authority is defined ex ante. |
| Semantic verifier | correct agreement, false accept, false reject, explicit disagreement/unknown | Obtained from an independently authored verifier or frozen failure fixtures, not stipulated to favor F1. |
| Action relevance | consequential commitment, informational negative control | Post-state oracle is separate from authorization conformance. |
| Base-rate/calibration stratum | at least two frozen risk strata | Derived from a disjoint calibration set for the exact producer/configuration. |

Not every full-factor combination is coherent. For example, `authority_mapping` applies only where a proposition or action has an authority requirement. Exclusions must be declared before analysis; they cannot be chosen after seeing policy performance.

### Case families

At least two independently authored task families are required:

1. **Semantic-result family:** a bounded transformation or decision task with deterministic post-state truth, where correct and incorrect producer claims occur and semantic verification has plausible false-positive/false-negative modes.
2. **Authorized-commit family:** a reversible consequential state transition whose factual preconditions and authorization policy are distinct. The same correct proposed action can be authorized under one ex ante principal mapping and unauthorized under another without changing its factual correctness.

A third **record-only family** is the required R3 control: evidence and authority metadata can affect audit records, but the experiment deliberately exposes no policy-controlled consequential action. Full F1 should add no action benefit here.

No task may be adapted from its own evaluator's expected output. The held-out task instances and post-state oracle must be sealed before the perturbation implementation sees them.

## Comparator policies

All four required policies operate on the same episode and issue one of `accept_commit`, `reject`, or `abstain`. Their interfaces are frozen and logged. None is the ground truth.

### P0 — calibrated outcome baseline

P0 uses only a calibrated estimate `q = P(actual_outcome=success | permitted producer/task features)` and a threshold or decision rule selected on a disjoint calibration split under a frozen loss/coverage constraint. It cannot inspect producer evidence, authority, or verifier decisions.

Requirements:

- calibration must be measured for the exact producer configuration and score construction;
- self-reported confidence without empirical calibration is inadmissible;
- threshold selection and any loss weights precede the D1 held-out set;
- if no valid probability/score exists, P0 is missing and D1a fails rather than substituting a straw baseline.

### P1 — semantic-verification-only

P1 consumes the producer output and the independently authored semantic-verifier result. It ignores evidence binding and authority mapping. Its disagreement and verifier-error rules must be frozen, including when it abstains.

The semantic verifier's scope is task-content satisfaction. It may inspect task inputs required for semantics but not provenance/authority fields. If authorization is itself part of task semantics, that task cannot identify R2 versus R4 and must be excluded or separately classified.

### P2 — evidence-bound

P2 applies P1 and additionally requires the predeclared evidence items to be valid and bound to the exact episode/claim/state/horizon. It does not consume the authority map. Missing, invalid, and non-binding evidence remain distinguishable in the record even if the decision rule maps several to abstention.

### P3 — authority-aware F1

P3 applies P2 and, only where the task contract declares an authority requirement, requires conformance to the independently supplied ex ante authority map before commitment. On tasks with no authority requirement, P3 must reduce exactly to P2.

P3 is not declared correct because it conforms to policy. Its effects are evaluated independently on actual outcome, action outcome, authorization error, coverage, and resources.

### R5 decomposition analysis

The primary comparison is the four policy vector, but analysis must also fit or tabulate a factorized account with separate calibration, semantic-verification, evidence-integrity, and authorization components. Full F1 requires an interaction, transfer, or explanatory economy not already exhausted by this decomposition; otherwise R5 is preferred.

## Required outcome vector

No primary scalar reliability score is authorized for D1a or D1b. For every policy, preserve counts/rates with denominators and task-family strata for:

- actual task success/failure;
- false commitment / false accept, defined against `actual_outcome` and separately against `action_outcome`;
- false rejection;
- unverified success;
- abstention;
- authority error, including unauthorized acceptance and authorized rejection;
- verifier agreement, disagreement, false accept, false reject, and error/unknown;
- adjudication reproducibility and invalid-record count;
- execution resources;
- verification resources;
- adjudication resources;
- latency only if timestamps and measurement method are credible;
- provider/model calls and retries;
- human/manual cost as `Unknown` unless directly measured.

If a later decision rule needs a scalar loss, it must be frozen before held-out data, report its component weights, and never replace the vector. Pareto non-dominance should be reported before any weighted preference.

## Negative and discriminating controls

1. **No-authority negative control:** all eligible principals are equivalent and no authority-specific action constraint applies. P3 must equal P2 bit-for-bit; an apparent P3 advantage invalidates the instrument.
2. **No-warrant-increment control:** semantic verification is correct, all required evidence is valid/bound, and authority is canonical. P1, P2, and P3 should make the same decision. Differences indicate policy leakage or unnecessary abstention.
3. **Evidence-volume control:** add valid but irrelevant evidence items without changing the required binding. P2/P3 must not improve merely because evidence volume increases.
4. **Outcome-fixed authority control:** change authorized principal while preserving exact task input, producer output, semantic result, and actual outcome digests. Only authority-consuming decisions and authorization-conformance fields may change.
5. **Verifier-failure control:** include a frozen false accept and false reject from an independent verifier. This allows R1 or F1 policies to outperform R2 without declaring the verifier path broken.
6. **Record-only control:** let F1 improve provenance/audit resolution while no consequential action is exposed. This is a valid R3-win region.

## Theory-discrimination qualification

Before any D1b production, deterministic fixtures must demonstrate all of the following:

| Required win region | Qualifying pattern |
|---|---|
| R1 can win | Calibrated outcome risk preserves correct commitments that a false-negative verifier rejects, with equal or better false commitment and lower resource cost. |
| R2 can win | An independent semantic verifier captures task failures; evidence/authority factors are irrelevant or canonical, so P2/P3 add no benefit and may add cost or abstention. |
| R3 can win | Binding/authority improve record validity and adjudication reproducibility but cannot change any consequential action or independent utility outcome. |
| R4 can win | Outcome is fixed, semantic verification alone would commit, but non-binding evidence or ex ante unauthorized provenance predicts an independently observed harmful/invalid commitment; P3 prevents it without dominated tradeoffs. |
| R5 can win | Separate evidence-integrity and authorization terms explain the P3 effect fully; no unified interaction or cross-family transfer remains. |

This is the anti-tautology criterion: **the instrument is qualified only if each rival can win without the study being declared broken.** At present, none of these regions has been implemented as a frozen D1a artifact.

## Frozen interpretation matrix for a future qualified D1

These interpretations are fixed at specification version 1. A materially changed D1a must version this document and refreeze the matrix before any live output.

| Observed pattern | Required interpretation |
|---|---|
| Outcome-only is sufficient | Prefer R1 within the tested boundary; narrow or reject F1-B/D there. Preserve F1-A as measurement separability only. |
| Semantic verification absorbs essentially all benefit | Prefer R2; split or narrow binding/authority to optional substrate unless a different independent action boundary is justified. |
| F1 improves research records but not consequential commitments | Prefer R3; retain F1 as research/evaluation hygiene, not the central agent phenomenon. |
| F1 adds incremental commitment value | Provisionally support F1-B and bounded F1-D only for the tested boundary; do not infer universal F1-C/E. Test R5 decomposition before calling the effect uniquely F1. |
| False-commitment reduction is dominated by false rejection, abstention, or resources | Do not retain a practical F1 advantage; classify F1-E as narrowed or unsupported even if F1-B changes decisions. |
| Verifier or authority independence is not established | Result is non-identifying. Return `needs_revision` or `scientifically_blocked`; do not score it as evidence for any full account. |
| A new live confound appears | Quarantine the affected stratum, preserve raw records, and withhold theory adjudication. Do not modify criteria post hoc. |
| Factorized authorization/verification explains all gains | Prefer R5; split F1 rather than claim a unified theory. |
| Policies are indistinguishable because the batch lacks disagreements | Treat as uninformative, not support for equivalence or F1. |

## D1a reproducibility and analysis freeze

An implementation-ready D1a package must contain separate directories for definition, inputs, scripts, raw deterministic records, and interpretation, following `experiments/AGENTS.md`. It must freeze:

- JSON schemas and stable identifiers;
- all task/oracle and authority-policy digests;
- role/authoring provenance and information-boundary attestations;
- factor exclusions and sampling rule;
- calibration split, method, diagnostics, and thresholds;
- exact comparator functions and abstention/disagreement rules;
- negative-control expected invariants;
- outcome-vector calculations and denominators;
- invalid-record and missing-data handling;
- interpretation matrix;
- deterministic tests that deliberately produce R1–R5 win regions.

Analysis must fail closed on unknown schema fields, digest mismatch, oracle access by perturbation code, policy access to forbidden fields, or incomplete outcome vectors. It must never turn `unknown` into false.

## Current D1a qualification audit

| Requirement | State | Consequence |
|---|---|---|
| Independent task/oracle construction | Missing | No D1 held-out task set or sealed post-state oracle exists. |
| Outcome/claim agreement and divergence | Design specified; fixture not built | Cannot qualify policy behavior. |
| Valid/invalid/non-binding evidence | Existing H-V1b is reusable as a development pattern, not an independent D1 target | New independently grounded cases are required. |
| Exogenous authority-map perturbation with fixed outcome | Missing | Locally inventing both map and value target would make authorization “win” by construction. |
| Independent verifier disagreement/failure cases | Missing | H-V1a shares its task oracle with outcome adjudication. |
| Calibrated outcome baseline | Missing | Existing live outputs do not provide a held-out, exact-configuration calibrated score. |
| Comparator policies and outcome vector | Specified, not implemented | No frozen reproducible analysis logic exists. |
| Negative controls | Specified, not implemented | Invariants are not executable. |
| R1–R5 can each win | Required by design, not demonstrated | Anti-tautology gate fails. |

Therefore D1a is **not scientifically qualified and not implementation-ready**.

## D1b — conditional model-produced batch

D1b may be developed only after D1a passes all qualification tests. Its limited purpose would be to produce a first frozen set of producer outputs for later independent collection and adjudication. It would not prove warrant generalization.

Because D1a has not passed, this session deliberately does **not** freeze:

- a producer model/provider configuration;
- a live task/input set or sampling rule;
- a call count below the absolute ceiling;
- a launch command;
- live run artifact locations;
- a D1b experiment identifier.

The repository contains a previously admitted read-only, no-tool, no-retry Codex CLI substrate for an exact historical environment and an accepted provider/model baseline. Those are candidate commodity substrates only. They do not cure D1's missing scientific assets, and their admission must be revalidated at the eventual freeze SHA.

Any eventual D1b must obey the controlling plan: one background launch, at most six total provider/model calls, zero retries/routes/fallbacks/escalations/online optimization/model judges/follow-on tasks, external launcher stdout/stderr, exactly one immediate process confirmation, and no result inspection until a later owner-authorized collection turn. If the smallest defensible balanced batch needs more than six calls, the verdict remains `needs_revision`; the study must not be shrunk until it loses discrimination.

## Live-execution admission gate audit

The controlling plan requires all gates to pass simultaneously.

| Gate | Current status | Basis |
|---:|---|---|
| 1. F1-A through F1-E are separately operationalized and falsifiable | Pass at charter level | Exact claims, units, rivals, predictions, and falsifiers are specified. |
| 2. R1–R4 are genuine rivals with win conditions | Pass at theory level | R1–R4 plus R5 have non-failure win conditions. |
| 3. Constructs are non-circular enough to distinguish rivals | **Fail** | No exogenous D1 authority policy; semantic verification versus authorization remains task-dependent and uninstantiated. |
| 4. D1a is complete, reproducible, scientifically discriminating, and locally qualified | **Fail** | No D1a instrument or independent assets exist. |
| 5. Negative controls and F1 loss conditions exist | Pass at specification level; unqualified in code | Controls are frozen conceptually but not executable. |
| 6. Exact live producer configuration is justified and frozen | **Fail** | Sequencing prohibits a D1b freeze before D1a passes. |
| 7. Task/input set, sampling, call ceiling, output schema, policies, and analysis are frozen | **Fail** | Schema requirements exist, but no independent inputs, sample, or scientifically defensible call count exist. |
| 8. Exact provider/model call ceiling is finite and no greater than six | **Fail** | The safety maximum is known, but no scientifically justified D1b batch size is frozen. |
| 9. Retries, routes, fallbacks, escalations, judges, online optimization, search, and recovery are disabled | Not reached | The specification requires zero of each, but no executable D1b package exists to verify. |
| 10. Action environment is read-only or explicitly bounded | Pass as a required boundary; not frozen for D1b | Read-only/no-tool is plausible, but no live configuration is selected. |
| 11. Definition, inputs, scripts, and expected schema are committed | **Fail** | Correctly not created while D1 is blocked. |
| 12. Normal repository checks pass without unexplained failures | Pass for the research package | `repository_check.py` and `git diff --check` pass; no D1a-specific preflight exists. |
| 13. Tree is clean at freeze SHA | Pending | Can only be assessed after a future admitted package is committed. |
| 14. TURN-A protocol can be obeyed | Pass procedurally | The boundary is explicit; no launch is authorized. |

Multiple mandatory conditions fail. `ready_for_launch` is unavailable.

## Exact blockers

1. **Shared-oracle verifier evidence:** H-V1a/H-V1b establish producer/verifier separation but not independently grounded verifier competence; the verifier and outcome adjudicator use the same authored fixture oracle.
2. **Criterion leakage in H-V1b:** the evidence-bound advantage is measured partly by a verified-success eligibility label that itself requires evidence sufficiency. It cannot serve as the independent action-value target for D1.
3. **No exogenous authority target:** the repository lacks a pre-existing legitimate authority policy coupled to a separate consequential outcome. Authoring both policy and favorable cases in this session would test rule enforcement, not discover F1 value.
4. **R2/R5 identifiability:** unless semantic-verifier scope and standard authorization are fixed independently, full F1 can absorb their functions by definition and cannot lose fairly.
5. **No calibrated R1 baseline:** there is no disjoint calibration set and valid success score for the exact future producer configuration. Self-reported confidence would be an unfair comparator.
6. **No cross-construction assets:** the same primary session cannot honestly manufacture independent task/oracle and verifier authorship after seeing the target theory.

These blockers are resolvable design/provenance gaps rather than proof that discrimination is impossible, so the verdict is `needs_revision`, not `scientifically_blocked`.

## Smallest next research step

Authorize a **zero-provider-call D1a asset-preparation turn** with separated custodians:

1. a task/oracle custodian supplies two small sealed task families, post-state oracles, and a legitimate ex ante authority policy;
2. an evaluator author supplies a semantic verifier and frozen disagreement/failure fixtures without seeing authority/evidence perturbation assignments;
3. a calibration custodian supplies a disjoint score/outcome split for the exact candidate producer configuration, or documents that no valid P0 can be built;
4. only then, a primary session implements the deterministic comparator instrument and demonstrates every R1–R5 win region and negative-control invariant.

That step should create the experiment package only when the independent inputs exist. It requires no model/provider call and does not create a new phase.

## Uncertainty

- Whether a six-call D1b can be scientifically meaningful after balanced D1a qualification is `Unknown`; no call count should be chosen yet.
- Whether authority perturbations can be both realistic and outcome-fixed in the selected task family is `Not established`.
- Whether an exact-config calibrated outcome baseline can be constructed without additional model calls is `Unknown`.
- Human/manual cost is `Unknown` unless the future package measures it.
- Novelty remains `novelty_not_established` as documented in the F1 charter.
