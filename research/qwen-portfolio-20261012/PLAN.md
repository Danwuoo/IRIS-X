# Qwen14B preregistered portfolio successor

## Purpose and evidence
Manual v18 completed a real BF16 Qwen3-14B pilot. Program LoRA at update16 improved the six seen-family disjoint queries from2/6 to5/6, but the original one-exposed-case/direct-grid-NLL selector selected update0. An exploratory fixed base/8/16 demo-only portfolio reached6/6 on that already inspected panel. This motivates a prospective selection experiment, not an accuracy claim.

## Locked first release
- Preserve exact157-member pilot baseline in this new worktree; never rewrite prior releases or evidence.
- Qwen3-14B same official model revision, BF16 frozen base, FP32 rank8/alpha16 LoRA, context2048, batch1, deterministic native generation. No FP8/4L4 claim.
- One manual notebook, session maximum43200seconds including setup/hash/load/closure; fresh timestamp captured once when the user explicitly starts a fresh unique run. No server submission by this development task.
- Reuse bounded cache admission and physical work accounting. Test actual decisions and retain diagnostic evidence. No generic full-prefix fallback whose forecast cannot complete the measured panel.
- Two independent authored-training branches, grid and program, checkpoint updates0/8/16. Persist every candidate, branch identity, full resume state and exact inference tensors. Reload from disk after clean reset; verify real generation and NLL parity. Never restore physical accounting.
-63 fixed cases:13 old seen regression,12 new grids within trained families,6 new-family holdout,8 multi-family canaries excluded from optimizer/holdout,24 deterministic genuine ARC training-source tasks in held-out official development partition. Public evaluation data/gold are never inputs.
- Separate target-free solver cases, canary-only target access for development ranking, and target escrow for final scoring. Seal predictions and all candidate choices before scoring heldout targets.
- Branch-aligned canary rank: grid exact/shape/validity with matched grid NLL only as tie-break; program exact/demo-fit/query-validity, no grid NLL. Retain every checkpoint even if canary chooses base.
- Per-task program portfolio is preregistered base→program8→program16, demo-only eligibility and bounded VM query, top2 distinct grids, explicit abstention. Record individual checkpoint, canary-chosen checkpoint, fixed portfolio and separate oracle diagnostic; do not silently replace actual outputs.
- Grid and program output bounds256 (within prior admitted native maximum) to avoid the observed program128 truncation, while recording all context/length exclusions in full denominators. Old13 cap changes are disclosed as a new configuration, not a perfectly identical replication.
- No claim the63 cases are PUBLIC120, unbiased general ARC, untouched pretraining data or90%. New-family scope is explicit. Authored families and exact real-task split are frozen before run.
- A separate fixed32-parent realARC training candidate inventory and safe demo-verified program-record API provide the next expansion path. First release does not silently train on evaluation/canary tasks; any optional second training phase must have its own predeclared plan and budget before enabling.

## Budget and execution
V18 measured ~14min notebook cell,184s model load,57s calibration and457s for eight13-case panels. New plan scales only generation/scoring work with explicit full-size token bounds; it includes reload/checkpoint disk costs. Forecasts are estimates, actual token/wall/memory costs are reported. A bounded core panel must be feasible before training; insufficient time leads sealed partial evidence with denominator intact, not success or a new clock. The12h ceiling is a maximum, not a target duration.

## Success criteria
Engineering acceptance requires complete hash/source/data lineage, all candidate disk reloads, clean process closure, no gold-dependent selection, full denominators, actual PEFT CPU behavior, and production-topology tests including failure/partial/resume. Scientific acceptance is separate: on the new heldout panels, evaluate portfolio vs frozenbase on the same cases, report gains/losses and pass@1/pass@2. A positive signal requires net paired gain without dropping invalid/excluded cases; no guarantee is asserted. RealARC result and authored controls are separate.

## Ownership and validation
Selection, independent panels and checkpoint persistence have separate source writers. Lead integrates experiment/runner/deployment and sealed analysis. Independent reviewer audits final assembled bytes and adversarial contracts. Heavy CPU tests run sequentially. Full14B GPU behavior, wall cost and new accuracy remain untested until the user manually runs the artifact. No external writes are needed for local development; any later upload binds exact payload/destination separately.
