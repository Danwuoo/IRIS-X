# Combined 008: owner-Editor startup diagnostic QUICK_SAVE

Decision 0042 authorizes one private QUICK_SAVE of distinct
`nvarc-m2-m3-combined-008`. The owner will start it in Editor and supply
`結果.zip`. No agent session start, monitoring or result retrieval is
authorized. This transport repair adds detailed startup phases and catches
interrupt-class exits for a terminal ZIP; M2/M3 workloads and limits remain
those of combined 007. The precise boundaries are in
[Decision 0042](../../docs/decisions/0042-save-nvarc-startup-diagnostics.md).
The sole QUICK_SAVE was accepted as version 1 on 2026-09-28 and is consumed.
Notebook: [nvarc-m2-m3-combined-008](https://www.kaggle.com/code/danielwuu/nvarc-m2-m3-combined-008).
Provider kernel ID: `136229226`. One SaveKernel request used
`KernelExecutionType.QUICK_SAVE`, private visibility, Internet off and the
existing sources. No agent session was started or queried; runtime was
subsequently observed in the [owner-supplied result ZIP](combined-008-editor-diagnosis.md).
It completed both worker branches, with no accepted M3 pair.

Plan digest:
`sha256:f8644274acac94f860839b1c93c2ddf54e82dd1ccdbc906027bcc5d36b873b49`.
Offline package: `.irisx/arc-agi-2/qwen35-nvarc/m2-m3/combined-editor-008-final/`.

Exact local bindings (SHA-256):

| Artifact | SHA-256 |
| --- | --- |
| Saved notebook | `a5234973af3737da0953cceecbde2db06da4db5def9b73165fbfae2ec000aea7` |
| Metadata | `1fa43660c4d422022b9a687e8e51b498fa092f1e89327305e865821787d48a26` |
| Plan bytes | `1614eea275b5198686b611d6d49efccfad23beaacf27a9073b3e45851e875d33` |
| Packaged wheel | `ba86d6ab2df57030d2da21a72676cba663f01358580e705aa40ac73ae18abce6` |
| One-save transport script | `6e489f2a2f9909809183db7f57aafa19579329b956afa1a57dcc1a0eef2f6808` |
| SDK request | `0f4446d73b8243d7cb885ff89307490c754d828f74e8dfddda3e4c80eaa7777d` |
| Provider receipt | `3730128d14da4cf0ad4700d3773f34f7e645e581b6b11fec6c7a3d20079615bc` |
| Consumed save ledger | `330a128d68f911fa45563fb5533a5fd84aa1ab281d0abfe4e81616eb5323a715` |
| Offline preflight | `ab7ae604ea985aa5c8d0ebad6fafb4670b49d51c5158f6f38e3006626501f36b` |

The request, receipt, ledger and preflight remain under the ignored local
`.irisx/arc-agi-2/qwen35-nvarc/m2-m3/` directory. Offline exact-package
preflight, hardware fixtures, approved/draft guards and the controlled
Torch-import interruption passed. The full repository check passed 274 tests
(four optional skips). These checks do not establish actual GPU or 4B runtime
quality. No agent run, status/log/output query, retrieval, Dataset mutation
or automatic retry is authorized.
