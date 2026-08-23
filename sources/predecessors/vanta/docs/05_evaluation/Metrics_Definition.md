# Metrics Definition

## Purpose

Define MVP metrics for Vanta evaluation. Stage 1 local smoke thresholds are
locked below. Post-Stage-1 Lane A acceptance thresholds are governed by
[Post-Stage-1 Metric Policy](Post_Stage_1_Metric_Policy.md).

## `task_success_rate`

- Definition: Fraction of benchmark tasks completed according to task-specific success criteria.
- Formula or computation rule: `successful_tasks / total_tasks`.
- Required fields: `task_id`, task success label, evaluator identity, task criteria version.
- Interpretation: Higher is better, but it must not be interpreted without process-integrity metrics.
- Failure modes: Inflated by weak success criteria, hidden invalid actions, or evaluator inconsistency.

## `invalid_action_rate`

- Definition: Fraction of actions judged invalid, unsafe, malformed, or unsupported by state and evidence.
- Formula or computation rule: `invalid_actions / total_actions`.
- Required fields: `step_id`, action validity label, side-effect class, evaluator identity.
- Interpretation: Lower is better; reductions should be checked against false reject and abstention behavior.
- Failure modes: Under-counted when logs omit failed actions or when validators only inspect final output.

## `verifier_false_accept_rate`

- Definition: Fraction of invalid items accepted by the verifier.
- Formula or computation rule: `invalid_items_accepted / invalid_items_reviewed`.
- Required fields: verifier decision, ground-truth validity label, evidence packet ID, task type.
- Interpretation: Lower is better; this is high priority for side-effectful actions.
- Failure modes: Requires reliable invalid-item labels; may be distorted by class imbalance.

## `verifier_false_reject_rate`

- Definition: Fraction of valid items rejected by the verifier.
- Formula or computation rule: `valid_items_rejected / valid_items_reviewed`.
- Required fields: verifier decision, ground-truth validity label, evidence packet ID, task type.
- Interpretation: Lower is better, but some increase may be acceptable if false accepts fall substantially.
- Failure modes: Overly conservative verifier may reduce task completion without improving safety.

## `evidence_sufficiency_score`

- Definition: Mean labeled sufficiency of evidence supporting a verifier decision or commit.
- Formula or computation rule: `mean(labeled_sufficiency_score)` over evaluated evidence packets.
- Required fields: evidence packet ID, sufficiency label, label scale, evaluator identity.
- Interpretation: Higher means evidence is more complete, grounded, and auditable.
- Failure modes: Scores may be inflated if labels reward fluent explanations rather than provenance-backed evidence.
- Post-Stage-1 human or secondary computation: use
  [Post-Stage-1 Labeling Scope and Adjudication Policy](Post_Stage_1_Labeling_Scope_and_Adjudication_Policy.md)
  with `label_policy_version: PS1-LB-LABEL-001`.
  The raw evidence sufficiency label is `0-4`, the normalized score is
  `label_value / 4`, and `needs_review` receives no score until adjudicated.

## `verifier_brier_score`

- Definition: Mean squared error between verifier confidence and strict verifier correctness.
- Formula or computation rule: `mean((confidence - correctness)^2)`, where correctness is `1.0` when the verifier decision matches the oracle under the experiment policy and `0.0` otherwise.
- Required fields: verifier decision, verifier confidence, oracle validity label, evidence packet ID where available, task type.
- Interpretation: Lower is better; it measures confidence calibration for the chosen decision policy.
- Failure modes: Not comparable across experiments unless abstain and request-evidence policies are fixed.

## `commit_integrity_score`

- Definition: Fraction of commits passing journal, verification, and side-effect integrity checks.
- Formula or computation rule: `commits_passing_integrity_checks / total_commits`.
- Required fields: commit ID, episode ID, verifier output, side-effect class, journal completeness label.
- Interpretation: Higher is better; low values indicate unsafe or unauditable application of changes.
- Failure modes: Can be gamed by committing fewer actions or classifying risky actions as low risk.
- Experiment 003 local computation: treatment counts only committed episodes in
  the denominator; baseline is `0.0` because tool-trace-only direct execution
  has no journal/verifier commit path.

## `replay_consistency`

- Definition: Fraction of replay attempts that reconstruct the same accepted state or an explicitly equivalent state.
- Formula or computation rule: `consistent_replay_runs / replay_attempts`.
- Required fields: episode ID, runtime manifest, tool/environment versions, state hashes, replay result.
- Interpretation: Higher is better in controlled environments.
- Failure modes: Non-deterministic tools, missing version metadata, or irreversible external effects can invalidate comparison.

## `audit_completeness`

- Definition: Fraction of episodes containing all required audit fields.
- Formula or computation rule: `episodes_containing_required_audit_fields / total_episodes`.
- Required fields: episode ID, required audit field checklist, journal, evidence references, verifier outputs.
- Interpretation: Higher is better; it measures reviewability, not correctness by itself.
- Failure modes: Complete logs can still contain incorrect evidence or wrong verifier decisions.

## Phase 4 Recovery Metrics

### `recovery_success_rate`

- Definition: Fraction of recovery attempts that satisfy the fixture-specific
  recovery assertions.
- Computation rule: `successful_recoveries / recovery_attempts`.
- Interpretation: Higher is better, but it must be read with compute cost and
  failure-label accuracy.

### `targeted_recovery_success`

- Definition: Fraction of tasks where the selected recovery policy matches the
  expected recovery policy and the recovery attempt succeeds.
- Computation rule: `policy_matched_and_successful / recovery_attempts`.
- Interpretation: Measures whether recovery repaired the intended failure layer
  rather than merely rerunning work.

### `failure_label_accuracy`

- Definition: Fraction of tasks where the recovery classifier includes the
  fixture oracle failure labels.
- Computation rule: `correct_failure_label_sets / labeled_recovery_tasks`.
- Interpretation: Scores classification for Experiment 004 only; fixture oracle
  labels are used for scoring, not treatment input.

### `repeated_failure_rate`

- Definition: Fraction of recovery attempts that leave the original failure
  unresolved.
- Computation rule: `unresolved_recovery_attempts / recovery_attempts`.
- Interpretation: Lower is better and is expected to expose blind-retry limits.

### `recovery_compute_cost`

- Definition: Matched local compute ledger for Experiment 004.
- Computation rule: report model-call count, prompt chars, response chars,
  estimated input tokens, estimated output tokens, and action-attempt ceiling.
- Interpretation: Character-derived token counts are estimates unless the
  backend exposes exact usage.

### `rollback_recovery_success`

- Definition: Recovery success rate on rollback-failure fixtures.
- Computation rule: successful rollback recoveries divided by rollback-failure
  fixture attempts.

### `audit_gap_closure_rate`

- Definition: Fraction of audit-gap fixtures whose repaired audit record passes
  the audit checklist.
- Computation rule: audit-gap recoveries with complete repaired audit divided by
  audit-gap fixture attempts.

### `compensation_policy_accuracy`

- Definition: Fraction of compensable-action fixtures where the system selects
  and completes compensation treatment rather than claiming rollback.
- Computation rule: correct compensation policy successes divided by
  compensable-action fixture attempts.

### Experiment 003 Audit Checklist

An Episode Journal is audit-complete for the Experiment 003 local smoke only
when all checklist groups pass:

- `episode_metadata`: journal has `schema_version`, `episode_id`, `task_id`,
  and `runtime_manifest`.
- `replay_metadata`: runtime manifest records runtime, language, tool
  environment, schema contracts, and allowed side-effect classes.
- `step_audit`: every action path has a schema-valid step with action identity,
  payload, status, side-effect class, and rollback policy.
- `state_audit`: journal records accepted state hashes; rejected candidate
  state is not added as accepted state.
- `evidence_audit`: evidence refs are present and resolve to schema-valid
  Evidence Packets tied to journal steps.
- `verifier_audit`: verifier refs are present and resolve to schema-valid
  Verifier Outputs tied to journal evidence refs.
- `commit_audit`: committed steps have verifier `accept`, complete evidence,
  allowed side-effect class, and reversible backup metadata when applicable.
- `rollback_memory_boundary`: rollback status is explicit and Stage 1
  `memory_write_effects` remains empty.

## Phase 5 Working Set Metrics

### `working_set_budget_adherence`

- Definition: Fraction of evaluated context artifacts whose selected context
  stays within the fixed prompt-character budget.
- Formula or computation rule: `budget_adherent_contexts / total_contexts`.
- Required fields: context artifact ID, arm, max context chars, selected context
  chars, token estimation method, evaluator identity.
- Interpretation: Higher is better; Phase 5 local smoke requires treatment
  adherence of `1.0`.
- Failure modes: Character-derived token estimates are not exact token usage;
  prompt templates must be fixed before comparing runs.

### `working_set_provenance_completeness`

- Definition: Fraction of selected working-set refs with complete provenance
  metadata.
- Formula or computation rule:
  `selected_refs_with_source_path_hash / selected_refs`.
- Required fields: working set ID, selected ref IDs, ref kind, source, path,
  content hash, evaluator identity.
- Interpretation: Higher is better; missing provenance means the working set is
  not auditable even if task output succeeds.
- Failure modes: A ref can have complete provenance and still be irrelevant or
  insufficient for the task.

### `context_omission_error_rate`

- Definition: Fraction of fixture-required refs omitted from the context
  artifact used by an arm.
- Formula or computation rule: `omitted_required_refs / required_refs`.
- Required fields: task ID, arm, fixture required refs, included refs, omitted
  refs, evaluator identity.
- Interpretation: Lower is better; Phase 5 expects treatment to reduce omission
  relative to bounded raw trace under the same budget.
- Failure modes: Fixture oracles may under-specify required context, and this
  metric does not measure whether the model used included context correctly.

### `working_set_relevance_score`

- Definition: Mean relevance of included refs according to fixture relevance
  metadata.
- Formula or computation rule:
  `relevant_included_refs / max(included_refs, 1)`, with required refs counted
  as relevant.
- Required fields: task ID, arm, included refs, fixture relevant refs, fixture
  irrelevant refs, evaluator identity.
- Interpretation: Higher is better; it measures selection precision, not final
  correctness.
- Failure modes: A small but incomplete context can score high if required refs
  are missing, so it must be read with `context_omission_error_rate`.

### `long_task_stability`

- Definition: Fraction of long-context Document Ops fixtures that complete
  without task failure, unsupported commits, or memory writes.
- Formula or computation rule:
  `stable_long_tasks / total_long_context_tasks`.
- Required fields: task ID, arm, task success label, unsupported commit count,
  memory write count, runtime status, evaluator identity.
- Interpretation: Higher is better; Phase 5 requires treatment stability to be
  at least baseline stability.
- Failure modes: Smoke-scale fixture counts do not establish statistical
  stability and must not be interpreted as broad H3 validation.

## Phase 5 Human Labeling Contract

Human or secondary working-set labels are defined by
[Human Labeling Guide](Human_Labeling_Guide.md). The Phase 5 metrics above may
come from different label sources, and reports must name the source explicitly.

For Experiment 005 local smoke:

- `context_omission_error_rate` and `working_set_relevance_score` are computed
  from deterministic fixture metadata in `expected/working_set_acceptance.json`.
- `working_set_provenance_completeness` is a structural check over included
  refs with `ref_id`, `kind`, `source`, `path`, and `content_hash`.
- These values are local smoke scoring references, not human labels and not H3
  validation.

For broader evaluation:

- Human omission labels require a redacted candidate-ref inventory, source
  artifacts, a context artifact, and double annotation or documented secondary
  review before they can be used as broader evaluation evidence.
- Human-derived `context_omission_error_rate` uses
  `human_omitted_task_critical_refs / human_task_critical_candidate_refs` only
  after adjudication. If the denominator is unresolved, report only the ordinal
  omission severity from the labeling guide.
- Human-derived `working_set_relevance_score` treats refs labeled
  `task_critical` or `supporting` as relevant. It must be reported with the
  omission label because high precision can still hide missing critical refs.
- Human provenance audit labels are broader reviewability evidence. They do not
  replace structural `working_set_provenance_completeness` unless a later metric
  policy version defines an explicit mapping.
- A report may describe adjudicated larger-sample labels as broader evaluation
  evidence for working-set quality or H3 pressure testing. It must not describe
  local smoke results, labeling pilots, schema validity, budget adherence,
  provenance completeness, task stability, or absence of unsupported commits as
  H3 validation.

## PS1-G8 Side-Effect Planning Pilot Metrics

These metrics apply only to the named `committable_docops_planning_pilot`.
Positive-proposal completeness uses the predeclared complete positive controls;
family-specific rejection rates use the corresponding negative fixtures; audit
and oracle conformance use all fixtures. Every rate has a strict `1.0` pilot
completion floor.

| Metric family | Metrics | Required |
| --- | --- | ---: |
| Positive completeness | `approval_boundary_completeness`, `target_identity_completeness`, `duplicate_guard_completeness`, `rollback_or_compensation_declaration_rate` | `1.0` |
| Negative rejection | missing target, missing approval, missing idempotency/duplicate guard, missing rollback/compensation, path escape, source-fixture mutation, irreversible misclassification, and memory-write smuggling rejection rates | `1.0` each |
| Whole-pilot integrity | `planning_rejection_rule_accuracy`, `planning_audit_completeness`, `fixture_oracle_conformance` | `1.0` each |

Actual runtime `COMMITTABLE`, `IRREVERSIBLE`, and `MEMORY_WRITE` counts;
external/production target execution; source-fixture mutation; unsupported
commit; approval-as-label; collected approval; schema change; runtime action
addition; and runtime dispatch counts must all be `0`.

The complete `20260715_223158` run passes these planning floors. These metrics
do not measure executed side-effect safety, approval correctness, rollback
success, compensation adequacy, or production readiness.

## PS1-G9 Persistence Metrics

These hard metrics apply only to the named `Fixture-Local SQLite Persistence
v0` gate and Experiment 006. Reports must include observed denominators and raw
counts.

| Metric | Computation | Hard requirement |
| --- | --- | ---: |
| `persistence_artifact_schema_validity` | typed persisted artifacts validating against envelope and payload schemas divided by artifacts checked | `1.0` |
| `persistence_write_success_rate` | successful durable writes divided by writes expected to succeed; expected negative injections are evaluated separately | `1.0` |
| `restart_recovery_success` | safe completed, aborted, or rolled-back recoveries divided by restart recovery cases | `1.0` |
| `replay_consistency` | strict full-fidelity replay successes divided by replay cases | `1.0` |
| `audit_completeness` | committed episodes with resolvable state/journal pointers and required refs divided by audited committed episodes | `1.0` |
| `state_journal_atomicity_violations` | transactions leaving one accepted pointer without the other or a partially visible commit | `0` |
| `duplicate_logical_commits` | repeated identical idempotency requests that create another logical commit/effect | `0` |
| `silent_partial_commits` | partial commits not surfaced as explicit errors or recovery work | `0` |
| `committed_effects_without_journal_refs` | committed effects whose journal lacks resolvable required refs | `0` |
| `artifact_integrity_detection_rate` | injected corrupt or missing integrity conditions detected divided by integrity injections | `1.0` |
| `unsupported_commits` | unsupported side-effect commits | `0` |
| `memory_writes` | executed or persisted memory writes | `0` |
| `irreversible_effects` | executed irreversible effects | `0` |

These metrics support only the named persistence scope. They do not validate
H1-H5, production readiness, distributed persistence, durable memory, full
Context OS, or external side effects.

## PS1-G10 Fixture-Local COMMITTABLE Metrics

These hard metrics apply only to `Fixture-Local COMMITTABLE Document Promotion
v0` and Experiment 007. Expected authorization, verifier, path, crash,
corruption, rollback-failure, and replay-mismatch rejections are successful
negative outcomes, not failed commits.

| Metric | Computation | Hard requirement |
| --- | --- | ---: |
| `valid_approved_commit_success` | successful valid approved promotions divided by positive controls | `1.0` |
| `unauthorized_commit_count` | committed missing/denied/expired/wrong-scope or mismatched approvals | `0` |
| `approval_verifier_substitution_count` | commits where verifier acceptance substitutes for approval or approval substitutes for verifier | `0` |
| `duplicate_effects` | same-key same-request retries that create another file effect | `0` |
| `idempotency_conflicts_incorrectly_accepted` | same-key different-request conflicts accepted | `0` |
| `path_escapes_or_source_mutations` | effects outside the copied workspace or mutations of source fixtures/inputs | `0` |
| `silent_partial_commits` | partial effects or persistence results not surfaced as abort, rollback, recovery-required, or committed | `0` |
| `committed_effects_without_durable_refs` | commits missing journal, approval, evidence, verifier, state, or artifact refs | `0` |
| `restart_recovery_success` | safe restart outcomes divided by restart cases | `1.0` |
| `rollback_success` | proven strict restores divided by applicable restore cases | `1.0` |
| `replay_consistency` | strict replay matches divided by replay cases | `1.0` |
| `audit_completeness` | committed episodes with all resolvable required refs divided by audited committed episodes | `1.0` |
| `unsupported_commits` | action/domain/policy commits outside G10 | `0` |
| `irreversible_effects` | executed irreversible effects | `0` |
| `memory_writes` | executed or persisted memory writes | `0` |

The `20260716_020716` measured run passes every metric. After repository
verification, the separate manifest closure accepts only the named copied-
fixture promotion scope.

## Stage 1 Local Smoke Gate

The first Experiment 001 local smoke run uses OpenClaw
`openai-codex/gpt-5.4-mini` as the candidate canonical local LLM
action-sequence baseline and runs the current seven Document Ops fixtures once.
The measured baseline must be labeled as
`openclaw_agent_local/openai-codex/gpt-5.4-mini_direct_execution` because the
call path includes the OpenClaw local agent harness.

The run may leave the local Document Ops smoke stage only if the treatment arm
meets all of these conditions:

- `task_success_rate == 1.0`
- `evidence_sufficiency_score == 1.0`
- `replay_consistency == 1.0`
- unsupported commits equal `0`

For this gate, an unsupported commit means a treatment task with status
`committed` despite an invalid or unsupported action path. In the compact
`run.json`, this is checked by confirming that no treatment task has
`status == "committed"` with `invalid_actions > 0`.

Failing this gate may still be recorded as a local measured run, but it must be
reported as a failed smoke run and not as validation of the architecture.

The 2026-05-03 run at
`docs/04_experiments/results/experiment_001/20260503_130927/` satisfied this
gate and closes Stage 1 as `Closed: local smoke completed`.

## Post-Stage-1 Gate Tracking

Post-Stage-1 metric and labeling questions are tracked by
[Post-Stage-1 Advancement Gate](../00_manifest/Post_Stage_1_Advancement_Gate.md):

- Larger-sample frame: `PS1-G1`, accepted by
  [Post-Stage-1 Larger Sample Plan](../04_experiments/Post_Stage_1_Larger_Sample_Plan.md).
- Baseline identity: `PS1-G5`, accepted by
  [Baseline Identity Plan](../04_experiments/Baseline_Identity_Plan.md).
- Evidence sufficiency label scale: `PS1-G3`, accepted by
  [Post-Stage-1 Labeling Scope and Adjudication Policy](Post_Stage_1_Labeling_Scope_and_Adjudication_Policy.md).
- MVP acceptance thresholds beyond local smoke: `PS1-G2`, accepted by
  [Post-Stage-1 Metric Policy](Post_Stage_1_Metric_Policy.md).
- Double human annotation or secondary-review requirements: `PS1-G4`, accepted by
  [Post-Stage-1 Labeling Scope and Adjudication Policy](Post_Stage_1_Labeling_Scope_and_Adjudication_Policy.md).
- Phase 5 working-set omission, relevance, and provenance labeling contract:
  [Human Labeling Guide](Human_Labeling_Guide.md).
- Storage and persistence hard metrics: `PS1-G9`, defined by
  [Storage and Persistence Gate](../00_manifest/Storage_and_Persistence_Gate.md)
  and measured by
  [Experiment 006](../04_experiments/Experiment_006_Persistence_and_Recovery.md).
- Side-effect planning-pilot metrics: `PS1-G8`, defined by
  [Post-Stage-1 Side-Effect Evaluation Plan](../04_experiments/Post_Stage_1_Side_Effect_Evaluation_Plan.md)
  and measured by the
  [planning pilot run report](Post_Stage_1_Side_Effect_Planning_Pilot_Run_Report.md).
