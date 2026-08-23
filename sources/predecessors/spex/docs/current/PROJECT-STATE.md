# PROJECT STATE

- **State version:** v0.9
- **Last updated:** 2026-08-06
- **Evidence cutoff:** Evidence Base v1.1 / Evidence Adjudication v1; ARC external-source snapshot through 2026-07-31
- **Operational snapshot:** ARC dataset and Toolkit checks through 2026-08-02
- **Document role:** Primary project entrypoint, high-value state record, and source router. It does not replace the Problem Definition, project/domain evaluation definitions, evidence records, or adjudication.
- **Current lifecycle:** Problem definition stabilized → evidence adjudicated → project-level evaluation architecture drafted → ARC evaluation specification drafted → ARC-AGI-1 Stage 0 substrate recorded → Stage 1 local-reference evaluator core accepted → Stage 2 development-only run and artifact substrate accepted → Stage 3 G0/S1 provider-independent development substrate partially implemented, with a Stage 0 rules-manifest integrity conflict recorded
- **Current operational stage:** ARC-AGI-1 Stage 2 development-only run and artifact substrate is accepted. Stage 3 now has tested provider-independent G0/S1, frozen disclosure, calibration-proposal, and paired-reconstruction contracts, but it has not configured or called a model. The local A1 canonical source, task manifest, rules snapshot, strict task/prediction contract, public-exposure label, schema-validated run manifest, atomic run bundle, resume rule, and local cost/resource ledger are recorded; direct validation still reports a pre-existing rules-manifest hash mismatch. Official scorer material, sealed governance, a model/provider configuration, numerical compute tiers, and formal-run approvals remain unavailable or `TBD`.
- **Global experiment-design readiness:** `Not ready`
- **ARC-specific design readiness:** `Draft for implementation`
- **Project owner / decision authority:** `TBD`
- **State maintainer:** `TBD`

> The project has a current empirical problem and a draft ARC evaluation program, but no authoritative artifact supports any ARC stage achievement, official score, winning hypothesis, or cross-domain/AGI conclusion. The immediate task is to freeze the A1 evaluation substrate and establish reproducible run infrastructure before executing the baseline ladder.

---

## 0. Start here

1. Read this file first.
2. Use [Task-to-source routing](#6-task-to-source-routing) to open only the minimum required source.
3. Treat `docs/current/` and `docs/eval/` as the complete document bundle available to the GPT Chat Project.
4. If a routed source or run artifact is absent from those folders, report `Unavailable in project context`; do not reconstruct it from memory, legacy material, or inference.

State labels used here:

- **Source-stated:** explicitly recorded by the authoritative source.
- **Directly observed:** verified from the local checkout or a controlled setup check; not an empirical research result.
- **State inference:** inferred from stage order or missing artifacts; not an empirical claim.
- **TBD / Unknown / Not evidenced:** not decided, unavailable, or unsupported by the current artifact set.

When this file conflicts with a routed source, the routed source wins. New evidence cannot change a claim status here first; it must enter the Evidence Base and Evidence Adjudication workflow.

---

## 1. Executive state

### 1.1 Current empirical position

The stable empirical puzzle is:

> Why do model-level specialization interventions frequently produce same-backbone gains, yet only a smaller set of cases reliably establish broad, contemporary, resource-comparable, and persistent frontier superiority; while system-level, hybrid, and formal/narrow specialization can produce strong advantages in bounded workflows or problem spaces?

Current evidence supports four high-level conclusions:

1. Model-level same-backbone relative gain is recurring.
2. Relative gain does not automatically establish contemporary or persistent frontier superiority.
3. System, hybrid, and formal/verifier-bound wins can be strong but remain unit- and boundary-specific.
4. Unit, advantage type, capability construct, resources, exposure, and time index must remain separate.

ARC is the first controlled evaluation domain, not the full research problem. ARC-only results cannot independently support cross-domain specialization laws, broad professional capability, AGI, or general capability claims.

### 1.2 Current readiness

| Layer | Status | Meaning |
|---|---|---|
| Problem Definition v1 | Current / ready with conditions | The empirical problem, taxonomy, minimum rules, and falsification conditions are defined. |
| Evidence Base v1.1 | Current | Record-level evidence and provenance are available. |
| Evidence Adjudication v1 | Current | Claims, counterexamples, contradictions, boundary conditions, gaps, and decisions are adjudicated. |
| Project Evaluation Definition v0.1 | Draft for project-level evaluation architecture | Cross-domain evaluation, comparison, aggregation, evidence-downgrade, falsification, and domain-inheritance rules are defined; this does not make global experiment design ready. |
| Global experiment design | Not ready | Comparator, private-task, temporal, resource, and generalization controls remain incomplete. |
| ARC Evaluation Definition v0.1 | Draft for implementation | Working ARC program exists, with unresolved implementation decisions and unmet v1 gates. |
| Local ARC data and Toolkit | A1 Stage 0 artifacts recorded with a rules-manifest hash mismatch; Stage 1 local-reference evaluator core and Stage 2 development-only run/artifact substrate accepted; Stage 3 G0/S1 development contracts partially implemented; other substrate available for implementation setup | A1 canonical source, task identity, local-reference rules, strict evaluator contract, public-exposure status, local run/artifact contract, and provider-independent G0/S1 disclosure/calibration/pairing contracts are recorded. No real provider/model or public-data calibration was configured or run. The evaluator remains non-official and not parity-validated. The Stage 0 validator currently reports `rules_snapshot_mismatch`; A2 public data, A3 imports, local smoke test, and remote discovery remain operational setup. |
| ARC formal runs and stage achievements | Not evidenced | No formal preregistration, run manifest, official score, ablation, or stage-completion record is present. |

### 1.3 Evidence corpus index

| Artifact | Compact inventory |
|---|---|
| Evidence Base v1.1 | 65 evidence records, 49 sources, 43 benchmarks, 22 claims, 10 counterexamples, 12 gaps, 12 verification records |
| Evidence Adjudication v1 | 22 claim adjudications, 10 counterexample adjudications, 14 contradictions, 17 boundary conditions, 12 gaps, 14 decisions |
| Claim-status distribution | Supported 9; conditionally supported 5; partially supported 2; indeterminate 3; contradicted 1; unsupported 1; needs split 1 |

Detailed records, status reasoning, counterexample scope, contradiction maps, and gap queues remain in the evidence and adjudication artifacts; they are not duplicated here.

---

## 2. Authority and source navigation

### 2.1 Current document set

| Role | Current artifact | Authority |
|---|---|---|
| Empirical problem, scope, terminology, minimum claim rules, falsification | [Problem Definition v1](./Problem%20Definition%20v1.md) | Highest authority for the current research problem |
| Cross-domain evaluation, comparison, aggregation, claim-decision rules, and domain inheritance | [Project Evaluation Definition v0](./Project-Evaluation-Definition-v0.md) | Project-level evaluation architecture between the Problem Definition and Domain Evaluation Definitions |
| Record-level evidence, IDs, provenance, benchmark metadata, verification | [Evidence Base v1.1](./Evidence-Base-v1.1.xlsx) | Highest authority for record-level evidence fields |
| Structured claim and gap adjudication, decision log | [Evidence Adjudication v1 workbook](./Evidence-Adjudication-v1.xlsx) | Highest authority for current adjudication status |
| Human-readable adjudication and readiness summary | [Evidence Adjudication v1 summary](./Evidence-Adjudication-v1.md) | Readable summary; workbook controls exact structured status |
| ARC design, governance, metrics, stage gates, and claim taxonomy | [ARC Evaluation Definition v0](../eval/ARC-Eval-Definition-v0.md) | Highest authority for the ARC evaluation program |
| Dataset inventory, Toolkit configuration, imports, environments, smoke test | [ARC Dataset and Toolkit Status v0](../eval/ARC-Dataset-Toolkit-Status-v0.md) | Operational setup record; not run evidence or empirical authority |
| A1 canonical source, file manifest, local-reference policy snapshot, and query-log location | [ARC-AGI-1 Substrate v0](../eval/ARC-AGI-1-Substrate-v0.md) | Stage 0 operational identity record; its current rules-manifest hash validation conflict is recorded below; not an official evaluator, score record, or empirical authority |
| A1 local-reference task/prediction/submission contract and scoring core | [ARC-AGI-1 Evaluator Core v0](../eval/ARC-AGI-1-Evaluator-Core-v0.md) | Stage 1 operational implementation record; not an official or parity-validated evaluator, score record, or empirical authority |
| A1 development run contract, artifacts, resume rule, and cost/resource ledger | [ARC-AGI-1 Run and Artifact Substrate v0](../eval/ARC-AGI-1-Run-Artifact-Substrate-v0.md) | Stage 2 operational implementation record; not a formal run, official score record, sealed-evaluation protocol, or empirical authority |
| A1 G0/S1 provider boundary, frozen disclosure, calibration proposal, and paired reconstruction | [ARC-AGI-1 G0/S1 Development v0](../eval/ARC-AGI-1-G0-S1-Development-v0.md) | Partially implemented Stage 3 development record; not an approved provider/model, formal calibration, paired result, official score, or stage achievement |
| Project entrypoint and navigation | `PROJECT-STATE.md` | State index only; no independent empirical authority |

### 2.2 Authority rules

- Research problem, terms, and extrapolation rules come from the Problem Definition.
- Cross-domain evaluation, comparison, aggregation, downgrade, and domain-inheritance rules come from Project Evaluation Definition; it does not choose domain benchmarks, thresholds, or compute tiers.
- Claim, counterexample, contradiction, boundary-condition, and gap status come from Evidence Adjudication.
- Record IDs, provenance, benchmark metadata, and verification details come from the Evidence Base.
- ARC metrics, data governance, run requirements, stages, and SOTA taxonomy come from ARC Evaluation Definition.
- A preregistration, run manifest, evaluator output, or experiment report can adjudicate only its run; it cannot silently rewrite an upper-level source.
- Operational installation success does not establish benchmark validity, scorer correctness, model capability, or stage completion.
- When sources conflict, record the conflict and follow the responsible source; do not silently reconcile it in this index.

### 2.3 GPT Chat Project boundary

The GPT Chat Project contains only `docs/current/` and `docs/eval/`. Therefore:

- all navigation required for interpretation must terminate in these folders;
- research/archive files are not prerequisites for normal project work;
- repository code, data, scripts, and external services are represented here only through explicit current/eval status records;
- if a new run, dataset manifest, rule snapshot, or decision must be available to the Chat Project, add a durable current/eval artifact rather than relying on a workspace-only path.

---

## 3. Mandatory analytical guardrails

### 3.1 Evaluation unit

| Code | Unit | Minimum interpretation |
|---|---|---|
| `G` | Generalist baseline | Non-specialized model/system comparator for the target distribution |
| `M` | Model specialist | Primary intervention is in weights; supports same-backbone model-level claims when system boundaries are matched |
| `S` | System specialist | Weights fixed; intervention is prompt, retrieval, tools, search, memory, verifier, routing, scaffold, or environment |
| `H` | Hybrid specialist | Weights and system stack are both specialized and effects cannot be cleanly separated |
| `N` | Narrow/formal solver | Fixed DSL, exact verifier, handcrafted primitives, narrow format, or bounded search space |

Tools, retrieval, search, verification, memory, context, routing, scaffolds, and environment access must not be attributed to specialized weights.

### 3.2 Keep these dimensions separate

- **Advantage:** same-backbone relative gain; contemporary absolute superiority; persistent superiority; configuration-level superiority; cost/efficiency advantage.
- **Capability construct:** benchmark proxy; broad domain capability; professional workflow capability; formalized/bounded task capability.
- **Generalization:** held-out task; OOD; temporal shift; cross-version transfer; independent replication.
- **Validity context:** exact model/system snapshot; evaluator; date; resources; public/sealed/private status; contamination/exposure.

One dimension does not imply another. Missing evidence must remain `Unknown`, `Not evaluated`, `Indeterminate`, or `Source does not support`.

### 3.3 Minimum claim discipline

Any superiority, frontier, SOTA, efficiency, or generalization claim must identify at least:

- evaluation unit and exact specialist/comparator configurations;
- model/system snapshot and evaluation date;
- benchmark/evaluator and capability construct;
- tools, information access, context, scaffold, and inference policy;
- token, call, rollout, search, retry, wall-clock, and hardware boundary where relevant;
- public/sealed/private and contamination/exposure status;
- resource parity, temporal status, and generalization/replication status;
- narrowest supported proposition and prohibited extrapolation.

Without these fields, downgrade to language such as `historical`, `partially matched`, `configuration-level`, `single-setting`, `public-exposed`, or `not interpretable`.

---

## 4. ARC program state

### 4.1 Program sequence

1. **ARC-AGI-1:** establish a reproducible, attributable, cost-visible static abstraction baseline.
2. **ARC-AGI-2:** test deeper/multistep complexity and A1 → A2 transfer.
3. **ARC-AGI-3:** evaluate interactive capability systems through controlled science and competition engineering.

Research-qualified and benchmark-complete are separate outcomes. Public results alone cannot establish verified completion.

### 4.2 Dataset and Toolkit snapshot

| Substrate | Directly observed status | Formal interpretation |
|---|---|---|
| A1 public training | 400 JSON files; manifest and rules snapshot are present, but current validator reports `rules_snapshot_mismatch` | Training tier only; see A1 Substrate v0 for the recorded manifest/identity and the integrity conflict. |
| A1 public evaluation | 400 JSON files; manifest and rules snapshot are present, but current validator reports `rules_snapshot_mismatch` | `public-exposed` development/evaluation substrate only; not sealed or private. |
| A2 public training | 1,000 JSON files available | Local data available; canonical snapshot/hash not frozen |
| A2 public evaluation | 120 JSON files available | Public-exposed portion only; semi-private/private not established |
| A3 root Toolkit | `arc-agi 0.9.9`; `arc_agi` and `arcengine` imports passed | Toolkit installation ready for implementation work |
| A3 offline smoke | Two bundled test environments; reset and one legal action passed | Local API path works; not a benchmark run |
| A3 remote discovery | 25 environments returned on 2026-08-02 using root `.env` | Time-indexed catalogue access; not an immutable rules or evaluator snapshot |

See [ARC Dataset and Toolkit Status v0](../eval/ARC-Dataset-Toolkit-Status-v0.md) for paths, environment IDs, commands, configuration scope, and smoke-test details.

### 4.3 Stage status

| Stage family | Current status | Missing decisive artifacts |
|---|---|---|
| A1 Research/Public/Verified | Not evidenced | Frozen baseline, paired result, ablation, run manifest, official/sealed score |
| A2 Research/Public/Verified | Not evidenced | A1 frozen port, A1-port/A2-adapted comparison, matched-compute curve, private/sealed result |
| A3 Research/Competition/SOTA/Solved | Not evidenced | Controlled ablation, official scorer output, runtime/container validation, private leaderboard result |

`Not evidenced` means the current document bundle does not support the status; it does not infer hidden progress.

### 4.4 Immediate blockers and next sequence

| Work item | Status | Blocks |
|---|---|---|
| Validate A1 canonical repository/data snapshot and hashes | Directly observed conflict: Stage 0 validator reports `rules_snapshot_mismatch` for the unmodified manifest/rules pair | Formal A1 run data identity and reproducibility |
| Pin official parser, scorer, evaluator, and rules | Official material `Unavailable in checkout`; local-reference core uses the actual rules-file hash, while Stage 0 manifest integrity remains conflicted | Official/parity-validated scores and cross-run comparison |
| Define sealed validation, custodian, and evaluation firewall | TBD | Generalization and verified completion |
| Implement local development run manifest, output archive, cost/deviation logging, and resume rule | Stage 2 accepted; Stage 3 adds a tested provider-independent boundary with frozen request/prompt/retry disclosure and pre-request reservation/settlement, but no real provider was configured or called | Formal attribution, reproducibility package, and frontier/efficiency interpretation |
| Calibrate Low/Matched/High compute tiers and seed policy | Derivation utility implemented; numerical policy and real baseline calibration remain `TBD` | Resource-matched claims |
| Decide first-round scope: fixed-backbone system only or include model adaptation | TBD | Baseline ladder and eligible claims |

Shortest implementation sequence:

1. Resolve or adjudicate the recorded A1 rules-manifest integrity conflict, then obtain/freeze official A1 evaluator material and sealed-governance decisions.
2. Configure the first approved fixed-backbone development solver and its policy/budget inputs against the implemented local run substrate.
3. Execute `G0 → S1 → S2 → S3` only after the applicable governance and preregistration requirements are met; add `M1 → H1` only if model adaptation is in scope.
4. Perform at least one key ablation, then issue a formal decision record before A2 transfer work.

Detailed metrics, baseline definitions, run-manifest fields, stage gates, unresolved decisions, and v1 acceptance criteria remain in ARC Evaluation Definition v0.

---

## 5. Required artifacts not yet evidenced

| Need | Durable artifact class |
|---|---|
| Data identity | A1 canonical source/release pin, 800-file manifest, and hashes are recorded in A1 Substrate v0, but the current validator reports an unresolved rules-manifest hash mismatch |
| Evaluator identity | Official parser/scorer/evaluator/submission-writer material `Unavailable in checkout`; local-reference rules snapshot and Stage 1 evaluator core available, but non-official and not parity-validated. The Stage 0 manifest/rules hash mismatch remains unresolved. |
| Governance | Sealed-validation protocol, access/custodian record, contamination/query ledger |
| Run infrastructure | Local development run-manifest schema, atomic source-of-truth bundle, cost/deviation ledger, resume rule, and G0/S1 provider/disclosure/calibration/pairing contracts are available in A1 Run and Artifact Substrate v0 and A1 G0/S1 Development v0; experiment registry service, dependency lock/container, approved provider, and actual calibration remain absent/not evidenced |
| Result trace | Per-task outputs, failed-run/deviation log, cost ledger |
| First formal experiment | A1 preregistration, G0 run manifest, baseline report, key ablation |
| Decision control | Structured ARC decision log with allowed/prohibited claims and reversible-if condition |

Additional project-level `TBD`s include ownership, state maintenance, compute/procurement boundaries, approved model/API policy, retention, security/secrets, publication approval, and incident response.

These are implementation requirements, not evidence that any stage has failed or succeeded.

---

## 6. Task-to-source routing

| Task | Read first | Read next only if needed | Do not assume |
|---|---|---|---|
| Current status / shortest orientation | `PROJECT-STATE.md` §1 and §4 | Routed source for the specific question | State index has independent empirical authority |
| Research problem / scope / falsification | [Problem Definition v1](./Problem%20Definition%20v1.md) §2–3, §7, §10 | PD §8–9 | Legacy framing is current |
| Project-wide evaluation / comparison / aggregation / claim decision | [Project Evaluation Definition v0](./Project-Evaluation-Definition-v0.md) §3–11 | PD §4–6, §10; Evidence Adjudication for current status | An operational rule is an empirical finding |
| Units / advantage / constructs / minimum rules | Project Eval §4–8 | PD §4–6 | `specialist` implies superiority or one advantage implies another |
| Claim status / counterexample / contradiction / boundary / gap | [Evidence Adjudication v1 summary](./Evidence-Adjudication-v1.md) §4–10 | Structured workbook, then relevant Evidence IDs | A plausible explanation resolves a contradiction |
| Record IDs / provenance / benchmark metadata / verification | [Evidence Base v1.1](./Evidence-Base-v1.1.xlsx) | Adjudication workbook for current status | Repository presence establishes authority |
| Create or revise a Domain Evaluation Definition | Project Eval §12–14 | PD and relevant adjudicated gaps; domain sources only as needed | Project Eval chooses the actual benchmark, threshold, or compute tier |
| ARC design / metrics / governance / stage gate | [ARC Evaluation Definition v0](../eval/ARC-Eval-Definition-v0.md) | Project Eval inheritance contract; PD minimum rules and relevant adjudicated gaps | ARC-only supports cross-domain or AGI conclusions |
| Dataset counts / Toolkit / environments / configuration / smoke test | [ARC Dataset and Toolkit Status v0](../eval/ARC-Dataset-Toolkit-Status-v0.md) | Actual code/data only when executing in the repository | Installation equals evaluator or stage validation |
| A1 implementation | ARC Eval §6–9, §13–19 | A1 Substrate v0, Dataset/Toolkit status, and new durable implementation artifacts | Current public data fills sealed/compute TBDs |
| A1 evaluator core contract or local-reference score interpretation | [ARC-AGI-1 Evaluator Core v0](../eval/ARC-AGI-1-Evaluator-Core-v0.md) | ARC Eval §6–9; A1 Substrate v0 | Local-reference score is official or parity-validated |
| A1 development runner, run artifact, cost, or resume interpretation | [ARC-AGI-1 Run and Artifact Substrate v0](../eval/ARC-AGI-1-Run-Artifact-Substrate-v0.md) | ARC Eval §6–9, §15–18; A1 Evaluator Core v0 | A local development bundle is a formal run, official result, or stage achievement |
| A1 G0/S1 configuration, provider contract, calibration proposal, or paired reconstruction | [ARC-AGI-1 G0/S1 Development v0](../eval/ARC-AGI-1-G0-S1-Development-v0.md) | ARC Eval §5–9, §13–18; A1 Run and Artifact Substrate v0 | A fixture test or proposal is an approved provider configuration, calibration result, superiority result, or stage achievement |
| A2 transfer | ARC Eval §10 and §12 | Frozen A1 runs and manifests | Testing only a new best A2 system establishes transfer |
| A3 science / competition | ARC Eval §11 and §13–19 | Current official scorer/rules snapshot when added | Public development score equals private/final SOTA |
| Run interpretation | Preregistration + run manifest + evaluator output | Relevant Domain Eval, then Project Eval claim rules and decision record | Aggregate score replaces per-task/per-environment outputs |
| Publication / external claim | Formal report + decision record | PD, adjudication, relevant Domain Eval, and Project Eval claim rules | Date, unit, resources, exposure, or verification can be omitted |
| State update | Responsible authoritative source + this file | Change log and downstream routes | `PROJECT-STATE.md` can change adjudication by itself |

If a preregistration, manifest, evaluator output, report, or decision record is not in `docs/current/` or `docs/eval/`, mark it `Unavailable in project context` for GPT Chat Project work.

---

## 7. State update protocol

Update this file when any of the following occurs:

- a current authoritative document changes version or location;
- evidence/adjudication changes a claim, contradiction, boundary, gap, or decision;
- ARC Eval, official rules, evaluator, or dataset snapshot changes;
- a formal preregistration, run manifest, result, reproducibility package, or stage decision is added;
- operational substrate changes materially enough to affect routing or implementation readiness;
- a current/eval artifact is added, moved, renamed, or removed.

Every update must:

1. increment `State version` and `Last updated`;
2. identify the responsible source and whether the statement is source-stated, directly observed, inferred, or unknown;
3. update affected readiness, blockers, routes, and downstream impact;
4. add a change-log entry;
5. state empirical claim, ARC stage, and winning-hypothesis impact explicitly;
6. avoid changing empirical status here without the evidence/adjudication sequence.

---

## 8. Change log

| Date | Version | Change | Impact |
|---|---|---|---|
| 2026-08-01 | v0.1 | Established the integrated project-state index from Problem Definition v1, Evidence Base v1.1, Evidence Adjudication v1, and ARC Eval v0. | Initial index |
| 2026-08-01 | v0.2 | Aligned document topology, authority, and task routing. | No empirical adjudication change |
| 2026-08-01 | v0.3 | Removed short-lived repository/integration identity from current state and separated repository workflow from empirical state. | No empirical, ARC stage, or scope change |
| 2026-08-02 | v0.4 | Reduced the state file to a high-value record and navigation layer; moved dataset/Toolkit details to ARC Dataset and Toolkit Status v0; recorded verified A1/A2 counts, A3 installation, offline smoke, and remote discovery; made current/eval the complete GPT Chat Project routing boundary. | Operational readiness updated. Empirical claim impact: none. ARC stage impact: none. Winning-hypothesis impact: none. |
| 2026-08-05 | v0.5 | Added Project Evaluation Definition v0.1 as the project-level evaluation architecture between Problem Definition v1 and Domain Evaluation Definitions; updated authority and task routing. | Global experiment-design readiness remains `Not ready`. Empirical claim impact: none. ARC stage impact: none. Winning-hypothesis impact: none. |
| 2026-08-05 | v0.6 | Added ARC-AGI-1 Substrate v0: canonical repository identity, deterministic task manifest/hashes, local-reference rules snapshot, public-exposure labels, and development-query-log location. Official evaluator material remains `Unavailable in checkout`; sealed/private governance remains `TBD`. | Operational Stage 0 readiness updated. Empirical claim impact: none. ARC stage impact: none. Winning-hypothesis impact: none. |
| 2026-08-05 | v0.7 | Added ARC-AGI-1 Evaluator Core v0: strict task/prediction contracts, solver-safe task view, deterministic local-reference scoring and submission envelope, diagnostics, schemas, and regression suite. Direct validation also found a pre-existing mismatch between the Stage 0 manifest's recorded rules SHA-256 and the unmodified rules file; no Stage 0 artifact was changed. Official evaluator material remains `Unavailable in checkout`; the local core is explicitly non-official and not parity-validated. | Operational Stage 1 implementation readiness updated; Stage 0 integrity conflict recorded. Empirical claim impact: none. ARC stage impact: none. Winning-hypothesis impact: none. |
| 2026-08-06 | v0.8 | Added ARC-AGI-1 Run and Artifact Substrate v0: schema-validated local development run manifest, deterministic task selection/seed control, atomic seven-file run bundle, terminal-record resume rule, structured failures/deviations, and local resource/cost ledger. The runner uses only the non-official, non-parity-validated Stage 1 evaluator and does not add a model, formal run, sealed governance, or official scorer. The pre-existing Stage 0 rules-manifest hash mismatch was not changed. | Operational Stage 2 implementation readiness updated. Empirical claim impact: none. ARC stage impact: none. Winning-hypothesis impact: none. |
| 2026-08-06 | v0.9 | Added ARC-AGI-1 G0/S1 Development v0: provider-independent G0/S1 solvers, frozen provider/request/prompt/retry disclosure in run-manifest schema v1.1, pre-request resource reservation/settlement, calibration-proposal derivation, paired task-level reconstruction, and regression coverage. No real model/provider was configured or called; numerical tiers and formal-run prerequisites remain `TBD`. | Operational Stage 3 development substrate partially implemented. Empirical claim impact: none. ARC stage impact: none. Winning-hypothesis impact: none. |
