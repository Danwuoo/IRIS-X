# Source and evidence citations

## Official Qwen source

- Model metadata endpoint recorded in `provenance/hf-official-metadata.json`: https://huggingface.co/api/models/Qwen/Qwen3-14B?blobs=true . This retained response pins revision40c069824f4251a91eefaf281ebe4c544efd3e18, eight LFS weight SHA256/sizes, small Git blobs, architecture and BF16 parameter count. It is retained metadata, not a claim about the current moving main branch.
- Exact source tree: https://huggingface.co/Qwen/Qwen3-14B/tree/40c069824f4251a91eefaf281ebe4c544efd3e18
- Exact config: https://huggingface.co/Qwen/Qwen3-14B/blob/40c069824f4251a91eefaf281ebe4c544efd3e18/config.json
- Exact index: https://huggingface.co/Qwen/Qwen3-14B/blob/40c069824f4251a91eefaf281ebe4c544efd3e18/model.safetensors.index.json
- Exact license: https://huggingface.co/Qwen/Qwen3-14B/blob/40c069824f4251a91eefaf281ebe4c544efd3e18/LICENSE
- Exact per-file resolve URLs and hashes are in `material-contract.json:overlay_files`. Small files were reused from already verified local `model-next-r3/assets/qwen3-14b`; no network retrieval occurred in this preparation.

## Official numeric Kaggle model

- https://www.kaggle.com/models/qwen-lm/qwen-3/transformers/14b/1
- Closed numeric-v1 file list retained in `provenance/provider-file-list-v1.json`.
- Prior official small-file retrieval receipt retained in `provenance/provider-small-file-receipt.json`; it explicitly records the tokenizer_config mismatch.
- Sole publisher retrieved the36,514-byte index once. `provenance/provider-index-receipt.json` binds reference/numeric1/versionID363149, before/after inventories, SHA25662d7ad35757bae5e7baa452cb1483178b7daa50e869e923226b8da10871f7ebc and Git blobb4d92f9fec7ec78a89aaf1cf9d740ffc69cb9aac. It expressly says full weight hashes were not yet verified.
- `provenance/provider-mount-contract.json` cites official Kaggle API and kagglehub source explaining provider-assigned mountSlug. SaveKernel's modelDataSources does not guarantee a mount path.

## Owned offline environment and observed hardware

- Owned wheels numeric1: https://www.kaggle.com/datasets/danielwuu/iris-arc-next-cu128-cp312-wheels/versions/1 . Its retained prepared lock SHA2562b082a3c36534b5602b8a9f738beec2c01b3d2df11b5438f1c352a84c118b052 and complete52 wheel bindings are preserved. `provenance/verified-owned-wheels.json` is the prior download/identity receipt; `provenance/existing-environment-verification.json` is this preparation's read-only SHA recheck,3,959,690,542 bytes.
- Owned interpreter numeric2: https://www.kaggle.com/datasets/danielwuu/iris-arc-next-cpython312-offline/versions/2 . Full interpreter manifest SHA25620a52944f1ee2abf6f47a2e3beafce44951993439fede39335e660cea143495e; archive/executable bindings appear in `environment-lock.json` and prior bootstrap evidence.
- Owned runtime numeric8: https://www.kaggle.com/datasets/danielwuu/iris-arc-next-runtime/versions/8 . Outer bundle manifest SHA256c2e7913e8ae208deb26e06f37fcd76c79c1a87b6c49ffb3de7b2ee054fee7e67; inner source-lock SHA2568cf82737a0c6c92d0d26f3a7a268e59c55f4a4de213733777f71324930ece239.
- Actual v9 archived evidence `worker/result.json`, JSON path `stages.model_load.hardware`, is bound by archive/member hashes in `provenance/v9-hardware-evidence.json`. This was a prior Granite execution. It establishes observed device properties, not Qwen memory fit or performance. `provenance/v9-environment-lock.json` and `v9-bootstrap-receipt.json` preserve exact original installation evidence including historical paths.
- `provenance/meta-derivation-receipt.json` binds this native meta shape derivation, tokenizer vocabulary/template identity, exact interpreter and library versions. This is CPU/meta evidence only.
