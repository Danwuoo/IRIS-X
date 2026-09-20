# Decision 0008: bind an offline Qwen3.5 Transformers runtime

Date: 2026-09-20  
Status: Accepted

## Context

The frozen `Qwen/Qwen3.8-27B` configuration declares model type `qwen3_5`
and records `transformers_version` as `5.8.0.dev0`. The bound Kaggle image
provides Transformers 5.0.0, which does not register that architecture. A
configuration-only load therefore failed before weights were loaded, before
inference began, and before any result package was produced.

## Decision

Trial 001 carries a closed, digest-bound Linux x86-64/Python 3.12 wheel set
whose effective Transformers version is the released version 5.8.1. The set
includes the exact base dependencies resolved for Transformers and the
`accelerate`/`psutil` pair required by the existing direct-to-GPU load path.
The outbound manifest binds every wheel's path, byte size, and SHA-256 digest.

The Kaggle notebook verifies the extracted Trial Dataset first, then verifies
and safely expands the wheel set beneath `/kaggle/working`. It supplies that
isolated directory through `PYTHONPATH`, keeps user site packages disabled,
checks that Transformers 5.8.1 exposes `Qwen3_5Config`, and only then invokes
the runner. It does not contact PyPI, Hugging Face, or any other network
service. The runner independently requires the effective Python, Torch, and
Transformers versions to equal the outbound runtime binding before it reads
model weights.

The previously uploaded Trial Dataset revision containing only the Kaggle
image's Transformers 5.0.0 is not execution-eligible. This decision requires
a newly built and manually uploaded private immutable Trial Dataset version.

This decision authorizes dependency materialization, package repair, offline
verification, and preflight only. It does not authorize the real model/solver run,
external spending, network-enabled execution, or scoring on Kaggle.
