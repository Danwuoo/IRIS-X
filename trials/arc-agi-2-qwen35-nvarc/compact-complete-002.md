# Compact 4B small complete pilot 002: terminal record

Status: **failed during compact conversion serialization**. Decision 0027
authorized a distinct private, Internet-disabled, free kernel for program-error
repair. Kaggle accepted
[`danielwuu/iris-x-4b-compact-complete-002`](https://www.kaggle.com/code/danielwuu/iris-x-4b-compact-complete-002)
as version 1 under the exact intended slug, then reported
`KernelWorkerStatus.ERROR`. The staged package, launch ledger, terminal log
snapshot and partial output are retained under ignored
`.irisx/arc-agi-2/qwen35-nvarc/compact-complete-launch-002/`.

The approved plan, current IRIS-X wheel, notebook and metadata SHA-256 values
are respectively `09ba2052f4e71414646ff0032fae8c7cb6c5cee199d087c6d55844375da0e04f`,
`30d328df4dca4a72f951993b3b7b497b44ee8ab7e2a425ec7979c3c6f0be2648`,
`d1d04834cf2cf2f6f333ca9c4050c0b8a577cfcd13e2a30f1f81a2abb7a31704`,
and `5730966dbe43346fd9fa89ae6a5e437717d410ecd63cfdd23161929937170809`.
The private Dataset file listing showed all 48 pinned model and wheel files
with expected byte sizes, plus the nine known legacy files under
`trial-002-smoke-002/`. The exact legacy tree was accepted by the new
closed-world gate; source verification and model save were reached.

The terminal log pinpoints `convert_qwen35_checkpoint` writing
`grid-tokenizer.json`: its `symbols` field was a Python tuple, which canonical
JSON rejects with `ValidationError: $.symbols: unsupported canonical JSON value
tuple`. This happened after the large compact weights had been written but
before reload, material manifest, task-local adaptation, generation,
checkpoint or result packaging. No completed GPU flow or model result is
claimed. The terminal log snapshot SHA-256 is
`df3d132498f05354d91b113066526c670a3eaffe70543b529e5748130089abd9`.

One terminal `kaggle kernels output` command was attempted. It downloaded
three small compact files, then failed with `IncompleteRead` after
6,265,996,352 of 7,807,303,872 bytes of the single weight file. The local
weight placeholder is zero length; no compact material or result was verified.
The failed retrieval is retained as a failure, not repeated for this version.

The local repair serializes `symbols` as a JSON list and adds an actual tiny
Qwen3.5 converter/reload/material-verification regression test. The next
distinct attempt also requests 2 GB output shards so a single download member
does not exceed the size that failed here. This version and its bytes remain
frozen.
