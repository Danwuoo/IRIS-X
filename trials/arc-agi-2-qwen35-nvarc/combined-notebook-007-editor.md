# Combined 007: owner-Editor QUICK_SAVE

Decision 0041 authorizes one private QUICK_SAVE of distinct
`nvarc-m2-m3-combined-007`. The owner will start it in Editor and provide
`結果.zip`. No agent session start, monitoring or result retrieval is authorized.
The sole save was accepted as version 1 on 2026-09-28 and is consumed.
Notebook: [nvarc-m2-m3-combined-007](https://www.kaggle.com/code/danielwuu/nvarc-m2-m3-combined-007).
Provider kernel ID: `136223231`. One SaveKernel request used
`KernelExecutionType.QUICK_SAVE`, private visibility, Internet off and the
existing sources. No agent session was started or queried; runtime is
partially observed in the [owner-supplied ZIP](combined-007-editor-diagnosis.md).
That ZIP ends during startup and contains no M2/M3 outcome.

M2 uses public-shape and palette grammar completion with model-ranked legal
colors after one shared TTT step and four bounded generation calls. M3 adds a
one-argument output-function example to the public-rule guidance while
preserving the raw teacher response and isolated program gates. Both retain
the material, budget and two-L4 limits in [Decision 0041](../../docs/decisions/0041-save-nvarc-grammar-and-signature-repairs.md).

Plan digest:
`sha256:3b32c1ce64662c5e108d8dfd494fa51d67b31a4da084d8d3434fb41727e9d77d`.
Offline package: `.irisx/arc-agi-2/qwen35-nvarc/m2-m3/combined-editor-007-reviewed/`.

Exact local bindings (SHA-256):

| Artifact | SHA-256 |
| --- | --- |
| Saved notebook | `a87583ce55e9c541f47ee754bbc8f16afd48291e237afc0224b7a94098b54335` |
| Metadata | `a425f5cb46fc19d1ae5b99f648ffd79a6b9b96f3dbd1b0e5f7a0c2dd84c3881c` |
| Plan bytes | `1ae6543157352f28a29efbb72eab93b8513fd30f5cafa524cd130811989de0a1` |
| Packaged wheel | `63428d783ad231a19f33f51f6004b38d8f5a33d0a1b8add9f4bf48ed6920f2eb` |
| One-save transport script | `2cace96108a777156d64c2d48fe3e670c6a8bd053e05bde382ab81db0956d3a4` |
| SDK request | `20b9c40ac9bb3e0d0798454f36ac64f290ff57343cfbddf4bbb40fe3f1aa0a1c` |
| Provider receipt | `89037b7915f4610eec198cc6c454817582238f144dc073068342e8e36c8949d3` |
| Consumed save ledger | `98f206f36793176dca2ce4118e504271db43420231069441ff319e2a325f14a1` |
| Offline preflight | `988b6c479f44aaf7525a5d18171fc18c38b0c66e0a6af4e3abac50eac854133f` |

The request, receipt, ledger and preflight remain under the ignored local
`.irisx/arc-agi-2/qwen35-nvarc/m2-m3/` directory. Offline exact-package
preflight, approved/draft guards and hardware fixtures passed. The full
repository check passed 274 tests (four optional skips). A tiny real-model
worker produced grammar-complete candidates, and a separate local
counterfactual replay of the saved M3 first-three-stage replies with a
one-argument output program passed the 44-invocation gate and produced five
pairs. Neither is an observation of the full 4B Editor execution; the later
owner ZIP supplies only partial startup evidence.
