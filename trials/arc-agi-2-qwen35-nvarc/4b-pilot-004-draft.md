# Qwen3.5-4B pilot 004 dependency repair

Status: **version 1 runtime complete and locally verified; Decisions 0024–0025 consumed**.

The [pilot 003](4b-pilot-003.md) accepted version verified the official
`arc-prize-2026-arc-agi-2` mount, four distinct L4 devices and the pinned
private model material. It then failed before model loading because Kaggle's
preinstalled `torchao 0.10.0` is incompatible with the pinned PEFT 0.21.0.
Its accepted launch and terminal retrieval attempt consumed Decision 0023.
This draft uses a new run and kernel identity; it does not mutate or retry
pilot 003.

The [draft plan](configs/draft-4b-pilot-004.json) keeps the same private
Dataset v2, pinned Qwen3.5-4B revision and offline wheels, official competition
mount for challenge-file presence only, private visibility, disabled Internet,
`NvidiaL4` request, and USD 0 paid cost. It keeps one synthetic grid
demonstration, at most two LoRA steps and 128 training tokens, zero model
generations and teacher calls, and the 1,800-second notebook/1,500-second
worker/300-second finalization bounds. Only device 0 may be used. There is
no ARC scoring, competition submission or publication.

The notebook first records the hardware and mount preflights, then detects
the optional `torchao` package. If present, it runs an offline `pip uninstall`
and records the version and outcome in a truth-free dependency preflight file.
It fails closed if the package remains or removal fails. The runner checks
again before importing PEFT. No other solver, workload or pinned dependency
version is changed. Removing `torchao` is supported by the locally installed
PEFT 0.21.0 source path, but the repair has not yet been tested on Kaggle's
GPU image.

The staged draft is `approved: false` with a `DRAFT-DO-NOT-PUSH` kernel ID.
Its notebook refuses to run without the exact Decision 0024 authorization
binding and separate approved package.
The offline stage and test pass. The current draft plan SHA-256 is
`57f581383f96661fc980a15e5a877654c8f324e6ddeb00da9865c1c907d024cd`.
The current local draft wheel, notebook and metadata SHA-256 values are
`70241f00764bad3849a29aae20dbde7d6e20657c76ebca6f374c0f279c8f6e22`,
`73753d8a1f0f9ad41bb5ac39f83299c24c853a8996ba0f0ccf8d942c8eeae237`,
and `481d9d073c21405077862055eb6b1e52adda381bb17133a9077aefd6b0e794d1`.
An approved package has different plan and notebook hashes and must be bound
separately before provider mutation. Decision 0024 authorizes exactly one
such package and launch with one terminal retrieval; it does not authorize
another retry or Dataset update.

The first approved-package `SaveKernel` request returned HTTP 401 because the
local OAuth access token had expired at `2026-09-23T16:00:14Z`. The owner-kernel
list after credential refresh contained no pilot 004 version. Decision 0025
binds one additional transport attempt to the *unchanged* approved package:
plan, wheel, notebook and metadata SHA-256 values
`cca98adaab611c2eff11f099b875785fe9d4b64443d4bbeb27ba6533fdf5ef46`,
`70241f00764bad3849a29aae20dbde7d6e20657c76ebca6f374c0f279c8f6e22`,
`08627fa4ba2cbaff101bb6fb7ed4f0d4c5af291f1b88685dca69d61513886ea9`,
and `b4907d434348128fe0db9f495963e0ef5b8fb88ea6c5a099db4480c462e8b013`.
This did not permit a third push or a changed workload.

For the authorized terminal retrieval, set `PYTHONIOENCODING=utf-8` in
the local CLI process so a Unicode log line does not repeat pilot 003's
Windows `charmap` download failure. This note does not authorize another
retrieval of pilot 003.

## Executed version and terminal evidence

The one Decision 0025 retry of the unchanged package was accepted at
[`danielwuu/iris-x-4b-lora-pilot-004`](https://www.kaggle.com/code/danielwuu/iris-x-4b-lora-pilot-004),
version 1. Kaggle reported `COMPLETE`, and the application result also reports
`complete`. One terminal output retrieval succeeded with UTF-8 local CLI
output; the log and all eight other expected files were retained. The result
plan digest is
`sha256:6162bb4426ff848d843e9b2b56d006e8801ce52bfd794922cad55d646d01fc26`.
Local verification matched the returned plan, wheel and model manifest to
the approved package hashes and confirmed the result/ledger identity and
truth-free counters.

The dependency preflight observed `torchao 0.10.0`, removed it with exit code
0, and found it absent afterward. The notebook and runner verified the one
official competition challenge mount and four distinct NVIDIA L4 GPUs, each
with 22,563 MiB visible to PyTorch. Only device 0 was used. The pinned
Qwen3.5-4B loaded and completed two synthetic LoRA optimizer steps using 16
total training tokens. The returned losses were 6.4069 and 4.0467; attention,
delta, embedding and head gradient groups were all observed, and adapter
reset matched its initial state. Peak allocated GPU memory was 9,419 MiB.
There were zero model generations and zero teacher calls. No ARC task was
trained or scored, so this establishes only the bounded 4B compatibility
path, not full NVARC reproduction or ARC accuracy.

The ignored local evidence is under
`.irisx/arc-agi-2/qwen35-nvarc/4b-pilot-launch-004/`. Returned result
SHA-256 is
`4c501af39032542f9b16f53fd373f0b582b5ef6151f4b360c348ee20484cc088`;
the local verification report SHA-256 is
`e529b66502f45553d462e7dbddfa72fd03feaa3d319ad90d96ebf64f5016b3b1`.
The first HTTP 401, accepted retry, terminal monitoring and one retrieval are
all consumed. Any additional external experiment requires new owner direction.
