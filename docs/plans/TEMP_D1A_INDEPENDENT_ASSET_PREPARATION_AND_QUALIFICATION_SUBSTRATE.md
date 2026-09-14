# TEMP — D1a Independent Asset Preparation and Qualification Substrate

Status: **Owner-scoped / not started**  
Date: **2026-09-14 Asia/Taipei**  
Repository: **Danwuoo/IRIS-X**  
Required baseline `main`: **`b62ec56b029f0478911e9454f9a3cde7d054cd54`**  
Primary development session: **one continuous GPT-5.6 Sol / High reasoning session**  
Phase authority: **none; this plan does not create Phase 7**  
Architecture authority: **none; D1a qualification-substrate development only**  
Repository model/provider calls authorized: **0**  
Background launches authorized: **0**  
Model judges authorized: **0**  
D1b/live producer execution authority: **none**  
Hard terminal boundary: **STOP after deterministic D1a preparation/qualification-substrate development, validation, handoff, and commit; do not launch or collect any live model-produced D1 batch**

---

## 1. Owner intent and scientific purpose

The prior F1/D1 XHigh session terminated correctly with `needs_revision` at commit
`b62ec56b029f0478911e9454f9a3cde7d054cd54`.

That session established the present boundary:

- F1-A separability is supported only within bounded deterministic IRIS-X fixtures;
- F1-B incremental decision value remains `inferred`;
- F1-C cross-construction generalization is `Not established`;
- F1-D agency relevance is `Not established`;
- F1-E practical non-dominance is `Not established`;
- wider novelty is `novelty_not_established`;
- D1 remains scientifically promising but is not yet identifiable because the
  repository lacks independently authored task/oracle assets, an exogenous
  authority policy, an independently authored semantic verifier with explicit
  disagreement/failure cases, and an exact-configuration calibrated outcome
  baseline.

The next task is therefore **not** to obtain more model outputs and **not** to
weaken D1 until it fits available artifacts. It is to build the deterministic,
provenance-safe qualification substrate required for independent custodians to
supply those missing assets without contaminating one another.

The controlling question is:

> **What minimum fail-closed schemas, role boundaries, sealing procedures,
> deterministic comparator implementations, meta-fixtures, negative controls,
> validation rules, and assembly gates are required so that independently
> authored D1a assets can later be admitted and tested without allowing the
> coordinating session to manufacture the independence that D1 is supposed to
> measure?**

This task develops the D1a research instrument. It does not itself establish the
independent empirical inputs that the instrument requires.

---

## 2. Controlling authorities

All applicable repository instructions remain authoritative, especially:

- `AGENTS.md`;
- `research/AGENTS.md`;
- `experiments/AGENTS.md`.

The Sol High session must directly inspect, at minimum:

- `docs/post-foundational-synthesis-research-state.md`;
- `research/foundational-research-synthesis.md`;
- `research/f1-research-charter-and-adversarial-specification.md`;
- `research/d1-held-out-warrant-generalization-spec.md`;
- `docs/f1-d1-xhigh-session-handoff.md`;
- `docs/plans/TEMP_F1_D1_SINGLE_SOL_XHIGH_RESEARCH_AND_CONDITIONAL_LAUNCH.md`;
- relevant Phase 4/5/6 primary evidence paths referenced by the F1 charter;
- `experiments/configurations/provider-model-baseline-v0.json`;
- the existing model-execution qualification substrate only to learn repository
  experiment conventions and identity/accounting patterns, not to infer D1
  evidence that is not present.

The prior F1 charter and D1 specification are the immediate research authority
for this task. Historical observations must not be reclassified.

---

## 3. Starting-state verification

Before substantive work, the Sol High session must:

1. read every applicable `AGENTS.md`;
2. inspect:
   - `git status --short`;
   - `git rev-parse HEAD`;
   - `git rev-parse origin/main`;
   - `git rev-list --left-right --count origin/main...main`;
3. verify the actual starting state is exactly, or is a clean descendant of,
   `b62ec56b029f0478911e9454f9a3cde7d054cd54`;
4. verify that the F1 charter, D1 specification, and XHigh handoff are present
   and unchanged from their controlling commit unless later owner-authored
   changes are explicitly identified;
5. record all post-baseline drift before changing files;
6. preserve unrelated owner work.

If unexplained scientific-authority drift exists, stop and report
`authority_drift_blocked` rather than building against an uncertain baseline.

---

## 4. Zero-call and independence rule

This task authorizes:

```text
repository provider/model calls: 0
background model launches: 0
model judges: 0
retries: 0
routes: 0
fallbacks: 0
escalations: 0
online optimization: 0
workflow search: 0
D1b producer executions: 0
```

The active Sol High session is the **qualification-substrate coordinator**. It is
not allowed to manufacture independent authorship by assigning itself multiple
labels.

In particular, this one session must **not** claim to be simultaneously:

- the independent task/oracle custodian;
- the independent semantic-verifier author;
- the independent authority-policy owner;
- the independent calibration custodian.

It may write neutral schemas, contracts, validators, synthetic/meta-fixtures for
instrument self-tests, and role-specific submission packets. It may audit
pre-existing repository material as a candidate input. It may not relabel
co-authored or shared-oracle material as independent merely because it lives in
another file, function, directory, source project, or process.

A later independent custodian session or human author must supply any asset whose
scientific validity depends on independent authorship.

---

## 5. Non-goals and hard prohibitions

The session must not:

- prove, promote, or finalize F1;
- revise F1-B/C/D/E upward without new independent evidence;
- claim D1a is empirically qualified merely because the harness passes synthetic
  self-tests;
- create or launch D1b;
- select a production architecture, router, retry policy, optimizer, or stronger
  model;
- create Phase 7;
- run a provider reachability check;
- run `codex exec` or any equivalent model call from the repository;
- use a model judge;
- generate hidden task/oracle labels and then call a second prompt/function
  "independent";
- derive authority retrospectively from realized correctness;
- define `actual_outcome`, `action_outcome`, and `authorization_conformance` from
  one shared label;
- substitute model self-confidence for empirical calibration;
- manufacture a P0 calibrated baseline from too-small or non-disjoint samples;
- treat predecessor/external source code as D1 evidence merely because its
  authorship is external to IRIS-X;
- modify preserved source trees or historical experiment outputs;
- silently turn `Unknown` into `false`, zero, or failure;
- change the frozen D1 interpretation matrix to make a future result easier to
  classify.

---

## 6. Required scientific invariants

The implementation must preserve the D1 specification's three independent
outcome targets:

1. `actual_outcome` — semantic task success under an independent task oracle;
2. `action_outcome` — the predeclared consequential post-state/utility result;
3. `authorization_conformance` — conformance to an ex ante authority policy.

These may correlate. They must not be defined by copying one another.

The following information barriers are mandatory:

- task/oracle assets cannot depend on evidence/authority perturbation assignment;
- authority policy cannot depend on which principal later proves correct;
- semantic-verifier authoring cannot use held-out outcome labels, authority maps,
  perturbation labels, or policy outputs;
- perturbation code cannot define task outcome or inspect hidden oracle labels;
- comparator policies cannot access fields outside their declared interfaces;
- analysis cannot revise thresholds, schemas, exclusions, or interpretation
  rules after held-out results are visible.

---

## 7. Required repository package

Develop a compact pre-execution D1a package under:

```text
experiments/d1a-warrant-discrimination-v0/
```

The directory is an **experiment-definition and qualification-development
package**, not an executed empirical result. Its top-level README/status must say
that D1a remains unqualified until independent custodian submissions are sealed,
admitted, assembled, and pass all required qualification tests.

At minimum create or adapt the following structure:

```text
experiments/d1a-warrant-discrimination-v0/
  README.md
  definition/
    experiment-definition.json
    role-boundaries.json
    episode.schema.json
    policy-contracts.json
    qualification-contract.json
    interpretation-matrix.json
    negative-control-contract.json
    provenance-contract.json
  custodian-packets/
    task-oracle-custodian.md
    authority-policy-custodian.md
    semantic-verifier-custodian.md
    calibration-custodian.md
    analysis-custodian.md
  submission-schemas/
    task-oracle-bundle.schema.json
    authority-policy-bundle.schema.json
    semantic-verifier-bundle.schema.json
    calibration-bundle.schema.json
    custodian-attestation.schema.json
  meta-fixtures/
    README.md
    ... deterministic instrument-only fixtures ...
  scripts/
    validate_submission.py
    validate_information_boundaries.py
    assemble_d1a_bundle.py
    evaluate_policies.py
    qualify_instrument.py
  tests/
    ... focused deterministic tests ...
```

Equivalent names are acceptable if they preserve the same role separation and
purpose. Avoid unnecessary hierarchy.

Do not create `runs/` containing empirical D1 results. A deterministic
qualification output may be stored only if repository convention supports a
clearly labeled development/validation record that cannot be confused with a
D1 empirical result.

---

## 8. Role-boundary and custodian packet requirements

Create role-specific submission packets derived from the frozen D1 specification.
They are instructions/contracts, not independently authored scientific assets.

### 8.1 Task/oracle custodian packet

Must require:

- at least two bounded task families if/when supplied;
- task contracts and stable instance IDs;
- post-state or semantic oracle rules defined without access to perturbation
  assignments;
- a seal manifest containing digests of all task/oracle assets;
- explicit information-boundary attestation;
- no access to future policy decisions or held-out producer outputs;
- a reversible/consequential action family if F1-D is to be tested;
- separate labeling of task truth and authorization status.

The coordinator must not fill this packet with held-out study content.

### 8.2 Authority-policy custodian packet

Must require:

- legitimate ex ante principals/roles;
- proposition/action classes they may authorize;
- deterministic conformance rule or separately adjudicable policy;
- policy defined before realized task correctness is known;
- cases where factual correctness and authorization can diverge;
- no policy that defines "authorized" as "whoever was correct";
- sealed policy identity and digest.

### 8.3 Semantic-verifier custodian packet

Must require:

- verifier scope limited to task semantics;
- no access to provenance/authority perturbation fields except fields genuinely
  required by task semantics;
- authoring independence from task/oracle custodian sufficient for the intended
  F1-C claim;
- a disjoint development set;
- explicit false-accept, false-reject, disagreement, and unknown/error cases;
- verifier identity/version/digest;
- a statement of known blind spots rather than an assumption of correctness.

### 8.4 Calibration custodian packet

Must require:

- exact producer configuration identity;
- a score construction that does not use D1 warrant/authority labels;
- disjoint calibration and held-out splits;
- empirical calibration diagnostics and sample-size disclosure;
- frozen thresholds/loss/coverage rule before D1 held-out analysis;
- a permitted `P0_unavailable` result if a fair calibrated baseline cannot be
  constructed.

The package must explicitly prefer `P0_unavailable` over a straw outcome-only
baseline.

### 8.5 Analysis custodian packet

Must require:

- only sealed inputs after all component digests are frozen;
- no authority to revise oracles, verifier logic, policies, thresholds, factor
  exclusions, or interpretation rules;
- full vector reporting before scalar preference;
- explicit R1–R5 comparison and R5 decomposition;
- quarantine of non-identifying strata.

---

## 9. Submission schemas and provenance

Each custodian submission must have:

- stable bundle ID;
- custodian role;
- author/session identity sufficient for provenance without embedding secrets;
- creation timestamp;
- source paths;
- content digests;
- dependencies and prohibited dependencies;
- information seen before freeze;
- information explicitly not seen before freeze;
- seal status;
- modification history after seal, which must normally be empty;
- compatibility version with the D1 definition package.

The validator must reject:

- missing digests;
- path traversal or ambiguous asset references;
- incompatible schema versions;
- undeclared dependencies;
- task/oracle bundles that reference perturbation assignments;
- verifier bundles that reference held-out oracle labels or authority maps;
- authority policies derived from realized correctness;
- calibration bundles that reuse held-out D1 outcomes;
- post-seal mutation unless explicitly versioned as a new bundle.

A syntactically valid submission is not automatically scientifically independent.
The validation report must distinguish:

```text
schema_valid
provenance_complete
information_boundary_declared
information_boundary_mechanically_checkable
independence_supported
independence_not_established
rejected
```

Never convert `independence_not_established` into `independent=true`.

---

## 10. Comparator policy implementation

Implement the frozen D1 policy interfaces without changing their scientific
meaning:

- **P0 — calibrated outcome baseline**;
- **P1 — semantic-verification-only**;
- **P2 — evidence-bound**;
- **P3 — authority-aware F1**.

Requirements:

- all policies receive the same canonical episode object;
- field-level access must be enforceable or auditable;
- P0 must fail closed if no admitted calibration bundle exists;
- P1 cannot inspect evidence-binding or authority fields;
- P2 may inspect evidence validity/binding but not authority mapping;
- P3 may inspect P2 fields plus authority mapping only where the task contract
  declares an authority requirement;
- on no-authority tasks, P3 must reduce bit-for-bit to P2;
- each policy emits `accept_commit`, `reject`, or `abstain`, plus a typed reason;
- policy output is not ground truth.

Keep policy functions simple enough that a later independent validator can audit
their field consumption.

---

## 11. Meta-fixtures and anti-tautology qualification

The Sol High coordinator **may and should** author deterministic meta-fixtures to
test the instrument itself. These are not D1 held-out evidence and must be
physically and semantically separated from later custodian submissions.

Meta-fixtures must demonstrate coherent synthetic win regions for:

- R1 outcome-only/calibrated baseline;
- R2 semantic-verification-only;
- R3 measurement-substrate;
- R4 full F1 incremental commitment value;
- R5 factorized verification/evidence/authorization decomposition.

Each rival must be allowed to win without the harness declaring the case invalid.

At minimum test these negative controls from the D1 specification:

1. no-authority control: P3 == P2 bit-for-bit;
2. no-warrant-increment control: P1 == P2 == P3;
3. evidence-volume control: irrelevant valid evidence changes no decision;
4. outcome-fixed authority control: raw outcome and semantic digest remain fixed;
5. verifier-failure control: frozen false accept and false reject are representable;
6. record-only control: audit/provenance improvement can occur with no action
   benefit.

The instrument fails qualification if an R4/F1 win is structurally guaranteed by
its oracle or scoring definitions.

---

## 12. Deterministic analysis and outcome vector

Implement the D1 outcome vector exactly enough to preserve separate denominators
and task-family strata for:

- actual task success/failure;
- false commitment against `actual_outcome`;
- false commitment against `action_outcome`;
- false rejection;
- unverified success;
- abstention;
- authorization error;
- verifier agreement/disagreement/false accept/false reject/error/unknown;
- invalid-record count;
- adjudication reproducibility;
- execution resources;
- verification resources;
- adjudication resources;
- provider/model call count;
- retries;
- credible latency only when measurement is valid;
- human/manual cost as `Unknown` unless measured.

No scalar reliability score is primary.

If a scalar loss is implemented for future use, it must be disabled by default,
require an explicit pre-frozen weighting configuration, and never replace the
vector or Pareto report.

---

## 13. Assembly must fail closed

`assemble_d1a_bundle.py` (or equivalent) must not fabricate missing assets.

It must refuse to assemble an identifying D1a study bundle unless all required
independent submissions are present and admitted.

Expected terminal assembly states should include at least:

```text
ready_for_meta_qualification
ready_for_independent_custodian_submission
independent_assets_incomplete
calibration_unavailable
independence_not_established
ready_for_d1a_qualification
rejected
```

`ready_for_d1a_qualification` is permitted only when the necessary independent
assets actually exist and pass their admission checks.

The coordinating Sol High session should normally expect to end at
`ready_for_independent_custodian_submission`, unless qualifying independently
authored assets already exist and survive a direct provenance audit.

---

## 14. Audit of reusable repository material

The Sol High task should inspect existing IRIS-X and preserved-source materials
for patterns or candidate assets, including prior held-out protocols,
verification guides, task contracts, provider baselines, and calibration-related
records.

For each candidate reuse, record:

- exact path and provenance;
- original purpose;
- whether authorship is actually independent of D1 construction;
- whether oracle/verifier/authority information boundaries match D1;
- whether using it would create leakage or retrofitted authority;
- disposition: `reuse_pattern_only`, `candidate_asset`, `ineligible`, or
  `Not established`.

Do not use source/project independence as a shortcut for D1 independence.

---

## 15. Tests required before terminal verdict

Focused deterministic tests must cover at least:

- schema validation for every submission type;
- digest/seal validation;
- undeclared-dependency rejection;
- role information-boundary checks;
- forbidden policy-field access;
- preservation of `unknown`;
- P3 == P2 on no-authority controls;
- P1 == P2 == P3 on no-warrant-increment controls;
- evidence-volume invariance;
- outcome-fixed authority invariance of raw outcome/semantic fields;
- verifier false-accept/false-reject representation;
- record-only R3 win region;
- coherent R1, R2, R4, and R5 win regions;
- deterministic rerun identity;
- incomplete independent assets causing assembly failure, not silent fallback;
- absent calibration causing P0 to become unavailable, not a straw baseline;
- complete outcome-vector denominators.

Run normal repository validation before finalizing.

---

## 16. Required task outputs

At minimum produce:

1. the D1a qualification-development package under
   `experiments/d1a-warrant-discrimination-v0/`;
2. a durable handoff, preferably:
   `docs/d1a-independent-asset-preparation-handoff.md`;
3. updates to `research/d1-held-out-warrant-generalization-spec.md` **only if**
   deterministic development discovers a genuine specification defect or a
   necessary clarification; do not rewrite it merely to describe implementation;
4. this TEMP plan updated only for retirement/terminal accounting if existing
   repository convention requires that pattern.

The handoff must record:

- starting and terminal SHA;
- exact files created/changed;
- repository/provider/model call accounting;
- which independence-sensitive assets remain missing;
- candidate reusable assets and their disposition;
- tests and repository validation;
- terminal readiness state;
- the smallest next owner-authorized task.

---

## 17. Terminal verdicts

The task must end with exactly one primary verdict:

### `ready_for_independent_custodians`

Use when:

- schemas, contracts, validators, comparator logic, meta-fixtures, tests, and
  fail-closed assembly are complete;
- R1–R5 each have coherent instrument-level win regions;
- negative controls pass;
- repository validation passes;
- independent scientific assets are still intentionally absent or incomplete.

This is the expected successful outcome.

### `ready_for_d1a_qualification`

Use only if independently authored, provenance-complete assets already exist or
arrive outside this coordinating session, pass all admission checks, and the
session did not itself compromise their independence.

This verdict still does **not** authorize D1b or any provider/model call.

### `needs_revision`

Use when the substrate can be repaired without changing the scientific question,
but one or more required contracts, tests, or comparator distinctions cannot be
made coherent in this task.

### `scientifically_blocked`

Use when D1's required independence or rival identifiability cannot be made
operational without changing the research question in a material way.

### `authority_drift_blocked`

Use when repository authority drift prevents safe continuation.

No verdict in this plan authorizes a model/provider call.

---

## 18. What this task may establish

If successful, this task may establish only that:

- the D1a instrument and submission boundary are implementation-ready for
  independent custodian contributions;
- the comparator logic can represent genuine R1–R5 win regions;
- the negative controls and information-barrier checks are executable;
- missing independent assets are explicit rather than silently approximated.

It must **not** claim that:

- F1-B/C/D/E is supported;
- D1a has produced an empirical result;
- D1a is held-out merely because files are sealed;
- independent authorship has been satisfied by the coordinating session;
- D1b is ready;
- a live model run is scientifically justified.

---

## 19. Expected next step after a successful task

If the verdict is `ready_for_independent_custodians`, the next work should be
separate, information-bounded custodian tasks or human submissions, not one
combined authoring session.

A sensible order is:

1. task/oracle custodian submission and seal;
2. authority-policy submission and seal;
3. independent semantic-verifier submission and seal, respecting its forbidden
   information set;
4. calibration submission for a separately owner-selected exact producer
   configuration, or an explicit `P0_unavailable` determination;
5. independent analysis/qualification after all assets are sealed.

Only a later owner-authorized task may decide whether D1a has passed and whether
D1b should be specified or launched.

---

## 20. Hard stop

After deterministic development, validation, handoff, and the normal commit:

**STOP.**

Do not:

- launch a model;
- monitor a background process;
- create D1b;
- collect new provider output;
- promote F1;
- start Phase 7;
- combine the future independent custodian roles into one follow-on task without
  explicit owner authorization and a scientific justification for preserving
  independence.
