# Compact 4B small complete pilot 001: terminal record

Status: **failed before model loading; no compact artifact or generation**.
Decision 0026 authorized this distinct private, Internet-disabled, USD 0
Kaggle attempt. The one accepted kernel version and one terminal output
retrieval are consumed. The staged package and returned evidence remain under
ignored `.irisx/arc-agi-2/qwen35-nvarc/compact-complete-launch-001/`.

## Identity and transport

The run ID is `nvarc-4b-compact-complete-001`. The approved metadata specified
`danielwuu/iris-x-4b-compact-complete-001`, but Kaggle warned that its title
resolved to another slug. Its accepted version 1 appeared in the owner's kernel
list at [`danielwuu/iris-x-compact-4b-pilot`](https://www.kaggle.com/code/danielwuu/iris-x-compact-4b-pilot).
The provider reported `KernelWorkerStatus.ERROR`. No second push was made.
One output retrieval from that exact version succeeded with UTF-8 CLI output
and returned 11 files, including the phase record and log. There is no
`result.zip`, checkpoint, or compact model directory.

The returned approved plan, visible source, original model manifest, offline
wheel manifest, and current IRIS-X runtime wheel have the exact prelaunch
SHA-256 values in [Decision 0026](../../docs/decisions/0026-authorize-nvarc-4b-compact-complete-pilot.md).
The returned phase record SHA-256 is
`de9d48ce61ac65bc1b54a8746e029a0948c7fade4a7057b1dc3821932f4e790d`;
the log SHA-256 is
`c4bf29f033229c8fef86eb75841eeb0cf425ac396247f8d918f8f3308577c736`.
Local `terminal-verification.json` SHA-256 is
`5e04ffbf076680083194efba7e289f8dfa587745090fc6997f1c028d97028e5d`.

## Observed failure

The official competition challenge file was checked for presence only; its
contents were not read. Kaggle exposed four distinct NVIDIA L4 devices, each
with 22,563 MiB visible to PyTorch. Offline installation of the pinned
dependencies succeeded, and optional `torchao 0.10.0` was removed before PEFT
import. The application phase record contains `preflight` followed by `failed`
after about 1.8 seconds of application runtime. The failure is
`ValidationError: Dataset v2 material inventory is not closed`.

The verifier requires the Dataset mount root's immediate filenames to equal
the union of the 14 pinned model filenames and 34 pinned wheel filenames.
Local inspection of the returned manifests confirms that those 48 expected
names are unique and disjoint. Consequently, the observed failure is the
mounted root's filename set differing from that union. The run did not record
the actual directory listing, so it cannot establish which names were extra
or absent. It stopped before hashing the 9.34 GB model weights, conversion,
model load, LoRA, outbound/checkpoint creation, DFS, or result packaging.
There were zero training steps, training tokens, model generations, DFS
forwards, verification forwards, and teacher calls.

This attempt gives hardware, mount-presence, dependency, and transport
evidence only. It does not verify 4B compact conversion, memory fit, grid
generation, ranking, ARC accuracy, or the complete GPU flow. The accepted
version cannot be repaired, resumed, or rerun under Decision 0026. A future
attempt needs a separate owner decision and should first obtain a closed
Dataset root inventory and bind a title that resolves to its intended slug.
