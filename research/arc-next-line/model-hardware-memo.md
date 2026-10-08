# IRIS-X next-line model and hardware audit

Date: 2026-10-08 UTC. Scope: read-only primary-source research, exact public model metadata/tokenizer acquisition, local artifact contracts. No model weights downloaded, model executed, GPU admitted, machine provisioned, credential changed, paid service purchased, or competition submission made.

## Decision in brief

1. Keep the requested order: **ibm-granite/granite-4.2-8b**, **Qwen/Qwen3.5-9B**, **ByteDance-Seed/Seed-Coder-8B-Reasoning**. All exact names exist publicly and are ungated at the captured revisions. Choose the eventual model using measured task-disjoint training/validation and four-L4 deployment results. Priority is a testing order, not a claim of ARC superiority.
2. Begin with **Granite BF16 + LoRA**, full official vocabulary, native Hugging Face attention with SDPA, activation checkpointing and one-device training. The training target is **g4-standard-48 with one RTX PRO 6000 Blackwell Server Edition**. It is not a four-GPU training machine.
3. Use a source-verified common Transformers **5.8.1** environment for all three rather than blocking Qwen behind an older Granite-compatible library. PyTorch **2.8.0+cu128**, PEFT **0.21.0**, Accelerate **1.10.1**, Tokenizers **0.22.2**, Safetensors **0.8.0**, Hugging Face Hub **1.32.0**, Jinja2 **3.1.6** are a concrete proposed tuple. A complete transitive wheel/hash lock and authorized GPU probes are still required. This memo does not mark that tuple runtime-validated.
4. Submission remains **four independent L4s**. Preserve portable BF16 source/adapter exports. Qualify four independent replicas first; test tensor-parallel alternatives only if a measured memory/latency need justifies them. Four 24-GB devices do not create a 96-GB allocation domain.
5. Do not reuse the compact grid-only vocabulary/head from the prior NVARC line for a language/code/tool agent. It cannot represent ordinary program tokens, instructions and tool traces. Keep the old method as a separately named comparator.

## Exact upstream identity and lock

Machine-readable deliverable: `research/arc-next-line/model-source-lock.json` in the new repository. It contains exact repository revisions, complete runtime-relevant file URLs, sizes and SHA-256 values, captured configs, dtype counts, tokenizer/template facts, proposed package wheel identities, and hardware constraints. A duplicate is retained beside this memo.

| Priority | Exact official repository | Pinned revision | Parameter metadata | Source storage |
|---|---|---|---:|---|
| 1 | ibm-granite/granite-4.2-8b | f8de16cdcdbc6c779ca517604e050d82cc119e44 | 8,791,592,960 | BF16 |
| 2 | Qwen/Qwen3.5-9B | c202236235762e1c871ad0ccb60c8ee5ba337b9a | 9,653,104,368 | 9,653,100,528 BF16 + 3,840 FP32 |
| 3 | ByteDance-Seed/Seed-Coder-8B-Reasoning | 9927b7724deb1f8189da1cc6a50328dfb885d60d | 8,250,462,208 | FP32 |

Authority is upstream API at `/api/models/{repo}/revision/{sha}?blobs=true`. Weight SHA-256 comes from upstream LFS object IDs; these are not hashes self-attested by a local material directory. For non-LFS files, downloaded byte SHA-256 was independently bound to the upstream Git object by recomputing `SHA1("blob " + size + NUL + data)`. All 14 Granite, 15 Qwen, and 14 Seed Hugging Face artifacts, including model cards, are locked. Supplemental Granite/Seed license files are separately pinned to official Git repository commits because their model repositories do not contain LICENSE files. Config/tokenizer/template files are locally available; no weight shard is.

Pinned metadata: [Granite](https://huggingface.co/api/models/ibm-granite/granite-4.2-8b/revision/f8de16cdcdbc6c779ca517604e050d82cc119e44?blobs=true), [Qwen](https://huggingface.co/api/models/Qwen/Qwen3.5-9B/revision/c202236235762e1c871ad0ccb60c8ee5ba337b9a?blobs=true), [Seed](https://huggingface.co/api/models/ByteDance-Seed/Seed-Coder-8B-Reasoning/revision/9927b7724deb1f8189da1cc6a50328dfb885d60d?blobs=true).

### Granite: exact architecture, not a Granite 4 hybrid substitute

This checkpoint declares `GraniteForCausalLM`, `model_type=granite`: dense decoder-only GQA, 40 layers, hidden 4096, MLP 12800, 32 attention heads and 8 KV heads, untied input/output embeddings. Vocabulary rows: 100352; BOS 100283; EOS/PAD 100257. Preserve `attention_multiplier=0.0078125`, embedding/residual multipliers 1, logits scaling 1, RoPE theta 10000000. A conversion to a generic Llama class can silently change attention scaling. Configured context is 131072; long-context marketing does not authorize silently raising that limit.

IBM identifies release date 2026-08-25 and Apache-2.0 licensing. This is the reasoning/post-trained model, not the 4.1 base checkpoint. Its public training description includes code/tool/agentic post-training; these are helpful prior capabilities, not evidence of ARC clean-room quality. [Pinned config](https://huggingface.co/ibm-granite/granite-4.2-8b/blob/f8de16cdcdbc6c779ca517604e050d82cc119e44/config.json), [IBM release description](https://huggingface.co/blog/ibm-granite/granite-4-2).

**Verified inconsistency:** upstream `model.safetensors.index.json` reports `metadata.total_size=16,761,102,336`, while official BF16 parameter metadata implies 17,583,185,920 tensor-payload bytes. Four upstream shard files total **17,583,228,032 bytes**, consistent with the latter plus headers. Preserve the index unchanged; independently inspect shard headers and aggregate actual tensor sizes. Never size VRAM from this index field. [Pinned index](https://huggingface.co/ibm-granite/granite-4.2-8b/blob/f8de16cdcdbc6c779ca517604e050d82cc119e44/model.safetensors.index.json).

### Qwen: exact dense hybrid multimodal checkpoint, with a native text path

The official post-trained checkpoint is `Qwen3_5ForConditionalGeneration`, `model_type=qwen3_5`. The text component is `qwen3_5_text`: 32 layers, 24 Gated DeltaNet linear-attention and 8 full-attention layers, hidden 4096, MLP 12288, 16 attention/4 KV heads, head dimension 256. Vocabulary rows 248320; configured context 262144; preserve multimodal RoPE parameters. The repository also stores vision and MTP weights. “9B” is a product size name, not exact full-checkpoint parameter accounting. [Pinned config](https://huggingface.co/Qwen/Qwen3.5-9B/blob/c202236235762e1c871ad0ccb60c8ee5ba337b9a/config.json).

The official project announced the small models on **2026-03-02**. License is Apache-2.0; no substitution with `-Base`, an invented `-Instruct` repo, a community quantization or Qwen3-8B. [Official project news](https://github.com/QwenLM/Qwen3.5), [model license](https://huggingface.co/Qwen/Qwen3.5-9B/blob/c202236235762e1c871ad0ccb60c8ee5ba337b9a/LICENSE).

Transformers 5.8.1 directly maps both `qwen3_5` and `qwen3_5_text` to `Qwen3_5ForCausalLM` in AutoModelForCausalLM. The text loader's native conversion removes `language_model` under the `model` prefix. It explicitly allows unused `mtp.*` and `model.visual.*`. Prefer this supported route over an improvised checkpoint converter; audit all retained text tensors, record excluded vision/MTP keys, and require no missing trainable text weights. Text-only parameters cannot be asserted equal to the full upstream 9.653B count.

Sources: [5.8.1 automatic model mapping](https://github.com/huggingface/transformers/blob/v5.8.1/src/transformers/models/auto/modeling_auto.py), [native prefix conversion](https://github.com/huggingface/transformers/blob/v5.8.1/src/transformers/conversion_mapping.py), [Qwen text loader](https://github.com/huggingface/transformers/blob/v5.8.1/src/transformers/models/qwen3_5/modeling_qwen3_5.py).

### Seed: requested repository is FP32

Exact architecture is `LlamaForCausalLM`, `model_type=llama`, 32 layers, hidden 4096, MLP 14336, 32 attention/8 KV heads, head dimension 128, untied embedding/head, vocabulary rows 155136, context 65536, BOS/PAD/EOS 0/1/2 and RoPE theta 500000. Its source is **FP32**, with seven shards totalling **33,001,882,488 bytes**. Explicitly casting this exact checkpoint to BF16 is a recorded numerical transformation; silently switching to the separately named official `Seed-Coder-8B-Reasoning-bf16` is not the same source identity. [Pinned config](https://huggingface.co/ByteDance-Seed/Seed-Coder-8B-Reasoning/blob/9927b7724deb1f8189da1cc6a50328dfb885d60d/config.json), [source files](https://huggingface.co/ByteDance-Seed/Seed-Coder-8B-Reasoning/tree/9927b7724deb1f8189da1cc6a50328dfb885d60d).

ByteDance's dated public announcement is 2025-05-19; the model repository was created 2025-04-27 and last changed 2025-06-06. Repository creation is not automatically public release. MIT permits modification and redistribution subject to retaining its copyright/permission notice. No separate gated access or custom use restriction was found in the inspected primary material. Preserve licenses/notices in deployment artifacts. [Official announcement](https://seed.bytedance.com/en/blog/seed-coder-open-sourced-llm-based-code-data-building-method-validated), [MIT license](https://github.com/ByteDance-Seed/Seed-Coder/blob/master/LICENSE).

## Tokenizers and supervision: concrete incompatibilities

- Granite uses the official GPT2Tokenizer/BPE assets and a separate `chat_template.jinja`. Source vocabulary has 100352 entries and max ID 100351.
- Qwen's saved tokenizer class is Qwen2Tokenizer; the BPE has 248044 base entries, 26 added tokens, max emitted ID 248069, and 248320 embedding rows. It contains both an inline template and a separate template file. Hash the loaded/resolved template and verify rendering, not only whichever file is convenient.
- Seed uses PreTrainedTokenizerFast/BPE with 155121 base entries, max emitted ID 155120 and padded 155136 embedding rows. Its template is embedded in tokenizer_config.json, and **raises an error for a system-role message**. For a shared benchmark, use a deliberately recorded user-only instruction format; do not quietly change prompts only for the failing model.
- Therefore `len(tokenizer)==config.vocab_size` is an invalid universal check. Require stable exact tokenizer hashes, expected ID/entry counts, and every emitted/special ID within the actual input/output embedding range. Never resize/crop embeddings just to make an equality check pass.
- None of these pinned official templates contains Jinja `generation`/`endgeneration` blocks. TRL `assistant_only_loss=True` depends on generation-mask-capable templates. Use tested completion-only token masks, or a separately versioned template edit whose rendered text/token output is proven unchanged. Verify prompt/answer boundary tokenization, nonzero supervised labels, padding masks, EOS and truncation explicitly.
- Keep `enable_thinking` and reasoning-effort settings fixed per scientific arm and included in renderer identity. Do not accidentally supervise fabricated hidden reasoning or let unfinished thinking consume all output capacity.

Evidence: pinned tokenizer assets in the source lock; [TRL's assistant-only masking contract](https://huggingface.co/docs/trl/v0.21.0/en/sft_trainer). For training examples exceeding 2048/4096 tokens, reject or select a separately declared long-example phase; silent truncation can erase the target and misrepresent training volume.

## Library support and real limits

### Transformers and PEFT

Transformers 5.3.0 already contained native Qwen3.5, and the audited **5.8.1 release** (PyPI 2026-05-13) contains all three exact model families. The original config fields `transformers_version=4.57.1`, `4.57.0.dev0`, `4.47.1` are serialization provenance, not reliable required-version declarations. An old release can load Granite/Seed while being unable to load Qwen3.5. [5.3.0 release](https://github.com/huggingface/transformers/releases/tag/v5.3.0), [5.8.1 package](https://pypi.org/project/transformers/5.8.1/).

LoRA target names must come from actual loaded modules. For Granite/Seed, initial attention/MLP targets are q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj. For Qwen this list omits all 24 DeltaNet mixers. Include their **in_proj_qkv, in_proj_z, in_proj_b, in_proj_a, out_proj** under text layers; do not train visual/MTP/embedding/head modules accidentally. In a native text model the prefix is `model.layers`; a full conditional model uses `model.language_model.layers`. Record names/counts/shapes of matched modules and validate gradient coverage. PEFT supports `all-linear`, but explicit reviewed text-scope enumeration is safer here. [PEFT LoRA contract](https://huggingface.co/docs/peft/main/package_reference/lora).

Concrete import hazard: PEFT **0.21.0** checks installed TorchAO and rejects versions below **0.16.0**. A preinstalled optional TorchAO can break an otherwise non-quantized LoRA setup. Use an isolated environment without TorchAO for the BF16 pilot; if quantization later needs it, separately pin its compatible Torch/CUDA build. Do not reproduce the old Kaggle TorchAO failure or assume the older 0.14 floor applies. [PEFT tagged check](https://github.com/huggingface/peft/blob/v0.21.0/src/peft/import_utils.py).

### TRL

TRL is optional for the bounded first optimizer loop. It offers SFT, preference and GRPO machinery, but an importable trainer is not proof of this model's packing, assistant mask, hybrid state reset, reference-policy or rollout synchronization semantics. For the first pilot use unpacked examples and explicit masks. Later RL needs a separate exact TRL/vLLM/PEFT lock, recorded reward definition, group size, KL/reference policy, rollout budget and audit of the complete loss/gradient path. Avoid unrequested mixing of online RL into an SFT acceptance run.

### NeMo

IBM reports using NeMo RL and NeMo Gym in its own Granite post-training. That proves the family's use in an IBM training stack, not that stock public NeMo provides a one-RTX-PRO6000 recipe for the exact released checkpoint. NeMo RL advertises broad HF AutoModel coverage and explicitly lists Qwen3.5-9B; current detailed long-run examples distinguish 9B-Base from the requested post-trained model and constrain backend/parallelism choices. Dense Qwen3.5 AutoModel context parallelism is not supported in the inspected guide (`cp_size=1`). [NeMo model support](https://docs.nvidia.com/nemo/rl/latest/about/model-support.html), [Qwen guide](https://docs.nvidia.com/nemo/rl/nightly/guides/models/qwen/qwen3-5.html).

The NeMo Seed page demonstrates **Seed-Coder-Instruct**, and labels that family Qwen2. Exact requested Reasoning config is **Llama**. Treat this documentation mismatch as an explicit reason to verify the actual model and recipe, never as authority to substitute the Instruct checkpoint. NeMo/Megatron/Transformer Engine are not needed for the first single-GPU LoRA notebook. [NeMo Seed page](https://docs.nvidia.com/nemo/automodel/latest/model-coverage/large-language-models/seed-byte-dance).

### vLLM

The architecture registry supports Granite, Llama and Qwen3.5. This is necessary but not sufficient for a particular quantization, LoRA target set, dtype and GPU. Granite's official reasoning parser plugin requires vLLM 0.20+; native raw-token inference does not require that plugin. If used, pin and locally package parser source. [vLLM supported models](https://docs.vllm.ai/en/stable/models/supported_models/), [IBM serving instructions](https://huggingface.co/ibm-granite/granite-4.2-8b#serving-with-vllm).

Qwen's fast DeltaNet path requires compatible FLA/causal-conv1d; without it Transformers can use slower, more memory-hungry reference operations. SDPA addresses full-attention layers, not those 24 mixers. Record the actual backend rather than silently accepting a fallback. vLLM's Qwen guide documents experimental Mamba prefix-cache alignment and graph-capture sizes exceeding Mamba-cache capacity. Begin with cache/graph policies validated for the exact small model and workload, not large H200 MoE recipe defaults. [Transformers Qwen notes](https://huggingface.co/docs/transformers/model_doc/qwen3_5), [vLLM Qwen recipe](https://docs.vllm.ai/projects/recipes/en/latest/Qwen/Qwen3.5.html).

## Hardware: two separate execution targets

### Training: g4-standard-48

Google documents 48 vCPUs (hardware hyperthreads), 180 instance-memory units in the machine table and **180 GiB** on pricing, AMD EPYC Turin 5th generation, **one 96-GB GDDR7 RTX PRO 6000 Blackwell Server Edition**, one NIC and up to 50 Gbps network. Optional Titanium SSD capacity is up to 1500 GiB; this is neither guaranteed existing disk nor free storage. G4 uses Hyperdisk Balanced for boot; ordinary Persistent Disk is not supported. No paid resource is provisioned by this memo. [Machine specifications](https://docs.cloud.google.com/compute/docs/accelerator-optimized-machines#g4-vms), [pricing/spec unit cross-check](https://cloud.google.com/products/compute/pricing/accelerator-optimized).

The GPU is compute capability **12.0 / sm_120**, not B200's sm_100 or GB10's sm_121. Current Google recommendations are R580 Linux **580.95.05+** and Toolkit **13.1+**. These are distinct from a PyTorch wheel's bundled CUDA runtime. CUDA12.8 introduced sm_120 compiler support; PyTorch2.7 introduced official Blackwell/cu128 wheels; official2.8.0+cu128 remains a plausible reproducible candidate on a suitable modern driver. Do not assume success without an actual matrix/attention/backward probe. Do not change drivers as part of this read-only task. [Compute capability](https://developer.nvidia.com/cuda/gpus), [Google drivers](https://docs.cloud.google.com/compute/docs/gpus/install-drivers-gpu), [CUDA12.8 release](https://docs.nvidia.com/cuda/archive/12.8.0/cuda-toolkit-release-notes/index.html), [PyTorch2.7](https://pytorch.org/blog/pytorch-2-7/).

### Submission: four L4s

L4 is Ada Lovelace **sm_89**, nominal **24 GB GDDR6 per device**. The four-L4 topology remains the task's deployment contract; fresh competition rules and actual authorized-run hardware still need verification before official submission. A nominal aggregate 96 GB is not a single allocation pool and does not make full-GPU G4 checkpoints automatically runnable. Capture four distinct GPU UUIDs, total/free bytes individually, process placement, and interconnect measurements. [NVIDIA L4 specification table](https://images.nvidia.com/data-center/technical-brief-gpu-positioning-virtualized-compute-and-graphics-workloads.pdf?ncid=no-ncid), [compute capabilities](https://developer.nvidia.com/cuda/gpus).

Use `torch.cuda.get_device_properties(...).total_memory`, allocator peaks and free-memory observations in **bytes**. Marketing GB, OS GiB and post-reservation usable memory differ. A guessed “94 GiB available” is not an admissible runtime fact.

## Honest capacity estimates

These are arithmetic estimates, not benchmarks. BF16 weight payload only:

| Model scope | BF16-equivalent payload GiB | Conventional 16-byte/parameter full-Adam state GiB |
|---|---:|---:|
| Granite exact full model | 16.376 | 131.005 |
| Qwen full checkpoint, including vision/MTP | 17.980 | 143.842 |
| Seed exact model cast from FP32 | 15.368 | 122.941 |

The 16-byte model is BF16 parameters/gradients plus FP32 master weights and two FP32 moments. Implementations differ; even a 12-byte/parameter variant would be approximately 98.254/107.882/92.206 GiB before activations, workspaces, logits and fragmentation. Therefore do not claim ordinary full-parameter Adam fits comfortably on the training GPU. CPU/offloaded optimizers or reduced-state methods are separate measured variants, not an implicit fallback.

BF16 LoRA keeps the base frozen and optimizer state only for adapters. Granite rank16 across the seven stated projection types is approximately **49.48M adapter parameters**, before any optional trained embeddings/head. This is a credible first approach on a 96-GB card at microbatch1 and modest sequence length. Exact activation/logit memory still depends on sequence length, attention backend, loss implementation and checkpointing.

Granite BF16 KV cache is about **160 KiB per token per sequence** (40 layers × two K/V × 8 heads × 128 × 2 bytes), or **0.625 GiB at4096 tokens**. Do not set a128K serving context just because the config permits it: cache alone would approach20 GiB per sequence. Qwen's eight full-attention layers have approximately32 KiB/token KV plus separate recurrent/conv state; use measured memory rather than a transformer-only estimator.

NF4 QLoRA reduces eligible frozen linear storage, but total device memory is not simply0.5×parameter count: scales, double-quantization metadata, unquantized embeddings/head/norms, FP32 recurrent state, adapters, optimizer state and activations remain. Quantized training is extra-parameter training, not arbitrary full-weight backpropagation. Reserve it as a separate comparison after the BF16 baseline.

## Blackwell-to-Ada portability and offline export

- **Weights and adapters:** save plain Safetensors, pinned config/tokenizer/templates and exact base lineage. These numerical tensors can be portable; CUDA extension binaries and compiled execution engines are not automatically portable.
- **Separate wheel manifests:** lock Python ABI, OS architecture/glibc, Torch build, CUDA-linked libraries, extension build targets, package versions and SHA256. A Blackwell-only sm_120 cubin cannot execute on sm_89. Forward-compatible PTX is not backward compatibility from Blackwell to Ada. Runtime download/build must be disabled in competition. [NVIDIA binary/PTX compatibility](https://docs.nvidia.com/cuda/archive/12.8.0/inline-ptx-assembly/blackwell-compatibility-guide/index.html).
- **No rolling source installs:** `main`, `latest`, nightly URLs, Hub-kernel auto-downloads and “pip install -U” are documentation examples, not reproducible notebook dependencies. Pin source commits and build wheels ahead of time for each target when unavoidable.
- **BF16 portable baseline:** package original base+LoRA adapter, or merge into a BF16 derivative outside the scored run and retain both identities. Verify merged/unmerged logits within a declared numerical tolerance and task-level outputs. Do not assume bitwise sampling equivalence across GPU architectures.
- **QLoRA export:** retain the source checkpoint, quantization config and adapter. For a BF16 merged export, explicitly load/cast the original base and apply the adapter; record that the training base was quantized and measure any quality shift. Never relabel packed4-bit bytes as BF16 or copy a Blackwell engine.
- **Quantization choice:** bitsandbytes NF4/FP4 is supported on both target capability families by appropriately built CUDA12.8+ x86 wheels. That FP4 format is not NVIDIA NVFP4 tensor-core execution. vLLM documents Ada support for AWQ/GPTQ/Marlin/bitsandbytes and some FP8 routes, but exact architecture/backend combinations still require a target probe. Blackwell-optimized NVFP4/TensorRT/Transformer-Engine artifacts are not the default L4 deployment format. [bitsandbytes build targets](https://huggingface.co/docs/bitsandbytes/main/en/installation), [vLLM quantization support](https://docs.vllm.ai/en/stable/features/quantization/).
- **Topology:** start with one selected model replica per L4 and schedule independent tasks/rollouts. If one replica exceeds per-GPU capacity, compare a supported quantization or two-/four-way sharding under measured throughput. `device_map=auto` is not proof of a deliberate tensor-parallel plan and must not silently add CPU offload.

## Fail-closed phase and admission contract

Keep source-valid, CPU-valid, GPU-compatible, quality-qualified and submission-ready as separate booleans; none implies another.

**A. Offline static admission:** exact source lock matches every config/tokenizer/index/shard hash and size; no unlisted load-bearing files; safe index/header paths; source dtype/shape totals verified; model ID+revision immutable; full vocabulary and template fixture hashes; finite loss-label counts; data lineage/task-disjoint split and source exposure preserved; no hidden answer material in runtime; exact wheel lock complete; no remote code unless separately reviewed/pinned; Internet disabled.

**B. Authorized hardware smoke:** exactly one full G4 GPU withsm_120, expected product and distinct identity, BF16 support, usable-memory bytes, correct driver/runtime/build architecture; finite tiny BF16 matmul, SDPA forward/backward; full model load with expected retained/excluded keys; exact LoRA targets; no trainable base weights outside allowlist; two or another explicitly declared small number of updates with finite gradients and changed adapter digest; export/reload/adapter-reset checks. The notebook's execution guard remains False until the owner chooses to run.

**C. Bounded training pilot:** e.g.16 optimizer updates at max sequence2048, microbatch1 and fixed accumulated token budget. A128-update or4096-token run is an explicitly distinct plan, not an automatic retry. Preserve complete examples or report exclusions, held-out eval before/after, trained-token totals, peak device/host memory, wall time and nonfinite/OOM events. Failure does not silently alter model, precision, rank, sequence, data, budget or backend.

**D. Four-L4 deployment qualification:** materialize the selected export and L4-specific offline wheels; verify exactly four distinctsm_89 devices; load one replica and then all planned replicas; test real longest admissible prompt/output lengths and concurrency; verify grammar/tool sandbox, reset/isolation, bounded output artifacts and final submission schema; measure full-workload time and per-device peaks. A small successful forward is not whole-notebook acceptance.

**E. Quality selection:** model preference order breaks ties or sets acquisition sequence; promotion requires measured task-disjoint ARC outcomes plus valid-output rate, complete-run success, inference cost/time and reproducibility. Use matched data/token budgets, record thinking mode and tokenizer-token differences, and distinguish plain prompting, SFT, TTT and search contributions. Open benchmark contamination and model pretraining exposure remain unresolved unless independently audited.

## Remaining uncertainty

No candidate has been run on the new G4 target or newly qualified on four L4s in this task. No full transitive offline environment lock has been resolved against an actual chosen Python/driver image. FLA/causal-conv1d, vLLM LoRA/quantized paths, NeMo conversions and target numerical parity remain conditional. Model licenses do not establish ARC competition external-data eligibility. Source availability does not authorize paid provisioning, account changes, runtime queries or official submission.
