# Combined notebook 002: GPU identity repair

Date: 2026-09-27
Status: submitted version 1; runtime unqueried; push consumed
Authority: [Decision 0036](../../docs/decisions/0036-repair-combined-nvarc-notebook.md)

## Verified predecessor failure

The owner reported an error in `danielwuu/nvarc-m2-m3-combined-001` and
requested repair and re-push. Its one newly authorized diagnostic retrieval
completed, returning the terminal aggregate, startup event stream and full log.
Every startup event's embedded payload hashes matches the exact submitted
notebook, and the terminal plan digest matches Decision 0035's approved plan.
This is the retained version-1 package; no mutation of its kernel was made.

The notebook failed after 9.8166 seconds in `hardware-inventory`, raising
`RuntimeError: hardware UUID mapping differs`. Both branches report zero
launches and zero model calls. Dependency installation and model work had
not started. The original bytes and failure evidence remain frozen.

Evidence is under `.irisx/arc-agi-2/qwen35-nvarc/m2-m3/combined-001-retrieved/`.
The local diagnostic binding report is `decision-0036-diagnosis.json` in its
parent directory. SHA-256 bindings:

| Member | SHA-256 |
| --- | --- |
| Aggregate terminal | `23fd4ec1dc8e0d601b9898cbd01607109798dee55d575c9699a1a51f84985d4c` |
| Startup events | `78642a5ae767b9fdb1d051757be62aa0487013a691fbb37899424b6bfde57d13` |
| Full kernel log | `491410cd5222a9279b1990f780640360716deaf548a2a941c5c5c9e4a47d9da6` |

## Defect and repair boundary

The original parent compared `str(properties.uuid)` directly to the
`nvidia-smi` UUID at the same positional index. Its worker repeated the raw
string comparison. PyTorch v2.10.0's [CUDA binding](https://github.com/pytorch/pytorch/blob/v2.10.0/torch/csrc/cuda/Module.cpp#L971-L979)
uses [uuid_to_string](https://github.com/pytorch/pytorch/blob/v2.10.0/torch/csrc/utils.cpp#L224-L249),
which formats a bare hexadecimal UUID without NVIDIA's `GPU-` prefix.
The direct comparison therefore rejects equivalent GPU identities. The
previously retained L4 inventory contains `GPU-`-prefixed NVIDIA UUIDs.

The failed run did not save its actual raw UUID strings before the assertion.
The failure location is verified; the precise values in that session and any
additional enumeration-order difference are not observed. The representation
defect is established by source inspection and must be covered by regression.

The replacement uses a distinct run/kernel `nvarc-m2-m3-combined-002` with new
child identities. The shared stdlib helper `src/irisx/arc_nvarc_hardware.py`
normalizes complete UUID representations, matches by physical UUID instead of
positional device index, rejects malformed/ambiguous/duplicate or genuinely
different IDs, and retains raw hardware diagnostics before validation. The
parent embeds the exact helper source before dependency setup; isolated workers
import that helper from the packaged wheel. Worker binding also checks physical
index and both memory representations against the parent assignment.
The two distinct L4/BF16/memory requirements remain in force.

All existing Dataset mounts, model/material hashes, generation/training
ceilings, 1,800-second total limit and offline/private/USD 0 policy remain
unchanged. No Dataset update or new model acquisition is part of this repair.
The original inert draft and submitted 001 template/package are preserved.
The replacement stops at its submission receipt; actual GPU acceptance and
model completion require later evidence and are not established by preflight.

## Offline validation

The focused combined supervisor, approval and hardware suites pass 23 tests.
The generated notebook's actual hardware segment passes 12 controlled Torch
and NVIDIA-SMI fixtures, including bare/prefixed uppercase UUIDs, reordered
physical ordinals, true mismatch, partial and duplicate identities, malformed
rows, unsupported hardware/BF16 and insufficient memory. Rejection checks require
the intended exception type and reason. The worker fixture verifies one visible
logical device against the assigned physical UUID, and raw observations survive
collection failures. These are offline fixtures, not actual CUDA acceptance.

The five affected strict package tests pass, including the actual packaged
parent/worker authorization guards, preserved historical 001 rejection,
deterministic rebuild, closed inventory and unchanged scientific fields.
`python tools/repository_check.py --all` passes: 244 tests, four optional
dependency skips, repository invariants, validator self-tests and diff checks.
The log is `.irisx/nvarc-combined-decision-0036-repository.txt`.

The final 15-member package is
`.irisx/arc-agi-2/qwen35-nvarc/m2-m3/combined-approved-002/`.
Its plan digest is
`sha256:48e9fa7c28e37fc585f87046957e723573697eb01016e1175fab50c9152364ef`.
`decision-0036-preflight.json` independently checks the embedded payloads,
exact executable template, model/export/tokenizer materials, approval guards
and all 12 generated-hardware fixtures, with zero external calls.

The coordinating review independently verified both package inventories,
the replacement wheel against final source bytes, and exactly seven changed
plan paths: parent run/kernel/decision and each child's run/kernel identity.
`decision-0036-comparison.json` records the complete original inventory and
unchanged scientific fields, materials, original templates and draft.

## Exact submission and stopping point

Source commit: `0772bdda701fe045fcb38d8b98ad90f8fabacac1` on local `main`.
The single push was reserved at `2026-09-27T03:12:55.807200+00:00` in
`decision-0036-execution-ledger.json` before the provider call. The UTF-8 CLI
used `NvidiaL4` and timeout `1800`. Kaggle returned exit 0 and accepted
[combined 002 version 1](https://www.kaggle.com/code/danielwuu/nvarc-m2-m3-combined-002)
at `2026-09-27T03:12:59.672679+00:00` (11:12:59 Asia/Taipei).

SHA-256 bindings:

| Member | SHA-256 |
| --- | --- |
| Plan file | `39f9c31d4fd2b25fb079d4cf258e916d68f29e0655c59ad176e304e2902edb69` |
| Notebook | `b4d2027da0f81396fb4fba17f20476a582bda3e52104e20a5c4e8bd073bf9931` |
| Metadata | `f6d216d4c05c6b619cf7dca2b37404c41379afcb77cb414e683184058fcb34b1` |
| Runtime wheel | `7d04854f89ecb6930827ba79044967a372442103d90ea5eb4c07feb5fe5493af` |
| Stage summary | `2109c08c7a514b72fbd49356293766bada9e593d1b1b910e9c9940ca489d8596` |
| Preflight | `4eee368338af99d3e9a8801fb64a6bb175aefd0be182a8fa230edabce1243b59` |
| Comparison | `1db810c6b5e2f8b837d25e02e37e3758f192a6ec0e9ab64bef0fe806003d5118` |
| Push receipt | `36d17f040b6fd7f7df51fc09e076574f249d676a3e122dc5d8f71c7051fcf756` |

The receipt is `decision-0036-push-002.txt` beside the package. Both the
predecessor diagnostic retrieval and replacement push are consumed. No status,
log or output request was made for the replacement, no Dataset was mutated,
and no heartbeat was resumed. Runtime startup, GPU acceptance and model
outcomes remain unknown. No further retry or retrieval follows automatically.
