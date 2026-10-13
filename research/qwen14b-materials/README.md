# Qwen3-14B single-session composite probe materials

This is a prepared material contract and CPU verification package, not an independent review, execution authorization, completed GPU capability test, or claim of measured fit. No pretrained model weights were downloaded, copied, or loaded in this preparation. No provider calls, package installations, GPU calls, or publication actions were made here.

## Immutable entry point

`material-contract.json` SHA256:
`8d26b2f04a91147bbb5e11231f614552d36e2862af9b8d2d2b05b273805b69b0`

The independently reviewed runtime source must pin that digest as a constant. A caller-supplied success flag, manifest, digest, or calibration receipt must never admit another deployment. The entry point binds the exact environment, hardware, native meta tensor inventory, provider index, and five-file Hugging Face overlay.

## Three distinct material roots

1. **Provider model root:** official `qwen-lm/qwen-3/transformers/14b/1`, numeric version ID 363149. Sixteen regular files total 29,552,600,690 bytes; eight shard files total 29,536,665,640 bytes. Its actual mount slug has not been observed and must not be guessed. Discover exactly one bounded, regular, read-only root below `/kaggle/input` using exact config/index identity and the closed inventory. Full eight-shard SHA256 streaming, header and tensor coverage verification must complete before any native weight load. Do not copy the approximately 29 GB model into the workspace or create a symlinked fake combined folder.
2. **HF overlay root:** `hf-overlay/`, exactly `config.json`, `generation_config.json`, `tokenizer.json`, `tokenizer_config.json`, and `LICENSE`. All are exact-byte assets from HF revision `40c069824f4251a91eefaf281ebe4c544efd3e18`. The license is separately sourced, because the provider inventory has no LICENSE file. Instantiate exact native Qwen3Config and GenerationConfig objects from this overlay and pass them explicitly with the verified weight root to `Qwen3ForCausalLM.from_pretrained`. Tokenizer loading uses only this overlay. Keep `trust_remote_code=False` and `local_files_only=True`.
3. **Owned wheel root:** existing `danielwuu/iris-arc-next-cu128-cp312-wheels/1` read-only mount. Its52 wheels remain there; the new environment-lock descriptor lives in the code payload. Pass a separate `wheel_root_path`; never assume `environment-lock.parent/wheels`, copy 4 GB of wheels, or manufacture symlinks. Existing verified offline bootstrap may install this exact closure into the isolated pinned interpreter; no new dependency or download is admitted.

The provider tokenizer_config is 9,675 bytes, SHA256 `5a7303fcb1a27ede63134a2cbd61d5282c247ca6d769ce4746d4ffa124aedd63`; the HF tokenizer_config is 9,732 bytes, SHA256 `d5d09f07b48c3086c508b30d1c9114bd1189145b74e982a265350c923acd8101`. They are not interchangeable. Provider config, generation config and tokenizer.json match their corresponding HF files. Its index was additionally matched to the exact HF Git blob. No whole-snapshot equality claim is made. Provider README/vocab/merges are permitted only as ordinary unused files with the exact provider-listed sizes; their content identity is not claimed and native loading must not consult them. All load-bearing files have full SHA bindings.

## Exact runtime and device contract

- CPython3.12.15 exact executable/archive; Linux x86_64, glibc≥2.28.
- All52 transitive packages and wheels are pinned, including Torch2.8.0+cu128, Transformers5.8.1, PEFT0.21.0, Tokenizers0.22.2, Safetensors0.8.0 and Accelerate1.10.1.
- Historical wheel-lock provenance retains its preparation-host Python3.12.3; it is not rewritten or confused with the actual pinned3.12.15 runtime. All52 installed versions and original local wheel hashes were read-only reverified here.
- Exactly one `NVIDIA RTX PRO 6000 Blackwell Server Edition`,101,973,819,392 bytes, capability[12,0], BF16 support, driver580.178.04 and Torch CUDA12.8. These came from actual v9 archived evidence, which expressly says machine_type_verified=false despite target `g4-standard-48`.
- Frozen BF16 base, FP32 LoRA rank 8 / alpha 16 / dropout 0, batch 1, native SDPA, context≤2048, prompt≤1792/output≤256. No FP8, 4L4, quantization or tensor-parallel fallback.
- Analytic engineering allowance is49,420,761,088 bytes, with an additional4GiB free-VRAM reserve. This is not measured peak memory or proof of fit. Peak/throughput remain null until the real probe measures them.
- Full-vocabulary cached/full parity uses predeclared atol=rtol=0.01 ceilings at actual tested sequence lengths before and after update. A failed check is no-go; do not widen tolerances silently.
- All discovery/setup/hashing/loading/testing/training/evaluation/teardown time belongs inside one3-hour probe and the12-hour global elapsed budget. Preserve the bounded capability subprocess limit≤1800s and owned-process closure enforcement.

## Tensor identity

`expected-tensor-inventory.json` contains443 exact native state keys/shapes and their eight-shard mappings,14,768,307,200 elements. Shapes were derived using the existing exact3.12.15/Torch2.8/Transformers5.8.1 environment under `torch.device('meta')`; there were no model forward calls or pretrained values. Expected BF16 dtype is from the pinned official config/model metadata, not a measurement of meta values. Runtime must separately check the actual safetensors headers and loaded tensor dtypes, then reconstruct native meta shapes again. Both embedding/head matrices retain151,936 rows even though the tokenizer exposes151,669 IDs.

## Verification in this package

`tests/TEST-RESULTS.txt`:33CPU tests passed, covering the actual HF overlay, descriptor bindings, native/index443-tensor coverage, wrong SHA/length/index/shard/total, unsafe paths, unknown files, symlinked files/root/ancestors, root mixing, malicious auto_map, malformed/duplicate/bounded headers, overlap/gaps, dtype and native-shape mismatches, and nonfabricated hardware measurement fields.

These are standalone material-oracle tests. They do not substitute for testing the runtime owner's actual separate-root loader. Full model bytes were not locally available; runtime full-weight validation remains mandatory.

Reproduce with an existing pinned isolated environment, without installing anything:

    E=learning-agent-v6-next-20261011/production-topology/production-run/environment/environment-cp312-cu128
    "$E/bin/python" -I -B -S "$E/offline-run.py" learning-agent-qwen-probe-20261012/materials/contract/tests/test_material_contract.py

`derive_meta.py` recreates shapes/tokenizer digests with the same pinned environment. `verify_existing_environment.py` rechecks the existing52 local wheels and installed package versions. `build_contract.py` deterministically recreates descriptors from the retained sources. Refer to `SOURCES.md`, provenance receipts and `HASH-MANIFEST.json` for exact source and output identity.
