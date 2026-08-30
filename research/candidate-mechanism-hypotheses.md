# Candidate Mechanisms and Falsifiable Hypotheses

- **ID:** `note-2026-08-28-candidate-mechanisms`
- **Status:** hypothesis / comparative
- **Question/scope:** Compare corpus mechanisms that could change success, evidence quality, applicable reliability, or lifecycle cost on `taskdist-2026-08-28-vanta-docops-readonly-12`. This is not an architecture or dependency recommendation.
- **Corpus records:** `src.eidos`, `src.spex`, `src.vanta`, `src.prime-intellect-verifiers-v1`, `src.nemo-agent-toolkit-develop`, `src.dspy`, `src.gepa`, `src.aflow`, `src.frugalgpt`, `src.routellm`

## Evidence Basis and Claim Discipline

| Source | Inspected original paths | What is source-stated or directly observed |
| --- | --- | --- |
| `src.eidos` | `sources/predecessors/eidos/README.md`, `eidos.yaml`, `docs/schema/document.schema.json`, `docs/index.json` | Source-stated schema for typed document IDs, authority, relations, and provenance. Directly observed index has zero governed records; operational benefit is `Not evaluated`. |
| `src.spex` | `sources/predecessors/spex/docs/current/PROJECT-STATE.md`, `docs/eval/ARC-AGI-1-Run-Artifact-Substrate-v0.md`, `docs/eval/ARC-AGI-1-G0-S1-Development-v0.md`, `src/spex_arc/runner/arc_a1.py` | Source-stated frozen manifests, per-task terminal records, resource budgets, cost/failure ledgers, exact paired-task reconstruction, and explicit official/parity limitations. |
| `src.vanta` | `sources/predecessors/vanta/docs/02_specs/Evidence_Packet_and_Verifier_Runtime.md`, `Commit_Abort_Replay_Semantics.md`, `Failure_Taxonomy_v0.md`, and `docs/04_experiments/Experiment_002_Evidence_Verifier.md` | Source-stated separation of evidence, verification, commit/reject, and failure/recovery records; the selected fixtures directly provide task oracles. These are predecessor mechanisms, not IRIS-X requirements. |
| `src.prime-intellect-verifiers-v1` | `sources/external/prime_intellect_verifiers_v1/README.md`, `environments/reverse_text/reverse_text/taskset.py`, `environments/bash_interception/bash_interception/taskset.py` | Source-stated library purpose and directly observed task-local stop/intercept/reward functions over traces and runtimes. |
| `src.nemo-agent-toolkit-develop` | `sources/external/NeMo-Agent-Toolkit-develop/docs/source/improve-workflows/evaluate.md`, `profiler.md`, `packages/nvidia_nat_core/src/nat/data_models/evaluate.py`, `profiler.py` | Source-stated workflow/evaluator artifacts and profiler outputs; directly observed configuration models. Some evaluators use judge LLMs, so evaluator output is not independent truth by default. |
| `src.dspy` | `sources/external/dspy/README.md`, `dspy/signatures/signature.py`, `dspy/predict/predict.py`, `dspy/evaluate/evaluate.py` | Source-stated declarative modular LM programs and optimization; directly observed input/output signatures, prediction traces, metric-driven evaluation, parallelism, and failure scores. |
| `src.gepa` | `sources/external/gepa/README.md`, `src/gepa/proposer/reflective_mutation/reflective_mutation.py`, `src/gepa/core/state.py` | Source-stated trace-informed reflective mutation and Pareto-aware selection; directly observed parent/child batch evaluation with captured traces and candidate state. Performance claims from its README are not assumed to transfer. |
| `src.aflow` | `sources/external/aflow/README.md`, `scripts/optimizer.py`, `scripts/evaluator.py`, `benchmarks/README.md` | Source-stated code-represented workflow search using an MCTS variant and evaluation feedback; directly observed optimizer/evaluator separation. |
| `src.frugalgpt` | `sources/external/frugalgpt/README.md`, `src/FrugalGPT/llmcascade.py`, `src/FrugalGPT/llmchain.py` | Source-stated budget-constrained LLM application techniques; directly observed trained response scorers, budget setting, model chains, and thresholded cascade prediction. |
| `src.routellm` | `sources/external/routellm/README.md`, `routellm/controller.py`, `routellm/routers/routers.py` | Source-stated strong/weak routing and cost thresholds; directly observed prompt-based strong-win-rate threshold routing. The controller notes current routers use the last turn despite training on first-turn data. |

All imported upstream revisions are `Unknown`. Source-reported gains are not treated as IRIS-X results.

## Comparison Map

| Mechanism | Research problem addressed | Required assumptions | Expected first-cycle effect | Likely failures / trade-offs | Substrate vs possible IRIS-X contribution | Falsifiable task-local hypothesis and minimum distinguishing experiment |
| --- | --- | --- | --- | --- | --- | --- |
| Typed evidence envelope and independent deterministic verifier (`src.vanta`, with EIDOS provenance fields as a separate record-shape candidate) | Distinguish actual outcome from claims and make source support auditable | Fixture oracle is usable; hashes bind the bytes actually read; verifier is independent of the producer | Lower accepted false successes; higher verifier time/output bytes; possible false failures on equivalent but non-canonical JSON | Oracle error, verifier coupling, evidence laundering, exact-match brittleness | Hashing/JSON validation is commodity substrate; what evidence is sufficient is an IRIS-X research question | **H-V1:** Adding required path/hash evidence and independent oracle comparison will reduce `false_success` acceptance relative to claim-only acceptance on injected wrong/omitted outputs, while leaving actual outcome unchanged. Compare the same frozen outputs under claim-only and evidence-aware acceptance. |
| Frozen run manifest, terminal per-task records, and resource ledger (`src.spex`) | Attribution and comparable success–cost measurement | Configuration and data identities can be frozen; measured resource events are honest and complete | Fewer `Unknown` execution fields and reconstructable per-task comparisons; small logging overhead | Manifest drift, missing provider truth, incomplete lifecycle boundary, false confidence from development-only evaluators | Artifact writing and ledgers are reusable substrate; valid comparison boundaries remain research-specific | **H-M1:** A frozen manifest plus terminal records will detect configuration/resource mismatches that an aggregate-only report misses. Run deliberately mismatched configuration fixtures and count detected versus undetected mismatches. |
| Task-local trace/runtime reward and action interception (`src.prime-intellect-verifiers-v1`) | Evaluate trajectories and block/replace unsafe tool calls | Harness observes calls before execution; reward matches empirical task outcome | Could prevent disallowed effects and expose tool-path failures, at added harness complexity | Reward hacking, incomplete interception, taskset/runtime coupling, two-case examples not representative | Generic task/trace interfaces are substrate; which interventions improve the selected distribution is research | **H-I1:** Pre-execution interception will prevent all injected write attempts in a copied-workspace variant, whereas post-hoc outcome checking cannot prevent mutation. Compare identical proposed actions with interception on/off. Not tested in Phase 3. |
| Evaluation/profiling instrumentation (`src.nemo-agent-toolkit-develop`) | Observe latency, tokens, errors, traces, and evaluator outputs across configurations | Instrumentation captures relevant calls without changing behavior materially | Reduce unavailable runtime-cost fields; increase latency and artifact volume | Observer overhead, missing spans, judge-model dependence, privacy/storage cost | Tracing transport/profiling are commodity substrate; selecting sufficient lifecycle fields is research | **H-O1:** Enabling structured profiling reduces missing runtime-cost fields but increases wall time and output bytes. Compare identical deterministic episodes with instrumentation off/on; do not predict an unsupported overhead threshold. |
| Declarative program/signature plus metric-driven prompt/program optimization (`src.dspy`) | Replace manual prompt tuning with reproducible program-level specialization | Stable metric, representative train/validation split, fixed model, sufficient optimization budget | May improve held-out exact outcome and schema adherence; adds design-time calls/cost | Metric overfit, leakage, optimizer variance, failure score hiding errors | Program/evaluator framework is substrate; whether optimization substitutes for runtime capability is research | **H-P1:** At fixed runtime model/tool envelope, an optimized structured-output program improves held-out task success over its unoptimized seed enough to offset its separately reported design-time cost. Minimum experiment: frozen train/validation/test split, seed vs compiled program, repeated optimizer seeds. |
| Trace-informed reflective mutation with Pareto selection (`src.gepa`) | Use failure traces to target textual component changes under an evaluation budget | Traces contain causal signal; reflection model is capable; Pareto objectives are correctly specified | May reach a better success–design-cost set than scalar-only mutation | Trace misdiagnosis, reflector cost, overfit, nondeterminism, objective gaming | Search engine is substrate; task-specific failure representation and cost boundary are research | **H-G1:** At matched candidate-evaluation and reflection-model budgets, trace-informed proposals produce more held-out improvements than score-only random textual mutation. Minimum experiment: same seed prompt, split, candidate budget, and evaluator; compare accepted held-out deltas and total design cost. |
| Code-represented workflow search (`src.aflow`) | Search multi-step agent workflows rather than one prompt | Workflow operators are safe/expressive; evaluator is stable; search budget is adequate | Could improve structured/contract tasks by adding appropriate steps; high design-time cost | Search-space explosion, executable-code risk, benchmark overfit, attribution ambiguity | Workflow executor/search are candidate substrate; useful operator boundaries are research | **H-W1:** At fixed runtime model and tool set, workflow search improves held-out success over a hand-written one-step workflow, but may be dominated after design-time cost is included. Minimum experiment: one operator set, frozen split/evaluator, matched search budget, report frontier rather than one score. |
| Confidence-based model cascade (`src.frugalgpt`) | Stop on a cheaper response when predicted quality is sufficient; escalate otherwise | Confidence scorer is calibrated on this task distribution; model outputs and costs are available | Lower model cost than always-strong with possible success loss and scorer overhead | Miscalibration, distribution shift, cascading latency, scorer training cost, correlated failures | Model adapters/cascade executor are substrate; sufficient stopping evidence is research | **H-C1:** A calibrated weak-to-strong cascade maintains the always-strong verified-success count within the observed finite sample while using fewer strong calls; the claim fails if any retained weak answer is a false success or total lifecycle cost is not reduced. Minimum experiment: weak/strong outputs frozen first, train scorer on disjoint tasks, replay thresholds. |
| Prompt-level strong/weak routing (`src.routellm`) | Allocate more runtime capability to tasks predicted to need it | Router score transfers to the selected task/model pair; threshold is calibrated; first-turn features suffice | Fewer higher-capability invocations than always-strong, potentially lower runtime cost | Router transfer failure, threshold drift, routing overhead, first-turn/last-turn mismatch, training data dependence | Serving/router implementation is substrate; escalation evidence and task features are research | **H-R1:** A task-feature router between the Phase 3 narrow controls achieves the structured control's success with fewer structured-control invocations than always-structured. Minimum experiment: leave-one-task-family-out calibration and task-level routed outcomes/costs. |

## Phase 4 Narrow Refinements

The parent hypotheses above are preserved. The following sub-hypotheses isolate
only the mechanisms authorized by the temporary Phase 4 plan; they do not
silently replace or establish their parents.

### H-M1a — Registered Source Snapshot Assertion

> Resolving a run's `source_id` and `source_snapshot_id` through
> `corpus/sources.yaml` and asserting that the observed Git source-tree OID
> equals the registered snapshot tree OID will detect deliberately injected
> source-identity mismatches that a record-only provenance path does not
> detect, while accepting the valid registered identity.

This tests only a narrow part of H-M1. It does not establish the complete
manifest, terminal-record, or resource-ledger hypothesis.

### H-V1a — Independent Acceptance Verification

> Holding producer output, system claim, task bytes, evidence/path-hash
> substrate, and actual-outcome adjudication fixed, requiring an independent
> deterministic verification decision before accepting a claimed success will
> reduce false-success acceptance relative to claim-only acceptance on frozen
> invalid-output challenges, without rejecting semantically valid
> claimed-success outputs in the evaluated finite sample.

The existing H-V1 bundles evidence binding and independent verification.
H-V1a isolates independent acceptance verification and does not inject missing
hashes, stale hashes, or missing evidence.

`H-V1b — evidence/provenance binding: deferred / not evaluated in this batch`

### H-O1a — Structured Instrumentation Completeness

> Holding task, control behavior, evaluator, resource envelope, and execution
> policy fixed, structured profiling will reduce missingness for a predeclared
> runtime-profile field set while preserving paired output and actual-outcome
> behavior. Artifact-size and timing overhead must be measured descriptively
> rather than assumed.

This tests a narrow task-local part of H-O1 without adopting the NeMo Agent
Toolkit as an IRIS-X dependency.

## Separation Rules for Later Experiments

- Verification, retry/recovery, routing/escalation, prompt/program optimization, workflow optimization, and specialization remain separate interventions.
- A gain from a deterministic tool or verifier is a system/configuration gain, not model-weight capability.
- Design-time optimization cost is reported separately before any amortization assumption.
- A verifier or reward score is evidence under its contract, not empirical truth by definition.
- No mechanism above is recommended as IRIS-X architecture. Phase 4 may test one row at a time after the Phase 3 decision gate.

## Uncertainty

- **Supported — task-local:** H-M1a, H-V1a, and H-O1a under their respective
  Phase 4 finite-sample experiment contracts.
- **Not established:** the complete parent H-M1, H-V1, and H-O1 hypotheses;
  improvement on any broader task family; or any architecture requirement.
- **Not evaluated:** H-V1b, H-I1, H-P1, H-G1, H-W1, H-C1, H-R1, and the
  remaining untested parts of the parent hypotheses.
- **Unclear:** whether 12 development fixtures support a defensible train/validation/test split; generated or independently authored tasks may be required.
- **Unknown:** paid model costs, provider snapshots, and optimization budgets for future model-based experiments.
- **Conflicting evidence:** none identified within the inspected mechanism paths; absence of conflict is not evidence of validity.
