# Compact base / SFT / SFT+TTT owner-Editor comparison

Decision 0044 authorizes one private QUICK_SAVE of
`nvarc-compact-abc-editor-001`. The approved plan is
`configs/compact-abc-editor-001.json`, digest
`sha256:430f144b6f58482aee2870a857429f9bf73d2126fd64f983518d26d9f8936b97`.
The agent stops at the save receipt. The owner will start the notebook in
Kaggle Editor with two L4 GPUs and Internet disabled, then download
`/kaggle/working/結果.zip` and return it for separate analysis.

The fixed, truth-free public workload is `00576224`, `c9e6f938`, and
`0d3d703e`, all listed as dev parents in the retained eight-step SFT split.
The first task was previously explored in combined 009. A uses the exact
compact base; B and C use the exact 8-step, 2,578-token SFT pilot export. C
alone takes one TTT step per task on public demonstrations. Candidate budgets,
views, decoding and ranking are equal across arms, as bound by the plan and
Decision 0044. This small selected pilot cannot establish broad ARC ability.
Report these public shape/palette strata separately: `00576224` 2×2→6×6
with palette preservation, `c9e6f938` 3×3→3×6 with palette preservation,
and `0d3d703e` 3×3→3×3 with changing palette. All three are outside the
eight exact SFT training parents; known semantic near-duplicate status is
unknown. The local `tools/analyze_nvarc_abc.py` entry verifies member digests
and reports missing tasks as unknown. Only an explicit, legally available
solver-isolated truth file enables oracle coverage and pass@1/pass@2 there.

The sole private QUICK_SAVE was accepted as version 1 on 2026-09-28 and is
consumed. Notebook: [nvarc-compact-abc-editor-001](https://www.kaggle.com/code/danielwuu/nvarc-compact-abc-editor-001).
Provider kernel ID: `136275587`. The one request used
`KernelExecutionType.QUICK_SAVE`, private visibility, Internet off, and the
three existing Datasets in the plan. The local ledger records one send. No
agent session was started or queried. Runtime and result status were
**unobserved at save time** pending the owner's Editor report below.

Exact local bindings (SHA-256):

| Artifact | SHA-256 |
| --- | --- |
| Approved plan digest | `430f144b6f58482aee2870a857429f9bf73d2126fd64f983518d26d9f8936b97` |
| Saved notebook | `9af5c165c5ae94e1b589670ef2e0a2cf9d456e1f09e64035a47b53971234e0d6` |
| Metadata | `644d41942b6c3c28da19f73bfe1cf44c2ff6420db65d3c173c961edac989a4b0` |
| Plan bytes | `8a59f02c91ba9705f5ea6f9670bf53ff0f948ac220305a0142240e00a99b29e8` |
| Packaged wheel | `d56754e63b22f5d05cd205cb80d00ddf9d2177afc8977675443a22ac2bf38ae6` |
| One-save transport script | `6d79ddd4388db539d7ec4f3e52a846234a62b560bef168b24c48da9f3ffdd368` |
| SDK request | `f975b5ca5fb561825daee92d203a5b8c3fc64516f5a67cef6f9f5bb2e8de742d` |
| Provider receipt | `5844eeb8bf5ea32bca335e3775a8e657e98edf0e414d1474b75972faf319a40f` |
| Consumed save ledger | `11af0401cd3a99f14dd25ccc3f0574f6e1a4dabda7acb006560b3dfe79484509` |
| Offline preflight | `cbff9203e76eb963f702912f7a311e7b65a2c379eb65ba6a976102462509c677` |

The package and save evidence are under ignored local
`.irisx/arc-agi-2/qwen35-nvarc/m2-m3/`, with the exact submitted package at
`compact-abc-editor-001-submission/`. The final exact-package preflight,
notebook approved/draft guard checks, tiny real Qwen CPU comparison/reset
replay, digest-tamper rejection and `python tools/repository_check.py --all`
passed. The latter ran 280 tests with four optional skips. The owner then
started the Kaggle Editor run and returned `結果.zip` for digest-bound local
analysis. No score or three-arm result is asserted from this save.

The owner later returned that Editor ZIP. Its SHA-256 is
`72476b79f7a59f4fb81f6ca1a067177448b9720885ee55ee39c951440d526a12`;
all 13 members passed the local digest verifier. Four distinct BF16 L4s were
observed, then the worker failed at the base material inventory gate before
arm A. No A/B/C model result is retained. Decision 0045 and
[`compact-abc-editor-002.md`](compact-abc-editor-002.md) record the distinct
repair and save. The 001 kernel and package remain frozen.
