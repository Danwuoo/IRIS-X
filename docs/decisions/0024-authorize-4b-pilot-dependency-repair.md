# Decision 0024: Authorize one 4B pilot dependency repair

Status: Accepted

Date: 2026-09-24

## Context

Decision 0023's accepted pilot 003 version verified the official ARC-AGI-2
competition mount, four L4 GPUs and pinned private model material. It failed
before model loading, training or generation because Kaggle's preinstalled
`torchao 0.10.0` is incompatible with the pinned PEFT 0.21.0. Its one kernel
launch and one terminal retrieval attempt are consumed. The owner reviewed
the distinct [pilot 004 local draft](../../trials/arc-agi-2-qwen35-nvarc/4b-pilot-004-draft.md)
and explicitly replied 「授權」 to the proposed next external attempt.

## Decision

Authorize exactly one new private Kaggle `SaveKernel` attempt for
`nvarc-4b-compat-pilot-004`, with intended kernel ID
`danielwuu/iris-x-4b-lora-pilot-004` and title `IRIS-X 4B LoRA pilot 004`.
Bind the unchanged [pilot 004 draft plan](../../trials/arc-agi-2-qwen35-nvarc/configs/draft-4b-pilot-004.json)
SHA-256 `57f581383f96661fc980a15e5a877654c8f324e6ddeb00da9865c1c907d024cd`.
If Kaggle accepts a version, make bounded status checks to terminal and
retrieve that version's output once. If the provider rejects before version
creation, retain the response; this decision does not authorize repeating
the same submission or another kernel identity.

The only runtime repair is offline removal of the optional preinstalled
`torchao` package before the pinned wheel installation, with a truth-free
dependency preflight record and a fail-closed absence check before PEFT import.
No Dataset update, new solver, workload change or dependency version change is
authorized. Keep the existing private Dataset v2, pinned
`Qwen/Qwen3.5-4B@851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a` material,
offline wheels, official `arc-prize-2026-arc-agi-2` competition mount,
private visibility and disabled Internet. The notebook may check only the
challenge file's presence, never its contents, solutions or evaluator truth.

Request `NvidiaL4`; one to four GPUs may be visible, but use only device 0
and require it to be an L4 with at least 22,000 MiB. Use only one synthetic
grid demonstration. Maximums: USD 0 paid cost, 1,800 seconds notebook wall
time, 1,500 seconds worker time, 300 seconds finalization reserve, two LoRA
optimizer steps, 128 training tokens, zero model generations, zero teacher
calls, one kernel push and one terminal output retrieval. No ARC scoring,
full SFT, competition submission, publication, external model API, retry or
resume is authorized.

Before the push, stage and inspect an approved package, verify its plan,
wheel, notebook and metadata digests, and atomically reserve the one push in
a local launch ledger. At terminal, retrieve once with UTF-8 local CLI output,
verify identity and truth-free counters, retain file digests, and stop. An
accepted kernel version consumes this decision whether the application
succeeds or fails. Preserve pilots 001–003 and their evidence unchanged.
