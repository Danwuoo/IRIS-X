# Reliability Protocol v0

- **ID:** `reliability-protocol-v0`
- **Status:** exploratory — active protocol for the current Phase 4 reliability experiments
- **Scope:** Defines common identity, evidence, validity, resource, and dimension-specific measurement requirements. It does not create a universal reliability score, production threshold, architecture, or deployment claim.

## Common terminal record

Every measured episode or cycle must record, directly or through an immutable run manifest:

```text
experiment_id
run_id
reliability_dimension
task_or_action_id
configuration_id
episode_id
cycle_or_sequence_index
task_frame_id
source_id and source_snapshot_id when imported evidence is used
code_commit
frozen_definition_path and SHA-256
environment identity
actual_outcome
empirical_evidence_status
acceptance_decision when applicable
verified_success_eligibility when applicable
terminal_execution_status
invalid_reason when applicable
resource vector
```

The five evaluation states follow `research/evaluation-state-semantics-v1.md`. An acceptance decision cannot supply empirical outcome or evidence truth.

## Frozen identity and validity

Before measured execution, each experiment must freeze and commit its hypothesis, causal variable, arms, task/action bytes, order, inputs, evaluator/oracle, evidence policy, horizon, retry/recovery policy, environment/resource envelope, invalidity rules, and aggregation rules. The run manifest records that earlier commit and a SHA-256 of the definition bytes.

A run is invalid if frozen identity cannot be established, an arm receives non-equivalent starting inputs outside the declared causal difference, imported source changes, a run directory would be overwritten, the independent oracle cannot adjudicate, terminal records cannot be serialized, or aggregates do not reconstruct from raw records. Invalid attempts remain preserved and are not pooled with later runs.

## Reliability dimensions

### Operational reliability

Question: does one fixed configuration remain stable under nominally equivalent execution?

Required observables include outcome, output/evidence hash, terminal status, invalid episodes, sequence/pass position, and unexpected process-state accumulation. Process-lifetime studies must compare equivalent task bytes/configuration/order and attribute only the declared process-lifetime difference. Stable finite execution does not establish days/weeks, concurrent, production, or shifted reliability.

### Stateful reliability

Question: are required invariants preserved across persistent or accumulated state?

Required observables include frozen baseline identity, post-apply state, post-rollback state, path set, SHA-256 by path, required metadata, residual paths/bytes, first drift cycle, and later-cycle degradation. A rollback-return flag is never state truth; an independent state oracle compares empirical state with the frozen baseline. Mutations occur only in validated copied workspaces.

### Robustness

Question: does behavior persist under an independently validated shift?

Every perturbation freezes its preconditions, deterministic builder and seed, equivalence or expected-change validator, and oracle relationship. A transformation is called semantics-preserving only when the independent validator accepts it. Substrate qualification without candidate execution is not system-robustness evidence.

### Change reliability / maintainability

Question: does a frozen candidate/configuration change introduce regressions or improvements under an otherwise identical comparison?

Required identities include both candidate hashes, task-frame identity, evaluator identity, task/source or generation identity, and runtime envelope. Per-task outcomes retain regression, improvement, unchanged success/failure, evidence regression, cost increase/decrease, and invalid-comparison dimensions. Detecting an injected fault demonstrates measurement sensitivity only.

### Recovery reliability

Question: can a declared procedure recover from a frozen failure state to independently valid final state/outcome without new violations?

Records must separately preserve:

```text
failure_state_validated
failure_detected
recovery_attempted
recovery_action_completed
final_state_valid
final_actual_outcome
final_evidence_status
new_side_effect_violation
```

Both arms start from byte-identical frozen failure state. Recovery code cannot consume a precomputed final-success label. An independent final-state oracle supplies state and outcome truth after recovery output is frozen.

## Resource and lifecycle-cost vector

When reliable on the host, record wall time, process CPU time, artifact bytes, changed/residual bytes, action/tool counts, retry/recovery counts, and peak/process memory observations. Unreliable or unavailable measurements are `Unknown`, not zero.

Design-time cost, runtime cost, maintenance/remediation cost, and external failure impact remain separate. A resource envelope constrains execution; a lifecycle-cost boundary defines what a comparison includes. No amortization or scalar lifecycle cost is allowed without a declared workload volume, horizon, units, and accounting rule.

## Aggregation and interpretation

Raw terminal records are authoritative evidence. Derived results must be reproducible solely from the frozen definition, run manifest, and raw records. Report counts/rates and sequence/cycle positions relevant to the tested dimension; preserve partial, failure, invalid, and unresolved states.

Do not combine the five dimensions into one reliability score. A positive result in one dimension does not support another. Use bounded results such as:

```text
Stable under declared horizon
Drift observed — task-local
Supported — task-local
Mixed evidence
Rejected — task-local
Not established
Invalid run
```

## Evidence retention

Normal successful stateful/recovery runs retain compact state manifests, hashes, changed-path lists, required payload/diff evidence, and terminal records. Full copied workspaces are retained only for invalid runs, drift, rollback/recovery failure, or cases where compact evidence cannot establish the relevant fact.

## Uncertainty

- **Unknown:** production workloads, acceptable failure thresholds, electricity/hardware/development/maintenance cost, and external failure impact.
- **Unclear:** appropriate production horizons and whether every dimension needs the same unit of analysis.
- **Not established:** a justified unified reliability metric or transfer from these local fixtures to real systems.
- **Not evaluated:** model, network, concurrency, multi-host, adversarial, and production reliability under this protocol version.
