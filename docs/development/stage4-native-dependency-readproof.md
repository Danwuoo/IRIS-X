# Selected-byte gate for the next native synthetic probe

The next admitted probe must receive a separate immutable
`--dependency-readproof` JSON input. The reviewed candidate is
`research/stage4-e10/dependency-readproof-v2.json`. It records only paths,
sizes, hashes, inert acquisition evidence pins, finite read limits and explicit
limitations. No dependency binary or discovered source is packaged.

The input binds public `sorokin/pip-install-unsloth-flash-patch`, numbered
Version 2, script-version ID 272622465, and these five selected files:

- `qwen3.patch`
- `unsloth/models/qwen3.py`
- `flash_attn-2.8.2.dist-info/METADATA`
- `flash_attn-2.8.2.dist-info/RECORD`
- `flash_attn_2_cuda.cpython-311-x86_64-linux-gnu.so`

The native file is 997,494,640 bytes, SHA256
`b9e8fbe638153d8e2f6f458c4cfa1c6339a780c73eb6d40c86be5309fde11a1d`.
The five files total 997,550,297 bytes. The original 41-entry native source
inventory and scientific/model configuration remain unchanged. Overlapping
inventory rows must equal the additive proof; the new gate is not a substitute
for the original inventory check.

## Explicit runtime boundary

`tools/nvarc_dependency_readproof.py` streams these exact paths before the
probe calls `prepare`, which performs the explicit Torch import and existing
native setup. POSIX directory-descriptor traversal rejects symlink ancestors,
symlink members, nonregular files and multiply linked files. Exact size and
SHA256, stable descriptor metadata, positive finite deadline, free disk,
bounded chunks and a cumulative read cap are mandatory. No discovery,
dependency import, archive extraction, model call or provider action occurs.
The candidate uses 1-MiB chunks, 300 seconds, 997,550,302 read bytes including
five possible EOF checks, and a 10-GiB free-working-space reserve. Deadline
checks are cooperative around each read; the existing outer notebook process
supervisor supplies the separate process-level bound.

`dependency-readproof.json` is in the static payload hash closure, along with
the gate helper source. `dependency-readproof-receipt.json` binds its contract
and probe plan digests, the locally inspected dependency root, observed
selected bytes, resource observation, elapsed host time and any failure.
Both the static proof and dynamic receipt are permitted archive members.
A failed receipt is retained and cannot be overwritten by a retry. A mismatch
prevents preparation and worker launch. Each worker also requires the exact
parent receipt hash before explicit native engine construction. This does not
rehash four copies of the one-GiB binary or certify later filesystem stability.

Inert packages can still be constructed without the proof, but remain blocked
from runtime. Resource admission and this proof do not provide third-party
run/import authorization. That remains a separate owner approval boundary.

## Declared provider reference and limitations

New probe metadata declares `sorokin/pip-install-unsloth-flash-patch/2`.
The installed official Kaggle CLI 2.2.4 source explicitly accepts
`owner/slug/version` in `validate_kernel_string` and passes validated
`kernel_sources` unchanged to `ApiSaveKernelRequest.kernel_data_sources`
inside `kernels_push`. This is local client-syntax evidence only. No provider
request was made to validate server resolution, and no resolved mount claim
follows. At a separately authorized execution, the actual five local mount
files must independently pass the byte gate.

The gate does not establish a full import inventory, independent native build
provenance, complete license closure, import safety or platform parent startup
attestation. The unchanged worker dependency `PYTHONPATH` also is not a Python
startup attestation. The fresh RECORD declaration and independent opaque-byte
hash comparison support only the narrow selected-byte equality claim.
All prior package/run identities and retained failure bytes remain frozen.

## Offline verification

`python -m unittest tests.test_nvarc_dependency_readproof tests.test_nvarc_e10_probe tests.test_nvarc_e10_runtime_gates -v`

Tiny independently prepared inert files test streaming, size/hash/missing-file
mismatches, symlink ancestors and members, hardlinks, FIFO rejection, finite
caps, deadline exhaustion, disk reserve, concurrent descriptor changes,
failure retention, additive inventory/source closure, versioned metadata and
worker receipt binding. An injected preparation sentinel checks ordering,
without importing or executing any discovered bytes. These tests are not GPU,
native import, full-screen or scientific qualification evidence.

## Current resource reconciliation

The new probe uses resource-admission v2. It binds a fresh provider quota
snapshot with zero reserved seconds and a local Stage4 campaign with zero
pending actions. This is a current resource-occupancy check, not an assertion
that every historical kernel or Editor session is terminal; that assertion
remains explicitly false. The execution ledger independently binds snapshot
bytes, applies 15-minute freshness, reserves the complete session cost, and
blocks duplicate or uncertain pushes. This first probe conservatively reserves
7,200 charged quota seconds for four GPUs for 1,800 wall seconds, without
relying on a charging discount. No historical artifact bytes are changed.
