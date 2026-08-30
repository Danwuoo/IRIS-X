# Phase 4 Evidence-Binding and Interception Results

- **ID:** `note-2026-08-30-phase-4-evidence-interception-results`
- **Status:** result — reviewed second scoped Phase 4 batch
- **Question/scope:** Record separate H-V1b and H-I1a results. This note does
  not rank mechanisms, synthesize architecture, authorize another Phase 4
  mechanism, or begin Phase 5.
- **Corpus records:** `src.vanta`, `src.prime-intellect-verifiers-v1`

## Evidence Basis

| Evidence | Classification | Use in this batch |
| --- | --- | --- |
| `src.vanta`: `sources/predecessors/vanta/docs/02_specs/Evidence_Packet_and_Verifier_Runtime.md` and `docs/04_experiments/Experiment_002_Evidence_Verifier.md` | Source-stated imported mechanism and limitation evidence | Motivated externally grounded evidence, separate verifier decisions, and false-accept/false-reject accounting. VANTA's schemas, runtime, and reported results were not inherited as IRIS-X results. |
| `src.prime-intellect-verifiers-v1`: `sources/external/prime_intellect_verifiers_v1/environments/bash_interception/bash_interception/taskset.py` | Directly observed imported mechanism example | Demonstrated that a buffered Bash request can be stopped or replaced before execution and then checked through sentinel state. Its task/runtime interfaces were not adopted. |
| The two completed run directories named below | Directly observed local deterministic experiment evidence | Supplies frozen definitions, raw records and copied workspaces, derived aggregates, and reviewed interpretations. |

H-V1b asserted the registered VANTA tree
`4e095233520418705168f40a556177477839b052`. H-I1a asserted the registered
Prime Intellect Verifiers tree `cbe80a474790e5aa98642c754e34ded4a759bbf4`.
Both runs used no network, model, credential, token/API, or paid service and left
imported source and papers unchanged.

## H-V1b — Evidence / Provenance Binding

**Exact hypothesis**

> Holding actual output, actual outcome, system claim, task bytes, semantic
> verifier behavior, and execution path fixed, evidence-bound verification will
> distinguish success supported by complete path/hash evidence from success
> accompanied by missing, stale, crossed, unrelated, conflicting, or otherwise
> invalid evidence, while leaving actual outcome unchanged.

- **Experiment ID:** `exp-2026-08-30-docops-evidence-binding`
- **Completed run ID:** `hv1b-20260830-local-01`
- **Evidence classification:** directly observed finite-sample paired local
  path/hash-integrity evidence
- **Support status:** `Supported — task-local`
- **Directly observed result:** 576/576 valid records. All 576 actual outcomes
  were success and every semantic-verifier decision was accept. Treatment
  accepted all 36 complete-correct records as sufficient and denied
  verified-success eligibility to all 252 invalid/insufficient records: 36
  missing-entry records were insufficient and 216 other invalid variants were
  invalid bindings. Those 252 cases remained actual successes labeled
  `unverified_success`. Treatment had zero false verified-success acceptances
  and zero complete-evidence rejections; all decisions repeated three times.
- **Reliability observation:** deterministic arm/case repeat agreement under the
  declared horizon. Held-out, shifted, stateful, change, recovery, long-running,
  and production reliability were `Not evaluated`.
- **Cost observation:** treatment path/hash checking recorded 230.65 ms wall and
  187.5 ms process CPU across 288 records. Evidence payloads totaled 60,318
  bytes per arm; decision payloads were 50,112 bytes control and 55,650 bytes
  treatment; the combined raw terminal artifact was 1,306,208 bytes.
- **Narrow supported constraint:** under this local protocol, a semantically
  correct claimed-success result should not become eligible for verified success
  unless required evidence paths identify declared inputs and their actual bytes
  recompute to the supplied hashes without missing, extra, or conflicting
  entries.
- **Remaining uncertainty:** causal provenance beyond registered bytes,
  universal evidence sufficiency, model-generated citation trust, real-world
  lineage, held-out behavior, and complete parent H-V1 are `Not established`.

The treatment interface received only fixture boundary, declared path/role
requirements, and supplied evidence. It received no case/variant identifier,
challenge validity, actual outcome, or semantic-verifier decision. A targeted
temporary-fixture test changed real bytes under an unchanged envelope and
changed the decision, directly checking real path/hash recomputation rather
than case lookup.

## H-I1a — Pre-execution Write Prevention

**Exact hypothesis**

> Holding the proposed action, copied-workspace starting state, policy, and
> state oracle fixed, pre-execution interception will prevent prohibited state
> mutations, whereas post-hoc checking can detect but cannot prevent those same
> mutations after execution.

- **Experiment ID:** `exp-2026-08-30-preexecution-write-interception`
- **Completed run ID:** `hi1a-20260830-local-01`
- **Evidence classification:** directly observed paired deterministic
  copied-workspace mutation/prevention evidence
- **Support status:** `Supported — task-local`
- **Directly observed result:** 48/48 valid records. Post-hoc executed all 18
  prohibited proposals, empirically observed all 18 protected-state mutations,
  and detected all 18 after execution. Treatment executed zero prohibited
  mutation primitives and the independent post-state oracle confirmed 18/18
  protected-state preventions. Both permitted controls completed in all six
  treatment records with zero false blocks. Starting snapshots and action
  hashes were paired-identical and all decisions repeated three times.
- **Reliability observation:** deterministic arm/action repeat agreement under
  the declared horizon. Shell/process containment, adversarial bypass, model
  compliance, OS sandbox security, stateful, change, recovery, and long-running
  reliability were `Not evaluated`.
- **Cost observation:** post-hoc recorded 9.7789 ms wall and treatment 2.3996 ms
  across 24 records per arm; process CPU measured 0.0 ms at timer resolution.
  Terminal payloads were 94,198 bytes post-hoc and 94,591 bytes treatment; raw
  terminal output was 200,852 bytes and preserved copied-workspace files were
  8,643 bytes. Timing is descriptive because arms take different paths.
- **Narrow supported constraint:** for these deterministic local actions, policy
  evaluation must occur before the mutation primitive if prevention—not merely
  detection—is required, and prevention claims must be confirmed through
  measured post-state.
- **Remaining uncertainty:** complete tool safety, shell/process/OS isolation,
  adversarial resistance, broader mutation classes, model behavior, and complete
  parent H-I1 are `Not established` or `Not evaluated` as stated above.

Every state change targeted a fresh workspace under the new experiment run's
`raw/workspaces/` directory. The post-state oracle accepted only before state,
after state, action, and policy; it could not consume the interceptor decision.

## Cross-Result Boundary and Uncertainty

The mechanisms answer different questions and are not reduced to a scalar
winner.

- **Unknown:** upstream revisions beyond registered local trees; electricity,
  hardware depreciation, development/maintenance effort, policy and fixture
  authoring effort, deployment workload, and external failure impact.
- **Unclear:** whether the 12 development fixtures support a defensible future
  train/validation/test split and what broader evidence contract would be
  sufficient for model/tool/stateful workflows.
- **Not established:** causal provenance beyond local registered bytes;
  held-out/general performance; production thresholds; complete lifecycle cost;
  parent H-V1 or H-I1; and any final architecture.
- **Not evaluated:** H-P1, H-G1, H-W1, H-C1, H-R1; additional Phase 4
  mechanisms; shell/process isolation; OS sandbox security; model-based
  mechanisms; paid APIs; stateful, robustness, change, and recovery reliability;
  architecture synthesis; and Phase 5.
- **Invalid attempts:** none in this scoped batch.

## Closure Boundary

This batch ends after H-V1b, H-I1a, validation, and retirement of its temporary
plan. It does not authorize another mechanism, architecture synthesis, or Phase
5.
