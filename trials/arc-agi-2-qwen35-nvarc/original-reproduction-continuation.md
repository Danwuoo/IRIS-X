# Original NVARC reproduction continuation

Authority: [Decision 0054](../../docs/decisions/0054-nvarc-original-reproduction-continuation.md).
New owner direction follows the completed overnight Goal, without a new timer,
Goal or deadline. Start: main `e325fea`. Previous identities stay frozen.

## Original-family material and version audit

The pinned NVARC `run_sft_4b.sh`, applied over `sft_mg.yaml`, selects
`Qwen3-4B-Thinking-2507-16t`, seed 24, global batch 256, TP8/CP2 on four
eight-GPU nodes, 12,716 steps, BF16, MFFD 256,000-token bins rounded to 64,
source Adam schedule and 200-step checkpoint interval. The YAML alone has
different defaults; the audit resolves the real shell overrides. The current
Qwen3.5 port remains distinct.

The actual acquired original-family base is
[`Qwen/Qwen3-4B-Thinking-2507`](https://huggingface.co/Qwen/Qwen3-4B-Thinking-2507/tree/768f209d9ea81521153ed38c47d515654e938aea),
fixed at `768f209d9ea81521153ed38c47d515654e938aea`. All thirteen files,
8,060,920,921 bytes, match Hub LFS SHA-256 or Git blob identities. The source
does not state the historical base commit, so family/version compatibility is
established but exact historical base-commit identity remains unknown.

The sorted 16-row mapping is
`[15,16,17,18,19,20,21,22,23,24,198,872,77091,151643,151644,151645]`.
The source WordLevel tokenizer JSON and other tokenizer config bytes are copied
unchanged. The 36-layer full-attention, tied-embedding base is cut to sixteen
rows; all 398 actual tensors are independently compared byte for byte against
their raw source tensors or selected rows. Compact inventory digest:
`sha256:6c93bb738c9203ef19cc02deeac67c6a659e3128807f5c5d02a74104a479d430`.
This is a compact **base**, not the published ARC-SFT weights or a completed SFT.

An actual compatibility difference is retained: Transformers 5.8.1
`AutoTokenizer` resolves the source `Qwen2Tokenizer` configuration such that
standalone `user` and `assistant` encode to empty lists. The source WordLevel
JSON interpreter produces rows 11 and 12 correctly. This path uses the explicit
JSON interpreter and checks a complete chat sequence; it does not silently
change the original tokenizer files. Two failed offline conversion-gate logs
remain retained; they produced no model output before the corrected interpreter.

The exact notebook v10 binds Python 3.11.13, Kaggle Docker image 31090, model
instance version 627758, model path `qwen3_4b_grids15_sft139/transformers/bfloat16/1`
and Unsloth code. It does not lock the Unsloth wheels. The NVARC source does not
lock NeMo-RL or Megatron revisions. These remain `null` in the machine audit;
the previous NeMo-RL v0.3.0 MFFD placement reference is not relabelled as the
historical training environment. Audit SHA-256:
`5c7335b01175945d17ecbf659ef807aa8b4d1731cdcf50518f96a0bf6f9b25d7`.

Materials, exact acquisition/conversion/independent verification, Dataset ledger
and logs are isolated under
`.irisx/nvarc-original/materials/qwen3-thinking-2507-20261002-001/`.
The sole private Dataset creation was accepted as
[`danielwuu/irisx-nvarc-original-qwen3-001`](https://www.kaggle.com/datasets/danielwuu/irisx-nvarc-original-qwen3-001),
version 1, and its ready state was observed. The initial local parser rejected
the provider's capitalized `Ok` despite the successful receipt. The corrected
receipt interpretation and two read-only checks retain that original receipt;
no second create occurred. No paid or public material operation occurs.

Actual BF16 CPU forward comparison separately loads the full raw base and the
16-row cut. For one fixed twelve-token chat, every selected base logit equals
the compact logit bitwise (maximum absolute difference 0.0), with tied weights.
This reserves exactly two forwards/24 input tokens, no optimizer or generation,
and takes 97.109 seconds under Torch 2.12.1+cpu. Its complete numeric vectors
and cost ledger are retained in `forward-verification.json` under that material
directory. This checks this cut and input, not historical CUDA/backend parity.

## Exact published original ARC-SFT checkpoint

The source Qwen notebook's published
[`sorokin/qwen3_4b_grids15_sft139/Transformers/bfloat16/1`](https://www.kaggle.com/models/sorokin/qwen3_4b_grids15_sft139/Transformers/bfloat16/1)
is now acquired. Official metadata confirms model instance `472720`, exact
version ID `627758`, version 1, and Apache 2.0. All ten files total
7,267,271,302 bytes and have retained local SHA-256 identities. Independent
re-reading verifies the closed inventory and all 399 finite BF16 tensors,
including separate `[16,2560]` embedding and output-head tensors. Material
digest: `sha256:27de51ef22658a0cce3a9fc04fac8fc456165645e2665a82b215f72e20194b03`.
Files remain at `.irisx/nvarc-original/materials/qwen3-published-sft139-20261002-001/`.
This is the published original inference material; its training was not
reproduced here and its exposure is not established clean.

This checkpoint is **untied**, unlike the tied newly cut base. Its config
records Transformers 4.53.3, BOS 13, EOS 15 and the same sixteen-row WordLevel
chat sequence. Both distinctions are preserved rather than applying the
Qwen3.5 loader or forcing the base's tying assumption onto this checkpoint.

Two separately reserved BF16 CPU forwards use identical weights and the same
twelve-token source chat under Transformers 4.53.3 and 5.8.1. All 192 logits
match bitwise (maximum error 0.0). The two observations consume two forwards/
24 tokens in total and zero optimizer/generation calls. Torch is 2.12.1+cpu;
the local 4.53.3 environment also has Tokenizers 0.21.4 and Hub 0.35.3.
This narrow current-host comparison does not determine the historical CUDA,
Python 3.11.13, Unsloth or NeMo environment. Exact numeric result hashes are
`39b83ca33f6a903a735705ecc83ac638e4415d5738c99b398c4164e3113cb136` and
`233bc80bd05060363f54f233b8a0cff9b89a22f63726fb53e870fb74241ab2ec`.

The task-local adapter now explicitly selects every original Qwen3 attention/
MLP projection plus embedding/head, and requires its four actual gradient
groups without a nonexistent DeltaNet group. An untied tiny Qwen3 completes
all 128 source views at rank 2. Checkpointing with CPU Adam mirrors matches
every loss, rate and final adapter tensor bitwise against ordinary Adam;
reset is exact. This is a tiny-model differential, not an actual rank-256 4B
long-task epoch. Existing hybrid TTT/reset/export checks still pass.

## Packed execution

`arc_nvarc_qwen3_packing` supplies one model forward per logical pack with
reset positions and explicit sample boundaries. Rounded MFFD placement and
lineage remain intact; physical varlen tensors omit padding-only tokens.
Dense SDPA is a bounded quadratic reference, not a whole-SFT backend. Real tiny
Qwen3 logits, global token loss, every gradient, altered-prior-sample isolation
and an unsafe flat-concatenation negative control pass.

The source-step engine now has an opt-in Qwen3 packed path with unchanged
global token normalization, reduced FP32 CPU gradient accumulation, clipping
and Adam schedule. An independent all-sample oracle verifies both weights and
Adam moments. A two-rank Gloo control forces one versus three real packs and
two versus zero connected-zero dummy calls; all three collective slots match
the independent global-token update. This is CPU DDP evidence, not GPU FSDP
sharding or throughput. The first Windows launcher failed for missing libuv;
the final explicit Gloo launcher passes and retains the failed logs.
An additional real two-rank CPU FSDP test reconstructs the full original-Qwen3
weight and optimizer state after the unequal packed slots. All weights and
Adam moments match the independent global oracle. CPU sharding correctness
does not prove four-L4 memory or timing.

Physical execution can now split a retained logical MFFD bin only at whole
sample boundaries. Every original label, position, row digest, ordered parent,
exposure and logical segment order is retained. The 256,000-token logical bin
is not treated as a feasible four-L4 physical forward. A 32,768-input-token
ceiling is an explicit FSDP resource adaptation, not original TP8/CP2 parity.
The original first seed-24 global-256 batch has 916,739 input / 403,115
supervised tokens and a 10,338-token longest whole row, across all six source
families without filtering. Its four logical rank bins become 8/7/8/8 physical
forwards, with one connected-zero dummy on rank 1. This is layout evidence,
not measured memory or throughput. Profile SHA-256:
`c2c64b91fa756c2ebce0883136ca75894e4b2aeb24fca927eb9d62d1d61a6705`.
The first local profile failed report serialization after reading the wrong
source metadata field; its failure stays at `physical-packing-20261002-001`.
The corrected distinct complete profile is `physical-packing-20261002-002`.

The independent optimizer oracle also passes after physical splitting. A
two-rank CPU FSDP case retains one logical bin per rank but forces one versus
three physical calls; every weight and Adam moment matches the global oracle.
Distributed callers now explicitly pass the rank compute device because an
idle CPU-offloaded parameter shard does not identify the CUDA input device.
Owned/missing gradient-shard coverage is reported separately.

The new one-step Qwen3 full-gradient runner, parent template, stage tool and
closed input/cost reader are local development only. No such package has been
staged or submitted. Staging requires a successful independently read exact
material CUDA differential and its terminal archive binding; the queued
prerequisite is rejected before creating an execution package. The prospective
finite envelope is one optimizer step, 32 outer forwards including the dummy,
916,741 physical input tokens, 36 checkpointed layers, four L4s, FP32 CPU
parameter/gradient/Adam state, 4,500 notebook seconds, zero generations/teachers,
USD 0 and no exported checkpoint. It retains the acquired base's tying;
published SFT remains separately untied and historical NeMo tying is unknown.
The actual source step, memory and timing remain unobserved. Parent template
compilation and rehashed rank-reservation/Boolean attacks pass locally.

The CUDA candidate uses the public
[PyTorch 2.10 varlen FlashAttention API](https://docs.pytorch.org/docs/2.10/nn.attention.varlen.html),
explicit cumulative lengths and no dense attention mask. Its grouped-query
heads are explicitly repeated for the version's public signature. This is a
new precisely bound backend, not the historical NeMo or Unsloth backend.
CUDA success is not inferred from CPU tests.

`nvarc-original-qwen3-probe-001` was offline verified and accepted as private
`SAVE_AND_RUN_ALL` version 1, kernel `136726898`. Its receipt SHA-256 is
`384c77a39e2bd24d50ea3ab5e500437fd4fbfba756100855e49f5387ffd1c1ff`.
[Kaggle kernel](https://www.kaggle.com/code/danielwuu/nvarc-original-qwen3-probe-001).
It has thirteen
reserved outer-forward slots, 94,706 input tokens, two tiny backwards, eight
whole original shuffle-prefix records, three actual-weight passes, zero
optimizer steps, zero generations/teachers and a 1,800-second private offline
four-L4 session limit. Only one model worker is used. The competition mount is
for hardware entitlement and no competition file is read. Plan digest:
`sha256:6b9f28c04fef7d277ea7144fd5f0998c4accfd4b34be3d1f79ab37f0d7c726d4`.
Its sole submission/retrieval ledger is
`.irisx/nvarc-original/runs/nvarc-original-qwen3-probe-001/execution-final/`.
The last observed provider state is `QUEUED`, with no terminal retrieval yet.
The official SDK omits the zero-valued `QUEUED` enum in `to_dict()`, so the
typed enum is now retained beside the unchanged raw responses. Do not infer
model execution or a quota cause from that state. No CUDA outcome is asserted
before independently checked terminal evidence. A cold inference timing is
not full-training throughput.

## Complete published SDG yield reconciliation

Every byte of all 103,223 published synthetic puzzle members was rechecked
against the frozen 338,160,847-byte archive and its closed inventory. All
2,984,385 pairs pass grid/schema and pinned source diversity/minimum-twelve
predicates. All members join the complete original SDG parent metadata, with
mixture, input and output stages present. The archive has 102,930 unique
parent sets; 162,562 raw-artifact parent sets have no published puzzle. These
are artifact coverage counts, not regenerated success probabilities.

| Retained family/exposure | Published puzzle count |
|---|---:|
| `nvarc_training` | 47,337 |
| `nvarc_full` | 55,886 |
| Public-training-only lineage | 33,771 |
| ARC evaluation ancestor | 55,886 |
| Locked-holdout ancestor | 17,748 |
| Protected parent/visible family | 22,312 |

Exposure labels overlap and are preserved without filtering. Published pair
counts range from twelve to thirty, including 87,039 puzzles with thirty.
Every ordered pair of ancestors is retained; none is relabelled clean data.
No teacher call, generated-Python execution, ARC scoring or new pair acceptance
occurs. Whole-program semantics and the original majority-eight/four-consistent-
solutions filter are not replayed by these structural checks.

The first local pass completed every member but failed only while serializing
integer histogram keys. Its ledger and complete `members.jsonl` stay frozen at
`.irisx/nvarc-original/manifests/sdg-published-yield-20261002-001/`. A distinct
summary run independently reconstructs every member/parent/exposure/stage
binding and all counters from those retained observations, with zero repeated
program or predicate execution, at
`.irisx/nvarc-original/manifests/sdg-published-yield-summary-20261002-001/`.
Retained member stream SHA-256:
`c9b57f7450932327c66e58d19d7e3643e881e059bba1001eb133b27856755cd6`.

## Remaining scale and quality boundaries

Required full repository validation passes 320 tests in 346.026 seconds,
log SHA-256 `9f601f6ba177c4180df93faf5fc8943c49b5a9065319de9a356d04905fe4b09a`.
This follows one retained full-run failure in seven existing subprocess timing
cases; all eight process tests pass independently, and the unchanged full
suite passes on recheck. No timeout was widened. The later two new static/
duration cases and rotary compatibility case are covered by all eight current
source/evidence/transport tests, which pass in 0.021 seconds. Seven packed/
source-step tests pass in 70.448 seconds, followed by the new original tiny
128-view TTT differential (11.197 seconds), original packed CPU FSDP oracle
(16.708 seconds), and three existing hybrid TTT/reset/export checks
(53.312 seconds). These exact logs stay with the Qwen3 base material.

The continuation milestone's full repository check passes 321 tests in
266.923 seconds with four skips; SHA-256:
`40923964c3df89e0499328dec67b75667628080d1a75ba4036ea82ba1193b5a0`.
The later one-step reservation test and integer-bound repair are covered by
all twelve current source/evidence/transport tests (0.464 seconds), SHA-256:
`dd5906274b59ca9f0659036437bdc6a51e9398022a170cc4e8cf4bb5190cc056`.
All ten current packed/source-step strict tests pass in 72.478 seconds,
SHA-256 `71bb6eb32c0032adf6ae8af21a95bd7655121968dea3607753dd5d6ec0f33a07`.
A real Parquet complete-static-profile/immutable-prefix recovery test passes
in 7.355 seconds, SHA-256:
`dfe1f33fd0e19e099df49bcf88781153663d0c05333e8228ee3b0ba9e71aa532`.
The prefix test rechecks source bytes and every row binding, performs only the
three missing static AST analyses, yields identical full row bytes/counters,
and leaves predecessor files unchanged. No generated program is executed.

A separate complete input/output response static analysis is running at
`.irisx/nvarc-original/manifests/sdg-program-static-20261002-001/`, against all
170 input/output shards and 2,244,042 expected raw responses. It retains
program/response digests, exact five-field joins, both parent exposures,
source-parser syntax and one-argument entry diagnostics. A finite 3,600-second
local limit and immutable analysis-source snapshot apply. It never executes
generated code or claims dynamic semantics; full coverage is pending its
closed terminal report.
The continuation implementation can carry only an exact frozen response/code/
parent/exposure prefix with the same static diagnostic function AST and source
snapshot. Every shard byte and response join is rechecked, while completed AST
diagnostics are carried without repeating them. A new immutable identity and
its own finite local time limit are required after a retained incomplete pass.

One read-only accelerator quota snapshot is retained separately at
`.irisx/nvarc-original/manifests/free-resource-20261002-001/`. The SDK's
fractional-duration serialization defect is reproduced with an offline
synthetic timedelta; the retained snapshot reconciles to 13,695.029 free GPU
seconds remaining and zero reserved seconds at that instant. The next quota
refresh is 2026-10-03 00:00 UTC. This is an account snapshot, not an explanation
for the still-queued new kernel or permission to use paid capacity. No old
kernel state was requested and no monitoring automation or Goal was resumed.

The old Qwen3.5 segmented global-256 step takes 27–31 minutes. Multiplying by
12,716 gives 5,722–6,570 GPU-session hours (238–274 days), before checkpoint,
validation and transfer overhead. This is only an extrapolation of that port's
measured prefix, not a prediction for original NeMo or the new Qwen3 backend.
Fused numerical proof must precede an actual full-gradient throughput probe.
Neither the 32-H100 original SFT allocation nor eight-H100 TRM pretraining is
provided by four-L4 free Kaggle sessions. Durable cross-session optimizer
checkpoint transport remains a requirement before whole training.

Full long-task source TTT, original TRM 2,000-epoch TTT/10,000-epoch pretraining,
exact TRM notebook v18, whole SDG program semantics/filter yield, original
teacher regeneration and independent ARC quality remain open. Existing SDG raw
exposure is preserved; no Python generated by a teacher executes in this probe.
External teacher APIs and paid resources are outside the owner's authority.
Repeated public tasks remain tuning data and hidden competition answers remain
unused. New base/packing evidence does not establish a clean score or promotion.
