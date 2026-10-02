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
and Unsloth code. Its dependency kernel was not yet acquired at the first
audit. The NVARC source does not lock NeMo-RL or Megatron revisions. These
remain `null` in that frozen machine audit;
the previous NeMo-RL v0.3.0 MFFD placement reference is not relabelled as the
historical training environment. Audit SHA-256:
`5c7335b01175945d17ecbf659ef807aa8b4d1731cdcf50518f96a0bf6f9b25d7`.

The subsequent exact public dependency acquisition resolves the Unsloth version
gap. Original notebook v10 names dependency script-version ID `272622465`.
The public installer version 2 output index and all eight separately downloaded
small files resolve to precisely that ID. Its distribution metadata and
installation log bind Unsloth **2025.9.7**, Unsloth Zoo **2025.9.9**, Torch
**2.8.0**, Transformers **4.55.4**, PEFT **0.17.1** and FlashAttention **2.8.2**,
under Python 3.11.13 and original Docker image 31090 / OCI digest
`sha256:320043e14c68293f1c946585b9257123385205a58af4b94b17d31868cae4e868`.
The installer source's literal 3,029-byte patch equals the exact output patch;
the 16,701-byte patched Qwen3 source contains its corrected batch output shape
and `flash_attn_func` cached decode. The original notebook metadata, source,
version-specific files, installation log and distribution versions pass a
separate local binding check without importing or executing installer/package
code. Its proof is
`.irisx/nvarc-original/manifests/original-environment-binding-20261002-001/result.json`,
SHA-256 `8e9b0f15da091f7f4b14584a775e18c20e38fe5e4f20cb0020f1d39027cc0691`.
This establishes these original dependency identities, not every environment
file, historical CUDA numerics or the unknown NeMo/Megatron training revisions.
The earlier config audit and compatibility runtime are preserved unchanged.

One source read, one bounded 100-file output-index/log read and eight exact
version-2 small-file reads are retained. The first local index collector failed
on its `inspect.py` filename shadowing Python's standard library, before its
intended provider call; its failed identity remains frozen. A distinct collector
with Python's safe-path mode made the successful index read. Signed URLs and
credentials are never retained. No source installer or model is run locally.

The distinct private CPU-only environment probe
[`nvarc-original-qwen3-environment-001`](https://www.kaggle.com/code/danielwuu/nvarc-original-qwen3-environment-001)
was accepted as version 1. It requests the exact Docker image and existing
public dependency, requires all eight bound files, and checks imported Torch/
Transformers/Tokenizers paths plus the original twelve-token WordLevel chat.
Its private, Internet-disabled 600-second session has zero model forwards,
optimizer steps, generations, teacher calls and GPU/TPU allocation. The plan
digest is `sha256:6d67b521706111559adfed250224713b3ab9fa96666a285371468295939aad99`.
The sole push and terminal retrieval are consumed. The frozen version failed
at `dependency-mount`, after Python 3.11.13 passed, because `/kaggle/input` was
empty and none of the explicit input/working roots contained its dependency.
The 0.002547-second terminal envelope records zero model work; the sole archive
SHA-256 is `59399c452717505c8aee7982e2d2a22d861aa567c8deb5550032a346756d5c76`.
Independent package/archive verification passes without asserting imported
packages. The original version-1 template and bytes remain frozen.

Distinct private CPU-only
[`nvarc-original-qwen3-environment-002`](https://www.kaggle.com/code/danielwuu/nvarc-original-qwen3-environment-002)
adds the exact Kaggle notebook library roots and bounded Python dependency
paths, still requiring every eight-file digest. All model/compute/Internet/
USD 0 boundaries are unchanged; the solver is not run. Its private version 1
was accepted under plan digest
`sha256:ba75b92f2097a2eb07fdb913ec744b45d731ae956ef48d9293168fba3ebc897a`.
The sole push and terminal retrieval are now consumed. The 121.725-second
CPU session completes and its archive and exact plan verify independently.
All eight original dependency files match. Torch, Transformers and Tokenizers
actually import from
`/kaggle/usr/lib/notebooks/sorokin/pip_install_unsloth_flash_patch/`; all six
bound distribution versions match and Torch reports CUDA build 12.8 with no
available CUDA hardware. Original `Qwen2TokenizerFast` encodes `user` as `[11]`,
`assistant` as `[12]` and the complete chat as
`[14,11,10,0,1,15,14,12,10,1,0,15]`. Package installation, model forward,
optimizer, generation and source-program execution counts are zero.
Archive SHA-256:
`720594415c8733149d4b358ca257943ac18579878a2ab6f791e00e3ae802d570`;
independent proof SHA-256:
`355f7c4bf81fe5b34f35b506b9d865c85c406c7e863c9a2299121d9b65f806cd`.
Neither probe imports Unsloth's GPU-only loader or asserts CUDA parity. The
verified original tokenizer behavior remains distinct from the earlier 5.8.1
compatibility failure.

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

## Original CUDA numerical probe

After the exact CPU import/tokenizer prerequisite, the distinct private
[`nvarc-original-qwen3-unsloth-probe-001`](https://www.kaggle.com/code/danielwuu/nvarc-original-qwen3-unsloth-probe-001)
was accepted as version 1. Its original Docker/dependency and published SFT
version are bound to the same verified material. Four distinct BF16 L4s and
the official entitlement mount are required; no competition file is opened.
Two isolated sequential rank-zero processes each reserve one twelve-token
prefill and one fixed cached input token: Transformers 4.55.4 SDPA versus the
original Unsloth patched inference. There is no LoRA adaptation, optimizer,
generation, teacher call, score or exported model. The 1,200-second private,
Internet-disabled session reserves exactly four outer forwards/26 input
tokens. A production call guard blocks constructor-time or additional model
calls, and the reader independently recomputes the two retained logit-vector
comparisons; runtime completion does not assert solver parity.

Plan digest:
`sha256:36f613243728f604577a74efb4166507ea6541d574924d739f7f3c81a0708b45`;
sole save receipt SHA-256:
`0bd3152e38980e15f89ffede9cf100728ead68fa548b260ab26f6aa70e67afd5`.
The push and sole terminal retrieval are consumed. Version 1 failed in
212.817 seconds at the original Unsloth cached-token call. Four distinct
BF16 L4s, the original Torch 2.8.0 CUDA 12.8 build and all ten model files
verify. The same-runtime SDPA reference completed both calls; original
Unsloth returned its prefill, then rejected `position_ids=None` in
`move_to_device`. Four outer calls/26 tokens were reserved, with zero
optimizer steps, generations or teacher calls. The first native prefill
vector was not persisted before the failed cached call; no native numerical
comparison or full-runtime prerequisite follows. Frozen archive SHA-256:
`4d367632ebd6cd60fc2bf6f420ef3f6b5ff85f222a53eef8ce93c460eaec5cc6`.

The exact original DFS passes an explicit position tensor for cached tokens.
Distinct private
[`nvarc-original-qwen3-unsloth-probe-002`](https://www.kaggle.com/code/danielwuu/nvarc-original-qwen3-unsloth-probe-002)
therefore binds prefill positions 0–11 and cached position 12. It also records
completion after each actual call and saves each prefill vector before the
cached call. The original Docker, dependency, model, four-L4 entitlement,
four-forward/26-token/zero-training envelope and 1,200-second bound remain
fixed. Version 1 was accepted with its one push consumed and no retrieval yet.
Plan digest:
`sha256:98dd97a73e30f31d445cd64ba703cc47d4a92b6f2001d4833e0209b71eaf8c54`;
receipt SHA-256:
`815dc64495063be69d351311350309a0340ec320ce2924ef68f930333786e92f`.
Six source-call-guard/closed-reader tests pass, including missing/wrong
positions, failed completed-prefix accounting and altered retained prefill
vectors. The frozen 001 package still passes offline preflight.
An actual tiny current CPU Qwen3 compares default cache positions with the
production guarded explicit positions: both complete prefill `[1,12,16]`
and cached `[1,1,16]` logits match bitwise. Exactly four tiny forwards/26 input
tokens and zero optimizer/generation calls occur. This is a compatible CPU
reference check, not the original 4B/Unsloth CUDA observation. Proof SHA-256:
`4b8e92f6fda1d8060472856dd63f3b123e7d8c1ec3a3932a663c1727332de711`.

The current read-only free-quota snapshot 004 reconciles to 12,814.729 free
seconds remaining, zero reserved seconds and pay-to-scale disabled before
the repair push. It is an account snapshot, not a queue-cause diagnosis or
permission for paid/full-scale work. Native-training inspection tooling is now
implemented and locally checked, with no transport package, push or original
runtime observation. Its package generator refuses to write any package before
the original explicit-position Unsloth GPU prerequisite completes and verifies.

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

## Exact source TTT target and precision policy

Five additional small dependency files from exact installer version 2 / script
ID 272622465 bind the original loader, adapter rewrite, trainer and Torch Adam
code. They are read without importing or executing them. The original
`FastLanguageModel` inherits `FastLlamaModel.get_peft_model`. That implementation
removes `embed_tokens`/`lm_head` from LoRA projection targets and puts each into
full `modules_to_save`. The source model therefore has 252 rank-256 projection
targets and two full `[16,2560]` trainable matrices. From the exact published
config this implies 528,564,224 trainable parameters; it is a source-based
count inference, not an actual original Unsloth runtime count.

The frozen plain-PEFT compatibility observation instead has 254 LoRA targets,
529,801,216 FP32 trainable parameters, including LoRA embedding/head factors.
The original notebook converts every FP32 parameter to BF16 before retaining
its default snapshot. The original Torch Adam implementation allocates moments
with `zeros_like` the current parameter, but actual trainer-time parameter/
moment dtypes have not been observed. The source also has a runtime detail:
both declared checkpoint options are False, while its unqualified
`FastLanguageModel.for_training(model)` calls a default that sets checkpoint
flags True. The effective original checkpoint backend remains unmeasured.

The complete source-policy audit is
`.irisx/nvarc-original/manifests/original-ttt-policy-20261002-002/result.json`,
SHA-256 `7afc110155fd087c259dc750be6e4434e642fd8ef732463ccad755813339ed79`.
The first offline parser failed before creating a result because the source
uses literal `dict(...)` constructors; a distinct corrected audit reads only
literal arguments and rejects executable calls/unpacking/duplicate keys.
No model call, optimizer step, source-package import or generation occurs.
The long-task 002 package remains frozen and inert as a compatibility/resource
proposal. Its known target/precision/backend differences prevent treating it
as an exact original TTT reproduction. A new original-runtime candidate must
bind the actual Unsloth adapter and training behavior before execution.

The later policy audit additionally binds the exact published configuration
and independently verified material, without replacing the earlier proof.
Its SHA-256 is
`3a061806fd40202a4494ce5f35a46d3b6be8b8018990487f59d8167df83ae31f`.

Thirty exact files from dependency script ID 272622465 now verify sixteen
installed distribution versions and thirteen training/config/state Python
modules. In addition to the six core versions above, the original installation
contains Accelerate 1.11.0, TRL 0.22.2, Datasets 3.6.0, Tokenizers 0.21.4,
Hugging Face Hub 0.36.0, Safetensors 0.6.2, NumPy 2.2.6, Triton 3.4.0,
TorchAO 0.14.1 and Cut Cross Entropy 25.1.1. The earlier compatible runtime's
versions remain separate. Exact metadata/source audit SHA-256:
`bf0f748811d96c110152ab0f38e203a080e3252b7e05b6772441d281520b368a`.
This closes those version identities, not the full environment inventory or
actual patched Trainer behavior.

Effective context requires the complete patch chain and native runtime inspection.
Native TRL's `SFTConfig.max_length` defaults to 1,024, while the original
notebook passes legacy `max_seq_length=8192`. Its compatibility wrapper can
retain an existing argument object and discard that extra legacy keyword.
Two subsequently acquired exact dependency files bind `unsloth/models/__init__.py`
and `unsloth/models/rl.py`. The original Llama module calls `PatchFastRL` at
import, and its generated SFT constructor patch uses the model's context to
set `args.max_length`. The literal patch fixture changes an artificial
1,024 default to 8,192 when the model carries `max_seq_length=8192`, retains
an explicit 4,096 alias, and retains 1,024 when no model context exists.
The earlier compatibility-wrapper fixture covers only the outer wrapper;
its 1,024 observation cannot establish actual original truncation. Complete
length-patch fixture SHA-256:
`80e0271489643a0044310d5216916a818918e229324cf8b5e9c337af7b2cb4e4`.
Both new source files and the original Llama import call are byte-bound;
no vendor package, native Trainer or model is imported by this fixture.
The exact PEFT state extractor returns tensor references, but the complete
original worker immediately clones and detaches every returned tensor before
retaining `default_weights`. Its later dictionary `.copy()` therefore uses
the independent baseline tensors. The earlier audit 001 and fixture 002
described only the raw extractor references; they do not identify an original
snapshot defect. The new audit 002 includes the complete clone assignment.
Effective GPU preprocessing and actual task-reset behavior after all Unsloth
patches remain unobserved.

A distinct local fixture replays these literal trusted functions on explicitly
artificial constructor classes and a tiny BF16 projection tensor. It observes
the retained 1,024 argument value, the raw extractor's shared storage, and the
complete original clone assignment's independent detached baseline after one
manual scalar perturbation, restoring the scalar afterward. It performs zero model
forwards, optimizer steps, generations, teacher/provider calls or generated
program executions. It is not an actual original adapter or Trainer test.
Complete snapshot fixture 003 SHA-256:
`47a6d6dba071e9490870a02707eca7a680f10db56eadfb95fbed19109c7846e5`.
The first fixture's missing artificial constant failure is separately frozen;
both corrected observations use distinct identities. Exact source-expression
tests reject removing clone or detach and check that baseline dictionary copies
survive perturbation. Original runtime preprocessing and task reset remain
explicit prerequisites.

## Native adapter and Trainer inspection preparation

The new zero-work inspection tool binds all thirty-seven exact dependency
source/metadata files, sixteen versions, the published original untied model,
the complete original classes and recipes, and the completed cache prerequisite.
It has a 1,200-second parent and 900-second child ceiling, four distinct BF16
L4 gate, one rank-zero worker, Internet disabled and USD 0. The parent kills the
worker process group on timeout or interruption. It creates no source Dataset.
The tooling blocks normal/compiled module call dispatch, both autograd entry
points, tensor backward, optimizer construction and Adam/AdamW step before
execution, and detects a guard replaced during imports or construction. It
retains topology before Trainer construction, all finite detached baseline and
reset tensor fingerprints, actual prepared arguments, checkpoint flags and
native Trainer class sources. It makes no call to `train()` or the loss method.

Complete source-view materialization preserves all 128 original `as_list()`
rows, the existing parent/exposure tags, exact solver cell and source-mask
digests. Every text/token digest agrees with the earlier closed replay; no mask
AST replay, model, teacher or evaluator call occurs. It retains 3,309,314
uncompressed bytes and 242,886 gzip bytes. Proof SHA-256:
`88ee3161a7f82eb051ae846161a6cfd2d9ebdbfa145b0d84cb3d52098763b134`.
The first local materializer failed before writing source output because it
compared the raw visible mapping with the normalized task digest. Its source
and failure are frozen; distinct materialization 002 uses the existing
`visible_task` normalization and passes.

Native inspection mirrors the actual HF Dataset dataloader's unused-column
removal before the original collator. It retains every resulting input ID and
label as closed signed-int16 little-endian vectors. The independent reader
recomputes every vector digest, length and supervised count against the frozen
complete source-mask proof, all baseline/reset fingerprint equality, and the
complete source-inferred projection/full-save topology. Completion remains
separate from qualification for long-task source TTT: a context, dtype,
topology or mask difference does not unlock it. Nine offline budget/vector/
state/envelope tests pass, including faults that rehash the entire archive.
The original numerical 001/002 packages stay unchanged.

An actual tiny CPU construction fixture first passes under current Torch/
Transformers/PEFT with zero model forwards, five prohibited operations blocked
before execution and restored guard methods. Its SHA-256 is
`a08baf9ff66084db0f022957cffaf556d07706e3519a95618eee2c0c21bd1248`.
The later full-source fixture 002 retains a failed Transformers 5.8.1 frontend
observation. Each source view loses the eight user/assistant role IDs (7,456
instead of 7,464 tokens), so the unchanged completion mask has zero supervised
tokens. Its exact source and 3,817,472-byte binary are frozen. This agrees with
the earlier standalone role-loss observation, not an original 4.55.4 failure.

Distinct fixture 003 uses the retained compatible Transformers 4.53.3,
Torch 2.12.1 CPU and PEFT 0.21.0. Under the same production guard, an actual
tiny Qwen3/rank-2 projection adapter with full embedding/head save modules
constructs, its original clone/detach recipe remains independent, and every
saved tensor resets exactly after one scalar perturbation. The exact original
completion class runs over the actual compatible Transformers parent collator.
All 128 source input/label vectors agree, totaling 955,392 input and 476,160
supervised tokens. Five work attempts are blocked, with zero forwards,
optimizer construction/steps or provider calls. It completes in 40.234 seconds;
proof SHA-256:
`fdb516ade19474ad2bc494d1b5de72a0d5deacc8e3df8e58458096355b53d982`.
An independent zero-tokenizer/zero-mask-replay reader recounts all 3,821,568
vector bytes and every source digest. Its SHA-256 is
`e04f18152c495d09fc82a7fd9dadc8b4ee54df53a58fdad44c47adfeb9167d65`.
The fixture's Trainer base and unused-column routing are explicitly artificial;
no actual Unsloth Trainer, original 4B adapter, optimizer state or long epoch
is observed. The original runtime and free-resource prerequisites remain open.

## Compatibility runtime and full long-task candidate

The separate Transformers 4.53.3 environment first rejected the tiny epoch
before training because PEFT was absent; that failed log stays retained.
After installing pinned PEFT 0.21.0, Accelerate 1.10.1 and Psutil 7.2.2 there,
the unchanged full 128-view checkpoint/CPU-Adam differential passes in 14.085
seconds. A later real training-path test also attaches the production forward
reservation hook and independently reconciles all 128 optimizer events;
it passes in 15.098 seconds, SHA-256
`2212506baae1ab77fa61eb0ffe9966b3de173fc50df5d0b426d645ff50d1beb6`.
These are actual tiny CPU training observations, not 4B GPU epochs.

The actual untied published 4B checkpoint was separately loaded on CPU with
its original-family rank-256, alpha-32 rsLoRA. All 254 targets and
529,801,216 trainable FP32 parameters were observed. One manual parameter
perturbation changes the state hash and reset restores every retained state
byte exactly. No model forward, training token, optimizer or generation occurs.
The 39.735-second observation is
`.irisx/nvarc-original/runs/nvarc-original-qwen3-adapter-material-001/result.json`,
SHA-256 `149779b012478bf49aa03a9657e49f4f8fc22e7b0554d3fa20e6d422d4f10739`.
This exposes the real adapter's size without asserting L4 memory feasibility.

Seven exact Linux/universal wheels—Transformers 4.53.3, Tokenizers 0.21.4,
Hub 0.35.3, PEFT 0.21.0, Accelerate 1.10.1, Safetensors 0.8.0 and
Psutil 7.2.2—total 16,385,462 bytes. All filenames, sizes and SHA-256 values
match seven bounded official PyPI release reads. The earlier pinned pip
download's individual HTTP count was not independently retained. Material
digest: `sha256:9fa3f0e5365f99a15ee48643842123bfe1867d16eeb84d110d84af63bc4d995f`.
Their sole private Dataset creation and one ready check are consumed:
[`danielwuu/irisx-nvarc-original-qwen3-ttt-runtime-001`](https://www.kaggle.com/datasets/danielwuu/irisx-nvarc-original-qwen3-ttt-runtime-001),
version 1. Existing Dataset versions are not mutated. The checkpoint's recorded
Transformers version is retained. The later dependency acquisition establishes
original Unsloth and the notebook's Transformers 4.55.4; the complete historical
runtime byte inventory remains unverified. These seven wheels are the earlier
checkpoint-config compatibility runtime, not the original dependency overlay.

The full-long-task runner reserves only exact approved input/label row digests
before actual model forwards. It retains every returned step, original
13-step warmup/cosine rates, finite gradient-group coverage, changed adapter
bytes and exact reset. An independent closed result reader reconstructs all
128 source views and their multiplicities, per-step tokens and schedule. It
checks actual worker UUID against four-L4 inventory and preserves failed
prefixes without asserting completed epochs. Artificial local archives against
the real frozen package pass failure-prefix reading and reject rehashed Boolean
costs; they are explicitly fixtures, not provider outputs. Fixture report
SHA-256 `2887bf09e207cc881e86e39a8000467bf0996c628f3260b5f4f8e3819c4bb454`.

`nvarc-original-qwen3-long-ttt-001` remains an immutable, unsubmitted local
prototype. The distinct reviewed `002` package is offline verified and its
sole transport journal is initialized with push/status/retrieval reservations
all zero. Plan digest:
`sha256:df58ebb4e99b9c2f56117bc7f3b5fd171ff43884e0e741db069817f00d1d6e2a`.
It binds the same public long task's 128 complete views, 955,392 input tokens,
128 optimizer steps, one rank-zero model worker on a four-L4 gate, original
untied published material, offline dependencies, zero generations/teacher/
verification calls, no export, USD 0 and a 10,800-second notebook ceiling.
The initial offline SDK initialization failed on absent ML packages before
creating any submission budget. Its log is retained; bounded offline preflight
now uses the separate ML interpreter while credential transport stays in the
SDK environment. The kernel package bytes remain unchanged. No C kernel has
been submitted. Actual CUDA long-epoch memory/time remain unobserved; execution
is held by the now-known original topology/precision/backend differences,
in addition to numerical prerequisites and free-resource accounting.
No historical task-clock parity follows.

The full long-task input/loss-mask replay now executes only the hash-gated
original formatter and collator mask definitions. All 128 views, 955,392 input
tokens and 476,160 supervised tokens match the frozen proposal token by token.
It uses the actual published WordLevel JSON and the unchanged source mask
method with an explicit single-example/no-padding base-batch substitution.
Original `UnslothFixedTrainer.compute_loss` also preserves cloned independent
storage and correct gradients under one/four-process artificial tensor cases.
Those are explicitly callable stubs, not model or original Trainer runs.
The 49.391-second proof has SHA-256
`bb6039067f5d008b465e5ff4e519ceb706211555ed8e318a1c84a577ba0ff484` at
`.irisx/nvarc-original/manifests/original-ttt-loss-20261002-001/result.json`.
It proves source data/loss-mask alignment with zero model/optimizer/generation/
teacher/provider calls, while actual original Unsloth training remains open.

The explicitly referenced TRM v18 source remains unverified. Prior exact SDK
forms retain HTTP 404/403, and the separate public source-page read reports
the URL inaccessible. This does not establish that the version is absent;
the acquired v21 is not relabelled v18.

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
material CUDA differential and its terminal archive binding; the failed
001 prerequisite is rejected before creating an execution package. The prospective
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
Its sole push and terminal retrieval are consumed. The terminal archive has
SHA-256 `be6cfbb2e0608e9d328c8eec9b8d3a3df562aa00a6e36e8a06f40c32aee33025`;
the independent reader verifies all fourteen members, exact materials and four
distinct L4s. The 180.346-second session fails at the actual 4B packed numerical
gate. Tiny BF16 CUDA gradients pass their 0.006/0.06 gate across all 24 gradient
tensors. The first actual-weight comparison rejects 1,070/120,992 elements
(0.9%) at the unchanged 0.25/0.03 tolerance, with maximum absolute error 8.125.
Twelve forward slots and 63,152 input tokens were reserved; the stage-level
ledger does not establish that every reserved call completed. Isolation was
not reached, and no optimizer step, generation or training-throughput evidence
exists. The full numeric report was written after assertions, so it is absent.
The distinct local read `independent-verification-002.json` also validates the
retained tiny observation without claiming the failed full-model gate passed.

The next distinct diagnostic uses the same whole eight rows and original
material. It forces SDPA's Flash backend and decomposes independent SDPA,
single-sequence varlen and merged varlen. The original 0.25/0.03 gate remains
fixed. Actual model-entry hooks reserve every input before the call and retain
completion, with 21 outer forwards, 126,260 input tokens, two tiny backwards,
zero steps/generations/teachers and an 1,800-second session limit. Full logits
and three fixed positions per row at embedding, all 36 layers and final norm
are saved before gating. No hook adds a model or attention-reference call.
An independent dependency-free reader reconstructs every input/cost prefix,
full-logit error, argmax disagreement, sampled-state difference and isolation
from closed little-endian FP32 representations of the actual BF16 outputs.
These are cold diagnostic timings, not training throughput. Package status and
receipt are retained below after offline verification and submission.

`nvarc-original-qwen3-probe-002` passed exact offline preflight and was accepted
as private `SAVE_AND_RUN_ALL` version 1, kernel `136776339`.
[Kaggle kernel](https://www.kaggle.com/code/danielwuu/nvarc-original-qwen3-probe-002).
Plan digest: `sha256:b76461897b101207b784b1b91db66d25dea4ec6c567d541c2e4a571b18ede5d8`.
Receipt SHA-256: `2f610dab5c3cb1e3c96bbb89b4517c0331c4729251ec73e002a62351f4a16630`.
The sole push is consumed; no terminal retrieval has occurred. The fixed
package and journal are under the new run's `package-l4/` and
`execution-final/`. The real tiny Qwen3 CPU entry-hook integration passes in
0.342 seconds, with one unreserved entry rejected and two budgeted actual
forwards completing. This establishes hook operation, not CUDA numerics.

The separate source-policy audit 003 strengthens the unchanged 528,564,224
parameter-count inference with the byte-verified published checkpoint config
and the retained actual compatibility observation. It imports no original
package and executes no model or source program. Its proof SHA-256 is
`3a061806fd40202a4494ce5f35a46d3b6be8b8018990487f59d8167df83ae31f`;
002 remains frozen. Original adapter/trainer behavior is still unobserved.

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

The earlier fixed published-group dynamic replay is separately reconciled
from its full retained ledger: 635 reserved isolated invocations (35 input
attempts and 600 outputs), 27 sandbox rejections, 578 valid nonidentity output
observations and thirty accepted pairs under the exact 8/12/4 filter. The
latest recovery performs zero new invocations. Result SHA-256:
`f6fe8d74bcd9490053b931b80444ad854f2d6fc53f727558fc45950efbfd6511`.
The 630 figure in earlier shorthand describes the thirty-input/six-hundred-
output successful-path workload; it is not the actual reservation count.
This remains one fixed exposed group, not complete dynamic SDG verification.

The current long-epoch/runtime milestone's required full repository check
passes 327 tests in 448.486 seconds with four skips. Log SHA-256:
`4805aca59f5cdb301b2f6d09d8bfefcd17787a2df9cb67afd71225c4868337d1`.

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

A separate complete input/output response static analysis targets all
170 input/output shards and 2,244,042 expected raw responses. It retains
program/response digests, exact five-field joins, both parent exposures,
source-parser syntax and one-argument entry diagnostics. A finite 3,600-second
local limit and immutable analysis-source snapshot apply. It never executes
generated code or claims dynamic semantics. The first pass retained 80 closed
shards, 81 reserved shards and 1,023,189 analyzed rows when its 3,600-second
wall ceiling ended. Its immutable response stream SHA-256 is
`91ebd3372e109100a88a585ae80c177ef02e2553f37cc02d3aa205e159c75773`.
The distinct `sdg-program-static-20261002-002` continuation has a 10,800-second
local ceiling and carries those exact rows without repeating AST diagnostics.
Every shard, response/code and both parent/exposure bindings are rechecked.
It completed all 170 shards and 2,244,042 responses in 9,069.032 seconds,
carrying 1,023,189 prior diagnostics and adding the missing 1,220,853. Complete
response-stream SHA-256:
`411d2dfac850dc6d0025bd5654d104c12ff6b0c5c6e23375bf9c12d6a2ef3500`.
The continuation implementation can carry only an exact frozen response/code/
parent/exposure prefix with the same static diagnostic function AST and source
snapshot. Every shard byte and response join is rechecked, while completed AST
diagnostics are carried without repeating them. A new immutable identity and
its own finite local time limit are required after a retained incomplete pass.

The new independent static reader recounts the closed response stream without
repeating raw-Parquet reads, generated-code AST analysis or program execution.
Every shard's count must match the earlier independently read Parquet headers;
every normalized parent/stage count and exposure must match the complete raw
metadata profile. The reader also checks exact diagnostic row schemas, report
counters, source-parser and analysis snapshot hashes, and unchanged preceding
prefix evidence. A real 170-shard Parquet fixture exercises both complete and
carried-prefix paths and rejects changed row/exposure/schema bindings. Its two
tests pass in 18.072 seconds, SHA-256
`a32435c4b32e8ed9e8294accc201091885fd55b6976b0d7fd670f3ff6b8940fd`.
The real whole-response terminal recount now passes. It independently checks
all retained rows, the earlier raw Parquet header counts, every parent/stage
count, both parent exposures, unchanged predecessor bindings and all reported
histograms. Proof SHA-256:
`b9320669b9fa411dbbf02078016909976ac71ccf0a13d90265604606dc091778`.
It consumes zero new AST diagnostics, raw-Parquet reads, program executions,
teacher/model calls or accepted pairs. The closed static counts are:

| Stage | Raw responses | One-argument entry contract | Python syntax rejected | Other entry rejection |
|---|---:|---:|---:|---:|
| Input programs | 193,793 | 192,415 | 1,221 | 157 |
| Output programs | 2,050,249 | 2,040,730 | 9,248 | 271 |

There are 131,804 output groups: 73,139 retain twenty solutions, 58,566 retain
ten, and 99 retain another observed count. All output groups have an input
response; 61,989 input groups have no output response. These are raw source
joins and static entry observations, not executed semantics or accepted
synthetic pairs. Whole 8/12/4 filter replay and dynamic program yield remain open.

After adding the independent static reader, full repository validation passes
328 tests in 474.911 seconds with four skips. Log SHA-256:
`a7a560e92ac3cabb0a3800078c4004a64d6a91551ddb79d20d8732e594fea192`.

The subsequent environment acquisition and CPU-only transport tests reject
rehash attacks on version, dependency identity, patch, source inventory and
GPU-enable metadata. All four focused tests pass after adding the separate
immutable version-2 transport template. Full validation 008 passes 332 tests
in 516.444 seconds with four skips, log SHA-256
`1999de9763b0b6675bad31b4577bd2dd8a7545f6effb5261a52b8af0d18c19df`.
The frozen environment 001 preflight still passes after the distinct 002 repair.

One exact-integer public TRM version-18 request for its presumed converted
script filename returned HTTP 404 and acquired no source bytes. The attempted
public page also could not open in the browser runtime. These observations
do not establish that version 18 is absent. Exact TRM v18 remains unverified;
the separately retained v21 notebook and original claimed v18 ID remain distinct.
One subsequent source request with that explicit script ID as `version_label`
also returned HTTP 404 with zero source bytes. That failed acquisition remains
frozen and likewise establishes no absence claim.
One distinct public version-18 output-index request likewise returned HTTP
404. It retained no source, log or model bytes and requested no own-kernel
runtime state. These failed acquisition methods are preserved without retry.

Full validation after the original CUDA probe passes 336 tests in 498.653
seconds with four skips, SHA-256
`040ed30f42dd39d418e736366012476d8076154b7160dd0b19b61d1806d44f56`.

All seventeen current original evidence/runtime/cost/transport tests pass in
0.551 seconds, SHA-256
`99ca41e2a1ef01351a49a277e5518ad43400000200e0b224fecd60448c74492d`.

Validation 010 was interrupted and makes no PASS claim. The resumed full
validation 011 passes 338 tests in 276.617 seconds with four skips; log SHA-256
`66023db04519dbb0c1a12a112ad16b6c6005bdd340202d7428c11a9c62b18fa5`.
Full validation 012 passes 342 tests in 332.805 seconds with four skips,
SHA-256 `d69c3d32f838977261a72d99f23a3ecda47f0289f36ae4cd459c2210b32ce585`.
Full validation 013 covers the source loss replay and prerequisite-reader
dispatch: 343 tests pass in 340.363 seconds with four skips, SHA-256
`9329b0f0765eeba24f11b0e5ef7d605e61e99bf48c34ff3c8e83fb1caaceee0b`.
The subsequent exact training-environment audit and source-edge fixtures
require another full check before handoff. Their metadata parser test passes;
no source package is imported by the environment auditor.
Full validation 014 retains one existing Windows `os.replace` access-denied
failure in a saved-teacher fixture (344 tests, four skips); that unchanged test
passes independently. Its failed log SHA-256 is
`880f57343693a9035404c71ff732570849917a60b65743ae5008e99cb02a1550`.
Full validation 015 includes the complete snapshot-source regression: 345
tests pass in 274.413 seconds with four skips, SHA-256
`7653cac4cf5154528706097c1c73e31e4e652592270cc623b72a3258ed45c9c2`.
After the separate native-GQA adapter, full validation 016 passes 345 tests
in 258.139 seconds with four skips, log SHA-256
`e3c72040ca6873387b3c6ef2cba02e74b4a2f6c549e9b8dbe80723d064291a61`.
All eleven real tiny-Qwen3 packing/optimizer/collective/guard/layout tests
also pass in 63.679 seconds, SHA-256
`86e03b178e7139cbe99d0e772567606e0ab7c3b35a278348b0e266245f242883`.
Full validation 017 covers the cached-position repair and completed-prefix
reader: 347 tests pass in 280.664 seconds with four skips, SHA-256
`5987e6c17e01d1831d683db9ca7593fb46dfee81b3b33fc5756dd912f237017d`.
Full validation 018 covers the native zero-work inspection and independent
raw-vector reader: 356 tests pass in 302.871 seconds with four skips, SHA-256
`b4e2b3c7ae22ea6e30d8660a94b684f15fdf26b966765dde04f54e3817d0a471`.

One read-only accelerator quota snapshot is retained separately at
`.irisx/nvarc-original/manifests/free-resource-20261002-001/`. The SDK's
fractional-duration serialization defect is reproduced with an offline
synthetic timedelta; the retained snapshot reconciles to 13,695.029 free GPU
seconds remaining and zero reserved seconds at that instant. The next quota
refresh is 2026-10-03 00:00 UTC. This is an account snapshot, not an explanation
for the still-queued new kernel or permission to use paid capacity. No old
kernel state was requested and no monitoring automation or Goal was resumed.
The distinct snapshot 003, after 001's terminal failure, reconciles to
13,290.199 free seconds and zero reserved seconds, with pay-to-scale disabled.
Its raw and typed SDK duration representations retain their identical
remaining-duration difference; no paid capacity is used.

The old Qwen3.5 segmented global-256 step takes 27–31 minutes. Multiplying by
12,716 gives 5,722–6,570 GPU-session hours (238–274 days), before checkpoint,
validation and transfer overhead. This is only an extrapolation of that port's
measured prefix, not a prediction for original NeMo or the new Qwen3 backend.
Fused numerical proof must precede an actual full-gradient throughput probe.
Two exact PyTorch v2.10.0 public source files are now retained locally with
two reserved read-only requests. The public varlen wrapper calls the native
Flash operator, whose forward and backward support unequal query/KV head
counts when the KV count divides the query count. The current adapter repeats
KV heads explicitly. This is a possible kernel-layout numerical difference,
not an established explanation for probe 001's failure. Submitted 001/002
bytes remain unchanged. Any native-GQA experiment must use a distinct identity
and retain the fixed numerical acceptance thresholds. Source SHA-256s:
`60bd026d3e1f2628aa6997c9e669179e6129f349821dfb1725add3c2c172f54b`
(public wrapper) and
`0a2e90419f0583d9f34ffc22567fd0d6d882fdb6ec2260f5c7a0e5ba2afb3021`
([native Flash implementation](https://github.com/pytorch/pytorch/blob/v2.10.0/aten/src/ATen/native/transformers/cuda/flash_attn/flash_api.cpp)).
The separate `torch-varlen-flash-gqa` adapter is locally implemented with an
explicit Torch 2.10.0 CUDA gate and unchanged sample offsets. Its CPU-only
layout/arithmetic test preserves four query heads and two KV heads, compares
both segmented forward values and every Q/K/V gradient to explicit KV repeat,
and rejects invalid head ratios/shapes and CPU varlen dispatch. It passes in
0.267 seconds. This is no native CUDA operator or 4B numerical observation;
no GQA-variant package is staged or submitted. Earlier probes and the existing
full-gradient prerequisite remain on their exact repeated-KV backend.
Diagnostic 002 is now terminal. Its fifth backed-off status returned ERROR;
the sole retrieval consumed one output listing and archive download. All
twenty-one forwards and 126,260 input tokens completed on four distinct BF16
L4s; the retained vectors pass an independent twenty-five-member recount.
Archive SHA-256:
`1a300e4a60ed062e1f3c6036910e47bcc464d3de2a4612def8472d997825de14`;
independent proof SHA-256:
`13f56f4ebb7fef1f43b6fa911055fa8c7115d2337b1470be41c065adec058970`.
The 177.802-second session fails only after retaining every mode's logits,
sampled states, isolation vector and exact completed-call ledger. Every
single-sequence varlen logit and all thirty-eight sampled states match the
forced Flash SDPA reference bitwise across all eight complete samples. Merged
packing's embedding samples match, but layer 0 already differs by up to 0.0625
and the maximum final-logit difference is 13.59375. In total 9,147 of 504,864
logits exceed the unchanged 0.25/0.03 gate, with 58 argmax disagreements across
31,554 token positions. Changing the first sample leaves every later packed
logit bitwise unchanged. No optimizer, generation, teacher or scoring occurs.
This localizes the open difference to merged execution after embedding;
KV repetition alone is not established as its cause because single varlen
already matches. Any new first-layer/operator diagnostic needs a new immutable
identity and exact bounds. Full-gradient staging remains blocked.
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
