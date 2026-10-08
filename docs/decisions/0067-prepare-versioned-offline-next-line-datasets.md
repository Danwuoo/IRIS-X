# Decision 0067: Prepare independently versioned offline next-line Datasets

Date: 2026-10-08. Status: accepted owner scope; implementation and physical
material closure in progress, no GPU runtime success claimed.

## Owner direction

The owner asked for a version requiring no network and, if cloud storage was
insufficient, temporary local development in a gpt-6.1-sol / xhigh task. They
then explicitly asked to upload model weights and package wheels as Kaggle
Datasets, and code as its own Dataset versioned with development iterations.

This extends Decision 0066's preparation scope. It does not authorize paid
compute/provisioning, an automatic GPU run, public release, credentials transfer,
or official competition submission. The original accepted notebook remains
immutable evidence. A new source-only save cannot reuse its consumed journal.

## Material contract

1. Granite model Dataset: exact official revision
   f8de16cdcdbc6c779ca517604e050d82cc119e44, all four safetensor shards,
   complete native tokenizer/config/template/model card, Apache license and
   independently SHA256-verified model material manifest. Upstream payload is
   17,593,020,491 bytes. No model conversion or vocabulary compression.
2. Dependency Dataset: target Linux x86_64, CPython 3.12, glibc at least 2.28,
   PyTorch 2.8.0+cu128 and the previously reviewed HF/PEFT core versions. Native
   Linux dependency resolution, every transitive wheel, hashes, exact requirement
   lock, source provenance and licenses are required. No source builds or
   optional quantization/attention packages are silently added.
3. Runtime Dataset: separately versioned reviewed source, existing pinned
   demonstration-only 32/4 task-group material, attribution, and closed byte
   inventory. No weights or wheels. Evaluator answers remain isolated under
   training/evaluator and are read only by the separate post-stop scorer.

Every Dataset is private in the authenticated owner's danielwuu account.
Exact numerical Dataset versions and manifest hashes are bound by each notebook
revision. No latest-version mount fallback. The SDK request and source readback
must preserve the numerical version references; runtime checks validate bytes
independently of the mount path or source echo.

The intended slugs, subject to availability verification, are
iris-arc-granite42-8b-offline, iris-arc-next-cu128-cp312-wheels and
iris-arc-next-runtime. No private code is relicensed as Apache merely because
its training-data and model dependencies use that license.

## Offline execution and verification

The revised notebook has no network preparation cells. All operation switches
remain False. It installs the verified wheel closure into a fresh isolated venv
using no-index/no-cache/hash-required pip, and runs subsequent phases with that
interpreter. This avoids mutating Kaggle's host packages and avoids optional
host torchao conflicts. CPython patch-level relocation preserves the immutable
prepared wheel lock hash and records actual target interpreter evidence.

Missing/changed mounts, weights, tokenizer data, wheels, source, licenses or
unsupported ABI must fail before loading or training. Python socket/DNS denial
is defense in depth and a negative-test mechanism, not a substitute for Kaggle
Internet OFF or an OS firewall. CPU import/tokenizer/safetensor checks and
missing-material/network-denial tests are separate from real full-model GPU
load, training, accuracy or four-L4 deployment qualification.

Keep actual download/upload completion, sizes, Dataset IDs/versions, CPU test
receipts and remaining runtime gaps in the trial's evolving report. Do not mark
physical closure complete solely because code or manifests exist.

## Confirmed upstream index defect and narrow derived artifact

On 2026-10-08 the owner explicitly directed continuation after diagnosis.
Independent bounded reads of the immutable public Granite shard headers and
index confirmed 241 of 363 shard assignments disagree; all 363 tensor names
and the full 8,791,592,960 BF16 parameter inventory are present. The index's
payload total is also wrong by one native embedding matrix. The public proof
and its limits are retained under research/arc-next-line/granite-index-audit/.

Preparation may create a distinct explicitly derived v2 material artifact:
retain the official original index and v1 material manifest, verify every
full source SHA256 locally, regenerate only the index's shard map and payload
total from actual headers, and reproduce the independently pinned corrected
index hash. All weight/config/tokenizer bytes stay unchanged. Keep a prominent
modification notice and exact derivation provenance. The original v1 validator
continues to reject the inconsistency; no generic hash/index gate is waived.

The new repair code requires its own independently reviewed code Dataset
version. Physical full-file hash, header/index, tokenizer and configuration validation
is required before publishing the derived model Dataset. The local WSL host
has only 14.78 GiB available RAM (4 GiB swap), insufficient for a safe full
BF16 model load; no full CPU load or memory-configuration change is authorized.
Full HF weight loading and G4/GPU qualification remain explicitly unverified.
No full source weights were downloaded in the cloud; no GPU run is authorized.

## Completion boundary

At 10:45 UTC the owner directed: complete this stage, push main, then pause.
This authorizes normal integration of the completed offline assets/notebook
stage into current main, preserving independently existing changes and source
history. Refresh both main and recovery first; resolve and test any integration
normally, without force-pushing. Verify the remote commit and available CI.
Do not publish an offline-ready notebook before all three real Dataset versions
and their complete content receipts are verified. Training and subsequent
research remain outside this completion instruction.
