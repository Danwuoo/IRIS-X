# Phase 4 Reliability and Specialization Readiness

- **ID:** note-2026-08-31-phase-4-reliability-specialization-readiness
- **Status:** result / decision
- **Question/scope:** Consolidate the final Phase 4 reliability-expansion and specialization-substrate batch and decide only whether IRIS-X is ready to design H-P1. This document neither designs nor executes H-P1 and contains no architecture decision.
- **Corpus records:** `src.vanta` fixture evidence is referenced through `document-ops-task-frame-v1`; imported semantics remain evidence, not authority over IRIS-X architecture.

## 1. Evaluation-state semantics

Substrate status: **Qualified for later use**.

`evaluation-state-semantics-v1.md` separately represents actual outcome, empirical evidence status, acceptance decision, verified-success eligibility, and execution/state status. It explicitly rejects the inference that `accept` automatically means empirical `verified_success`. Historical completed run artifacts were not rewritten.

## 2. Forty-eight-fixture qualification

Substrate status: **Qualified with limitations**.

All 48 preserved VANTA Document Ops fixtures were inspected at their executable contracts, including task definitions, declared inputs, acceptance files, expected artifacts, and relevant action/recovery/working-set implementations. Each has a machine-readable status and reason in `task-frames/document-ops-v1.json`.

Status counts:

| Status | Count |
| --- | ---: |
| `qualified-local` | 21 |
| `qualified-with-copied-workspace` | 14 |
| `qualified-for-substrate-only` | 7 |
| `deferred-framework-dependent` | 6 |
| Total | 48 |

Status by stratum:

| Stratum | Status distribution |
| --- | --- |
| traceability extraction | 6 `qualified-local` |
| terminology consistency | 6 `qualified-local` |
| simulated patch and diff | 6 `qualified-for-substrate-only` |
| reversible edit and commit | 6 `qualified-with-copied-workspace` |
| invalid action and path guard | 6 `qualified-local` |
| evidence and verifier challenge | 3 `qualified-local`; 3 `qualified-with-copied-workspace` |
| journal replay and recovery | 5 `qualified-with-copied-workspace`; 1 `qualified-for-substrate-only` |
| working-set long context | 6 `deferred-framework-dependent` |

The six working-set cases are deferred because executable success depends on VANTA Working Set Compiler selection, ordering, kind-priority, and budgeting semantics, while no framework-independent IRIS-X working-set contract is frozen. The replay case is substrate-only because replay/audit-complete success remains coupled to predecessor runtime/journal identity. Simulation cases are substrate-only rather than candidate-execution tasks. No fixture was forced into an inapplicable execution group.

This is a broader local research/evaluation frame, not a representative, general, or validated benchmark.

## 3. Reliability Protocol v0

Substrate status: **Qualified for later use**.

The protocol defines operational, stateful, robustness, change, and recovery reliability separately, with shared record identities but dimension-specific measurements. It introduces no scalar reliability score. Actual outcome, evidence, acceptance, execution, and resource vectors remain separable.

## 4. H-OR1a — process-lifetime operational stability

Empirical status: **Stable under declared horizon**.

Definition commit `da4b698edb1eab8f1b2d59c56fd9c3511aa466f4` predates result commit `47928b5e080ad946f7cd43bd2ad80eb5c97dd05e`. Run `hor1a-20260901-local-01` held 12 task bytes, configuration, evaluator, evidence policy, order, source snapshot, and retry/recovery/model behavior fixed across `fresh-process-v0` and `long-lived-process-v0`.

The horizon was 12 tasks x 20 fixed-order passes x 2 arms = 480 episodes. Both arms had 240/240 successful, evidence-sufficient, completed, verified-success-eligible records. Every sequence position was 20/20 per arm with one response-core hash. Sequence-position drift, within-arm drift, cross-arm mismatch, and invalid episodes were all zero.

Fresh execution launched 240 worker processes; long-lived execution launched one process for 240 episodes. Fresh/long-lived bytes read were each 723,060 and output bytes each 30,900. Observed orchestration wall time was 31,198,144,200 ns fresh versus 1,019,636,300 ns long-lived; worker wall/CPU measurements were 642,255,400/640,625,000 ns fresh and 953,843,200/828,125,000 ns long-lived. These descriptive local timings are not a performance benchmark.

Invalid attempts: none.

## 5. H-SR1a — reversible-cycle stateful stability

Empirical status: **Stable under declared horizon**.

Definition commit `01eaa325d9e9c2e28b59dea89c00e15c5c0b0b86` predates result commit `c19f1bfe0428b516471cf0237671953310c80e25`. Run `hsr1a-20260901-local-01` used all six qualified reversible fixtures over ten cycles in `fresh-workspace-cycle-v0` and `persistent-workspace-cycle-v0`: 120 cycle records.

Each arm had 60/60 changed-state verifications, rollback actions, exact baseline restorations, and successful actual outcomes. Both had zero drift, residual paths, residual bytes, invalid cycles, or retained full workspaces. The independent residual-state sensitivity self-test detected the injected `residual.tmp` path and 17 residual bytes.

Observed wall/CPU measurements were 3,959,461,500/921,875,000 ns fresh and 3,889,273,800/859,375,000 ns persistent. These are descriptive local observations.

Invalid attempts: none.

## 6. H-RCV1a — targeted recovery to valid state

Empirical status: **Supported — task-local**.

Definition commit `efa75a94cbe1fe76296d8c09256b4ad06f30f8ce` predates result commit `43eacb281df6fb7a01ae4d2e78846341fb22c268`. Run `hrcv1a-20260901-local-01` paired five frozen deterministic failure states over three repetitions in `detect-only-v0` and `targeted-recovery-v0`: 30 episodes.

Both arms began each pair at the identical frozen failure-state manifest and detected all 15 failures. Detect-only attempted no recovery and had 0/15 valid final states, with 15 empirically sufficient failure outcomes. Targeted recovery completed exactly one declared recovery action in each episode and had 15/15 independently verified valid final states, 15 sufficient success outcomes, zero new side-effect violations, and zero recovery-induced failures. The recovery implementation did not receive oracle fields or a precomputed final-success label. The failed-recovery sensitivity self-test rejected an altered target.

Observed detect-only wall/CPU measurements were 703,065,000/109,375,000 ns. Targeted recovery used 15 actions and 759,564,500/125,000,000 ns. No full workspaces were retained because no unexpected recovery failure or drift required them.

Invalid attempts: none. Expected detect-only final-state failures are controls, not invalid runs.

## 7. Robustness substrate

Substrate status: **Qualified with limitations**.

Four narrow families qualified: ignored-context insertion under an explicit ignored-field contract, equivalent JSON serialization, permutation under declared set semantics with unique identities, and canonical-equivalent relative path presentation. Each has a deterministic builder, parameters, precondition, independent validator, and oracle-identity check.

The intentionally semantics-changing selector modification was rejected by the equivalence validator. This demonstrates sensitivity of the substrate only. No candidate was executed, and system robustness is **Not established**.

## 8. Change-reliability substrate

Substrate status: **Qualified with limitations**.

The paired harness binds candidate SHAs, task frame, evaluator, generation identity, and runtime envelope, and supports regression, improvement, unchanged success/failure, evidence regression, cost increase/decrease, and invalid comparison as separable dimensions.

Against the intentionally faulty deterministic candidate, it detected one outcome regression, one evidence regression, and one cost increase while preserving three unchanged successes. Unit tests also exercised improvement, unchanged failure, cost decrease, and invalid-comparison behavior. This demonstrates injected-regression measurement sensitivity only; general maintainability is **Not established**.

## 9. Held-out governance

Substrate status: **Qualified for later use**.

The protocol distinguishes `development-visible`, `protocol-instance-heldout`, `protocol-family-heldout`, and `post-freeze-generated-blind`. It prohibits retroactive holdout and post-generation cherry-picking. It requires candidate freeze and SHA, evaluator/generator/runtime freeze, closure of design-time cost, a new seed, complete valid-instance generation, candidate execution, output freeze, and independent evaluation in that order.

If a candidate changes after blind contents/results are inspected, the prior set loses blind status for the changed candidate. The generator implementation is not claimed to be secret.

## 10. Generated task substrate

Substrate status: **Qualified with limitations**.

All four proposed IRIS-X-authored families qualified: traceability extraction, terminology consistency, path/action guard, and structured simulation. Eight declared `development-visible` qualification instances exercised two seeds per family.

Same-seed reproducibility, distinct-seed variation, oracle determinism, public-input sufficiency, hidden-oracle separation, and automated leakage audits all passed. An invalid `count: 0` generator configuration was rejected. Candidate-visible bundles excluded hidden oracle/state, generation seed, candidate freeze SHA, expected answer/validity, and answer-revealing generation metadata.

The future real blind set remains unmaterialized. Difficulty calibration and real-world representativeness remain **Unclear**.

## 11. Specialization execution contract

Substrate status: **Qualified for later use**.

Dry-run `dry-run-20260901-local-01` exercised provider-neutral candidate loading and hashing, public task packaging, generation-manifest binding to candidate SHA, output freeze before independent evaluation, distinct design/runtime ledgers, unknown-provider-cost preservation, and immutable run directories.

The successful deterministic fake completed and was independently verified. The explicit failure fake produced no output, invoked no evaluator, and was retained as a failed terminal record with actual outcome `Unknown`, evidence `unavailable`, no acceptance decision, and no verified-success eligibility. Both design-time and runtime `provider_cost_usd` values remained `Unknown`, not zero.

The dry-run used zero network, model, and paid API calls. It materialized no future blind set.

## 12. Remaining uncertainty

### Unknown

- Future model/provider identity, provider snapshot, provider prices, token usage, optimization budget, blind generation seed, and candidate SHA.
- Behavior under process crashes, machine restarts, network failures, provider failures, and real external compensation.

### Unclear

- Generated-family difficulty calibration and real-world representativeness.
- Whether the qualified task frame and generated families provide a useful future specialization gradient.
- The appropriate future H-P1 design, sample size, optimization budget, and lifecycle-cost decision rule.

### Not established

- Production, concurrent, adversarial, multi-host, days/weeks, or shifted-distribution reliability.
- System robustness or general maintainability; only their measurement substrates were qualified.
- General recovery, arbitrary diagnosis, or safe real-world compensation.
- A representative/general benchmark, a unified reliability score, model-specialization gains, or an architecture requirement.

### Not evaluated

- H-P1, H-G1, H-W1, H-C1, and H-R1.
- Any model, prompt optimizer, workflow search, router/cascade calibration, fine-tuning, or post-freeze-generated-blind candidate run.
- Phase 5 and architecture synthesis.

## 13. Readiness decision

# Ready to design H-P1

All controlling exit criteria for evaluation semantics, fixture accounting, dimension-specific reliability, three separately frozen reliability experiments, robustness/change measurement sensitivity, held-out governance, generated-family qualification, and provider-neutral fake-candidate execution are satisfied within their stated boundaries.

This decision means readiness only to design a separately authorized H-P1 experiment. It does not select a model/provider, authorize a model call, choose an optimizer, establish a result, start H-P1, or promote any mechanism to architecture.

## Validation evidence

The following validations were executed from repository root and passed:

- `python tools\build_document_ops_frame.py`: 48 fixtures, no duplicate, path, source, or status-vocabulary failures; counts 21 local, 14 copied-workspace, 7 substrate-only, and 6 deferred.
- `python -m unittest discover -s experiments\exp-2026-08-31-process-lifetime-stability\tests -v`: 5/5 passed.
- `python -m unittest discover -s experiments\exp-2026-08-31-reversible-cycle-state-stability\tests -v`: 5/5 passed.
- `python -m unittest discover -s experiments\exp-2026-08-31-targeted-recovery-valid-state\tests -v`: 5/5 passed.
- `python -m unittest discover -s experiments\substrates\docops-robustness-v0\tests -v`: 5/5 passed.
- `python -m unittest discover -s experiments\substrates\config-regression-v0\tests -v`: 5/5 passed.
- `python -m unittest discover -s experiments\substrates\docops-generated-heldout-v0\tests -v`: 5/5 passed.
- `python -m unittest discover -s experiments\substrates\model-specialization-v0\tests -v`: 5/5 passed.
- Raw-record aggregate reconstruction: H-OR1a 480/480, H-SR1a 120/120, and H-RCV1a 30/30 records reconstructed the committed result fields.
- `python -m py_compile` over all 20 Python files added or changed since `36de905`: passed.
- `python tools\repository_check.py`: passed with 13 sources, 7 paper artifacts, and hashes checked.
- `git diff --check`: passed.
- Git tree/diff preservation checks: `sources/` tree remained `10e28d83184c789fc468ca1edc3bebf42ba40b46`; `references/papers/` remained `ed29ebcde3f01b00a0e49eb33eef1688566dcad3`; all six pre-existing completed run directories compared cleanly to `36de905`.

## Boundary confirmation

```text
model calls: 0
paid API calls: 0
H-P1 started: no
H-G1 started: no
H-W1 started: no
H-C1 started: no
H-R1 started: no
architecture synthesis started: no
Phase 5 started: no
```
