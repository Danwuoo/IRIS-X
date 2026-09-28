# Combined 006: public-witness M2/M3 owner-Editor notebook

Decision 0040 authorized one private QUICK_SAVE of distinct
`nvarc-m2-m3-combined-006` without an agent run. The sole save was accepted
as version 1 on 2026-09-28 and is consumed. The owner started it in
Editor and supplied `/kaggle/working/結果.zip`. The
[digest-bound diagnosis](combined-006-editor-diagnosis.md) confirms two
completed branches but no M2 candidates or M3 pairs. This observation does
not establish ARC correctness or SDG pair acceptance.

Notebook: [nvarc-m2-m3-combined-006](https://www.kaggle.com/code/danielwuu/nvarc-m2-m3-combined-006).
Provider kernel ID: `136217857`. One SaveKernel request used
`KernelExecutionType.QUICK_SAVE`, private visibility, Internet off and
existing sources. No agent session start or status/output request followed.

M2 now enforces both the public 6×6 output shape and the public demos'
input-color preservation under every augmented view, with one TTT and four
bounded generation calls. M3 gives its model the exact public-rule-derived
mix target while retaining the original semantic and isolated program gates.
The precise limits and stop conditions are in
[Decision 0040](../../docs/decisions/0040-save-nvarc-public-witness-repairs.md).

Plan digest:
`sha256:2479810ca715523c62263d1de9256146081edbfe3b2a3ce79af053c76d625637`.
Offline package: `.irisx/arc-agi-2/qwen35-nvarc/m2-m3/combined-editor-006-final/`.

Exact local bindings (SHA-256):

| Artifact | SHA-256 |
| --- | --- |
| Saved notebook | `6bcff1319d77b2c18b0b1afc5a6247774a2221a1e5eb0ed484e3f85bb463e1aa` |
| Metadata | `13109f49c3f9c8ae03453ca692c284bed91016bb96bf71577f5762861c31240b` |
| Plan bytes | `9351c5441352b002a3eb66b968150e74fd6055c98e9e3cb34c8f96f3cd90ccb7` |
| Packaged wheel | `ad900da77c4281f77d97f00fecdba36ed479a2c001ccc85006f354fdfdd123e9` |
| One-save transport script | `2d0abf90cdb834330c64c556ff6e49d4a940523c3ea4e82ec8d3fd5701e098ba` |
| SDK request | `d7dee19ea9400a9f3bc8444b480ddc5c8b31e301fef05b99864f650f6d3c8216` |
| Provider receipt | `b0123fa3b5753f25bd3c8aee6988801e104d5b304f4b33a375296f19ebd93334` |
| Consumed save ledger | `89de75320410f90184831136a4b7f17551695bb30f7a5b0382f6cdf03c29631d` |
| Offline preflight | `0e08cf5d4f099c556957e9e865b86e2fde5716f539a75407560ccc9da887e887` |

The request, receipt, ledger and preflight remain under the ignored local
`.irisx/arc-agi-2/qwen35-nvarc/m2-m3/` directory. Offline exact-package
preflight, hardware fixtures and approved/draft execution guards passed. The
full repository check passed 274 tests (four optional skips); separate tiny
model and saved-response tests exercised the new M2/M3 worker paths. These
checks did not establish full 4B runtime quality; the subsequent owner result
is documented above. No agent run,
status/log/output query, retrieval, Dataset mutation or automatic retry is
authorized.
