# Compact ABC 002 owner-Editor result

The owner returned `結果.zip` from the manually run
`nvarc-compact-abc-editor-002` version 1. Its SHA-256 is
`965ac0622546efe2d2e996e925ab376f4e219e5657d705cbe45685e8e060f37e`.
The exact file is retained as ignored local evidence at
`.irisx/arc-agi-2/qwen35-nvarc/m2-m3/compact-abc-editor-002-result.zip`.
`verify_abc_zip` checked all 27 listed data members against their byte lengths
and SHA-256 digests, the 002 run ID and the approved Decision 0045 plan digest
`sha256:20de08cb39cc4bfe7de02b15d1a350e1dbf4c040c94a5aaf26f4914a93fc5c4e`.
The embedded plan equals the approved plan. The analysis manifest declares no
evaluator truth.

The parent observed four distinct BF16 NVIDIA L4 UUIDs and the exact official
competition mount at `/kaggle/input/competitions/arc-prize-2026-arc-agi-2`.
The worker verified both exact model material digests and completed arms A, B,
and C in order. `aggregate-terminal.json` reports `complete` after 551.63
seconds. Each arm reports all three public tasks complete. Worker stderr has
library fallback and load notices, without a fatal traceback.

| Arm | Model and adaptation | `00576224` candidates | `c9e6f938` candidates | `0d3d703e` candidates |
| --- | --- | ---: | ---: | ---: |
| A | Compact base, no TTT | 3 | 4 | 4 |
| B | Eight-step SFT pilot export, no TTT | 4 | 4 | 4 |
| C | Same SFT export, one task-local TTT step per task | 4 | 4 | 4 |

Across all nine task/arm rows, the ledger records 18 completed generation
calls, 36 returned sequences and 35 candidate verifications. C completed
three task-local TTT steps using 108, 117 and 120 training tokens, respectively
(345 total). These remain within the approved ceilings of 18 calls, 36
sequences, 36 verifications, three TTT steps and 768 TTT training tokens.
The one fewer verification reflects deduplication of A's four returned
sequences for `00576224` into three ranked candidates, not a failed call.

The comparison is **compute complete and truth free**. Candidate counts and
model verification scores are not ARC exact-match accuracy, pass@1, pass@2 or
oracle coverage. Those remain unknown because no isolated evaluator truth was
used. This observation supplies no promotion claim or new execution authority.
No runtime repair or replacement QUICK_SAVE is needed for the owner's
conditional request. The saved 002 identity and result remain frozen.

Reproduce the truth-free local report with:

```text
python tools/analyze_nvarc_abc.py .irisx/arc-agi-2/qwen35-nvarc/m2-m3/compact-abc-editor-002-result.zip --plan trials/arc-agi-2-qwen35-nvarc/configs/compact-abc-editor-002.json
```
