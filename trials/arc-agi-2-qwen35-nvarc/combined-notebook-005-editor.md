# Combined 005: repaired M2/M3 owner-Editor notebook

Decision 0039 authorized one private QUICK_SAVE of
`nvarc-m2-m3-combined-005`, with no agent run. The sole save was accepted as
version 1 on 2026-09-28 and is consumed. The owner will start the saved
notebook in Editor with two L4 GPUs and Internet disabled, then supply
`/kaggle/working/結果.zip` for local analysis. A saved notebook is **not** a
verified M2 candidate or accepted M3 SDG pair.

Notebook: [nvarc-m2-m3-combined-005](https://www.kaggle.com/code/danielwuu/nvarc-m2-m3-combined-005).
Provider kernel ID: `136208688`. One SaveKernel request used
`KernelExecutionType.QUICK_SAVE` with private visibility, Internet off,
existing sources and no run fallback. No agent execution or status/output
request followed.

M2 now conditions search on the 6×6 output shape shared by its public demos
and uses a 0.02 per-token floor, with one TTT and four bounded calls. M3
provides public-demo-derived rule checks, accepts a single fenced JSON object,
and preserves the semantic and isolated program gates. The bound materials,
two workers, cost and timeout are described in [Decision 0039](../../docs/decisions/0039-save-repaired-nvarc-combined-editor.md).

Plan digest:
`sha256:24d2f2a1a31c49f968c8076c73b4c09cfec8bad5f8979b218c40c391c84aedf5`.
Offline package: `.irisx/arc-agi-2/qwen35-nvarc/m2-m3/combined-editor-005-final/`.

Exact local bindings (SHA-256):

| Artifact | SHA-256 |
| --- | --- |
| Saved notebook | `9d1d8363cfc25841ed76385d02492623e8b45a1a68971e3ce4f186eced26afba` |
| Metadata | `aeb3b3270b90750f6ec166629231f4ed47c5153d9dbd7e6821ce2f26ec36d45f` |
| Plan bytes | `21ddb1b8a935acbc707df68ff1a58f5e315fd900305c6ab5dcb48d733558bc4e` |
| Packaged wheel | `487c5a5513ccb6103a3848f66a611b972cec58ba15e20436bfbd9afbc5a25539` |
| One-save transport script | `82ed909cd075f72b96cfb880b3337bdb16241301266afaf7893208330b0e7ed8` |
| SDK request | `aa1eab98f50fe9f4d32cbd114162f80e1a05e0980db703c655307714060352d4` |
| Provider receipt | `8c3a4f10355756ab7681ddebae0ff9f40d94113b747067d8b43bc3279690f92d` |
| Consumed save ledger | `b4f84bfc6c725180ba8eac8d8cfa59f3516aa84afddabc7d9443307946fdf80c` |
| Offline preflight | `c2be6f760bc074eb8604fe948457082ca0651deba7797b996b95e2006384bd95` |

Request, receipt, ledger and preflight are retained under the ignored local
`.irisx/arc-agi-2/qwen35-nvarc/m2-m3/` directory. The ledger records one
reserved and completed SaveKernel send. The full repository check passed 272
tests (four optional skips); separate local tiny-model M2 and saved M3 tests
passed. These checks do not establish 4B runtime quality. No agent execution,
status/log/output request, retrieval, monitoring, Dataset mutation or retry
is authorized.
