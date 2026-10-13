# IRIS-X historical experimental synthesis, through 8 October 2026

Repository reviewed: `Danwuoo/IRIS-X`, commit `2901a97a1aa934d15e468e3e6d57bd96d95791e9`. Read-only research on 13 October 2026. Paths and line ranges below are relative to that repository unless explicitly marked as archived Git blobs. No repository files were edited, no tests or model/GPU jobs were launched, and no Kaggle state was changed. This review used committed reports, aggregate metrics, experiment contracts and metadata, not evaluator answer files or raw prediction/answer grid bodies. Historical reports' assertions of independent verification are attributed to those reports; the original large ignored artifacts were not independently rehashed in this review.

## Executive judgment

The project has accumulated real engineering capability, but its evidence through 8 October does not support an official-score success, original full NVARC reproduction, or a high-performing ARC-AGI-2 system. Its strongest scientific lesson is that a valid, complete and rigorously preserved pipeline can still have poor candidate quality.

The most diagnostic terminal observation is the uncapped native run: all 512 TTT updates, all six searches, all 24 batches/96 generation views and eight-view verification completed; 41 unique candidates and 12 actual guess slots survived; top-1, top-2 and retained-pool oracle each remained **1/6** on the four exposed development tasks. Five misses therefore cannot be repaired by changing only the ranking of those retained candidates. This localizes that observation's bottleneck to proposals/representation/adaptation rather than final selection or incomplete execution. It does not prove any replacement architecture, nor that longer search never helps in general. [research/arc-next-line/uncapped-result/README.md:5–11, 36–48, 52–80, 82–110]

Earlier evidence agrees directionally but has narrower or different scope:

- Instruction-only GEPA produced nine legal candidates and no improvement over B1's **12/128 dev**. The locked holdout never reached inference. [trials/arc-agi-2-prompt-pilot/README.md:23–76]
- Increasing no-thinking output budgets from 512 to 1,024/4,096 reduced truncation but added **zero correct answers** on an outcome-selected 64-case diagnostic; a 4,096-token thinking arm frequently never reached a final answer. [trials/arc-agi-2-budget-ablation/README.md:88–124]
- Compact eight-step SFT and one/two-step TTT did not beat compact base on three repeatedly examined tasks; candidate-pool oracle matched the poor final score, so selection was again not the bottleneck there. [trials/arc-agi-2-qwen35-nvarc/compact-abc-002-public-dev-score.md:18–32; compact-abc-003-editor-diagnosis.md:23–36; compact-abc-005-editor-diagnosis.md:22–48]
- Full original-style native TTT raised top-two matches from **5/172 to 10/172** on a modified public input, but at **6.119× recorded wall time**. This is a useful paired development signal, not canonical official-input or uncontaminated-generalization evidence. [trials/arc-agi-2-qwen35-nvarc/public-eval-notebooks-001-diagnosis.md:11–60, 62–103, 136–154]
- E12's 64/128-step pilot reached **1/6 each** among retained predictions while **0/6 each** satisfied full-search output qualification. E13's 120/240-second paired test had **zero matched completed pairs** and is inconclusive. [docs/development/stage4-e12-run003-terminal.md:3–9, 28–62; docs/development/stage4-e13-search-budget.md:103–128]

Do not collapse these distinct observations into one learning curve: they use different models, checkpoints, representations, source variants, task sets, test counts, budgets and completion definitions.

## 1. Initial rationale and product transition

### Pre-product center

The archived foundational synthesis dated 13 September framed the strongest supported center as evidence-governed agency: actual outcome, producer claim, evidence validity/binding, authority and acceptance must be observable separately. It proposed minimum-sufficient configuration followed by failure-directed intervention as an emerging decision program, while treating persistent/long-running state as unestablished. It explicitly denied that one miss demonstrates intrinsic model incapability or the value of stronger models, retries, routing or recovery. This is a source-stated historical synthesis, not a fresh replication of its experiments. [Archive tag `archive/pre-product-transition-2026-09-17`, `research/foundational-research-synthesis.md`, blob `4de4b57e3a7b5dff3be84f54d7752742c9fbf898`:12–22, 32–47, 91–116, 124–139]

That archive also explicitly warned that a run, its result note, closure and later summary are one evidence chain, not four replications. This remains especially relevant to the many README/decision/status duplicates in the ARC work. [Same archived blob:41–47]

The cold archive identifies the pre-transition source commit as `83207e48cc44ce26d0bcb0c98006facfc4f01844`; the payload remains at original Git paths rather than being moved under `archive/`. It is historical evidence and not current product authority. [archive/README.md:3–20, 49–51; archive/AGENTS.md:3–10]

### Product transition

Decision 0001 on 17 September adopted Domain Specification → Build–Measure–Select → Engineering Trial → versioned, reproducible Domain Package. It intentionally did not choose the first domain, model, backend, budget or detailed architecture. [docs/decisions/0001-adopt-product-oriented-domain-ai-specialization.md:3–22, 35–47]

The thesis's essential proposition is not a mandatory training stack. Specialization is a configuration-selection problem over model, prompt/program, context, workflow, adaptation and verification; complexity earns promotion only through measurable value under a real workload and operational constraints. Research is justified when repeated engineering failure exposes a question whose answer improves engineering decisions. [PRODUCT_THESIS.md:5–9, 15–27, 48–91, 151–161, 375–407, 485–505, 509–587]

This explains the historical sequence: establish a runnable baseline, test the simplest intervention, diagnose failure, expand to adaptation/reproduction, then investigate proposal representation. It also supplies the criterion for the next cycle: an improvement must survive matched measurement and deployment constraints, not merely produce a new subsystem or more tests.

## 2. Baseline and prompt optimization: real negative evidence, failed holdout

### Trial 001: the quality question was never measured

The first P2 trial asked whether static prompt/program specialization could add at least five percentage points to official public pass@2 using the frozen `Qwen/Qwen3.8-27B` configuration. `run-001` returned no result after roughly twelve hours and had no recoverable partial state; owner-reported `run-002` logs showed four 600-second timeouts; no verified `run-003` result was accepted. It closed **inconclusive-no-promotion** with no accuracy, no selected candidate and no Domain Package. Timeouts establish failed completion for this configuration, not a measured model-quality baseline or score zero. [trials/first-real-domain/README.md:8–36, 53–64]

### Trial 002: smaller model made the runtime completable

The repair smoke used pinned Qwen3.5-4B, four distinct L4s, four inference-only calls, no TTT and no retry. All four returned valid grids in 175.427 seconds, but exact match was **0/4**. The repository correctly labels this **runtime-verified**, not a successful quality baseline or a public-evaluation result. The first attempt had failed before generation because its competition source was omitted and only two GPUs were visible. [trials/arc-agi-2-baseline/README.md:8–45, 61–100]

### Prompt pilot: GEPA did not improve the frozen configuration

The fixed experiment used greedy Qwen3.5-4B, thinking disabled, 512 generated tokens, one test-index-0 call per task and a 256/128/128 public-training split. Baseline B1 scored 18/256 train and 12/128 dev. Nine evaluated instructions ranged from 5/128 to 10/128 dev; G2 failed in the proposer. Ten proposal attempts were consumed, but all were B1 children, not a demonstrated ten-generation improving lineage. There were 3,840 completed Qwen calls. [trials/arc-agi-2-prompt-pilot/README.md:23–96; failure-analysis.md:80–96]

The baseline's terminal export failed on integer JSON rank keys after all 384 jobs completed. Deterministic checkpoint repackaging recovered the result without new generation. This is an early example of successful model execution but failed artifact finalization. [trials/arc-agi-2-prompt-pilot/README.md:145–177]

The proposed final holdout failed before model load. Its initial diagnosis suggested source drift, but the later full 512-case visible-content audit established a **single-test projection versus full multi-test comparison bug**, not changed source content. Holdout accuracy remains unavailable; it cannot be substituted with zero. [trials/arc-agi-2-prompt-pilot/failure-analysis.md:108–122; trials/arc-agi-2-budget-ablation/README.md:44–56]

Failure analysis separated parsing from content: 380/384 baseline outputs parsed, yet only 30 were exact; 34 hit the cap and all were wrong, but another 320 uncapped outputs were wrong. Best-candidate regressions were not explained by truncation. Ten prompt variants' retrospective dev union was only 16/128 and required an answer oracle, so it was not a deployable ensemble result. [trials/arc-agi-2-prompt-pilot/failure-analysis.md:28–78]

The reflective interface omitted stop reason and actual token counts, selected at most three examples by serialization size, and did not preserve an audit-ready coverage record. It could therefore misdiagnose truncation as reasoning failure while only allowing instruction changes. Evaluation wall cost was roughly 19 times reflection wall cost; reducing proposer size was not the evidence-supported optimization target. [Same file:80–106]

### Budget ablation falsified the narrow easy fix

The frozen 64-case train diagnostic contained 18 previously correct, 22 capped, 12 wrong-size and 12 wrong-content cases. Cached B0 off/512, A1 off/1,024 and A2 off/4,096 each scored 18/64, retaining the same 18 correct. A1/A2 reduced cap hits from 22 to four without adding correctness. A3 on/4,096 scored 7/64, retained six old successes, gained one and lost twelve; 57/64 exhausted reasoning/final budget before the final separator. No arm met the preregistered +4 net/≥16 retained gate, so no validation workload ran. [trials/arc-agi-2-budget-ablation/README.md:51–56, 88–124]

Interpretation: more output capacity did not solve this fixed diagnostic, and this bounded greedy thinking treatment was unhelpful. This is not a claim about unconstrained reasoning, all thinking settings, general GEPA, or public evaluation performance. The outcome-selected cohort cannot estimate population accuracy. [Same file:110–160]

## 3. NVARC port, compact M2/M3 and SFT/TTT

### Why NVARC was a distinct method line

The imported recipe combined a 16-symbol grid representation, ARC SFT, per-task rank-256 rsLoRA adaptation, augmented DFS at cumulative probability floor .2, eight-view likelihood verification, vote-minus-mean-NLL ranking, and separate synthetic-data/TRM branches. The historical Qwen3.5 port was not identical to original Qwen3/NeMo/Unsloth: it mapped different token IDs, changed the hybrid-model adapter/cache path and initially used short unpacked training. The reported NVARC 4B-only score and 2B+TRM score were different systems and must not be conflated. [trials/arc-agi-2-qwen35-nvarc/source-use.md:15–36]

### Compatibility and backend feasibility earned narrow acceptance

The compact flow progressed through real operational failures: hardware mismatch, incompatible preinstalled torchao/PEFT, Dataset root-inventory mismatch, then tuple serialization. The eventual compact-003 flow verified conversion/reload, two synthetic task-local LoRA steps, four generations and a truth-free result; candidate availability was 2/4, not accuracy. [AGENTS.md:395–473; trials/arc-agi-2-qwen35-nvarc/README.md:505–523]

M2 FSDP first hit a collective timeout, then completed a step but lost its result to tuple serialization. The third probe verified one full-parameter compact 4B step across four L4s, 240 input tokens, finite gradients/weights and a changed global fingerprint; peak allocation was 9,426.9 MiB/rank, step wall 6.324 seconds. No model checkpoint was exported in that feasibility probe. [trials/arc-agi-2-qwen35-nvarc/m2-m3.md:245–308]

M2's later eight-step run completed 2,578 input tokens/32 forwards, four-rank restore and an independently verified HF export, then failed before TTT because the installed package lacked its repository-relative source manifest. Its optimizer state had lived only in session scratch and was not retained. These are genuine training/export milestones, but not full-scale ARC-SFT or a durable-resume product. [trials/arc-agi-2-qwen35-nvarc/m2-m3-decision-0032-terminal.md:7–30]

### M3: schema success did not establish semantic data quality

The first usable teacher batch consumed all four 1,024-token output ceilings, leaving incomplete dependent replies and no accepted SDG data. A later direct/structured batch produced four EOS/schema-valid stages, yet violated the intended transformation, composition and program contracts; there were still no accepted SDG pairs. Continuing dependent stages after merely nonempty replies had compounded earlier errors. [trials/arc-agi-2-qwen35-nvarc/m2-m3-decision-0032-terminal.md:32–45; combined-003-editor-diagnosis.md:27–42, 71–112]

This history warrants complete-stage and executable semantic checks, not merely EOS, JSON, AST or process-exit validation. Later replay of published programs is separately useful but is not new teacher regeneration or proof of whole-corpus semantic yield.

### Early source DFS diagnosis: extra time could not overcome root pruning

Combined-003's M2 branch took one finite TTT step and four calls but produced no candidates. Every legal root digit was below .2; the best probabilities were approximately .156–.191 despite >99% mass on legal digits. All roots were pruned after one expansion. More expansion/token allowance cannot create an edge once this root is completely pruned. That diagnoses the proximal mechanism, not why the model was uncertain or whether lower-threshold outputs would be right. [trials/arc-agi-2-qwen35-nvarc/combined-003-editor-diagnosis.md:35–69]

### Compact ABC repeatedly found candidate-content misses

On three repeatedly examined public parents:

| Diagnostic | Compared arms | Result |
|---|---|---|
| ABC002 | compact base A; eight-step SFT B; B + one TTT step C | A 1/3; B/C 0/3 for pass@1, pass@2 and oracle |
| ABC003 | A, B; C0 one step 5e-5; C2 two steps 5e-5; CH one step 1e-4 | A 1/3; every B/C arm 0/3 |
| ABC004 | two-path decoder with A/B/C | A 1/3; B/C 0/3 despite changed candidate sets |
| ABC005 | base A; base+TTT AT; SFT B; SFT+TTT C | A/AT 1/3; B/C 0/3 |

Sources: `compact-abc-002-public-dev-score.md:18–32`; `compact-abc-003-editor-diagnosis.md:23–37`; `compact-abc-004-editor-diagnosis.md:25–38`; `compact-abc-005-editor-diagnosis.md:26–48`, all under `trials/arc-agi-2-qwen35-nvarc/`.

Finite updates and exact reset were verified; no missed test had a correct retained candidate. Accordingly, the evidence did not justify another parameter tweak or continued tuning to these three tasks. It also did not establish that full SFT, another checkpoint or substantial adaptation cannot work. The export was an eight-step pilot, not the original 12,716-step recipe.

## 4. Data exposure and original reproduction

### The clean/reproduction split is essential

The six-source original corpus had 3,255,481 training records and 11,509,821,262 compact projected input tokens. All 1,785,960 `nvarc_full` records had an ARC evaluation ancestor; 279,322 also had protected dev/holdout ancestry or duplicate-family exposure. All 120 original validation parent IDs occurred among training ancestors. The separate 720-record validation source is therefore exposed recipe validation, not clean evaluation. These are lineage claims from the committed audit, not a new read of evaluator grids. [trials/arc-agi-2-qwen35-nvarc/original-corpus-20261001.md:18–42]

The clean audit excluded all 55,886 synthetic `nvarc_full` puzzles and retained only five source families, 1,101,555 records, after parent/length exclusions. It could not honestly claim the original six-source clean recipe. Both parents of mixed synthetic examples must be preserved; dropping the second parent creates false cleanliness. Unknown semantic overlap remains unknown. [trials/arc-agi-2-qwen35-nvarc/dataset-acquisition-20261001.md:29–55, 65–110]

The isolated original track intentionally preserved all source rows, long records and exposure tags. Material preparation, tokenizer identity, packing isolation, training execution, checkpoint durability and quality were separate gates. Corpus availability alone did not satisfy them. [trials/arc-agi-2-qwen35-nvarc/original-corpus-20261001.md:46–64, 95–138]

### What the larger engineering continuation established

The Qwen3.5 overnight work verified two-step global-256 prefix SFT/restart/export with 724 tensor digests, complete short-task rank-256 TTT/search/ranking/reset, some joint Qwen/TRM execution, two-step full-width TRM/EMA export, and bounded replay of published SDG programs accepting thirty pairs. All 192 SDG archive members were acquired and hashed. These are nontrivial component and integration proofs. [trials/arc-agi-2-qwen35-nvarc/reproduction-matrix.md:277–314]

What remained open: full 12,716-step SFT and sustainable throughput, original Qwen3/NeMo numerical/version parity, complete teacher regeneration/whole-archive semantics, TRM original notebook v18 and original scale, and independent ARC quality. Segmented packing correctness does not imply fused packed throughput. [Same file:316–327]

### Native 008 closed one important gate

Using the published original-family ARC-SFT checkpoint, native 008 verified one complete 128-step long-task epoch, 955,392 input/476,160 supervised tokens, 506 finite terminal Adam states and exact reset of 506 changed trainable tensors. Training took 862.043 seconds; allocated/reserved CUDA peaks were about 13.90/15.45 GB. Four L4s were present, but only one sequential rank-zero worker performed this training. There were zero generations and no ARC score. Low loss, 0–.002287, was demonstration training loss. [trials/arc-agi-2-qwen35-nvarc/native-ttt-008-editor-diagnosis.md:19–61]

The independent acceptance explicitly says this did not reproduce the published checkpoint's SFT. Original-Qwen3 SFT controls passed on CPU, but the two-step GPU durable restart/export proposal needed 98.8 GB working storage compared with a prior 20.9 GB observation and remained unsubmitted. That was a historical resource comparison, not a new provider rejection. [trials/arc-agi-2-qwen35-nvarc/original-reproduction-acceptance-20261004.md:13–24, 33–59, 86–103]

## 5. Stage 3: private execution, evidence qualification and official scorer separated

The original-native trained solver used the published Qwen3 SFT139 compact checkpoint, original r256 rsLoRA, 128-step adaptation and fixed DFS/verification recipe. Cross-runtime numerical replay remained a separate qualification issue: local Torch 2.12 versus recorded 2.8, Python startup hash seeds and cache output contracts had already caused mismatches. The source-only Stage3 handoff was not quality evidence. [trials/arc-agi-2-qwen35-nvarc/native-solve-stage3-20261004.md:26–64; AGENTS.md:979–1023]

The official candidate's private preview did complete in **21,681.367 seconds (6h 1m)** with 240 tasks, 259 tests, 30,720 optimizer updates and 35,347,968 training input tokens. It exported 372 model slots and 146 duplicate-first filler slots; every test had at least one model attempt. Search terminated natively on 219 tests, at source deadlines on 30 and inference deadlines on ten. [trials/arc-agi-2-qwen35-nvarc/stage3-official-score-001.md:185–212]

That private execution still had partial independent retention qualification: 5,077/5,080 selected evidence files were available; three baseline inventories were missing. All 240 reset-prefill controls were retained, but full before/reset tensor comparison was only possible on 237 tasks. Strict portable GPU replay remained false. [Same file:214–234]

The owner's formal submission **56840442** then ended **Notebook Threw Exception** with null public and private scores. Provider/API `COMPLETE` meant terminal processing, not successful scoring. No traceback or hidden hardware/input/workload evidence established the rerun cause; neither zero work nor completed work should be inferred. This was not official score zero. [Same file:156–175]

## 6. The public BASE/TTT comparison: one positive but costly development signal

Both public runs completed all 120 task pipelines. BASE pass@1/pass@2/oracle were 5/172, 5/172, 6/172; full TTT128 yielded 8/172, 10/172, 11/172. There were four paired top-two successes, six TTT gains, one TTT loss and 161 failures under both. Candidate coverage increased from 32 to 54 tests. [trials/arc-agi-2-qwen35-nvarc/public-eval-notebooks-001-diagnosis.md:18–60]

Important denominator correction: this input was the pinned NVARC/TinyRecursive variant, with five extra tests and two changed demonstration sets versus canonical upstream 120/167. Projected scores of 5/167 versus 10/167 are post hoc projections of that variant execution, not canonical-input reruns. [Same file:62–103]

All 15,360 native TTT updates and reset evidence verified. Recorded wall time was 1,290.418 seconds for BASE and 7,896.522 seconds for TTT (6.119×), while owner approximate timings implied 5.875×. Training represented 83.14% of summed TTT worker duration, not parent elapsed time. Host sums, GPU time and quota charges are different units. [Same file:105–160]

Inference remained severely bounded: 147/172 BASE and 171/172 TTT searches hit a planned deadline. Empty pools accounted for 140 and 118 tests; a correct retained candidate fell outside top two on only one test per arm. Perfect reranking would recover just one additional test in each profile. This supports candidate generation/coverage work before a costly learned judge or more TTT steps. It does not prove the optimal search/verification allocation. [Same file:162–205]

## 7. Stage 4: instrumentation, controlled comparisons and the completed uncapped run

### E00/E01: make the measurement trustworthy

E00 added actual phase clocks, reservations/token accounting, candidate-stage/multiplicity observations and failure/deadline probes. It did not change the default 128 TTT updates or .2 threshold. Initial scope deliberately deferred E01's multi-file/root export transactions; individual atomic file writes did not guarantee a mutually consistent output generation. A reproduced Windows mailbox race showed why existence checks did not guarantee openability; bounded read probation was introduced without hiding permanent errors or extending compute clocks. [research/stage4-e00/CONTROLLER_SCOPE.md:25–53; E01_GAPS.md:6–14, 20–47; REPAIR_001.md:10–30, 37–75]

The durable conceptual distinction is four independent outcomes: `output_valid`, `notebook_exit`, `evidence_qualified`, `promotion`. A legal file with fillers can coexist with failed execution and no scientific success. [research/stage4-e00/E01_GAPS.md:39–47]

Stage4 canonical source was frozen at 120 tasks/167 tests, partitioned answer-blind into 24 dev tasks/35 tests and 96 confirmation tasks/132 tests. This offered prospective decision isolation on historically exposed public material, not a fresh model/project holdout. Technical repeats do not multiply independent task clusters. [docs/plan/2026-10-06-cloud-stage4-development.md:41–60, 70–79]

### E10: hypothesis implemented; full quality effect unestablished

E10 compared interleaved verification against a first-occurrence FIFO deferred queue, preserving default source traversal, .2 threshold, full TTT, votes and source ranking. Only complete eight-view verification could enter a ranked pool; duplicate occurrences still contributed all their votes. [docs/development/nvarc-verification-schedule.md:10–59]

An independent review found a coordinated deadline-tampering gap: producer declaration and terminal could both be changed +30 seconds and rehashed. The repair bound deadlines to a separately retained caller admission. Agreement between two producer-authored records had not independently established an admitted budget. [Same file:89–120]

A narrow native probe was ultimately accepted with 28 control forwards/672 input tokens, zero optimizer steps and no TTT128 measurement. The retained history says the complete E10 quality screen was not run; the four-worker TTT calibration's accepted RUN receipt did not itself observe its result. Later E11/E12/uncapped results show some subsequent runtime capability, but should not be relabelled as the omitted interleaved/deferred screen. [research/stage4-continuation/HISTORICAL-CURRENT-cb5ea253.json:110–120, 261–303]

### E11 and E20: do not recycle unsupported branches

The surviving E11 v9 analysis reports DFS floors .2 and .1 both at 1/6, with no union improvement on the exposed six-test footprint. Its original full recent Git history and some acceptance artifacts had been lost; the recovery clearly distinguished exact package-byte reconstruction from unavailable historical tree/log provenance. The committed summary supports only this narrow prior result. [docs/development/stage4-recovery-20261007.md:3–9, 13–34, 54–67]

The bounded symbolic E20 configuration also failed its larger dev screen: 24 tasks/35 tests, zero candidate vectors, 17 wall-limit outcomes and seven node-cap completions. Its frozen language had 1,120 macros, depth three/twelve expanded AST nodes, 50,000 expansion attempts and ten seconds per task. This rejects that operator/search configuration, not all executable-program or object reasoning. [research/stage4-e20/DEV_SCREEN_001.json:1; research/stage4-e20/README.md:28–79, 164–172]

### E12: prefix mechanics verified, cost/quality hypothesis not established

The 64-step treatment was an early stop of the same original 128-row sampler and 128-step scheduler with 13-step warmup, not a redefined 64-step schedule. Independent fresh optimizer/RNG state and identical first-64 trajectories were required; saved training time could not be quietly reallocated to inference. [docs/development/stage4-e12-prefix-contract.md:3–7, 24–63]

Run002/v10 failed after 646 durable updates because two independent arms shared PhaseTelemetry test indices. Run003/v11 repaired that collision and verified all 768 updates (256 short-arm, 512 long-arm), four worker pairs, 12 test executions and resets. Both retained top-one/top-two outcomes were 1/6; 64-step retained six attempts and 128-step nine. Eleven tests hit source DFS deadlines and one an inference deadline; none completed full native search, so each arm had zero output-qualified tests. [research/stage4-continuation/CURRENT.json, `historical_E12_run002`; docs/development/stage4-e12-run003-terminal.md:3–9, 24–62]

The pilot cannot meet the full screen's ≥25% total allocated-GPU cost reduction/no-more-than-one-lost-test requirement. It had only four selected exposed clusters and one technical repeat; shared-session times cannot identify independent arm costs. Coordinator wall was 1,656.124 seconds; account usage delta was not a job-specific bill. [docs/development/stage4-e12-prefix-contract.md:106–142; docs/development/stage4-e12-run003-terminal.md:64–75]

### E13: genuine paired design, failed measurement

E13 compared 120- versus 240-second generation windows plus 30-second verification reserve from one shared post-TTT128 state per task; arm order was counterbalanced. Other probability/token/forward limits persisted. The intended paired causal comparison was materially stronger than comparing separately retrained earlier runs. [docs/development/stage4-e13-search-budget.md:8–41]

It failed when an 8 MiB event ledger could not reserve the next event. The call was rejected before model entry after 3,703 calls; other workers were stopped and partial evidence was archived. All 512 updates were observed, eight of twelve test executions started, five committed, but **zero matching pairs**, zero qualified tests and zero qualified workers remained. Accuracy scoring was withheld. Therefore the intended search-budget efficacy question is unanswered. [Same file:103–128]

### Uncapped: operational explanation removed for this run, candidate misses remain

The distinct manual run removed program time/forward/token/ledger/archive resource ceilings but retained .2 probability pruning, 16 views, four-view batches, interleaved eight-view verification, 8,192 context, 931 answer-token ceiling, grammar and original ranking. Thus “uncapped” was not exhaustive search over all valid ARC answers. [research/arc-next-line/uncapped-result/README.md:74–80]

All four TTT128 epochs completed: 512 updates, 1,588,992 input tokens, 789,888 supervised tokens; every task's mean training loss fell. All 506 trainable state records changed and reset per task. Six searches completed all 24 batches/96 views, producing 66 raw occurrences, 41 unique candidates, 328 verifier rows and twelve real guess slots without artificial filler. There were 28,542 generation forwards and 82 verifier forwards; coordinator wall was 1,677.447 seconds. Full inference ledgers occupied 95.472 MiB, and every worker exceeded the old 8 MiB ceiling. [Same file:26–72]

Top-1/top-2/oracle remained 1/6, all six tests now qualified, task-macro top-two 25%. Task-macro and test-micro must not be substituted. Native logits were not numerically replayed, and weight files were not in the returned ZIP for a new local rehash. There was no no-TTT control. Its shared 1/6 with E12 is not causal equivalence of TTT64 and TTT128 or evidence that all extra search is useless. [Same file:28–48, 80–101; research/arc-next-line/uncapped-result/public-dev-aggregate.json:9–31]

## 8. Cross-cutting failures not to repeat

1. **Mistaking a lifecycle label for the scientific outcome.** Submitted/RUNNING/COMPLETE, model execution, legal output, retained evidence, scorer success and method efficacy need separate fields. The formal Stage3 exception and the uncapped low score prove why.
2. **Using missing data as zeros.** Trial001 and prompt holdout were inconclusive; Stage3 official scores were null; E13 had unmatched pairs; unknown token/phase/quota values are unknown.
3. **Optimizing the ranker when oracle equals top-two.** Compact ABC and uncapped results had no correct missed-pool candidates. A ranker cannot manufacture them.
4. **Treating easy-to-count training success as generalization.** Updated tensors, finite Adam states and falling demo loss prove optimization, not rule discovery.
5. **Continuing a scientific hypothesis after only engineering repair.** Correcting mounts, dependencies, exports or log limits can yield a measurable run but does not justify promotion.
6. **Changing several factors while calling it a reproduction or ablation.** Qwen3.5 port, original published Qwen3 checkpoint, short SFT pilots, full original training, alternative decoding and source variants are different configurations. Keep exact pins and method boundaries.
7. **Answer-dependent selection or repeated dev overfit.** Keep whole task/family/dual-parent lineage splits; preserve exposed tasks as tuning evidence; do not route by task ID or let evaluator labels enter runtime selection. A fresh partition does not erase pretrained checkpoint exposure.
8. **Making evidence logging itself the dominant failure mechanism.** Serialization, event caps, archive exclusions and exporter transactions repeatedly destroyed finalization. Derive evidence volume from actual worst-case event work; preserve bounded, hash-linked diagnostic chunks without dropping required science/process evidence.
9. **Conflating host timing, parallel-worker sums, device-hour proxies and account quota.** Whole-session accounting includes setup, loading, controls, cleanup and export. Shared leases do not provide independent per-arm cost without an attribution design.
10. **Assuming tiny tests or a green focused suite establish target-hardware validity.** Real long-sequence memory, native dependency behavior, durable storage and cross-Torch numerical replay had distinct failures. Full historical suites eventually remained non-green because of missing artifacts; do not synthesize fixtures or call focused passes full acceptance. [AGENTS.md:1204–1213; docs/development/stage4-e12-run003-terminal.md:77–93; research/stage4-uncapped/README.md:42–48]
11. **Treating recovered bytes as recovered history.** Exact source/package equality can be proven while original Git objects, receipts or independent acceptance reports remain unavailable. Preserve both claims separately. [docs/development/stage4-recovery-20261007.md:13–34, 54–62]
12. **Promoting speculative frameworks by association.** The product thesis says each added backend must earn measured benefit. Historical external results and framework names are design references, not observed IRIS-X efficacy. [PRODUCT_THESIS.md:375–407, 485–505]

## 9. Implications for the next controlled cycle

These are historical-evidence implications, not a replacement for the currently authorized October 13 protocol. The verified current executable plan is SFT256 A / fixed-64-slot B batches / time-matched extra-SFT C, progressing dev16 → PUBLIC120 → held32. Preserve that current design and its exact gates; do not resurrect an obsolete SFT64/full256-sweep plan from older documents. This report does not infer unavailable recent v25 science scores from cost evidence.

### Highest-value scientific discriminations

- **Distinguish learning from simply spending more compute.** The current matched extra-SFT control is important: compare quality and proposal oracle with exact physical training/inference work, not only nominal caps. Historical data never established that falling demo loss or longer training explains improved held-out output.
- **Measure candidate-pool complementarity before selector complexity.** Record valid complete candidate rate, full retained-pool oracle, top-two success, unique whole-task output vectors, empty pools and selector gap. A new branch earns further selector work only after it adds correct candidates on independently controlled tasks.
- **Separate proposal diversity from longer traversal of the same tree.** The uncapped .2 native run completed its declared protocol. More time on that exact completed run has no timeout left to remove; altered pruning, representation, model state or program proposals are new scientific factors.
- **Keep model/text capability appropriate to the proposal language.** A 16-symbol compact checkpoint cannot serve as a general code proposer. The October 8 next-line memo therefore proposed full-vocabulary grid/program/feedback-repair comparisons under a common model, source and accounting contract; this is a motivated hypothesis, not proven superiority. [research/arc-next-line/architecture-memo.zh-TW.md:5–11, 50–87]
- **Use demonstration-only validation honestly.** Program exact-fit is a proxy. Actual leave-one-demo-out must exclude the held-out example from prompting, memory, selection and feedback throughout the fold; simply rerunning a program selected with every demo is not cross-validation. Avoid turning public test success traces into training while still calling them holdout. [research/arc-next-line/architecture-memo.zh-TW.md:89–129]
- **Preregister task/family split, scoring denominator and promotion criteria.** Keep every actual test in denominator, failed/undispatched jobs included. Use paired whole-task uncertainty estimates; technical repeats remain repeated measurements of the same cluster. Keep development, confirmation, exposure and official-score claims visibly separate.

### Minimal evidence packet required before calling the next result a win

1. Exact source/model/tokenizer/environment identity; actual target hardware and loader behavior, not intended metadata only.
2. Complete sealed predictions and full task/test denominator; stopped solver ownership before answer access.
3. Training lineage and exposure audit, complete physical update/call/token counters, immutable session-clock continuity.
4. Distinct completion, evidence, score and promotion outcomes, with original failures preserved.
5. Matched controls, candidate oracle/top-two decomposition, paired gains/losses and whole-session cost at the correct unit.
6. Exact deployment rehearsal and scorer success before any official-performance claim. A private file that parses and an accepted submission receipt are insufficient.

The appropriate historical stance is neither “NVARC failed completely” nor “the method was reproduced and only plumbing remains.” It is: substantial components and a complete narrow native run were verified; original-scale reproduction and clean generalization remain open; the observed low-scoring completed candidate pools justify testing a meaningfully different proposal/learning mechanism with strict controls.
