# Official Granite 4.2 index inconsistency

The immutable official revision's index is internally inconsistent with its
four safetensor shard headers. This is independently reproduced from only
42,112 public shard-header bytes plus the 31,357-byte source index. This cloud
audit did not download or hash full multi-GB weight files.

- All 363 tensor names occur exactly once in the shard headers.
- 241 index-to-shard assignments disagree with those headers.
- Each shard's BF16 offsets cover its complete expected payload, without gaps
  or overlaps. Total: 8,791,592,960 BF16 parameters / 17,583,185,920 payload bytes.
- The source index declares 16,761,102,336 payload bytes. The discrepancy equals
  one full native 100352 × 4096 BF16 vocabulary matrix: 822,083,584 bytes.
- The deterministic replacement changes only weight_map assignments and
  metadata.total_size; no tensor byte, model config, tokenizer or vocabulary
  is altered. Its independently anchored SHA256 is in audit-manifest.json.

A stale index after re-sharding is plausible. The upstream publisher's internal
cause is not established by these public bytes, and is not claimed here.

The original v1 validator correctly rejects this inconsistency and remains
strict. A separately labeled derived material format must retain the official
original index and source manifest, verify every full source file hash locally,
regenerate the corrected index from real headers, reproduce the pinned derived
index hash, and pass the ordinary full model/tokenizer checks. Actual HF loading of the full local weights remains a separate unverified
gate: the local host has insufficient available RAM, so no full CPU load will
be attempted. File/header/index integrity is distinct from loader execution;
no GPU run is authorized.
