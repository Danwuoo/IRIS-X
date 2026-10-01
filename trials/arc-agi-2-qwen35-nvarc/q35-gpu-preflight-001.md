# Qwen3.5 original-corpus GPU preflight 001

Date: 2026-10-01 (Asia/Taipei). Terminal state: **partial-backend-verified,
long-sequence-step-failed**. This is a Qwen3.5 port resource probe under
[Decision 0051](../../docs/decisions/0051-run-qwen35-kaggle-gpu-preflight.md),
not full NVARC SFT, original Qwen3/NeMo parity, or ARC quality evidence.

## Executed workload and outcome

The owner chose the existing Qwen3.5 port. One private
[`nvarc-q35-gpu-preflight-001`](https://www.kaggle.com/code/danielwuu/nvarc-q35-gpu-preflight-001)
version 1 was accepted at 17:02:20 Taipei, using `SAVE_AND_RUN_ALL`, Internet
disabled, the existing compact-base/offline-wheel Datasets, and USD 0 paid
cost. The prior successful official competition mount was retained for the
four-L4 transport; no competition file was opened. Earlier kernels were not
queried or changed. No Dataset was uploaded or mutated.

Eight frozen, whole original-corpus records were scheduled across six sources,
47,078 input tokens in total, without filtering or truncation. Four records
cover heavy-source maxima of 9,330, 11,170, 11,196 and 11,196 compact tokens.
Both parent identities and all exposure tags remain attached. This material
includes previously exposed/evaluation-derived ancestry and is not a clean
or fresh evaluation set. No generation, teacher invocation or scoring ran.

| Check | Returned evidence | Conclusion |
| --- | --- | --- |
| Hardware | Four distinct BF16 NVIDIA L4 UUIDs, each 23,659,151,360 bytes; torch 2.10.0+cu128, CUDA 12.8 | Passed |
| Host and disk | 198,787,977,216 available host bytes; 1,201,713,496,064 free scratch bytes; working/scratch devices distinct | Passed at startup |
| Full-parameter source optimizer step 1 | Four complete sequences, 4,186 input / 2,961 supervised tokens; AdamW 0.9/0.98, epsilon 1e-8, weight decay 0.1, clipping 0.5, source warmup LR 1e-6 | One step completed |
| Numerical health | Global assistant-token mean loss 0.1121660752; pre-clip gradient norm 11.77361393; finite nonzero gradients on all four ranks; global weight fingerprint changed | Passed for step 1 only |
| Checkpoint | Closed manifest for 10 ephemeral members totaling 46,860,796,760 bytes | Save and inventory verification completed; checkpoint bytes were not retained |
| Resume | All ranks report `checkpoint-restored-and-evicted`, after the exact saved-weight fingerprint gate and model/optimizer/scheduler/RNG restoration | Restore gate reached; resumed training did not complete |
| Long-sequence step 2 | All ranks entered the fixed heavy-source forward; rank 3 traceback is inside `loss.backward()` with `CUBLAS_STATUS_ALLOC_FAILED`; ranks 0–2 report NCCL watchdog hangs | Failed; no second optimizer-step completion or final checkpoint/result |

Step 1 GPU peaks were 18.225–18.255 GiB allocated and 21.461–21.637 GiB
reserved per GPU. The synchronized step computation took approximately 11.21
seconds, but the complete first worker including load/checkpoint inventory
took 569.87 seconds. Whole-notebook terminal capture took 2,060.41 seconds.
Those timings do not establish long-sequence throughput or full-SFT duration.

The retained logs show both a cuBLAS allocation failure and a distributed
watchdog stall. Their exact causal ordering and the roles of live tensors,
allocator fragmentation and collective progress have not been isolated.
The first step already consumed much of one L4's memory. This observation is
consistent with resource pressure but is not proof that a particular memory
repair will solve the problem. The longest whole-sequence training gate remains
closed; the 42,892 step-2 input tokens are attempted workload, not completed
optimizer-step tokens. No larger training run follows from this result.

## Material and package bindings

The exact [approved plan](configs/q35-gpu-preflight-001-plan.json) uses FP32
parameters and optimizer state with BF16 compute, source token-normalized
loss, microbatch 1 / global batch 4, and unpacked independent sequences.
Original Megatron packing, attention/DeltaNet state isolation and global
batch 256 remain unverified. The 12,716-step schedule is a source reference,
not a claim that 12,716 steps were executed.

| Binding | SHA-256 / canonical digest |
| --- | --- |
| Original corpus manifest | `63277d77d2af04e2aba487e5a69f64df5113d2d12bc66a449232e1ac70fa6eff` |
| Compact base material | `sha256:1a8eebd70d811e58c35dc5b1ee27dc18bd73a1066c3ab33adf96ed8427d4c982` |
| Plan bytes | `e21cfe6fe020d275231f5ab75e257dd13ccceb05d2e63c28181f218eb8090c2d` |
| Canonical plan | `sha256:96fdad44b0a044e209466e1fb4af8fc5c20deb2a2355a647d6ae56de150e4a7a` |
| Worker identity | `sha256:4687615c112acde1cd37a2068b03174e2a53a0726543f7e6cc2fe20ff39c891c` |
| Whole sample bytes | `070f1c476e66b449ca1b63aa3a747c3784e0377aa15e0845a60a70e42c3ca333` |
| Offline wheel manifest | `f9106fe3d007d4b0963d12db6e7488a91b59e7824f8f0d192b4fcc45f8050887` |
| Embedded runtime wheel | `6ca4155946458d511b4927a784eed2b84dde2107e67c96923c80c3d7b88c335f` |
| Saved notebook | `58ae45cd671f47a3f13528aa1f875f44f31743eb3cd39c896ae95f717d8b9b02` |
| SaveKernel wire request | `e939168cd36aac58696706c1c71a5c5e5efe2d3a93d4347f0c184c90d9dfa87c` |
| Version-1 receipt | `788f65601882d09140abc2151f617ac92a400e5575607c1f7c9d9516f4c48e5e` |
| Returned diagnostic ZIP | `c879e29dc06758c8ae8fff89e107b2187f01f2c7257bb6d993088fae287393d2` |
| Provider log | `cf17fbd608a2c7f7933b9c65c75b62d3a1435a09ed73734df7a3fb183b99883a` |
| Final local verification report | `2e1fcddfd3f37889ed2b17bb97b578e313c47785d877fd69178fccb4a53c58ba` |

All 23 listed data members passed closed-inventory, ZIP CRC and digest checks.
Returned plan and embedded-payload bindings match the sole accepted package.
Step-1 lineage/counts, checkpoint identity, loss/gradients and rank UUIDs were
independently checked. The archive contains diagnostics and checkpoint
inventories, not sample tokens, model weights or optimizer shards.

Local disposable artifacts are under
`.irisx/nvarc-original/runs/nvarc-q35-gpu-preflight-001/`:

- `package-l4/`: the accepted immutable notebook, samples and runtime wheel.
- `execution-final/`: wire, ledger, exact receipt, offline preflight, and sole
  terminal retrieval (`retrieved/gpu-preflight-result.zip`, `provider.log`).
- `verification-final.json`: independent final verification; the earlier
  smaller `verification.json` is also preserved.
- `local-tests.log`: source loss and real two-rank tiny CPU checkpoint/resume
  differential checks; SHA-256
  `626498e1d4c96aa1a45c75af47b283be304a986cdcc0265fd2ecf346fa772095`.

The earlier no-competition `package/` and initial `execution/` journal were
offline drafts only; neither issued a SaveKernel request. A local SDK session
initialization error was caught before reserving/sending the sole mutation.
The fixed tool then sent exactly one SaveKernel request. The active turn was
interrupted after its receipt; it did not monitor continuously while absent.
On continuation, one numeric `version_label="1"` status query returned 404;
the installed official CLI's no-label query returned `ERROR`. Both checks are
counted. One output-list request and one ZIP download consumed the sole
terminal retrieval. The exact returned plan/payload digests establish the
saved-package binding; the status API itself does not return a version number.

## Reproduction and remaining work

The stage/preflight and result verifier are offline. The execution tool's
`submit`, `status` and `retrieve` actions are deliberate provider operations
with atomic reservation and no mutation/download retries. Do not replay them
for this consumed identity. Local verification can be repeated without a
provider call.

Local source-loss and two-rank CPU continuous-vs-resumed tests passed, and
archive tampering/unsafe members are rejected. The final strict run passed
both numerical/checkpoint tests in 98.496 seconds; the final pure scope/archive
run passed both tests. `python tools/repository_check.py --all` passed 304
tests in 256.126 seconds, with four existing optional skips. The earlier
interrupted repository test log is retained and is not described as a passing
run. All validation was local/offline and made no additional provider call.

Final validation logs under the run root have these SHA-256 bindings:

| Log | SHA-256 |
| --- | --- |
| `strict-tests-final.log` | `ac3966b1205cf6e8ec55fe52ff9b06cc508f0fc09488c6b4b816e1c0ab38a183` |
| `archive-scope-tests-final.log` | `421e57fcfc4dc1a83d573b823518c5a0ed007bf9f29d0d0526c25ddb380d85cf` |
| `repository-check-final.log` | `7c8d1f3cbeb86a212f8eba901b7c3764655f69998f6d8330c050a34ec42c7597` |
| Final execution ledger | `8e3a8ee8faf8e9c5299f38662ead92d92ce13263434e9d8195818d532db0062f` |

The next local work is to isolate resumed long-sequence live-memory/collective
behavior and prepare a separately reviewed resource repair. Decision 0051's
submission and retrieval are consumed. No second kernel, repeat download,
full SFT, teacher work or quality promotion is authorized by this observation.

A future repair needs per-rank live/reserved-memory observations before and
after restoration, forward and backward, plus bounded failure capture.
Preserving FP32 AdamW moments while reducing their GPU residency during
forward/backward is a candidate to evaluate locally before another execution.
The optimizer's foreach temporaries are another possible peak-memory factor;
[PyTorch 2.10's AdamW documentation](https://docs.pytorch.org/docs/2.10/generated/torch.optim.AdamW.html)
describes its extra temporary-memory cost. Neither candidate has been tested
on this GPU workload. Do not shorten the frozen whole sequences or disable
the NCCL watchdog and describe that as a successful reproduction.
