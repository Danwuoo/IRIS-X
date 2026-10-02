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
fixed. Version 1 was accepted; its push and sole terminal retrieval are now
consumed. The fourth backed-off status returned ERROR. Both reference calls
and both native Unsloth calls returned with their exact position IDs, but
cached-result extraction assumed `.logits` on the original tuple output.
The 507.520-second terminal envelope preserves all four completed calls and
26 input tokens, with zero training/generation/teacher work. Both prefill
vectors are retained: maximum absolute difference 0.03125 and equal argmax,
without bitwise equality or a retained native cached vector. Archive SHA-256:
`74868ffbb99de934dbc6713b5af6846d478227cee4d231e7a86024b995238cd7`;
independent proof SHA-256:
`d652bc8ed9356b7bdfcec5aa401788b80e1af7f966c05f8b3bbfcf316656fcdd`.
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

The exact original `llama.py` causal-LM wrapper explicitly returns
`(logits,) + outputs[1:]` when `return_dict` is false. Distinct private
[`nvarc-original-qwen3-unsloth-probe-003`](https://www.kaggle.com/code/danielwuu/nvarc-original-qwen3-unsloth-probe-003)
repairs only result extraction: attributes or tuple indices 0/1 must contain
the exact `[1,12,16]` / `[1,1,16]` logits and nonempty cache. Original explicit
positions, immutable materials, versions, four-forward/26-token workload and
1,200-second session are unchanged. Original source bytes and the consumed
002 archive are bound in the new plan. Eight offline guard/result tests pass;
the old 001/002 preflights still pass. Version 1 (kernel ID 136791873) was
accepted after one reserved private push. The third backed-off status observes
COMPLETE; the sole terminal retrieval consumes one listing and one archive
download. All four forwards and 26 input tokens complete in 412.480 seconds
on four distinct BF16 L4s with exact original dependency and model materials.
The reference returns model-output objects twice; Unsloth returns a
model-output prefill and a tuple for its cached call. Independent comparison
of the sixteen vocabulary logits at the last prefill position and the cached
token finds maximum absolute differences 0.03125 and 0.5, with equal argmax
for both. Full-prefix logits are not retained by this probe. This closes output capture, not
bitwise/numerical or historical full-solver parity. No optimizer, generation,
teacher or correctness scoring occurs. Archive SHA-256:
`9899ee1b58a3673cefd586e111c6d745006161b3213fa6bd59b0f817093eb8c7`;
independent proof SHA-256:
`23f387b52d46ead3d3d3e69ae4b378f9d4a11eebdc06352efb0ae14c21b5f1d6`.
Plan digest:
`sha256:1c1815ecfce27842880187f6693cdfe78e836545923902b3a20b744bf2508e0e`;
receipt SHA-256:
`446512fd13a150eac9d1f120311f1ef2382e7f3e00b8466ccc1b8ff3bac01477`.
This completed, once-retrieved original cache probe unlocks only the reviewed
zero-work Trainer inspection; failed 002 remains consumed.

The current read-only free-quota snapshot 004 reconciles to 12,814.729 free
seconds remaining, zero reserved seconds and pay-to-scale disabled before
the repair push. It is an account snapshot, not a queue-cause diagnosis or
permission for paid/full-scale work. Native-training inspection tooling is now
implemented and locally checked, with no transport package, push or original
runtime observation. Its package generator refuses to write any package before
the original explicit-position Unsloth GPU prerequisite completes and verifies.
Distinct snapshots 005/006, before the two current submissions, each reconcile
to 11,332.267 free seconds, zero provider-reserved seconds and pay-to-scale
disabled. Conservatively charging four GPUs for both 1,200-second session
ceilings reserves 9,600 seconds locally; this fits those account snapshots.
This does not supply original-scale or paid training capacity.
Snapshot 007 after the cache retrieval reconciles to 8,807.201 free seconds,
zero provider-reserved seconds and pay-to-scale disabled. A conservative
four-GPU reserve for the still-running 1,200-second operator probe plus a new
1,200-second inspection would total 9,600 seconds and exceed this snapshot.
The inspection is prepared offline and waits for the operator probe's terminal
state and another exact quota check before submission.

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
After original cache probe 003 completes and verifies, distinct inert
`nvarc-original-qwen3-training-inspect-001` stages and passes exact offline
preflight, with no external calls and no permitted forward/optimizer step.
Plan digest:
`sha256:13aee59319e1745c98138d65fa92ddaa4d62fa04facd6fced4913a866fb93dea`.
It is not submitted while the conservative remaining-resource check fails.

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

The next metadata-only join independently binds every published ordered parent
pair to complete raw input/output groups, without sorting away the generation
direction or choosing among multiple mix/summary groups. All 2,244,042 retained
response rows and 103,223 published members are recounted. The frozen source
`generate_output_grids.py` defaults `--min-solutions-per-puzzle` to twenty;
43,936 published members have no same-order group with twenty retained output
responses. Every such member is in `nvarc_full`. The family breakdown is:

| Published family | Same-order raw output response counts | Published members |
| --- | --- | ---: |
| `nvarc_full` | one group with 10 | 43,874 |
| `nvarc_full` | one group with 11–19 | 62 |
| `nvarc_full` | one group with 20 | 11,950 |
| `nvarc_training` | one group with 20 | 47,299 |
| `nvarc_training` | two distinct groups, each with 20 | 38 |

The other 59,287 members have a twenty-response group. Twenty raw responses
are only a necessary condition for twenty source-accepted programs: source
parsing/removal and dynamic checks are not established by the response count.
For the 38 multiple-group members, the historical selected mix is unknown.
The retained historical CLI, production source revision and completeness of
historical execution responses are also unknown. The current defaults alone
cannot establish the published generation route, nor prove corruption or a
historical execution failure. All parent/exposure bindings are retained.

The bound join is at
`.irisx/nvarc-original/manifests/sdg-published-groups-20261002-001/`.
It completes in 56.220 seconds; a separate 34.616-second reader independently
reconstructs every raw group, SID, same-order/reversed-order mapping and
published binding. Its source snapshot is retained after completion, with
the unchanged-launch timing stated explicitly. Three metadata parser tests
preserve direction/mix ambiguity and reject duplicate/bool SIDs, changed
exposure and duplicate input records. No new generated-code AST analysis,
raw-Parquet read, program execution, teacher/model call, accepted pair or score
occurs. Result SHA-256:
`37ddc4c7ddac498482b6924b031adf714477e2fffcbea9efd5730e9c1df53d1f`;
binding stream SHA-256:
`d9632d61143a742759dad93283f27920f5df3fc67bba1e9ab89f939d04e9d5c8`;
independent proof SHA-256:
`dafaba7addf62618e291f0132f695dbffbccfe38e7f3eb00f885062b8d185f79`.

### Fixed ten-response published-output diagnostic

The first frozen binding is
`nvarc_full/0934a4d8/0934a4d8_00576224.json`, with the original ordered
parents `0934a4d8`, `00576224`. Its evaluation-ancestor, protected-family and
pilot-ancestor exposure remains attached. Its sole same-order raw group is
`mix9/summary5/summary6`, with output SIDs 0–9 in
`outputs/data-00102.parquet`, rows 13,629–13,638. The selection is retained
before execution. One exact Parquet shard is read; all ten completion/code
hashes and the published member hash are checked before any program attempt.
Published member SHA-256:
`c60487d9133bcedf3193e0b37caac1d2b824664491ae089effb7438a0f80fe6f`.

Distinct local `nvarc-original-published-output-replay-001` uses the existing
WSL user/mount/PID/network namespace, read-only chroot and capability-drop
executor. Generated Python never executes on the host. The fixed workload
reserves one trusted isolation canary and ten output programs on each of the
thirty already-published synthetic inputs: 301 total attempts, under
1,800/1,200-second parent/execution ceilings. It does not regenerate inputs,
remove unused source helpers, call a teacher/model, score ARC answers or
change generated programs. Current source minimum twenty output programs is
not met; whole-method completion and accepted-source-pair count stay false/zero.

All 301 attempts return an observation in 85.547 seconds. SID 6 is rejected
on all thirty inputs: its line 127 calls `seed.flat.tolist()`, with retained
`AttributeError: 'numpy.flatiter' object has no attribute 'tolist'`. That
program is preserved without repair. The other nine SIDs produce 270 legal
nonidentity grids, every one equal to the published output for that input.
Every input has a 9/10 majority and the same nine consistent SIDs. Invoking
only the pinned source's pure 8/12/4 filter on these returned grids produces
thirty diagnostic pairs equal to the published pairs. This demonstrates one
partial output-program/filter route, not historical teacher parity or the
missing twenty-program precondition. No hidden-answer or ARC quality claim
follows from the synthetic-output comparison.

The independent reader recounts all reservations, result digests, legal grids,
majorities and global SID intersection without another program execution.
Three tests reject insufficient globally consistent programs, identity or
uniform outputs, hidden failed-prefix attempts, changed workload ceilings,
relaxed filtering and expanded material inventories. Its second proof has
the same content/digest as the first proof. Local evidence is retained under
`.irisx/nvarc-original/runs/nvarc-original-published-output-replay-001/`.
Plan digest:
`sha256:21602c38e3e0b1a30c7fc6868efa2fe760c3033a3b7ee9d2737d86203da8a15d`;
result SHA-256:
`146420aa2156143a741cc961ca8b6fde74ccd4e98a696b608fc7f98cd176eded`;
independent proof SHA-256:
`98a678d18b60165fb1de1ac876fb668667b04e234d27d5f85c3da4969a934a68`.
The subsequent `python tools/repository_check.py --all` passes all 368 tests
in 250.140 seconds, with four optional-dependency skips. Validation log
SHA-256: `c2e2d805ac52840774fbd7ac685edd64174d2554e81e6aeda62eb29c583a9129`.

### Original static parser and helper cleanup

The unchanged Git-verified `SDG/scripts/parser.py` now runs against the two
fixed retained groups using compatible
[tree-sitter 0.23.2](https://pypi.org/project/tree-sitter/0.23.2/) and
[tree-sitter-python 0.23.6](https://pypi.org/project/tree-sitter-python/0.23.6/).
These historical SDG package versions are unknown; the selected versions
establish only current-source API compatibility. Both Windows wheels are
verified against exact primary PyPI version metadata and installed offline.
The first acquisition retained one wheel before a metadata connection reset;
its failed ledger remains frozen. A distinct acquisition carries those exact
bytes and retains the second wheel, with no paid or GPU request.

The first static audit and its source snapshot remain frozen. The second
adds closed runtime-material verification and independent Python AST
comparison. It completes in 0.985 seconds, parsing the prior fixed input
program and all twenty plus ten output programs, with zero generated-program,
teacher or model execution. The twenty-response group satisfies the current
source's sequential parse/cleanup/entry precondition for all twenty programs.
Only SID 5 changes text: the source removes trailing comments, with no function
removed and no Python AST change. The ten-response group's programs are all
byte unchanged after source cleanup; its twenty-program precondition stays
false. Both fixed groups preserve their original parents and exposure.

This is a static equivalence observation for the previously replayed programs;
it does not add dynamic outcomes or qualify all raw groups. Literal contract
canaries confirm that generated top-level text is parsed without execution
and that the source's own cleanup-regex `AttributeError` is retained rather
than repaired when a first unused helper lacks the expected preceding block.
The latter is an artificial fixture, not an observed archive failure.
Evidence is at
`.irisx/nvarc-original/manifests/sdg-source-parser-20261002-002/`.
Parser source SHA-256:
`28da4f039e1e308f4cb31543e8875403045ce376425e488ed964f535649cfb04`;
result SHA-256:
`bab6e2fef90f1109af5c1b221404aadb51cb2817f819923f00257b6f0d8f3c86`;
literal contract proof SHA-256:
`a3ae91701e1e6c65371301369c7ce3026f1b2f4e1146ad5d7bff51bef8d625cc`.
An independent default-Python AST recount covers every cleaned/original output
program without tree-sitter queries or generated-program execution; proof
SHA-256: `d93d5b1fe2db6b04fb02095fae0b85b2ba35c83d380f95b37af81ae95e7620c7`.
The full repository check passes 368 tests in 279.611 seconds, with four
optional-dependency skips. Log SHA-256:
`bd2fb88a45f6b3be223990e239bec508e553c9c379ab6a4dc849e5e797791153`.

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
The explicit public version-18 page was also unavailable to the web reader;
its separate acquisition ledger retains one read, zero source bytes and no
own-kernel query. Exact historical v18 remains unknown.
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
Full validation 019 covers the tuple-output repair and first-layer operator
guard/reader: 362 tests pass in 259.663 seconds with four skips, SHA-256
`67dde869ff8d6e22d34fc0e62ab51afed9e76f27ef5166aaea143ce9b928a5a3`.
Three additional actual tiny CPU tests pass: all 21 first-layer operator
forwards under the real entry guard, precision/method/storage restoration
after injected failure, and real ModelOutput/cached-tuple extraction. The
fixture uses dense CPU attention, two-layer random weights reduced to one
layer and modern compatible dependencies; it proves no original CUDA or
native-varlen numerics. Strict log SHA-256:
`2b046ce0d27aa6f29760fcbab8ad7e198bd9547b305e7c1fed9c472059549728`.
Full validation 020 covers the complete published-group metadata join:
365 tests pass in 294.475 seconds with four skips, SHA-256
`7c711d2dc18779dcc06a50bd4a730c75f25a4233ba770499278c70b44b5623f2`.

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
The official competition's
[upgraded-accelerator description](https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-2/overview/upgraded-accelerators)
is now checked through its retrievable search-index text. It documents twice
the older-machine quota rate and reserves the right to increase that rate.
The index was crawled four weeks earlier; a direct page open supplies no
extractable lines. This is retained as primary documentation, not verification
of this account's actual multiplier. The current packages retain the more
conservative four-times local planning reserve. The existing 10,800-second
compatibility long-TTT proposal needs 21,600 quota seconds even at the
documented two-times rate, beyond snapshot 006's remaining 11,332.267. Its
submission remains blocked by both runtime and resource prerequisites.

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
at that local implementation checkpoint no GQA-variant package was staged or
submitted. The subsequent separate first-layer diagnostic below includes a
native-GQA mode; the earlier probes and existing full-gradient prerequisite
remain on their exact repeated-KV backend.
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

Distinct private
[`nvarc-original-qwen3-probe-003`](https://www.kaggle.com/code/danielwuu/nvarc-original-qwen3-probe-003)
is a first-layer operator diagnostic, not a full 4B solver. It byte-verifies
the same compact base, removes decoder layers 1–35 without changing retained
weights, and verifies all thirteen remaining named parameter shapes/dtypes.
Seven modes compare independent forced Flash SDPA, repeated-KV packing and
native-GQA packing, BF16 reduced-precision reduction enabled/disabled, and a
separate FP32 linear-compute diagnostic with outputs cast back to BF16. The
FP32 diagnostic changes arithmetic only; it never changes stored weights or
the earlier whole-model acceptance gate. PyTorch's official
[numerical-accuracy notes](https://docs.pytorch.org/docs/2.10/notes/numerical_accuracy.html)
describe batching and BF16 reduced-precision numerical effects; these are
hypotheses to test, not a diagnosis of the observed mismatch.

The bound workload is exactly 21 partial-model forwards and 220,878 input
tokens, one retained decoder layer per call, zero backwards/optimizers/
generations/teachers, four distinct BF16 L4s and one rank-zero worker. It
retains every sixteen-row logit and three fixed token samples per row at
sixteen operators, without extra model calls. The parent/child limits are
1,200/900 seconds. The independent reader rehashes every member, recounts
actual completed-call prefixes, verifies the partial parameter subset and
precision flags, and recomputes every operator difference from raw FP32-LE
vectors. It always leaves whole-model qualification false. Rehashed vector,
cost, precision, parameter, hardware and full-model-claim faults are rejected.
Actual tiny CPU hook/precision/guard tests pass; the local dense attention
fixture makes no CUDA varlen claim. Version 1 (kernel ID 136792365) was
accepted after one reserved private push. Its sixth backed-off status returned
COMPLETE, and its sole terminal retrieval is consumed.
Plan digest:
`sha256:c06b4737feebe271ec410fe34e38eba34705a937e6c9c152c44585b058f9a3f3`;
receipt SHA-256:
`867493cf28426cf5c4330adbaf28847f03434bb76ec3174f79cabb1101f882c0`.

All 21 partial-model forwards and 220,878 input tokens independently verify
on four distinct BF16 L4s. The session takes 129.524 seconds. Archive SHA-256
is `3f54f470163a0b35a6baba75c3ebd57f9afca021542864b6768a9b3a09fb0f07`;
independent proof is
`a2514650b8b87ca7c0eddd53329e4a77b0216d4afd17edc053c6a63890c7e417`.
All four BF16 packed modes have identical retained operator comparisons and
first differ at Q projection (maximum 0.0078125); changing native GQA or
BF16 reduced-precision reduction does not repair this observation. K/V
projection differences are 0.00390625, K norm reaches 2.0, layer-0 output
0.0625 and the final logits 0.125. FP32 linear compute still first differs
at K projection (0.0000019073486), with final-logit difference 0.125.
Independent and packed timings are cold, partial-model observations; they
do not supply whole-model training throughput. Whole-model qualification
remains false and there are no backwards, optimizer steps or generations.

Distinct `nvarc-original-qwen3-probe-004` is offline verified and accepted as
private version 1, kernel ID 136804856. It retains all 36 decoder layers and all eight complete
source samples. Every Linear runs one unchanged BF16 GEMM per whole sample;
native repeated-KV varlen attention, positions, causal boundaries and the
0.25/0.03 whole-logit gate stay fixed. There are exactly 13 outer forwards,
94,706 input tokens and two tiny native-varlen backwards, with no optimizer,
generation, teacher, export or ARC scoring. Its 4,078 counted segmented GEMMs
are forward calls; the two separately reserved tiny backwards also perform
their ordinary autograd arithmetic. Full-model gradients are not part of
this probe. Parent/worker limits remain 1,200/900 seconds on four distinct
BF16 L4s and one model worker. The independent reader recounts all 55 retained
vectors, each tiny parameter gradient, full logits and sample isolation.
An honestly failed numerical gate remains complete but unqualified; rehashed
numerical, budget, precision, shape, GPU and scope faults are rejected.
The real tiny CPU control-flow fixture passes all 13 calls, two backwards,
36 layers and restoration checks; its dense CPU attention and width-32 model
do not qualify the width-2,560 CUDA gate. The primitive additionally checks
unequal sample gradients and checkpoint recomputation. Plan digest:
`sha256:963c2f5813380fefff7fd04f590b6ebb9729d1f9d0db446645db52876537819e`.
The sole push completed at 16:35:55 UTC on October 2; receipt SHA-256
`32dc0199ed575f37f01105ee6e08e77fb45fa5bfd9b2d678abf1536f204c52a0`.
Its first backed-off status returned COMPLETE and its sole terminal retrieval
is consumed. All 76 listed members verify. Archive SHA-256
`b86559a95b7d35d61c4f85d9f7d0f23065bcc213ffe982a6b63cd1f66604b52d`;
independent proof
`5287640750119929edf156e5b99e0c40cdac6b425c193e78c65514615262dac1`.
All 13 forwards/94,706 inputs and both tiny backwards return. Every one of
504,864 full logits and all 38 sampled layer states match forced independent
Flash SDPA bitwise across all eight samples. Tiny gradients pass the fixed
0.006/0.06 gate; changing the first sample leaves all later logits bitwise
unchanged. This satisfies the bounded native-varlen numerical prerequisite
with the segmented-linear variant, not the previously failing merged GEMMs.
Cold independent/packed forward timings are 6.942/8.117 seconds including
diagnostic capture. They establish no throughput improvement or full-gradient
training rate. The session takes 406.191 seconds, with 54.044 worker seconds;
zero optimizer, generation, teacher, export or scoring occurs.

After the operator diagnostic's terminal retrieval, quota snapshot 008
reconciled 10,103.497 remaining free seconds with no provider reservation or
pay-to-scale. Native zero-work inspection 001 was then accepted as private
version 1, kernel ID 136800150; its plan is
`sha256:13aee59319e1745c98138d65fa92ddaa4d62fa04facd6fced4913a866fb93dea`
and receipt SHA-256
`563456397d7dda9420813614c9f45a191ad0c871b2061100998cdd75f4453924`.
Its second backed-off status returned ERROR. The sole terminal retrieval
retains archive
`ea4149e992b11a8de5864b03537db55e412937d837f84c056c707a8c78227d19`.
The 214.138-second session verifies dependencies/materials and installs the
zero-work guard before native import, then rejects the original class AST
hash before loading a model or constructing an adapter/Trainer. Its source
bytes are unchanged; the local Python 3.12 AST digest includes empty
`type_params` fields, whereas provider Python 3.11 omits that nonexistent
field. No model forward, backward, optimizer construction/step, generation,
teacher or scoring occurs. This is a transport verification error, not an
original Trainer failure or long-task observation.

Distinct inspection 002 is offline staged with only a reviewed AST rendering
repair: insert an empty `type_params` field when absent and show empty fields
explicitly. Both frozen 3.12 hashes match on the local runtime, and an
artificial 3.11-field fixture also matches while a changed method fails the
binding; nonempty type parameters are rejected. Original source/material
bytes, hashes, all 128 source views, zero-work guards and 1,200/900-second
limits remain fixed. The consumed 001 package still passes exact legacy
preflight and its worker bytes are unchanged. New 002 plan:
`sha256:f43ea20828233c5429c7de19a0809d13f6e0f4bc07f45b98cb4ad6eb5546de79`.
The sole push completed at 16:36:01 UTC on October 2 and accepted private
version 1, kernel ID 136804867; receipt SHA-256
`132addb12181a60f1866ae403615b391a76584d1e341f520d66f614e530b83d6`.
Its first backed-off status returned ERROR and its sole terminal retrieval is
consumed. Archive SHA-256
`4f81fb87e951e5468fd26e7c9fcfd55c90889a9b61758764f1b6c5a58b2e5883`;
independent proof
`bd4d53164018f9891f97b8823e6fefce17812bd70e48e47e6d19a609afc6569b`.
The 208.543-second session again stops before model loading. The worker
renderer replaced the AST expression after inserting the helper, changing
its old-API fallback to a recursive self-call. Python 3.11 rejects the new
`show_empty` keyword and then reaches RecursionError. This is an agent worker
generation error, not an original source or Trainer failure; no model,
backward, optimizer, generation or teacher work occurs.

The consumed inspection 001 independent proof SHA-256 is
`193ff6c40417f6e7b2e5eb32a8ce3a4e9268d0e9bd5a9b74f9d97e83e567518f`.
The separate AST repair proof is
`4d655627c4d1e6a117873e8b9796b66e40e0852c4e19d3b10e91214acff0afba`;
its missing-field fixture is explicitly artificial, not a Python 3.11 native
Trainer observation. Fresh account snapshot 009 independently reconciles
9,610.329 free GPU seconds, zero provider reservations and pay-to-scale False.
The two new 1,200-second packages require 9,600 seconds at the conservative
four-times reserve; no original-scale training is admitted by that budget.
Full repository validation 023 passes 374 tests with four optional skips in
222.993 seconds; log SHA-256
`08041ab344e5069f2f89dc1842639a65eca3564349bdf70ab49efc44c574f831`.

Distinct inspection 003 replaces only the original AST expression before
helper insertion. A test executes the generated reviewed worker against a
literal old AST API: frozen 002 reproduces the recursion and new 003 retains
the correct digest. Both consumed packages retain exact legacy preflight.
New plan:
`sha256:5ac07ec65e30d1a67f9b7ada571e36edb5a30791515995fc162ef57a092c99aa`.
Fresh quota 010 reconciles 8,270.497 free seconds with no provider reservation
and pay-to-scale False; 4,800 conservative seconds are admitted for this
unchanged zero-work 1,200-second envelope. Its sole push was accepted as
private version 1, kernel ID 136806318 at 16:50:09 UTC on October 2;
receipt SHA-256
`7d09bebffcd65d6ff626bb426a970f3ad83a2715416fdd37028687857044570e`.
The second backed-off status is COMPLETE, and its sole terminal retrieval is
consumed. Archive SHA-256
`dfb30e1fdbc2816920a7a39eefb06af881f8a20cc093570b1291455c44c7f7d4`;
independent proof
`b7fc6e38e97e1112c45c778c296394737991398d809457305a87defbd2b54fa1`.
The 704.831-second session verifies all sixteen native versions, the
528,564,224-parameter BF16 adapter topology, detached baseline/reset, and
actual Trainer context 8,192. All 128 prepared input/label vectors match the
source (955,392 inputs and 476,160 supervised tokens), and checkpoint flags
are enabled on the model and all 36 layers. This qualifies native long-task
TTT preparation. Guards observe zero model forwards, backwards, optimizer
construction/steps, generations or teacher calls; no TTT epoch has run.

The exact qualified segmented numerical variant is now propagated into a
new offline `nvarc-original-qwen3-packed-step-001` candidate. It preserves
the full first global-256 source batch: 916,739 real input tokens, 403,115
supervised tokens, 31 real physically packed forwards and one connected dummy
across four FSDP ranks. Every rank verifies actual input IDs, reset positions
and causal offsets before root model entry and retains completed-call prefixes.
Each per-pack segmented Linear scope spans the nonreentrant checkpoint
backward and is restored before CPU accumulation or a different-length dummy.
All 36 layers, unchanged source Adam/clip/schedule and FP32 owned CPU shard
accumulation remain. The full step uses the acquired base's tying; historical
NeMo parameter tying remains unknown. No export, generation, teacher or ARC
score is included. Independent reading verifies both source/material bindings
and every actual rank prefix, real/dummy layout, segmented checkpoint policy,
CPU state residency and changed global weight fingerprint.

This candidate caps parent/worker time at 1,800/1,560 seconds instead of the
earlier unsubmitted 4,500-second draft. Its scientific batch is not reduced.
Completion of one whole global step is still mandatory for a throughput
observation; timeout preserves only a failed prefix. The cap is an engineering
free-resource bound, not a prediction derived from inference timing. Host
available memory and container limits must both leave at least 140 GB before
model loading. Its initial offline preflight passed. This 001 proposal remains
unsubmitted: quota snapshot 011 reconciles 6,746.535 free GPU seconds, less
than its conservative 7,200-second reserve. Preserve its inert bytes and plan:
`sha256:898a62650f878b17a655d84ef0c2f1eeca6319bc4f9d13299d1337845bde16ae`.
Actual tiny CPU Qwen3/Adam and every optimizer moment match an independent
isolated oracle with checkpoint recomputation. A separate real/dummy test
uses artificial control collectives only, executes actual NN/backward/Adam,
and verifies both scope lengths and restoration. The existing real two-rank
FSDP accumulation/Adam differential still passes. These are CPU regressions,
not a 4B GPU gradient or training-rate observation.

Distinct offline `nvarc-original-qwen3-packed-step-002` caps parent/worker time
at 1,500/1,260 seconds. It retains the same complete global-256 batch, source
AdamW recipe, one-step completion gate and all resource/numerical checks.
Its conservative reserve is 6,000 seconds; no throughput claim follows if it
times out. Its package preflight passes with plan
`sha256:feb174a069a90e388422a0f710bbc90a9d80936eff84c247fd6dbf5a945f7550`.
Full repository validation 025 passes 378 tests with four optional skips in
285.981 seconds; log SHA-256
`aee0ef3382ddfc9e771a075628529e7398caca01cacecf2076965a9bad24dcc9`.
Fresh snapshot 012 independently reconciles the unchanged 6,746.535 free
seconds, zero reservations and disabled pay-to-scale. Its admission reserves
6,000 conservative GPU seconds locally, without a provider reservation;
admission SHA-256
`0ba2b393c08c78921110184ad5d3ca783fafef426bea8745b37d2474d66f476e`.
The account's actual multiplier is unverified. One distinct private push may
now proceed; no throughput or original-scale completion is presumed.
The sole `packed-step-002` push was accepted as private version 1, kernel ID
136810446 at 17:36:16 UTC on October 2. Receipt SHA-256
`10f361e23136d28af3890b85614a9f8fa431bcae5e797cf0b228e68818eb0f20`.
Its reviewed code is committed on main as `443f633`. The first backed-off
status is COMPLETE; its sole terminal retrieval is consumed. All 29 closed
members and the exact package bindings independently verify. Archive SHA-256
`4d09d84a0227370def58f52e26a62736fa2636a8e2f8be2737342d3eae992583`;
independent proof
`f61c126d7230d84036ba3204b979219d15eb341b309f64e7ae672ea4685853d9`.
Four distinct BF16 L4 ranks complete all 32 reserved actual root forwards,
one full source AdamW step and finite CPU FP32 state checks. Every gradient
shard is covered, and the global weight fingerprint changes. All ranks agree
on token mean loss 0.20310668831755904, pre-clip norm 3.020477533340454 and
initial source LR 1e-6. The 916,739 real inputs and 403,115 supervised tokens
are complete; no source row is truncated or removed. The one cold step takes
446.776809 seconds (2,051.895 aggregate input tokens/second), including
checkpoint recomputation, CPU shard accumulation and Adam. This is one timing
observation, not a sustained rate or historical NeMo comparison. Worker/session
times are 467.787/593.991 seconds. Peak allocated CUDA memory is 13.898 GB per
rank maximum; peak reserved memory is 22.605 GB. Actual host/container
availability is 184.617 GB against the 140 GB gate. Each rank retains 3.634 GB
FP32 owned parameters and gradients, approximately 7.267 GB optimizer state
and 22.781–23.355 GB process RSS. No checkpoint/export, generation, teacher
or ARC scoring occurs, and 12,716-step SFT remains uncompleted.
Full repository validation 024 passes 376 tests with four optional skips in
255.461 seconds; log SHA-256
`665d0632818eaf6b629fe8c1c1a9eea913ea3531104fea0c218a11e5e3ce2790`.

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

### Native TTT optimizer and scalar schedule audit

Four further public dependency files are acquired once from the same exact
script-version 272622465: Transformers optimization, Accelerate optimizer and
accelerator, and PyTorch gradient clipping. Their closed byte-bound inventory
is independent of the consumed private inspection's 37 files. The new audit
re-verifies that inspection, binds all four acquired files, and parses the
existing exact TrainingArguments/Trainer/Adam sources. It executes only two
reviewed scalar arithmetic functions with no ML package import, model forward
or optimizer construction. Proof SHA-256:
`e519d70b696c9bbcb76102a53c4cde3a3cd68bf560a8769879f1856e2eec4031`.

For the fixed 128 views, native warmup is ceil(128 × 0.1) = 13. TTT AdamW
defaults are betas 0.9/0.999 and epsilon 1e-8, with learning rate 5e-5,
weight decay 0 and gradient clipping 1.0. They differ from the full SFT
recipe. The exact Transformers file defines the cosine helper twice; Python
uses the final module-level binding with default min_lr_rate 0.0. All 129
scalar schedule indices verify. The first optimizer learning rate is 0, the
last used rate is 9.327968452232938e-9, and the post-epoch rate is 0. A future
completion guard must permit the first step to update moments without moving
weights. The original Adam source initializes both moments with zeros_like
parameters, without an explicit dtype cast. Two BF16 moments for the observed
528,564,224 trainable parameters would occupy 2,114,256,896 bytes; this is
source-derived storage, not measured native optimizer residency or peak VRAM.
Actual native forward/backward, full epoch, memory/time and reset after training
remain unobserved. Tests reject unsafe scalar calls/imports and retain the
final module-level binding instead of a nested or earlier definition.

Full repository validation 026 passes 380 tests with four optional skips in
240.034 seconds; log SHA-256
`73b70a23f6af88709c33862900816dffb5f62848315a18090564ffe8928c9036`.
After the terminal retrieval, quota snapshot 013 reconciles 5,523.863 remaining
free GPU seconds, zero provider reservations and disabled pay-to-scale. The
existing inert compatible 10,800-second long-epoch proposal still needs a
43,200-second conservative reserve and is not admitted. Native preparation and
scalar recipe are qualified; an actual native full-epoch transport remains
separate work and cannot reuse that compatibility identity or configuration.

### Native complete-epoch transport

The native epoch worker uses the original, hash-bound Trainer classes and
exact published untied SFT checkpoint under original Docker/dependency versions.
All 41 source/metadata files, 128 views, BF16 528,564,224-parameter layout,
actual native Trainer origins and checkpoint flags are bound. Preparation
remains under the zero-work guard. Each exact input/label pair is consumed once;
each Trainer microstep permits one root forward/backward before one actual
AdamW step. Every finite gradient, source clipping and exact 129-index native
learning-rate vector are checked, including the first zero-LR step. No
generation, verification, teacher or export is allowed. Complete acceptance
requires every row/step, finite BF16 Adam moments, changed saved state and exact
restoration of all seeded baseline tensors. Optimizer tensor state and
Accelerate optimizer/scheduler references are cleared before adapter reset.
Atomic prefixes retain completed versus reserved work on failure. Parent/child
time limits remain hard, including a terminal archive reserve.

The first three packages are inert, unsubmitted local proposals. Initial 001
needed complete 41-file plan binding; 002 needed explicit optimizer-state
discard. Both bytes remain retained. Corrected native 003 passes preflight:
`sha256:bb34ecdc641d85bb024ec59b1d9e9c6e8bc7632129680b0743dde1ef284b0454`.
Its 10,800/10,500-second envelope needs 43,200 conservative GPU seconds;
snapshot 013's 5,523.863 seconds does not admit it. Its no-submission gate is
`7e416ef81859e1718f4bba73509290d43fc74f547fca6e34e6582f3f0947b9a2`.
No execution journal or provider request exists for these proposals.

Distinct native 004 preserves the same complete scientific workload and gates
under a 1,300/1,000-second parent/child envelope. Its preflight passes:
`sha256:211dc7053e473e0d2003ac1116aff5b6c78ccd92d2c62b4a14ffe5706f278549`.
This is an engineering free-budget cap, not a runtime prediction. Timeout
retains a failed prefix, never a completed TTT epoch. Snapshot 014 reconciles
the unchanged 5,523.863 seconds, zero reservations and disabled pay-to-scale;
the candidate needs 5,200 conservative seconds. Submission waits for full
validation and exact admission. No original-clock or ARC quality claim follows.

Two actual CPU NN/AdamW tests pass in 2.766 seconds: zero-LR moment updates,
subsequent changed weights, exact call dependency/restoration and rejection
of extra/altered rows or unreserved optimizer entry. These are controls, not
original 4B/Unsloth training. Independent-reader tests use explicitly artificial
digest archives with preflight mocked; they exercise complete/failure prefixes
and reject rehashed count, mask, moment and reset faults. They cannot qualify
a real package/model. Full repository validation 027 passes 382 tests with
four optional skips in 241.675 seconds; log SHA-256
`876ef3328ebd296f057a42ab3c1829a51acd18ba8abc230f7be3c2e10c19e26a`.
The optimizer-discard repair additionally passes current-source compilation
and distinct 003/004 offline package gates.

Full repository validation 028 passes 382 tests with four optional skips in
250.756 seconds; log SHA-256
`f3098f8cb7fcab513030042e3480f9ee2a0869175736ddfb2f43494bdf172040`.
Snapshot 014's exact one-push admission SHA-256 is
`881f14149eb32e4c349676791617b217cd09de9fe9d5b207264f71f8aa225acb`.
Reviewed native-epoch code is committed on main as `ebe7cbe`. The sole native
004 push is accepted as private version 1, kernel ID 136815175 at 18:36:03 UTC
on October 2; receipt SHA-256
`600f94f471ce42a822b1bc16b310c0933425fabaf17dc539f0d376991fab77ee`.
Runtime is pending backed-off monitoring and one terminal retrieval. No
completion, native gradient/memory or quality observation is presumed.

An additional actual CPU BF16 NN/AdamW control retains BF16 parameters and
moments without a master-parameter cast. It verifies the zero-LR first step,
subsequent changed weights, exact two-moment byte counts and explicit state
discard. All three strict NN controls pass in 1.771 seconds under local
Torch 2.12.1 CPU. This adds no original Unsloth or 4B runtime evidence and
changes no submitted native 004 bytes.

### Native 004 terminal prefix and same-platform schedule repair

The second backed-off status check observes ERROR at 18:56:28 UTC on October 2.
The sole terminal retrieval is reserved and consumed, retaining one closed
archive and provider log. Archive SHA-256:
`a48d861ea3abd6f9db53cbc84f361d9dc67e03bf2032e409a743668443979f80`.
The initial cost-prefix proof remains immutable. The strengthened independent
reader additionally verifies all actual preparation/material/worker evidence
before accepting a training failure prefix; its distinct proof SHA-256 is
`11e8c1f62bc122aec4f3b0ada30aaf51cdbb7b82d8b840b51675dadbb9bf4629`.
All 28 data members match; four distinct BF16 L4s, the exact native worker,
41 source/metadata files, published model, adapter topology, Trainer origins,
checkpoint flags and all raw prepared-token/label vectors verify.

Native 004 completes 50 outer forwards and Trainer backwards, 373,200 inputs
and 186,000 supervised tokens. One actual AdamW is constructed and 49 updates
complete; every admitted update covers all 506 finite gradient tensors under
the source clipping and optimizer recipe. The 50th backward returns, but its
optimizer entry is denied before reservation/update because its rate differs
from the locally precomputed exact float. The parent terminates after
685.495 seconds with CalledProcessError; retained worker stderr identifies
`exact native cosine learning rate required`. This is a guard failure, not a
timeout or zero-work attempt. No generation, teacher, export or scoring occurs.
Full 128-step completion, final moment inventory, trained-state reset and native
peak memory remain unverified. The push and sole retrieval are consumed.

A reviewed scalar-only replay of the exact pinned cosine source executes on
local Windows and Ubuntu, without ML work or network calls. Its first differing
index is 49: Windows `3.885374458130437e-5`, Linux
`3.885374458130438e-5`, exactly one ULP apart. Indices 96, 102 and 104 also
differ, by at most three ULPs. Proof SHA-256:
`c30bf3a1ba4da21d324c01e2e9e21934e692b26f728ebe4ecc8aef2bf5649f54`.
The first local script has a keyword-only call error and is retained as an
inert failed fixture; the corrected replay is distinct. Native 004 did not
retain its rejected actual rate, so the cross-platform cause remains a
strongly supported inference, not a recovered Kaggle float.

The new v2 transport leaves the consumed v1 worker/budget bytes unchanged. It
binds the same two exact source functions and computes all 129 scalar rates
on the worker platform. AdamW must equal that local oracle exactly; there is
no tolerance at optimizer entry. The frozen Windows reference permits at most
four ULPs solely for cross-platform scalar verification, with exact zero and
warmup/maximum rates. Generated programs retain the actual rejected rates and
failure timing/peak memory. The reader binds the helper and local rate vector,
then requires every admitted optimizer rate to equal that vector exactly.
Source recipe, view count, model calls and acceptance of complete epochs stay
unchanged. An actual pinned-source replay through the new helper verifies on
both local platforms: Windows maximum difference 0, Linux 3 ULPs. Its proof
SHA-256 is `69bbbdd9131197328d6e9c8756c01f00b3ccde9ed2e36022cd779442cd4d60e0`.
These scalar controls do not add native 4B work.

Intermediate native 005 is an unsubmitted rendering before unused-import
cleanup; its bytes remain inert. Final distinct native 006 passes preflight:
`sha256:ddb90fdbf28fb7bd6d0402161e97d508f5289909e53d4fbcd199e1a77eee681a`.
It retains the full 128 views, 955,392 inputs and 476,160 labels under a
1,500/1,200-second parent/child envelope. The larger finite envelope is an
engineering bound, not a completion prediction. Fresh quota snapshot 015
reconciles 4,063.873 remaining free GPU seconds, zero provider reservations
and disabled pay-to-scale. A conservative four-GPU reserve needs 6,000 seconds;
the exact no-submission gate SHA-256 is
`2006c9f63caedd53bf04ad2d62b3e71fbc6cec3c376df1542c13b13b9d8a08b3`.
No execution journal, push reservation or provider request exists for 005/006.
The remaining free quota does not admit another complete-epoch attempt under
these bounds; reducing the scientific workload would not close this gap.

Six focused scalar/reader tests pass, including rehashed failure preparation,
rate, cost and source faults. Four actual CPU NN/AdamW strict controls pass in
1.813 seconds, including the rendered v2 budget's rejected-rate capture before
any optimizer state/update. These use a tiny CPU model, not native Unsloth or
an original 4B epoch. All earlier immutable native 003/004 packages remain
offline-verifiable; no active kernel or monitoring remains.

Full repository validation 029 passes 386 tests with four optional skips
(242.270-second test suite; 245.225-second complete command). Log SHA-256:
`db50410cb54c0615c37ded640b899705febf4a898042a7f9324df330dffeb0a4`.
Consumed native 004, inert native 003 and final inert native 006 also pass
their current exact offline package gates. Reviewed work remains on main;
no git push, paid execution, new Dataset, teacher call or ARC scoring occurs.
