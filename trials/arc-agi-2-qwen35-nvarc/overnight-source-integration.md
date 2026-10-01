# Overnight source integration

Authority is [Decision 0053](../../docs/decisions/0053-nvarc-overnight-development-goal.md).
The development Goal ends on substantial completion or the one-shot 07:00
Taipei timer on 2026-10-02. Previous run identities and results remain frozen.

## Packing and accumulation evidence

`arc_nvarc_packing` adapts NeMo-RL v0.3.0's MFFD placement under its retained
Apache-2.0 license. The exact primary reference is commit
`b1c86a816c5e2b4ca41ece193624a38dc62e6fdf`,
[algorithms.py](https://github.com/NVIDIA/NeMo-RL/blob/b1c86a816c5e2b4ca41ece193624a38dc62e6fdf/nemo_rl/data/packing/algorithms.py).
Its SHA-256 is `4b946e5913b50ae96891138b508352a1ce75a4e1bfe14aea14a31179ced64011`.
The original NVARC run's precise NeMo version remains unknown.

Logical packs round whole sequences to 64, cap each bin at 256,000 tokens,
retain dual-parent/exposure lineage, reset positions, and mask padding. Execution
uses a fresh hybrid attention/DeltaNet state for every segment. It establishes
isolation and loss semantics, not fused FlashAttention/NeMo throughput parity.
503 input sets match the separately loaded pinned placement implementation.
Real tiny Qwen3.5 independent-sequence logits, token-mean loss and all gradients
match; altering a prior sample cannot affect a later one. An unsafe flat
concatenation differs, so this check exercises the recurrent boundary.

FSDP CPU offload replaces reduced gradients; ordinary backward accumulation
does not suffice. This implementation adds reduced FP32 CPU shards and copies
the result into the last FSDP gradient views, with a globally supervised-token
mean. Each rank performs an equal number of collectives; zero-loss dummy slots
on shorter ranks do not count as training tokens. It does not retain full GPU
gradients with `no_sync`. The constraint is documented in the primary
[PyTorch FSDP reference](https://docs.pytorch.org/docs/2.10/fsdp.html).

Two real CPU FSDP workers, unequal rank sample counts and two optimizer steps
match an independent all-sample oracle, including AdamW moments. The reusable
SFT path also verifies uninterrupted versus process-restarted execution with
bitwise-equal model/optimizer tensors, scheduler, RNG and source cursor. Its
checkpoint consolidation and export/reload verify every tensor's exact bytes.
An initial Windows full-state CPU-offload gather crashed natively; the proof
uses the same sharded DCP path as the runtime, followed by independent local
consolidation. Failed diagnostics remain retained, and are not counted as passes.

The lazy original-corpus stream follows the complete source concatenation and
seed-24 shuffle, memory maps Arrow lineage, preserves whole long sequences and
keeps validation separate. The fixture retains a 17,000-token sample and both
exposed parents without filtering or truncation.

| Check | Outcome | Local log SHA-256 |
|---|---|---|
| Stream, packing, differential isolation | 6 passed / 11.757 s | `63aac0a0851aefad7cd8c6f1081c17735229edcc2c71c469126902c0edbbd045` |
| Independent distributed accumulation | 1 passed / 38.344 s | `113ab2ec960ac652d589aa3611f6795f9350f8e151026ec57275f65fb8eee65d` |
| Resume, cursor, RNG, exact export | 1 passed / 101.087 s | `c5f56c448aa6cfb573e87918705e1222dd07deb35aedbbdab6402399ac3dd4d8` |
| Required repository validation | 314 passed / 317.310 s | `72b482e2899d3a67732f2dd2e2ae3ff3c7443dcf0c60840eb41ab7ec480b8c41` |

Logs and the exact reference live under the isolated local
`.irisx/nvarc-original/materials/nemo-packing-reference-20261002/` namespace.

## Four-L4 runtime

The distinct integration packages repeat
eight frozen whole published records for two accumulated steps: all six source
families and the 11,196-token maximum are represented. Global batch is eight
for this integration probe. It is not the source global-256 epoch, 12,716-step
training, original Qwen3 checkpoint, or an ARC quality evaluation.

No new runtime outcome is asserted before an exact submission receipt and
digest-bound terminal result. The next runtime must also retain its HF export;
optimizer checkpoints remain explicitly ephemeral Kaggle scratch.

`nvarc-overnight-sft-001`'s one SaveKernel received HTTP 400 without a version
receipt. A single recent-own-kernel listing found 57 kernels and no matching
001 entry. Its failed push, exact request and package are retained; no runtime
work or provider error cause is inferred. The original uncompressed notebook
was 1,346,529 bytes, compared with 972,714 bytes for the previous accepted
preflight. The replacement compresses and bounds payload expansion while
retaining the same exact raw data and model workload.

`nvarc-overnight-sft-002`'s compressed 642,849-byte notebook passed offline
verification and its single private SAVE_AND_RUN_ALL was accepted as version 1,
kernel ID `136684509`, at `2026-10-01T17:02:28.456561` UTC.
[Kaggle notebook](https://www.kaggle.com/code/danielwuu/nvarc-overnight-sft-002).
Compression acceptance does not prove the earlier provider error's cause.
Plan digest is `sha256:96ac918d32ce722959f13b4ca2330dd85fed06596ca9c8760d604749df8afd26`;
runtime identity is `sha256:eb7abf3529a8888e831bd6b0f0f943c3427dc202f8584944ab4613c38bef99d3`.
The ledger and exact package live under
`.irisx/nvarc-original/runs/nvarc-overnight-sft-002/`.
The terminal provider status is COMPLETE. Its sole terminal retrieval retained
the exact closed diagnostic archive and all four HF shards.
The runtime completed two global-batch-eight accumulated steps, 94,156 input
and 48,670 supervised tokens, sixteen whole forwards and an exact process
restart at step one. Its FP32 saved/consolidated fingerprints agree within the
bound tolerance, and all 724 exported tensors reloaded identically onsite.
Material digest is `sha256:2f367df415813dbb82b96192750f334f2a91e84c9d6812daa92e7a2a5bd04ca7`.
The complete notebook took 2,454.945 seconds; actual rank optimizer steps took
128.101–140.096 seconds. Independent local safetensors reading verifies every
one of the 724 tensor byte digests against the retained export inventory.
Archive SHA-256 is `d2c98e971d0d406430a0c5db178b81d2ddd2de622336536a312f95ec50f18d97`;
independent verification SHA-256 is
`8052eb7a8662cf9159a05bca1c507c159e10e4ec7dafbec4a5eab25cbf7a5901`.
The original-scale SFT and original Qwen3/NeMo claims remain false.

The distinct `nvarc-overnight-sft-003` is accepted as private version 1,
kernel ID `136689146`, with a 10,800-second finite limit. It freezes the actual
first 512 seed-24 shuffle records: all six sources, dual-parent exposure retained,
zero filtered/truncated records, 1,770,662 input and 764,883 supervised tokens.
The two global-batch-256 steps use 64 reduced CPU-shard microsteps per rank.
Plan digest is `sha256:c5196971143abe73774581b17e5f7ac11b239d686520cf32e4a7f5d3bdb35dbb`;
identity is `sha256:95bb2b4ddf8151cf4cb7005276c4872b25e650596eda4df72986cb44f9773884`.
[Kaggle notebook](https://www.kaggle.com/code/danielwuu/nvarc-overnight-sft-003).
This is the source epoch's exact prefix, not a completed original-scale epoch.
It completed; all 724 exported tensor digests are independently verified
locally. See the final source-prefix report below.

## Complete TTT memory path

An opt-in nonreentrant activation-checkpoint setting now covers the full
source 128-view rank-256 epoch. A real hybrid tiny model returns bitwise-equal
losses, adapter weights and learning-rate schedules with/without checkpointing;
both reset to the exact initial adapter. The one differential test passed in
21.915 seconds (log SHA-256
`52828308cde6d52452f3643c84c110b658368e5587fc1f832d63f0160aa7fd80`).
The complete trained tiny export independently reconciles all 128 optimizer
events, sixteen source DFS calls, public-demo verifier probes kept outside the
candidate pool, exact adapter reset and rejection of an altered forward ledger.
That test passed in 13.996 seconds (log SHA-256
`4ea22f61ae50bb17e22353e9d8c411a8a3e24cb03c6411ba8ad7197665f635da`).

`nvarc-overnight-ttt-001` was accepted as private version 1, kernel ID
`136689709`. It uses the immutable 002 export via a kernel output mount; every
mounted weight must pass exact material verification before a model loads.
The local download need not gate this independent onsite material check, and
the plan explicitly says local export bytes were not yet verified at staging.
It binds one repeatedly exposed public tuning parent, all 128 source views,
rank 256/alpha 32, source cosine scheduling, sixteen source DFS calls and up to
34 eight-view verifications. Two public-demo verifier probes can exercise
ranking even if the decoder produces no candidates, and are never model
answers. It adds no palette/shape grammar or probability-floor repair.
Plan digest is `sha256:6a9dd999b59520b07003878c9305ca5f2cda04d55d909a2a90cc2d4f9b952500`.
[Kaggle notebook](https://www.kaggle.com/code/danielwuu/nvarc-overnight-ttt-001).
Its sole terminal retrieval verified failure at `exact-export-mount` after
8.110 seconds, before dependency/model work. Four distinct L4s were present;
the template omitted the owner-qualified `/kaggle/input/notebooks/` root.
Archive SHA-256 is `ee4590328b46169854f639913c5ddcdb3ebe628a999b250f90bd37f7a27d6ce9`.
The failed package and retrieval are frozen.

The distinct `nvarc-overnight-ttt-002` adds that exact notebook root and a
bounded mount inventory diagnostic, keeping the same scientific workload and
material bytes. It was accepted as private version 1, kernel ID `136690164`.
Plan digest is `sha256:9fcf49abeeece59eac5bb503240bc01d23dac3d64ba7e0860f02017f222fbc69`.
[Kaggle notebook](https://www.kaggle.com/code/danielwuu/nvarc-overnight-ttt-002).
Its terminal status is COMPLETE. The sole terminal retrieval and independent
verification reconcile 128 optimizer events, 13,824 source training tokens,
sixteen DFS calls, five unique model candidates and five candidate verifications.
Two separately labelled public-demo probes remain outside that candidate pool.
Eight-view verification and search reserved 874 total outer model forwards;
the adapter reset is exact. Rank-256 LoRA has 520,757,248 trainable parameters.
Training peak CUDA allocated/reserved was 18,535,515,648 / 19,266,535,424 bytes;
the complete notebook took 715.065 seconds. Runtime mount diagnostics confirm
the exact owner-qualified notebook export root. No candidate correctness,
full-scale SFT or original Qwen3/Unsloth parity is asserted.
Archive SHA-256 is `fdddaf6b06bb280343ddcb4b4536196bd772650944c9533e3da1ac3d2d38a5fd`;
independent verification SHA-256 is
`d350a62fbe3fd80c53a1d20459749cff6daa760eca6b75467093848a736da002`.

## SDG/TRM and milestone validation

The strict ML profile passed 45 tests in 329.491 seconds. It includes actual
WSL user/mount/PID/network namespace isolation, all ten saved-response SDG
stages, source preprocessing and real tiny TRM train/reload/TTT/joint Qwen
ranking. Log SHA-256 is
`dc67fc69d434b65b7c28e5279352678b30ca01027923a197c3314171fa6d1e21`.
These are engineering checks, not original teacher yield or full-size TRM proof.

Published SDG artifact version 1 has a closed provider inventory of 192
Parquet members and 47,514,077,184 uncompressed bytes. The 42,008,423,274-byte
compressed archive exceeded its first 5,400-second transport bound. Its
16,879,976,448 retained bytes and official ETag/size resume marker are frozen;
a distinct material identity copies both and uses the official validator-bound
range downloader, with a 10,800-second bound. Full archive SHA/CRC/member
verification is now complete: 192 closed members, exact sizes, CRC and every
member SHA verify. Archive SHA-256 is
`43c4df0b9da13f38f0da2071a4e94299e94f15036a5f86693d3e377aa6cee8ab`;
inventory SHA-256 is
`97239ee8456229a8bd393ceddcc04495b6634ea40b24d20ad175fb794d35d588`.
No program executes or full archive extraction occurs during acquisition.
Separate metadata profiling also completed in 430.141 seconds, rechecking
all 192 raw member digests while decoding only teacher/parent columns.
It covers 3,263 summaries, 266,593 mixtures, 193,793 input programs and
2,050,249 output programs, with all 265,492 unique parent sets and exposure
tags retained. Observed summaries include Sonnet 4 (716), Sonnet 4.5 (1,091),
OSS-120B/high (1,427) and human-authored metadata (29); mix/input/output stages
retain their observed OSS high/medium and Sonnet 4 profiles. These identities
are original row metadata, not regenerated teacher calls. In particular,
932,411 output records have an evaluation ancestor and 463,393 have protected
ancestry; categories overlap and no row is filtered. All-member program
semantics remain unverified. This audit has zero program/model/teacher calls,
zero accepted pairs and no score. Parent-lineage/member-metadata SHA-256 is
`b54b584e0b9ecd34db506889fb2308add6dbf61dc90dd89d4c6497c0422b541a` /
`d842b6bb1c4f94bdfb7b08f4994b09a9d4e6f5c9f72febe742e083bd047cfa03`.
Complete profile SHA-256 is
`b819e72b8904b6a63c5cd9c15a13f6103221d7bc70eee107026924edf48d0e1b`.

Four exact first Parquet shards were separately retained and SHA-verified for
bounded replay: summaries, mixtures, inputs and outputs (280,415,271 bytes).
The fixed first provider-ordered complete twenty-output group joins both
parents `00576224` and `84db8fc4`, without searching for a favorable result.
The retained summary rows use `claude-sonnet-4-20250514`; its mix uses the same
teacher, and input/output logic uses `gpt-oss-120b / medium`. The whole summary
first shard also contains `gpt-oss-120b / high`. Teacher identities are observed
row metadata, not fresh provider calls.

Real WSL NumPy execution uses the existing read-only `/usr`, namespace,
chroot and process/memory/time limits; fixed BLAS paths avoid `/etc/alternatives`
without exposing `/etc`. Source-recognized input tests run inside that same
sandbox, and output functions receive NumPy arrays as the original script does.
Local replay 001 stopped after 635 invocations on tuple-to-canonical-JSON I/O.
Replay 002 retained all 635 invocation results, then stopped on Windows' default
text encoding. Both are frozen (1,270 actual program invocations in total).
Recovery 003 retained a packaging basename/reused-rejection reporting error;
recovery 004 rebuilds only the UTF-8/canonical envelope from exact 002 results,
with **zero new program or teacher calls**. Twenty-seven actual program
rejections remain visible; 578/600 output attempts are valid and nonidentity.
The unchanged source 8-vote/12-pair/4-consistent-solution filter accepts 30
pairs: every input has 19–20 agreeing outputs and nineteen solution IDs agree
across all thirty inputs. Independent Counter/intersection reconciliation
verifies that exact selection and the closed artifacts. Source augmentation
also completes. Both parent/exposure tags (`protected-parent-or-visible-family`,
`pilot-ancestor`) remain on the new data; it is not clean holdout evidence.
Independent verification SHA-256 is
`838c8a21f3948172bbaa989f8d4fb5cbc9091f26ee311fffed00f62fa13e53dc`.

The source-linked public TRM Dataset `cpmpml/arc-prize-trm-031` version 1
contains seven 2,159,719,349-byte checkpoints. The exact source-named
`step_220708` is retained at SHA-256
`dbf771737d9799b84faf009c24c5376831f095d2cfd66debbe9a505a445bfc31`.
The full-width source model (512 hidden, 8 heads, 2 layers, H4/L4) strictly loads
all fifteen state tensors, with the source mean reset from 1,041,208×512 puzzle
embeddings to 1×512 and zero dropped keys. Distinct local CPU run 001 completes
one public-demo TTT step, changes thirteen state tensors, advances ten ACT
forwards, returns one legal 10×10 candidate and resets exactly, in 33.344 seconds.
This is float32 compatibility evidence, not original BF16 numerics, ten separate
attempts, full training, 2,000-epoch TTT or ARC correctness. Independent
verification SHA-256 is
`ec12fe8ebb1d539c8bbf6c938165f4215914306c635f1e09dd25b9b2049a9db6`.
The exact v18 source request with version label 18 returned HTTP 404. A distinct
request using the official CLI's `/18` slug convention returned HTTP 403.
Retained v21 source is not silently substituted for v18 parity.

Required repository validation passed 314 tests in 267.771 seconds for this
milestone. Log SHA-256 is
`bf5441a7801db8633f43d0191855b1f9a0f78184bcafe2542e74bb07e2e5fe06`.

The later strict ML profile passed 46 tests in 394.148 seconds (SHA-256
`e095c36246ee7ea2ccd1fb2fcec427ef25191fd3353d5f326db890b74867b4c9`),
including actual NumPy namespace calls and strict published TRM embedding/state
loading. One additional independent fixture oracle passes in 4.233 seconds,
checking Unicode I/O, the thirty-pair filter oracle, zero-execution recovery,
preservation of the original artifacts and rejection of altered program/shard
bytes. Its log SHA-256 is
`28b15b6b9be36d141433c5ec152e5aa6057ac687e49edce4e4f072facf823616`;
the current ML profile contains all 47 tests.

A later system-Python repository check retained a transient Windows replacement
denial and a short process/log deadline failure under concurrent I/O. Both
targeted rechecks pass. Atomic replacement now retries only Windows error
5/32/33 up to five attempts/150 ms total backoff, retains the previous complete
ledger during a lock, and still raises ordinary or persistent permission errors.
Its independent fault-injection regression passes. The required full repository
recheck using the ML runtime passed 315 tests in 253.887 seconds; log SHA-256 is
`255afcd09b4f0ac064d69913b251467290bef6634119af0ea5bc3237d42ea29e`.
The preceding failed log remains retained rather than counted as a pass.

The original TRM evaluation Dataset `cpmpml/arc-prize-trm-evaluation-data/1`
is retained only in `evaluator-materials`: all fourteen files (124,574,189 raw
bytes), archive/member SHA-256 and CRC verify. Numeric NPY headers and dataset
metadata were read without loading array payloads. Its 8,380,437-byte archive
SHA-256 is `735150bcc19f2e9f06b1ab30a2190b0bb969073121e763a62c63ba8104408d42`.
It contains evaluation labels and is forbidden from solver staging.
The original training Dataset version 1 has sixteen files totaling
39,447,934,651 raw bytes; its provider ZIP is 2,218,651,916 bytes. Acquisition
001 stopped before download at an undersized raw-byte gate. Distinct 002
separately caps compressed bytes at 4 GiB and raw inventory at 48 GiB while
reserving the outstanding SDG transfer and model storage. All sixteen members,
numeric headers, CRC and member SHA-256 now verify. Archive SHA-256 is
`2f28e5bb82f50df9938bf0f817b8eeda4744e36c85cd68eb5a91614ff4444d4c`.
Neither material acquisition trains, generates or scores.

The training audit verifies all 1,041,208 identifiers, puzzle/example/group
index axes and 4,073 groups: 1,000 public ARC training, 120 public ARC evaluation,
160 ConceptARC and 2,793 published SDG mixtures. Both parents and all exposure
tags remain: 2,913 groups have an evaluation ancestor and 593 have protected
ancestry. No group is filtered. The 1,041,207 augmented puzzles index 21,845,065
examples, and the identifier count matches the checkpoint embedding exactly.
Actual source `_collate_batch` on eight training-only rows matches an independent
PAD-to-ignore/identifier oracle (7,200 input / 792 supervised tokens).
No evaluation member was read; the full 39 GB arrays stay in the verified ZIP
to preserve the download/model disk reserve. Audit SHA-256 is
`d4909980423a99189634f3140519242beb80563a471ab01d063c9098057d3457`.

## Joint model integration continuation

Source `solve_task` now includes TRM views before Qwen task reset. New unique
grids receive the same adapted Qwen eight-view NLL; duplicate grids share their
score while retaining every model vote. Unchanged source `getter_kgmon` ranks
the combined pool. Public-demo probes remain separate. An independent active
state/vote/cache oracle and bitwise comparison with pinned TRM optimizers pass.
The source bundle binds five unchanged TRM model/loss files and its license at
revision `e7b68717f0a6c4cbb4ce6fbef787b14f42083bd9`. Exact AdamAtan2 0.2.4
wheel SHA-256 is `404d1c5ba331633a6f6e395891ed28cb13a7cf622ac824ba9913b8286ad97e99`.

TRM uses a distinct L4, one demo update and eight D4 views / at most eighty ACT
forwards. Qwen retains complete 128-view TTT, sixteen DFS calls and at most 42
total verifications. Reduced TRM work is not original 2,000-epoch TTT/v18 parity.
Inert TTT 003 failed offline transport ordering without a submission. TTT 004's
sole private version and retrieval are consumed: it loaded TRM, then stopped
before optimizer/model forward on a non-leaf sparse gradient buffer created by
CPU-to-GPU `.to`. Archive SHA-256 is
`cf8d725fd949bdc52b7cc186185ae22c7a8b3020a7535fab713ead10cdca0d62`.
Repair constructs directly on the final device, as upstream does. Actual CPU
dtype transfer reproduces the failure, and the repaired source optimizer
matches every control tensor. Distinct private TTT 005 version
1, kernel `136697897`, plan
`sha256:fc5e7de45510e5a3de3cd810dd8e0ac4dfb82a853a6248893a2df1b1874794a1`;
failed during its first ACT training forward: source carry factories omitted
the device and created CPU state for a CUDA batch. It completed no optimizer
step; its partial forward is retained rather than claimed absent. One retrieval
and independent failure verification are consumed. Carry initialization now
uses the batch's device context, matching upstream's calling convention.
A real default-meta versus CPU-batch regression reproduces the factory mismatch
and verifies every repaired carry tensor, loss, optimizer and reset.

Distinct TTT 006 version 1, kernel `136699426`, completed on four distinct L4s.
Plan digest is `sha256:632dd89ec115f1dd6e2b9c72bb14313ec1fb5d9e8821ec8019325c0e45dc2a5e`.
Its sole terminal retrieval and independent reconstruction verify 128 Qwen
steps / 13,824 tokens, sixteen DFS calls, one TRM demo update, eight D4 views
and eighty ACT forwards. All eight TRM model votes enter the same adapted
Qwen state before reset. The combined pool has eight unique grids, eight
candidate verifications and two selected attempts; two public-demo probes
remain separate. There are 880 Qwen outer forwards, exact reset and no
correctness score. Notebook time is 789.174 seconds. Archive SHA-256 is
`6dd2a519e63d2de62c9e0f2a12858f4f49ff85a101468ab1abcba94ec8b0763e`;
independent verification SHA-256 is
`181dc2f21ecb065854125212f67b07cb5f733fa48d39659451baa6bfd1e6dd98`.
[Kaggle notebook](https://www.kaggle.com/code/danielwuu/nvarc-overnight-ttt-006).

The complete short-task epoch's longest view is only 108 tokens. Distinct
resource check TTT 007 is accepted as private version 1, kernel `136702996`,
plan `sha256:32f296bbf268430370f87844c5416a5012a9a3e8e807611bf48a22163c28402b`.
It selects by public-demo size alone, retaining the chosen `f9d67f8b` parent's
protected/locked-holdout ancestry. No test answer enters the outbound and no
score is computed. Eight reduced source D4 views total 59,712 input tokens,
with a 7,464-token maximum; rank/alpha/checkpointing remain source-profile.
One color repeat and one warmup step are explicitly reduced resource settings,
not a verified original 128-view epoch. No generation or verifier call is
permitted. Its sole retrieval verifies CUDA OOM during the second forward:
one optimizer step / 7,464 tokens completed, two forwards were reserved.
Archive SHA-256 is `2a1d3c9c0c48cc8b8ba517130e625ad8813bd2138837e2849cead7941c103afe`.
The actual tiny trained-export resource path, independent schedule/token/event
reader, altered-ledger rejection and exact reset pass in the extended
integration test (16.472 seconds, SHA-256
`c2062e6605a11d277e8cecd01f172ed6ecf1be829d6e6368e22c0b8f47e0d43e`).

Global-batch-256 SFT 003 reports completion: two steps, cursor 512, 1,770,662
input / 764,883 supervised tokens, restart and export/reload. Notebook wall time
was 5,590.946 seconds; its resumed step took 1,637.64–1,637.66 seconds per rank.
The segmented CPU-offload backend proves resource/semantics feasibility, not
practical whole-SFT throughput. Sole export transfer and independent local
reading verify every one of the 724 tensors. Material digest is
`sha256:e701de11e9e58c52c60b35ab50af0c7cbca61a3d7f670cb56e7b55a07660e703`;
archive SHA-256 is `0d39432c767d7963e87f3d17c485cc72d43bf8468b78f650bd081b2c4a28776c`;
independent verification SHA-256 is
`34684dae0a36c4f161954f888369783d8beeb1a8617088d87e38ecaafda8925d`.

All 49 strict ML tests pass in 308.211 seconds; log SHA-256 is
`1fd8d3c61c5bd85f2579fb39897dd155607a1960e96687ae99a99f494c2b3723`.
The later leaf repair's two regressions pass in 2.950 seconds, SHA-256
`3667b0ada31ebbf43d3430da9f7f208c3b953a79e7dbea1999819410e4966516`.
Required repository validation passes 315 tests in 264.130 seconds, SHA-256
`5c82d5c46569f79ac0a8055575a062270c8f4cfc181c65598af29831d25d2cd3`.

Distinct TTT 008 retains the long task/eight-view workload using optional CPU
AdamW mirrors/moments. Tied embedding/head adapter storage remains shared:
independent clones failed the real differential and were never submitted.
The corrected path matches all 128 CPU source-epoch losses, schedules and
adapter tensors bitwise, with exact reset (27.255 seconds, SHA-256
`21ea2980309845e6d032bd5f25175625a1f27895268caf92a43ef21a85d36935`).
This does not infer CPU/CUDA kernel parity. Private version 1 is accepted,
kernel `136704162`, plan
`sha256:91ea08995eeae2711c1347b75f39c4381e96c9ed587cb0febd4792565d56f713`;
The sole terminal retrieval and independent reader verify all eight optimizer
events / 59,712 tokens, max 7,464, finite gradients, exact reset and zero
generation/verification. Notebook time is 618.370 seconds; CUDA training peak
allocated/reserved is 18,140,578,304 / 18,826,133,504 bytes. Archive SHA-256 is
`83cb1d8ad21b79cdd8c9a368da1d91e5bd57f878686a11c9a0326d9c953946f6`;
independent proof SHA-256 is
`43690b73c2367cb1e021ceec80725d6da418443c4a2e05efcc0b804081d47732`.
It does not establish a full 128-view long-task epoch.

## Persistent TRM pretraining path

`arc_nvarc_trm_training` retains source loss/global-batch normalization,
Sparse SignSGD + AdamAtan2, source warmup, persistent ACT carry and unchanged
EMAHelper. Resume restores model, optimizers, carry, EMA and CPU/CUDA RNG.
A real tiny-model oracle executes the unchanged pinned `train_batch` with
only CUDA transfer made identity for CPU replay; all model/optimizer/carry/EMA
tensors and RNG match bitwise. A separately reconstructed step-one checkpoint
produces the same second step. Altered identities and exported checkpoint
bytes are rejected. Actual EMA export loads and verifies every tensor.
Its one test passes in 3.044 seconds, SHA-256
`e0ff41d0b8008e3dad0b3157ad88d17ed4aeaf44b16d6e0b42baa7c9781e9a9d`.
Training function file SHA-256 is
`59dfb2523507046af3126790c473f371111f7b7ded77233266a71ea13d3104ac`;
EMA source SHA-256 is
`41f92b2ec89a53ebcd69ced5903ccc4519a199ec2208d9694dd49ec398379ece`.

Full-width private TRM 001 is accepted as version 1, kernel `136704165`, plan
`sha256:187a8bfaebfb2cbaf770aaa913be7f2bc8e1ee6e75fcb1ac88e6779e7790f412`.
It initializes all 1,041,208×512 puzzle embeddings, H3/L4 training model,
one L4/global batch eight, two steps, process restart, EMA export/reload,
zero generations and a finite 2,700-second limit. The first eight verified
training-array rows belong to public training parent `8b28cd80`; no evaluation
member is staged. Repeating this prefix is an explicit reduced sample policy,
not the original shuffled/global-3072/10,000-epoch run. It completed two actual
steps, 14,400 input / 1,584 supervised tokens, exact process-restarted
model/optimizer/carry/EMA/RNG and onsite EMA export/reload. Notebook time was
146.543 seconds and CUDA peak allocation was 4,244,938,240 bytes. Its sole
retrieval retains the 2,159,717,494-byte EMA checkpoint. All fifteen actual
tensor digests verify independently, including the exact source EMA-versus-
ordinary-buffer choice from the final checkpoint inventory. Checkpoint optimizer
bytes remain explicitly ephemeral. EMA checkpoint SHA-256 is
`0f78afda8d59be6089e20b55e3aad49582cc8ed13a2e735ee9ac3fe32bbe8ea8`;
material digest is `sha256:52ede3821bb6b6c418d2ab99bab4c0023f68201eede8f04b5277ece1beeeef07`;
archive SHA-256 is `03badb20b327e5fa95ef1566230d03683e2144ea9fa072fdb6a2269af2e6f970`;
independent proof SHA-256 is
`de6e5508a42964569cbbef69579e582210dfbb2b7e44073a63ac18bad718f7aa`.

The stronger source oracle also checks a batch of two with unequal label counts:
normalization, sparse duplicated-ID handling, persistent carry, schedule and EMA
still match exactly, including resumed second-step/export (5.788 seconds,
SHA-256 `7e4e94d54465803b2b48de31c35094593597040eb48567b2e1779799a5f27e88`).
The unwrapped source EMA export is accepted only by explicit prefix mode;
published compiler-prefixed loading retains its previous strict default.
Actual mean reset/all closed state tensors and shared-state candidate oracle
pass three tests in 3.180 seconds, SHA-256
`c69b61847efee9f9679808b33fdf47b493d169183c13295756c605265bb1c40b`.

Joint trained-export integration uses SFT 003 and TRM 001, each immutable private
version 1, with both mounted exports independently byte-checked before loading.
Inert staging 009 retained an old published-only plan-gate rejection and made
no provider call. Distinct 010 is accepted as private version 1, kernel
`136705403`, plan
`sha256:d3bf79a8b2bd62c757dd4362b2acb13a3bd060ce664cd86356240b7993152426`.
It retains the exact 128-step Qwen/16-DFS plus one TRM update/eight-view workload,
same adapted Qwen ranking/reset, four-L4 gate, finite 4,500 seconds and USD 0.
Its runtime remains pending. Latest five focused source/export/TTT/joint tests
pass in 26.419 seconds, SHA-256
`329c25e33ebfb6335939e685adcf43f3c75149ca98cfdbace95b880dd19d72d3`.

Required repository validation at milestone 006 passed 315 tests in 243.661
seconds, SHA-256 `9569ae852f8d28b952ccb970fb5e910b6550c5c7a7a7001eb42e4ecb2d12a2f1`.
It precedes the later CPU optimizer/TRM trainer additions; their targeted
checks pass. Full ML recheck passes all fifty tests in 304.273 seconds,
SHA-256 `ef17ec36a15b1488a9d5b1637965043d78d53732561e3a63fd91169817a6af8c`.
Repository milestone 007 passes 315 tests in 253.016 seconds, SHA-256
`f9734e3416b963acd76770fba1da427a51a6778527253ddb09910098c5b2144b`.
Later source-EMA inference bridge changes have the five focused checks above;
final repository verification follows those changes.
