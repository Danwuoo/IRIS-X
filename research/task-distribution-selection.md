# Initial Task-Distribution Selection

- **ID:** `note-2026-08-28-initial-task-distribution`
- **Status:** comparative — first-cycle selection decision
- **Question/scope:** Select one bounded task distribution for the first IRIS-X evidence cycle. This note does not select an agent architecture, framework, provider, or final product boundary.
- **Selected distribution:** `taskdist-2026-08-28-vanta-docops-readonly-12`
- **Corpus records:** `src.vanta`, `src.spex`, `src.prime-intellect-verifiers-v1`, `src.aflow`, `src.agent-lightning`

## Decision

The first cycle will use an enumerated 12-instance slice of the preserved VANTA Document Ops fixtures: the six **Traceability extraction** fixtures and the six **Terminology consistency** fixtures listed in `sources/predecessors/vanta/docs/04_experiments/fixtures/README.md`.

This is an IRIS-X selection over preserved source material, not adoption of VANTA's runtime, state model, verifier design, phase gates, or architecture. The executable enumeration is frozen in `experiments/exp-2026-08-28-docops-readonly-baseline/inputs/task-manifest.json`.

## Evidence Basis

| Record and path | Classification | Observation used here |
| --- | --- | --- |
| `src.vanta`: `sources/predecessors/vanta/docs/04_experiments/fixtures/README.md` | Source-stated | The catalog names 48 fixture-local Document Ops cases across eight six-item strata and describes the selected two strata as read-only traceability and terminology tasks. |
| `src.vanta`: the 12 selected `task.json` and `expected/*.json` files under `sources/predecessors/vanta/docs/04_experiments/fixtures/document_ops/` | Directly observed | Each selected task declares `READ_ONLY`; each has task-specific criteria and a deterministic expected observation artifact. The set includes expected positive observations, expected empty findings, a missing target that must not be repaired by inference, and a document-contract failure that must be reported correctly. |
| `src.vanta`: `sources/predecessors/vanta/docs/04_experiments/Document_Ops_Benchmark.md` | Source-stated | Document Ops is proposed as a controlled domain with source tracking, evidence, verification, and audit, while warning that the initial and expanded fixture sets do not establish broad benchmark validity. |
| `src.spex`: `sources/predecessors/spex/docs/current/PROJECT-STATE.md` and `sources/predecessors/spex/artifacts/arc-agi-1/manifest.json` | Source-stated and directly observed | ARC-AGI-1 has 400 public training and 400 public-evaluation tasks, but the source records a rules-manifest mismatch, unavailable official scorer material, and public-exposed status. |
| `src.prime-intellect-verifiers-v1`: `sources/external/prime_intellect_verifiers_v1/environments/reverse_text/reverse_text/taskset.py`, `environments/wordle/wordle/taskset.py`, and `environments/bash_interception/bash_interception/taskset.py` | Directly observed | These provide exact-reward or game-authoritative examples and a two-case interception task, but depend on external datasets/framework packages or are too small/trivial for the first research vehicle. |
| `src.aflow`: `sources/external/aflow/README.md` and `sources/external/aflow/benchmarks/README.md` | Source-stated | AFlow supplies evaluation code for common reasoning/code/QA datasets and workflow search, but its documented workflow invokes LLMs and expects downloaded datasets. |
| `src.agent-lightning`: `sources/external/agent_lightning/examples/gsm8k/README.md` | Directly observed | The example routes to additional setup documentation rather than supplying a self-contained, locally frozen first-cycle task distribution. |

Upstream revisions for these imported sources are `Unknown` in `corpus/sources.yaml`. Claims above describe the preserved local snapshots only.

## Eligibility Gates

No weighted score is used. A candidate is selected only if it passes the necessary first-cycle gates; qualitative advantages do not compensate for a failed gate.

| Candidate | Explicit outcome contract | Repeatable and controlled | Multiple configurations | Observable/boundable resources | Relevant failure/evidence phenomena | Bounded without framework adoption | Decision |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VANTA read-only Document Ops, 12 enumerated fixtures | Pass: exact expected JSON plus no-mutation condition | Pass: local files, independent episodes, fixed enumeration | Pass: narrow literal, structured, and later model/tool configurations can share the contract | Pass for local wall/CPU time, bytes, tool calls, retries, and output size; several lifecycle costs remain `Unknown` | Pass for omission, fabrication, evidence provenance, false acceptance/rejection, and limited context distraction; recovery is outside this slice | Pass: inputs are consumed through an IRIS-X harness, not the VANTA runtime | **Selected** |
| Full 48-fixture VANTA Document Ops frame | Pass in the source's own fixture contracts | Conditional: reversible edits and recovery require copied workspaces and more runtime behavior | Pass | Conditional: broader execution accounting is possible but requires substantially more scaffold | Strong coverage of verification, rollback, replay, recovery, and working-set failures | Conditional: a first implementation risks reproducing VANTA runtime assumptions | Deferred until individual mechanisms are tested safely |
| SPEX ARC-AGI-1 public data | Pass for exact grid outputs under the local-reference evaluator | Conditional: data are local, but the recorded rules-manifest integrity conflict remains | Pass in principle | Pass in the source's development runner | Weak fit for external-state, evidence-provenance, retry/recovery, and controlled-action questions in the first cycle | Pass, but the source's formal evaluation boundary is not ready | Deferred; integrity, official-evaluator, exposure, and governance limitations dominate |
| Prime Verifiers reverse-text / Wordle / Bash interception | Pass within each environment | Conditional: reverse-text loads a Hugging Face dataset; Wordle inherits `textarena`; Bash interception has only two tasks | Pass in principle | Conditional on installed runtime and model endpoint | Bash interception exposes action blocking; reverse-text is largely string transformation | Conditional on adopting or adapting the verifiers harness | Rejected as the initial distribution; retain as harness/mechanism references |
| AFlow / Agent Lightning benchmark families | Usually pass for benchmark answers | Fail for the present safe-local gate without dataset/model setup and, for meaningful runs, model access | Pass | API/model and optimization costs can be recorded but would require approval | Mostly answer-quality and optimization phenomena; weaker direct provenance/state-change fit | Conditional on framework/data setup | Deferred to later optimization studies |

## Why the Selected Slice Is the Best First Vehicle

1. **Outcome and evidence can be separated.** Exact expected observations determine actual outcome, while source-path/hash evidence and the system's own claim determine epistemic status. A document contract that correctly returns `passed: false` is a successful task outcome, preventing “negative observation” from being conflated with task failure.
2. **The environment is safe and reproducible.** All selected tasks are read-only, network-free, credential-free, and independently repeatable. Pre/post hashes can detect accidental mutation.
3. **The distribution is small but heterogeneous enough to expose errors.** It contains literal extraction, structure/selector observation, terminology conflict/no-conflict cases, and contract pass/fail cases.
4. **It supports interpretable controls.** A literal-only narrow control and a more capable structured narrow control can establish a local reference point while holding the evaluator, data, repetitions, and execution policy fixed.
5. **It leaves mechanisms separable.** Verification, retries, routing/escalation, prompt/program optimization, workflow search, and specialization can later be introduced one at a time without adopting an imported runtime.

## Limitations and Uncertainty

- **Not established:** that the 12 fixtures are representative of real document-operations workloads or of agentic intelligence generally.
- **Not established:** that source-provided expected artifacts are free of authoring errors; the first cycle treats them as the declared fixture oracle and records that boundary.
- **Not evaluated:** irreversible actions, external side effects, stateful operation, rollback, targeted recovery, maintenance under change, or long-running context management.
- **Unclear:** how much fixture-specific wording allows narrow controls or models to overfit. The baseline is explicitly development/pilot evidence, not held-out generalization evidence.
- **Unknown:** original upstream revisions and pre-import modifications for the preserved source snapshots.
- **Not established:** task-success or reliability thresholds required for any future deployment.

## Alternatives Reconsideration Gate

Reconsider the full 48-fixture frame only after copied-workspace execution and mutation containment can be tested as independent interventions. Reconsider ARC only after its recorded integrity/evaluator limitations are resolved for the intended claim. Reconsider external benchmark tasksets when dataset identity, model access, and cost authority are explicit.
