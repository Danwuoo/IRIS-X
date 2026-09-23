# Qwen3.5-4B pilot 004 dependency-repair draft

Status: **local draft only; no Kaggle push or execution authorized**.

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
Its notebook refuses to run without an exact, separate owner authorization.
The offline stage and test pass. The current draft plan SHA-256 is
`57f581383f96661fc980a15e5a877654c8f324e6ddeb00da9865c1c907d024cd`.
The current local draft wheel, notebook and metadata SHA-256 values are
`70241f00764bad3849a29aae20dbde7d6e20657c76ebca6f374c0f279c8f6e22`,
`73753d8a1f0f9ad41bb5ac39f83299c24c853a8996ba0f0ccf8d942c8eeae237`,
and `481d9d073c21405077862055eb6b1e52adda381bb17133a9077aefd6b0e794d1`.
An approved package would have different plan and notebook hashes and must be
bound separately before any provider mutation.

For a future authorized terminal retrieval, set `PYTHONIOENCODING=utf-8` in
the local CLI process so a Unicode log line does not repeat pilot 003's
Windows `charmap` download failure. This note does not authorize another
retrieval of pilot 003.
