# Decision 0022: Authorize one competition-mounted 4B pilot repair

Status: Accepted

Date: 2026-09-23

## Context

The distinct `nvarc-4b-compat-pilot-001` attempt consumed Decision 0021's
one push and retrieval. Its kernel metadata omitted the official ARC-AGI-2
competition source, and its application stopped at a hardware gate without
recording the observed GPU configuration. This does not prove the missing
mount caused the GPU failure. The owner asked whether the official source was
mounted, directed comparison with successful notebooks, reviewed the linked
[pilot 002 draft](../../trials/arc-agi-2-qwen35-nvarc/4b-pilot-002-draft.md),
and then said 「授權」. This creates a new identity; pilot 001 remains frozen.

## Decision

Authorize exactly one private Kaggle GPU kernel push for
`nvarc-4b-compat-pilot-002` with intended kernel ID
`danielwuu/iris-x-qwen3-5-4b-bounded-lora-compatibility-pilot-002`, bounded
status checks until terminal, and exactly one terminal output retrieval. Use
the existing private `danielwuu/irisx-arc-agi-2-trial-002-smoke-001` Dataset
version 2 with the same pinned
`Qwen/Qwen3.5-4B@851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a` material and
offline wheels. Mount exactly the official `arc-prize-2026-arc-agi-2`
competition source. The notebook may check only the presence of
`arc-agi_training_challenges.json` at the explicit current or legacy mount
path. It must not open challenge contents, solutions or evaluator truth.

The kernel must be private, Internet disabled, truth-free, and request
`NvidiaL4`. Use device 0 only, with one to four GPUs visible and at least
22,000 MiB on an L4 device 0. Record PyTorch and `nvidia-smi` hardware
diagnostics before model work. Maximums: USD 0 paid cost, 1,800 seconds
notebook wall time, 1,500 seconds worker time and 300 seconds finalization
reserve, two LoRA optimizer steps, 128 synthetic training tokens, zero model
generations, zero teacher calls, one kernel push and one terminal retrieval.
The synthetic demonstration remains the only training input. The run tests
4B load, LoRA gradients, reset, timing and peak memory. No full SFT, ARC
inference/scoring, competition submission, publication, external model API,
retry, resume or replacement kernel is authorized.

The authorization binds the unchanged draft plan SHA-256
`a2396c1ea45a783477353c088bad7dc8153a4edb93ee2c80418f4437adf7d7bb`.
Before push, stage a separate approved package, inspect its notebook,
metadata, wheel and plan digests, and atomically reserve the one push in a
local launch ledger. A failure consumes the launch. Retrieve terminal files
once, verify identity and truth-free counters, retain file digests and stop.
Any further external attempt needs new owner direction; Decision 0021's
consumed quota does not transfer.
