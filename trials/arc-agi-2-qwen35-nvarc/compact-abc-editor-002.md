# Compact ABC owner-Editor repair 002

Decision 0045 authorizes exactly one private QUICK_SAVE of
`nvarc-compact-abc-editor-002`; the owner runs it manually. The approved plan
is `configs/compact-abc-editor-002.json`, digest
`sha256:20de08cb39cc4bfe7de02b15d1a350e1dbf4c040c94a5aaf26f4914a93fc5c4e`.

The owner-returned 001 ZIP has SHA-256
`72476b79f7a59f4fb81f6ca1a067177448b9720885ee55ee39c951440d526a12`.
The exact owner file is retained locally as ignored evidence at
`.irisx/arc-agi-2/qwen35-nvarc/m2-m3/compact-abc-editor-001-result.zip`.
All 13 listed ZIP members passed digest verification. `worker-stderr.log`
records `ValidationError: model material has an unlisted or unsafe member` at
`check_materials(base, sft)`, before arm A. No generation, TTT step or A/B/C
result is retained. The parent inventory directly showed four distinct BF16
NVIDIA L4 UUIDs, while the worker saw one selected UUID. The ZIP does not
enumerate the mounted model directory. The diagnosed portability bug is that
the local publishing sidecar was required rather than optional. The repair
still rejects any unlisted file beyond that exact sidecar.

For the next Editor session, attach competition source
`arc-prize-2026-arc-agi-2` at
`/kaggle/input/competitions/arc-prize-2026-arc-agi-2` and select **L4 x4**.
The notebook checks both before model work. It uses one L4 sequentially for
A/B/C. Download `/kaggle/working/結果.zip` after the owner-run session and
return it for separate digest-bound analysis. This save carries no score or
promotion claim.

The sole QUICK_SAVE was accepted as version 1 and is consumed. Notebook:
[nvarc-compact-abc-editor-002](https://www.kaggle.com/code/danielwuu/nvarc-compact-abc-editor-002).
Provider kernel ID: `136279071`. The one request used private visibility,
Internet off, `NvidiaL4`, the three existing Datasets and the official
competition source. The atomic ledger records one send, with no agent start.
No status, logs or outputs were queried. Runtime is unobserved pending the
owner's Editor run.

Exact local bindings (SHA-256):

| Artifact | SHA-256 |
| --- | --- |
| Approved plan digest | `20de08cb39cc4bfe7de02b15d1a350e1dbf4c040c94a5aaf26f4914a93fc5c4e` |
| Saved notebook | `b0aa8b17aaa72ecddaf9c116fe5e48ecf0283c77da10d55be782f51b42b211e7` |
| Metadata | `c1b196a6e80294a1317677107f2bd1fc35d3f44fa95eac5c507b82df0c9157bb` |
| Plan bytes | `f861af4711ec9f5a1cc0d025f6cb507235d0d068e6a3fac07342d9f423a847b3` |
| Packaged wheel | `aa506aa87b1e4e31bc92cdecd3126d7535eadb78f7c6e8bddf8faef5dbc62ac9` |
| One-save transport script | `dd0a267c19e27352d5adc3f8e6570f1b7df9e76ceaaa8716d7fccb975ed47192` |
| SDK request | `c1e90188b7f045b6e55cb99a2bdfbece20c6fb12ef19c430fb8fe31128b580c6` |
| Provider receipt | `0e85f9e9889979cefd6955303198345747c4e569194e275ab00b0b076ddb63b4` |
| Consumed save ledger | `aa049a4fce0ee1f96338829dded5538932638a11f76902d006f69ed15afc3131` |
| Offline preflight | `2d3306b26ba9bdde61ef6afc2d697c6346da53747e2bed167186485c8e087ed4` |

The package and save evidence are under ignored local
`.irisx/arc-agi-2/qwen35-nvarc/m2-m3/`, with the submitted package at
`compact-abc-editor-002-submission/`. Exact-package preflight, the focused
material tests, 282 repository unit tests (four optional skips), repository
invariants and diff whitespace checks passed before the save. The initial
combined `--all` run found the owner ZIP at the active root; it was moved
intact to ignored local evidence and the invariant check then passed.
