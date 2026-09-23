# Qwen3.5-4B pilot 003 pre-version retry

Status: **terminal dependency failure after verified competition mount and four L4s; Decision 0023 consumed**.

Pilot 002's `SaveKernel` call returned HTTP 400 without a version receipt or
model work. The owner directed retry. This distinct identity preserves the
failed pilot 002 bytes and uses the shorter title `IRIS-X 4B LoRA pilot 003`
and matching slug `danielwuu/iris-x-4b-lora-pilot-003`. The previous 54
character title is a possible, unproven source of the validation failure;
the corrected title and slug are 24 characters and match the installed
Kaggle CLI slugification result.

The [draft plan](configs/draft-4b-pilot-003.json) binds the same private
Qwen3.5-4B model Dataset v2 and offline wheels, official
`arc-prize-2026-arc-agi-2` competition mount for challenge-file presence
only, one L4 device 0 with at least 22,000 MiB, Internet disabled and USD 0
paid cost. Only one synthetic grid demonstration may be trained, for at most
two LoRA steps and 128 training tokens. There are zero model generations,
teacher calls, ARC scoring or competition submissions. The notebook's
hardware and mount preflights and runner's failure diagnostics remain the
same as pilot 002. The 1,800-second notebook, 1,500-second worker and
300-second finalization bounds also remain.

The local draft refuses execution until an authorization file binds Decision
0023, draft-plan SHA-256
`14f95a83953777e7261b530e38d5cf2d0b33486ee4dc62fe52ad435f91cfb443`,
new run ID and final kernel ID. One `SaveKernel` call is authorized for this
exact package. If a version is accepted, only that version may be followed
to terminal and retrieved once. If the provider rejects before a version,
retain its response and repair under a separate bound identity; never repeat
the same failed payload unchanged.

## Executed version and returned evidence

One `SaveKernel` request succeeded at
[`danielwuu/iris-x-4b-lora-pilot-003`](https://www.kaggle.com/code/danielwuu/iris-x-4b-lora-pilot-003),
version 1. Kaggle reported `COMPLETE`. The exact approved local plan, wheel,
notebook and metadata SHA-256 values were respectively
`90bef58e7db57c873a069174f311fa285522d8e55275ba57c50ee509b75b543f`,
`463a6a763d73c9f1f1b6d1faabebee5197feb5de93556ea7cb1d1ac3e6f74d09`,
`f9b2bab450d69a27cadea42757d2d16354c060da3fb9ae35415f3aceea44c6bb`,
and `0d58353fc15632fc89c4a7a04e332eb4d5fd0900e9dbd43af5e391737d69d241`.
The approved plan digest in the returned result and ledger was
`sha256:58573d99b792bffdcce7594961fae4f4fa3160f1087e7031b3edaa84cafebf39`.

The notebook and runner recorded four distinct `NVIDIA L4` devices, each
with 22,563 MiB visible to PyTorch and 23,034 MiB in `nvidia-smi`. The
official current competition mount resolved exactly once at
`/kaggle/input/competitions/arc-prize-2026-arc-agi-2`; no challenge contents
or answer file were opened. The mounted base material passed its exact file
checks, and the runner then failed while importing its ML dependencies:
`ImportError: Found an incompatible version of torchao. Found version 0.10.0,
but only versions above 0.16.0 are supported`. The installed PEFT 0.21.0
source raises this error when an optional `torchao` version is present below
its minimum. The local CPU PEFT environment has no `torchao` and imports
successfully. The 4B model was not loaded, and the ledger confirms zero
reserved/completed steps, zero training tokens and zero generations. The
application result is `failed` despite Kaggle's notebook `COMPLETE` state.

One terminal output command was attempted. Seven non-log files were retained,
but the CLI exited with a Windows `charmap` encoding error while downloading
the log, leaving a zero-byte log file. No second retrieval was made. Local
verification matched the returned plan, model manifest and wheel to their
approved hashes, checked the hardware/mount evidence and truth-free zero
counters, and retained a verification report under
`.irisx/arc-agi-2/qwen35-nvarc/4b-pilot-launch-003/`. Its SHA-256 is
`127263612af18f358c48ec526f20a2704a63ed2843b759b3f4040aa1d8b30d35`;
the returned result SHA-256 is
`c9ca918c003e2de3db4c168457d938ad8948f337e78440947dcaa572cb86feb6`.
The accepted version and retrieval attempt consume Decision 0023. Another
runtime package or model execution requires a new owner decision.
