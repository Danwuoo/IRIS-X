# Decision 0042: Save combined startup diagnostics

Status: Accepted
Date: 2026-09-28

The owner supplied combined 007's partial Editor ZIP and directed repair
and QUICK_SAVE if needed. It verifies the exact saved payloads but stops at
the hardware-inventory event with no terminal cause or worker results. The
owner cannot distinguish a manual interruption from an automatic stop.
Decision 0041's save identity remains consumed. This decision authorizes
exactly one new private, unexecuted `nvarc-m2-m3-combined-008` QUICK_SAVE.
The exact plan is
`trials/arc-agi-2-qwen35-nvarc/configs/m2-m3-combined-editor-008.json`,
digest `sha256:f8644274acac94f860839b1c93c2ddf54e82dd1ccdbc906027bcc5d36b873b49`.

Only parent startup diagnostics change. Separate events bracket Torch import,
the `nvidia-smi` query and hardware mapping. The parent catches
`BaseException` at its outer terminal boundary so interrupt-class exits
receive a terminal event and a truth-free aggregate before the existing
`finally` ZIP packaging, then re-raises. A hard process kill may still
prevent packaging. A controlled local interruption at Torch import must
produce a ZIP with `KeyboardInterrupt` and zero worker launches. M2's
grammar-completion workload and M3's four-stage teacher prompts/semantic
gates are byte-identical in behavior to combined 007, apart from their
distinct run, plan and worker bindings.

Existing Datasets, two distinct BF16 L4 workers, Internet disabled, USD 0,
one TTT/four M2 generation calls, four M3 teacher calls, token and program
limits, and the 1,800-second session remain. No hidden truth, scoring,
method promotion or competition submission is added.

After exact offline package, guard, hardware-fixture and controlled-interrupt
checks, reserve and send one `KernelExecutionType.QUICK_SAVE` request. Stop at
its receipt. A rejected or uncertain request consumes the allowance. No
agent execution, status/log/output query, retrieval, monitoring, Dataset
mutation, paid run or automatic retry is authorized.

Status: `trials/arc-agi-2-qwen35-nvarc/combined-notebook-008-editor.md`.
