# Coordinator-Only Post-Freeze Context Unblind Memo

## Status

Memo status: `coordinator_only_post_freeze`.

Packet ID: `PS1-LB-PACKET-20260601-113121-BATCH-001`.

Source Lane A run: `20260601_113121`.

Primary label freeze: `2026-06-05T21:40:44+08:00`.

This memo was prepared only after the primary labels were frozen. It is not a
primary-labeler-visible packet artifact and must not be copied into
`working_set_context_items.jsonl`, redacted task packets, or packet-local label
templates.

## Sources

This memo uses only post-freeze coordinator sources:

- `working_set_context_items.jsonl`
- `label_results_primary_filled.json`
- `coordinator_primary_label_packet_freeze.json`
- `docs/04_experiments/results/post_stage_1_larger_sample/20260601_113121/run.json`
- `docs/04_experiments/Baseline_Identity_Plan.md`
- `docs/05_evaluation/Post_Stage_1_Lane_B_20260601_113121_Label_Report_Skeleton.md`
- `docs/04_experiments/Post_Stage_1_Context_OS_Evaluation_Plan.md`

The blinded item file identifies `context_arm_A` records with `raw_trace_*`
context artifacts and `context_arm_B` records with `working_set_*` context
artifacts. The source run metadata identifies the working-set baseline arm as
`raw_trace_bounded_openclaw_agent_local/openai-codex/gpt-5.4-mini_matched_budget`
and the working-set treatment arm as
`working_set_compiler_v0_reference_backed_openclaw_agent_local/openai-codex/gpt-5.4-mini_matched_budget`.

## Arm Mapping

| Blinded arm | True arm role | Source arm label | Context artifact prefix | Claim boundary |
| --- | --- | --- | --- | --- |
| `context_arm_A` | Context baseline | `raw_trace_bounded_openclaw_agent_local/openai-codex/gpt-5.4-mini_matched_budget` | `raw_trace_*` | Bounded raw-trace context baseline under OpenClaw local harness; not pure model-only. |
| `context_arm_B` | Working Set Compiler v0 treatment | `working_set_compiler_v0_reference_backed_openclaw_agent_local/openai-codex/gpt-5.4-mini_matched_budget` | `working_set_*` | Reference-backed `Working Set Compiler v0` treatment; not full Context OS. |

This mapping is coordinator-only. It may be used for post-freeze planning and
interpretation, but it must not be backfilled into reviewer-visible packet
records.

## Arm-Level Label Interpretation

| True arm | Blinded arm | Human omission result | Human relevance result | Main takeaway |
| --- | --- | ---: | ---: | --- |
| Bounded raw-trace context baseline | `context_arm_A` | `0.7368` (`14 / 19`) | `0.4545` (`5 / 11`) | Five of six items had critical omissions. The baseline often selected no context or selected only noise, with one partial recovery-context item and one structured-edit item that was mostly sufficient. |
| Working Set Compiler v0 treatment | `context_arm_B` | `0.0000` (`0 / 19`) | `0.9500` (`19 / 20`) | All human-labeled task-critical refs were present. Relevance was high, with the remaining loss caused by included irrelevant noise in the structured-edit context item. |
| Combined blinded packet | A+B | `0.3684` (`14 / 38`) | `0.7742` (`24 / 31`) | Combined values are packet-level Lane B label evidence only and should not hide the arm split. |

For omission, the denominator is human-labeled task-critical candidate refs.
For relevance, the denominator is included refs, with empty included-ref sets
counted as `max(included_refs, 1)`.

## Task-Level Takeaways

| Task | `context_arm_A` interpretation | `context_arm_B` interpretation |
| --- | --- | --- |
| `docops_ws_evidence_packet_001` | Critical omission. No selected refs; omitted `constraint:read_only`, `evidence:fixture_packet`, and `state:evidence_packet`. Relevance contribution: `0 / 1`. | No omission. Selected state, constraint, and evidence packet refs. Relevance contribution: `3 / 3`. |
| `docops_ws_irrelevant_context_001` | Critical omission. Selected only `artifact:noise`; omitted source, constraint, and state. Relevance contribution: `0 / 1`. | No omission. Selected state, constraint, and source; omitted only noise. Relevance contribution: `3 / 3`. |
| `docops_ws_omission_trap_001` | Critical omission. Selected only `artifact:noise`; omitted late source, constraint, and state. Relevance contribution: `0 / 1`. | No omission. Selected state, constraint, and late source; omitted only noise. Relevance contribution: `3 / 3`. |
| `docops_ws_recovery_context_001` | Critical omission. Selected noise plus state, but omitted `constraint:read_only` and `recovery:fixture_context`. Relevance contribution: `1 / 2`; packet quality was `minimal`. | No omission. Selected state, constraint, and recovery context; omitted only noise. Relevance contribution: `3 / 3`. |
| `docops_ws_traceability_long_001` | Critical omission. No selected refs; omitted source, constraint, and state. Relevance contribution: `0 / 1`. | No omission. Selected state, constraint, and source; omitted only noise. Relevance contribution: `3 / 3`. |
| `docops_ps1_ws_structured_edit_context_001` | No omission. Selected source, state, read-only constraint, selector, and noise. Relevance contribution: `4 / 5`; packet quality was `mostly_sufficient`. | No omission. Selected the same relevant refs and noise. Relevance contribution: `4 / 5`; packet quality was `mostly_sufficient`. |

## Allowed Interpretation

- The post-freeze unblinded packet supports the packet-level statement that the
  `Working Set Compiler v0` treatment arm had lower human-labeled omission and
  higher human-labeled relevance than the bounded raw-trace context baseline on
  the six labeled long-context tasks in this packet.
- The labels are consistent with the Lane A structural working-set direction
  for this same source run, but they do not replace Lane A metrics.
- Future Context OS planning may use these labels to prioritize omission
  control, provenance-preserving required-ref selection, and noise filtering.
- Relevance must be read with omission. A sparse or empty context can otherwise
  appear deceptively precise or require an artificial denominator.

## Disallowed Claims

- No H3 validation.
- No full Context OS validation.
- No production readiness or runtime approval.
- No learned retrieval, learned ranking, compression, memory governance, or
  memory-write authorization.
- No new `accepted_by_closure` status beyond the Lane A source closure.
- No pure model-only baseline claim for OpenClaw local harness arms.
- No statistical generalization beyond this named packet; raw agreement counts
  remain small-sample reporting only.
- No retroactive exposure claim. The arm mapping remained withheld until after
  primary labels were frozen.

## Packet Boundary

The reviewer-visible item JSONL files, redacted task packets, and primary label
results remain the recorded packet and label artifacts. This memo is an
additional coordinator-only interpretation note for post-freeze planning.
