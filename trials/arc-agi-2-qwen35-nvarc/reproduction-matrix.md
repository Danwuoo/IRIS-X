# Component completion and reproduction gaps

## Overnight implementation (2026-10-02)

[Decision 0053](../../docs/decisions/0053-nvarc-overnight-development-goal.md)
opens continuous local and free private Kaggle work until substantial
completion or the one-shot 07:00 Taipei timer. The [current report](overnight-source-integration.md)
supersedes the historical pending/absent rows below. Complete original corpus
bytes, shuffle and lineage are verified. Logical MFFD placement matches the
pinned NeMo reference; segmented Qwen3.5 execution passes real hybrid state,
loss and gradient isolation checks. Distributed CPU-shard accumulation,
optimizer/RNG/scheduler/cursor restart and exact export pass independent CPU
checks. Four-L4 SFT 002 completed two accumulated steps and a 724-tensor export;
every transferred tensor independently verifies locally. Full-source
global-256 prefix SFT 003 is accepted/pending. Complete rank-256 128-view TTT
002 verifies sixteen DFS calls, five model candidates, eight-view ranking and
exact reset on L4, with 18.5 GB training peak. TTT 001's mount failure is frozen.
Real isolated published SDG program replay and the unchanged 8/12/4 source
filter accept thirty pairs with both exposure ancestors retained. Full-width
published TRM checkpoint loading/demo-TTT/ACT/reset verifies on CPU float32;
the 192-member raw SDG archive, exact TRM v18 and original scale remain pending.

The Qwen3.5 port is not the original Qwen3/NeMo/Unsloth implementation.
Segmented correctness does not establish fused packing throughput. Full
12,716-step training, original teacher generation, TRM scale/v18 parity and
general ARC quality remain unverified; no promotion follows from these probes.

## Original-recipe scope correction (2026-10-01)

Under the owner's [Decision 0050](../../docs/decisions/0050-separate-original-nvarc-reproduction.md),
preserve all original recipe inputs and isolate exposure. The clean exclusions
below remain true for the earlier clean-data branch, but do not block original
reproduction. Its six training sources and validation bytes are already present;
full corpus import, separate policy/lineage manifests and complete runtime work
remain. Use the [current remaining-work inventory](../../docs/plan/2026-10-01-nvarc-reproduction-gaps.md)
before the older dated snapshots below.

## Actual dataset audit (2026-10-01)

The [dataset acquisition](dataset-acquisition-20261001.md) supersedes the
missing-download state below: both puzzle datasets are retained at version 1,
with ZIP/member digest and CRC verification. Synthetic lineage is a pair of
published ARC IDs, not a single parent. Every `nvarc_full` puzzle combines an
evaluation and training parent; clean-research excludes that whole source.
Five-source filtered HF preparation is distinct from the frozen six-source
contract. Distributed source-recipe integration, target GPU checks, semantic
overlap beyond declared ancestry and a reviewed clean method/data design remain
open. This acquisition is not SFT, full-method completion or execution authority.

## Method-completeness continuation (2026-09-30)

The [new method report](../../docs/plan/2026-09-30-nvarc-method-completeness.md)
supersedes pending-state statements in earlier sections. Current source
identities and available code are verified; full method reproduction remains
incomplete. New local paths import all six source datasets with bound
inventories/parent lineage, implement source SFT optimizer/schedule and
token-weighted accumulation, and consume a complete 128-view r256 task epoch
with source context cuts. Synthetic fixtures and tiny actual-model acceptance
verify engineering semantics only. Actual six-source material, distributed
source-recipe migration, packed isolation, GPU throughput and target-scale
TRM/SDG evidence remain gaps. The eight-step 4B export does not qualify as
full SFT. New dev comparison preparation is inert and data-gated; no ABC 006
or new external workload has been launched.

## Measured compact ABC continuation (2026-09-29)

The [004 result](compact-abc-004-editor-diagnosis.md) completed the fixed
A/B/C comparison with a two-path model beam. The beam changed candidate
pools but left public-development pass@1/pass@2/coverage at A 1/3, B/C
0/3. The [005 paired result](compact-abc-005-editor-diagnosis.md) held that
decoder fixed while comparing no TTT with the same one-step TTT on base and
eight-step SFT pilot weights. All four arms completed. A and AT each attained
1/3; B and C each attained 0/3 on the same three repeated public development
parents. TTT changed adapter tensors but gave no exact-match or candidate
coverage gain. The private version-1 QUICK_SAVE and owner Editor execution
remain distinct; the agent started no session or runtime query.

The [003 result](compact-abc-003-editor-diagnosis.md) completed all five
arms. Isolated public development scoring found A 1/3 and B/C0/C2/CH 0/3
for pass@1, pass@2 and candidate coverage. TTT changes yielded finite
updates but no exact gain on these repeated parents. The [004 plan](compact-abc-editor-004.md)
tests a two-path legal model beam with the same A/B/C checkpoint and call
budget. Its sole QUICK_SAVE and returned Editor result are separately
retained; no agent session was started.

The [002 owner-Editor comparison](compact-abc-editor-002-diagnosis.md) is an
engineering-complete five-hundred-fifty-second 4B run for A compact base, B
eight-step SFT export and C one-step task TTT on three public development
parents. The [isolated local score](compact-abc-002-public-dev-score.md) found
A pass@1/pass@2/oracle coverage 1/3, B 0/3 and C 0/3. B/C misses occur in
candidate generation or content, before ranking could recover an answer.
This selected, repeatedly examined set does not prove model-line superiority
or broad generalization. The eight-step SFT pilot is not full ARC-SFT.

The [003 bounded plan](compact-abc-editor-003.md) is a controlled TTT
sensitivity test with A/B and original C0 controls plus separate step-count
and learning-rate variations. Its saved package and eventual owner-run result
remain distinct states: its private version-1 QUICK_SAVE and returned Editor
result are separately retained. Larger SFT, SDG training benefit,
TRM integration and a locked final evaluation remain open reproduction gaps.

## Current bounded evidence (2026-09-27)

[Local semantic continuation](local-semantic-continuation.md) supplies executable
demo rules, exact composition, actual isolated NumPy contract checks and a full
pair gate. Retained wrong teacher replies yield zero pairs; authored controls
are engineering evidence only. V3's restricted language is a method candidate,
not full SDG parity or verified teacher yield. Source differential/tiny Qwen
checks and a shared-one-TTT threshold comparison are implemented; real .1/.02
arm candidate availability and quality remain unknown. The inert configurations
do not activate prior approvals or alter frozen .2 thresholds.

The [Decision 0032 terminal record](m2-m3-decision-0032-terminal.md) and
[combined 003 Editor diagnosis](combined-003-editor-diagnosis.md) supersede
the pending/unexecuted statements in the older checkpoints below. Runtime
completion does not establish usable candidates, accepted SDG data or ARC
quality. The Editor observations do not establish background kernel status.

| Component | Retained observation | Remaining gap |
| --- | --- | --- |
| M2 SFT/export | Four-L4 eight-step full-parameter SFT, 2,578 tokens, 32 forwards, session resume and digest-verified HF export | No retained optimizer bytes; bounded training does not establish full-scale ARC-SFT quality |
| Post-SFT source solve | Combined 003 Editor completed one TTT step/108 training tokens and four generation calls; every legal root digit was below the fixed 0.2 cumulative-probability threshold | Zero candidates and zero ranking calls; the trace identifies root pruning, not the upstream cause of model uncertainty or the quality of a lower-threshold answer |
| M3 teacher | Combined 003 Editor completed all four EOS/schema-valid stages with 1,071 input and 459 output tokens | Summary, composition and generated input/output programs violate the requested semantics; zero accepted generated SDG pairs |
| SDG replay | Existing isolated saved-response replay now persists pairs/messages/programs with lineage and hashes | Fixture data is not evidence of new teacher yield or semantic quality |
| Combined two-device notebook | Owner-supplied combined 003 diagnostics bind distinct L4 workers, both model-ready events and terminal records; both branches completed in 306.509 seconds | Verified only for this bounded workload; successful terminal checks did not ensure semantic correctness. No usable M2/M3 scientific output or new execution authority follows |
| TRM and joint result | Pinned TRM CPU train/reload/TTT/inference and a candidate passed through source-profile Qwen verification in the retained local checks | Original-scale GPU training, usable Qwen branch candidates, full joint execution and clean ARC quality remain unestablished |

Semantic validation and retained negative replay are now implemented and locally
checked as detailed above. Distinct inert M3 and M2 proposals are reviewable;
additional expansion/token allowance alone cannot overcome observed root
pruning. Full-method acceptance remains incomplete. Old identities, raw
responses, packages and consumed quotas stay frozen; new evidence is offline
program/fixture/tiny-model work, without provider or real 4B/teacher calls.

## M2/M3 bounded continuation (2026-09-25)

[Decision 0032](../../docs/decisions/0032-authorize-nvarc-m2-m3-terminal-repairs.md)
now authorizes the separately identified M2 scratch and M3 tokenizer repairs.
Both approved packages passed offline preflight with zero external calls.
Kaggle accepted private version 1 of each new identity. Actual new 4B SFT
and teacher execution evidence remains pending terminal retrieval; the table
below continues to describe verified work.

The [actual local artifacts and bounded external probe record](m2-m3.md) and
[checkpoint continuation proposal](../../docs/plan/2026-09-25-nvarc-m2-m3-checkpoint-continuation.md)
supersede older missing-path statements below. They do not establish original-scale
method reproduction or ARC quality.

| Component | Executed path | Remaining gap |
| --- | --- | --- |
| Public ARC-SFT split | Exact pinned 8 train/8 dev public training parents and hashes; only train augmented to 128 source-loaded episodes; dev visible-only | No full source mixture or long-context packed-state isolation |
| Full-parameter SFT | Two actual tiny hybrid Qwen3.5 CPU steps with resume/export/reload; the new two-rank FSDP CPU path resumes sharded model/optimizer/RNG/cursor after step 1, reaches 2 steps/240 ARC input tokens, and exports identical HF weights in continuous and resumed runs; FSDP `003` separately completed one real compact 4B step on four L4s, with finite updates, max 9,426.9 MiB CUDA allocation per rank and verified truth-free result `4624b1c4…` | Decision 0031 SFT `001` stopped at the 60 GB working-disk gate (20.94 GB observed) before model work, zero new steps. The 8-step/2,578-token 4B SFT checkpoint and 4B TTT/search/rank remain unverified; Decision 0032's separate-scratch package is approved and preflighted but unexecuted here |
| Post-SFT Qwen path | Tiny SFT and two-rank FSDP CPU exports each feed source TTT, bounded DFS, inverse/dedupe/rank and truth-free result; the latter made four generation calls, no completed grid | 4B source-profile cost, candidate availability, nonempty Qwen ranking and any quality claim |
| SDG | Pinned ten-stage prompt/replay and source pair/filter; real WSL namespace canary now rejects second chroot after capability drop, with normal replay and timeout/memory/process/filesystem/network checks; teacher `001` stopped at two-T4 allocation with zero calls; teacher `002` passed four L4s but its first reserved stage failed with `AttributeError`, producing zero completed calls/responses | New generated-pair yield and original teacher parity remain unknown; the repaired tokenizer adapter and teacher `003` package are approved and preflighted but unexecuted here |
| TRM and joint | Pinned TRM builder/model/loss/optimizers: one actual CPU training step, checkpoint/reload, one task-local TTT, visible-only inference and one TRM candidate sent to eight source-profile Qwen verifier forwards; direct differential confirms summed source NLL and artifact identity | NVARC width/horizon/scale, notebook v18 parity, GPU training, clean accuracy and Qwen branch candidate availability |


## Current source-integration checkpoint (2026-09-24)

This table is the current M0/M1 status for the owner-authorized local phases
1–3. The older implementation snapshots below remain lineage, including their
then-current missing-dependency statements. A fixture or tiny CPU pass does
not establish a 4B source-profile run, full-method completion or ARC quality.
The [source integration record](source-integration.md) and exact
[source manifest](source-manifest.json) contain the bindings.

| Component | Upstream reference | Reuse or patch; actual artifact | Verification command and observed result | Remaining gap |
| --- | --- | --- | --- | --- |
| Source acquisition | `NVARC@846d019` plus seven direct and one nested submodule; Qwen notebook v10; TRM notebook v21 | `tools/nvarc_source.py` checks every Git index/worktree and exact notebook; verified local source-tree bundle supports offline export/import, with `source-manifest.json`, `dependency-manifest.json`, `asset-inventory.json` committed | `python -m unittest tests.test_nvarc_source_materialization -v` covers F1/F2; actual nine-repository bundle export/import returned `source_ready: true`; `python tools/nvarc_source.py verify` passed | TRM notebook version 18 cited upstream could not be fetched; notebooks have no stated license and NVARC has no root license; large data/model assets not acquired |
| SDG messages and augmentation | `SDG/scripts/build_datasets.py:fix_settings/apply_augmentation/get_messages` | Hash-gated upstream functions invoked by `source_sdg_messages`; differential fixture records in-place color-map behavior | Strict `tools/nvarc_ml_profile.py` runs rectangular augmentation and source-message comparisons | Generated program sandbox and real teacher calls unrun; published data not regenerated |
| Source SFT data | `ARChitects/run_sft.py:load_datasets` | Original loader and alternating messages feed `source_sft_sequences`; local source-derived two-record dataset and tiny Qwen3.5 optimizer checkpoint | Strict profile exercises real loader, assistant mask, gradient step and checkpoint | NeMo preprocessing/packing and full real-data SFT remain unverified; no ARC-SFT artifact |
| Qwen3.5 material and model boundary | Qwen3 16-row cut; Qwen3.5 pinned 4B; PEFT | Distinct `arc_nvarc_qwen35_adapter.py` handles Qwen3.5 LoRA targets, full-prefix logits and NLL; source grammar flag preserves prior compact bytes | Strict profile checks tiny real model branch isolation and source role/newline/EOS/mask; historical compact 003 is separately digest-verified | Qwen3 rows/weights cannot be reused; 4B source-profile model and full SFT unrun |
| Task-local adaptation | Qwen notebook v10 `ArcDataset.augment` and `QwenDataCollatorForCompletionOnlyLM` | Original augmentation and collator run through hash-gated extraction; source training views label every demonstration assistant response | Strict profile compares augmented sequence/mask token for token and runs tiny PEFT step; historical compact 003 made two short 4B synthetic steps under its older profile | Source r256/length schedule and ARC tasks unrun; long-context cut/packing not proven |
| Candidate augmentation | Qwen notebook v10 `ArcDataset.forward_mod/invert_mod` | Original D4/color/demo-order views feed source candidate profile; inverse before dedupe | Strict profile compares rectangular inverse, demonstration shuffle and two-test task views | Original process-random hash seed is replaced by explicit seed; 4B source candidate run absent |
| DFS and model calls | Qwen notebook v10 `turbo_dfs` | Original DFS extracted for reference; bounded IRIS-X DFS retains traversal/pruning/EOS semantics on common domain; Qwen3.5 full-prefix forward avoids shared hybrid KV | Strict profile compares deterministic logits and >1,000-token path, each bound and tiny real sibling isolation | Batch KV reuse and performance are not reproduced; source has no equivalent IRIS-X stop accounting |
| Likelihood and top two | Qwen notebook v10 `calc_scores`, `getter_kgmon`, `score_kgmon` | Source profile uses sum NLL incl. EOS, eight shared views and original getter; explicit missing/duplicate vote records remain | Strict profile compares source NLL and top-two, eight views, duplicate and empty cases | ARC ranking quality and 4B source profile not measured |
| TRM data | `TinyRecursiveModels/dataset/build_arc_dataset.py:convert_dataset` | Original pinned builder invoked on locally staged labelled synthetic training fixture; NumPy arrays checked | Strict profile builds and inspects real upstream arrays | TRM train/reload/TTT/inference, weights and notebook v18 parity unverified |
| Shared local stage | Existing IRIS-X solver, reset, checkpoint, material and truth-free result | `configs/source-integration-stage.json` and `tools/nvarc_source_stage.py` select fixture/tiny/4B with one result schema | Strict profile runs fixture and tiny actual-Qwen3.5 paths; 4B profile is configured and identity-gated but not run | No full artifact chain from real SFT through 4B TTT, TRM and joint result |
| Transport regressions | Earlier pilot Dataset mount, optional `torchao`, JSON tuple, Windows log and interrupted transfer failures | Existing checks retained; `resume_digest_member` and `run_utf8_logged_command` added to shared transport | `python -m unittest tests.test_arc_nvarc_transport_io -v` passes interrupted same-digest continuation and non-ASCII log fixture; `python tools/repository_check.py --all` covers existing checks | No live provider range response or new large artifact retrieval tested |

The strict profile requires the offline source cache and installed ML
dependencies; missing prerequisites fail rather than skip. No new Kaggle
kernel, Dataset mutation, teacher call, ARC score or holdout read occurred.

## Earlier implementation snapshot

`implemented` means source code exists. `fixture-verified` refers only to
synthetic CPU tests. None of these labels implies model readiness or ARC score.

| Component | Source method | Implementation | Verification and gap |
| --- | --- | --- | --- |
| SDG stages and provenance | Description → summary/mix → input/output programs → pairing/filtering | Saved/fake teacher stage ledger and call reservations; Docker command bounds generated code; caller claims rejected | Stage fixtures pass; Docker daemon is absent, so container isolation and real teacher calls remain unverified |
| Source data/splits | Six concatenated SFT sources in `sft_mg.yaml` (ARC2 training, MiniARC, ConceptARC, REARC, NVARC training/full); published real + synthetic mix, 3.2M augmented samples | Streaming JSONL import, SQLite-backed parent and known-D4/color overlap, deterministic shards with per-source counts and file-backed training sequence view; clean policy rejects the known `arc2_evaluation6` source | CPU tested; no full dataset acquired, exact counts/ratios or semantic overlap unverified. Source IDs and excluded parents still require a trusted manifest |
| 16-token representation | Qwen3 selected 16 rows | Independent 16-symbol grammar; pinned Qwen3.5 tokenizer was read and all 16 exact single-row IDs verified; tied/untied HF checkpoint conversion, special-token and generation-config checks on reload/export | Compact pilot 003 verified pinned 4B source material, conversion, four-shard save/reload and local material digest; row IDs differ from Qwen3 |
| ARC full SFT | Qwen3 NeMo Megatron 4×8 H100, 12,716 steps | Local PyTorch full gradient, masks, limits, optimizer/scheduler/RNG/cursor checkpoint, inference export; separate bounded DDP worker and wall ledger | Python 3.12 torch single-process resume and two-rank CPU Gloo collective tested; only a separate two-step synthetic 4B LoRA pilot has GPU gradient/memory proof; full SFT throughput, VRAM and GPU sharding untested; no original data |
| Per-task TTT | Qwen3 rsLoRA r256 alpha32, no 4-bit | Qwen3.5 target discovery, fresh adapter state/optimizer/RNG per full task, augmented leave-one-out demos; reset on task success/failure and discarded optimizer | Compact pilot 003 completed one task-local 4B LoRA step on each of two synthetic tasks, with 20 total training tokens; full ARC task-local TTT and r256 remain untested |
| Augmentation | D4, color permutation, demo shuffle | Reversible rectangular-grid D4/color and seeded demo order | CPU round-trip incl. zero/non-square; training mixture differs from source notebook |
| Candidate decoding | Source batch DFS, cumulative NLL threshold `-log(0.2)`, sorted nonterminal siblings, EOS completion | Iterative bounded DFS with distinct expansion/sequence/token/deadline stops, safe full-prefix logit cache and named `hf-beam` alternative | Compact pilot 003 made four actual 4B generation calls and produced complete grids for two of four synthetic tests; source batch KV reuse, high-token and ARC quality remain untested |
| Rerank/top two | 8 shared augmentations and `votes - mean NLL` | Eight-view model NLL, inverse-before-dedupe, deterministic ties, missing-candidate records | Compact pilot 003 completed four actual 4B likelihood verification calls and returned two attempts for each of two tests; two other tests were marked missing; full ARC rerank quality remains untested |
| Four-L4 runtime | Persistent independent workers/dynamic queue | Exact four-L4/source gate, one load per worker, parent timeout/crash terminalization, atomic task ledger | Four synthetic worker processes and forced crash/timeout/result tested; this four-worker runtime has not run on Kaggle; adapter call budget remains proposed |
| ZIP/result/evaluator | Truth-free result, multi-test pass@2 | Existing canonical transport, workload binding, sealed per-test scorer | Compact pilot 003 produced an independently verified truth-free 4B result ZIP; no ARC scoring or holdout score |
| TRM | Independent TRM train/TTT, 10 attempts | Pinned labelled stage, source-hashed preprocess/train/eval specs, bounded invocation wrapper, ten-attempt parser and visible-input raw-tensor normalizer with fixture provenance | 30×30 encoding and launch/parser fixtures pass; upstream dependencies, checkpoint and pure inference launch semantics unverified |
| Combined submission | 2B+TRM and separate 4B-only versions | Combined candidate pool with Qwen verification plus explicit branch-priority fallback | Interface tested; no calibrated/real joint run; cannot attribute or combine original scores |

The original Qwen submission notebook uses Unsloth and a custom batch DFS. The
bounded DFS reproduces its score-pruned traversal semantics, but its safe cache
retains only complete-prefix logits to keep hybrid state isolated. It does not reproduce batch KV reuse,
runtime or the notebook's 540-second internal clock. The original 4B ARC-SFT weights cannot
be loaded into Qwen3.5. This line requires fresh training and measured
compatibility before any capability claim.

## Continuation evidence at 2026-09-23

| Component | Implemented and locally verified | Remaining gate |
| --- | --- | --- |
| Workload/result/material | Independent schema, complete terminal checkpoint, exact counters, closed model inventory and pinned base inventory checks; rehashed adversarial fixtures pass | Large real model material absent |
| DFS | Iterative >1,000-token path, distinct stop reasons and cost counters; safe full-prefix logit LRU parity with reference; canonical duplicate grids share one verification while retaining each vote | Source notebook's batched KV behavior and GPU performance unverified; hybrid KV is rejected |
| Single-process SFT | Python 3.12 torch synthetic gradient/resume passes; optional tiny Qwen3.5 compact reload and PEFT pass in a separate environment; pilot 004 completes two synthetic 4B LoRA gradients on one L4 | Full SFT memory and GPU sharding untested |
| Distributed SFT | Two-rank CPU Gloo DDP update with unused trainable visual branch, disjoint samples, exact pause/resume and forced worker failure pass; text weights update and unused visual weights stay fixed | DDP does not shard memory; actual Qwen3.5 text gradient groups, GPU and large-model path untested |
| 4B compatibility pilot | Private, offline, one-L4 LoRA package with existing Dataset v2 model/wheel digests and two-step atomic ledger; pilots 001–003 preserve separate failed identities; Decisions 0024–0025 are consumed | Pilot 004 verifies exact material, official mount, four visible L4s, offline `torchao` removal, 4B load, two synthetic PEFT steps using 16 tokens, gradient groups, adapter reset and 9,419 MiB peak allocation; zero generations; no ARC task or full-method measurement |
| 4B compact complete pilot | Private synthetic one-L4 source conversion, task-local LoRA, bounded DFS, likelihood ranking and truth-free result | Distinct pilot 003 verifies four-shard 4B save/reload, two task-local steps, four generations, two of four tests with complete grids, and independent model/result digests; no ARC accuracy or full-method measurement |
| SDG | Saved/fake stage provider, stable stage identity, failed/duplicate call accounting and fail-closed caller claims pass | Docker launcher flags tested; daemon absent, no real sandbox integration or teacher call |
| TRM | Pinned source hash binding, inference-only checkpoint/test entry and CPU fake-source call-order harness, bounded invocation fixture, ten-attempt parser and truth-free raw-tensor normalization pass | `argdantic`, `numba`, `hydra` and model checkpoint missing; actual upstream CUDA inference remains unverified |

The table above supersedes earlier implementation-status cells for this
continuation. The reviewed historical version remains described above.
