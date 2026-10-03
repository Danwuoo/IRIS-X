# Original native TTT 008 Editor completed epoch diagnosis

Authority: [Decision 0056](../../docs/decisions/0056-save-native-ttt-timeout-repair-for-owner-editor.md)
and the owner's returned local archive.
Status: digest-bound complete original-runtime task-local epoch and exact reset.
Date: 2026-10-03 (Asia/Taipei).

The owner supplies `結果.zip` in the main checkout root and reports `Run success`.
Independent local verification matches the [saved 008 package](native-ttt-008-editor.md),
approved plan digest
`sha256:6e7b20de68182151e3f92511bc9202d6b7e813e690f39ee8ca3bfac2e240f897`,
all **36 manifest members**, all 41 original source/metadata bindings, the exact
published model material and four distinct BF16 L4 UUIDs. The archive is
639,074 bytes, with 8,055,924 uncompressed bytes including its manifest;
SHA-256 `2a8acbc25e5f4b673e3982c550914728ddf8db350191cc4b9cf823db8014dfec`.
The accepted QUICK_SAVE receipt and consumed journal retain their prior hashes.
No provider request, retrieval, model call or scoring is made during diagnosis.

## Completed work

| Observation | Verified value |
| --- | --- |
| Native source views and context | 128 exact raw input/label vectors; context 8,192 |
| Completed model forwards / Trainer steps / optimizer updates | 128 / 128 / 128; no incomplete reservation |
| Input / supervised tokens | 955,392 / 476,160 |
| Gradients per update | All 506 finite; maximum observed post-clip norm 0.2051413953 |
| Native scheduler | All update rates exactly match the same-platform pinned source oracle; 13-step warmup |
| Terminal Adam state | 506 finite BF16 states, each at step 128; 528,564,224 parameter elements |
| Retained terminal moment inventory | 2,114,256,896 moment bytes represented; moment tensor bytes are not exported |
| Saved native trainable tensors | All 506 fingerprints change during training |
| Reset | All 506 baseline fingerprints restore exactly; optimizer discarded |
| Generations / teacher calls / paid USD | 0 / 0 / 0 |

The source-row multiset is exhausted exactly once, every backward/update completes,
Trainer global step is 128 and epoch is 1.0. Losses are finite, ranging from 0 to
0.0022874773. These are task-local training losses, not an ARC correctness score.
All terminal moment entries are finite, on `cuda:0`, and match the exact native
adapter topology. The unchanged native scalar recipe differs from the retained
cross-platform reference by at most three ULPs; actual optimizer rates match the
same-platform oracle exactly through the last update at index 127.

The parent verifies four L4 devices, but training uses one sequential rank-zero
model worker. This is not a four-worker training observation. The complete result
now verifies the full long-task native training epoch, changed trained tensors,
terminal optimizer inventory and reset that were absent after 007's timeout.
The original 007 prefix remains frozen; 008 restarts from the published checkpoint.

## Timing and memory

| Observation | Measured value |
| --- | --- |
| Training wall time | 862.043118859 seconds (about 14 minutes 22 seconds) |
| Worker wall time | 974.203979358 seconds |
| Parent terminal wall time | 1,068.025965460 seconds (about 17 minutes 48 seconds) |
| CUDA peak allocated / reserved | 13,897,781,248 / 15,451,815,936 bytes |
| Approved parent / child bounds | 3,600 / 3,000 seconds, with a 120-second finalization reserve |

The completed run remains within both finite deadlines and the verified L4 memory
capacity. These are measurements of this owner-Editor run; historical native-clock
parity, sustained multi-task throughput and a reproducible performance improvement
are not established by comparing this result with 007's interrupted session.

## Retention and limits

An exact verification copy, immutable independent proof and original root input
are retained under ignored
`.irisx/nvarc-original/runs/nvarc-original-qwen3-native-ttt-008/owner-editor-report-20261003-001/`.
The original input is moved reversibly to `owner-root-結果.zip` there to preserve
the repository root layout, with its bytes verified against the retained copy.
The independent proof SHA-256 is
`33ecfdcaecb4b1967a026ac5d1871af66d64cc75c782019657641d0e17b7e4b4`.
[Durable diagnostic evidence](configs/native-ttt-008-editor-diagnosis.json)
binds the archive, proof, hardware, work ledger, measurements and unchanged save.

This closes one complete native task-local training-epoch evidence gate. No
generation, candidate ranking, ARC evaluation or checkpoint export was requested
or performed. Full original SFT, original end-to-end solver/numerical parity,
SDG semantics, TRM scale/version and independent ARC quality remain open.
The returned result grants no new QUICK_SAVE, external run, query, retrieval,
Dataset mutation, scoring or promotion.

Full offline repository validation passes 405 tests with four optional skips in
392.583 test seconds. Repository layout and diff checks pass. The exact validation
log and verifier SHA-256 bindings are retained in the durable diagnostic evidence;
no scientific program, submitted package or consumed journal is changed.
