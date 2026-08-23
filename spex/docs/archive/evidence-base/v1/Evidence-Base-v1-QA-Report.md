# Evidence Base v1 QA Report

## Scope

This QA report checks structural traceability, uncertainty preservation and the most important verification queues. It does not perform a second research round.

## Structural checks passed

- 55 unique sequential evidence IDs; 44 unique source IDs; 39 unique benchmark IDs.
- All evidence rows link to an existing source.
- All non-placeholder benchmark references resolve to `Benchmarks`.
- All claim, taxonomy and counterexample evidence references resolve to `Evidence_Records`.
- All affected-claim references in `Evidence_Gaps` resolve to `Claims`.
- Every required evidence column is populated; unavailable values use explicit uncertainty labels.
- Author interpretation, DR synthesis and evidence-base inference are separated.
- The workbook contains no authored formulas; the formula-error scan found no evidence-table formula dependencies to audit.
- Visual previews were rendered for every sheet and for the result, comparison-quality and provenance regions of `Evidence_Records`.

## Verification queue

| QA issue | Count | Affected IDs / notes |
| --- | ---: | --- |
| Primary experimental evidence directly extracted in this task | 0 | All v1 evidence is normalized from the DR synthesis; direct primary-source verification remains required. |
| Source candidates without an atomic v1 evidence row | 8 | S0016, S0023, S0039, S0040, S0041, S0042, S0043, S0044 |
| Low-confidence evidence records | 6 | E0004, E0005, E0019, E0030, E0037, E0050 |
| Records below High comparability | 39 | See `Comparability_Rationale` in each record. |
| Comparator version unknown where a comparator is named | 30 | E0001, E0002, E0003, E0004, E0005, E0006, E0008, E0009, E0010, E0012, E0013, E0014, E0015, E0016, E0018, E0019, E0020, E0021, E0022, E0025, E0027, E0029, E0030, E0031, E0032, E0033, E0034, E0044, E0045, E0046 |
| Contemporary status unclear or partial | 9 | E0002, E0003, E0004, E0019, E0021, E0022, E0023, E0027, E0030 |
| Tool, retrieval or inference-compute parity High/Unknown | 47 | Inspect the asymmetry columns; the list is intentionally broad. |
| Exact specialist numeric result unavailable | 38 | Qualitative results were preserved without inventing numbers. |
| URLs/DOIs directly available in the DR text | 0 | All source rows are marked `Not reported`; citation handles are retained. |

## Highest-priority records for primary-source verification

- **E0009 — MMedIns-Llama 3 vs GPT-4 / Claude-3.5:** verify model versions, sampled test cases, few-shot settings, per-task scores and independent replication.
- **E0012 — clinical specialist tools vs 2025 frontier generalists:** identify the exact paper, access configuration, scores, tool/data parity and model versions.
- **E0017 — SaulLM vs GPT-4 / Llama 3-70B:** verify the smaller SaulLM variant, prompts, per-category scores, active parameters and contamination controls.
- **E0023 — FinTral vs GPT-4:** verify GPT-4 version, task-level scores, tool/retrieval parity and point-in-time controls.
- **E0032 — SWE-RL vs GPT-4o:** verify shared scaffold, GPT-4o version, rollout budget and exact comparison score.
- **E0037 — unidentified biology benchmark claim:** source identification is required before this row supports any strong claim.
- **E0041–E0043 — PaperQA2:** verify human baselines, time/tool budgets, model backbone, inference cost and per-task protocols.
- **E0044–E0046 — Aviary:** verify base models, scores, cost accounting, comparator scaffolds and the boundary of task-environment generalization.
- **E0047–E0048 — IMO capability systems:** verify inference budgets and preserve their status as boundary-condition system evidence.

## Numeric and citation conflict policy

No conflicting numeric results were silently reconciled. Where the DR presented different metrics or contexts, separate evidence rows were created. Where exact numbers were absent, the numeric fields remain `Unknown` or contain only the explicit qualitative relationship. Citation handles inherited from the DR must be resolved to primary URLs/DOIs in a future verification pass.
